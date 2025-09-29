"""
Callout Linker Module  
Links callouts and references in engineering drawings
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import re

from loguru import logger
from ..core.config import IntelligenceConfig
from ..models.schemas import CalloutData, BoundingBox, AnalysisRequest, ToolStatus
from ..models.target_schemas import (
    Callout, CalloutGeometry, CALLOUT_SCHEMA, PORTUGUESE_PATTERNS
)
from ..ai.llm_client import LLMClient
import fitz  # PyMuPDF

class CalloutLinker:
    """Links callouts, references, and annotations in engineering drawings"""
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.llm_client = LLMClient(config)
        self._loaded = False
    
    def load_models(self):
        """Load models for callout detection and linking"""
        self._loaded = True
        logger.info("Callout linker ready")
    
    async def get_status(self) -> ToolStatus:
        """Get callout linker status"""
        return ToolStatus(
            available=self._loaded,
            version="1.0.0"
        )
    
    async def extract_callouts(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract and link callouts from engineering drawings"""
        callouts = []
        processing_warnings = []
        
        try:
            # Step 1: Extract text elements from PDF
            text_elements = self._extract_text_elements(file_path)
            
            # Step 2: Identify potential callouts using patterns
            potential_callouts = self._identify_callout_patterns(text_elements)
            
            # Step 3: Enhance with AI if enabled
            if request.ai_enhancement.enabled:
                enhanced_callouts = await self._ai_enhance_callouts(potential_callouts, request)
            else:
                enhanced_callouts = self._rule_based_callout_processing(potential_callouts)
            
            callouts.extend(enhanced_callouts)
            
        except Exception as e:
            logger.error(f"Callout extraction failed: {e}")
            processing_warnings.append(f"Callout extraction error: {str(e)}")
        
        return {
            'callouts': callouts,
            'processing_warnings': processing_warnings
        }
    
    def _mock_callout_extraction(self) -> List[CalloutData]:
        """Mock callout extraction for demonstration"""
        callouts = []
        
        # Mock engineering callouts
        mock_data = [
            {
                'text': '1',
                'callout_type': 'number',
                'bbox': (100, 300, 120, 320),
                'confidence': 0.9,
                'part_number': 'P-001'
            },
            {
                'text': 'A',
                'callout_type': 'letter', 
                'bbox': (200, 400, 220, 420),
                'confidence': 0.85,
                'specification': 'Material: Steel'
            },
            {
                'text': 'DETAIL A',
                'callout_type': 'detail_ref',
                'bbox': (350, 150, 450, 170),
                'confidence': 0.8,
                'reference_target': 'detail_view_a'
            }
        ]
        
        for data in mock_data:
            callout = CalloutData(
                id=str(uuid.uuid4()),
                text=data['text'],
                bbox=BoundingBox(
                    x0=data['bbox'][0],
                    y0=data['bbox'][1],
                    x1=data['bbox'][2], 
                    y1=data['bbox'][3],
                    page=0
                ),
                confidence=data['confidence'],
                callout_type=data['callout_type'],
                part_number=data.get('part_number'),
                specification=data.get('specification'),
                reference_target=data.get('reference_target')
            )
            callouts.append(callout)
        
        return callouts
    
    def _extract_text_elements(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract text elements with positions from PDF using PyMuPDF"""
        text_elements = []
        
        try:
            doc = fitz.open(str(file_path))
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Extract text with detailed information
                text_dict = page.get_text("dict")
                
                for block in text_dict["blocks"]:
                    if "lines" in block:  # Text block
                        for line in block["lines"]:
                            for span in line["spans"]:
                                text = span["text"].strip()
                                if text:  # Skip empty text
                                    element = {
                                        "text": text,
                                        "bbox": span["bbox"],
                                        "page": page_num,
                                        "font_size": span["size"],
                                        "font": span["font"],
                                        "flags": span["flags"]  # Bold, italic, etc.
                                    }
                                    text_elements.append(element)
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Failed to extract text elements: {e}")
        
        return text_elements
    
    def _identify_callout_patterns(self, text_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify potential callouts using pattern matching"""
        potential_callouts = []
        
        # Callout patterns (engineering drawing references)
        callout_patterns = [
            r'^[A-Z]$',  # Single letters (A, B, C)
            r'^\d+$',    # Single numbers (1, 2, 3)
            r'^[A-Z]\d+$',  # Letter-number combinations (A1, B2)
            r'^\d+[A-Z]$',  # Number-letter combinations (1A, 2B)
            r'^DETAIL\s+[A-Z]',  # Detail references
            r'^SECTION\s+[A-Z-]+',  # Section references
            r'^VIEW\s+[A-Z]',  # View references
            r'^[A-Z]\s*-\s*[A-Z]',  # Range references (A-A, B-B)
        ]
        
        for element in text_elements:
            text = element["text"]
            
            # Check against patterns
            for pattern in callout_patterns:
                if re.match(pattern, text.upper()):
                    callout_type = self._classify_callout_type(text)
                    
                    potential_callout = {
                        "original_element": element,
                        "text": text,
                        "callout_type": callout_type,
                        "confidence": 0.7,  # Base confidence for pattern match
                        "bbox": element["bbox"],
                        "page": element["page"]
                    }
                    
                    potential_callouts.append(potential_callout)
                    break
        
        return potential_callouts
    
    def _classify_callout_type(self, text: str) -> str:
        """Classify the type of callout based on text pattern"""
        text_upper = text.upper()
        
        if re.match(r'^[A-Z]$', text_upper):
            return "letter_reference"
        elif re.match(r'^\d+$', text_upper):
            return "number_reference"
        elif "DETAIL" in text_upper:
            return "detail_reference"
        elif "SECTION" in text_upper:
            return "section_reference"
        elif "VIEW" in text_upper:
            return "view_reference"
        elif re.match(r'^[A-Z]\s*-\s*[A-Z]', text_upper):
            return "section_cut"
        else:
            return "general_reference"
    
    async def _ai_enhance_callouts(self, potential_callouts: List[Dict[str, Any]], request: AnalysisRequest) -> List[CalloutData]:
        """Use AI to enhance and validate callouts"""
        if not potential_callouts:
            return []
        
        try:
            # Prepare callout data for AI processing
            callout_texts = [c["text"] for c in potential_callouts]
            
            system_prompt = """
            You are an expert in Portuguese engineering drawing analysis.
            
            Task: Analyze and normalize callouts/annotations from engineering drawings.
            
            Context:
            - These are callouts extracted from Portuguese engineering drawings
            - They may include part references, detail callouts, section markers, etc.
            - Common types: numbered items, lettered sections, detail references, assembly markers
            
            Rules:
            1. Normalize callout text (clean OCR errors, standardize format)
            2. Identify the reference target if applicable
            3. Classify callout purpose (part_reference, detail_callout, section_marker, etc.)
            4. Provide confidence score (0.0-1.0)
            
            Return JSON matching the callout schema.
            """
            
            user_prompt = f"""
            Callouts to analyze:
            {callout_texts}
            
            Please provide normalized callout analysis.
            """
            
            result = await self.llm_client.extract_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=CALLOUT_SCHEMA,
                model_preference=["grok", "gemini", "groq"]
            )
            
            if result and "callouts" in result:
                return self._convert_ai_callouts_to_data(result["callouts"], potential_callouts)
            
        except Exception as e:
            logger.warning(f"AI callout enhancement failed: {e}")
        
        # Fallback to rule-based processing
        return self._rule_based_callout_processing(potential_callouts)
    
    def _convert_ai_callouts_to_data(self, ai_callouts: List[Dict], original_callouts: List[Dict]) -> List[CalloutData]:
        """Convert AI-enhanced callout data to CalloutData objects"""
        callout_data_list = []
        
        for i, ai_callout in enumerate(ai_callouts):
            if i < len(original_callouts):
                original = original_callouts[i]
                
                # Create CalloutData with AI enhancements
                callout_data = CalloutData(
                    id=str(uuid.uuid4()),
                    text=ai_callout.get("normalized", ai_callout.get("text", original["text"])),
                    bbox=BoundingBox(
                        x0=original["bbox"][0],
                        y0=original["bbox"][1],
                        x1=original["bbox"][2],
                        y1=original["bbox"][3],
                        page=original["page"]
                    ),
                    confidence=ai_callout.get("confidence", 0.8),
                    callout_type=original["callout_type"],
                    part_number=None,  # Could be extracted from AI analysis
                    specification=None,
                    reference_target=ai_callout.get("ref")
                )
                
                callout_data_list.append(callout_data)
        
        return callout_data_list
    
    def _rule_based_callout_processing(self, potential_callouts: List[Dict[str, Any]]) -> List[CalloutData]:
        """Process callouts using rule-based approach (fallback)"""
        callout_data_list = []
        
        for callout in potential_callouts:
            callout_data = CalloutData(
                id=str(uuid.uuid4()),
                text=callout["text"],
                bbox=BoundingBox(
                    x0=callout["bbox"][0],
                    y0=callout["bbox"][1],
                    x1=callout["bbox"][2],
                    y1=callout["bbox"][3],
                    page=callout["page"]
                ),
                confidence=callout["confidence"],
                callout_type=callout["callout_type"],
                part_number=None,
                specification=None,
                reference_target=None
            )
            
            callout_data_list.append(callout_data)
        
        return callout_data_list
    
    def convert_to_target_schema(self, callouts: List[CalloutData]) -> List[Callout]:
        """Convert CalloutData objects to target schema Callout format"""
        target_callouts = []
        
        for callout in callouts:
            # Determine targets from reference_target or empty list
            targets = [callout.reference_target] if callout.reference_target else []
            
            target_callout = Callout(
                text=callout.text,
                targets=targets,
                geometry=CalloutGeometry(
                    x=callout.bbox.x0,
                    y=callout.bbox.y0
                )
            )
            
            target_callouts.append(target_callout)
        
        return target_callouts
