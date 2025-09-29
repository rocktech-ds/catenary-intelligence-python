"""
Monitoring and metrics utilities
"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from fastapi import FastAPI
from loguru import logger
import time

# Metrics
ANALYSIS_REQUESTS = Counter('pdf_intelligence_analysis_requests_total', 'Total analysis requests')
ANALYSIS_DURATION = Histogram('pdf_intelligence_analysis_duration_seconds', 'Analysis duration')
ANALYSIS_ERRORS = Counter('pdf_intelligence_analysis_errors_total', 'Analysis errors', ['error_type'])
ACTIVE_ANALYSES = Gauge('pdf_intelligence_active_analyses', 'Currently active analyses')
PIPELINE_HEALTH = Gauge('pdf_intelligence_pipeline_health', 'Pipeline health status')

def create_metrics_middleware():
    """Create metrics middleware function"""
    
    async def metrics_middleware(request, call_next):
        if request.url.path == "/analyze":
            ANALYSIS_REQUESTS.inc()
            start_time = time.time()
            
            try:
                ACTIVE_ANALYSES.inc()
                response = await call_next(request)
                
                if response.status_code == 200:
                    duration = time.time() - start_time
                    ANALYSIS_DURATION.observe(duration)
                else:
                    ANALYSIS_ERRORS.inc(['http_error'])
                    
                return response
                
            except Exception as e:
                ANALYSIS_ERRORS.inc(['exception'])
                raise
            finally:
                ACTIVE_ANALYSES.dec()
        else:
            return await call_next(request)
    
    return metrics_middleware

def setup_monitoring():
    """Setup monitoring - called after initialization"""
    logger.info("Monitoring setup completed")