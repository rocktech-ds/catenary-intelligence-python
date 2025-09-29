"""
Free External Services Manager
Coordinates all FREE external APIs and services to maximize capabilities without cost
Includes usage tracking, rotation, fallbacks, and caching
"""
import os
import json
import base64
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

import httpx
from loguru import logger

class FreeServiceLimits:
    """Track usage limits for free services"""
    
    SERVICES = {
        # Vision/OCR Services (FREE TIERS)
        "google_vision": {"limit": 1000, "period": "month", "current": 0},
        "azure_vision": {"limit": 5000, "period": "month", "current": 0},
        "ocr_space": {"limit": 25000, "period": "month", "current": 0},
        "aws_textract": {"limit": 1000, "period": "month", "current": 0},
        
        # AI/ML Services (FREE TIERS)
        "huggingface": {"limit": 1000, "period": "month", "current": 0},
        "openai_free": {"limit": 100, "period": "month", "current": 0},
        "anthropic_free": {"limit": 100, "period": "month", "current": 0},
        
        # Document Processing (UNLIMITED FREE)
        "tabula": {"limit": -1, "period": "unlimited", "current": 0},
        "camelot": {"limit": -1, "period": "unlimited", "current": 0},
        "pdfquery": {"limit": -1, "period": "unlimited", "current": 0},
        "pymupdf": {"limit": -1, "period": "unlimited", "current": 0},
        "pdfplumber": {"limit": -1, "period": "unlimited", "current": 0},
    }
    
    def __init__(self):
        self.usage_file = Path("/tmp/free_services_usage.json")
        self.load_usage()
    
    def load_usage(self):
        """Load usage statistics from file"""
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    # Check if it's from current month
                    last_reset = datetime.fromisoformat(data.get("last_reset", "2000-01-01"))
                    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    
                    if last_reset < current_month:
                        # Reset monthly counters
                        self.reset_monthly_usage()
                    else:
                        # Load existing usage
                        for service, usage_data in data.get("services", {}).items():
                            if service in self.SERVICES:
                                self.SERVICES[service]["current"] = usage_data.get("current", 0)
        except Exception as e:
            logger.warning(f"Could not load usage data: {e}")
            self.reset_monthly_usage()
    
    def save_usage(self):
        """Save usage statistics to file"""
        try:
            data = {
                "last_reset": datetime.now().isoformat(),
                "services": self.SERVICES
            }
            with open(self.usage_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Could not save usage data: {e}")
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters"""
        for service in self.SERVICES:
            if self.SERVICES[service]["period"] == "month":
                self.SERVICES[service]["current"] = 0
        self.save_usage()
    
    def can_use_service(self, service: str) -> bool:
        """Check if service is available (under limits)"""
        if service not in self.SERVICES:
            return False
        
        service_data = self.SERVICES[service]
        if service_data["limit"] == -1:  # Unlimited
            return True
        
        return service_data["current"] < service_data["limit"]
    
    def increment_usage(self, service: str):
        """Increment usage counter for service"""
        if service in self.SERVICES:
            self.SERVICES[service]["current"] += 1
            self.save_usage()
    
    def get_available_services(self, category: str = None) -> List[str]:
        """Get list of available services"""
        available = []
        for service, data in self.SERVICES.items():
            if self.can_use_service(service):
                if category is None:
                    available.append(service)
                elif category == "vision" and service in ["google_vision", "azure_vision", "ocr_space", "aws_textract"]:
                    available.append(service)
                elif category == "ai" and service in ["huggingface", "openai_free", "anthropic_free"]:
                    available.append(service)
                elif category == "tables" and service in ["tabula", "camelot", "pdfquery"]:
                    available.append(service)
        return available

class FreeServicesManager:
    """Manages all free external services with intelligent routing and fallbacks"""
    
    def __init__(self):
        self.limits = FreeServiceLimits()
        self.cache_dir = Path("/tmp/free_services_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # Service configurations
        self.vision_services = self._init_vision_services()
        self.ai_services = self._init_ai_services()
        self.document_services = self._init_document_services()
    
    def _init_vision_services(self) -> Dict[str, Dict]:
        """Initialize vision service configurations"""
        return {
            "google_vision": {
                "url": "https://vision.googleapis.com/v1/images:annotate",
                "key": os.getenv("GOOGLE_CLOUD_API_KEY"),
                "headers": lambda key: {"Content-Type": "application/json"},
                "enabled": bool(os.getenv("GOOGLE_CLOUD_API_KEY"))
            },
            "azure_vision": {
                "url": "https://westeurope.api.cognitive.microsoft.com/vision/v3.2/ocr",
                "key": os.getenv("AZURE_VISION_KEY"),
                "headers": lambda key: {
                    "Ocp-Apim-Subscription-Key": key,
                    "Content-Type": "application/json"
                },
                "enabled": bool(os.getenv("AZURE_VISION_KEY"))
            },
            "ocr_space": {
                "url": "https://api.ocr.space/parse/image",
                "key": os.getenv("OCR_SPACE_API_KEY", "helloworld"),  # Free key available
                "headers": lambda key: {"apikey": key},
                "enabled": True  # Always available with free key
            },
            "aws_textract": {
                "region": "us-east-1",
                "key": os.getenv("AWS_ACCESS_KEY_ID"),
                "secret": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "enabled": bool(os.getenv("AWS_ACCESS_KEY_ID"))
            }
        }
    
    def _init_ai_services(self) -> Dict[str, Dict]:
        """Initialize AI service configurations"""
        return {
            "huggingface": {
                "url": "https://api-inference.huggingface.co/models/",
                "key": os.getenv("HUGGINGFACE_API_KEY"),
                "models": {
                    "document_qa": "deepset/roberta-base-squad2",
                    "text_classification": "cardiffnlp/twitter-roberta-base-sentiment-latest",
                    "ner": "dbmdz/bert-large-cased-finetuned-conll03-english"
                },
                "enabled": bool(os.getenv("HUGGINGFACE_API_KEY"))
            },
            "openai_free": {
                "url": "https://api.openai.com/v1/chat/completions",
                "key": os.getenv("OPENAI_API_KEY"),
                "model": "gpt-3.5-turbo",
                "enabled": bool(os.getenv("OPENAI_API_KEY"))
            },
            "anthropic_free": {
                "url": "https://api.anthropic.com/v1/messages",
                "key": os.getenv("ANTHROPIC_API_KEY"),
                "model": "claude-3-haiku-20240307",
                "enabled": bool(os.getenv("ANTHROPIC_API_KEY"))
            }
        }
    
    def _init_document_services(self) -> Dict[str, bool]:
        """Initialize document processing services (all free)"""
        return {
            "tabula": True,      # Free table extraction
            "camelot": True,     # Free advanced table extraction  
            "pdfquery": True,    # Free PDF querying
            "pymupdf": True,     # Free PDF processing
            "pdfplumber": True   # Free PDF analysis
        }
    
    def _get_cache_key(self, service: str, params: Dict) -> str:
        """Generate cache key for request"""
        cache_data = f"{service}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if available and not expired"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Check if cache is still valid (24 hours)
                    cached_time = datetime.fromisoformat(data["timestamp"])
                    if datetime.now() - cached_time < timedelta(hours=24):
                        logger.debug(f"Using cached result for {cache_key}")
                        return data["result"]
        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
        return None
    
    def _save_cached_result(self, cache_key: str, result: Dict):
        """Save result to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "result": result
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")
    
    async def extract_text_from_image(self, image_data: bytes, prefer_service: str = None) -> Optional[str]:
        """Extract text from image using free OCR services with fallbacks"""
        
        # Try to use preferred service first
        if prefer_service and self.limits.can_use_service(prefer_service):
            try:
                result = await self._call_ocr_service(prefer_service, image_data)
                if result:
                    self.limits.increment_usage(prefer_service)
                    return result
            except Exception as e:
                logger.warning(f"Preferred service {prefer_service} failed: {e}")
        
        # Try available services in order of generosity (most free requests first)
        service_order = ["ocr_space", "azure_vision", "google_vision", "aws_textract"]
        
        for service in service_order:
            if not self.limits.can_use_service(service):
                continue
            
            try:
                result = await self._call_ocr_service(service, image_data)
                if result:
                    self.limits.increment_usage(service)
                    logger.info(f"✅ OCR successful with {service}")
                    return result
            except Exception as e:
                logger.warning(f"OCR service {service} failed: {e}")
                continue
        
        logger.error("All OCR services failed or exhausted")
        return None
    
    async def _call_ocr_service(self, service: str, image_data: bytes) -> Optional[str]:
        """Call specific OCR service"""
        
        # Check cache first
        cache_key = self._get_cache_key(service, {"image_hash": hashlib.md5(image_data).hexdigest()})
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result.get("text")
        
        config = self.vision_services.get(service)
        if not config or not config["enabled"]:
            return None
        
        text_result = None
        
        if service == "ocr_space":
            text_result = await self._call_ocr_space(image_data, config)
        elif service == "google_vision":
            text_result = await self._call_google_vision(image_data, config)
        elif service == "azure_vision":
            text_result = await self._call_azure_vision(image_data, config)
        elif service == "aws_textract":
            text_result = await self._call_aws_textract(image_data, config)
        
        # Cache successful results
        if text_result:
            self._save_cached_result(cache_key, {"text": text_result})
        
        return text_result
    
    async def _call_ocr_space(self, image_data: bytes, config: Dict) -> Optional[str]:
        """Call OCR.space API (25K requests/month free)"""
        try:
            # Convert image to base64
            image_b64 = base64.b64encode(image_data).decode()
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    config["url"],
                    data={
                        "base64Image": f"data:image/png;base64,{image_b64}",
                        "language": "por",  # Portuguese
                        "detectOrientation": "true",
                        "scale": "true",
                        "OCREngine": "2"
                    },
                    headers=config["headers"](config["key"])
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("OCRExitCode") == 1:
                        # Extract text from all regions
                        text_parts = []
                        for parsed_result in result.get("ParsedResults", []):
                            text_parts.append(parsed_result.get("ParsedText", ""))
                        return "\n".join(text_parts)
                
        except Exception as e:
            logger.error(f"OCR.space API error: {e}")
        
        return None
    
    async def _call_google_vision(self, image_data: bytes, config: Dict) -> Optional[str]:
        """Call Google Cloud Vision API (1K requests/month free)"""
        try:
            image_b64 = base64.b64encode(image_data).decode()
            
            payload = {
                "requests": [{
                    "image": {"content": image_b64},
                    "features": [{"type": "TEXT_DETECTION"}]
                }]
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{config['url']}?key={config['key']}",
                    json=payload,
                    headers=config["headers"](config["key"])
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "responses" in result and result["responses"]:
                        annotations = result["responses"][0].get("textAnnotations", [])
                        if annotations:
                            return annotations[0].get("description", "")
                
        except Exception as e:
            logger.error(f"Google Vision API error: {e}")
        
        return None
    
    async def _call_azure_vision(self, image_data: bytes, config: Dict) -> Optional[str]:
        """Call Azure Computer Vision API (5K requests/month free)"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    config["url"],
                    data=image_data,
                    headers={
                        **config["headers"](config["key"]),
                        "Content-Type": "application/octet-stream"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text_parts = []
                    
                    for region in result.get("regions", []):
                        for line in region.get("lines", []):
                            line_text = " ".join([word["text"] for word in line.get("words", [])])
                            text_parts.append(line_text)
                    
                    return "\n".join(text_parts)
                
        except Exception as e:
            logger.error(f"Azure Vision API error: {e}")
        
        return None
    
    async def _call_aws_textract(self, image_data: bytes, config: Dict) -> Optional[str]:
        """Call AWS Textract API (1K pages/month free)"""
        # This would require boto3 and AWS credentials
        # For now, return None - can be implemented if AWS credentials are available
        return None
    
    async def enhance_with_ai(self, text: str, task: str, prefer_service: str = None) -> Optional[Dict]:
        """Use free AI services to enhance/analyze text"""
        
        # Try preferred service first
        if prefer_service and self.limits.can_use_service(prefer_service):
            try:
                result = await self._call_ai_service(prefer_service, text, task)
                if result:
                    self.limits.increment_usage(prefer_service)
                    return result
            except Exception as e:
                logger.warning(f"Preferred AI service {prefer_service} failed: {e}")
        
        # Try available AI services
        service_order = ["huggingface", "anthropic_free", "openai_free"]
        
        for service in service_order:
            if not self.limits.can_use_service(service):
                continue
            
            try:
                result = await self._call_ai_service(service, text, task)
                if result:
                    self.limits.increment_usage(service)
                    logger.info(f"✅ AI enhancement successful with {service}")
                    return result
            except Exception as e:
                logger.warning(f"AI service {service} failed: {e}")
                continue
        
        return None
    
    async def _call_ai_service(self, service: str, text: str, task: str) -> Optional[Dict]:
        """Call specific AI service"""
        config = self.ai_services.get(service)
        if not config or not config["enabled"]:
            return None
        
        # Cache check
        cache_key = self._get_cache_key(service, {"text": text[:100], "task": task})
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = None
        
        if service == "huggingface":
            result = await self._call_huggingface(text, task, config)
        elif service == "openai_free":
            result = await self._call_openai(text, task, config)
        elif service == "anthropic_free":
            result = await self._call_anthropic(text, task, config)
        
        if result:
            self._save_cached_result(cache_key, result)
        
        return result
    
    async def _call_huggingface(self, text: str, task: str, config: Dict) -> Optional[Dict]:
        """Call Hugging Face Inference API (1K requests/month free)"""
        try:
            model = config["models"].get(task, config["models"]["document_qa"])
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{config['url']}{model}",
                    json={"inputs": text},
                    headers={"Authorization": f"Bearer {config['key']}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                
        except Exception as e:
            logger.error(f"Hugging Face API error: {e}")
        
        return None
    
    async def _call_openai(self, text: str, task: str, config: Dict) -> Optional[Dict]:
        """Call OpenAI API with free tier"""
        try:
            prompt = self._build_prompt_for_task(text, task)
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    config["url"],
                    json={
                        "model": config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "temperature": 0.1
                    },
                    headers={"Authorization": f"Bearer {config['key']}"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {"response": result["choices"][0]["message"]["content"]}
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
        
        return None
    
    async def _call_anthropic(self, text: str, task: str, config: Dict) -> Optional[Dict]:
        """Call Anthropic Claude API with free tier"""
        try:
            prompt = self._build_prompt_for_task(text, task)
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    config["url"],
                    json={
                        "model": config["model"],
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    headers={
                        "x-api-key": config["key"],
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {"response": result["content"][0]["text"]}
                
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
        
        return None
    
    def _build_prompt_for_task(self, text: str, task: str) -> str:
        """Build appropriate prompt for AI task"""
        prompts = {
            "extract_stamps": f"Extract stamp and approval information from this engineering document text: {text}",
            "normalize_text": f"Clean and normalize this technical text: {text}",
            "extract_metadata": f"Extract document metadata from: {text}",
            "extract_components": f"Extract component information from this BOM/parts list: {text}"
        }
        
        return prompts.get(task, f"Analyze this text: {text}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        status = {
            "vision_services": {},
            "ai_services": {},
            "document_services": self.document_services.copy(),
            "usage_summary": {}
        }
        
        # Vision services status
        for service, config in self.vision_services.items():
            service_limits = self.limits.SERVICES.get(service, {})
            status["vision_services"][service] = {
                "enabled": config["enabled"],
                "available": self.limits.can_use_service(service),
                "used": service_limits.get("current", 0),
                "limit": service_limits.get("limit", 0)
            }
        
        # AI services status
        for service, config in self.ai_services.items():
            service_limits = self.limits.SERVICES.get(service, {})
            status["ai_services"][service] = {
                "enabled": config["enabled"],
                "available": self.limits.can_use_service(service),
                "used": service_limits.get("current", 0),
                "limit": service_limits.get("limit", 0)
            }
        
        # Usage summary
        total_available = sum(1 for s in self.limits.SERVICES if self.limits.can_use_service(s))
        status["usage_summary"] = {
            "total_services": len(self.limits.SERVICES),
            "available_services": total_available,
            "cache_entries": len(list(self.cache_dir.glob("*.json")))
        }
        
        return status

# Global instance
free_services = FreeServicesManager()