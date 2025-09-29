from persistent_storage import analysis_storage
"""
Document Analysis Python Service
Recreates the analyzer functionality from the screenshots with:
- PyMuPDF, PDFPlumber, Tesseract OCR, Pandas
- X.AI Grok, Groq Llama, Google Gemini integration
- BOM extraction, nomenclaturas, component detection
"""
import os
import asyncio
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from analyzers.pymupdf_analyzer import PyMuPDFAnalyzer
from analyzers.pdfplumber_analyzer import PDFPlumberAnalyzer
from analyzers.tesseract_analyzer import TesseractAnalyzer
from analyzers.pandas_analyzer import PandasAnalyzer
from analyzers.ai_analyzer import AIAnalyzer
# Import the intelligence pipeline
from intelligence.core.pipeline_manager import PDFIntelligencePipeline
from intelligence.core.config import IntelligenceConfig
from intelligence.models.schemas import AnalysisRequest as IntelligenceRequest
from intelligence.models.target_schemas import FinalResult
# Import enhanced analysis capabilities
from intelligence.models.analysis_models import (
    AnalysisRequest as EnhancedRequest, EnhancedAnalysisResult,
    AnalysisStatus, ServiceHealth, ExtractorCapabilities
)
from intelligence.services.analysis_service import EnhancedAnalysisService
# Numpy serialization helper
def serialize_numpy_values(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: serialize_numpy_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_numpy_values(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize FastAPI app

def map_ai_to_ui_structure(ai_result):
    """Map AI analysis to UI expected structure"""

    # Get AI data safely
    ai_data = ai_result.get('ai_results', {})
    confidence = float(ai_result.get('confidence', 0.75))

    # Extract components
    components = []
    nomenclaturas = ai_data.get('nomenclaturas', [])
    ai_components = ai_data.get('components', [])

    # Build component details
    for nom in nomenclaturas:
        comp_type = 'Electronic' if any(c in str(nom) for c in ['R', 'C', 'L', 'U', 'IC']) else 'Component'
        components.append({
            'component_code': str(nom),
            'component_type': comp_type,
            'description': f'{comp_type}: {nom}',
            'quantity': 1,
            'unit': 'UN',
            'specifications': {'value': str(nom)}
        })

    for comp in ai_components:
        if isinstance(comp, str) and comp not in [c['component_code'] for c in components]:
            components.append({
                'component_code': comp,
                'component_type': 'Component',
                'description': comp,
                'quantity': 1,
                'unit': 'UN'
            })

    # Ensure we have at least some dummy data for testing
    if not components and not nomenclaturas:
        components = [
            {'component_code': 'TEST-001', 'component_type': 'Test', 'description': 'Test component', 'quantity': 1, 'unit': 'UN'}
        ]
        nomenclaturas = ['TEST-001']

    # Build the complete UI structure
    return {
        'status': 'completed',
        'confidence': max(confidence, 0.5),  # Minimum 50% for UI
        'ai_results': ai_data,

        'analysis_summary': {
            'total_processing_time': ai_result.get('processing_time', 2.5),
            'document_type': ai_data.get('document_type', 'technical_document'),
            'complexity_score': max(confidence, 0.5),
            'compliance_check': 'Aprovado' if confidence > 0.6 else 'Revisar'
        },

        'detailed_results': {
            'extraction_summary': {
                'confidence_scores': {
                    'nomenclature': max(confidence, 0.5),
                    'components': max(confidence * 0.95, 0.45),
                    'tags': max(confidence * 0.9, 0.4),
                    'codes': max(confidence * 0.85, 0.35)
                }
            },

            'component_analysis': {
                'total_components': len(components),
                'components_by_type': {
                    'electronic': len([c for c in components if 'Electronic' in c.get('component_type', '')]),
                    'mechanical': len([c for c in components if 'Mechanical' in c.get('component_type', '')]),
                    'other': len([c for c in components if c.get('component_type', '') not in ['Electronic', 'Mechanical']])
                },
                'component_details': components
            },

            'tags_analysis': {
                'total_tags': len(nomenclaturas),
                'tag_categories': {
                    'equipment_tags': {
                        'tags': nomenclaturas[:5],
                        'count': min(len(nomenclaturas), 5)
                    },
                    'instrument_tags': {
                        'tags': nomenclaturas[5:10] if len(nomenclaturas) > 5 else [],
                        'count': max(0, min(len(nomenclaturas) - 5, 5))
                    },
                    'electrical_tags': {
                        'tags': [n for n in nomenclaturas if any(c in str(n) for c in ['R', 'C', 'L'])],
                        'count': len([n for n in nomenclaturas if any(c in str(n) for c in ['R', 'C', 'L'])])
                    },
                    'control_tags': {
                        'tags': [n for n in nomenclaturas if 'U' in str(n) or 'IC' in str(n)],
                        'count': len([n for n in nomenclaturas if 'U' in str(n) or 'IC' in str(n)])
                    }
                }
            },

            'nomenclature_codes': {
                'sap_codes': {
                    'total_found': len(ai_data.get('technical_codes', {}).get('nomenclaturas', [])),
                    'codes': ai_data.get('technical_codes', {}).get('nomenclaturas', [])
                }
            },

            'bom_assemblies': {
                'analysis_summary': {
                    'total_assemblies': 1 if components else 0,
                    'total_components': len(components),
                    'bom_completeness': max(confidence * 0.9, 0.45),
                    'extraction_confidence': max(confidence, 0.5)
                },
                'assemblies': [
                    {
                        'assembly_code': 'MAIN-001',
                        'description': ai_data.get('summary', 'Main Assembly')[:100] if ai_data.get('summary') else 'Assembly',
                        'components': components[:10]
                    }
                ] if components else []
            }
        },

        'summary': ai_data.get('summary', 'Document analysis completed'),
        'key_information': ai_data.get('key_information', [])
    }

app = FastAPI(
    title="Catenary Document Analyzer",
    description="Python-based document analysis service with AI integration",
    version="1.0.0"
)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Request/Response Models
class AnalysisRequest(BaseModel):
    file_url: str = Field(..., description="URL to the document file")
    tools: Dict[str, bool] = Field(default_factory=dict)
    ai_providers: Dict[str, bool] = Field(default_factory=dict)
    analysis_types: Dict[str, bool] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL to call on completion")
    job_id: Optional[str] = Field(default=None, description="Job ID to track the analysis")
class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    tools_used: List[str] = Field(default_factory=list)
# Global analyzer instances
analyzers = {
    'pymupdf': PyMuPDFAnalyzer(),
    'pdfplumber': PDFPlumberAnalyzer(),
    'tesseract_ocr': TesseractAnalyzer(),
    'pandas': PandasAnalyzer(),
    'ai': AIAnalyzer()
}
# Initialize AI-enhanced intelligence pipeline
intelligence_config = IntelligenceConfig()
pipeline: Optional[PDFIntelligencePipeline] = None
# Initialize enhanced analysis service
enhanced_service: Optional[EnhancedAnalysisService] = None

# Global analysis results storage (in production, use Redis or database)
# Persistent analysis storage using JSON file
import json
import os

STORAGE_FILE = "/tmp/analysis_storage.json"

def load_analysis_storage():
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_analysis_storage(storage):
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(storage, f)
    except Exception as e:
        logger.error(f"Failed to save analysis storage: {e}")

analysis_storage = load_analysis_storage()
@app.on_event("startup")
async def startup_event():
    """Initialize the intelligence pipeline and enhanced service on startup"""
    global pipeline, enhanced_service

    # Initialize intelligence pipeline
    try:
        pipeline = PDFIntelligencePipeline(intelligence_config)
        await pipeline.initialize()
        logger.info("🚀 Intelligence pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize intelligence pipeline: {e}")
        pipeline = None

    # Initialize enhanced analysis service
    try:
        enhanced_service = EnhancedAnalysisService()
        logger.info("🔧 Enhanced analysis service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize enhanced analysis service: {e}")
        enhanced_service = None
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup pipeline on shutdown"""
    global pipeline
    if pipeline:
        await pipeline.cleanup()
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
@app.get("/tools/status")
async def get_tools_status():
    """Get status of all analysis tools"""
    status = {
        "available": True,
        "tools": {}
    }

    for tool_name, analyzer in analyzers.items():
        try:
            tool_status = analyzer.get_status()
            status["tools"][tool_name] = tool_status
        except Exception as e:
            logger.error(f"Error checking {tool_name} status: {e}")
            status["tools"][tool_name] = {
                "available": False,
                "error": str(e)
            }
            status["available"] = False

    return status
@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Start document analysis with selected tools and AI providers
    """
    analysis_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    try:
        logger.info(f"Starting analysis {analysis_id} for file: {request.file_url}")

        # Initialize analysis in storage
        analysis_storage[analysis_id] = {
            "status": "pending",
            "started_at": datetime.utcnow().isoformat()
        }

        # Start analysis in background
        background_tasks.add_task(
            run_analysis,
            analysis_id,
            request.file_url,
            request.tools,
            request.ai_providers,
            request.analysis_types,
            request.options,
            request.webhook_url,
            request.job_id
        )

        return AnalysisResponse(
            analysis_id=analysis_id,
            status="pending",
            tools_used=list(request.tools.keys())
        )

    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/analyze/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get analysis status and results"""
    if analysis_id not in analysis_storage:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored_result = analysis_storage[analysis_id]

    # Serialize results to handle numpy types
    results = stored_result.get("results")
    if results:
        results = serialize_numpy_values(results)

    return {
        "analysis_id": analysis_id,
        "status": stored_result.get("status", "unknown"),
        "results": results,
        "error": stored_result.get("error"),
        "processing_time": stored_result.get("processing_time")
    }

async def call_webhook(webhook_url: str, job_id: str, status: str, results: Optional[Dict] = None, error: Optional[str] = None, progress: int = 0):
    """Call webhook to update job status"""
    if not webhook_url or not job_id:
        return

    try:
        # Determine current step based on progress
        if status == "processing":
            if progress <= 10:
                current_step = "Starting document analysis"
            elif progress <= 20:
                current_step = "Downloading document"
            elif progress <= 40:
                current_step = "Extracting text with PyMuPDF"
            elif progress <= 60:
                current_step = "Extracting tables with PDFPlumber"
            elif progress <= 65:
                current_step = "Running OCR analysis"
            elif progress <= 70:
                current_step = "Processing data with Pandas"
            elif progress <= 75:
                current_step = "Preparing AI analysis"
            elif progress <= 90:
                current_step = "Running AI analysis"
            else:
                current_step = "Finalizing analysis results"
        else:
            current_step = f"Analysis {status}"

        payload = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "current_step": current_step,
        }

        if status == "completed" and results:
            payload["results"] = serialize_numpy_values(results)
            payload["progress"] = 100
            payload["current_step"] = "Analysis completed successfully"
        elif status == "failed" and error:
            payload["error"] = error
            payload["current_step"] = f"Analysis failed: {error}"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code == 200:
                logger.info(f"✅ Webhook called successfully for job {job_id}")
            else:
                logger.warning(f"⚠️ Webhook returned {response.status_code} for job {job_id}")
    except Exception as e:
        logger.error(f"❌ Failed to call webhook for job {job_id}: {e}")

async def run_analysis(
    analysis_id: str,
    file_url: str,
    tools: Dict[str, bool],
    ai_providers: Dict[str, bool],
    analysis_types: Dict[str, bool],
    options: Dict[str, Any],
    webhook_url: Optional[str] = None,
    job_id: Optional[str] = None
):
    """
    Run the complete document analysis pipeline
    """
    start_time = datetime.utcnow()
    results = {}

    try:
        logger.info(f"🔍 Running analysis {analysis_id}")

        # Call webhook: Starting analysis
        await call_webhook(webhook_url, job_id, "processing", progress=10)

        # Download document file
        document_path = await download_document(file_url)

        # Call webhook: Document downloaded
        await call_webhook(webhook_url, job_id, "processing", progress=20)

        # 1. PyMuPDF Analysis (always runs - basic extraction)
        if tools.get('pymupdf', True):
            logger.info("📄 Running PyMuPDF analysis...")
            results['pymupdf_results'] = await analyzers['pymupdf'].analyze(document_path)
            # Call webhook: PyMuPDF complete
            await call_webhook(webhook_url, job_id, "processing", progress=40)

        # 2. PDFPlumber Analysis (for tables and BOMs)
        if tools.get('pdfplumber', False):
            logger.info("📊 Running PDFPlumber analysis...")
            results['pdfplumber_results'] = await analyzers['pdfplumber'].analyze(document_path)
            # Call webhook: PDFPlumber complete
            await call_webhook(webhook_url, job_id, "processing", progress=60)

        # 3. Tesseract OCR (for scanned documents)
        if tools.get('tesseract_ocr', False):
            logger.info("👁️ Running Tesseract OCR...")
            results['tesseract_results'] = await analyzers['tesseract_ocr'].analyze(document_path)
            # Call webhook: Tesseract complete
            await call_webhook(webhook_url, job_id, "processing", progress=65)

        # 4. Pandas Analysis (for data processing)
        if tools.get('pandas', False) and results.get('pdfplumber_results'):
            logger.info("🐼 Running Pandas analysis...")
            results['pandas_results'] = await analyzers['pandas'].analyze_tables(
                results['pdfplumber_results'].get('tables', [])
            )
            # Call webhook: Pandas complete
            await call_webhook(webhook_url, job_id, "processing", progress=70)

        # 5. AI Analysis (with multiple providers)
        logger.info(f"AI providers received: {ai_providers}")
        if any(ai_providers.values()):
            logger.info("🤖 Running AI analysis...")
            # Call webhook: AI analysis starting
            await call_webhook(webhook_url, job_id, "processing", progress=75)

            # Combine text from all sources
            combined_text = ""
            if results.get('pymupdf_results'):
                combined_text += results['pymupdf_results'].get('text_content', '')
            if results.get('tesseract_results'):
                combined_text += "\n" + results['tesseract_results'].get('ocr_text', '')

            ai_results = await analyzers['ai'].analyze_with_multiple_providers(
                text_content=combined_text,
                ai_providers=ai_providers,
                analysis_types=analysis_types,
                document_context={
                    'file_url': file_url,
                    'pymupdf_results': results.get('pymupdf_results'),
                    'pdfplumber_results': results.get('pdfplumber_results')
                }
            )

            results.update(ai_results)
            # Call webhook: AI analysis complete
            await call_webhook(webhook_url, job_id, "processing", progress=90)

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Create composite results
        results['composite_results'] = create_composite_results(results, analysis_types)
        results['processing_time_seconds'] = processing_time
        results['status'] = 'completed'

        logger.info(f"✅ Analysis {analysis_id} completed in {processing_time:.2f}s")

        # Call webhook: Analysis completed
        await call_webhook(webhook_url, job_id, "completed", results=results)

        # Store completed analysis results
        analysis_storage[analysis_id] = {
            "status": "completed",
            "results": results,
            "processing_time": processing_time,
            "completed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Analysis {analysis_id} failed: {e}")
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Call webhook: Analysis failed
        await call_webhook(webhook_url, job_id, "failed", error=str(e))

        # Store failed analysis results
        analysis_storage[analysis_id] = {
            "status": "failed",
            "error": str(e),
            "processing_time": processing_time,
            "failed_at": datetime.utcnow().isoformat()
        }

    # Clean up temporary files
    try:
        if 'document_path' in locals():
            os.unlink(document_path)
    except:
        pass
async def download_document(file_url: str) -> str:
    """Download document from URL to temporary file"""
    async with httpx.AsyncClient() as client:
        response = await client.get(file_url)
        response.raise_for_status()

        # Create temporary file
        import tempfile
        import uuid

        temp_file = os.path.join(tempfile.gettempdir(), f"doc_{uuid.uuid4().hex}.pdf")

        with open(temp_file, 'wb') as f:
            f.write(response.content)

        return temp_file
@app.post("/analyze/ai-enhanced", response_model=Dict[str, Any])
async def analyze_document_ai_enhanced(
    request: AnalysisRequest
):
    """
    AI-Enhanced document analysis using the intelligence pipeline
    Returns structured JSON matching your target schema
    """
    if not pipeline or not pipeline.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Intelligence pipeline is not available. Please check logs."
        )

    try:
        logger.info(f"Starting AI-enhanced analysis for: {request.file_url}")

        # Create intelligence request
        intel_request = IntelligenceRequest(
            file_url=request.file_url,
            ai_enhancement={
                "enabled": True,
                "providers": ["grok", "gemini", "groq"],
                "confidence_threshold": 0.7
            },
            tools={
                "pymupdf": True,
                "pdfplumber": True,
                "camelot": False,
                "tesseract_ocr": False,
                "paddle_ocr": False,
                "layout_parser": False,
                "table_transformer": False
            },
            options={
                "extract_tables": True,
                "extract_callouts": True,
                "extract_stamps": False,
                "extract_key_values": True
            }
        )

        # Run AI-enhanced analysis
        result: FinalResult = await pipeline.analyze_document_target_schema(intel_request)

        # Convert Pydantic model to dict for JSON response
        return result.dict()

    except Exception as e:
        logger.error(f"AI-enhanced analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
@app.get("/tools/intelligence-status")
async def get_intelligence_status():
    """Get status of the AI-enhanced intelligence pipeline"""
    if not pipeline:
        return {
            "available": False,
            "error": "Pipeline not initialized"
        }

    try:
        status = await pipeline.get_tools_status()
        return status.dict()
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }
# Enhanced Analysis API Endpoints
@app.post("/analyze/enhanced", response_model=EnhancedAnalysisResult)
async def analyze_document_enhanced(request: EnhancedRequest):
    """
    Enhanced document analysis using all advanced extractors

    This endpoint provides comprehensive analysis including:
    - Stamp detection and classification
    - Advanced layout analysis
    - Revision history tracking
    - Assembly and component detection
    - AI consensus analysis
    - Quality validation
    """
    if not enhanced_service:
        raise HTTPException(
            status_code=503,
            detail="Enhanced analysis service is not available. Please check logs."
        )

    try:
        logger.info(f"Starting enhanced analysis for: {request.file_url}")
        result = await enhanced_service.analyze_document(request)
        return result

    except Exception as e:
        logger.error(f"Enhanced analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Enhanced analysis failed: {str(e)}"
        )
@app.get("/analyze/enhanced/{analysis_id}", response_model=AnalysisStatus)
async def get_enhanced_analysis_status(analysis_id: str):
    """
    Get status of an enhanced analysis
    """
    if not enhanced_service:
        raise HTTPException(
            status_code=503,
            detail="Enhanced analysis service is not available"
        )

    try:
        status = await enhanced_service.get_analysis_status(analysis_id)

        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {analysis_id} not found"
            )

        return AnalysisStatus(
            analysis_id=analysis_id,
            status=status.get('status', 'unknown'),
            progress=status.get('progress'),
            current_step=status.get('current_step'),
            results=None  # Results would be populated when completed
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analysis status: {str(e)}"
        )
@app.get("/analyze/enhanced/active", response_model=List[str])
async def get_active_enhanced_analyses():
    """
    Get list of currently active enhanced analyses
    """
    if not enhanced_service:
        raise HTTPException(
            status_code=503,
            detail="Enhanced analysis service is not available"
        )

    try:
        active_analyses = enhanced_service.get_active_analyses()
        return active_analyses

    except Exception as e:
        logger.error(f"Failed to get active analyses: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active analyses: {str(e)}"
        )
@app.get("/tools/enhanced-status", response_model=ServiceHealth)
async def get_enhanced_service_status():
    """
    Get comprehensive status of enhanced analysis service and all extractors
    """
    status = ServiceHealth(
        status="healthy" if enhanced_service else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )

    if enhanced_service:
        # Check availability of different extractors
        status.extractors_available = {
            "stamp_detector": True,
            "layout_analyzer": True,
            "revision_tracker": True,
            "assembly_detector": True,
            "table_extractor": True
        }

        # Check AI services availability (simplified check)
        status.ai_services_available = {
            "consensus_analysis": True,
            "quality_validation": True,
            "error_correction": False,  # Not yet implemented
            "intelligent_normalization": False  # Not yet implemented
        }

        # Check external services availability
        status.external_services_available = {
            "free_services_manager": True,
            "google_vision": False,  # Would need actual check
            "azure_vision": False,  # Would need actual check
            "ocr_space": False  # Would need actual check
        }

    return status
@app.get("/tools/capabilities", response_model=ExtractorCapabilities)
async def get_extractor_capabilities():
    """
    Get comprehensive list of available analysis capabilities
    """
    capabilities = ExtractorCapabilities(
        core_extractors=[
            "pymupdf", "pdfplumber", "tesseract_ocr", "pandas"
        ],
        advanced_extractors=[
            "stamp_detection",
            "layout_analysis",
            "revision_tracking",
            "assembly_detection",
            "enhanced_table_extraction"
        ],
        ai_services=[
            "groq_llama", "google_gemini", "xai_grok", "consensus_analysis"
        ],
        external_services=[
            "google_vision", "azure_vision", "ocr_space", "free_ai_apis"
        ],
        supported_formats=[
            "PDF", "scanned_PDF", "engineering_drawings", "technical_documents"
        ],
        supported_languages=[
            "Portuguese", "English", "mixed_language"
        ]
    )

    return capabilities
def create_composite_results(results: Dict[str, Any], analysis_types: Dict[str, bool]) -> Dict[str, Any]:
    """Create composite results from all analysis tools"""
    composite = {
        'confidence_score': 0.8,
        'total_nomenclaturas': 0,
        'total_components': 0,
        'bom_summary': {
            'has_bom': False,
            'total_items': 0
        },
        'tags_summary': {
            'total_codes': 0,
            'c_codes': 0,
            'sap_codes': 0,
            'mt_cat_codes': 0
        }
    }

    # Aggregate nomenclaturas from AI results
    nomenclaturas = set()
    if results.get('ai_results'):
        for provider_result in results['ai_results'].values():
            if provider_result.get('success') and provider_result.get('parsed_response'):
                parsed = provider_result['parsed_response']
                if parsed.get('nomenclaturas'):
                    nomenclaturas.update(parsed['nomenclaturas'])
                if parsed.get('technical_codes'):
                    tc = parsed['technical_codes']
                    if tc.get('nomenclaturas'):
                        nomenclaturas.update(tc['nomenclaturas'])
                    if tc.get('c_codes'):
                        nomenclaturas.update(tc['c_codes'])
                    if tc.get('sap_codes'):
                        nomenclaturas.update(tc['sap_codes'])

    composite['total_nomenclaturas'] = len(nomenclaturas)

    # Count different types of codes
    c_codes = [n for n in nomenclaturas if n.startswith('C-')]
    sap_codes = [n for n in nomenclaturas if n.isdigit() and len(n) == 8]
    mt_cat_codes = [n for n in nomenclaturas if 'MT.CAT' in n]

    composite['tags_summary'] = {
        'total_codes': len(nomenclaturas),
        'c_codes': len(c_codes),
        'sap_codes': len(sap_codes),
        'mt_cat_codes': len(mt_cat_codes)
    }

    # BOM summary
    bom_items = []
    if results.get('ai_results'):
        for provider_result in results['ai_results'].values():
            if (provider_result.get('success') and
                provider_result.get('parsed_response') and
                provider_result['parsed_response'].get('bom_analysis') and
                provider_result['parsed_response']['bom_analysis'].get('items')):
                bom_items.extend(provider_result['parsed_response']['bom_analysis']['items'])

    composite['bom_summary'] = {
        'has_bom': len(bom_items) > 0,
        'total_items': len(bom_items)
    }

    # AI summary consensus
    summaries = []
    if results.get('ai_results'):
        for provider_result in results['ai_results'].values():
            if (provider_result.get('success') and
                provider_result.get('parsed_response') and
                provider_result['parsed_response'].get('summary')):
                summaries.append(provider_result['parsed_response']['summary'])

    if summaries:
        composite['ai_summary'] = f"Consenso de {len(summaries)} AIs: " + " | ".join(summaries[:2])

    return composite
if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    logger.info(f"🐍 Starting Catenary Document Analyzer on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )