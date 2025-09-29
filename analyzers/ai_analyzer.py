"""
AI Analyzer
Integrates with X.AI Grok, Groq Llama, Google Gemini for document analysis
"""

import os
import json
import asyncio
import httpx
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self):
        self.providers = {
            'xai_grok': {
                'base_url': os.getenv('XAI_BASE_URL', 'https://api.x.ai/v1'),
                'api_key': os.getenv('XAI_API_KEY'),
                'model': os.getenv('XAI_MODEL', 'grok-beta'),
                'name': 'X.AI Grok'
            },
            'groq_llama': {
                'base_url': 'https://api.groq.com/openai/v1',
                'api_key': os.getenv('GROQ_API_KEY'),
                'model': 'llama3-8b-8192',
                'name': 'Groq Llama'
            },
            'google_gemini': {
                'base_url': 'https://generativelanguage.googleapis.com/v1beta',
                'api_key': os.getenv('GOOGLE_GEMINI_API_KEY'),
                'model': 'gemini-pro',
                'name': 'Google Gemini'
            }
        }
    
    def get_status(self):
        """Get status of AI providers"""
        status = {
            'available': True,
            'providers': {}
        }
        
        for provider_id, config in self.providers.items():
            has_key = bool(config.get('api_key'))
            status['providers'][provider_id] = {
                'available': has_key,
                'name': config['name'],
                'model': config.get('model'),
                'has_api_key': has_key
            }
            if not has_key:
                status['available'] = False
        
        return status
    
    async def analyze_with_multiple_providers(
        self,
        text_content: str,
        ai_providers: Dict[str, bool],
        analysis_types: Dict[str, bool],
        document_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze with multiple AI providers"""
        
        enabled_providers = [
            provider for provider, enabled in ai_providers.items() 
            if enabled and provider != 'parallel_execution' and provider in self.providers
        ]
        
        if not enabled_providers:
            return {'ai_results': {}}
        
        parallel_execution = ai_providers.get('parallel_execution', True)
        
        logger.info(f"🤖 Starting AI analysis with {len(enabled_providers)} providers")
        logger.info(f"📋 Enabled providers: {enabled_providers}")
        logger.info(f"⚡ Parallel execution: {parallel_execution}")
        
        if parallel_execution:
            # Run all providers in parallel
            tasks = [
                self.analyze_with_provider(provider, text_content, analysis_types, document_context)
                for provider in enabled_providers
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            ai_results = {}
            for i, result in enumerate(results):
                provider = enabled_providers[i]
                if isinstance(result, Exception):
                    logger.error(f"❌ {provider} failed: {result}")
                    ai_results[provider] = {
                        'success': False,
                        'provider': provider,
                        'error': str(result)
                    }
                else:
                    ai_results[provider] = result
        else:
            # Run providers sequentially
            ai_results = {}
            for provider in enabled_providers:
                try:
                    result = await self.analyze_with_provider(
                        provider, text_content, analysis_types, document_context
                    )
                    ai_results[provider] = result
                except Exception as e:
                    logger.error(f"❌ {provider} failed: {e}")
                    ai_results[provider] = {
                        'success': False,
                        'provider': provider,
                        'error': str(e)
                    }
        
        # Create consensus results
        consensus = self.create_ai_consensus(ai_results)
        
        return {
            'ai_results': ai_results,
            'ai_consensus': consensus
        }
    
    async def analyze_with_provider(
        self,
        provider_id: str,
        text_content: str,
        analysis_types: Dict[str, bool],
        document_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze with a specific AI provider"""
        
        config = self.providers[provider_id]
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"🔍 Starting {config['name']} analysis")
            
            # Build analysis prompt
            prompt = self.build_analysis_prompt(text_content, analysis_types, document_context)
            
            # Call AI API
            if provider_id == 'google_gemini':
                response_data = await self.call_gemini_api(config, prompt)
            else:
                response_data = await self.call_openai_compatible_api(config, prompt)
            
            # Parse response
            raw_response = self.extract_response_text(response_data, provider_id)
            parsed_response = self.parse_ai_response(raw_response, analysis_types)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            result = {
                'success': True,
                'provider': provider_id,
                'model': config['model'],
                'raw_response': raw_response,
                'parsed_response': parsed_response,
                'processing_time': processing_time,
                'tokens_used': self.extract_token_usage(response_data, provider_id)
            }
            
            logger.info(f"✅ {config['name']} completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"❌ {config['name']} failed: {e}")
            
            return {
                'success': False,
                'provider': provider_id,
                'model': config['model'],
                'error': str(e),
                'processing_time': processing_time
            }
    
    def build_analysis_prompt(
        self,
        text_content: str,
        analysis_types: Dict[str, bool],
        document_context: Dict[str, Any]
    ) -> str:
        """Build analysis prompt based on enabled analysis types"""
        
        prompt = f"Analyze this technical railway document:\n\n{text_content[:4000]}\n\n"
        prompt += "Please provide a structured analysis covering:\n"
        
        if analysis_types.get('nomenclaturas', True):
            prompt += "- NOMENCLATURAS: Extract all technical codes, part numbers, SAP codes, C-codes (e.g., C-160, C-180), MT.CAT codes, and unique identifiers\n"
        
        if analysis_types.get('bom_extraction', False):
            prompt += "- BOM EXTRACTION: Extract bill of materials, component lists, quantities, part numbers, descriptions\n"
        
        if analysis_types.get('component_detection', False):
            prompt += "- COMPONENT DETECTION: Identify catenary components, electrical equipment, hardware, insulators\n"
        
        if analysis_types.get('ai_summary', False):
            prompt += "- SUMMARY: Provide intelligent summary of key points, purpose, and main content\n"
        
        if analysis_types.get('table_analysis', False):
            prompt += "- TABLE ANALYSIS: Analyze any tables, specifications, or structured data\n"
        
        if analysis_types.get('metadata_extraction', False):
            prompt += "- METADATA: Extract document metadata, dates, revision numbers, approval information\n"
        
        prompt += """
Return the response in a structured JSON format:
{
  "nomenclaturas": ["array", "of", "codes"],
  "technical_codes": {
    "c_codes": ["C-160", "C-180"],
    "sap_codes": ["75113048", "75113070"],
    "mt_cat_codes": ["MT.CAT.003"],
    "part_numbers": ["manufacturer parts"]
  },
  "summary": "Intelligent summary of the document",
  "document_type": "detected document type",
  "bom_analysis": {
    "has_bom": true,
    "items": [{"part_number": "", "description": "", "quantity": ""}]
  },
  "components": [{"name": "", "code": "", "description": ""}],
  "key_information": ["key", "points"],
  "confidence": 0.95
}"""
        
        return prompt
    
    async def call_openai_compatible_api(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Call OpenAI-compatible API (X.AI, Groq)"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers={
                    'Authorization': f"Bearer {config['api_key']}",
                    'Content-Type': 'application/json'
                },
                json={
                    'model': config['model'],
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 4000
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def call_gemini_api(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Call Google Gemini API"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{config['base_url']}/models/{config['model']}:generateContent?key={config['api_key']}",
                headers={'Content-Type': 'application/json'},
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {
                        'temperature': 0.1,
                        'maxOutputTokens': 4000
                    }
                }
            )
            response.raise_for_status()
            return response.json()
    
    def extract_response_text(self, data: Dict[str, Any], provider_id: str) -> str:
        """Extract response text from different API formats"""
        if provider_id == 'google_gemini':
            return data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        else:
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
    
    def extract_token_usage(self, data: Dict[str, Any], provider_id: str) -> int:
        """Extract token usage from API response"""
        if provider_id == 'google_gemini':
            return data.get('usageMetadata', {}).get('totalTokenCount', 0)
        else:
            return data.get('usage', {}).get('total_tokens', 0)
    
    def parse_ai_response(self, raw_response: str, analysis_types: Dict[str, bool]) -> Dict[str, Any]:
        """Parse AI response into structured format"""
        try:
            # Clean and parse JSON
            cleaned_response = raw_response.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(cleaned_response)
            
            return {
                'nomenclaturas': parsed.get('nomenclaturas', []),
                'technical_codes': parsed.get('technical_codes', {}),
                'summary': parsed.get('summary', ''),
                'document_type': parsed.get('document_type', ''),
                'bom_analysis': parsed.get('bom_analysis'),
                'components': parsed.get('components', []),
                'key_information': parsed.get('key_information', []),
                'confidence': parsed.get('confidence', 0.8)
            }
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse AI response as JSON, using fallback")
            
            # Fallback parsing
            nomenclaturas = self.extract_nomenclaturas_from_text(raw_response)
            
            return {
                'nomenclaturas': nomenclaturas,
                'technical_codes': {'nomenclaturas': nomenclaturas},
                'summary': raw_response[:500] + '...' if len(raw_response) > 500 else raw_response,
                'confidence': 0.5
            }
    
    def extract_nomenclaturas_from_text(self, text: str) -> List[str]:
        """Extract nomenclaturas using regex patterns"""
        import re
        
        patterns = [
            r'\bC-\d+\b',           # C-codes
            r'\b\d{8}\b',          # 8-digit SAP codes
            r'\bMT\.CAT\.\d+\b',   # MT.CAT codes
            r'\b[A-Z]{2,4}-\d+\b', # General equipment codes
        ]
        
        found = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            found.update(matches)
        
        return list(found)
    
    def create_ai_consensus(self, ai_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create consensus from multiple AI provider results"""
        successful_results = [
            result for result in ai_results.values() 
            if result.get('success') and result.get('parsed_response')
        ]
        
        if not successful_results:
            return {
                'consensus_confidence': 0,
                'agreements': [],
                'disagreements': [],
                'final_nomenclaturas': [],
                'final_summary': 'No successful AI analysis results'
            }
        
        # Collect nomenclaturas from all providers
        all_nomenclaturas = set()
        nomenclaturas_by_provider = {}
        
        for result in successful_results:
            provider_nomenclaturas = []
            parsed = result['parsed_response']
            
            # Collect from various sources
            if parsed.get('nomenclaturas'):
                provider_nomenclaturas.extend(parsed['nomenclaturas'])
            
            if parsed.get('technical_codes'):
                tc = parsed['technical_codes']
                if tc.get('nomenclaturas'):
                    provider_nomenclaturas.extend(tc['nomenclaturas'])
                if tc.get('c_codes'):
                    provider_nomenclaturas.extend(tc['c_codes'])
                if tc.get('sap_codes'):
                    provider_nomenclaturas.extend(tc['sap_codes'])
            
            nomenclaturas_by_provider[result['provider']] = provider_nomenclaturas
            all_nomenclaturas.update(provider_nomenclaturas)
        
        # Find agreements and disagreements
        agreements = []
        disagreements = []
        
        for nomenclatura in all_nomenclaturas:
            providers_with_this = [
                provider for provider, noms in nomenclaturas_by_provider.items()
                if nomenclatura in noms
            ]
            
            if len(providers_with_this) > 1:
                agreements.append(nomenclatura)
            else:
                disagreements.append(nomenclatura)
        
        # Calculate consensus confidence
        total_items = len(agreements) + len(disagreements)
        consensus_confidence = len(agreements) / total_items if total_items > 0 else 0
        
        # Create final summary
        summaries = [
            result['parsed_response'].get('summary', '')
            for result in successful_results
            if result['parsed_response'].get('summary')
        ]
        
        final_summary = f"Consenso de {len(successful_results)} AIs: " + " | ".join(summaries[:2]) if summaries else "No summaries available"
        
        return {
            'consensus_confidence': consensus_confidence,
            'agreements': agreements,
            'disagreements': disagreements,
            'final_nomenclaturas': agreements,  # Prioritize agreed-upon items
            'final_summary': final_summary
        }