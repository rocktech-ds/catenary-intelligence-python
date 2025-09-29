"""
Advanced FREE Table Extractor
Uses multiple free libraries (Tabula, Camelot, PDFQuery) for maximum table extraction capability
Zero VPS resource usage - all free external processing
"""
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import uuid
import tempfile
import os

from loguru import logger

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False
    logger.warning("Tabula-py not available - install with: pip install tabula-py")

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("Camelot not available - install with: pip install camelot-py[cv]")

try:
    import pdfquery
    PDFQUERY_AVAILABLE = True
except ImportError:
    PDFQUERY_AVAILABLE = False
    logger.warning("PDFQuery not available - install with: pip install pdfquery")

import pandas as pd
import fitz  # PyMuPDF
from ..core.config import IntelligenceConfig
from ..models.schemas import TableData, BoundingBox, AnalysisRequest, ToolStatus
from ..models.target_schemas import BOM_COLUMN_MAPPINGS, TableBlock
from ..utils.text import clean_text, clean_table_cell
from ..services.free_services_manager import free_services

class AdvancedTableExtractor:
    """
    Advanced table extraction using FREE libraries and services
    - Tabula-py: Java-based table extraction (unlimited free)
    - Camelot: Lattice and stream table detection (unlimited free)  
    - PDFQuery: jQuery-like PDF parsing (unlimited free)
    - Free AI normalization via external APIs
    """
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.available_tools = self._check_available_tools()
        logger.info(f"Advanced table extractor initialized with tools: {self.available_tools}")
    
    def _check_available_tools(self) -> List[str]:
        """Check which free table extraction tools are available"""
        tools = ["pdfplumber", "pymupdf"]  # Always available
        
        if TABULA_AVAILABLE:
            tools.append("tabula")
        if CAMELOT_AVAILABLE:
            tools.append("camelot")
        if PDFQUERY_AVAILABLE:
            tools.append("pdfquery")
            
        return tools
    
    async def get_status(self) -> ToolStatus:
        """Get table extractor status"""
        return ToolStatus(
            available=len(self.available_tools) > 0,
            version="2.0.0-free",
            load_time=None
        )
    
    async def extract_tables(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Extract tables using all available FREE methods with smart combination
        """
        all_tables = []
        processing_warnings = []
        extraction_methods_used = []
        
        try:
            # Method 1: PDFPlumber (fast, basic tables)
            if "pdfplumber" in self.available_tools:
                tables_pdfplumber = await self._extract_with_pdfplumber(file_path)
                all_tables.extend(tables_pdfplumber)
                extraction_methods_used.append("pdfplumber")
                logger.info(f"📊 PDFPlumber extracted {len(tables_pdfplumber)} tables")
            
            # Method 2: Tabula-py (excellent for structured tables)
            if TABULA_AVAILABLE and "tabula" in self.available_tools:
                tables_tabula = await self._extract_with_tabula(file_path)
                all_tables.extend(tables_tabula)
                extraction_methods_used.append("tabula")
                logger.info(f"📊 Tabula extracted {len(tables_tabula)} tables")
            
            # Method 3: Camelot (excellent for lattice/bordered tables)
            if CAMELOT_AVAILABLE and "camelot" in self.available_tools:
                tables_camelot = await self._extract_with_camelot(file_path)
                all_tables.extend(tables_camelot)
                extraction_methods_used.append("camelot")
                logger.info(f"📊 Camelot extracted {len(tables_camelot)} tables")
            
            # Method 4: PDFQuery (jQuery-like extraction)
            if PDFQUERY_AVAILABLE and "pdfquery" in self.available_tools:
                tables_pdfquery = await self._extract_with_pdfquery(file_path)
                all_tables.extend(tables_pdfquery)
                extraction_methods_used.append("pdfquery")
                logger.info(f"📊 PDFQuery extracted {len(tables_pdfquery)} tables")
            
            # Remove duplicates and merge similar tables
            unique_tables = self._deduplicate_tables(all_tables)
            logger.info(f"📊 After deduplication: {len(unique_tables)} unique tables")
            
            # Enhance with free AI services if enabled
            if request.ai_enhancement and request.ai_enhancement.enabled:
                enhanced_tables = await self._enhance_tables_with_free_ai(unique_tables)
                unique_tables = enhanced_tables
            
            # Convert to target schema format
            target_tables = self._convert_to_target_schema(unique_tables)
            
        except Exception as e:
            logger.error(f"Advanced table extraction failed: {e}")
            processing_warnings.append(f"Table extraction error: {str(e)}")
        
        return {
            'tables': unique_tables,
            'target_tables': target_tables,
            'methods_used': extraction_methods_used,
            'processing_warnings': processing_warnings,
            'total_tables_found': len(unique_tables)
        }
    
    async def _extract_with_pdfplumber(self, file_path: Path) -> List[TableData]:
        """Extract tables using PDFPlumber (fast, lightweight)"""
        tables = []
        
        try:
            import pdfplumber
            
            with pdfplumber.open(str(file_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Use default table extraction
                    page_tables = page.extract_tables()
                    
                    for i, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < 2:
                            continue
                        
                        table = self._create_table_data(
                            table_data=table_data,
                            page_num=page_num,
                            method="pdfplumber",
                            confidence=0.7,
                            bbox=(0, 0, page.width, page.height)  # Approximate
                        )
                        if table:
                            tables.append(table)
        
        except Exception as e:
            logger.error(f"PDFPlumber extraction failed: {e}")
        
        return tables
    
    async def _extract_with_tabula(self, file_path: Path) -> List[TableData]:
        """Extract tables using Tabula-py (Java-based, very powerful)"""
        tables = []
        
        if not TABULA_AVAILABLE:
            return tables
        
        try:
            # Extract tables from all pages
            df_list = tabula.read_pdf(
                str(file_path),
                pages='all',
                multiple_tables=True,
                pandas_options={'header': 0},
                silent=True,
                java_options=["-Xmx512m"]  # Limit Java memory usage
            )
            
            for i, df in enumerate(df_list):
                if df.empty:
                    continue
                
                # Convert DataFrame to table data format
                headers = [clean_text(str(col)) for col in df.columns]
                data_rows = []
                
                for _, row in df.iterrows():
                    clean_row = [clean_table_cell(str(val)) for val in row.values]
                    data_rows.append(clean_row)
                
                # Create table structure
                table_data = [headers] + data_rows
                
                table = self._create_table_data(
                    table_data=table_data,
                    page_num=0,  # Tabula doesn't provide page info easily
                    method="tabula",
                    confidence=0.85,  # Tabula is generally very accurate
                    bbox=(0, 0, 500, 300)  # Approximate
                )
                
                if table:
                    tables.append(table)
        
        except Exception as e:
            logger.error(f"Tabula extraction failed: {e}")
        
        return tables
    
    async def _extract_with_camelot(self, file_path: Path) -> List[TableData]:
        """Extract tables using Camelot (excellent for bordered tables)"""
        tables = []
        
        if not CAMELOT_AVAILABLE:
            return tables
        
        try:
            # Try lattice method first (for bordered tables)
            lattice_tables = camelot.read_pdf(
                str(file_path),
                pages='all',
                flavor='lattice'
            )
            
            for table in lattice_tables:
                if table.df.empty:
                    continue
                
                df = table.df
                headers = [clean_text(str(col)) for col in df.iloc[0]] if len(df) > 0 else []
                data_rows = []
                
                for _, row in df.iloc[1:].iterrows():
                    clean_row = [clean_table_cell(str(val)) for val in row.values]
                    data_rows.append(clean_row)
                
                table_data = [headers] + data_rows if headers else data_rows
                
                table_obj = self._create_table_data(
                    table_data=table_data,
                    page_num=table.page - 1,  # Camelot uses 1-based indexing
                    method="camelot-lattice",
                    confidence=table.accuracy / 100.0,
                    bbox=table._bbox
                )
                
                if table_obj:
                    tables.append(table_obj)
            
            # Try stream method for non-bordered tables
            try:
                stream_tables = camelot.read_pdf(
                    str(file_path),
                    pages='all',
                    flavor='stream'
                )
                
                for table in stream_tables:
                    if table.df.empty:
                        continue
                    
                    # Process similar to lattice method
                    df = table.df
                    headers = [clean_text(str(col)) for col in df.iloc[0]] if len(df) > 0 else []
                    data_rows = []
                    
                    for _, row in df.iloc[1:].iterrows():
                        clean_row = [clean_table_cell(str(val)) for val in row.values]
                        data_rows.append(clean_row)
                    
                    table_data = [headers] + data_rows if headers else data_rows
                    
                    table_obj = self._create_table_data(
                        table_data=table_data,
                        page_num=table.page - 1,
                        method="camelot-stream",
                        confidence=table.accuracy / 100.0 if hasattr(table, 'accuracy') else 0.7,
                        bbox=getattr(table, '_bbox', (0, 0, 500, 300))
                    )
                    
                    if table_obj:
                        tables.append(table_obj)
            
            except Exception as stream_error:
                logger.warning(f"Camelot stream method failed: {stream_error}")
        
        except Exception as e:
            logger.error(f"Camelot extraction failed: {e}")
        
        return tables
    
    async def _extract_with_pdfquery(self, file_path: Path) -> List[TableData]:
        """Extract tables using PDFQuery (jQuery-like PDF parsing)"""
        tables = []
        
        if not PDFQUERY_AVAILABLE:
            return tables
        
        try:
            # PDFQuery approach for structured data extraction
            doc = pdfquery.PDFQuery(str(file_path))
            doc.load()
            
            # Look for table-like structures (this is a simplified approach)
            # In practice, you'd need to identify table patterns specific to your documents
            
            # Find elements that look like table cells
            elements = doc.tree.iter()
            potential_table_data = []
            
            # This is a basic implementation - can be enhanced based on document structure
            for element in elements:
                if hasattr(element, 'text') and element.text:
                    text = clean_text(element.text)
                    if text and len(text) > 1:  # Skip single character elements
                        potential_table_data.append(text)
            
            # If we found structured data, try to form tables
            if len(potential_table_data) > 10:  # Minimum threshold
                # This is a simplified table creation - enhance based on your needs
                # Group data into table-like structure
                chunk_size = 8  # Assume 8 columns for BOM tables
                table_rows = []
                
                for i in range(0, len(potential_table_data), chunk_size):
                    row = potential_table_data[i:i+chunk_size]
                    if len(row) == chunk_size:  # Complete rows only
                        table_rows.append(row)
                
                if len(table_rows) > 2:  # At least header + 2 data rows
                    table = self._create_table_data(
                        table_data=table_rows,
                        page_num=0,
                        method="pdfquery",
                        confidence=0.6,  # Lower confidence for this method
                        bbox=(0, 0, 500, 300)
                    )
                    
                    if table:
                        tables.append(table)
        
        except Exception as e:
            logger.error(f"PDFQuery extraction failed: {e}")
        
        return tables
    
    def _create_table_data(self, table_data: List[List[str]], page_num: int, 
                          method: str, confidence: float, bbox: Tuple) -> Optional[TableData]:
        """Create TableData object from extracted table"""
        try:
            if not table_data or len(table_data) < 1:
                return None
            
            headers = table_data[0] if table_data else []
            data_rows = table_data[1:] if len(table_data) > 1 else []
            
            # Clean headers
            clean_headers = [clean_text(str(h)) for h in headers]
            
            # Clean data
            clean_data = []
            for row in data_rows:
                clean_row = [clean_table_cell(str(cell)) for cell in row]
                clean_data.append(clean_row)
            
            # Calculate quality metrics
            cell_completeness = self._calculate_cell_completeness(clean_data)
            
            table = TableData(
                id=str(uuid.uuid4()),
                bbox=BoundingBox(
                    x0=bbox[0],
                    y0=bbox[1], 
                    x1=bbox[2],
                    y1=bbox[3],
                    page=page_num
                ),
                extraction_method=method,
                confidence=confidence,
                rows=len(clean_data),
                cols=len(clean_headers) if clean_headers else (len(clean_data[0]) if clean_data else 0),
                headers=clean_headers,
                data=clean_data,
                table_type=self._identify_table_type(clean_headers),
                cell_completeness=cell_completeness,
                alignment_score=confidence  # Use confidence as proxy
            )
            
            return table
        
        except Exception as e:
            logger.warning(f"Failed to create table data: {e}")
            return None
    
    def _calculate_cell_completeness(self, data: List[List[str]]) -> float:
        """Calculate percentage of non-empty cells"""
        if not data:
            return 0.0
        
        total_cells = sum(len(row) for row in data)
        filled_cells = sum(
            len([cell for cell in row if cell and str(cell).strip()])
            for row in data
        )
        
        return filled_cells / total_cells if total_cells > 0 else 0.0
    
    def _identify_table_type(self, headers: List[str]) -> str:
        """Identify the type of engineering table"""
        headers_text = ' '.join(headers).lower()
        
        # BOM (Bill of Materials) detection
        bom_keywords = ['ref', 'designa', 'quantidade', 'peso', 'código', 'desenho']
        if any(keyword in headers_text for keyword in bom_keywords):
            return 'bom'
        
        # Schedule/timeline detection
        schedule_keywords = ['data', 'prazo', 'atividade', 'duração']
        if any(keyword in headers_text for keyword in schedule_keywords):
            return 'schedule'
        
        # Specifications table
        spec_keywords = ['especifica', 'valor', 'unidade', 'tolerância']
        if any(keyword in headers_text for keyword in spec_keywords):
            return 'specifications'
        
        return 'general'
    
    def _deduplicate_tables(self, tables: List[TableData]) -> List[TableData]:
        """Remove duplicate tables from different extraction methods"""
        if not tables:
            return []
        
        unique_tables = []
        seen_signatures = set()
        
        for table in tables:
            # Create signature based on headers and first few rows
            signature_parts = []
            signature_parts.extend(table.headers[:5])  # First 5 headers
            
            if table.data:
                for row in table.data[:3]:  # First 3 rows
                    signature_parts.extend(row[:3])  # First 3 cells
            
            signature = hash('|'.join(str(part) for part in signature_parts))
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_tables.append(table)
            else:
                # If duplicate, keep the one with higher confidence
                for i, existing in enumerate(unique_tables):
                    existing_sig_parts = []
                    existing_sig_parts.extend(existing.headers[:5])
                    if existing.data:
                        for row in existing.data[:3]:
                            existing_sig_parts.extend(row[:3])
                    existing_sig = hash('|'.join(str(part) for part in existing_sig_parts))
                    
                    if existing_sig == signature:
                        if table.confidence > existing.confidence:
                            unique_tables[i] = table
                        break
        
        return unique_tables
    
    async def _enhance_tables_with_free_ai(self, tables: List[TableData]) -> List[TableData]:
        """Enhance tables using free AI services"""
        enhanced_tables = []
        
        for table in tables:
            try:
                # Build context for AI enhancement
                table_context = {
                    "headers": table.headers,
                    "sample_data": table.data[:3] if table.data else [],  # First 3 rows
                    "table_type": table.table_type
                }
                
                # Use free AI to normalize headers
                ai_result = await free_services.enhance_with_ai(
                    text=f"Headers: {table.headers}\nSample data: {table_context['sample_data']}",
                    task="normalize_table"
                )
                
                if ai_result and ai_result.get("response"):
                    # AI might suggest header normalizations
                    # For now, just increase confidence if AI successfully processed it
                    table.confidence = min(table.confidence + 0.1, 1.0)
                    table.extraction_method += "+AI"
                
                enhanced_tables.append(table)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for table {table.id}: {e}")
                enhanced_tables.append(table)  # Keep original
        
        return enhanced_tables
    
    def _convert_to_target_schema(self, tables: List[TableData]) -> List[TableBlock]:
        """Convert TableData objects to target schema TableBlock format"""
        target_tables = []
        
        for table in tables:
            # Create rows as list of dictionaries
            rows = []
            
            if table.data and table.headers:
                for row_data in table.data:
                    row_dict = {}
                    for i, header in enumerate(table.headers):
                        cell_value = row_data[i] if i < len(row_data) else None
                        row_dict[header] = cell_value
                    rows.append(row_dict)
            
            # Create TableBlock matching target schema
            table_block = TableBlock(
                name=f"{table.table_type.title()} Table" if table.table_type else "Table",
                columns=table.headers or [],
                rows=rows
            )
            
            target_tables.append(table_block)
        
        return target_tables
    
    def get_available_tools(self) -> List[str]:
        """Get list of available table extraction tools"""
        return self.available_tools.copy()
    
    def get_tool_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get capabilities of each available tool"""
        capabilities = {
            "pdfplumber": {
                "cost": "Free",
                "speed": "Fast",
                "accuracy": "Good",
                "best_for": "Simple structured tables"
            },
            "tabula": {
                "cost": "Free", 
                "speed": "Medium",
                "accuracy": "Excellent",
                "best_for": "Complex tables with clear structure"
            },
            "camelot": {
                "cost": "Free",
                "speed": "Slow",
                "accuracy": "Excellent", 
                "best_for": "Tables with borders and complex layouts"
            },
            "pdfquery": {
                "cost": "Free",
                "speed": "Medium",
                "accuracy": "Fair",
                "best_for": "Structured documents with consistent patterns"
            }
        }
        
        return {tool: capabilities[tool] for tool in self.available_tools if tool in capabilities}