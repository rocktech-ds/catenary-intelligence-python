"""
Intelligence Pipeline Configuration
Environment-based configuration management
"""
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import validator
import logging

class IntelligenceConfig(BaseSettings):
    """Configuration for PDF Intelligence Pipeline"""
    
    # Core settings
    max_workers: int = int(os.getenv('MAX_WORKERS', '4'))
    analysis_timeout: int = int(os.getenv('ANALYSIS_TIMEOUT', '1800'))  # 30 minutes
    max_file_size_mb: int = int(os.getenv('MAX_FILE_SIZE_MB', '500'))
    enable_cache: bool = os.getenv('ENABLE_CACHE', 'true').lower() == 'true'
    
    # Model paths and settings
    models_dir: Path = Path(os.getenv('MODELS_DIR', '/app/models'))
    detectron_model_path: Optional[str] = os.getenv('DETECTRON_MODEL_PATH')
    table_transformer_path: Optional[str] = os.getenv('TABLE_TRANSFORMER_PATH')
    
    # OCR settings
    tesseract_config: str = os.getenv('TESSERACT_CONFIG', '--oem 3 --psm 6')
    paddle_ocr_lang: str = os.getenv('PADDLE_OCR_LANG', 'pt,en')
    ocr_confidence_threshold: float = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '0.6'))
    
    # Layout detection
    layout_confidence_threshold: float = float(os.getenv('LAYOUT_CONFIDENCE_THRESHOLD', '0.7'))
    min_table_cells: int = int(os.getenv('MIN_TABLE_CELLS', '4'))
    
    # Performance tuning
    opencv_threads: int = int(os.getenv('OPENCV_THREADS', '4'))
    multiprocessing_workers: int = int(os.getenv('MULTIPROCESSING_WORKERS', '2'))
    memory_limit_gb: int = int(os.getenv('MEMORY_LIMIT_GB', '8'))
    
    # API settings
    api_timeout: int = int(os.getenv('API_TIMEOUT', '300'))
    max_concurrent_analyses: int = int(os.getenv('MAX_CONCURRENT_ANALYSES', '10'))
    
    # Cache settings
    redis_url: Optional[str] = os.getenv('REDIS_URL')
    cache_ttl: int = int(os.getenv('CACHE_TTL', '86400'))  # 24 hours
    
    # Monitoring
    prometheus_enabled: bool = os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true'
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Quality thresholds
    min_extraction_confidence: float = 0.5
    table_quality_threshold: float = 0.6
    
    # LLM Configuration
    llm_enabled: bool = False
    llm_provider: str = "xai"  # xai|groq|gemini
    llm_timeout_s: int = 30
    llm_max_tokens_per_doc: int = 8000
    llm_temperature: float = 0.1
    
    # xAI Settings (OpenAI-compatible)
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-beta"
    xai_api_key: Optional[str] = None
    
    # Groq Settings (OpenAI-compatible)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"
    groq_api_key: Optional[str] = None
    
    # Gemini Settings
    google_gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    
    # LLM Provider Priority (fallback order)
    llm_provider_priority: List[str] = ["groq", "xai", "gemini"]
    
    # Directory Configuration
    port: int = 8080
    models_dir: str = "/models"
    data_dir: str = "/data"
    out_dir: str = "/out"
    
    @validator('models_dir', pre=True)
    def validate_models_dir(cls, v):
        path = Path(v)
        path.mkdir(exist_ok=True, parents=True)
        return str(path)
    
    @validator('llm_enabled')
    def validate_llm_config(cls, v, values):
        if v and not any([
            values.get('xai_api_key'),
            values.get('groq_api_key'), 
            values.get('google_gemini_api_key')
        ]):
            logging.warning("LLM enabled but no API keys provided - will disable LLM features")
            return False
        return v
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set OpenMP threads for better performance
        os.environ['OMP_NUM_THREADS'] = str(self.opencv_threads)
        
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        
    @property
    def tool_settings(self) -> Dict[str, Any]:
        """Get tool-specific settings"""
        return {
            'pymupdf': {
                'extract_images': True,
                'extract_fonts': True,
                'extract_links': True,
            },
            'pdfplumber': {
                'table_settings': {
                    'vertical_strategy': 'lines_strict',
                    'horizontal_strategy': 'lines_strict',
                    'snap_tolerance': 3,
                    'join_tolerance': 3,
                }
            },
            'tesseract': {
                'config': self.tesseract_config,
                'languages': ['por', 'eng'],
            },
            'paddle_ocr': {
                'use_angle_cls': True,
                'lang': self.paddle_ocr_lang,
                'use_gpu': False,  # Set to True if GPU available
            },
            'layout_parser': {
                'model': 'lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config',
                'confidence_threshold': self.layout_confidence_threshold,
            },
            'table_transformer': {
                'model_name': 'microsoft/table-transformer-detection',
                'confidence_threshold': 0.7,
            }
        }
    
    @classmethod
    def from_env(cls) -> 'IntelligenceConfig':
        """Create configuration from environment variables"""
        return cls()
    
    def get_active_llm_providers(self) -> List[str]:
        """Get list of LLM providers with valid API keys"""
        active = []
        if self.xai_api_key:
            active.append("xai")
        if self.groq_api_key:
            active.append("groq")
        if self.google_gemini_api_key:
            active.append("gemini")
        return active
    
    def get_llm_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for specific LLM provider"""
        configs = {
            "xai": {
                "base_url": self.xai_base_url,
                "api_key": self.xai_api_key,
                "model": self.xai_model,
                "timeout": self.llm_timeout_s,
                "temperature": self.llm_temperature
            },
            "groq": {
                "base_url": self.groq_base_url,
                "api_key": self.groq_api_key,
                "model": self.groq_model,
                "timeout": self.llm_timeout_s,
                "temperature": self.llm_temperature
            },
            "gemini": {
                "api_key": self.google_gemini_api_key,
                "model": self.gemini_model,
                "timeout": self.llm_timeout_s,
                "temperature": self.llm_temperature
            }
        }
        return configs.get(provider, {})
    
    def get_processing_limits(self) -> Dict[str, Any]:
        """Get processing limits for different file types"""
        return {
            'max_pages': 200,
            'max_tables_per_page': 20,
            'max_callouts_per_page': 100,
            'max_text_elements_per_page': 1000,
            'timeout_per_page': 60,  # seconds
        }