"""
Universal LLM Client for PDF Intelligence
Supports xAI Grok, Google Gemini, and Groq with consistent interface
"""
import os
import json
import httpx
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import time
from functools import wraps

from loguru import logger

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Gemini SDK not available")

class LLMProvider(str, Enum):
    XAI = "xai"
    GEMINI = "gemini"  
    GROQ = "groq"

@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout: int = 30
    max_retries: int = 2
    retry_delay: float = 1.0

def retry_on_failure(max_retries: int = 2, delay: float = 1.0):
    """Decorator for retrying failed LLM calls"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
            return None
        return wrapper
    return decorator

class LLMClient:
    """Universal LLM client supporting multiple providers"""
    
    def __init__(self):
        self.providers = self._initialize_providers()
        self.default_provider = self._get_default_provider()
        
    def _initialize_providers(self) -> Dict[LLMProvider, LLMConfig]:
        """Initialize all available providers"""
        providers = {}
        
        # xAI Grok (OpenAI-compatible)
        if os.getenv("XAI_API_KEY"):
            providers[LLMProvider.XAI] = LLMConfig(
                provider=LLMProvider.XAI,
                api_key=os.getenv("XAI_API_KEY"),
                base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
                model=os.getenv("XAI_MODEL", "grok-beta"),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS_PER_DOC", "8000")),
                timeout=int(os.getenv("LLM_TIMEOUT_S", "30"))
            )
        
        # Groq (OpenAI-compatible)
        if os.getenv("GROQ_API_KEY"):
            providers[LLMProvider.GROQ] = LLMConfig(
                provider=LLMProvider.GROQ,
                api_key=os.getenv("GROQ_API_KEY"),
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS_PER_DOC", "8000")),
                timeout=int(os.getenv("LLM_TIMEOUT_S", "30"))
            )
        
        # Google Gemini (native SDK)
        if os.getenv("GOOGLE_GEMINI_API_KEY") and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))
                providers[LLMProvider.GEMINI] = LLMConfig(
                    provider=LLMProvider.GEMINI,
                    api_key=os.getenv("GOOGLE_GEMINI_API_KEY"),
                    model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                    max_tokens=int(os.getenv("LLM_MAX_TOKENS_PER_DOC", "8000")),
                    timeout=int(os.getenv("LLM_TIMEOUT_S", "30"))
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        
        return providers
    
    def _get_default_provider(self) -> Optional[LLMProvider]:
        """Get default provider based on environment"""
        provider_order = [LLMProvider.GROQ, LLMProvider.GEMINI, LLMProvider.XAI]
        for provider in provider_order:
            if provider in self.providers:
                return provider
        return None
    
    def is_enabled(self) -> bool:
        """Check if LLM processing is enabled"""
        return (
            os.getenv("LLM_ENABLED", "false").lower() == "true" and 
            len(self.providers) > 0
        )
    
    async def extract_structured_json(
        self, 
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        provider: Optional[LLMProvider] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from text using LLM
        Tries providers in order with fallback
        """
        if not self.is_enabled():
            logger.warning("LLM processing disabled")
            return {}
        
        target_provider = provider or self.default_provider
        if not target_provider:
            logger.error("No LLM providers available")
            return {}
        
        # Try primary provider
        try:
            result = await self._call_provider(
                target_provider, system_prompt, user_prompt, schema
            )
            if result:
                logger.info(f"✅ LLM extraction successful with {target_provider.value}")
                return result
        except Exception as e:
            logger.warning(f"Primary provider {target_provider.value} failed: {e}")
        
        # Try fallback providers if enabled
        if fallback:
            for fallback_provider in self.providers:
                if fallback_provider != target_provider:
                    try:
                        result = await self._call_provider(
                            fallback_provider, system_prompt, user_prompt, schema
                        )
                        if result:
                            logger.info(f"✅ LLM extraction successful with fallback {fallback_provider.value}")
                            return result
                    except Exception as e:
                        logger.warning(f"Fallback provider {fallback_provider.value} failed: {e}")
        
        logger.error("All LLM providers failed")
        return {}
    
    @retry_on_failure(max_retries=2, delay=1.0)
    async def _call_provider(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Call specific provider with retry logic"""
        config = self.providers[provider]
        
        start_time = time.time()
        
        try:
            if provider == LLMProvider.GEMINI and GEMINI_AVAILABLE:
                result = await self._call_gemini(config, system_prompt, user_prompt, schema)
            else:
                result = await self._call_openai_compatible(config, system_prompt, user_prompt, schema)
            
            duration = time.time() - start_time
            logger.debug(f"LLM call to {provider.value} took {duration:.2f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"LLM call to {provider.value} failed after {duration:.2f}s: {e}")
            raise
    
    async def _call_openai_compatible(
        self,
        config: LLMConfig,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI-compatible API (xAI, Groq)"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        
        # Truncate prompts if too long
        max_prompt_length = config.max_tokens * 3  # Rough estimate
        if len(user_prompt) > max_prompt_length:
            user_prompt = user_prompt[:max_prompt_length] + "..."
            logger.warning(f"User prompt truncated to {max_prompt_length} characters")
        
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": min(config.max_tokens, 4000),  # Provider limits
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {
                    "role": "system", 
                    "content": f"Return ONLY valid JSON matching this schema: {json.dumps(schema)}"
                }
            ]
        }
        
        timeout = httpx.Timeout(config.timeout)
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{config.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "choices" not in result or not result["choices"]:
                    raise ValueError("No choices in API response")
                
                content = result["choices"][0]["message"]["content"]
                
                if not content:
                    raise ValueError("Empty response from API")
                
                return self._parse_json_response(content)
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.TimeoutException:
            logger.error("Request timeout")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI-compatible call: {e}")
            raise
    
    async def _call_gemini(
        self,
        config: LLMConfig,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Call Google Gemini API with function calling"""
        if not GEMINI_AVAILABLE:
            raise ValueError("Gemini SDK not available")
        
        try:
            # Truncate prompts if too long
            max_prompt_length = config.max_tokens * 3
            if len(user_prompt) > max_prompt_length:
                user_prompt = user_prompt[:max_prompt_length] + "..."
                logger.warning(f"User prompt truncated for Gemini to {max_prompt_length} characters")
            
            model = genai.GenerativeModel(
                model_name=config.model,
                system_instruction=system_prompt,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            prompt = f"{user_prompt}\n\nReturn ONLY valid JSON matching schema: {json.dumps(schema)}"
            
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=config.temperature,
                    max_output_tokens=min(config.max_tokens, 8192),  # Gemini limit
                )
            )
            
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
            
            content = response.text
            return self._parse_json_response(content)
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response with error handling"""
        try:
            # Clean up response
            content = content.strip()
            
            # Remove markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            content = content.strip()
            
            # Parse JSON
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            
            # Try to fix common issues
            try:
                # Remove trailing commas
                content = content.rstrip(',')
                return json.loads(content)
            except:
                pass
            
            return None

# Global instance
llm_client = LLMClient()

async def extract_with_llm(
    system_prompt: str,
    user_prompt: str,
    schema: Dict[str, Any],
    provider: Optional[LLMProvider] = None
) -> Dict[str, Any]:
    """Convenience function for LLM extraction"""
    return await llm_client.extract_structured_json(
        system_prompt, user_prompt, schema, provider
    )