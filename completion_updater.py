#!/usr/bin/env python3
import asyncio
import asyncpg
import json
import requests
from datetime import datetime, timedelta

async def update_completed_analyses():
    """Check for completed analyses and update database"""
    try:
        # Get completed analyses from Intelligence Service
        response = requests.get("http://localhost:8002/analyses/active")
        if response.status_code == 200:
            analyses = response.json()
            
            # Connect to database
            conn = await asyncpg.connect("postgresql://postgres:CaTy2025SecureDB_7aa74fde@catenary-db:5432/postgres")
            
            # Check for completed analyses that need status update
            for analysis_id, analysis_data in analyses.items():
                if analysis_data.get("status") == "completed":
                    # Find corresponding job_id and update database
                    # This would need to be enhanced with proper job_id mapping
                    print(f"Found completed analysis: {analysis_id}")
            
            await conn.close()
            
    except Exception as e:
        print(f"Error updating completed analyses: {e}")

if __name__ == "__main__":
    asyncio.run(update_completed_analyses())
