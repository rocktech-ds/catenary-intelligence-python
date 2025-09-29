#!/usr/bin/env python3
"""
Update the Intelligence Service to use direct PostgreSQL connections
instead of webhooks for updating analysis job status.
"""
import re

def update_main_py():
    # Read the current main.py
    with open('/root/catenary-intelligence/main.py', 'r') as f:
        content = f.read()

    # Add PostgreSQL imports at the top after existing imports
    imports_section = """import os
import asyncio
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field"""

    new_imports_section = imports_section + """
import asyncpg
import json"""

    content = content.replace(imports_section, new_imports_section)

    # Replace the webhook function with a PostgreSQL update function
    webhook_function = r'''async def call_webhook\(webhook_url: str, job_id: str, status: str, results: Optional\[Dict\] = None, error: Optional\[str\] = None, progress: int = 0\):
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
                current_step = "Analyzing document structure"
            elif progress <= 60:
                current_step = "Extracting data from document"
            elif progress <= 75:
                current_step = "Processing with AI providers"
            elif progress <= 90:
                current_step = "Finalizing analysis results"
            else:
                current_step = "Completing analysis"
        else:
            current_step = f"Analysis {status}"

        # Prepare webhook payload
        payload = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "current_step": current_step
        }

        if status == "completed" and results:
            payload["results"] = serialize_numpy_values\(results\)
            payload["progress"] = 100
            payload["current_step"] = "Analysis completed successfully"
        elif status == "failed" and error:
            payload["error"] = error
            payload["current_step"] = f"Analysis failed: {error}"

        async with httpx\.AsyncClient\(timeout=30\) as client:
            response = await client\.post\(webhook_url, json=payload\)
            if response\.status_code == 200:
                logger\.info\(f"✅ Webhook called successfully for job {job_id}"\)
            else:
                logger\.warning\(f"⚠️ Webhook returned {response\.status_code} for job {job_id}"\)
    except Exception as e:
        logger\.error\(f"❌ Failed to call webhook for job {job_id}: {e}"\)'''

    new_db_function = '''async def update_analysis_job(job_id: str, status: str, results: Optional[Dict] = None, error: Optional[str] = None, progress: int = 0):
    """Update analysis job status directly in PostgreSQL"""
    if not job_id:
        return

    try:
        # Determine current step based on progress
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
        else:
            current_step = f"Analysis {status}"

        # Connect to PostgreSQL
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@catenary-db:5432/postgres")
        conn = await asyncpg.connect(database_url)

        try:
            # Prepare update data
            update_data = {
                "status": status,
                "progress": progress,
                "current_step": current_step,
                "updated_at": datetime.utcnow()
            }

            if status == "processing" and progress == 10:
                update_data["started_at"] = datetime.utcnow()
            elif status == "completed":
                update_data["completed_at"] = datetime.utcnow()
                update_data["progress"] = 100
                update_data["current_step"] = "Analysis completed successfully"
                if results:
                    update_data["results"] = json.dumps(serialize_numpy_values(results))
            elif status == "failed":
                update_data["completed_at"] = datetime.utcnow()
                update_data["error_message"] = error or "Analysis failed"
                update_data["current_step"] = f"Analysis failed: {error or 'Unknown error'}"

            # Build SQL update query
            set_clauses = []
            values = []
            param_count = 1

            for key, value in update_data.items():
                if key == "status":
                    set_clauses.append(f"{key} = ${param_count}::status_enum")
                else:
                    set_clauses.append(f"{key} = ${param_count}")
                values.append(value)
                param_count += 1

            # Add job_id parameter
            values.append(job_id)

            query = f"UPDATE analysis_jobs SET {', '.join(set_clauses)} WHERE id = ${param_count}"

            # Execute update
            result = await conn.execute(query, *values)

            if result == "UPDATE 1":
                logger.info(f"✅ Updated job {job_id} to {status} (progress: {progress}%)")
            else:
                logger.warning(f"⚠️ Job {job_id} not found in database")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ Failed to update job {job_id}: {e}")'''

    content = re.sub(webhook_function, new_db_function, content, flags=re.DOTALL)

    # Replace all call_webhook calls with update_analysis_job calls
    content = re.sub(r'await call_webhook\(webhook_url, job_id, "([^"]+)"(?:, progress=(\d+))?\)',
                     r'await update_analysis_job(job_id, "\1", progress=\2 if \2 else 0)', content)
    content = re.sub(r'await call_webhook\(webhook_url, job_id, "([^"]+)", results=results\)',
                     r'await update_analysis_job(job_id, "\1", results=results)', content)
    content = re.sub(r'await call_webhook\(webhook_url, job_id, "([^"]+)", error=str\(e\)\)',
                     r'await update_analysis_job(job_id, "\1", error=str(e))', content)

    # Remove webhook_url from run_analysis function signature and calls
    content = re.sub(r'webhook_url: Optional\[str\] = None,\s*', '', content)
    content = re.sub(r'request\.webhook_url,\s*', '', content)
    content = re.sub(r',\s*webhook_url', '', content)

    # Write updated content
    with open('/root/catenary-intelligence/main.py', 'w') as f:
        f.write(content)

    print("✅ Updated main.py to use direct PostgreSQL connections")

if __name__ == "__main__":
    update_main_py()