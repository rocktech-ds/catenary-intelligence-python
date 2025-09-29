"""
Advanced Table Extraction Module
Multi-method table extraction specialized for engineering drawings
"""
import pdfplumber
import pandas as pd

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    camelot = None
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import numpy as np
from loguru import logger

from ..core.config import IntelligenceConfig
from ..models.schemas import (
    TableData, BoundingBox, AnalysisRequest, ToolStatus
)
from ..models.target_schemas import (
    TableBlock, BOM_COLUMN_MAPPINGS, TABLE_HEADER_SCHEMA,
    PORTUGUESE_PATTERNS
)
from ..ai.llm_client import LLMClient
from .component_matcher import ComponentMatcher

class TableExtractor:
    """
    Advanced table extraction using multiple specialized tools:
    - PDFPlumber: Best for structured tables
    - Camelot: Best for complex layouts
    - Table Transformer: AI-based detection
    """
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.table_transformer_model = None
        self.llm_client = LLMClient(config)
        self.component_matcher = ComponentMatcher()
        self._loaded = False
    
    def load_models(self):
        """Load AI models for table detection"""
        try:
            # Load Table Transformer model if available
            try:
                from transformers import pipeline
                self.table_transformer_model = pipeline(
                    "object-detection",
                    model="microsoft/table-transformer-detection",
                    device=-1  # CPU
                )
                logger.info("Table Transformer model loaded")
            except Exception as e:
                logger.warning(f"Could not load Table Transformer: {e}")
            
            self._loaded = True
            
        except Exception as e:
            logger.error(f"Failed to load table extraction models: {e}")
    
    async def get_status(self) -> ToolStatus:
        """Get table extractor status"""
        return ToolStatus(
            available=self._loaded,
            version="1.0.0",
            load_time=None
        )
    
    async def extract_tables(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Extract tables using multiple methods and return best results
        """
        tables = []
        processing_warnings = []
        
        try:
            # Method 1: PDFPlumber (best for clean, structured tables)
            if request.tools.pdfplumber:
                pdfplumber_tables = self._extract_with_pdfplumber(file_path)
                tables.extend(pdfplumber_tables)
                logger.info(f"PDFPlumber found {len(pdfplumber_tables)} tables")
            
            # Method 2: Camelot (best for complex layouts)
            try:
                camelot_tables = self._extract_with_camelot(file_path)
                # Merge with existing tables, avoiding duplicates
                merged_tables = self._merge_table_results(tables, camelot_tables)
                tables = merged_tables
                logger.info(f"Total tables after Camelot: {len(tables)}")
            except Exception as e:
                processing_warnings.append(f"Camelot extraction failed: {str(e)}")
            
            # Method 3: Table Transformer (AI-based detection)
            if self.table_transformer_model and request.tools.table_transformer:
                try:
                    ai_tables = self._extract_with_table_transformer(file_path)
                    merged_tables = self._merge_table_results(tables, ai_tables)
                    tables = merged_tables
                    logger.info(f"Total tables after Table Transformer: {len(tables)}")
                except Exception as e:
                    processing_warnings.append(f"Table Transformer failed: {str(e)}")
            
            # Post-process and enhance tables with AI
            enhanced_tables = await self._enhance_tables_with_ai(tables, file_path, request)
            
            # Filter and rank tables by quality
            quality_tables = self._filter_by_quality(enhanced_tables)
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            processing_warnings.append(f"Table extraction error: {str(e)}")
        
        return {
            'tables': quality_tables,
            'processing_warnings': processing_warnings
        }
    
    def _extract_with_pdfplumber(self, file_path: Path) -> List[TableData]:
        """Extract tables using PDFPlumber"""
        tables = []
        
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    
                    # Use customized table settings
                    table_settings = self.config.tool_settings['pdfplumber']['table_settings']
                    
                    page_tables = page.extract_tables(table_settings)
                    
                    for i, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < 2:
                            continue
                        
                        # Get table bounding box
                        table_bbox = self._get_table_bbox_pdfplumber(page, table_data)
                        
                        # Create TableData object
                        table = TableData(
                            id=str(uuid.uuid4()),
                            bbox=BoundingBox(
                                x0=table_bbox[0],
                                y0=table_bbox[1],
                                x1=table_bbox[2],
                                y1=table_bbox[3],
                                page=page_num
                            ),
                            extraction_method="pdfplumber",
                            confidence=0.85,  # High confidence for PDFPlumber
                            rows=len(table_data),
                            cols=len(table_data[0]) if table_data else 0,
                            headers=table_data[0] if table_data else [],
                            data=table_data[1:] if len(table_data) > 1 else [],
                            cell_completeness=self._calculate_cell_completeness(table_data),
                            alignment_score=0.8  # Default for PDFPlumber
                        )
                        
                        # Identify table type (BOM, schedule, etc.)
                        table.table_type = self._identify_table_type(table)
                        
                        tables.append(table)
                        
        except Exception as e:
            logger.error(f"PDFPlumber table extraction failed: {e}")
        
        return tables
    
    def _extract_with_camelot(self, file_path: Path) -> List[TableData]:
        """Extract tables using Camelot"""
        tables = []
        
        if not CAMELOT_AVAILABLE:
            logger.warning("Camelot not available, skipping camelot table extraction")
            return tables
        
        try:
            # Extract tables with Camelot
            camelot_tables = camelot.read_pdf(
                str(file_path),
                flavor='lattice',  # Use lattice for bordered tables
                pages='all'
            )
            
            for i, table in enumerate(camelot_tables):
                if table.df.empty:
                    continue
                
                # Get table data
                df = table.df
                headers = df.iloc[0].tolist() if len(df) > 0 else []
                data = df.iloc[1:].values.tolist() if len(df) > 1 else []
                
                # Create TableData object
                table_data = TableData(
                    id=str(uuid.uuid4()),
                    bbox=BoundingBox(
                        x0=table._bbox[0],
                        y0=table._bbox[1],
                        x1=table._bbox[2],
                        y1=table._bbox[3],
                        page=int(table.page) - 1  # Camelot uses 1-based indexing
                    ),
                    extraction_method="camelot",
                    confidence=table.accuracy / 100.0,  # Convert to 0-1 scale
                    rows=len(df),
                    cols=len(df.columns),
                    headers=headers,
                    data=data,
                    cell_completeness=self._calculate_cell_completeness_df(df),
                    alignment_score=table.accuracy / 100.0
                )
                
                # Identify table type
                table_data.table_type = self._identify_table_type(table_data)
                
                tables.append(table_data)
                
        except Exception as e:
            logger.error(f"Camelot table extraction failed: {e}")
        
        return tables
    
    def _extract_with_table_transformer(self, file_path: Path) -> List[TableData]:
        """Extract tables using Table Transformer AI model"""
        tables = []
        
        if not self.table_transformer_model:
            return tables
        
        try:
            # Convert PDF pages to images for AI processing
            images = self._pdf_to_images(file_path)
            
            for page_num, image in enumerate(images):
                # Detect tables using AI
                detections = self.table_transformer_model(image)
                
                for detection in detections:
                    if detection['score'] > 0.7:  # High confidence threshold
                        
                        bbox = detection['box']
                        
                        table = TableData(
                            id=str(uuid.uuid4()),
                            bbox=BoundingBox(
                                x0=bbox['xmin'],
                                y0=bbox['ymin'],
                                x1=bbox['xmax'],
                                y1=bbox['ymax'],
                                page=page_num
                            ),
                            extraction_method="table_transformer",
                            confidence=detection['score'],
                            rows=0,  # Would need OCR to fill
                            cols=0,  # Would need OCR to fill
                            headers=[],
                            data=[],
                            cell_completeness=0.0,
                            alignment_score=detection['score']
                        )
                        
                        tables.append(table)
                        
        except Exception as e:
            logger.error(f"Table Transformer extraction failed: {e}")
        
        return tables
    
    def _merge_table_results(
        self, existing_tables: List[TableData], new_tables: List[TableData]
    ) -> List[TableData]:
        """Merge table results from different methods, avoiding duplicates"""
        
        merged = existing_tables.copy()
        
        for new_table in new_tables:
            # Check if this table overlaps significantly with existing tables
            is_duplicate = False
            
            for existing_table in existing_tables:
                if (existing_table.bbox.page == new_table.bbox.page and
                    self._calculate_bbox_overlap(existing_table.bbox, new_table.bbox) > 0.7):
                    is_duplicate = True
                    
                    # Keep the higher quality version
                    if new_table.confidence > existing_table.confidence:
                        merged.remove(existing_table)
                        merged.append(new_table)
                    break
            
            if not is_duplicate:
                merged.append(new_table)
        
        return merged

    def _enhance_bom_with_components(self, table: TableData) -> TableData:
        """Enhance BOM table by matching components from parts database"""
        if table.table_type != 'bom':
            return table

        try:
            # Convert table data to processable format
            bom_items = self._extract_bom_items_from_table(table)

            # Match components
            matched_items = self.component_matcher.batch_match_components(bom_items)

            # Update table data with matched components
            enhanced_table = self._update_table_with_matches(table, matched_items)

            logger.info(f"Enhanced BOM table {table.id} with {len(matched_items)} component matches")
            return enhanced_table

        except Exception as e:
            logger.warning(f"Failed to enhance BOM table {table.id} with components: {e}")
            return table

    def _extract_bom_items_from_table(self, table: TableData) -> List[Dict]:
        """Extract individual BOM items from table data"""
        items = []
        headers = [h.lower() for h in table.headers]

        # Map headers to standard fields
        header_mapping = {}
        for i, header in enumerate(headers):
            if any(kw in header for kw in ['nomenclat', 'nomenclatura']):
                header_mapping['nomenclatura'] = i
            elif any(kw in header for kw in ['ref', 'referência']):
                header_mapping['ref'] = i
            elif any(kw in header for kw in ['codigo', 'código', 'code']):
                header_mapping['codigo'] = i
            elif any(kw in header for kw in ['designa', 'description']):
                header_mapping['designacao'] = i
            elif any(kw in header for kw in ['quantidade', 'qtd', 'qty']):
                header_mapping['quantidade'] = i

        # Extract items
        for row in table.data:
            if len(row) >= len(headers):
                item = {}

                # Extract values based on header mapping
                for field, col_idx in header_mapping.items():
                    if col_idx < len(row):
                        item[field] = row[col_idx].strip() if row[col_idx] else ""

                # Only add items that have some identifying information
                if any(item.get(field) for field in ['nomenclatura', 'codigo', 'ref', 'designacao']):
                    items.append(item)

        return items

    def _update_table_with_matches(self, table: TableData, matched_items: List[Dict]) -> TableData:
        """Update table with component matching information"""
        enhanced_table = table.model_copy()

        # Add metadata about component matches
        match_stats = {
            'total_items': len(matched_items),
            'matched_items': sum(1 for item in matched_items if item.get('match_confidence', 0) > 0),
            'high_confidence_matches': sum(1 for item in matched_items if item.get('match_confidence', 0) > 90),
            'average_confidence': sum(item.get('match_confidence', 0) for item in matched_items) / len(matched_items) if matched_items else 0
        }

        enhanced_table.metadata = enhanced_table.metadata or {}
        enhanced_table.metadata['component_matches'] = match_stats
        enhanced_table.metadata['components'] = matched_items

        # Update confidence based on component matching success
        if match_stats['matched_items'] > 0:
            component_bonus = min(20, match_stats['matched_items'] / match_stats['total_items'] * 20)
            enhanced_table.confidence = min(100, enhanced_table.confidence + component_bonus)

        return enhanced_table
    
    async def _enhance_tables_with_ai(self, tables: List[TableData], file_path: Path, request: AnalysisRequest) -> List[TableData]:
        """Enhance extracted tables with AI-powered analysis"""
        enhanced = []
        
        for table in tables:
            try:
                # Skip AI enhancement if disabled
                if not request.ai_enhancement.enabled:
                    enhanced_table = self._add_engineering_context(table)
                    enhanced.append(enhanced_table)
                    continue
                
                # Apply AI enhancements
                enhanced_table = await self._ai_enhance_table(table, request)

                # Apply component matching for BOM tables
                if enhanced_table.table_type == 'bom':
                    enhanced_table = self._enhance_bom_with_components(enhanced_table)

                enhanced.append(enhanced_table)
                
            except Exception as e:
                logger.warning(f"Failed to enhance table {table.id}: {e}")
                # Fallback to rule-based enhancement
                enhanced_table = self._add_engineering_context(table)

                # Apply component matching for BOM tables even in fallback
                if enhanced_table.table_type == 'bom':
                    enhanced_table = self._enhance_bom_with_components(enhanced_table)

                enhanced.append(enhanced_table)
        
        return enhanced
    
    def _filter_by_quality(self, tables: List[TableData]) -> List[TableData]:
        """Filter tables by quality metrics"""
        quality_tables = []
        
        for table in tables:
            # Quality criteria
            min_cells = self.config.min_table_cells
            min_confidence = self.config.table_quality_threshold
            
            if (table.rows * table.cols >= min_cells and
                table.confidence >= min_confidence and
                table.cell_completeness > 0.3):  # At least 30% cells filled
                
                quality_tables.append(table)
        
        # Sort by quality score (combination of confidence and completeness)
        quality_tables.sort(
            key=lambda t: t.confidence * t.cell_completeness,
            reverse=True
        )
        
        return quality_tables
    
    def _identify_table_type(self, table: TableData) -> str:
        """Identify the type of engineering table"""
        headers_text = ' '.join(table.headers).lower()

        # BOM (Bill of Materials) detection - Portuguese and English
        bom_keywords = [
            # Portuguese BOM keywords
            'nomenclat', 'nomenclatura', 'designação', 'designacao',
            'ref.', 'ref', 'referência', 'codigo', 'código',
            'quantidade', 'qtd', 'qnt', 'peso', 'observações', 'observacoes',
            'desenho', 'material', 'especificação', 'especificacao',
            # English BOM keywords
            'item', 'qty', 'quantity', 'part', 'description', 'material',
            'reference', 'code', 'weight', 'notes', 'drawing'
        ]

        # Count matching keywords (need at least 2 for BOM identification)
        bom_matches = sum(1 for keyword in bom_keywords if keyword in headers_text)
        if bom_matches >= 2:
            return 'bom'
        
        # Schedule detection
        schedule_keywords = ['schedule', 'date', 'activity', 'duration']
        if any(keyword in headers_text for keyword in schedule_keywords):
            return 'schedule'
        
        # Specifications table
        spec_keywords = ['specification', 'value', 'unit', 'tolerance']
        if any(keyword in headers_text for keyword in spec_keywords):
            return 'specifications'
        
        # Legend/symbol table
        legend_keywords = ['symbol', 'legend', 'note', 'abbreviation']
        if any(keyword in headers_text for keyword in legend_keywords):
            return 'legend'
        
        return 'general'
    
    async def _ai_enhance_table(self, table: TableData, request: AnalysisRequest) -> TableData:
        """Use AI to enhance table data with normalized headers and cleaned content"""
        try:
            # Step 1: Normalize headers using AI
            normalized_headers = await self._ai_normalize_headers(table.headers, table.table_type)
            
            # Step 2: Clean and validate table data using AI
            cleaned_data = await self._ai_clean_table_data(table.data, normalized_headers, table.table_type)
            
            # Step 3: Convert to target schema format
            target_table = self._convert_to_target_format(table, normalized_headers, cleaned_data)
            
            return target_table
            
        except Exception as e:
            logger.warning(f"AI table enhancement failed for table {table.id}: {e}")
            # Fallback to rule-based enhancement
            return self._add_engineering_context(table)
    
    async def _ai_normalize_headers(self, headers: List[str], table_type: str) -> Dict[str, str]:
        """Use AI to normalize and map table headers to canonical format"""
        if not headers or all(not h.strip() for h in headers):
            return {}
        
        system_prompt = f"""
        You are an expert in Portuguese engineering documentation analysis.
        
        Task: Normalize table headers to canonical BOM format.
        
        Context:
        - Table type: {table_type}
        - This is a Portuguese engineering drawing document
        - Headers may contain variations, abbreviations, or formatting issues
        
        Canonical BOM headers: {list(set(BOM_COLUMN_MAPPINGS.values()))}
        
        Rules:
        1. Map original headers to closest canonical equivalent
        2. Handle common Portuguese variations and abbreviations
        3. If no good match exists, keep original but clean formatting
        4. Return confidence score (0.0-1.0) for mapping quality
        
        Return JSON matching this schema exactly:
        {{
            "mapping": {{"original_header": "canonical_header"}},
            "confidence": 0.85
        }}
        """
        
        user_prompt = f"""
        Original table headers to normalize:
        {headers}
        
        Please provide normalized header mapping.
        """
        
        try:
            result = await self.llm_client.extract_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=TABLE_HEADER_SCHEMA,
                model_preference=["grok", "gemini", "groq"]
            )
            
            if result and "mapping" in result:
                return result["mapping"]
            
        except Exception as e:
            logger.warning(f"AI header normalization failed: {e}")
        
        # Fallback to rule-based mapping
        return self._rule_based_header_mapping(headers)
    
    async def _ai_clean_table_data(self, data: List[List[str]], header_mapping: Dict[str, str], table_type: str) -> List[List[str]]:
        """Use AI to clean and validate table data entries"""
        if not data or not header_mapping:
            return data
        
        # For large tables, process in chunks
        if len(data) > 20:
            return await self._ai_clean_table_chunks(data, header_mapping, table_type)
        
        system_prompt = f"""
        You are an expert in Portuguese engineering documentation data cleaning.
        
        Task: Clean and normalize table data entries.
        
        Context:
        - Table type: {table_type}
        - Headers: {list(header_mapping.values())}
        - This is Portuguese engineering drawing BOM/parts data
        
        Cleaning rules:
        1. Fix common OCR errors in Portuguese text
        2. Standardize part numbers and references
        3. Clean quantity values (numbers only)
        4. Normalize material descriptions
        5. Remove extra whitespace and fix encoding issues
        6. Keep original structure (same number of rows/columns)
        
        Return cleaned data maintaining exact row/column structure.
        """
        
        user_prompt = f"""
        Table data to clean (first 5 rows shown):
        Headers: {list(header_mapping.keys())}
        
        Data:
        {data[:5]}
        
        Please return cleaned data in same format.
        """
        
        try:
            # For data cleaning, we expect the LLM to return the cleaned table structure
            result = await self.llm_client.extract_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema={"cleaned_data": [["string"]]},  # Array of arrays
                model_preference=["gemini", "grok", "groq"]
            )
            
            if result and "cleaned_data" in result:
                return result["cleaned_data"]
            
        except Exception as e:
            logger.warning(f"AI data cleaning failed: {e}")
        
        # Fallback to rule-based cleaning
        return self._rule_based_data_cleaning(data)
    
    async def _ai_clean_table_chunks(self, data: List[List[str]], header_mapping: Dict[str, str], table_type: str) -> List[List[str]]:
        """Process large tables in chunks for AI cleaning"""
        chunk_size = 10
        cleaned_data = []
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            try:
                cleaned_chunk = await self._ai_clean_table_data(chunk, header_mapping, table_type)
                cleaned_data.extend(cleaned_chunk)
            except Exception as e:
                logger.warning(f"Failed to clean chunk {i//chunk_size + 1}: {e}")
                # Use original chunk if cleaning fails
                cleaned_data.extend(chunk)
        
        return cleaned_data
    
    def _convert_to_target_format(self, original_table: TableData, header_mapping: Dict[str, str], cleaned_data: List[List[str]]) -> TableData:
        """Convert enhanced table to target schema format"""
        # Create a copy of the original table with enhancements
        enhanced_table = TableData(
            id=original_table.id,
            bbox=original_table.bbox,
            extraction_method=f"{original_table.extraction_method}+AI",
            confidence=min(original_table.confidence + 0.1, 1.0),  # Slight confidence boost
            rows=len(cleaned_data) + 1,  # +1 for headers
            cols=len(header_mapping),
            headers=list(header_mapping.values()),  # Use canonical headers
            data=cleaned_data,
            cell_completeness=self._calculate_cell_completeness(cleaned_data),
            alignment_score=original_table.alignment_score,
            table_type=original_table.table_type
        )
        
        return enhanced_table
    
    def _rule_based_header_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Fallback rule-based header normalization"""
        mapping = {}
        
        for header in headers:
            if not header or not header.strip():
                continue
            
            clean_header = header.strip().upper()
            
            # Direct mapping from BOM_COLUMN_MAPPINGS
            if clean_header in BOM_COLUMN_MAPPINGS:
                mapping[header] = BOM_COLUMN_MAPPINGS[clean_header]
            else:
                # Fuzzy matching for common variations
                for variation, canonical in BOM_COLUMN_MAPPINGS.items():
                    if variation.lower() in clean_header.lower() or clean_header.lower() in variation.lower():
                        mapping[header] = canonical
                        break
                else:
                    # Keep original if no match
                    mapping[header] = clean_header
        
        return mapping
    
    def _rule_based_data_cleaning(self, data: List[List[str]]) -> List[List[str]]:
        """Fallback rule-based data cleaning"""
        cleaned = []
        
        for row in data:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # Basic cleaning: strip whitespace, fix common issues
                    cleaned_cell = str(cell).strip()
                    # Remove extra whitespace
                    cleaned_cell = ' '.join(cleaned_cell.split())
                    cleaned_row.append(cleaned_cell)
            cleaned.append(cleaned_row)
        
        return cleaned
    
    def convert_to_target_schema(self, tables: List[TableData]) -> List[TableBlock]:
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
    
    def _add_engineering_context(self, table: TableData) -> TableData:
        """Add engineering-specific context to table (rule-based fallback)"""
        # Apply rule-based header normalization if not already done
        if table.headers:
            header_mapping = self._rule_based_header_mapping(table.headers)
            table.headers = list(header_mapping.values())
        
        # Apply basic data cleaning
        if table.data:
            table.data = self._rule_based_data_cleaning(table.data)
        
        return table
    
    def _calculate_cell_completeness(self, table_data: List[List[str]]) -> float:
        """Calculate percentage of non-empty cells"""
        if not table_data:
            return 0.0
        
        total_cells = sum(len(row) for row in table_data)
        filled_cells = sum(
            len([cell for cell in row if cell and str(cell).strip()])
            for row in table_data
        )
        
        return filled_cells / total_cells if total_cells > 0 else 0.0
    
    def _calculate_cell_completeness_df(self, df: pd.DataFrame) -> float:
        """Calculate cell completeness for pandas DataFrame"""
        if df.empty:
            return 0.0
        
        total_cells = df.size
        filled_cells = df.notna().sum().sum()
        
        return filled_cells / total_cells if total_cells > 0 else 0.0
    
    def _calculate_bbox_overlap(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """Calculate overlap ratio between two bounding boxes"""
        # Calculate intersection
        x_left = max(bbox1.x0, bbox2.x0)
        y_top = max(bbox1.y0, bbox2.y0)
        x_right = min(bbox1.x1, bbox2.x1)
        y_bottom = min(bbox1.y1, bbox2.y1)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = (bbox1.x1 - bbox1.x0) * (bbox1.y1 - bbox1.y0)
        area2 = (bbox2.x1 - bbox2.x0) * (bbox2.y1 - bbox2.y0)
        union_area = area1 + area2 - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def _get_table_bbox_pdfplumber(self, page, table_data: List[List[str]]) -> tuple:
        """Estimate table bounding box from PDFPlumber"""
        # This is a simplified implementation
        # In practice, you'd use page.chars to find the actual text positions
        return (0, 0, page.width, page.height / len(table_data))
    
    def _pdf_to_images(self, file_path: Path) -> List:
        """Convert PDF pages to images for AI processing"""
        # This would implement PDF to image conversion
        # Placeholder for now
        return []