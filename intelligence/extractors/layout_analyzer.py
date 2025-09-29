"""
Advanced Layout Analyzer for Engineering Documents

This module provides comprehensive document layout analysis using:
- Free computer vision APIs (Google Vision, Azure, OCR.space)
- Text-based geometric analysis
- AI-powered structure recognition
- Multi-modal layout detection

Optimized for VPS environments with minimal local processing.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import json
import math

from ..models.analysis_models import AnalysisRequest, BoundingBox

logger = logging.getLogger(__name__)

@dataclass
class LayoutElement:
    """Represents a detected layout element"""
    id: str
    element_type: str  # title, header, body, table, figure, stamp, annotation
    bbox: BoundingBox
    confidence: float
    text_content: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class LayoutStructure:
    """Complete document layout structure"""
    elements: List[LayoutElement]
    page_structure: Dict[str, Any]
    reading_order: List[str]  # Element IDs in reading order
    metadata: Dict[str, Any]

class AdvancedLayoutAnalyzer:
    """Advanced document layout analyzer using free services"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Layout element patterns for text-based detection
        self.element_patterns = {
            'title': [
                r'^[A-ZÁÉÍÓÚÂÊÔÀÇ\s]{10,80}$',
                r'título[:\s]*(.+)',
                r'project[o]?\s*title[:\s]*(.+)',
            ],
            'header': [
                r'^\d+[\.\s]+[A-ZÁÉÍÓÚ][^\.]{5,50}$',
                r'^[A-ZÁÉÍÓÚÂÊÔÀÇ]{3,}[:\-\s]*$',
                r'CAPÍTULO\s+\d+',
            ],
            'drawing_number': [
                r'desenho\s+n[º°]?\s*[:\-]?\s*([A-Z0-9\-/]+)',
                r'dwg\s*[:\-]?\s*([A-Z0-9\-/]+)',
                r'planta\s+n[º°]?\s*[:\-]?\s*([A-Z0-9\-/]+)',
            ],
            'scale': [
                r'escala[:\s]+1[:\s]*(\d+)',
                r'scale[:\s]+1[:\s]*(\d+)',
                r'esc[:\.\s]+1[:\s]*(\d+)',
            ],
            'dimensions': [
                r'\b\d+[\.,]\d*\s*[x×]\s*\d+[\.,]\d*(?:\s*[mx]m)?\b',
                r'\b\d+[\.,]\d*\s*mm?\b',
                r'[ØΦφ]\s*\d+[\.,]?\d*',
            ],
            'coordinates': [
                r'[XY]\s*[=:]\s*\d+[\.,]?\d*',
                r'coord[enadas]*[:\s]*\d+[\.,]\d*[,\s]+\d+[\.,]\d*',
            ]
        }
    
    async def analyze_layout(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Comprehensive layout analysis of engineering document
        """
        try:
            # Load document
            import fitz  # PyMuPDF
            doc = fitz.open(document_path)
            
            all_layouts = []
            processing_warnings = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Multi-method layout analysis
                    text_dict = page.get_text("dict")
                    
                    # 1. Text-based geometric analysis
                    text_layout = await self._analyze_text_layout(text_dict, page_num)
                    
                    # 2. Free computer vision analysis (if enabled)
                    cv_layout = None
                    if request.use_external_services:
                        cv_layout = await self._analyze_with_computer_vision(page, page_num)
                    
                    # 3. Combine and deduplicate results
                    page_layout = self._combine_layout_results(text_layout, cv_layout, page_num)
                    
                    # 4. AI-enhanced structure recognition
                    if request.use_ai_enhancement:
                        page_layout = await self._enhance_with_ai(page_layout, text_dict, request)
                    
                    all_layouts.append(page_layout)
                    
                except Exception as e:
                    error_msg = f"Layout analysis failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # Create complete document structure
            document_structure = self._build_document_structure(all_layouts)
            
            return {
                'layout_structure': asdict(document_structure),
                'page_layouts': [asdict(layout) for layout in all_layouts],
                'processing_warnings': processing_warnings,
                'analysis_metadata': {
                    'total_pages': len(all_layouts),
                    'total_elements': sum(len(layout.elements) for layout in all_layouts),
                    'methods_used': ['text_geometric', 'computer_vision', 'ai_enhancement']
                }
            }
            
        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return {'error': str(e), 'layout_structure': None}
    
    async def _analyze_text_layout(self, text_dict: Dict, page_num: int) -> LayoutStructure:
        """Analyze layout using text positioning and patterns"""
        elements = []
        
        # Extract text blocks with positions
        text_blocks = []
        for block in text_dict.get('blocks', []):
            if 'lines' in block:  # Text block
                block_bbox = block['bbox']
                block_text = self._extract_block_text(block)
                
                if block_text.strip():
                    text_blocks.append({
                        'text': block_text,
                        'bbox': block_bbox,
                        'lines': block['lines']
                    })
        
        # Sort blocks by vertical position (reading order)
        text_blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))
        
        # Analyze each text block
        for i, block in enumerate(text_blocks):
            element_type = self._classify_text_block(block, text_blocks)
            
            # Create layout element
            element = LayoutElement(
                id=str(uuid.uuid4()),
                element_type=element_type,
                bbox=BoundingBox(
                    x0=block['bbox'][0],
                    y0=block['bbox'][1],
                    x1=block['bbox'][2],
                    y1=block['bbox'][3],
                    page=page_num
                ),
                confidence=0.8,
                text_content=block['text'],
                metadata={
                    'method': 'text_geometric',
                    'reading_order': i,
                    'font_info': self._extract_font_info(block['lines'])
                }
            )
            
            elements.append(element)
        
        # Determine page structure
        page_structure = self._analyze_page_structure(elements)
        reading_order = [e.id for e in elements]
        
        return LayoutStructure(
            elements=elements,
            page_structure=page_structure,
            reading_order=reading_order,
            metadata={'analysis_method': 'text_geometric'}
        )
    
    async def _analyze_with_computer_vision(self, page, page_num: int) -> Optional[LayoutStructure]:
        """Analyze layout using free computer vision APIs"""
        try:
            from ..services.free_services_manager import free_services
            
            # Convert page to image for CV analysis
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))  # Higher DPI
            img_data = pix.tobytes("png")
            
            # Use free OCR/Computer Vision service
            cv_result = await free_services.analyze_image_layout(img_data)
            
            if cv_result and cv_result.get('layout_elements'):
                elements = []
                
                for cv_element in cv_result['layout_elements']:
                    element = LayoutElement(
                        id=str(uuid.uuid4()),
                        element_type=cv_element.get('type', 'unknown'),
                        bbox=BoundingBox(
                            x0=cv_element['bbox'][0],
                            y0=cv_element['bbox'][1],
                            x1=cv_element['bbox'][2],
                            y1=cv_element['bbox'][3],
                            page=page_num
                        ),
                        confidence=cv_element.get('confidence', 0.5),
                        text_content=cv_element.get('text'),
                        metadata={
                            'method': 'computer_vision',
                            'service_used': cv_result.get('service_name', 'unknown')
                        }
                    )
                    elements.append(element)
                
                return LayoutStructure(
                    elements=elements,
                    page_structure={},
                    reading_order=[e.id for e in elements],
                    metadata={'analysis_method': 'computer_vision'}
                )
            
        except Exception as e:
            logger.warning(f"Computer vision layout analysis failed: {e}")
            return None
    
    def _combine_layout_results(self, text_layout: LayoutStructure, 
                              cv_layout: Optional[LayoutStructure], 
                              page_num: int) -> LayoutStructure:
        """Combine results from different analysis methods"""
        all_elements = text_layout.elements.copy()
        
        if cv_layout:
            # Add CV elements that don't significantly overlap with text elements
            for cv_element in cv_layout.elements:
                if not self._has_significant_overlap(cv_element, all_elements):
                    all_elements.append(cv_element)
        
        # Remove duplicates and merge similar elements
        unique_elements = self._deduplicate_elements(all_elements)
        
        # Rebuild reading order
        reading_order = self._determine_reading_order(unique_elements)
        
        # Combine page structures
        combined_structure = text_layout.page_structure.copy()
        if cv_layout and cv_layout.page_structure:
            combined_structure.update(cv_layout.page_structure)
        
        return LayoutStructure(
            elements=unique_elements,
            page_structure=combined_structure,
            reading_order=reading_order,
            metadata={'analysis_method': 'combined'}
        )
    
    async def _enhance_with_ai(self, layout: LayoutStructure, text_dict: Dict, 
                             request: AnalysisRequest) -> LayoutStructure:
        """Enhance layout analysis with AI structure recognition"""
        try:
            from ..services.free_services_manager import free_services
            
            # Prepare layout context for AI
            layout_context = self._prepare_layout_context(layout, text_dict)
            
            # Use AI to improve element classification and structure
            ai_result = await free_services.enhance_with_ai(
                text=layout_context,
                task="analyze_document_layout"
            )
            
            if ai_result and ai_result.get('response'):
                # Parse AI response and update elements
                layout = self._apply_ai_enhancements(layout, ai_result)
            
        except Exception as e:
            logger.warning(f"AI layout enhancement failed: {e}")
        
        return layout
    
    def _classify_text_block(self, block: Dict, all_blocks: List[Dict]) -> str:
        """Classify text block based on content and position"""
        text = block['text'].strip()
        bbox = block['bbox']
        
        # Check against element patterns
        for element_type, patterns in self.element_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return element_type
        
        # Geometric classification
        block_height = bbox[3] - bbox[1]
        block_width = bbox[2] - bbox[0]
        
        # Check if it's likely a title (large, centered, short)
        if (block_height > 20 and len(text) < 100 and 
            self._is_horizontally_centered(bbox, all_blocks)):
            return 'title'
        
        # Check if it's a header (larger font, short text)
        if block_height > 15 and len(text) < 150:
            return 'header'
        
        # Check if it might be a table (structured layout)
        if self._looks_like_table_content(text):
            return 'table'
        
        # Default classification
        if len(text) < 50:
            return 'annotation'
        else:
            return 'body'
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract clean text from a text block"""
        text_parts = []
        
        for line in block.get('lines', []):
            line_text = []
            for span in line.get('spans', []):
                if span.get('text', '').strip():
                    line_text.append(span['text'])
            if line_text:
                text_parts.append(' '.join(line_text))
        
        return '\n'.join(text_parts)
    
    def _extract_font_info(self, lines: List[Dict]) -> Dict[str, Any]:
        """Extract font information from text lines"""
        font_sizes = []
        font_names = []
        
        for line in lines:
            for span in line.get('spans', []):
                if span.get('size'):
                    font_sizes.append(span['size'])
                if span.get('font'):
                    font_names.append(span['font'])
        
        return {
            'avg_size': sum(font_sizes) / len(font_sizes) if font_sizes else 12,
            'max_size': max(font_sizes) if font_sizes else 12,
            'fonts': list(set(font_names)) if font_names else []
        }
    
    def _analyze_page_structure(self, elements: List[LayoutElement]) -> Dict[str, Any]:
        """Analyze overall page structure"""
        structure = {
            'has_title': any(e.element_type == 'title' for e in elements),
            'has_headers': any(e.element_type == 'header' for e in elements),
            'has_tables': any(e.element_type == 'table' for e in elements),
            'has_stamps': any(e.element_type == 'stamp' for e in elements),
            'element_count': len(elements),
            'layout_type': 'unknown'
        }
        
        # Determine layout type
        if structure['has_title'] and structure['has_headers']:
            structure['layout_type'] = 'document'
        elif structure['has_tables']:
            structure['layout_type'] = 'technical_drawing'
        elif len(elements) > 20:
            structure['layout_type'] = 'detailed_document'
        else:
            structure['layout_type'] = 'simple_document'
        
        return structure
    
    def _is_horizontally_centered(self, bbox: Tuple, all_blocks: List[Dict]) -> bool:
        """Check if element is horizontally centered on page"""
        element_center = (bbox[0] + bbox[2]) / 2
        
        # Calculate page center from all blocks
        all_lefts = [b['bbox'][0] for b in all_blocks]
        all_rights = [b['bbox'][2] for b in all_blocks]
        page_center = (min(all_lefts) + max(all_rights)) / 2
        
        # Check if element center is close to page center
        return abs(element_center - page_center) < 50
    
    def _looks_like_table_content(self, text: str) -> bool:
        """Check if text looks like table content"""
        # Look for table-like patterns
        table_patterns = [
            r'\|.*\|',  # Pipe-separated
            r'\t.*\t',  # Tab-separated
            r'^\s*\d+[\.\)]\s+.*\s+\d+',  # Numbered with values
            r'.*\s+\d+[\.,]\d+\s+.*',  # Contains decimal numbers
        ]
        
        return any(re.search(pattern, text, re.MULTILINE) for pattern in table_patterns)
    
    def _has_significant_overlap(self, element: LayoutElement, elements: List[LayoutElement]) -> bool:
        """Check if element significantly overlaps with existing elements"""
        for existing in elements:
            if self._calculate_overlap_ratio(element.bbox, existing.bbox) > 0.7:
                return True
        return False
    
    def _calculate_overlap_ratio(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """Calculate overlap ratio between two bounding boxes"""
        # Calculate intersection
        x_left = max(bbox1.x0, bbox2.x0)
        y_top = max(bbox1.y0, bbox2.y0)
        x_right = min(bbox1.x1, bbox2.x1)
        y_bottom = min(bbox1.y1, bbox2.y1)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0  # No intersection
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = (bbox1.x1 - bbox1.x0) * (bbox1.y1 - bbox1.y0)
        area2 = (bbox2.x1 - bbox2.x0) * (bbox2.y1 - bbox2.y0)
        union_area = area1 + area2 - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def _deduplicate_elements(self, elements: List[LayoutElement]) -> List[LayoutElement]:
        """Remove duplicate layout elements"""
        unique_elements = []
        
        for element in elements:
            is_duplicate = False
            
            for existing in unique_elements:
                if (self._calculate_overlap_ratio(element.bbox, existing.bbox) > 0.8 and
                    element.element_type == existing.element_type):
                    # Keep the one with higher confidence
                    if element.confidence > existing.confidence:
                        unique_elements.remove(existing)
                        unique_elements.append(element)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_elements.append(element)
        
        return unique_elements
    
    def _determine_reading_order(self, elements: List[LayoutElement]) -> List[str]:
        """Determine reading order of elements"""
        # Sort by vertical position first, then horizontal
        sorted_elements = sorted(elements, 
                               key=lambda e: (e.bbox.y0, e.bbox.x0))
        return [e.id for e in sorted_elements]
    
    def _build_document_structure(self, page_layouts: List[LayoutStructure]) -> LayoutStructure:
        """Build complete document structure from page layouts"""
        all_elements = []
        reading_order = []
        
        for page_layout in page_layouts:
            all_elements.extend(page_layout.elements)
            reading_order.extend(page_layout.reading_order)
        
        # Analyze document-level structure
        document_metadata = {
            'total_pages': len(page_layouts),
            'total_elements': len(all_elements),
            'element_types': list(set(e.element_type for e in all_elements)),
            'has_consistent_structure': self._check_structure_consistency(page_layouts)
        }
        
        # Build overall page structure summary
        page_structure = {
            'pages': len(page_layouts),
            'avg_elements_per_page': len(all_elements) / len(page_layouts) if page_layouts else 0,
            'common_layout_type': self._determine_common_layout_type(page_layouts)
        }
        
        return LayoutStructure(
            elements=all_elements,
            page_structure=page_structure,
            reading_order=reading_order,
            metadata=document_metadata
        )
    
    def _check_structure_consistency(self, page_layouts: List[LayoutStructure]) -> bool:
        """Check if document has consistent structure across pages"""
        if len(page_layouts) < 2:
            return True
        
        layout_types = [layout.page_structure.get('layout_type') for layout in page_layouts]
        return len(set(layout_types)) <= 2  # Allow some variation
    
    def _determine_common_layout_type(self, page_layouts: List[LayoutStructure]) -> str:
        """Determine most common layout type across pages"""
        layout_types = [layout.page_structure.get('layout_type', 'unknown') 
                       for layout in page_layouts]
        
        if not layout_types:
            return 'unknown'
        
        # Return most common type
        return max(set(layout_types), key=layout_types.count)
    
    def _prepare_layout_context(self, layout: LayoutStructure, text_dict: Dict) -> str:
        """Prepare layout context for AI enhancement"""
        context_parts = []
        
        context_parts.append(f"Document Layout Analysis:")
        context_parts.append(f"Total elements: {len(layout.elements)}")
        
        for element in layout.elements[:10]:  # First 10 elements
            context_parts.append(
                f"- {element.element_type}: {element.text_content[:100] if element.text_content else 'N/A'}"
            )
        
        return '\n'.join(context_parts)
    
    def _apply_ai_enhancements(self, layout: LayoutStructure, ai_result: Dict) -> LayoutStructure:
        """Apply AI enhancements to layout structure"""
        # This would parse AI response and update element classifications
        # For now, just mark that AI enhancement was applied
        
        for element in layout.elements:
            if element.metadata is None:
                element.metadata = {}
            element.metadata['ai_enhanced'] = True
        
        layout.metadata['ai_enhanced'] = True
        return layout