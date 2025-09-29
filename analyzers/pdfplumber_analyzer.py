"""
PDFPlumber Analyzer - Advanced table extraction for BOMs
"""

import pdfplumber
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class PDFPlumberAnalyzer:
    def get_status(self):
        return {
            'available': True,
            'version': pdfplumber.__version__,
            'description': 'Advanced table extraction for BOMs'
        }
    
    async def analyze(self, document_path: str) -> Dict[str, Any]:
        """Analyze PDF with PDFPlumber for tables"""
        try:
            result = {
                'success': True,
                'tables': [],
                'pages': [],
                'text_objects': []
            }
            
            with pdfplumber.open(document_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_info = {
                        'page': page_num + 1,
                        'width': page.width,
                        'height': page.height,
                        'objects': len(page.chars)
                    }
                    result['pages'].append(page_info)
                    
                    # Extract tables
                    tables = page.find_tables()
                    for table in tables:
                        table_data = table.extract()
                        if table_data:
                            result['tables'].append({
                                'page': page_num + 1,
                                'bbox': table.bbox,
                                'data': table_data,
                                'header_rows': 1 if table_data and len(table_data) > 1 else 0
                            })
                    
                    # Extract text objects with positioning
                    for char in page.chars[:100]:  # Limit for performance
                        result['text_objects'].append({
                            'page': page_num + 1,
                            'text': char['text'],
                            'x0': char['x0'],
                            'y0': char['y0'],
                            'x1': char['x1'],
                            'y1': char['y1']
                        })
            
            logger.info(f"✅ PDFPlumber: Found {len(result['tables'])} tables across {len(result['pages'])} pages")
            return result
            
        except Exception as e:
            logger.error(f"❌ PDFPlumber analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }