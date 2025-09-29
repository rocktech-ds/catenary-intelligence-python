"""
Text Extraction Module
Comprehensive text extraction using PyMuPDF and PDFPlumber
"""
import fitz  # PyMuPDF
import pdfplumber
from typing import Dict, Any, List, Optional
from pathlib import Path
import time
from datetime import datetime

from ..core.config import IntelligenceConfig
from ..models.schemas import (
    TextElement, BoundingBox, DocumentMetadata, 
    PageAnalysis, AnalysisRequest
)
from loguru import logger

class TextExtractor:
    """Advanced text extraction with multiple engines"""
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.pymupdf_doc: Optional[fitz.Document] = None
        
    def load_models(self):
        """Load any required models (none for basic text extraction)"""
        logger.info("Text extractor ready")
        
    def extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract comprehensive document metadata"""
        try:
            doc = fitz.open(str(file_path))
            metadata = doc.metadata
            
            # Basic metadata
            title = metadata.get('title', '')
            subject = metadata.get('subject', '')
            author = metadata.get('author', '')
            creator = metadata.get('creator', '')
            
            # Parse dates
            creation_date = None
            modification_date = None
            
            if metadata.get('creationDate'):
                try:
                    creation_date = datetime.fromisoformat(
                        metadata['creationDate'].replace('D:', '').replace('Z', '')
                    )
                except:
                    pass
                    
            if metadata.get('modDate'):
                try:
                    modification_date = datetime.fromisoformat(
                        metadata['modDate'].replace('D:', '').replace('Z', '')
                    )
                except:
                    pass
            
            # Engineering-specific metadata extraction
            drawing_number = self._extract_drawing_number(doc)
            revision = self._extract_revision(doc)
            scale = self._extract_scale(doc)
            
            doc.close()
            
            return DocumentMetadata(
                title=title if title else None,
                subject=subject if subject else None,
                author=author if author else None,
                creator=creator if creator else None,
                creation_date=creation_date,
                modification_date=modification_date,
                drawing_number=drawing_number,
                revision=revision,
                scale=scale,
                pdf_version=f"PDF {doc.pdf_version()}" if hasattr(doc, 'pdf_version') else None,
                is_scanned=self._is_scanned_document(doc),
                has_layers=len(doc.layer_configs) > 0 if hasattr(doc, 'layer_configs') else False
            )
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return DocumentMetadata()
    
    def extract_text_and_layout(
        self, file_path: Path, request: AnalysisRequest
    ) -> Dict[str, Any]:
        """Extract text and basic layout using PyMuPDF and PDFPlumber"""
        
        results = {
            'pages': [],
            'processing_warnings': []
        }
        
        try:
            # PyMuPDF extraction
            pymupdf_results = self._extract_with_pymupdf(file_path, request)
            
            # PDFPlumber extraction (for better table detection)
            if request.tools.pdfplumber:
                pdfplumber_results = self._extract_with_pdfplumber(file_path, request)
                # Merge results
                pymupdf_results = self._merge_extraction_results(
                    pymupdf_results, pdfplumber_results
                )
            
            results.update(pymupdf_results)
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            results['processing_warnings'].append(f"Text extraction error: {str(e)}")
        
        return results
    
    def _extract_with_pymupdf(
        self, file_path: Path, request: AnalysisRequest
    ) -> Dict[str, Any]:
        """Extract using PyMuPDF"""
        
        doc = fitz.open(str(file_path))
        pages = []
        
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get page dimensions
                rect = page.rect
                dimensions = (rect.width, rect.height)
                
                # Extract text elements with detailed info
                text_elements = []
                text_dict = page.get_text("dict")
                
                for block in text_dict.get("blocks", []):
                    if "lines" in block:  # Text block
                        for line in block["lines"]:
                            for span in line["spans"]:
                                bbox = BoundingBox(
                                    x0=span["bbox"][0],
                                    y0=span["bbox"][1], 
                                    x1=span["bbox"][2],
                                    y1=span["bbox"][3],
                                    page=page_num
                                )
                                
                                element = TextElement(
                                    text=span["text"],
                                    bbox=bbox,
                                    font=span.get("font"),
                                    font_size=span.get("size"),
                                    font_flags=span.get("flags")
                                )
                                text_elements.append(element)
                
                # Calculate coverage metrics
                text_coverage = self._calculate_text_coverage(text_elements, dimensions)
                
                page_analysis = PageAnalysis(
                    page_number=page_num + 1,
                    dimensions=dimensions,
                    text_elements=text_elements,
                    tables=[],  # Will be filled by table extractor
                    callouts=[],  # Will be filled by callout extractor
                    stamps=[],  # Will be filled by stamp detector
                    layout_regions=[],  # Will be filled by layout detector
                    key_value_pairs=[],  # Will be filled by KV extractor
                    text_coverage=text_coverage,
                    drawing_coverage=1.0 - text_coverage,  # Rough estimate
                    confidence_score=0.9  # High confidence for PyMuPDF text
                )
                
                pages.append(page_analysis)
                
        finally:
            doc.close()
        
        return {'pages': pages}
    
    def _extract_with_pdfplumber(
        self, file_path: Path, request: AnalysisRequest
    ) -> Dict[str, Any]:
        """Extract using PDFPlumber (better for tables)"""
        
        pages = []
        
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    
                    # Get page dimensions
                    dimensions = (page.width, page.height)
                    
                    # Extract text objects (chars)
                    chars = page.chars
                    text_elements = []
                    
                    # Group characters into text elements
                    if chars:
                        text_elements = self._group_chars_to_elements(chars, page_num)
                    
                    # Calculate coverage
                    text_coverage = self._calculate_text_coverage(text_elements, dimensions)
                    
                    page_analysis = PageAnalysis(
                        page_number=page_num + 1,
                        dimensions=dimensions,
                        text_elements=text_elements,
                        tables=[],
                        callouts=[],
                        stamps=[],
                        layout_regions=[],
                        key_value_pairs=[],
                        text_coverage=text_coverage,
                        drawing_coverage=1.0 - text_coverage,
                        confidence_score=0.85  # Good confidence for PDFPlumber
                    )
                    
                    pages.append(page_analysis)
                    
        except Exception as e:
            logger.error(f"PDFPlumber extraction failed: {e}")
            return {}
        
        return {'pages': pages}
    
    def _group_chars_to_elements(self, chars: List[Dict], page_num: int) -> List[TextElement]:
        """Group individual characters into text elements"""
        if not chars:
            return []
        
        text_elements = []
        current_text = ""
        current_bbox = None
        current_font = None
        current_size = None
        
        for char in chars:
            # Start new element if font/size changes significantly
            if (current_font and char.get('fontname') != current_font) or \
               (current_size and abs(char.get('size', 0) - current_size) > 1):
                
                if current_text.strip():
                    text_elements.append(TextElement(
                        text=current_text.strip(),
                        bbox=current_bbox,
                        font=current_font,
                        font_size=current_size
                    ))
                
                current_text = char.get('text', '')
                current_bbox = BoundingBox(
                    x0=char['x0'], y0=char['y0'],
                    x1=char['x1'], y1=char['y1'],
                    page=page_num
                )
                current_font = char.get('fontname')
                current_size = char.get('size')
            else:
                # Extend current element
                current_text += char.get('text', '')
                if current_bbox:
                    current_bbox.x1 = max(current_bbox.x1, char['x1'])
                    current_bbox.y1 = max(current_bbox.y1, char['y1'])
                    current_bbox.x0 = min(current_bbox.x0, char['x0'])
                    current_bbox.y0 = min(current_bbox.y0, char['y0'])
        
        # Add final element
        if current_text.strip():
            text_elements.append(TextElement(
                text=current_text.strip(),
                bbox=current_bbox,
                font=current_font,
                font_size=current_size
            ))
        
        return text_elements
    
    def _merge_extraction_results(
        self, pymupdf_results: Dict[str, Any], pdfplumber_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge results from different extraction methods"""
        # For now, just return PyMuPDF results
        # In production, this would intelligently merge the best elements
        return pymupdf_results
    
    def _calculate_text_coverage(
        self, text_elements: List[TextElement], dimensions: tuple
    ) -> float:
        """Calculate what percentage of the page is covered by text"""
        if not text_elements:
            return 0.0
        
        page_area = dimensions[0] * dimensions[1]
        text_area = sum(
            (elem.bbox.x1 - elem.bbox.x0) * (elem.bbox.y1 - elem.bbox.y0)
            for elem in text_elements
        )
        
        return min(text_area / page_area, 1.0) if page_area > 0 else 0.0
    
    def _extract_drawing_number(self, doc: fitz.Document) -> Optional[str]:
        """Extract drawing number from title block"""
        # This would implement sophisticated pattern matching
        # for engineering drawing numbers
        return None
    
    def _extract_revision(self, doc: fitz.Document) -> Optional[str]:
        """Extract revision information"""
        # Pattern matching for revision info
        return None
    
    def _extract_scale(self, doc: fitz.Document) -> Optional[str]:
        """Extract drawing scale"""
        # Pattern matching for scale information
        return None
    
    def _is_scanned_document(self, doc: fitz.Document) -> bool:
        """Detect if document is scanned (image-based)"""
        # Check if document contains mostly images vs text
        # This is a simplified check
        return False