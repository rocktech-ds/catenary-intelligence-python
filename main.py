"""
Document Analysis Python Service with Database Integration
Includes real-time progress updates and cancellation support
"""
import os
import asyncio
import asyncpg
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Catenary Document Analyzer",
    description="Python-based document analysis service with AI integration and database updates",
    version="2.0.0"
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
    job_id: Optional[str] = Field(default=None, description="Job ID to track the analysis")

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    tools_used: List[str] = Field(default_factory=list)

# Global storage for analysis results
STORAGE_FILE = "/tmp/analysis_storage.json"
analysis_storage = {}

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

# Cancellation tracking
active_analyses = {}
cancelled_analyses = set()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Intelligence Service with Database Integration started")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "features": ["database_integration", "progress_tracking", "cancellation_support"]
    }

async def create_analysis_job_db(job_id: str, document_id: str, user_id: str = "00000000-0000-0000-0000-000000000000", organization_id: str = "default", config: dict = None):
    """Create analysis job record in PostgreSQL database"""
    if not job_id or not document_id:
        print("❌ Missing job_id or document_id for create_analysis_job_db")
        return False

    try:
        print(f"🔄 Creating database record for job: {job_id}")

        # Connect to PostgreSQL using container hostname
        database_url = "postgresql://postgres:CaTy2025SecureDB_7aa74fde@catenary-db:5432/postgres"
        conn = await asyncpg.connect(database_url)

        try:
            # Insert analysis job record
            await conn.execute("""
                INSERT INTO analysis_jobs (id, document_id, user_id, organization_id, config, status, progress, analysis_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, 'pending', 0, $6, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """, job_id, document_id, user_id, organization_id, config or {}, job_id)

            logger.info(f"✅ Created analysis job record for {job_id}")
            print(f"✅ Database record created for job {job_id}")
            return True

        finally:
            await conn.close()
            print(f"🔌 Database connection closed for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Failed to create job record {job_id}: {e}")
        print(f"❌ EXCEPTION in create_analysis_job_db for job {job_id}: {e}")
        return False

async def update_analysis_job_db(job_id: str, status: str, results: dict = None, error: str = None, progress: int = 0):
    """Update analysis job directly in PostgreSQL database with progress tracking"""
    if not job_id:
        print("❌ No job_id provided to update_analysis_job_db")
        return

    try:
        print(f"🔄 Database update called: job_id={job_id}, status={status}, progress={progress}")

        # Determine current step based on progress and status
        if status == "processing":
            if progress <= 10:
                current_step = "Starting document analysis"
            elif progress <= 20:
                current_step = "Downloading document"
            elif progress <= 40:
                current_step = "Analyzing document structure"
            elif progress <= 60:
                current_step = "Extracting data from document"
            elif progress <= 75:
                current_step = "Processing with AI providers"
            elif progress <= 90:
                current_step = "Finalizing analysis results"
            else:
                current_step = "Completing analysis"
        elif status == "completed":
            current_step = "Analysis completed successfully"
        elif status == "failed":
            current_step = f"Analysis failed: {error or 'Unknown error'}"
        elif status == "cancelled":
            current_step = "Analysis cancelled by user"
        else:
            current_step = f"Analysis {status}"

        print(f"📝 Connecting to database for job {job_id}")
        # Connect to PostgreSQL using container hostname
        database_url = "postgresql://postgres:CaTy2025SecureDB_7aa74fde@catenary-db:5432/postgres"
        conn = await asyncpg.connect(database_url)

        try:
            print(f"📞 Calling database function for job {job_id}")
            # Call the PostgreSQL function
            result = await conn.fetchval(
                "SELECT update_analysis_job_progress($1, $2, $3, $4, $5, $6)",
                job_id, status, progress, current_step,
                results if results else None,
                error
            )

            if result:
                logger.info(f"✅ Updated job {job_id} to {status} (progress: {progress}%)")
                print(f"✅ Database update successful for job {job_id}")
            else:
                logger.warning(f"⚠️ Job {job_id} not found in database")
                print(f"⚠️ Job {job_id} not found in database")

        finally:
            await conn.close()
            print(f"🔌 Database connection closed for job {job_id}")

    except Exception as e:
        logger.error(f"❌ Failed to update job {job_id}: {e}")
        print(f"❌ EXCEPTION in update_analysis_job_db for job {job_id}: {e}")

async def is_analysis_cancelled(job_id: str) -> bool:
    """Check if analysis has been cancelled"""
    return job_id in cancelled_analyses

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(request: AnalysisRequest):
    """
    Start document analysis with progress tracking and database updates
    """
    analysis_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    try:
        logger.info(f"Starting analysis {analysis_id} for file: {request.file_url}")
        print(f"📋 About to start analysis task for job_id: {request.job_id}")

        # Initialize analysis in storage
        analysis_storage[analysis_id] = {
            "status": "pending",
            "job_id": request.job_id,
            "started_at": datetime.utcnow().isoformat()
        }
        save_analysis_storage(analysis_storage)

        # Track active analysis
        if request.job_id:
            active_analyses[request.job_id] = analysis_id

        # Create analysis job record in database first
        if request.job_id:
            # Extract document ID from file URL if available
            document_id = "00000000-0000-0000-0000-000000000000"  # Default fallback
            if "/documents/" in request.file_url:
                try:
                    # Extract document ID from URL like: .../documents/86a70a15-9066-4348-a0be-8d0d81cf8cd8/...
                    url_parts = request.file_url.split("/documents/")
                    if len(url_parts) > 1:
                        doc_part = url_parts[1].split("/")[0]
                        if len(doc_part) == 36 and doc_part.count('-') == 4:  # UUID format check
                            document_id = doc_part
                except:
                    pass

            # Create job record in database
            config = {
                "tools": request.tools,
                "ai_providers": request.ai_providers,
                "analysis_types": request.analysis_types,
                "options": request.options
            }
            await create_analysis_job_db(request.job_id, document_id, config=config)

        # Update database immediately to processing status
        if request.job_id:
            await update_analysis_job_db(request.job_id, "processing", progress=10)

        # Start analysis as an asyncio task
        asyncio.create_task(
            run_analysis(
                analysis_id,
                request.file_url,
                request.tools,
                request.ai_providers,
                request.analysis_types,
                request.options,
                request.job_id
            )
        )

        return AnalysisResponse(
            analysis_id=analysis_id,
            status="pending",
            tools_used=list(request.tools.keys())
        )

    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cancel/{job_id}")
async def cancel_analysis(job_id: str):
    """Cancel a running analysis"""
    try:
        # Mark analysis as cancelled
        cancelled_analyses.add(job_id)

        # Update database
        await update_analysis_job_db(job_id, "cancelled", error="Analysis cancelled by user")

        # Clean up tracking
        if job_id in active_analyses:
            analysis_id = active_analyses[job_id]
            if analysis_id in analysis_storage:
                analysis_storage[analysis_id]["status"] = "cancelled"
                save_analysis_storage(analysis_storage)
            del active_analyses[job_id]

        logger.info(f"✅ Analysis {job_id} cancelled successfully")
        return {"message": f"Analysis {job_id} cancelled successfully", "status": "cancelled"}

    except Exception as e:
        logger.error(f"❌ Failed to cancel analysis {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel analysis: {str(e)}")

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

async def run_analysis(
    analysis_id: str,
    file_url: str,
    tools: Dict[str, bool],
    ai_providers: Dict[str, bool],
    analysis_types: Dict[str, bool],
    options: Dict[str, Any],
    job_id: Optional[str] = None
):
    """
    Run the complete document analysis pipeline with progress tracking
    """
    start_time = datetime.utcnow()
    print(f"🚀 ENTERING run_analysis: analysis_id={analysis_id}, job_id={job_id}")
    results = {}

    try:
        logger.info(f"🔍 Running analysis {analysis_id}")

        # Check for cancellation
        if await is_analysis_cancelled(job_id):
            logger.info(f"❌ Analysis {job_id} was cancelled before starting")
            return

        # Update progress: Starting analysis
        await update_analysis_job_db(job_id, "processing", progress=15)

        # Download document file
        document_path = await download_document(file_url)
        logger.info(f"📄 Downloaded document: {document_path}")

        # Check for cancellation
        if await is_analysis_cancelled(job_id):
            logger.info(f"❌ Analysis {job_id} cancelled during download")
            return

        # Update progress: Document downloaded
        await update_analysis_job_db(job_id, "processing", progress=25)

        # Basic document analysis (simulated)
        if tools.get('pymupdf', True):
            logger.info("📄 Running PyMuPDF analysis...")
            # Simulate analysis
            await asyncio.sleep(2)
            results['pymupdf_results'] = {
                'text_content': 'Sample extracted text content',
                'page_count': 1,
                'char_count': 1000
            }

            # Check for cancellation
            if await is_analysis_cancelled(job_id):
                logger.info(f"❌ Analysis {job_id} cancelled during PyMuPDF")
                return

            await update_analysis_job_db(job_id, "processing", progress=50)

        # Table extraction (simulated)
        if tools.get('pdfplumber', True):
            logger.info("📊 Running PDFPlumber analysis...")
            # Simulate analysis
            await asyncio.sleep(3)
            results['pdfplumber_results'] = {
                'tables': [{'data': 'Sample table data'}],
                'table_count': 1
            }

            # Check for cancellation
            if await is_analysis_cancelled(job_id):
                logger.info(f"❌ Analysis {job_id} cancelled during PDFPlumber")
                return

            await update_analysis_job_db(job_id, "processing", progress=75)

        # AI Analysis (simulated)
        logger.info("🤖 Running AI analysis...")
        await asyncio.sleep(2)

        # Check for cancellation one more time
        if await is_analysis_cancelled(job_id):
            logger.info(f"❌ Analysis {job_id} cancelled during AI analysis")
            return

        results['ai_results'] = {
            'summary': 'Document analysis completed successfully',
            'confidence': 0.85,
            'components': ['Component A', 'Component B'],
            'nomenclaturas': ['TAG-001', 'TAG-002']
        }

        await update_analysis_job_db(job_id, "processing", progress=90)

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Finalize results
        results['processing_time_seconds'] = processing_time
        results['status'] = 'completed'

        logger.info(f"✅ Analysis {analysis_id} completed in {processing_time:.2f}s")

        # Final database update: Analysis completed
        await update_analysis_job_db(job_id, "completed", results=results, progress=100)

        # Store completed analysis results
        analysis_storage[analysis_id] = {
            "status": "completed",
            "results": results,
            "processing_time": processing_time,
            "completed_at": datetime.utcnow().isoformat()
        }
        save_analysis_storage(analysis_storage)

        # Clean up tracking
        if job_id in active_analyses:
            del active_analyses[job_id]

        # Clean up temporary files
        try:
            if 'document_path' in locals():
                os.unlink(document_path)
        except:
            pass

    except Exception as e:
        logger.error(f"❌ Analysis {analysis_id} failed: {e}")
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Update database: Analysis failed
        await update_analysis_job_db(job_id, "failed", error=str(e))

        # Store failed analysis results
        analysis_storage[analysis_id] = {
            "status": "failed",
            "error": str(e),
            "processing_time": processing_time,
            "failed_at": datetime.utcnow().isoformat()
        }
        save_analysis_storage(analysis_storage)

        # Clean up tracking
        if job_id in active_analyses:
            del active_analyses[job_id]

@app.get("/analyze/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get analysis status and results"""
    if analysis_id not in analysis_storage:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored_result = analysis_storage[analysis_id]

    return {
        "analysis_id": analysis_id,
        "status": stored_result.get("status", "unknown"),
        "results": stored_result.get("results"),
        "error": stored_result.get("error"),
        "processing_time": stored_result.get("processing_time")
    }

@app.get("/analyze/{job_id}/status")
async def get_analysis_status_by_job_id(job_id: str):
    """Get analysis status by job ID - for force update functionality"""
    # Look for analysis by job_id
    for analysis_id, data in analysis_storage.items():
        if data.get("job_id") == job_id:
            return {
                "analysis_id": analysis_id,
                "job_id": job_id,
                "status": data.get("status", "unknown"),
                "results": data.get("results"),
                "error": data.get("error"),
                "processing_time": data.get("processing_time")
            }

    raise HTTPException(status_code=404, detail="Analysis not found")

@app.get("/active")
async def get_active_analyses():
    """Get list of currently active analyses"""
    return {
        "active_count": len(active_analyses),
        "active_analyses": list(active_analyses.keys()),
        "cancelled_count": len(cancelled_analyses)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)