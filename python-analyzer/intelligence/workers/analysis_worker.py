"""
Analysis Worker - Background Processing
Handles queuing and processing of PDF intelligence analyses
"""
import asyncio
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
from enum import Enum

from loguru import logger
from ..core.pipeline_manager import PDFIntelligencePipeline
from ..core.config import IntelligenceConfig
from ..models.schemas import (
    AnalysisRequest, PipelineStatus, ExtractionResult, ProcessingStatus
)
from ..integrations.supabase_webhook import SupabaseWebhookClient

class TaskStatus(str, Enum):
    QUEUED = "pending"
    RUNNING = "running"  
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AnalysisTask:
    """Individual analysis task"""
    
    def __init__(self, analysis_id: str, request: AnalysisRequest):
        self.analysis_id = analysis_id
        self.request = request
        self.task_id = str(uuid.uuid4())
        
        # Status tracking
        self.status = TaskStatus.QUEUED
        self.progress = 0.0
        self.current_stage = "pending"
        self.current_operation = "Waiting in queue"
        
        # Timing
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.estimated_completion: Optional[datetime] = None
        
        # Results
        self.result: Optional[ExtractionResult] = None
        self.error: Optional[str] = None
        
        # Processing details
        self.pages_processed = 0
        self.total_pages = 0
        
    def to_pipeline_status(self) -> PipelineStatus:
        """Convert to PipelineStatus response"""
        return PipelineStatus(
            analysis_id=self.analysis_id,
            status=ProcessingStatus(self.status.value),
            progress=self.progress,
            current_stage=self.current_stage,
            started_at=self.started_at or self.created_at,
            estimated_completion=self.estimated_completion,
            pages_processed=self.pages_processed,
            total_pages=self.total_pages,
            current_operation=self.current_operation,
            partial_results_available=False
        )

class AnalysisWorker:
    """Background worker for processing PDF intelligence analyses"""
    
    def __init__(self, pipeline: PDFIntelligencePipeline, config: IntelligenceConfig):
        self.pipeline = pipeline
        self.config = config
        
        # Task management
        self.tasks: Dict[str, AnalysisTask] = {}
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Worker state
        self.status = "stopped"
        self.worker_task: Optional[asyncio.Task] = None
        self.max_concurrent = config.max_concurrent_analyses
        
        # Webhook client for Supabase notifications
        self.webhook_client = SupabaseWebhookClient()
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "average_processing_time": 0.0,
            "uptime_start": time.time()
        }
    
    async def start(self):
        """Start the background worker"""
        if self.status == "running":
            return
        
        self.status = "running"
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Analysis worker started")
    
    async def stop(self):
        """Stop the background worker"""
        if self.status == "stopped":
            return
        
        self.status = "stopping"
        
        # Cancel all running tasks
        for task in self.running_tasks.values():
            task.cancel()
        
        # Wait for worker to stop
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        self.status = "stopped"
        logger.info("Analysis worker stopped")
    
    async def queue_analysis(self, analysis_id: str, request: AnalysisRequest) -> str:
        """Queue a new analysis task"""
        task = AnalysisTask(analysis_id, request)
        
        # Estimate completion time
        estimated_duration = self.pipeline.estimate_processing_time(request)
        task.estimated_completion = datetime.now() + timedelta(seconds=estimated_duration)
        
        # Store task
        self.tasks[analysis_id] = task
        
        # Add to queue
        await self.queue.put(task)
        
        logger.info(f"Queued analysis {analysis_id} (task: {task.task_id})")
        return task.task_id
    
    async def get_analysis_status(self, analysis_id: str) -> Optional[PipelineStatus]:
        """Get status of an analysis"""
        task = self.tasks.get(analysis_id)
        if not task:
            return None
        
        return task.to_pipeline_status()
    
    async def get_analysis_results(self, analysis_id: str) -> Optional[ExtractionResult]:
        """Get results of a completed analysis"""
        task = self.tasks.get(analysis_id)
        if not task or task.status != TaskStatus.COMPLETED:
            return None
        
        return task.result
    
    async def cancel_analysis(self, analysis_id: str) -> bool:
        """Cancel a running or pending analysis"""
        task = self.tasks.get(analysis_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        # Cancel if running
        if analysis_id in self.running_tasks:
            self.running_tasks[analysis_id].cancel()
        
        # Update status
        task.status = TaskStatus.CANCELLED
        task.current_operation = "Cancelled by user"
        task.completed_at = datetime.now()
        
        logger.info(f"Cancelled analysis {analysis_id}")
        return True
    
    async def _worker_loop(self):
        """Main worker loop"""
        logger.info("Worker loop started")
        
        try:
            while self.status == "running":
                # Check if we can process more tasks
                if len(self.running_tasks) >= self.max_concurrent:
                    await asyncio.sleep(1)
                    continue
                
                try:
                    # Get next task from queue (with timeout)
                    task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    
                    # Start processing
                    process_task = asyncio.create_task(self._process_task(task))
                    self.running_tasks[task.analysis_id] = process_task
                    
                except asyncio.TimeoutError:
                    # No tasks in queue, continue loop
                    continue
                
                # Cleanup completed tasks
                await self._cleanup_completed_tasks()
                
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            self.status = "error"
    
    async def _process_task(self, task: AnalysisTask):
        """Process a single analysis task"""
        try:
            logger.info(f"Starting analysis {task.analysis_id}")
            
            # Update status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.current_stage = "initializing"
            task.current_operation = "Initializing analysis pipeline"
            task.progress = 0.1
            
            # Notify Supabase that analysis started via webhook
            await self.webhook_client.notify_analysis_started(
                task.analysis_id,
                task.task_id  # Using task_id as intelligence_analysis_id
            )
            
            # Run the analysis
            result = await self._run_analysis_with_progress(task)
            
            # Update success status
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            task.progress = 1.0
            task.current_stage = "completed"
            task.current_operation = "Analysis completed successfully"
            
            # Notify Supabase via webhook
            await self.webhook_client.notify_analysis_completed(
                task.analysis_id,
                task.task_id,  # Using task_id as intelligence_analysis_id
                result
            )
            
            # Update statistics
            self.stats["total_processed"] += 1
            if task.started_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                self._update_average_processing_time(duration)
            
            logger.success(f"Completed analysis {task.analysis_id}")
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.current_operation = "Analysis cancelled"
            logger.info(f"Analysis {task.analysis_id} was cancelled")
            raise
            
        except Exception as e:
            # Update error status
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            task.current_operation = f"Analysis failed: {str(e)}"
            
            # Notify Supabase of failure via webhook
            await self.webhook_client.notify_analysis_failed(
                task.analysis_id,
                task.task_id,  # Using task_id as intelligence_analysis_id
                str(e)
            )
            
            self.stats["total_failed"] += 1
            
            logger.error(f"Analysis {task.analysis_id} failed: {e}")
            
        finally:
            # Remove from running tasks
            if task.analysis_id in self.running_tasks:
                del self.running_tasks[task.analysis_id]
    
    async def _run_analysis_with_progress(self, task: AnalysisTask) -> ExtractionResult:
        """Run analysis with progress updates"""
        
        # Stage 1: Document loading and metadata
        task.current_stage = "loading"
        task.current_operation = "Loading document and extracting metadata"
        task.progress = 0.2
        await asyncio.sleep(0.1)  # Allow status update
        
        # Stage 2: Text extraction
        task.current_stage = "text_extraction"
        task.current_operation = "Extracting text and basic layout"
        task.progress = 0.4
        await asyncio.sleep(0.1)
        
        # Stage 3: Table extraction
        if task.request.options.extract_tables:
            task.current_stage = "table_extraction"
            task.current_operation = "Extracting tables and structured data"
            task.progress = 0.6
            await asyncio.sleep(0.1)
        
        # Stage 4: Advanced analysis
        task.current_stage = "advanced_analysis"
        task.current_operation = "Running advanced AI analysis"
        task.progress = 0.8
        await asyncio.sleep(0.1)
        
        # Stage 5: Finalization
        task.current_stage = "finalizing"
        task.current_operation = "Finalizing results and generating report"
        task.progress = 0.9
        
        # Run the actual analysis
        result = await self.pipeline.analyze_document(task.request)
        
        return result
    
    async def _cleanup_completed_tasks(self):
        """Cleanup completed tasks from running_tasks dict"""
        to_remove = []
        
        for analysis_id, task_future in self.running_tasks.items():
            if task_future.done():
                to_remove.append(analysis_id)
        
        for analysis_id in to_remove:
            del self.running_tasks[analysis_id]
    
    def _update_average_processing_time(self, duration: float):
        """Update average processing time statistic"""
        current_avg = self.stats["average_processing_time"]
        total_processed = self.stats["total_processed"]
        
        if total_processed == 1:
            self.stats["average_processing_time"] = duration
        else:
            # Moving average
            self.stats["average_processing_time"] = (
                (current_avg * (total_processed - 1) + duration) / total_processed
            )
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        uptime = time.time() - self.stats["uptime_start"]
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "status": self.status,
            "pending_tasks": self.queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "total_tasks": len(self.tasks),
            "max_concurrent": self.max_concurrent
        }