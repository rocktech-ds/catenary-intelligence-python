#!/usr/bin/env python3
"""
Fix storage and polling for analysis results
Implements in-memory storage with proper status tracking
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from collections import OrderedDict
import threading
import time

class AnalysisStorage:
    """Simple in-memory storage for analysis results with TTL"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.storage: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def store(self, analysis_id: str, data: Dict[str, Any]) -> None:
        """Store analysis data with automatic cleanup"""
        with self.lock:
            # Add timestamp
            data["stored_at"] = datetime.utcnow().isoformat()
            data["expires_at"] = (datetime.utcnow() + timedelta(hours=self.ttl_hours)).isoformat()
            
            # Store data
            self.storage[analysis_id] = data
            
            # Enforce size limit (LRU)
            while len(self.storage) > self.max_size:
                self.storage.popitem(last=False)
    
    def get(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis data if exists and not expired"""
        with self.lock:
            if analysis_id not in self.storage:
                return None
            
            data = self.storage[analysis_id]
            expires_at = datetime.fromisoformat(data["expires_at"])
            
            if datetime.utcnow() > expires_at:
                del self.storage[analysis_id]
                return None
            
            return data
    
    def update_status(self, analysis_id: str, status: str, progress: int = None, 
                     current_step: str = None, results: Any = None, error: str = None) -> bool:
        """Update analysis status"""
        with self.lock:
            if analysis_id not in self.storage:
                # Create new entry if doesn't exist
                self.storage[analysis_id] = {
                    "analysis_id": analysis_id,
                    "status": status,
                    "created_at": datetime.utcnow().isoformat()
                }
            
            data = self.storage[analysis_id]
            data["status"] = status
            data["updated_at"] = datetime.utcnow().isoformat()
            
            if progress is not None:
                data["progress"] = progress
            if current_step:
                data["current_step"] = current_step
            if results:
                data["results"] = results
            if error:
                data["error"] = error
            
            if status == "completed":
                data["completed_at"] = datetime.utcnow().isoformat()
                if "created_at" in data:
                    created = datetime.fromisoformat(data["created_at"])
                    data["processing_time"] = (datetime.utcnow() - created).total_seconds()
            
            return True
    
    def _cleanup_loop(self):
        """Background thread to clean up expired entries"""
        while True:
            time.sleep(3600)  # Check every hour
            self._cleanup_expired()
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        with self.lock:
            now = datetime.utcnow()
            expired_keys = []
            
            for key, data in self.storage.items():
                if "expires_at" in data:
                    expires_at = datetime.fromisoformat(data["expires_at"])
                    if now > expires_at:
                        expired_keys.append(key)
            
            for key in expired_keys:
                del self.storage[key]
            
            if expired_keys:
                print(f"Cleaned up {len(expired_keys)} expired analysis entries")

# Global storage instance
analysis_storage = AnalysisStorage()

# Export for use in main.py
__all__ = ["analysis_storage", "AnalysisStorage"]

if __name__ == "__main__":
    # Test the storage
    storage = AnalysisStorage()
    
    # Test store and get
    test_id = "test_analysis_123"
    storage.store(test_id, {"status": "pending", "file": "test.pdf"})
    print(f"Stored: {storage.get(test_id)}")
    
    # Test update
    storage.update_status(test_id, "running", progress=50, current_step="Processing PDF")
    print(f"Updated: {storage.get(test_id)}")
    
    # Test completion
    storage.update_status(test_id, "completed", progress=100, 
                         results={"pages": 10, "text": "Sample text"})
    print(f"Completed: {storage.get(test_id)}")
EOF'