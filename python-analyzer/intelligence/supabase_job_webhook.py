"""
Supabase Job Webhook Endpoint
Receives notifications from Supabase when new analysis jobs are created
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger
from supabase import create_client, Client
import os
from datetime import datetime

from .models.schemas import AnalysisRequest, ExtractionOptions
from .workers.analysis_worker import AnalysisWorker

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Supabase client for direct database updates
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://api.rocktech.pt")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NTc1NzMwMTksImV4cCI6MjA3MjkzMzAxOX0.7qO3Lz_UwZW2av_pm7cxDOGqLJIur9sjKPFrFm7U2IU")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

class JobWebhookPayload(BaseModel):
    """Webhook payload from Supabase when a new job is created"""
    job_id: str
    document_id: str
    tenant_id: str
    user_id: str
    config: Dict[str, Any]
    document_url: Optional[str] = None
    document_path: Optional[str] = None

async def process_analysis_job(job_id: str, payload: JobWebhookPayload, worker: AnalysisWorker):
    """Process an analysis job and update Supabase directly"""
    try:
        logger.info(f"Starting analysis job {job_id}")
        
        # Update job status to processing
        supabase.table('analysis_jobs').update({
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 5,
            'current_step': 'Initializing analysis pipeline'
        }).eq('id', job_id).execute()
        
        # Get document details from Supabase
        document_response = supabase.table('documents').select('*').eq('id', payload.document_id).single().execute()
        document = document_response.data
        
        if not document:
            raise ValueError(f"Document {payload.document_id} not found")
        
        # Construct document URL
        document_url = payload.document_url
        if not document_url and document.get('file_path'):
            # Construct URL from Supabase storage
            document_url = f"{SUPABASE_URL}/storage/v1/object/public/documents/{document['file_path']}"
        
        if not document_url:
            raise ValueError("No document URL available")
        
        # Update progress
        supabase.table('analysis_jobs').update({
            'progress': 10,
            'current_step': 'Loading document'
        }).eq('id', job_id).execute()
        
        # Prepare analysis request based on config
        config = payload.config
        
        # Map config to extraction options
        extraction_options = ExtractionOptions(
            extract_tables=config.get('analysisTypes', {}).get('bom_extraction', True),
            extract_images=False,
            extract_stamps=config.get('analysisTypes', {}).get('component_detection', True),
            extract_callouts=config.get('analysisTypes', {}).get('tags_analysis', True),
            extract_key_value_pairs=config.get('analysisTypes', {}).get('metadata', True),
            ocr_enabled=config.get('pythonTools', {}).get('tesseract_ocr', False),
            parallel_processing=config.get('aiProviders', {}).get('parallelExecution', True),
            confidence_threshold=0.7
        )
        
        # Create analysis request
        analysis_request = AnalysisRequest(
            file_url=document_url,
            options=extraction_options,
            webhook_url=None  # We'll update Supabase directly
        )
        
        # Queue the analysis with the worker
        task_id = await worker.queue_analysis(job_id, analysis_request)
        
        logger.info(f"Analysis job {job_id} pending with task {task_id}")
        
        # The worker will handle the rest and update Supabase directly
        # via the SupabaseWebhookClient
        
    except Exception as e:
        logger.error(f"Failed to process job {job_id}: {str(e)}")
        
        # Update job as failed
        supabase.table('analysis_jobs').update({
            'status': 'failed',
            'error_message': str(e),
            'completed_at': datetime.now().isoformat(),
            'current_step': 'Analysis failed'
        }).eq('id', job_id).execute()
        
        raise

@router.post("/job-created")
async def handle_job_created(
    payload: JobWebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Webhook endpoint called by Supabase when a new analysis job is created
    """
    try:
        logger.info(f"Received webhook for job {payload.job_id}")
        
        # Get the worker instance
        from .main import worker
        
        if not worker:
            raise HTTPException(status_code=503, detail="Analysis worker not available")
        
        # Process the job in the background
        background_tasks.add_task(
            process_analysis_job,
            payload.job_id,
            payload,
            worker
        )
        
        return {
            "success": True,
            "message": f"Job {payload.job_id} pending for processing"
        }
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/job-cancelled")
async def handle_job_cancelled(job_id: str):
    """
    Webhook endpoint called when an analysis job is cancelled
    """
    try:
        from .main import worker
        
        if worker:
            success = await worker.cancel_analysis(job_id)
            
            if success:
                # Update job status in Supabase
                supabase.table('analysis_jobs').update({
                    'status': 'cancelled',
                    'completed_at': datetime.now().isoformat(),
                    'current_step': 'Analysis cancelled by user'
                }).eq('id', job_id).execute()
                
                return {"success": True, "message": f"Job {job_id} cancelled"}
        
        return {"success": False, "message": "Job not found or already completed"}
        
    except Exception as e:
        logger.error(f"Cancel webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))