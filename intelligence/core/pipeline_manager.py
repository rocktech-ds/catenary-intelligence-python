"""
PDF Intelligence Pipeline Manager
Orchestrates all extraction modules for engineering drawings
"""
import asyncio
import time
import traceback
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid

from loguru import logger
import httpx
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from .config import IntelligenceConfig
from ..extractors.layout_detector import LayoutDetector
from ..extractors.table_extractor import TableExtractor
from ..extractors.callout_linker import CalloutLinker
from ..extractors.kv_extractor import KeyValueExtractor
from ..extractors.stamp_detector import StampDetector
from ..extractors.text_extractor import TextExtractor
from ..models.schemas import (
    AnalysisRequest, ExtractionResult, DocumentMetadata,
    ExtractionMetrics, ToolsStatus, ToolStatus
)
from ..models.target_schemas import (
    FinalResult, DocumentResult, PageResult, TitleBlock, 
    TableBlock, Callout, Assembly, RevisionEntry, AuthorBlock
)

class PDFIntelligencePipeline:
    """
    Master orchestrator for PDF intelligence extraction
    Manages all extraction modules and processing workflow
    """
    
    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.extractors: Dict[str, Any] = {}
        self.thread_pool: Optional[ThreadPoolExecutor] = None
        self.process_pool: Optional[ProcessPoolExecutor] = None
        self._initialized = False
        self._models_loaded = {}
        
    async def initialize(self):
        """Initialize all extraction modules and models"""
        try:
            logger.info("Initializing PDF Intelligence Pipeline...")
            
            # Initialize thread pools
            self.thread_pool = ThreadPoolExecutor(
                max_workers=self.config.max_workers,
                thread_name_prefix="PDFIntel"
            )
            self.process_pool = ProcessPoolExecutor(
                max_workers=self.config.multiprocessing_workers
            )
            
            # Initialize extractors
            await self._initialize_extractors()
            
            # Load models
            await self._load_models()
            
            self._initialized = True
            logger.success("PDF Intelligence Pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _initialize_extractors(self):
        """Initialize all extraction modules"""
        extractor_classes = {
            'layout_detector': LayoutDetector,
            'table_extractor': TableExtractor,
            'callout_linker': CalloutLinker,
            'kv_extractor': KeyValueExtractor,
            'stamp_detector': StampDetector,
            'text_extractor': TextExtractor,
        }
        
        for name, cls in extractor_classes.items():
            try:
                self.extractors[name] = cls(self.config)
                logger.info(f"Initialized {name}")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")
                # Continue with other extractors
    
    async def _load_models(self):
        """Load all ML models"""
        logger.info("Loading AI models...")
        
        # Load models in parallel where possible
        load_tasks = []
        
        for name, extractor in self.extractors.items():
            if hasattr(extractor, 'load_models'):
                load_tasks.append(self._load_extractor_models(name, extractor))
        
        results = await asyncio.gather(*load_tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            extractor_name = list(self.extractors.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Failed to load models for {extractor_name}: {result}")
                self._models_loaded[extractor_name] = False
            else:
                self._models_loaded[extractor_name] = result
        
        logger.info(f"Models loaded: {sum(self._models_loaded.values())}/{len(self._models_loaded)}")
    
    async def _load_extractor_models(self, name: str, extractor) -> bool:
        """Load models for a specific extractor"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.thread_pool, extractor.load_models)
            return True
        except Exception as e:
            logger.error(f"Failed to load models for {name}: {e}")
            return False
    
    def is_ready(self) -> bool:
        """Check if pipeline is ready for processing"""
        return self._initialized and any(self._models_loaded.values())
    
    def get_models_status(self) -> Dict[str, bool]:
        """Get status of all loaded models"""
        return self._models_loaded.copy()
    
    async def get_tools_status(self) -> ToolsStatus:
        """Get comprehensive tools status"""
        tools_status = {}
        
        for name, extractor in self.extractors.items():
            try:
                if hasattr(extractor, 'get_status'):
                    status = await extractor.get_status()
                else:
                    status = ToolStatus(
                        available=self._models_loaded.get(name, False),
                        version="unknown"
                    )
                tools_status[name] = status
            except Exception as e:
                tools_status[name] = ToolStatus(
                    available=False,
                    last_error=str(e)
                )
        
        return ToolsStatus(
            pipeline_ready=self.is_ready(),
            tools=tools_status,
            models_loaded=self._models_loaded,
            system_info={
                "max_workers": self.config.max_workers,
                "memory_limit_gb": self.config.memory_limit_gb,
                "extractors": list(self.extractors.keys())
            }
        )
    
    def estimate_processing_time(self, request: AnalysisRequest) -> int:
        """Estimate processing time in seconds"""
        base_time = 30  # Base processing time
        
        # Add time based on enabled tools
        if request.tools.layout_parser:
            base_time += 60
        if request.tools.table_transformer:
            base_time += 45
        if request.tools.tesseract_ocr:
            base_time += 120
        if request.tools.paddle_ocr:
            base_time += 90
        
        return min(base_time, self.config.analysis_timeout)
    
    async def analyze_document(self, request: AnalysisRequest) -> ExtractionResult:
        """
        Main analysis entry point
        Orchestrates full PDF intelligence extraction
        """
        analysis_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            logger.info(f"Starting analysis {analysis_id} for {request.file_url}")
            
            # Download file
            file_path = await self._download_file(request.file_url, analysis_id)
            
            # Extract document metadata
            metadata = await self._extract_metadata(file_path)
            
            # Core extraction pipeline
            extraction_results = await self._run_extraction_pipeline(
                file_path, request, analysis_id
            )
            
            # Convert to target schema format
            target_result = await self._convert_to_target_schema(
                file_path, extraction_results, metadata
            )
            
            # Build final results
            result = self._build_extraction_result(
                analysis_id, metadata, extraction_results, start_time
            )
            
            # Cleanup
            await self._cleanup_temp_file(file_path)
            
            logger.success(f"Analysis {analysis_id} completed in {result.extraction_metrics.processing_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {str(e)}")
            await self._cleanup_temp_file(locals().get("file_path"))
            raise e
    
    async def analyze_document_target_schema(self, request: AnalysisRequest) -> FinalResult:
        """
        Analyze document and return results in target schema format
        This is the main method for producing the final JSON matching your example
        """
        analysis_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Starting target schema analysis {analysis_id} for {request.file_url}")
            
            # Download file
            file_path = await self._download_file(request.file_url, analysis_id)
            
            # Extract document metadata
            metadata = await self._extract_metadata(file_path)
            
            # Core extraction pipeline
            extraction_results = await self._run_extraction_pipeline(
                file_path, request, analysis_id
            )
            
            # Convert to target schema format
            target_result = await self._convert_to_target_schema(
                file_path, extraction_results, metadata
            )
            
            # Cleanup
            await self._cleanup_temp_file(file_path)
            
            logger.success(f"Target schema analysis {analysis_id} completed")
            return target_result
            
        except Exception as e:
            logger.error(f"Target schema analysis {analysis_id} failed: {e}")
            logger.error(traceback.format_exc())
            raise
            
        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _download_file(self, file_url: str, analysis_id: str) -> Path:
        """Download file from URL"""
        temp_dir = Path("/tmp/pdf_intelligence")
        temp_dir.mkdir(exist_ok=True)
        
        file_path = temp_dir / f"{analysis_id}.pdf"
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(file_url)
            response.raise_for_status()
            
            file_path.write_bytes(response.content)
        
        return file_path
    
    async def _extract_metadata(self, file_path: Path) -> DocumentMetadata:
        """Extract document metadata"""
        extractor = self.extractors.get('text_extractor')
        if not extractor:
            return DocumentMetadata()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, extractor.extract_metadata, file_path
        )
    
    async def _run_extraction_pipeline(
        self, file_path: Path, request: AnalysisRequest, analysis_id: str
    ) -> Dict[str, Any]:
        """Run the complete extraction pipeline"""
        
        results = {
            'pages': [],
            'all_tables': [],
            'all_callouts': [],
            'all_stamps': [],
            'all_key_value_pairs': [],
            'element_relationships': {},
            'processing_warnings': []
        }
        
        try:
            # Stage 1: Basic text and layout extraction
            if request.tools.pymupdf or request.tools.pdfplumber:
                text_results = await self._extract_text_and_layout(file_path, request)
                results.update(text_results)
            
            # Stage 2: Advanced layout detection
            if request.tools.layout_parser:
                layout_results = await self._detect_layout(file_path, request)
                results.update(layout_results)
            
            # Stage 3: Table extraction
            if request.options.extract_tables:
                table_results = await self._extract_tables(file_path, request)
                results['all_tables'].extend(table_results.get('tables', []))
            
            # Stage 4: Callout and reference linking
            if request.options.extract_callouts:
                callout_results = await self._extract_callouts(file_path, request)
                results['all_callouts'].extend(callout_results.get('callouts', []))
            
            # Stage 5: Stamp and seal detection
            if request.options.extract_stamps:
                stamp_results = await self._detect_stamps(file_path, request)
                results['all_stamps'].extend(stamp_results.get('stamps', []))
            
            # Stage 6: Key-value extraction
            if hasattr(request.options, 'extract_key_values') and request.options.extract_key_values:
                kv_results = await self._extract_key_values(file_path, request)
                results['all_key_value_pairs'].extend(kv_results.get('kv_pairs', []))
            
            # Stage 7: Cross-reference analysis
            relationships = await self._analyze_relationships(results)
            results['element_relationships'] = relationships
            
            return results
            
        except Exception as e:
            logger.error(f"Extraction pipeline failed: {e}")
            results['processing_warnings'].append(f"Pipeline error: {str(e)}")
            return results
    
    async def _extract_text_and_layout(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract text and basic layout"""
        extractor = self.extractors.get('text_extractor')
        if not extractor:
            return {}
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, extractor.extract_text_and_layout, file_path, request
        )
    
    async def _detect_layout(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Detect page layout using AI models"""
        detector = self.extractors.get('layout_detector')
        if not detector:
            return {}
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, detector.detect_layout, file_path, request
        )
    
    async def _extract_tables(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract tables with multiple methods (now async with AI)"""
        extractor = self.extractors.get('table_extractor')
        if not extractor:
            return {}
        
        # Direct async call - no thread executor needed since the method is now async
        return await extractor.extract_tables(file_path, request)
    
    async def _extract_callouts(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract and link callouts (now async with AI)"""
        linker = self.extractors.get('callout_linker')
        if not linker:
            return {}
        
        # Direct async call - no thread executor needed since the method is now async
        return await linker.extract_callouts(file_path, request)
    
    async def _detect_stamps(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Detect stamps and seals"""
        detector = self.extractors.get('stamp_detector')
        if not detector:
            return {}
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, detector.detect_stamps, file_path, request
        )
    
    async def _extract_key_values(self, file_path: Path, request: AnalysisRequest) -> Dict[str, Any]:
        """Extract key-value pairs (now async with AI)"""
        extractor = self.extractors.get('kv_extractor')
        if not extractor:
            return {}
        
        # Direct async call - no thread executor needed since the method is now async
        return await extractor.extract_key_values(file_path, request)
    
    async def _analyze_relationships(self, results: Dict[str, Any]) -> Dict[str, List[str]]:
        """Analyze relationships between extracted elements"""
        # This would implement sophisticated relationship analysis
        # For now, return empty relationships
        return {}
    
    async def _convert_to_target_schema(
        self, file_path: Path, results: Dict[str, Any], metadata: DocumentMetadata
    ) -> FinalResult:
        """Convert extraction results to target schema format"""
        
        # Extract document-level metadata from KV pairs
        document_data = await self._extract_document_metadata(results, metadata)
        
        # Convert page-level data
        pages = []
        for page_idx in range(metadata.page_count if hasattr(metadata, 'page_count') else 1):
            page_result = await self._convert_page_to_target_schema(
                page_idx, results, file_path
            )
            pages.append(page_result)
        
        return FinalResult(
            document=document_data,
            pages=pages
        )
    
    async def _extract_document_metadata(
        self, results: Dict[str, Any], metadata: DocumentMetadata
    ) -> DocumentResult:
        """Extract document-level metadata from extraction results"""
        
        # Get KV pairs from extraction results
        kv_pairs = results.get('all_key_value_pairs', [])
        kv_dict = {}
        
        # Convert KV pairs to dictionary for easier access
        for kv in kv_pairs:
            if hasattr(kv, 'key') and hasattr(kv, 'value'):
                kv_dict[kv.key] = kv.value
            elif isinstance(kv, dict):
                kv_dict.update(kv)
        
        # Extract authors if present
        authors = None
        if 'projectist' in kv_dict or 'director' in kv_dict:
            authors = AuthorBlock(
                projectist=kv_dict.get('projectist'),
                director=kv_dict.get('director'),
                others=[]
            )
        
        return DocumentResult(
            file_name=getattr(metadata, 'file_name', 'document.pdf'),
            language='pt',  # Portuguese engineering documents
            title=kv_dict.get('title'),
            specialty=kv_dict.get('specialty'),
            sap_number=kv_dict.get('sap_number'),
            version=kv_dict.get('version'),
            project_code=kv_dict.get('project_code'),
            date=kv_dict.get('date'),
            authors=authors
        )
    
    async def _convert_page_to_target_schema(
        self, page_idx: int, results: Dict[str, Any], file_path: Path
    ) -> PageResult:
        """Convert page-level results to target schema"""
        
        # Convert tables using extractor's conversion method
        tables = []
        table_extractor = self.extractors.get('table_extractor')
        if table_extractor and hasattr(table_extractor, 'convert_to_target_schema'):
            page_tables = [t for t in results.get('all_tables', []) if getattr(t, 'bbox', {}).get('page', 0) == page_idx]
            tables = table_extractor.convert_to_target_schema(page_tables)
        
        # Convert callouts using linker's conversion method  
        callouts = []
        callout_linker = self.extractors.get('callout_linker')
        if callout_linker and hasattr(callout_linker, 'convert_to_target_schema'):
            page_callouts = [c for c in results.get('all_callouts', []) if getattr(c, 'bbox', {}).get('page', 0) == page_idx]
            callouts = callout_linker.convert_to_target_schema(page_callouts)
        
        # Create title block from KV pairs (typically on page 0)
        title_block = None
        if page_idx == 0:
            kv_pairs = results.get('all_key_value_pairs', [])
            title_fields = {}
            for kv in kv_pairs:
                if hasattr(kv, 'key') and hasattr(kv, 'value'):
                    title_fields[kv.key] = kv.value
                elif isinstance(kv, dict):
                    title_fields.update(kv)
            
            if title_fields:
                title_block = TitleBlock(fields=title_fields)
        
        # Mock assemblies and revision history (would be extracted from specific areas)
        assemblies = []
        revision_history = []
        
        return PageResult(
            page_index=page_idx,
            title_block=title_block,
            tables=tables,
            callouts=callouts,
            assemblies=assemblies,
            revision_history=revision_history
        )
    
    def _build_extraction_result(
        self, analysis_id: str, metadata: DocumentMetadata, 
        results: Dict[str, Any], start_time: float
    ) -> ExtractionResult:
        """Build the final extraction result"""
        
        processing_time = time.time() - start_time
        
        # Calculate metrics
        metrics = ExtractionMetrics(
            processing_time=processing_time,
            file_size_mb=0,  # Would be calculated from actual file
            page_count=len(results.get('pages', [])),
            overall_quality=0.8,  # Would be calculated based on extraction quality
            text_extraction_quality=0.9,
            table_extraction_quality=0.7,
            layout_detection_quality=0.8,
            tools_used=list(self.extractors.keys()),
            primary_extraction_method="pymupdf",
            fallback_methods_used=[],
            total_text_elements=len([e for page in results.get('pages', []) for e in page.get('text_elements', [])]),
            total_tables=len(results.get('all_tables', [])),
            total_callouts=len(results.get('all_callouts', [])),
            total_stamps=len(results.get('all_stamps', [])),
            total_kv_pairs=len(results.get('all_key_value_pairs', []))
        )
        
        return ExtractionResult(
            analysis_id=analysis_id,
            document_metadata=metadata,
            extraction_metrics=metrics,
            processing_timestamp=time.time(),
            pages=results.get('pages', []),
            all_tables=results.get('all_tables', []),
            all_callouts=results.get('all_callouts', []),
            all_stamps=results.get('all_stamps', []),
            all_key_value_pairs=results.get('all_key_value_pairs', []),
            bom_tables=[],  # Would filter from all_tables
            reference_map=results.get('element_relationships', {}),
            specification_summary={},
            revision_history=[],
            element_relationships=results.get('element_relationships', {}),
            extraction_confidence=0.8,  # Would be calculated
            validation_results={},
            processing_warnings=results.get('processing_warnings', [])
        )
    
    async def _cleanup_temp_file(self, file_path: Path):
        """Cleanup temporary file"""
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")
    
    async def cleanup(self):
        """Cleanup pipeline resources"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        
        logger.info("Pipeline cleanup completed")