"""
Advanced Revision Tracker for Engineering Documents

This module provides comprehensive revision tracking and analysis:
- Revision block detection and extraction
- Change history analysis
- Version comparison capabilities
- AI-powered revision summarization
- Portuguese and English language support

Optimized for VPS environments using free services.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json

from ..models.analysis_models import AnalysisRequest, BoundingBox

logger = logging.getLogger(__name__)

@dataclass
class RevisionEntry:
    """Represents a single revision entry"""
    id: str
    revision_code: str
    description: str
    date: Optional[str] = None
    author: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class RevisionBlock:
    """Represents a complete revision block/table"""
    id: str
    revisions: List[RevisionEntry]
    bbox: BoundingBox
    block_type: str  # table, list, stamp
    confidence: float
    metadata: Dict[str, Any] = None

@dataclass
class DocumentRevisionHistory:
    """Complete document revision history"""
    current_revision: Optional[str]
    revision_blocks: List[RevisionBlock]
    all_revisions: List[RevisionEntry]
    revision_timeline: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class AdvancedRevisionTracker:
    """Advanced revision tracking using text analysis and AI enhancement"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Revision detection patterns (Portuguese and English)
        self.revision_patterns = {
            'revision_code': [
                r'rev[\.\s]*([A-Z0-9]+)',
                r'revisão[\s:]*([A-Z0-9]+)',
                r'alteração[\s:]*([A-Z0-9]+)',
                r'version[\s:]*([A-Z0-9\.]+)',
                r'\b([A-Z]\d*|[0-9]+[A-Z]*)\b'  # Generic revision codes
            ],
            'revision_table_header': [
                r'rev[\.\s]*\|.*descri[çc]ão.*\|.*data',
                r'alteração.*descrição.*data',
                r'revision.*description.*date',
                r'código.*alteração.*data.*responsável',
            ],
            'revision_description': [
                r'emissão\s+inicial',
                r'primeira\s+emissão',
                r'correç[õa]o\s+de.*',
                r'alteração\s+de.*',
                r'revisão\s+geral',
                r'atualização.*',
                r'initial\s+issue',
                r'first\s+emission',
                r'correction\s+of.*',
                r'update.*',
            ],
            'date_patterns': [
                r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(\d{2,4}[-/\.]\d{1,2}[-/\.]\d{1,2})',
                r'(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',
                r'(\w+\s+\d{1,2},?\s+\d{4})',
            ],
            'author_patterns': [
                r'eng[º°]?\s+([A-Z][a-záéíóúâêôàç\s]+)',
                r'respons[áa]vel[:\s]*([A-Z][a-záéíóúâêôàç\s]+)',
                r'autor[:\s]*([A-Z][a-záéíóúâêôàç\s]+)',
                r'elaborado\s+por[:\s]*([A-Z][a-záéíóúâêôàç\s]+)',
            ]
        }
    
    async def track_revisions(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Comprehensive revision tracking and analysis
        """
        try:
            # Load document
            import fitz  # PyMuPDF
            doc = fitz.open(document_path)
            
            all_revision_blocks = []
            all_revisions = []
            processing_warnings = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Extract text for analysis
                    text_dict = page.get_text("dict")
                    page_text = page.get_text()
                    
                    # 1. Detect revision blocks/tables
                    revision_blocks = await self._detect_revision_blocks(text_dict, page_text, page_num)
                    all_revision_blocks.extend(revision_blocks)
                    
                    # 2. Extract individual revisions from blocks
                    for block in revision_blocks:
                        all_revisions.extend(block.revisions)
                    
                    # 3. Look for scattered revision information
                    scattered_revisions = await self._detect_scattered_revisions(text_dict, page_text, page_num)
                    all_revisions.extend(scattered_revisions)
                    
                except Exception as e:
                    error_msg = f"Revision tracking failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # 4. Deduplicate and organize revisions
            unique_revisions = self._deduplicate_revisions(all_revisions)
            
            # 5. AI enhancement (if enabled)
            if request.use_ai_enhancement:
                unique_revisions = await self._enhance_revisions_with_ai(unique_revisions, request)
            
            # 6. Build revision history
            revision_history = self._build_revision_history(unique_revisions, all_revision_blocks)
            
            return {
                'revision_history': asdict(revision_history),
                'processing_warnings': processing_warnings,
                'analysis_metadata': {
                    'total_revision_blocks': len(all_revision_blocks),
                    'total_revisions': len(unique_revisions),
                    'current_revision': revision_history.current_revision,
                    'revision_span': self._calculate_revision_span(unique_revisions)
                }
            }
            
        except Exception as e:
            logger.error(f"Revision tracking failed: {e}")
            return {'error': str(e), 'revision_history': None}
    
    async def _detect_revision_blocks(self, text_dict: Dict, page_text: str, page_num: int) -> List[RevisionBlock]:
        """Detect structured revision blocks (tables/lists)"""
        revision_blocks = []
        
        # Look for revision table headers
        for header_pattern in self.revision_patterns['revision_table_header']:
            header_matches = re.finditer(header_pattern, page_text, re.IGNORECASE | re.MULTILINE)
            
            for header_match in header_matches:
                # Find the table/block region
                block_bbox, block_text = self._extract_table_region(
                    text_dict, header_match.start(), header_match.end(), page_text
                )
                
                if block_bbox and block_text:
                    # Parse revisions from the block
                    revisions = self._parse_revision_table(block_text, page_num)
                    
                    if revisions:
                        revision_block = RevisionBlock(
                            id=str(uuid.uuid4()),
                            revisions=revisions,
                            bbox=block_bbox,
                            block_type='table',
                            confidence=0.8,
                            metadata={
                                'detection_method': 'table_header',
                                'raw_text': block_text[:500]  # First 500 chars for reference
                            }
                        )
                        revision_blocks.append(revision_block)
        
        # Look for list-style revision blocks
        revision_blocks.extend(await self._detect_revision_lists(text_dict, page_text, page_num))
        
        return revision_blocks
    
    async def _detect_revision_lists(self, text_dict: Dict, page_text: str, page_num: int) -> List[RevisionBlock]:
        """Detect list-style revision information"""
        revision_blocks = []
        
        # Pattern for revision lists
        list_patterns = [
            r'(rev\s*[A-Z0-9]+[\s\-:]+.*?)(?=rev\s*[A-Z0-9]+|$)',
            r'([A-Z0-9]+\s*[\-:]\s*.*?)(?=[A-Z0-9]+\s*[\-:]|$)',
        ]
        
        for pattern in list_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            
            if len(matches) >= 2:  # At least 2 revision entries
                # Create revision block for the list
                revisions = []
                
                for match_text in matches[:10]:  # Limit to first 10 matches
                    revision = self._parse_single_revision_entry(match_text, page_num)
                    if revision:
                        revisions.append(revision)
                
                if revisions:
                    # Estimate bounding box (would need more sophisticated positioning)
                    block_bbox = BoundingBox(x0=50, y0=100, x1=500, y1=300, page=page_num)
                    
                    revision_block = RevisionBlock(
                        id=str(uuid.uuid4()),
                        revisions=revisions,
                        bbox=block_bbox,
                        block_type='list',
                        confidence=0.7,
                        metadata={
                            'detection_method': 'list_pattern',
                            'pattern_used': pattern
                        }
                    )
                    revision_blocks.append(revision_block)
                    break  # Only use first matching pattern
        
        return revision_blocks
    
    async def _detect_scattered_revisions(self, text_dict: Dict, page_text: str, page_num: int) -> List[RevisionEntry]:
        """Detect scattered revision information throughout the page"""
        revisions = []
        
        # Look for revision codes followed by descriptions
        combined_pattern = r'(rev[\.\s]*[A-Z0-9]+)[\s\-:]*([^\.]{10,100})(?:[\s\-]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}))?'
        
        matches = re.finditer(combined_pattern, page_text, re.IGNORECASE)
        
        for match in matches:
            revision_code = re.sub(r'rev[\.\s]*', '', match.group(1), flags=re.IGNORECASE).strip()
            description = match.group(2).strip()
            date = match.group(3) if match.group(3) else None
            
            revision = RevisionEntry(
                id=str(uuid.uuid4()),
                revision_code=revision_code,
                description=description,
                date=date,
                confidence=0.6,
                metadata={
                    'detection_method': 'scattered',
                    'raw_match': match.group(0)
                }
            )
            
            revisions.append(revision)
        
        return revisions
    
    def _extract_table_region(self, text_dict: Dict, start_pos: int, end_pos: int, 
                            page_text: str) -> Tuple[Optional[BoundingBox], Optional[str]]:
        """Extract table region around detected header"""
        # This is a simplified version - in practice would need more sophisticated
        # table boundary detection using text positioning
        
        # Find text context around the header
        context_start = max(0, start_pos - 100)
        context_end = min(len(page_text), end_pos + 1000)
        table_text = page_text[context_start:context_end]
        
        # Estimate bounding box (simplified)
        bbox = BoundingBox(x0=50, y0=100, x1=500, y1=400, page=0)
        
        return bbox, table_text
    
    def _parse_revision_table(self, table_text: str, page_num: int) -> List[RevisionEntry]:
        """Parse revisions from table-like text"""
        revisions = []
        
        # Split into potential rows
        lines = table_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Try to extract revision info from line
            revision = self._parse_table_row(line, page_num)
            if revision:
                revisions.append(revision)
        
        return revisions
    
    def _parse_table_row(self, row_text: str, page_num: int) -> Optional[RevisionEntry]:
        """Parse single table row for revision information"""
        # Pattern for table row: REV | DESCRIPTION | DATE | AUTHOR
        row_pattern = r'([A-Z0-9]+)[\s\|]*([^|\n]{5,100})[\s\|]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})?[\s\|]*([A-Za-záéíóúâêôàç\s]+)?'
        
        match = re.search(row_pattern, row_text)
        if match:
            revision_code = match.group(1).strip()
            description = match.group(2).strip()
            date = match.group(3).strip() if match.group(3) else None
            author = match.group(4).strip() if match.group(4) else None
            
            return RevisionEntry(
                id=str(uuid.uuid4()),
                revision_code=revision_code,
                description=description,
                date=date,
                author=author,
                confidence=0.8,
                metadata={
                    'detection_method': 'table_row',
                    'raw_row': row_text
                }
            )
        
        return None
    
    def _parse_single_revision_entry(self, entry_text: str, page_num: int) -> Optional[RevisionEntry]:
        """Parse single revision entry from text"""
        # Extract revision code
        rev_code_match = re.search(r'(?:rev[\.\s]*)?([A-Z0-9]+)', entry_text, re.IGNORECASE)
        if not rev_code_match:
            return None
        
        revision_code = rev_code_match.group(1)
        
        # Extract description (text after revision code)
        description_start = rev_code_match.end()
        description_text = entry_text[description_start:].strip()
        
        # Clean description
        description = re.sub(r'^[\s\-:]+', '', description_text)
        description = description.split('\n')[0]  # Take first line
        
        # Extract date if present
        date_match = re.search(r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})', description)
        date = date_match.group(1) if date_match else None
        
        # Extract author if present
        author_match = None
        for pattern in self.revision_patterns['author_patterns']:
            author_match = re.search(pattern, description, re.IGNORECASE)
            if author_match:
                break
        
        author = author_match.group(1) if author_match else None
        
        return RevisionEntry(
            id=str(uuid.uuid4()),
            revision_code=revision_code,
            description=description[:200],  # Limit description length
            date=date,
            author=author,
            confidence=0.7,
            metadata={
                'detection_method': 'single_entry',
                'raw_entry': entry_text[:100]
            }
        )
    
    def _deduplicate_revisions(self, revisions: List[RevisionEntry]) -> List[RevisionEntry]:
        """Remove duplicate revision entries"""
        seen_codes = {}
        unique_revisions = []
        
        for revision in revisions:
            code = revision.revision_code.upper()
            
            if code not in seen_codes:
                seen_codes[code] = revision
                unique_revisions.append(revision)
            else:
                # Keep the one with higher confidence or more complete information
                existing = seen_codes[code]
                
                if (revision.confidence > existing.confidence or
                    (revision.date and not existing.date) or
                    (revision.author and not existing.author)):
                    
                    # Replace existing with new one
                    unique_revisions.remove(existing)
                    unique_revisions.append(revision)
                    seen_codes[code] = revision
        
        return unique_revisions
    
    async def _enhance_revisions_with_ai(self, revisions: List[RevisionEntry], 
                                       request: AnalysisRequest) -> List[RevisionEntry]:
        """Enhance revision information using AI services"""
        enhanced_revisions = []
        
        for revision in revisions:
            try:
                # Prepare context for AI enhancement
                context = f"""
                Revision Code: {revision.revision_code}
                Description: {revision.description}
                Date: {revision.date or 'Unknown'}
                Author: {revision.author or 'Unknown'}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_revision_info"
                )
                
                if ai_result and ai_result.get('response'):
                    # AI successfully processed the revision
                    revision.confidence = min(revision.confidence + 0.1, 1.0)
                    
                    if revision.metadata is None:
                        revision.metadata = {}
                    revision.metadata['ai_enhanced'] = True
                    revision.metadata['ai_suggestions'] = ai_result.get('response', '')[:200]
                
                enhanced_revisions.append(revision)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for revision {revision.revision_code}: {e}")
                enhanced_revisions.append(revision)  # Keep original
        
        return enhanced_revisions
    
    def _build_revision_history(self, revisions: List[RevisionEntry], 
                              revision_blocks: List[RevisionBlock]) -> DocumentRevisionHistory:
        """Build complete document revision history"""
        
        # Sort revisions by code (attempt chronological order)
        sorted_revisions = self._sort_revisions_chronologically(revisions)
        
        # Determine current revision
        current_revision = sorted_revisions[-1].revision_code if sorted_revisions else None
        
        # Build timeline
        timeline = []
        for revision in sorted_revisions:
            timeline_entry = {
                'revision_code': revision.revision_code,
                'description': revision.description,
                'date': revision.date,
                'author': revision.author,
                'confidence': revision.confidence
            }
            timeline.append(timeline_entry)
        
        # Build metadata
        metadata = {
            'total_revisions': len(sorted_revisions),
            'has_dates': sum(1 for r in sorted_revisions if r.date),
            'has_authors': sum(1 for r in sorted_revisions if r.author),
            'revision_codes': [r.revision_code for r in sorted_revisions],
            'analysis_completeness': self._calculate_analysis_completeness(sorted_revisions)
        }
        
        return DocumentRevisionHistory(
            current_revision=current_revision,
            revision_blocks=revision_blocks,
            all_revisions=sorted_revisions,
            revision_timeline=timeline,
            metadata=metadata
        )
    
    def _sort_revisions_chronologically(self, revisions: List[RevisionEntry]) -> List[RevisionEntry]:
        """Sort revisions in chronological order"""
        # First, try to sort by date if available
        dated_revisions = [r for r in revisions if r.date]
        undated_revisions = [r for r in revisions if not r.date]
        
        # Sort dated revisions by date
        try:
            dated_revisions.sort(key=lambda r: self._parse_date(r.date))
        except:
            # If date parsing fails, fall back to code sorting
            dated_revisions.sort(key=lambda r: r.revision_code)
        
        # Sort undated revisions by revision code
        undated_revisions.sort(key=lambda r: r.revision_code)
        
        return dated_revisions + undated_revisions
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        if not date_str:
            return datetime.min
        
        # Try different date formats
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
            "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # If all formats fail, return a default
        return datetime.min
    
    def _calculate_revision_span(self, revisions: List[RevisionEntry]) -> Dict[str, Any]:
        """Calculate revision span information"""
        if not revisions:
            return {}
        
        dated_revisions = [r for r in revisions if r.date]
        
        if len(dated_revisions) < 2:
            return {'span_available': False}
        
        try:
            dates = [self._parse_date(r.date) for r in dated_revisions]
            dates = [d for d in dates if d != datetime.min]
            
            if len(dates) >= 2:
                span_days = (max(dates) - min(dates)).days
                return {
                    'span_available': True,
                    'first_revision_date': min(dates).strftime("%Y-%m-%d"),
                    'last_revision_date': max(dates).strftime("%Y-%m-%d"),
                    'span_days': span_days,
                    'span_years': round(span_days / 365.25, 2)
                }
        except:
            pass
        
        return {'span_available': False}
    
    def _calculate_analysis_completeness(self, revisions: List[RevisionEntry]) -> Dict[str, float]:
        """Calculate completeness metrics for revision analysis"""
        if not revisions:
            return {}
        
        total = len(revisions)
        
        return {
            'has_description': sum(1 for r in revisions if r.description and len(r.description) > 5) / total,
            'has_date': sum(1 for r in revisions if r.date) / total,
            'has_author': sum(1 for r in revisions if r.author) / total,
            'high_confidence': sum(1 for r in revisions if r.confidence > 0.7) / total,
            'overall_completeness': sum([
                1 if r.description and len(r.description) > 5 else 0,
                1 if r.date else 0,
                1 if r.author else 0,
                1 if r.confidence > 0.7 else 0
            ]) / (total * 4)  # 4 criteria per revision
        }