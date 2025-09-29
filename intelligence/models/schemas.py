"""
Gold-standard JSON schemas for PDF intelligence pipeline
Comprehensive type definitions for engineering drawing analysis
"""
from typing import Dict, List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class AnalysisTools(str, Enum):
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"
    TESSERACT_OCR = "tesseract_ocr"
    PADDLE_OCR = "paddle_ocr"
    LAYOUT_PARSER = "layout_parser"
    TABLE_TRANSFORMER = "table_transformer"
    OPENCV_VISION = "opencv_vision"

class ExtractionType(str, Enum):
    LAYOUT_DETECTION = "layout_detection"
    TABLE_EXTRACTION = "table_extraction"
    CALLOUT_LINKING = "callout_linking"
    KEY_VALUE_PAIRS = "key_value_pairs"
    STAMP_DETECTION = "stamp_detection"
    REFERENCE_MAPPING = "reference_mapping"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Request schemas
class ToolsConfig(BaseModel):
    pymupdf: bool = True
    pdfplumber: bool = True
    tesseract_ocr: bool = False
    paddle_ocr: bool = True
    layout_parser: bool = True
    table_transformer: bool = True
    opencv_vision: bool = True

class ExtractionOptions(BaseModel):
    extract_images: bool = True
    extract_tables: bool = True
    extract_callouts: bool = True
    extract_stamps: bool = True
    extract_metadata: bool = True
    ocr_scanned_pages: bool = True
    link_references: bool = True
    process_multi_page: bool = True
    detect_handwriting: bool = False

class AnalysisRequest(BaseModel):
    file_url: str
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    options: ExtractionOptions = Field(default_factory=ExtractionOptions)
    priority: int = Field(default=1, ge=1, le=5)
    callback_url: Optional[str] = None

# Core data structures
class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    confidence: Optional[float] = None

class TextElement(BaseModel):
    text: str
    bbox: BoundingBox
    font: Optional[str] = None
    font_size: Optional[float] = None
    font_flags: Optional[int] = None
    confidence: Optional[float] = None
    language: Optional[str] = None

class TableData(BaseModel):
    """Enhanced table structure for engineering drawings"""
    id: str
    bbox: BoundingBox
    extraction_method: str  # pdfplumber, camelot, table-transformer
    confidence: float

    # Table structure
    rows: int
    cols: int
    headers: List[str]
    data: List[List[str]]

    # Engineering-specific metadata
    table_type: Optional[str] = None  # bom, schedule, specs, etc
    related_callouts: List[str] = Field(default_factory=list)
    referenced_drawings: List[str] = Field(default_factory=list)

    # Quality metrics
    cell_completeness: float  # % of non-empty cells
    alignment_score: float    # geometric alignment quality
    ocr_quality: Optional[float] = None

class CalloutData(BaseModel):
    """Engineering drawing callout/reference system"""
    id: str
    text: str
    bbox: BoundingBox
    confidence: float

    # Callout properties
    callout_type: str  # number, letter, symbol, detail_ref
    reference_target: Optional[str] = None
    leader_line: Optional[List[Tuple[float, float]]] = None

    # Relationships
    linked_table_rows: List[str] = Field(default_factory=list)
    linked_elements: List[str] = Field(default_factory=list)
    part_number: Optional[str] = None
    specification: Optional[str] = None

class StampData(BaseModel):
    """Engineering stamps and seals"""
    id: str
    bbox: BoundingBox
    stamp_type: str  # approval, revision, company, professional
    confidence: float

    # Extracted information
    text_content: Dict[str, Any] = Field(default_factory=dict)
    date_stamp: Optional[datetime] = None
    signature_detected: bool = False

    # Metadata
    template_match: Optional[str] = None
    ocr_method: Optional[str] = None

class KeyValuePair(BaseModel):
    """Key-value extraction for specifications"""
    key: str
    value: str
    bbox: BoundingBox
    confidence: float

    # Context
    section: Optional[str] = None  # title block, notes, specs
    data_type: Optional[str] = None  # dimension, material, tolerance
    units: Optional[str] = None

class LayoutRegion(BaseModel):
    """Page layout detection"""
    id: str
    region_type: str  # drawing, table, title_block, notes, legend
    bbox: BoundingBox
    confidence: float

    # Content summary
    primary_content: str
    element_count: int
    text_density: float

    # Relationships
    contains_elements: List[str] = Field(default_factory=list)

# Response schemas
class ExtractionMetrics(BaseModel):
    """Quality and performance metrics"""
    processing_time: float
    file_size_mb: float
    page_count: int

    # Quality scores (0-1)
    overall_quality: float
    text_extraction_quality: float
    table_extraction_quality: float
    layout_detection_quality: float

    # Tool performance
    tools_used: List[str]
    primary_extraction_method: str
    fallback_methods_used: List[str]

    # Statistics
    total_text_elements: int
    total_tables: int
    total_callouts: int
    total_stamps: int
    total_kv_pairs: int

class PageAnalysis(BaseModel):
    """Per-page analysis results"""
    page_number: int
    dimensions: Tuple[float, float]  # width, height

    # Elements on this page
    text_elements: List[TextElement]
    tables: List[TableData]
    callouts: List[CalloutData]
    stamps: List[StampData]
    layout_regions: List[LayoutRegion]
    key_value_pairs: List[KeyValuePair]

    # Page-level metrics
    text_coverage: float  # % of page with text
    drawing_coverage: float  # % with technical drawing
    confidence_score: float

class DocumentMetadata(BaseModel):
    """Comprehensive document metadata"""
    title: Optional[str] = None
    subject: Optional[str] = None
    author: Optional[str] = None
    creator: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None

    # Engineering-specific
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    scale: Optional[str] = None
    sheet_size: Optional[str] = None
    project_name: Optional[str] = None
    client: Optional[str] = None

    # Technical properties
    pdf_version: Optional[str] = None
    is_scanned: bool = False
    has_layers: bool = False
    color_mode: Optional[str] = None

    # Languages detected
    languages: List[str] = Field(default_factory=list)
    primary_language: Optional[str] = None

class ExtractionResult(BaseModel):
    """Complete extraction results - Gold Standard Schema"""
    # Analysis metadata
    analysis_id: str
    document_metadata: DocumentMetadata
    extraction_metrics: ExtractionMetrics
    processing_timestamp: datetime

    # Per-page results
    pages: List[PageAnalysis]

    # Cross-page aggregations
    all_tables: List[TableData]
    all_callouts: List[CalloutData]
    all_stamps: List[StampData]
    all_key_value_pairs: List[KeyValuePair]

    # Engineering drawing intelligence
    bom_tables: List[TableData]  # Identified BOMs
    reference_map: Dict[str, List[str]]  # callout -> referenced items
    specification_summary: Dict[str, Any]
    revision_history: List[Dict[str, Any]]

    # Cross-references and relationships
    element_relationships: Dict[str, List[str]]
    drawing_hierarchy: Optional[Dict[str, Any]] = None

    # Quality and confidence
    extraction_confidence: float
    validation_results: Dict[str, Any]
    processing_warnings: List[str] = Field(default_factory=list)

# Status and monitoring schemas
class PipelineStatus(BaseModel):
    analysis_id: str
    status: ProcessingStatus
    progress: float = Field(ge=0, le=1)
    current_stage: str

    # Timing
    started_at: datetime
    estimated_completion: Optional[datetime] = None

    # Progress details
    pages_processed: int
    total_pages: int
    current_operation: str

    # Intermediate results available
    partial_results_available: bool = False

class AnalysisResponse(BaseModel):
    analysis_id: str
    task_id: str
    status: ProcessingStatus
    message: str
    estimated_duration: Optional[int] = None  # seconds

class ToolStatus(BaseModel):
    available: bool
    version: Optional[str] = None
    load_time: Optional[float] = None
    last_error: Optional[str] = None

class ToolsStatus(BaseModel):
    pipeline_ready: bool
    tools: Dict[str, ToolStatus]
    models_loaded: Dict[str, bool]
    system_info: Dict[str, Any]