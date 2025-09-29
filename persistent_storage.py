"""
Persistent storage for analysis results
Saves analysis results to files so they survive container restarts
"""
import json
import os
from datetime import datetime
from typing import Dict, Any

STORAGE_DIR = "/tmp/analysis_results"
STORAGE_FILE = "/tmp/analysis_storage.json"

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

def load_analysis_storage():
    """Load analysis storage from file"""
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading analysis storage: {e}")
    return {}

def save_analysis_storage(storage):
    """Save analysis storage to file"""
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(storage, f, indent=2)
    except Exception as e:
        print(f"Error saving analysis storage: {e}")

def save_analysis_file(analysis_id: str, job_id: str, results: Dict[str, Any]):
    """Save individual analysis results to separate file"""
    try:
        analysis_file = os.path.join(STORAGE_DIR, f"{job_id or analysis_id}.json")
        analysis_data = {
            "analysis_id": analysis_id,
            "job_id": job_id,
            "status": "completed",
            "results": results,
            "processing_time": results.get("processing_time_seconds", 0),
            "completed_at": datetime.utcnow().isoformat(),
            "saved_at": datetime.utcnow().isoformat()
        }
        
        with open(analysis_file, "w") as f:
            json.dump(analysis_data, f, indent=2)
        
        print(f"✅ Saved analysis results to {analysis_file}")
        return analysis_file
    except Exception as e:
        print(f"❌ Error saving analysis file: {e}")
        return None

def load_analysis_file(job_id: str):
    """Load analysis results from individual file"""
    try:
        analysis_file = os.path.join(STORAGE_DIR, f"{job_id}.json")
        if os.path.exists(analysis_file):
            with open(analysis_file, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading analysis file: {e}")
    return None

# Initialize global storage
analysis_storage = load_analysis_storage()
