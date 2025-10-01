"""
PyMuPDF Analyzer - Basic PDF text and metadata extraction
"""

import fitz  # PyMuPDF
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class PyMuPDFAnalyzer:
    def get_status(self):
        return {
            'available': True,
            'version': fitz.version[0],
            'description': 'PDF text and metadata extraction'
        }
    
    async def analyze(self, document_path: str) -> Dict[str, Any]:
        """Analyze PDF with PyMuPDF"""
        try:
            doc = fitz.open(document_path)
            
            result = {
                'success': True,
                'page_count': doc.page_count,
                'text_content': '',
                'text_by_page': [],
                'metadata': doc.metadata,
                'toc': [],
                'images': [],
                'links': [],
                'tables': []
            }
            
            # Extract text by page
            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_text = page.get_text()
                result['text_by_page'].append(page_text)
                result['text_content'] += page_text + '\n'
                
                # Extract basic table info
                tables = page.find_tables()
                for i, table in enumerate(tables):
                    bbox = table.bbox
                    result['tables'].append({
                        'page': page_num + 1,
                        'table_index': i,
                        'bbox': list(bbox),
                        'row_count': len(table.extract()),
                        'col_count': len(table.extract()[0]) if table.extract() else 0
                    })
                
                # Extract links
                links = page.get_links()
                for link in links:
                    if 'uri' in link:
                        result['links'].append({
                            'page': page_num + 1,
                            'uri': link['uri'],
                            'rect': link['from']
                        })
            
            # Extract table of contents
            toc = doc.get_toc()
            for item in toc:
                result['toc'].append({
                    'level': item[0],
                    'title': item[1],
                    'page': item[2]
                })
            
            doc.close()
            logger.info(f"✅ PyMuPDF: Extracted {len(result['text_content'])} chars from {result['page_count']} pages")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ PyMuPDF analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }