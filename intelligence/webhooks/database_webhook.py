"""
Database Webhook Endpoint
Receives webhooks from Supabase database changes
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from loguru import logger

from ..core.pipeline_manager import PDFIntelligencePipeline
from ..workers.analysis_worker import AnalysisWorker
from ..models.schemas import AnalysisRequest, ToolsConfig, ExtractionOptions

router = APIRouter(prefix="/webhook", tags=["webhooks"])

class DatabaseWebhookPayload(BaseModel):
    event: str
    timestamp: float
    table: str
    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    status: Optional[str] = None
    requested_by: Optional[str] = None
    data: Dict[str, Any]

# Global references (will be injected)
pipeline: Optional[PDFIntelligencePipeline] = None
worker: Optional[AnalysisWorker] = None

def setup_webhook_handlers(pipeline_instance: PDFIntelligencePipeline, worker_instance: AnalysisWorker):
    """Setup global references for webhook handlers"""
    global pipeline, worker
    pipeline = pipeline_instance
    worker = worker_instance

@router.post("/analysis-status")
async def handle_database_webhook(
    payload: DatabaseWebhookPayload,
    authorization: Optional[str] = Header(None)
):
    """
    Handle database webhook notifications from Supabase
    This endpoint receives notifications when database records change
    """

    # Simple webhook authentication
    if authorization != "Bearer webhook-secret":
        logger.warning(f"Unauthorized webhook attempt: {authorization}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(f"Received database webhook: {payload.event} for analysis {payload.analysis_id}")

    try:
        # Handle different webhook events
        if payload.event == "analysis_created":
            await handle_analysis_created(payload)
        elif payload.event == "document_uploaded_auto_analyze":
            await handle_auto_analysis_trigger(payload)
        elif payload.event in ["analysis_started", "analysis_completed", "analysis_failed"]:
            logger.info(f"Analysis status update: {payload.event} - {payload.analysis_id}")
            # These are status updates we've already processed, just log them
        else:
            logger.warning(f"Unknown webhook event: {payload.event}")

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "message": f"Processed {payload.event}"}

async def handle_analysis_created(payload: DatabaseWebhookPayload):
    """Handle new analysis creation from database"""
    global pipeline, worker

    if not worker or not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not ready")

    analysis_data = payload.data
    analysis_id = payload.analysis_id
    document_id = payload.document_id

    # Extract configuration from analysis data
    config = analysis_data.get('analysis_config', {})

    # Build analysis request
    request = AnalysisRequest(
        file_url=f"supabase://documents/{document_id}",  # Special URL format for Supabase docs
        tools=ToolsConfig(**config.get('python_tools', {})),
        options=ExtractionOptions(**config.get('extraction_options', {})),
        priority=config.get('priority', 1)
    )

    # Queue the analysis
    task_id = await worker.queue_analysis(analysis_id, request)

    logger.info(f"PENDING analysis {analysis_id} from database webhook (task: {task_id})")

async def handle_auto_analysis_trigger(payload: DatabaseWebhookPayload):
    """Handle automatic analysis trigger for uploaded documents"""
    global pipeline, worker

    if not worker or not pipeline:
        logger.warning("Pipeline not ready for auto-analysis")
        return

    document_data = payload.data
    document_id = payload.document_id

    # Create analysis ID
    analysis_id = str(uuid.uuid4())

    # Build default analysis request for engineering documents
    request = AnalysisRequest(
        file_url=f"supabase://documents/{document_id}",
        tools=ToolsConfig(
            pymupdf=True,
            pdfplumber=True,
            tesseract_ocr=False,
            paddle_ocr=True,
            layout_parser=True,
            table_transformer=True,
            opencv_vision=True
        ),
        options=ExtractionOptions(
            extract_images=True,
            extract_tables=True,
            extract_callouts=True,
            extract_stamps=True,
            extract_metadata=True,
            ocr_scanned_pages=True,
            link_references=True
        ),
        priority=2  # Lower priority for auto-analysis
    )

    # Queue the auto-analysis
    task_id = await worker.queue_analysis(analysis_id, request)

    logger.info(f"Auto-pending analysis {analysis_id} for document {document_id} (task: {task_id})")

    # TODO: Insert analysis record in database via API call
    # This would create the analysis record that the user can then track