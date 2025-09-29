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
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
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
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize FastAPI app
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
# Initialize analyzers
analyzers = {
    'pymupdf': PyMuPDFAnalyzer(),
    'pdfplumber': PDFPlumberAnalyzer(),
    'tesseract': TesseractAnalyzer(),
    'pandas': PandasAnalyzer(),
    'ai': AIAnalyzer()
}
# Initialize AI-enhanced intelligence pipeline
intelligence_config = IntelligenceConfig()
pipeline: Optional[PDFIntelligencePipeline] = None
# Initialize enhanced analysis service
enhanced_service: Optional[EnhancedAnalysisService] = None

# Global analysis results storage (in production, use Redis or database)
analysis_storage = {}

def convert_numpy_types(obj):
    """Recursively convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj
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
        await enhanced_service.initialize()
        logger.info("🎯 Enhanced analysis service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize enhanced analysis service: {e}")
        enhanced_service = None

# Pydantic models
class AnalysisRequest(BaseModel):
    file_url: str = Field(..., description="URL of the document to analyze")
    tools: Dict[str, bool] = Field(default={
        "pymupdf": True,
        "pdfplumber": True,
        "tesseract": True,
        "pandas": True
    }, description="Analysis tools to use")
    ai_providers: Dict[str, bool] = Field(default={
        "gemini": True,
        "groq": True,
        "xai": False
    }, description="AI providers to use")
    analysis_types: Dict[str, bool] = Field(default={
        "bom_extraction": True,
        "component_detection": True,
        "nomenclaturas": True
    }, description="Types of analysis to perform")
    options: Dict[str, Any] = Field(default={}, description="Additional options")

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str = "pending"
    tools_used: List[str] = []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "analyzers": {}
    }

    # Check analyzer status
    for name, analyzer in analyzers.items():
        try:
            if hasattr(analyzer, 'health_check'):
                status["analyzers"][name] = {
                    "status": "healthy",
                    "available": True
                }
            else:
                status["analyzers"][name] = {
                    "status": "healthy",
                    "available": True
                }
        except Exception as e:
            status["analyzers"][name] = {
                "status": f"error: {e}",
                "available": False
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
            request.options
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

    # Convert any numpy types to native Python types for JSON serialization
    safe_result = {
        "analysis_id": analysis_id,
        "status": stored_result.get("status", "unknown"),
        "results": convert_numpy_types(stored_result.get("results")),
        "error": stored_result.get("error"),
        "processing_time": convert_numpy_types(stored_result.get("processing_time"))
    }

    return safe_result
async def run_analysis(
    analysis_id: str,
    file_url: str,
    tools: Dict[str, bool],
    ai_providers: Dict[str, bool],
    analysis_types: Dict[str, bool],
    options: Dict[str, Any]
):
    """
    Run the complete document analysis pipeline
    """
    start_time = datetime.utcnow()
    results = {}

    try:
        logger.info(f"🔍 Running analysis {analysis_id}")

        # CRITICAL FIX: Update status to processing immediately when analysis starts
        analysis_storage[analysis_id] = {
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
            "progress": 0
        }

        # Download document file
        document_path = await download_document(file_url)

        # Update progress
        analysis_storage[analysis_id].update({"progress": 10})

        # Run PyMuPDF analysis
        if tools.get('pymupdf', False):
            logger.info("📄 Running PyMuPDF analysis...")
            results['pymupdf_results'] = await analyzers['pymupdf'].analyze(document_path)
            analysis_storage[analysis_id].update({"progress": 25})

        # Run PDFPlumber analysis
        if tools.get('pdfplumber', False):
            logger.info("📊 Running PDFPlumber analysis...")
            results['pdfplumber_results'] = await analyzers['pdfplumber'].analyze(document_path)
            analysis_storage[analysis_id].update({"progress": 50})

        # Run Tesseract OCR
        if tools.get('tesseract', False):
            logger.info("👁️ Running Tesseract OCR...")
            results['tesseract_results'] = await analyzers['tesseract'].analyze(document_path)
            analysis_storage[analysis_id].update({"progress": 65})

        # Run Pandas analysis
        if tools.get('pandas', False):
            logger.info("🐼 Running Pandas analysis...")
            results['pandas_results'] = await analyzers['pandas'].analyze(document_path)
            analysis_storage[analysis_id].update({"progress": 80})

        # Run AI analysis if any providers are enabled
        enabled_providers = [k for k, v in ai_providers.items() if v]
        if enabled_providers:
            logger.info(f"AI providers received: {ai_providers}")
            logger.info("🤖 Running AI analysis...")

            ai_results = await analyzers['ai'].analyze(
                pdf_path=document_path,
                enabled_providers=enabled_providers,
                document_context={
                    'file_url': file_url,
                    'pymupdf_results': results.get('pymupdf_results'),
                    'pdfplumber_results': results.get('pdfplumber_results')
                }
            )

            results.update(ai_results)
            analysis_storage[analysis_id].update({"progress": 95})

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Create composite results
        results['composite_results'] = create_composite_results(results, analysis_types)
        results['processing_time_seconds'] = processing_time
        results['status'] = 'completed'

        logger.info(f"✅ Analysis {analysis_id} completed in {processing_time:.2f}s")

        # Store completed analysis results (convert numpy types for JSON safety)
        analysis_storage[analysis_id] = {
            "status": "completed",
            "results": convert_numpy_types(results),
            "processing_time": processing_time,
            "completed_at": datetime.utcnow().isoformat(),
            "progress": 100
        }

    except Exception as e:
        logger.error(f"❌ Analysis {analysis_id} failed: {e}")
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Store failed analysis results
        analysis_storage[analysis_id] = {
            "status": "failed",
            "error": str(e),
            "processing_time": processing_time,
            "failed_at": datetime.utcnow().isoformat(),
            "progress": 0
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
        # Convert request to intelligence format
        intel_request = IntelligenceRequest(
            document_url=request.file_url,
            target_schema=FinalResult,  # Use the target schema
            options=request.options
        )

        # Run AI-enhanced analysis
        result = await pipeline.process_document(intel_request)

        return {
            "analysis_id": f"ai_enhanced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "status": "completed",
            "intelligence_result": result.model_dump() if hasattr(result, 'model_dump') else result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"AI-enhanced analysis failed: {e}")
        return {
            "analysis_id": f"ai_enhanced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
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
            detail="Enhanced analysis service is not available"
        )

    try:
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
            status=status.get("status", "unknown"),
            progress=status.get("progress", 0),
            current_step=status.get("current_step", ""),
            results=status.get("results"),
            error=status.get("error"),
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at")
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
@app.get("/analyze/enhanced/capabilities", response_model=ExtractorCapabilities)
async def get_enhanced_capabilities():
    """
    Get capabilities of all enhanced extractors
    """
    if not enhanced_service:
        raise HTTPException(
            status_code=503,
            detail="Enhanced analysis service is not available"
        )

    try:
        capabilities = enhanced_service.get_capabilities()
        return capabilities

    except Exception as e:
        logger.error(f"Failed to get capabilities: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get capabilities: {str(e)}"
        )
def create_composite_results(results: Dict[str, Any], analysis_types: Dict[str, bool]) -> Dict[str, Any]:
    """Create composite analysis results from individual analyzer outputs"""
    composite = {
        "summary": {
            "total_analyzers_run": len([k for k in results.keys() if k.endswith('_results')]),
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    }

    # BOM extraction composite
    if analysis_types.get('bom_extraction', False):
        bom_data = []

        # Combine BOM data from different sources
        if 'pandas_results' in results:
            pandas_bom = results['pandas_results'].get('bom_data', [])
            bom_data.extend(pandas_bom)

        if 'ai_groq_results' in results:
            ai_bom = results['ai_groq_results'].get('bom_analysis', {}).get('components', [])
            bom_data.extend(ai_bom)

        composite['bom_extraction'] = {
            "components_found": len(bom_data),
            "components": bom_data
        }

    # Component detection composite
    if analysis_types.get('component_detection', False):
        all_components = []

        # Collect components from all sources
        if 'pdfplumber_results' in results:
            tables = results['pdfplumber_results'].get('tables', [])
            for table in tables:
                if isinstance(table, dict) and 'data' in table:
                    all_components.extend(table['data'])

        composite['component_detection'] = {
            "total_components": len(all_components),
            "components": all_components
        }

    # Nomenclaturas extraction
    if analysis_types.get('nomenclaturas', False):
        nomenclaturas = []

        # Extract nomenclaturas from AI results
        if 'ai_gemini_results' in results:
            gemini_nomenclaturas = results['ai_gemini_results'].get('nomenclaturas_found', [])
            nomenclaturas.extend(gemini_nomenclaturas)

        composite['nomenclaturas'] = {
            "total_found": len(nomenclaturas),
            "nomenclaturas": nomenclaturas
        }

    return composite

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)