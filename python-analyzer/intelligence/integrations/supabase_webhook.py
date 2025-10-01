"""
Supabase Webhook Integration
Handles callback notifications to Supabase when analysis completes
"""
import asyncio
import httpx
from typing import Dict, Any, Optional
from loguru import logger

from ..models.schemas import ExtractionResult, ProcessingStatus

class SupabaseWebhookClient:
    """Client for sending webhook notifications to Supabase"""
    
    def __init__(self, webhook_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.webhook_url = webhook_url or "https://api.rocktech.pt/functions/v1/analysis-webhook"
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def notify_analysis_started(self, analysis_id: str, intelligence_analysis_id: str):
        """Notify Supabase that analysis has started"""
        try:
            payload = {
                "event": "analysis_started",
                "analysis_id": analysis_id,
                "intelligence_analysis_id": intelligence_analysis_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_webhook(payload)
            logger.info(f"Notified analysis started: {analysis_id}")
            
        except Exception as e:
            logger.error(f"Failed to notify analysis started: {e}")
    
    async def notify_analysis_progress(self, analysis_id: str, progress: float, current_stage: str):
        """Notify Supabase of analysis progress"""
        try:
            payload = {
                "event": "analysis_progress",
                "analysis_id": analysis_id,
                "progress": progress,
                "current_stage": current_stage,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_webhook(payload)
            
        except Exception as e:
            logger.warning(f"Failed to notify progress: {e}")
    
    async def notify_analysis_completed(
        self, 
        analysis_id: str, 
        intelligence_analysis_id: str,
        results: ExtractionResult
    ):
        """Notify Supabase that analysis has completed successfully"""
        try:
            # Process results into Supabase-compatible format
            processed_results = {
                # Legacy format for compatibility
                "python_analysis": {
                    "pymupdf_results": {
                        "success": True,
                        "text_content": self._extract_text_from_pages(results.pages),
                        "page_count": len(results.pages),
                        "metadata": results.document_metadata.dict() if results.document_metadata else {}
                    } if results.pages else None,
                    "pdfplumber_results": {
                        "success": True,
                        "tables": [table.dict() for table in results.all_tables]
                    } if results.all_tables else None,
                    "pandas_results": {
                        "success": True,
                        "processed_tables": [table.dict() for table in results.bom_tables]
                    }
                },
                
                # Enhanced Intelligence Pipeline results
                "intelligence_analysis": {
                    "document_metadata": results.document_metadata.dict() if results.document_metadata else {},
                    "extraction_metrics": results.extraction_metrics.dict() if results.extraction_metrics else {},
                    
                    # Structured extractions
                    "pages": [page.dict() for page in results.pages],
                    "all_tables": [table.dict() for table in results.all_tables],
                    "all_callouts": [callout.dict() for callout in results.all_callouts],
                    "all_stamps": [stamp.dict() for stamp in results.all_stamps],
                    "all_key_value_pairs": [kv.dict() for kv in results.all_key_value_pairs],
                    
                    # Engineering-specific intelligence
                    "bom_tables": [table.dict() for table in results.bom_tables],
                    "reference_map": results.reference_map,
                    "specification_summary": results.specification_summary,
                    "revision_history": results.revision_history,
                    
                    # Relationships and cross-references
                    "element_relationships": results.element_relationships,
                    "drawing_hierarchy": results.drawing_hierarchy,
                    
                    # Quality metrics
                    "extraction_confidence": results.extraction_confidence,
                    "validation_results": results.validation_results,
                    "processing_warnings": results.processing_warnings
                },
                
                "processing_time": results.extraction_metrics.processing_time if results.extraction_metrics else 0,
                "success": True,
                
                "metadata": {
                    "pipeline_version": "intelligence_v1.0",
                    "analysis_timestamp": results.processing_timestamp,
                    "extraction_summary": {
                        "pages_analyzed": len(results.pages),
                        "tables_found": len(results.all_tables),
                        "callouts_linked": len(results.all_callouts),
                        "stamps_detected": len(results.all_stamps),
                        "confidence_score": results.extraction_confidence
                    }
                }
            }
            
            payload = {
                "event": "analysis_completed",
                "analysis_id": analysis_id,
                "intelligence_analysis_id": intelligence_analysis_id,
                "results": processed_results,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_webhook(payload)
            logger.success(f"Notified analysis completed: {analysis_id}")
            
        except Exception as e:
            logger.error(f"Failed to notify analysis completed: {e}")
    
    async def notify_analysis_failed(
        self, 
        analysis_id: str, 
        intelligence_analysis_id: str,
        error_message: str
    ):
        """Notify Supabase that analysis has failed"""
        try:
            payload = {
                "event": "analysis_failed",
                "analysis_id": analysis_id,
                "intelligence_analysis_id": intelligence_analysis_id,
                "error_message": error_message,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await self._send_webhook(payload)
            logger.info(f"Notified analysis failed: {analysis_id}")
            
        except Exception as e:
            logger.error(f"Failed to notify analysis failure: {e}")
    
    async def _send_webhook(self, payload: Dict[str, Any]):
        """Send webhook payload to Supabase"""
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        response = await self.client.post(
            self.webhook_url,
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        
    def _extract_text_from_pages(self, pages) -> str:
        """Extract text content from pages for legacy format"""
        if not pages:
            return ""
        
        text_parts = []
        for page in pages:
            page_text = " ".join([elem.text for elem in page.text_elements])
            text_parts.append(page_text)
        
        return "\n".join(text_parts)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()