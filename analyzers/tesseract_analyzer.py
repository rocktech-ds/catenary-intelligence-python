"""
Tesseract OCR Analyzer - For scanned documents
"""

import pytesseract
from PIL import Image
import fitz  # For PDF to image conversion
import io
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class TesseractAnalyzer:
    def get_status(self):
        try:
            version = pytesseract.get_tesseract_version()
            return {
                'available': True,
                'version': str(version),
                'description': 'OCR for scanned documents'
            }
        except:
            return {
                'available': False,
                'error': 'Tesseract not installed or not in PATH'
            }
    
    async def analyze(self, document_path: str) -> Dict[str, Any]:
        """Analyze PDF with Tesseract OCR"""
        try:
            result = {
                'success': True,
                'ocr_text': '',
                'pages': [],
                'detected_languages': [],
                'ocr_confidence': 0
            }
            
            doc = fitz.open(document_path)
            total_confidence = 0
            page_count = 0
            
            for page_num in range(min(doc.page_count, 5)):  # Limit to first 5 pages
                page = doc[page_num]
                
                # Convert page to image
                mat = fitz.Matrix(2, 2)  # Increase resolution
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # OCR the image
                image = Image.open(io.BytesIO(img_data))
                
                # Get OCR data with confidence
                ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang='eng+por')
                
                # Extract text and confidence
                page_text = pytesseract.image_to_string(image, lang='eng+por')
                confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                result['pages'].append({
                    'page': page_num + 1,
                    'text': page_text,
                    'confidence': avg_confidence
                })
                
                result['ocr_text'] += page_text + '\n'
                total_confidence += avg_confidence
                page_count += 1
            
            result['ocr_confidence'] = total_confidence / page_count if page_count > 0 else 0
            result['detected_languages'] = ['eng', 'por']
            
            doc.close()
            
            logger.info(f"✅ Tesseract OCR: Processed {page_count} pages, avg confidence: {result['ocr_confidence']:.1f}%")
            return result
            
        except Exception as e:
            logger.error(f"❌ Tesseract OCR failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }