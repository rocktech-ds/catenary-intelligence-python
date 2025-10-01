"""
Document Analysis Python Service with Realtime Supabase Communication
No polling - direct Supabase database updates via realtime webhooks
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
from supabase import create_client, Client

# Import analyzers
from analyzers.pymupdf_analyzer import PyMuPDFAnalyzer
from analyzers.pdfplumber_analyzer import PDFPlumberAnalyzer
from analyzers.tesseract_analyzer import TesseractAnalyzer
from analyzers.pandas_analyzer import PandasAnalyzer
from analyzers.ai_analyzer import AIAnalyzer

# Supabase client for direct database updates
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://catenary.api.rocktech.pt")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjYXRlbmFyeSIsInJvbGUiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE3NTgzMDg3MDEsImV4cCI6MjM4OTAyODcwMX0.Eu_O_phLffNBFdoeJfj5AjZNj7Hw3Pbgok20bBEvMb8")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catenary Document Analyzer - Realtime",
    description="Python-based document analysis service with Supabase realtime integration",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class AnalysisRequest(BaseModel):
    job_id: str = Field(..., description="Analysis job ID from Supabase")
    file_url: str = Field(..., description="URL to the document file")
    tools: Dict[str, bool] = Field(default_factory=dict)
    ai_providers: Dict[str, bool] = Field(default_factory=dict)
    analysis_types: Dict[str, bool] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    job_id: str

# Global analyzer instances
analyzers = {
    'pymupdf': PyMuPDFAnalyzer(),
    'pdfplumber': PDFPlumberAnalyzer(),
    'tesseract': TesseractAnalyzer(),
    'pandas': PandasAnalyzer(),
    'ai': AIAnalyzer()
}

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

async def update_job_status(job_id: str, status: str, progress: int, current_step: str, results: Optional[Dict] = None, error_message: Optional[str] = None):
    """Update analysis job status in Supabase - triggers realtime updates"""
    try:
        update_data = {
            'status': status,
            'progress': progress,
            'current_step': current_step,
            'updated_at': datetime.now().isoformat()
        }

        if status == 'processing' and progress == 0:
            update_data['started_at'] = datetime.now().isoformat()
        elif status in ['completed', 'failed']:
            update_data['completed_at'] = datetime.now().isoformat()

        if results:
            update_data['results'] = serialize_numpy_values(results)

        if error_message:
            update_data['error_message'] = error_message

        response = supabase.table('analysis_jobs').update(update_data).eq('id', job_id).execute()
        logger.info(f"✅ Updated job {job_id} status to {status} ({progress}%): {current_step}")

    except Exception as e:
        logger.error(f"❌ Failed to update job {job_id} status: {e}")

async def create_analysis_step(job_id: str, step_name: str, step_type: str, status: str = 'pending'):
    """Create analysis step in Supabase"""
    try:
        step_data = {
            'job_id': job_id,
            'step_name': step_name,
            'step_type': step_type,
            'status': status,
            'created_at': datetime.now().isoformat()
        }

        response = supabase.table('analysis_steps').insert(step_data).execute()
        logger.info(f"📋 Created analysis step: {step_name}")

    except Exception as e:
        logger.error(f"❌ Failed to create analysis step {step_name}: {e}")

async def update_analysis_step(job_id: str, step_name: str, status: str, results: Optional[Dict] = None, error_message: Optional[str] = None):
    """Update analysis step status in Supabase"""
    try:
        update_data = {
            'status': status,
            'updated_at': datetime.now().isoformat()
        }

        if status == 'processing':
            update_data['started_at'] = datetime.now().isoformat()
        elif status in ['completed', 'failed']:
            update_data['completed_at'] = datetime.now().isoformat()

        if results:
            update_data['results'] = serialize_numpy_values(results)

        if error_message:
            update_data['error_message'] = error_message

        response = supabase.table('analysis_steps').update(update_data).eq('job_id', job_id).eq('step_name', step_name).execute()
        logger.info(f"✅ Updated step {step_name} to {status}")

    except Exception as e:
        logger.error(f"❌ Failed to update analysis step {step_name}: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "supabase_url": SUPABASE_URL,
        "realtime_enabled": True
    }

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Start document analysis with realtime Supabase updates
    No polling needed - updates sent directly to database
    """
    try:
        logger.info(f"🚀 Starting realtime analysis for job {request.job_id}")

        # Update job status to processing immediately
        await update_job_status(request.job_id, 'processing', 0, 'Starting analysis...')

        # Create analysis steps based on enabled tools
        enabled_steps = []

        # Python tool steps
        for tool, enabled in request.tools.items():
            if enabled:
                step_name = f"analysis_{tool}"
                await create_analysis_step(request.job_id, step_name, 'analysis_tool')
                enabled_steps.append((step_name, 'analysis_tool'))

        # AI provider steps
        for provider, enabled in request.ai_providers.items():
            if provider != 'parallelExecution' and enabled:
                step_name = f"ai_{provider}"
                await create_analysis_step(request.job_id, step_name, 'ai_analysis')
                enabled_steps.append((step_name, 'ai_analysis'))

        # Start analysis in background with realtime updates
        background_tasks.add_task(
            run_realtime_analysis,
            request.job_id,
            request.file_url,
            request.tools,
            request.ai_providers,
            request.analysis_types,
            request.options,
            enabled_steps
        )

        return AnalysisResponse(
            success=True,
            message=f"Analysis job {request.job_id} started with realtime updates",
            job_id=request.job_id
        )

    except Exception as e:
        logger.error(f"❌ Error starting analysis: {e}")
        await update_job_status(request.job_id, 'failed', 0, 'Failed to start analysis', error_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def run_realtime_analysis(
    job_id: str,
    file_url: str,
    tools: Dict[str, bool],
    ai_providers: Dict[str, bool],
    analysis_types: Dict[str, bool],
    options: Dict[str, Any],
    enabled_steps: List[tuple]
):
    """
    Run complete document analysis with realtime Supabase updates
    Each step update triggers realtime notifications to frontend
    """
    start_time = datetime.utcnow()
    results = {}

    try:
        # Download document
        await update_job_status(job_id, 'processing', 10, 'Downloading document...')
        document_path = await download_document(file_url)

        progress = 20
        step_increment = 60 / max(len(enabled_steps), 1)  # Distribute 60% across steps

        # Run enabled analysis tools
        for tool, enabled in tools.items():
            if enabled:
                step_name = f"analysis_{tool}"
                await update_analysis_step(job_id, step_name, 'processing')
                await update_job_status(job_id, 'processing', int(progress), f'Running {tool} analysis...')

                try:
                    if tool == 'pymupdf':
                        result = await analyzers['pymupdf'].analyze(document_path)
                        results[f'{tool}_results'] = result
                    elif tool == 'pdfplumber':
                        result = await analyzers['pdfplumber'].analyze(document_path)
                        results[f'{tool}_results'] = result
                    elif tool == 'tesseract':
                        result = await analyzers['tesseract'].analyze(document_path)
                        results[f'{tool}_results'] = result
                    elif tool == 'pandas' and results.get('pdfplumber_results'):
                        result = await analyzers['pandas'].analyze_tables(
                            results['pdfplumber_results'].get('tables', [])
                        )
                        results[f'{tool}_results'] = result

                    await update_analysis_step(job_id, step_name, 'completed', results=result)
                    logger.info(f"✅ Completed {tool} analysis")

                except Exception as e:
                    await update_analysis_step(job_id, step_name, 'failed', error_message=str(e))
                    logger.error(f"❌ Failed {tool} analysis: {e}")

                progress += step_increment

        # Run AI analysis if enabled
        enabled_ai_providers = [k for k, v in ai_providers.items() if k != 'parallelExecution' and v]
        if enabled_ai_providers:
            await update_job_status(job_id, 'processing', int(progress), 'Running AI analysis...')

            # Combine text from all sources
            combined_text = ""
            if results.get('pymupdf_results'):
                combined_text += results['pymupdf_results'].get('text_content', '')
            if results.get('tesseract_results'):
                combined_text += "\n" + results['tesseract_results'].get('ocr_text', '')

            for provider in enabled_ai_providers:
                step_name = f"ai_{provider}"
                await update_analysis_step(job_id, step_name, 'processing')

                try:
                    # Run AI analysis for this provider
                    ai_result = await analyzers['ai'].analyze_with_provider(
                        provider=provider,
                        text_content=combined_text,
                        analysis_types=analysis_types,
                        document_context={
                            'file_url': file_url,
                            'pymupdf_results': results.get('pymupdf_results'),
                            'pdfplumber_results': results.get('pdfplumber_results')
                        }
                    )

                    results[f'ai_{provider}_results'] = ai_result
                    await update_analysis_step(job_id, step_name, 'completed', results=ai_result)
                    logger.info(f"✅ Completed {provider} AI analysis")

                except Exception as e:
                    await update_analysis_step(job_id, step_name, 'failed', error_message=str(e))
                    logger.error(f"❌ Failed {provider} AI analysis: {e}")

                progress += step_increment / len(enabled_ai_providers)

        # Calculate final results
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Create composite results
        composite_results = create_composite_results(results, analysis_types)
        final_results = {
            'composite_results': composite_results,
            'processing_time_seconds': processing_time,
            'tools_used': list(tools.keys()),
            'ai_providers_used': enabled_ai_providers,
            **results
        }

        # Update job as completed with results
        await update_job_status(job_id, 'completed', 100, 'Analysis completed successfully', results=final_results)

        logger.info(f"🎉 Analysis {job_id} completed in {processing_time:.2f}s")

    except Exception as e:
        logger.error(f"❌ Analysis {job_id} failed: {e}")
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Update job as failed
        await update_job_status(job_id, 'failed', 0, 'Analysis failed', error_message=str(e))

        # Mark all pending steps as failed
        for step_name, step_type in enabled_steps:
            await update_analysis_step(job_id, step_name, 'failed', error_message=str(e))

    # Cleanup
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

def create_composite_results(results: Dict[str, Any], analysis_types: Dict[str, bool]) -> Dict[str, Any]:
    """Create composite results from all analysis tools"""
    composite = {
        'confidence_score': 0.8,
        'total_nomenclaturas': 0,
        'total_components': 0,
        'processing_summary': {
            'tools_executed': len([k for k in results.keys() if k.endswith('_results')]),
            'successful_extractions': len([k for k, v in results.items() if k.endswith('_results') and v]),
            'timestamp': datetime.utcnow().isoformat()
        }
    }

    # Aggregate data from AI results
    all_nomenclaturas = set()
    all_components = []

    # Process AI results
    for key, result in results.items():
        if key.startswith('ai_') and key.endswith('_results'):
            if isinstance(result, dict) and result.get('success'):
                parsed = result.get('parsed_response', {})

                # Extract nomenclaturas
                if parsed.get('nomenclaturas'):
                    all_nomenclaturas.update(parsed['nomenclaturas'])

                # Extract components
                if parsed.get('components'):
                    all_components.extend(parsed['components'])

    composite['total_nomenclaturas'] = len(all_nomenclaturas)
    composite['total_components'] = len(all_components)
    composite['nomenclaturas'] = list(all_nomenclaturas)
    composite['components'] = all_components

    return composite

if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8003))

    logger.info(f"🐍 Starting Catenary Document Analyzer (Realtime) on {host}:{port}")

    uvicorn.run(
        "main_realtime:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )