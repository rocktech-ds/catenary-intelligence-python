"""
Enhanced Analysis Models for Catenary Document Analyzer

This module defines the request/response models for all analysis capabilities
including the new advanced extractors.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass

@dataclass
class BoundingBox:
    """Represents a bounding box with coordinates"""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int

class AnalysisRequest(BaseModel):
    """Enhanced analysis request supporting all new extractors"""
    file_url: str = Field(..., description="URL to the document file")
    
    # Core analysis tools
    tools: Dict[str, bool] = Field(default_factory=lambda: {
        "pymupdf": True,
        "pdfplumber": True,
        "camelot": False,
        "tesseract_ocr": False,
        "paddle_ocr": False,
        "layout_parser": False,
        "table_transformer": False
    })
    
    # AI providers
    ai_providers: Dict[str, bool] = Field(default_factory=lambda: {
        "groq": True,
        "gemini": True,
        "grok": True,
        "consensus": True
    })
    
    # Enhanced analysis types - including new extractors
    analysis_types: Dict[str, bool] = Field(default_factory=lambda: {
        # Core analysis
        "extract_tables": True,
        "extract_callouts": True,
        "extract_key_values": True,
        "bom_analysis": True,
        
        # New advanced extractors
        "stamp_detection": True,
        "layout_analysis": True,
        "revision_tracking": True,
        "assembly_detection": True,
        "technical_specs": True,
        "dimensional_analysis": True,
        "vector_graphics": True,
        
        # Future extractors
        "handwriting_recognition": False,
        "standards_compliance": False,
        
        # AI enhancements
        "ai_consensus": True,
        "error_correction": True,
        "intelligent_normalization": True,
        "quality_validation": True
    })
    
    # Analysis options
    options: Dict[str, Any] = Field(default_factory=lambda: {
        # External services
        "use_external_services": True,
        "use_ai_enhancement": True,
        
        # Quality controls
        "confidence_threshold": 0.7,
        "enable_caching": True,
        "max_processing_time": 300,  # 5 minutes
        
        # Language settings
        "primary_language": "pt",
        "secondary_language": "en",
        "technical_terminology": True,
        
        # Output preferences
        "include_raw_results": False,
        "include_confidence_scores": True,
        "include_processing_metadata": True
    })

class StampDetectionResult(BaseModel):
    """Result from stamp detection analysis"""
    stamps: List[Dict[str, Any]] = Field(default_factory=list)
    processing_warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LayoutAnalysisResult(BaseModel):
    """Result from layout analysis"""
    layout_structure: Dict[str, Any] = Field(default_factory=dict)
    page_layouts: List[Dict[str, Any]] = Field(default_factory=list)
    processing_warnings: List[str] = Field(default_factory=list)
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)

class RevisionTrackingResult(BaseModel):
    """Result from revision tracking analysis"""
    revision_history: Dict[str, Any] = Field(default_factory=dict)
    processing_warnings: List[str] = Field(default_factory=list)
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)

class AssemblyDetectionResult(BaseModel):
    """Result from assembly detection analysis"""
    assembly_analysis: Dict[str, Any] = Field(default_factory=dict)
    processing_warnings: List[str] = Field(default_factory=list)
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)

class EnhancedAnalysisResult(BaseModel):
    """Complete enhanced analysis result"""
    analysis_id: str
    status: str = "completed"
    processing_time: Optional[float] = None
    
    # Core results
    core_results: Dict[str, Any] = Field(default_factory=dict)
    
    # New extractor results
    stamp_detection: Optional[StampDetectionResult] = None
    layout_analysis: Optional[LayoutAnalysisResult] = None
    revision_tracking: Optional[RevisionTrackingResult] = None
    assembly_detection: Optional[AssemblyDetectionResult] = None
    
    # AI enhancement results
    ai_consensus: Optional[Dict[str, Any]] = None
    quality_validation: Optional[Dict[str, Any]] = None
    
    # Aggregated insights
    composite_results: Dict[str, Any] = Field(default_factory=dict)
    processing_warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AnalysisStatus(BaseModel):
    """Analysis status response"""
    analysis_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[float] = None  # 0.0 to 1.0
    current_step: Optional[str] = None
    results: Optional[EnhancedAnalysisResult] = None
    error: Optional[str] = None
    
class ServiceHealth(BaseModel):
    """Service health status"""
    status: str
    timestamp: str
    version: str
    extractors_available: Dict[str, bool] = Field(default_factory=dict)
    ai_services_available: Dict[str, bool] = Field(default_factory=dict)
    external_services_available: Dict[str, bool] = Field(default_factory=dict)

class ExtractorCapabilities(BaseModel):
    """Available extractor capabilities"""
    core_extractors: List[str] = Field(default_factory=list)
    advanced_extractors: List[str] = Field(default_factory=list)
    ai_services: List[str] = Field(default_factory=list)
    external_services: List[str] = Field(default_factory=list)
    supported_formats: List[str] = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=list)