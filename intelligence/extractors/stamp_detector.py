"""
Lightweight Stamp Detector Module
Detects engineering stamps, seals, and approval marks using efficient text pattern matching
Optimized for low-resource VPS deployment
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
from datetime import datetime
import re

import fitz  # PyMuPDF
from loguru import logger

from ..core.config import IntelligenceConfig
from ..models.schemas import StampData, BoundingBox, AnalysisRequest, ToolStatus
from ..models.target_schemas import PORTUGUESE_PATTERNS
from ..utils.text import clean_text, parse_date, extract_authors
from ..ai.llm_client import llm_client
import base64
import httpx
import json

class StampDetector:
    """Detects and analyzes engineering stamps and seals"""
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self._loaded = False
    
    def load_models(self):
        """Load models for stamp detection"""
        self._loaded = True
        logger.info("Stamp detector ready")
    
    async def get_status(self) -> ToolStatus:
        """Get stamp detector status"""
        return ToolStatus(
            available=self._loaded,
            version="1.0.0"
        )
    
    async def detect_stamps(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Detect engineering stamps using lightweight text pattern matching"""
        stamps = []
        processing_warnings = []
        
        try:
            # Use PyMuPDF text extraction (very fast, minimal resources)
            pdf_doc = fitz.open(str(file_path))
            
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                
                # Extract text with positioning info
                text_dict = page.get_text("dict")
                page_stamps = self._detect_stamps_from_text(text_dict, page_num)
                stamps.extend(page_stamps)
            
            pdf_doc.close()
            
            # Remove duplicates
            stamps = self._remove_duplicate_stamps(stamps)
            
            # Enhance with AI if enabled (external compute, no VPS load)
            if request.ai_enhancement and request.ai_enhancement.enabled:
                stamps = await self._enhance_stamps_with_ai(stamps, request)
            
        except Exception as e:
            logger.error(f"Stamp detection failed: {e}")
            processing_warnings.append(f"Stamp detection error: {str(e)}")
        
        return {
            'stamps': stamps,
            'processing_warnings': processing_warnings
        }
    
    def _detect_stamps_from_text(self, text_dict: Dict, page_num: int) -> List[StampData]:
        """Detect stamps using text pattern matching (lightweight)"""
        stamps = []
        
        # Stamp detection patterns (Portuguese engineering documents)
        stamp_patterns = {
            'approval': [
                r'aprovado\s+por[:\s]*(.*?)(?:data[:\s]*(\d{2}[-/]\d{2}[-/]\d{4}))?',
                r'eng[º°]?\s+([^\n]{5,30})',
                r'responsável[:\s]*(.*?)(?:data)?',
            ],
            'revision': [
                r'rev[\.,]?\s*([A-Z0-9]+)',
                r'revisão[:\s]*([A-Z0-9]+)',
                r'alteração[:\s]*(.*?)(?:data[:\s]*(\d{2}[-/]\d{2}[-/]\d{4}))?',
            ],
            'professional': [
                r'eng[º°]?\s+(civil|mecânico|elétrico|eletrotécnico)',
                r'crea[:\s]*([0-9/-]+)',
                r'oep[:\s]*([0-9/-]+)',
            ],
            'company': [
                r'(refer|cp|infraestruturas|metro|carris)',
                r'carimbo\s+da\s+(empresa|entidade)',
            ]
        }
        
        # Extract text content from PyMuPDF text dictionary
        page_text = self._extract_page_text(text_dict)
        
        # Look for stamp-like text patterns
        for stamp_type, patterns in stamp_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                
                for match in matches:
                    # Extract context around the match
                    start_pos = max(0, match.start() - 50)
                    end_pos = min(len(page_text), match.end() + 50)
                    context = page_text[start_pos:end_pos]
                    
                    # Create stamp data
                    stamp_data = {
                        'stamp_type': stamp_type,
                        'matched_text': match.group(0),
                        'context': context,
                        'confidence': 0.7,
                        'method': 'text_pattern'
                    }
                    
                    if match.groups():
                        stamp_data['extracted_info'] = match.groups()
                    
                    stamp = StampData(
                        id=str(uuid.uuid4()),
                        bbox=BoundingBox(
                            x0=0, y0=0, x1=100, y1=50,  # Approximate - could be enhanced
                            page=page_num
                        ),
                        stamp_type=stamp_type,
                        confidence=0.7,
                        text_content=stamp_data
                    )
                    
                    stamps.append(stamp)
        
        return stamps
    
    def _extract_page_text(self, text_dict: Dict) -> str:
        """Extract readable text from PyMuPDF text dictionary"""
        text_parts = []
        
        for block in text_dict.get('blocks', []):
            if 'lines' in block:  # Text block
                for line in block['lines']:
                    line_text = []
                    for span in line['spans']:
                        if span.get('text', '').strip():
                            line_text.append(span['text'])
                    if line_text:
                        text_parts.append(' '.join(line_text))
        
        return '\n'.join(text_parts)
    
    def _remove_duplicate_stamps(self, stamps: List[StampData]) -> List[StampData]:
        """Remove duplicate stamps based on content similarity"""
        if not stamps:
            return []
        
        unique_stamps = []
        seen_content = set()
        
        for stamp in stamps:
            # Create content signature
            content_key = f"{stamp.stamp_type}_{stamp.text_content.get('matched_text', '')[:20]}"
            
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_stamps.append(stamp)
            else:
                # Keep higher confidence version
                for i, existing in enumerate(unique_stamps):
                    existing_key = f"{existing.stamp_type}_{existing.text_content.get('matched_text', '')[:20]}"
                    if existing_key == content_key:
                        if stamp.confidence > existing.confidence:
                            unique_stamps[i] = stamp
                        break
        
        return unique_stamps
    
    async def _enhance_stamps_with_ai(self, stamps: List[StampData], request: AnalysisRequest) -> List[StampData]:
        """Enhance stamps using free AI services"""
        enhanced_stamps = []
        
        for stamp in stamps:
            try:
                # Prepare context for AI enhancement
                context_text = f"""
                Stamp Type: {stamp.stamp_type}
                Matched Text: {stamp.text_content.get('matched_text', '')}
                Context: {stamp.text_content.get('context', '')[:200]}
                """
                
                # Use free AI service to extract structured information
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context_text,
                    task="extract_stamps"
                )
                
                if ai_result and ai_result.get('response'):
                    # AI successfully processed the stamp
                    stamp.confidence = min(stamp.confidence + 0.1, 1.0)
                    stamp.text_content['ai_enhanced'] = True
                    stamp.text_content['ai_response'] = ai_result['response'][:200]
                
                enhanced_stamps.append(stamp)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for stamp {stamp.id}: {e}")
                enhanced_stamps.append(stamp)  # Keep original
        
        return enhanced_stamps
    
    def _mock_stamp_detection(self) -> List[StampData]:
        """Mock stamp detection for demonstration"""
        stamps = []
        
        # Mock engineering stamps
        mock_data = [
            {
                'stamp_type': 'approval',
                'bbox': (600, 50, 750, 150),
                'confidence': 0.9,
                'text_content': {
                    'approved_by': 'João Silva',
                    'date': '2024-01-15',
                    'title': 'Eng. Civil'
                }
            },
            {
                'stamp_type': 'revision',
                'bbox': (500, 200, 600, 250),
                'confidence': 0.85,
                'text_content': {
                    'revision': 'Rev. A',
                    'date': '2024-01-20',
                    'description': 'Initial release'
                }
            }
        ]
        
        for data in mock_data:
            stamp = StampData(
                id=str(uuid.uuid4()),
                bbox=BoundingBox(
                    x0=data['bbox'][0],
                    y0=data['bbox'][1],
                    x1=data['bbox'][2],
                    y1=data['bbox'][3],
                    page=0
                ),
                stamp_type=data['stamp_type'],
                confidence=data['confidence'],
                text_content=data['text_content']
            )
            stamps.append(stamp)
        
        return stamps