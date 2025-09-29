#!/usr/bin/env python3
"""
Fix the Intelligence Service to use PostgreSQL direct connection
instead of webhooks. Use external IP since container networking is problematic.
"""
import re

# Read current main.py
with open('/root/catenary-intelligence/main.py', 'r') as f:
    content = f.read()

# Add asyncpg import at the top
if 'import asyncpg' not in content:
    content = content.replace('import asyncio', 'import asyncio\nimport asyncpg')

# Replace the entire call_webhook function with PostgreSQL direct update
webhook_pattern = r'async def call_webhook\(.*?\n.*?logger\.error\(f"❌ Failed to call webhook for job \{job_id\}: \{e\}"\)'
postgres_function = '''async def update_analysis_job_db(job_id: str, status: str, results: dict = None, error: str = None, progress: int = 0):
    """Update analysis job directly in PostgreSQL database"""
    if not job_id:
        return

    try:
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
        else:
            current_step = f"Analysis {status}"

        # Connect to PostgreSQL using external IP
        database_url = "postgresql://postgres:CaTy2025SecureDB_7aa74fde@204.44.123.122:5434/postgres"
        conn = await asyncpg.connect(database_url)

        try:
            # Call the PostgreSQL function we created
            result = await conn.fetchval(
                "SELECT update_analysis_job_progress($1::UUID, $2::status_enum, $3, $4, $5::JSONB, $6)",
                job_id, status, progress, current_step,
                results if results else None,
                error
            )

            if result:
                logger.info(f"✅ Updated job {job_id} to {status} (progress: {progress}%)")
            else:
                logger.warning(f"⚠️ Job {job_id} not found in database")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ Failed to update job {job_id}: {e}")'''

content = re.sub(webhook_pattern, postgres_function, content, flags=re.DOTALL)

# Replace all call_webhook calls with update_analysis_job_db calls
content = re.sub(r'await call_webhook\(webhook_url, job_id,', 'await update_analysis_job_db(job_id,', content)

# Remove webhook_url parameter from function signatures
content = re.sub(r'webhook_url: Optional\[str\] = None,\s*', '', content)
content = re.sub(r'request\.webhook_url,\s*', '', content)

# Write the updated content
with open('/root/catenary-intelligence/main.py', 'w') as f:
    f.write(content)

print("✅ Fixed Intelligence Service to use direct PostgreSQL connections")