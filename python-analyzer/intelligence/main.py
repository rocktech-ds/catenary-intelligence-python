"""
PDF Intelligence Pipeline - FastAPI Main Application
Bullet-proof analysis for dense engineering drawings
"""
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uuid
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from loguru import logger

from .core.pipeline_manager import PDFIntelligencePipeline
from .core.config import IntelligenceConfig
from .models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    PipelineStatus,
    ToolsStatus,
    ExtractionResult
)
from .workers.analysis_worker import AnalysisWorker
# from .utils.monitoring import setup_monitoring, create_metrics_middleware

# Global instances
pipeline: Optional[PDFIntelligencePipeline] = None
config: Optional[IntelligenceConfig] = None
worker: Optional[AnalysisWorker] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global pipeline, config, worker
    
    try:
        # Initialize configuration
        config = IntelligenceConfig()
        logger.info("Initializing PDF Intelligence Pipeline...")
        
        # Initialize core pipeline
        pipeline = PDFIntelligencePipeline(config)
        await pipeline.initialize()
        
        # Initialize background worker
        worker = AnalysisWorker(pipeline, config)
        await worker.start()
        
        # Setup monitoring (disabled for now due to import issues)
        # setup_monitoring()
        
        logger.success("PDF Intelligence Pipeline ready!")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        # Cleanup
        if worker:
            await worker.stop()
        if pipeline:
            await pipeline.cleanup()

# Create FastAPI app
app = FastAPI(
    title="PDF Intelligence Pipeline",
    description="Bullet-proof analysis for dense engineering drawings",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware (disabled for now due to import issues)
# from fastapi.middleware.base import BaseHTTPMiddleware
# app.add_middleware(BaseHTTPMiddleware, dispatch=create_metrics_middleware())

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    pipeline_ready: bool
    worker_status: str
    models_loaded: Dict[str, bool]

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check"""
    global pipeline, worker
    
    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        pipeline_ready=pipeline is not None and pipeline.is_ready(),
        worker_status=worker.status if worker else "not_initialized",
        models_loaded=pipeline.get_models_status() if pipeline else {}
    )

@app.get("/tools/status", response_model=ToolsStatus)
async def get_tools_status():
    """Get status of all PDF intelligence tools"""
    global pipeline
    
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    return await pipeline.get_tools_status()

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger comprehensive PDF intelligence analysis
    Returns immediately with analysis ID for tracking
    """
    global pipeline, worker
    
    if not pipeline or not worker:
        raise HTTPException(status_code=503, detail="Pipeline not ready")
    
    try:
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"Starting analysis {analysis_id} for file: {request.file_url}")
        
        # Queue analysis task
        task_id = await worker.queue_analysis(analysis_id, request)
        
        # Return immediate response
        return AnalysisResponse(
            analysis_id=analysis_id,
            task_id=task_id,
            status="pending",
            message="Analysis pending successfully",
            estimated_duration=pipeline.estimate_processing_time(request)
        )
        
    except Exception as e:
        logger.error(f"Failed to queue analysis: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{analysis_id}/status", response_model=PipelineStatus)
async def get_analysis_status(analysis_id: str):
    """Get analysis status and progress"""
    global worker
    
    if not worker:
        raise HTTPException(status_code=503, detail="Worker not ready")
    
    try:
        status = await worker.get_analysis_status(analysis_id)
        if not status:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{analysis_id}/results", response_model=ExtractionResult)
async def get_analysis_results(analysis_id: str):
    """Get complete analysis results"""
    global worker
    
    if not worker:
        raise HTTPException(status_code=503, detail="Worker not ready")
    
    try:
        results = await worker.get_analysis_results(analysis_id)
        if not results:
            raise HTTPException(status_code=404, detail="Analysis results not found")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str):
    """Cancel running analysis"""
    global worker
    
    if not worker:
        raise HTTPException(status_code=503, detail="Worker not ready")
    
    try:
        success = await worker.cancel_analysis(analysis_id)
        if not success:
            raise HTTPException(status_code=404, detail="Analysis not found or already completed")
        
        return {"message": "Analysis cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/pipeline")
async def debug_pipeline():
    """Debug endpoint for pipeline inspection"""
    global pipeline
    
    if not pipeline:
        return {"error": "Pipeline not initialized"}
    
    return {
        "ready": pipeline.is_ready(),
        "models": pipeline.get_models_status(),
        "extractors": list(pipeline.extractors.keys()),
        "config": {
            "max_workers": pipeline.config.max_workers,
            "timeout": pipeline.config.analysis_timeout,
            "cache_enabled": pipeline.config.enable_cache
        }
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP exception: {exc.detail}")
    return {"error": exc.detail, "status_code": exc.status_code}

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return {"error": "Internal server error", "status_code": 500}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        workers=2,
        log_level="info",
        access_log=True
    )