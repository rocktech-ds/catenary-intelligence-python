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
        print("❌ [DB-UPDATE] No job_id provided to update_analysis_job_db")
        logger.error("❌ [DB-UPDATE] No job_id provided to update_analysis_job_db")
        return

    try:
        print(f"🔄 [DB-UPDATE] Database update called: job_id={job_id}, status={status}, progress={progress}")
        logger.info(f"🔄 [DB-UPDATE] Database update called: job_id={job_id}, status={status}, progress={progress}")

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

        print(f"📝 [DB-UPDATE] Current step determined: {current_step}")
        print(f"📝 [DB-UPDATE] Connecting to database for job {job_id}")
        logger.info(f"📝 [DB-UPDATE] Connecting to database for job {job_id} with current_step: {current_step}")

        # Connect to PostgreSQL using container hostname
        database_url = "postgresql://postgres:CaTy2025SecureDB_7aa74fde@catenary-db:5432/postgres"
        print(f"📡 [DB-UPDATE] Using database URL: {database_url}")

        try:
            conn = await asyncpg.connect(database_url)
            print(f"✅ [DB-UPDATE] Database connection established for job {job_id}")
            logger.info(f"✅ [DB-UPDATE] Database connection established for job {job_id}")
        except Exception as conn_error:
            print(f"❌ [DB-UPDATE] Failed to connect to database: {conn_error}")
            logger.error(f"❌ [DB-UPDATE] Failed to connect to database: {conn_error}")
            raise

        try:
            # First, check if the job exists
            print(f"🔍 [DB-UPDATE] Checking if job {job_id} exists in database")
            job_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM analysis_jobs WHERE id = $1)",
                job_id
            )
            print(f"🔍 [DB-UPDATE] Job {job_id} exists: {job_exists}")
            logger.info(f"🔍 [DB-UPDATE] Job {job_id} exists: {job_exists}")

            if not job_exists:
                print(f"⚠️ [DB-UPDATE] Job {job_id} not found in database - creating it")
                logger.warning(f"⚠️ [DB-UPDATE] Job {job_id} not found in database - creating it")
                # Try to create the job if it doesn't exist
                await conn.execute("""
                    INSERT INTO analysis_jobs (id, status, progress, current_step, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (id) DO NOTHING
                """, job_id, status, progress, current_step)
                print(f"✅ [DB-UPDATE] Created missing job {job_id} in database")
                logger.info(f"✅ [DB-UPDATE] Created missing job {job_id} in database")

            # Check if the database function exists
            print(f"🔍 [DB-UPDATE] Checking if update_analysis_job_progress function exists")
            function_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE p.proname = 'update_analysis_job_progress' AND n.nspname = 'public'
                )
            """)
            print(f"🔍 [DB-UPDATE] Function update_analysis_job_progress exists: {function_exists}")
            logger.info(f"🔍 [DB-UPDATE] Function update_analysis_job_progress exists: {function_exists}")

            if function_exists:
                print(f"📞 [DB-UPDATE] Calling database function for job {job_id}")
                logger.info(f"📞 [DB-UPDATE] Calling database function with params: job_id={job_id}, status={status}, progress={progress}, current_step={current_step}, results={json.dumps(results) if results else None}, error={error}")

                # Call the PostgreSQL function (it returns void, not a value)
                await conn.execute(
                    "SELECT update_analysis_job_progress($1, $2, $3, $4, $5, $6)",
                    job_id, status, progress, current_step,
                    json.dumps(results) if results else None,
                    error
                )
                print(f"✅ [DB-UPDATE] Function executed successfully for job {job_id}")
                logger.info(f"✅ [DB-UPDATE] Function executed successfully for job {job_id}")

                # Verify the update worked by checking if the job exists and was updated
                job_check = await conn.fetchval(
                    "SELECT status FROM analysis_jobs WHERE id = $1",
                    job_id
                )

                if job_check:
                    logger.info(f"✅ [DB-UPDATE] Verified job {job_id} updated to status: {job_check}")
                    print(f"✅ [DB-UPDATE] Database update successful for job {job_id} - status: {job_check}")
                else:
                    logger.warning(f"⚠️ [DB-UPDATE] Job {job_id} not found after update attempt")
                    print(f"⚠️ [DB-UPDATE] Job {job_id} not found after update attempt")
            else:
                # Function doesn't exist, use direct SQL update
                print(f"📝 [DB-UPDATE] Function not found, using direct SQL update for job {job_id}")
                logger.info(f"📝 [DB-UPDATE] Function not found, using direct SQL update for job {job_id}")

                update_data = {
                    'status': status,
                    'progress': progress,
                    'current_step': current_step,
                    'updated_at': datetime.utcnow()
                }

                if status == 'completed':
                    update_data['completed_at'] = datetime.utcnow()
                    if results:
                        update_data['results'] = json.dumps(results)
                        # Calculate processing time if we have started_at
                        processing_time_result = await conn.fetchval(
                            "SELECT EXTRACT(EPOCH FROM (NOW() - started_at)) FROM analysis_jobs WHERE id = $1",
                            job_id
                        )
                        if processing_time_result:
                            update_data['processing_time_seconds'] = float(processing_time_result)
                            print(f"📊 [DB-UPDATE] Calculated processing time: {processing_time_result}s")

                if error:
                    update_data['error_message'] = error

                # Build dynamic SQL update
                set_clauses = []
                values = []
                param_count = 1

                for key, value in update_data.items():
                    if key == 'updated_at':
                        set_clauses.append(f"{key} = NOW()")
                    elif key == 'completed_at' and value:
                        set_clauses.append(f"{key} = NOW()")
                    else:
                        set_clauses.append(f"{key} = ${param_count}")
                        values.append(value)
                        param_count += 1

                values.append(job_id)  # WHERE condition
                sql = f"UPDATE analysis_jobs SET {', '.join(set_clauses)} WHERE id = ${param_count}"

                print(f"📝 [DB-UPDATE] Executing SQL: {sql}")
                print(f"📝 [DB-UPDATE] With values: {values}")
                logger.info(f"📝 [DB-UPDATE] Executing SQL: {sql} with values: {values}")

                result = await conn.execute(sql, *values)
                rows_affected = int(result.split()[-1]) if result else 0

                print(f"📊 [DB-UPDATE] Rows affected: {rows_affected}")
                logger.info(f"📊 [DB-UPDATE] Rows affected: {rows_affected}")

                if rows_affected > 0:
                    print(f"✅ [DB-UPDATE] Successfully updated job {job_id} to {status} (progress: {progress}%)")
                    logger.info(f"✅ [DB-UPDATE] Successfully updated job {job_id} to {status} (progress: {progress}%)")
                else:
                    print(f"⚠️ [DB-UPDATE] No rows updated for job {job_id} - job may not exist")
                    logger.warning(f"⚠️ [DB-UPDATE] No rows updated for job {job_id} - job may not exist")

        finally:
            await conn.close()
            print(f"🔌 [DB-UPDATE] Database connection closed for job {job_id}")
            logger.info(f"🔌 [DB-UPDATE] Database connection closed for job {job_id}")

    except Exception as e:
        logger.error(f"❌ [DB-UPDATE] Failed to update job {job_id}: {e}")
        print(f"❌ [DB-UPDATE] EXCEPTION in update_analysis_job_db for job {job_id}: {e}")
        print(f"❌ [DB-UPDATE] Exception type: {type(e).__name__}")
        print(f"❌ [DB-UPDATE] Exception details: {str(e)}")
        import traceback
        print(f"❌ [DB-UPDATE] Traceback: {traceback.format_exc()}")
        logger.error(f"❌ [DB-UPDATE] Traceback: {traceback.format_exc()}")

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
        print(f"🚀 [ANALYZE] ================== NEW ANALYSIS REQUEST ==================")
        print(f"🚀 [ANALYZE] Analysis ID: {analysis_id}")
        print(f"🚀 [ANALYZE] Job ID: {request.job_id}")
        print(f"🚀 [ANALYZE] File URL: {request.file_url}")
        print(f"🚀 [ANALYZE] Tools: {request.tools}")
        print(f"🚀 [ANALYZE] AI Providers: {request.ai_providers}")
        print(f"🚀 [ANALYZE] Analysis Types: {request.analysis_types}")
        print(f"🚀 [ANALYZE] Options: {request.options}")
        print(f"🚀 [ANALYZE] ==========================================================")

        logger.info(f"[ANALYZE] Starting analysis {analysis_id} for file: {request.file_url}")
        logger.info(f"[ANALYZE] Job ID: {request.job_id}, Tools: {request.tools}")
        print(f"📋 [ANALYZE] About to start analysis task for job_id: {request.job_id}")

        # Initialize analysis in storage
        print(f"💾 [ANALYZE] Initializing analysis storage for {analysis_id}")
        analysis_storage[analysis_id] = {
            "status": "pending",
            "job_id": request.job_id,
            "started_at": datetime.utcnow().isoformat()
        }
        save_analysis_storage(analysis_storage)
        print(f"✅ [ANALYZE] Analysis storage initialized and saved")
        logger.info(f"[ANALYZE] Analysis storage initialized for {analysis_id}")

        # Track active analysis
        if request.job_id:
            print(f"📊 [ANALYZE] Tracking active analysis: job_id={request.job_id}, analysis_id={analysis_id}")
            active_analyses[request.job_id] = analysis_id
            logger.info(f"[ANALYZE] Added to active analyses: {request.job_id} -> {analysis_id}")
        else:
            print(f"⚠️ [ANALYZE] No job_id provided - analysis will not be tracked in active_analyses")
            logger.warning(f"[ANALYZE] No job_id provided for analysis {analysis_id}")

        # Create analysis job record in database first
        if request.job_id:
            print(f"📋 [ANALYZE] Creating database record for job: {request.job_id}")
            logger.info(f"[ANALYZE] Creating database record for job: {request.job_id}")

            # Extract document ID from file URL if available
            document_id = "00000000-0000-0000-0000-000000000000"  # Default fallback
            print(f"🔍 [ANALYZE] Extracting document ID from URL: {request.file_url}")

            if "/documents/" in request.file_url:
                try:
                    # Extract document ID from URL like: .../documents/86a70a15-9066-4348-a0be-8d0d81cf8cd8/...
                    url_parts = request.file_url.split("/documents/")
                    if len(url_parts) > 1:
                        doc_part = url_parts[1].split("/")[0]
                        if len(doc_part) == 36 and doc_part.count('-') == 4:  # UUID format check
                            document_id = doc_part
                            print(f"✅ [ANALYZE] Extracted document ID: {document_id}")
                            logger.info(f"[ANALYZE] Extracted document ID: {document_id}")
                        else:
                            print(f"⚠️ [ANALYZE] Document part doesn't look like UUID: {doc_part}")
                    else:
                        print(f"⚠️ [ANALYZE] Could not split URL on /documents/")
                except Exception as extract_error:
                    print(f"❌ [ANALYZE] Error extracting document ID: {extract_error}")
                    logger.error(f"[ANALYZE] Error extracting document ID: {extract_error}")
            else:
                print(f"⚠️ [ANALYZE] URL doesn't contain /documents/ - using default document_id")

            print(f"📋 [ANALYZE] Final document_id: {document_id}")

            # Create job record in database
            config = {
                "tools": request.tools,
                "ai_providers": request.ai_providers,
                "analysis_types": request.analysis_types,
                "options": request.options
            }
            print(f"📋 [ANALYZE] Calling create_analysis_job_db with config: {config}")
            logger.info(f"[ANALYZE] Calling create_analysis_job_db for {request.job_id} with document {document_id}")

            db_creation_result = await create_analysis_job_db(request.job_id, document_id, config=config)
            print(f"📊 [ANALYZE] Database creation result: {db_creation_result}")
            logger.info(f"[ANALYZE] Database creation result: {db_creation_result}")
        else:
            print(f"⚠️ [ANALYZE] No job_id provided - skipping database record creation")
            logger.warning(f"[ANALYZE] No job_id provided - skipping database record creation")

        # Update database immediately to processing status
        if request.job_id:
            print(f"🔄 [ANALYZE] Updating job {request.job_id} to processing status (10% progress)")
            logger.info(f"[ANALYZE] Updating job {request.job_id} to processing status")
            await update_analysis_job_db(request.job_id, "processing", progress=10)
            print(f"✅ [ANALYZE] Initial status update completed")
        else:
            print(f"⚠️ [ANALYZE] No job_id - skipping initial status update")

        # Start analysis as an asyncio task
        print(f"🚀 [ANALYZE] Starting async analysis task for {analysis_id}")
        logger.info(f"[ANALYZE] Starting async analysis task for {analysis_id}")

        analysis_task = asyncio.create_task(
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
        print(f"✅ [ANALYZE] Async analysis task created successfully")
        logger.info(f"[ANALYZE] Async analysis task created for {analysis_id}")

        print(f"📤 [ANALYZE] Returning response: analysis_id={analysis_id}, status=pending")
        logger.info(f"[ANALYZE] Returning analysis response for {analysis_id}")

        response = AnalysisResponse(
            analysis_id=analysis_id,
            status="pending",
            tools_used=list(request.tools.keys())
        )

        print(f"✅ [ANALYZE] Analysis request processed successfully - response ready")
        logger.info(f"[ANALYZE] Analysis request completed successfully for {analysis_id}")
        return response

    except Exception as e:
        print(f"❌ [ANALYZE] CRITICAL ERROR in analyze_document: {e}")
        print(f"❌ [ANALYZE] Exception type: {type(e).__name__}")
        print(f"❌ [ANALYZE] Exception details: {str(e)}")
        import traceback
        print(f"❌ [ANALYZE] Traceback: {traceback.format_exc()}")

        logger.error(f"[ANALYZE] Error starting analysis: {e}")
        logger.error(f"[ANALYZE] Traceback: {traceback.format_exc()}")

        # Try to update job to failed if we have a job_id
        if hasattr(request, 'job_id') and request.job_id:
            try:
                print(f"🔄 [ANALYZE] Updating job {request.job_id} to failed status due to error")
                await update_analysis_job_db(request.job_id, "failed", error=str(e))
            except Exception as update_error:
                print(f"❌ [ANALYZE] Failed to update job status to failed: {update_error}")
                logger.error(f"[ANALYZE] Failed to update job status to failed: {update_error}")

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
    """Download document from URL or copy from local file path to temporary file"""
    if file_url.startswith("file://"):
        # Remove file:// prefix and use local file system
        local_path = file_url[7:]  # Remove "file://" prefix
        if os.path.exists(local_path):
            return local_path
        else:
            raise FileNotFoundError(f"Local file not found: {local_path}")

    # For HTTP/HTTPS URLs, download directly (storage is public)
    headers = {}
    async with httpx.AsyncClient() as client:
        response = await client.get(file_url, headers=headers)
        response.raise_for_status()

        # Create temporary file
        import tempfile
        import uuid

        temp_file = os.path.join(tempfile.gettempdir(), f"doc_{uuid.uuid4().hex}.pdf")

        with open(temp_file, "wb") as f:
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

        # Basic document analysis (REAL PyMuPDF)
        if tools.get('pymupdf', True):
            logger.info("📄 Running PyMuPDF analysis...")
            print(f"📄 [ANALYSIS] Processing document: {document_path}")

            try:
                import fitz  # PyMuPDF

                # Open and analyze the document
                doc = fitz.open(document_path)
                page_count = len(doc)
                text_content = ""
                images = []

                print(f"📊 [ANALYSIS] Document has {page_count} pages")

                # Extract text from all pages
                for page_num in range(page_count):
                    page = doc[page_num]
                    page_text = page.get_text()
                    text_content += f"Page {page_num + 1}:\n{page_text}\n\n"

                    # Extract images info
                    image_list = page.get_images()
                    for img_index, img in enumerate(image_list):
                        images.append({
                            'page': page_num + 1,
                            'index': img_index,
                            'xref': img[0],
                            'width': img[2] if len(img) > 2 else None,
                            'height': img[3] if len(img) > 3 else None
                        })

                doc.close()

                # Clean and process text
                text_content = text_content.strip()
                char_count = len(text_content)
                word_count = len(text_content.split())

                print(f"✅ [ANALYSIS] Extracted {char_count} characters, {word_count} words from {page_count} pages")

                results['pymupdf_results'] = {
                    'text_content': text_content,
                    'page_count': page_count,
                    'char_count': char_count,
                    'word_count': word_count,
                    'images': images,
                    'images_count': len(images)
                }

            except Exception as e:
                print(f"❌ [ANALYSIS] PyMuPDF analysis failed: {e}")
                logger.error(f"PyMuPDF analysis failed: {e}")
                # Fallback to simulated data if real analysis fails
                results['pymupdf_results'] = {
                    'text_content': f'Error extracting text: {str(e)}',
                    'page_count': 1,
                    'char_count': 0,
                    'error': str(e)
                }

            # Check for cancellation
            if await is_analysis_cancelled(job_id):
                logger.info(f"❌ Analysis {job_id} cancelled during PyMuPDF")
                return

            await update_analysis_job_db(job_id, "processing", progress=50)

        # Table extraction (REAL PDFPlumber)
        if tools.get('pdfplumber', True):
            logger.info("📊 Running PDFPlumber analysis...")
            print(f"📊 [TABLES] Starting table extraction with PDFPlumber")

            try:
                import pdfplumber

                tables = []
                with pdfplumber.open(document_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        page_tables = page.extract_tables()

                        for table_index, table in enumerate(page_tables):
                            if table and len(table) > 0:
                                # Clean and process table data
                                cleaned_table = []
                                for row in table:
                                    if row and any(cell for cell in row if cell and str(cell).strip()):
                                        cleaned_row = [str(cell).strip() if cell else '' for cell in row]
                                        cleaned_table.append(cleaned_row)

                                if cleaned_table:
                                    tables.append({
                                        'page': page_num + 1,
                                        'table_index': table_index,
                                        'data': cleaned_table,
                                        'rows': len(cleaned_table),
                                        'columns': len(cleaned_table[0]) if cleaned_table else 0
                                    })

                print(f"✅ [TABLES] Extracted {len(tables)} tables from document")

                results['pdfplumber_results'] = {
                    'tables': tables,
                    'table_count': len(tables)
                }

            except Exception as e:
                print(f"❌ [TABLES] PDFPlumber analysis failed: {e}")
                logger.error(f"PDFPlumber analysis failed: {e}")
                # Fallback to empty results if analysis fails
                results['pdfplumber_results'] = {
                    'tables': [],
                    'table_count': 0,
                    'error': str(e)
                }

            # Check for cancellation
            if await is_analysis_cancelled(job_id):
                logger.info(f"❌ Analysis {job_id} cancelled during PDFPlumber")
                return

            await update_analysis_job_db(job_id, "processing", progress=75)

        # AI Analysis (REAL with extracted text)
        logger.info("🤖 Running AI analysis...")
        print(f"🤖 [AI-ANALYSIS] Starting AI analysis of extracted text")

        # Check for cancellation one more time
        if await is_analysis_cancelled(job_id):
            logger.info(f"❌ Analysis {job_id} cancelled during AI analysis")
            return

        try:
            # Get the extracted text from PyMuPDF results
            extracted_text = results.get('pymupdf_results', {}).get('text_content', '')

            if extracted_text and len(extracted_text.strip()) > 0:
                print(f"📋 [AI-ANALYSIS] Analyzing {len(extracted_text)} characters of text")

                # Simple text analysis for components and tags
                text_lower = extracted_text.lower()

                # Extract component-like patterns
                components = []
                nomenclaturas = []

                # Look for common technical drawing components
                component_keywords = ['motor', 'valve', 'pump', 'sensor', 'filter', 'tank', 'pipe', 'bearing', 'gasket', 'seal', 'switch', 'relay', 'transformer', 'capacitor', 'resistor', 'connector']
                for keyword in component_keywords:
                    if keyword in text_lower:
                        components.append(keyword.title())

                # Look for tag patterns (alphanumeric codes)
                import re
                tag_patterns = [
                    r'\b[A-Z]{1,3}[-_]?\d{2,4}\b',  # TAG-001, MT123, etc.
                    r'\b\d{2,4}[-_][A-Z]{1,3}\b',   # 001-TAG, 123MT, etc.
                    r'\bP&ID[-_]?\d+\b',            # P&ID references
                    r'\b[A-Z]\d{2,4}[A-Z]?\b'       # A123B, M45, etc.
                ]

                for pattern in tag_patterns:
                    matches = re.findall(pattern, extracted_text, re.IGNORECASE)
                    nomenclaturas.extend(matches[:10])  # Limit to first 10 matches

                # Remove duplicates
                components = list(set(components))[:10]  # Limit to 10 components
                nomenclaturas = list(set(nomenclaturas))[:10]  # Limit to 10 tags

                # Calculate confidence based on how much useful data we found
                confidence = 0.5  # Base confidence
                if components:
                    confidence += 0.2
                if nomenclaturas:
                    confidence += 0.2
                if len(extracted_text) > 1000:
                    confidence += 0.1
                confidence = min(confidence, 0.95)  # Cap at 95%

                # Generate summary
                summary = f"Document analysis completed. Found {len(components)} components and {len(nomenclaturas)} nomenclaturas/tags in {results['pymupdf_results']['page_count']} pages."

                print(f"✅ [AI-ANALYSIS] Found {len(components)} components, {len(nomenclaturas)} nomenclaturas")
                print(f"📊 [AI-ANALYSIS] Confidence: {confidence:.2f}")

                results['ai_results'] = {
                    'summary': summary,
                    'confidence': confidence,
                    'components': components if components else ['No components identified'],
                    'nomenclaturas': nomenclaturas if nomenclaturas else ['No nomenclaturas found'],
                    'text_length': len(extracted_text),
                    'analysis_method': 'rule_based_extraction'
                }

            else:
                # No text extracted
                print(f"⚠️ [AI-ANALYSIS] No text content available for AI analysis")
                results['ai_results'] = {
                    'summary': 'No text content could be extracted from the document',
                    'confidence': 0.1,
                    'components': ['Text extraction failed'],
                    'nomenclaturas': ['No text available'],
                    'error': 'No text content extracted'
                }

        except Exception as e:
            print(f"❌ [AI-ANALYSIS] AI analysis failed: {e}")
            logger.error(f"AI analysis failed: {e}")
            results['ai_results'] = {
                'summary': f'AI analysis failed: {str(e)}',
                'confidence': 0.0,
                'components': ['Analysis error'],
                'nomenclaturas': ['Error occurred'],
                'error': str(e)
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