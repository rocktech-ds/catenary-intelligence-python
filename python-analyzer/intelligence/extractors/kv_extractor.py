"""
AI-Enhanced Key-Value Extractor Module
Extracts title block and key-value pairs from engineering drawings
Combines rule-based extraction with LLM normalization
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import re
import fitz  # PyMuPDF

from loguru import logger
from ..core.config import IntelligenceConfig
from ..models.schemas import KeyValuePair, BoundingBox, AnalysisRequest, ToolStatus
from ..models.target_schemas import TITLE_BLOCK_SCHEMA, PORTUGUESE_PATTERNS
from ..ai.llm_client import extract_with_llm

class KeyValueExtractor:
    """AI-Enhanced extractor for title blocks and key-value pairs"""
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self._loaded = False
        
        # Portuguese regex patterns
        self.kv_patterns = [
            (r"N[º°.\s]*SAP", "N.º SAP"),
            (r"Vers[aã]o", "Versão"),
            (r"Data", "Data"),
            (r"Especialidade|CATEN[ÁA]RIA.*ENERGIA", "Especialidade"),
            (r"Projeto|Projecto", "Projeto"),
            (r"Desenho\s*N[º°]", "Nº DESENHO")
        ]
    
    def load_models(self):
        """Load models for key-value extraction"""
        self._loaded = True
        logger.info("AI-enhanced key-value extractor ready")
    
    async def get_status(self) -> ToolStatus:
        """Get key-value extractor status"""
        return ToolStatus(
            available=self._loaded,
            version="2.0.0-AI"
        )
    
    async def extract_key_values(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract and normalize key-value pairs using AI"""
        try:
            # Stage 1: Extract raw text with PyMuPDF
            doc = fitz.open(file_path)
            page = doc[0]  # Focus on first page
            
            raw_text = self._extract_text_spans(page)
            
            # Stage 2: Rule-based extraction
            rule_based_kv = self._extract_with_rules(raw_text)
            
            # Stage 3: AI normalization and enhancement
            ai_enhanced_kv = await self._enhance_with_ai(raw_text, rule_based_kv)
            
            doc.close()
            
            return {
                'title_block': ai_enhanced_kv.get('fields', {}),
                'document_metadata': {
                    'title': ai_enhanced_kv.get('title'),
                    'specialty': ai_enhanced_kv.get('specialty'),
                    'sap_number': ai_enhanced_kv.get('sap_number'),
                    'version': ai_enhanced_kv.get('version'),
                    'project_code': ai_enhanced_kv.get('project_code'),
                    'date': ai_enhanced_kv.get('date')
                },
                'processing_warnings': []
            }
            
        except Exception as e:
            logger.error(f"Key-value extraction failed: {e}")
            return {
                'title_block': {},
                'document_metadata': {},
                'processing_warnings': [f"KV extraction error: {str(e)}"]
            }
    
    def _extract_text_spans(self, page) -> str:
        """Extract text spans from PDF page"""
        spans = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if text:
                        spans.append(text)
        return " ".join(spans)
    
    def _extract_with_rules(self, raw_text: str) -> Dict[str, Any]:
        """Extract key-value pairs using regex rules"""
        fields = {}
        
        # Apply Portuguese regex patterns
        for pattern, key in self.kv_patterns:
            match = re.search(pattern + r".{0,20}([0-9A-Za-z./-]{2,})", raw_text, re.I)
            if match:
                value = match.group(1).strip()
                if value:
                    fields[key] = value
        
        # Extract title using title cues
        title = None
        for cue_pattern in PORTUGUESE_PATTERNS["title_cues"]:
            match = re.search(cue_pattern, raw_text, re.I)
            if match:
                title = match.group(0).strip()
                break
        
        # Extract project code (e.g., C-160)
        project_match = re.search(r"\b([A-Z]-\d{2,4})\b", raw_text)
        project_code = project_match.group(1) if project_match else None
        
        # Extract date in Portuguese format
        date_match = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", raw_text)
        date = date_match.group(1) if date_match else None
        
        return {
            'title': title,
            'project_code': project_code, 
            'date': date,
            'fields': fields,
            'raw_text_sample': raw_text[:1000]  # First 1000 chars for AI
        }
    
    async def _enhance_with_ai(self, raw_text: str, rule_based: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance extraction results using AI"""
        try:
            system_prompt = """Você é um especialista em desenhos técnicos ferroviários portugueses.
            Extraia e normalize informações do bloco de título com absoluta precisão.
            Foque em:
            - N.º SAP (apenas números)
            - Versão (ex: 01)
            - Data (retorne como YYYY-MM-DD)
            - Código do projeto (ex: C-160)
            - Especialidade (ex: CATENÁRIA E ENERGIA)
            - Título (maiúsculas permitidas)
            
            Se um valor estiver em branco ou não encontrado, retorne null."""
            
            user_prompt = f"""Analise este texto de um desenho técnico e normalize os valores encontrados:
            
            TEXTO BRUTO (primeiros 1000 caracteres):
            {raw_text[:1000]}
            
            VALORES EXTRAÍDOS POR REGEX:
            {rule_based.get('fields', {})}
            
            TÍTULO ENCONTRADO:
            {rule_based.get('title', 'Não encontrado')}
            
            PROJETO:
            {rule_based.get('project_code', 'Não encontrado')}
            
            DATA:
            {rule_based.get('date', 'Não encontrada')}"""
            
            result = await extract_with_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=TITLE_BLOCK_SCHEMA
            )
            
            if result:
                logger.info("✅ AI enhanced title block extraction successful")
                return result
            else:
                logger.warning("AI enhancement failed, using rule-based results")
                return self._format_rule_based_result(rule_based)
                
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
            return self._format_rule_based_result(rule_based)
    
    def _format_rule_based_result(self, rule_based: Dict[str, Any]) -> Dict[str, Any]:
        """Format rule-based results to match schema"""
        fields = rule_based.get('fields', {})
        
        # Convert date format if needed
        date = rule_based.get('date')
        if date and re.match(r"\d{2}[-/]\d{2}[-/]\d{4}", date):
            # Convert DD-MM-YYYY to YYYY-MM-DD
            parts = re.split(r"[-/]", date)
            if len(parts) == 3:
                date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        
        # Determine specialty based on keywords
        raw_text = rule_based.get('raw_text_sample', '')
        specialty = None
        for spec, keywords in PORTUGUESE_PATTERNS["specialty_terms"].items():
            if any(keyword.lower() in raw_text.lower() for keyword in keywords):
                specialty = spec
                break
        
        return {
            'title': rule_based.get('title'),
            'specialty': specialty,
            'sap_number': fields.get('N.º SAP'),
            'version': fields.get('Versão'), 
            'project_code': rule_based.get('project_code'),
            'date': date,
            'fields': {
                'N.º SAP': fields.get('N.º SAP'),
                'Versão': fields.get('Versão'),
                'Data': fields.get('Data')
            }
        }
