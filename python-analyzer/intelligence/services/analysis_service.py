"""
Enhanced Analysis Service

This service integrates all the new advanced extractors and provides
a unified interface for comprehensive document analysis.
"""

import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import tempfile
import uuid

from ..models.analysis_models import (
    AnalysisRequest, EnhancedAnalysisResult, StampDetectionResult,
    LayoutAnalysisResult, RevisionTrackingResult, AssemblyDetectionResult
)

# Import the new extractors
from ..extractors.stamp_detector import StampDetector
from ..extractors.layout_analyzer import AdvancedLayoutAnalyzer
from ..extractors.revision_tracker import AdvancedRevisionTracker
from ..extractors.assembly_detector import AdvancedAssemblyDetector
from ..extractors.advanced_table_extractor import AdvancedTableExtractor as FreeTableExtractor
from ..extractors.technical_specs_extractor import TechnicalSpecsExtractor
from ..extractors.dimensional_analyzer import DimensionalAnalyzer
from ..extractors.vector_graphics_extractor import VectorGraphicsExtractor

# Import free services manager
from ..services.free_services_manager import free_services
from ..core.config import IntelligenceConfig

logger = logging.getLogger(__name__)

class EnhancedAnalysisService:
    """
    Enhanced analysis service that coordinates all extractors
    """
    
    def __init__(self, config: Optional[IntelligenceConfig] = None):
        self.logger = logging.getLogger(__name__)
        
        # Initialize config if not provided
        if config is None:
            config = IntelligenceConfig()
        self.config = config
        
        # Initialize extractors
        self.stamp_detector = StampDetector(self.config)
        self.layout_analyzer = AdvancedLayoutAnalyzer()
        self.revision_tracker = AdvancedRevisionTracker()
        self.assembly_detector = AdvancedAssemblyDetector()
        self.table_extractor = FreeTableExtractor(self.config)
        self.technical_specs_extractor = TechnicalSpecsExtractor()
        self.dimensional_analyzer = DimensionalAnalyzer()
        self.vector_graphics_extractor = VectorGraphicsExtractor()
        
        # Analysis status tracking
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
    
    async def analyze_document(self, request: AnalysisRequest) -> EnhancedAnalysisResult:
        """
        Perform comprehensive document analysis using all enabled extractors
        """
        analysis_id = f"enhanced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        
        # Initialize analysis status
        self.active_analyses[analysis_id] = {
            'status': 'processing',
            'progress': 0.0,
            'current_step': 'initializing',
            'start_time': start_time
        }
        
        try:
            logger.info(f"🚀 Starting enhanced analysis {analysis_id} for {request.file_url}")
            
            # Download and prepare document
            document_path = await self._download_document(request.file_url)
            
            # Initialize result structure
            result = EnhancedAnalysisResult(
                analysis_id=analysis_id,
                status="processing"
            )
            
            processing_warnings = []
            total_steps = sum([
                1 if request.analysis_types.get("stamp_detection", False) else 0,
                1 if request.analysis_types.get("layout_analysis", False) else 0,
                1 if request.analysis_types.get("revision_tracking", False) else 0,
                1 if request.analysis_types.get("assembly_detection", False) else 0,
                1 if request.analysis_types.get("extract_tables", False) else 0,
                1 if request.analysis_types.get("technical_specs", False) else 0,
                1 if request.analysis_types.get("dimensional_analysis", False) else 0,
                1 if request.analysis_types.get("vector_graphics", False) else 0,
                1 if request.analysis_types.get("ai_consensus", False) else 0,
                1  # Final processing step
            ])
            
            current_step = 0
            
            # 1. Stamp Detection
            if request.analysis_types.get("stamp_detection", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Detecting stamps...")
                
                try:
                    logger.info(f"📋 Running stamp detection for {analysis_id}")
                    stamp_result = await self.stamp_detector.detect_stamps(document_path, request)
                    
                    result.stamp_detection = StampDetectionResult(
                        stamps=stamp_result.get('stamps', []),
                        processing_warnings=stamp_result.get('processing_warnings', []),
                        metadata=stamp_result.get('metadata', {})
                    )
                    processing_warnings.extend(stamp_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Stamp detection failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 2. Layout Analysis
            if request.analysis_types.get("layout_analysis", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Analyzing document layout...")
                
                try:
                    logger.info(f"📐 Running layout analysis for {analysis_id}")
                    layout_result = await self.layout_analyzer.analyze_layout(document_path, request)
                    
                    result.layout_analysis = LayoutAnalysisResult(
                        layout_structure=layout_result.get('layout_structure', {}),
                        page_layouts=layout_result.get('page_layouts', []),
                        processing_warnings=layout_result.get('processing_warnings', []),
                        analysis_metadata=layout_result.get('analysis_metadata', {})
                    )
                    processing_warnings.extend(layout_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Layout analysis failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 3. Revision Tracking
            if request.analysis_types.get("revision_tracking", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Tracking revisions...")
                
                try:
                    logger.info(f"🔄 Running revision tracking for {analysis_id}")
                    revision_result = await self.revision_tracker.track_revisions(document_path, request)
                    
                    result.revision_tracking = RevisionTrackingResult(
                        revision_history=revision_result.get('revision_history', {}),
                        processing_warnings=revision_result.get('processing_warnings', []),
                        analysis_metadata=revision_result.get('analysis_metadata', {})
                    )
                    processing_warnings.extend(revision_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Revision tracking failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 4. Assembly Detection
            if request.analysis_types.get("assembly_detection", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Detecting assemblies and components...")
                
                try:
                    logger.info(f"🔧 Running assembly detection for {analysis_id}")
                    assembly_result = await self.assembly_detector.detect_assemblies(document_path, request)
                    
                    result.assembly_detection = AssemblyDetectionResult(
                        assembly_analysis=assembly_result.get('assembly_analysis', {}),
                        processing_warnings=assembly_result.get('processing_warnings', []),
                        analysis_metadata=assembly_result.get('analysis_metadata', {})
                    )
                    processing_warnings.extend(assembly_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Assembly detection failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 5. Enhanced Table Extraction
            if request.analysis_types.get("extract_tables", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Extracting tables...")
                
                try:
                    logger.info(f"📊 Running enhanced table extraction for {analysis_id}")
                    table_result = await self.table_extractor.extract_tables(document_path, request)
                    
                    # Add table results to core results
                    if not result.core_results:
                        result.core_results = {}
                    result.core_results['tables'] = table_result
                    processing_warnings.extend(table_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Table extraction failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 6. Technical Specifications Extraction
            if request.analysis_types.get("technical_specs", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Extracting technical specifications...")
                
                try:
                    logger.info(f"📐 Running technical specs extraction for {analysis_id}")
                    tech_specs_result = await self.technical_specs_extractor.extract_technical_specs(document_path, request)
                    
                    # Add tech specs to core results
                    if not result.core_results:
                        result.core_results = {}
                    result.core_results['technical_specs'] = tech_specs_result
                    processing_warnings.extend(tech_specs_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Technical specs extraction failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 7. Dimensional Analysis
            if request.analysis_types.get("dimensional_analysis", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Analyzing dimensions and tolerances...")
                
                try:
                    logger.info(f"📏 Running dimensional analysis for {analysis_id}")
                    dimensional_result = await self.dimensional_analyzer.analyze_dimensions(document_path, request)
                    
                    # Add dimensional analysis to core results
                    if not result.core_results:
                        result.core_results = {}
                    result.core_results['dimensional_analysis'] = dimensional_result
                    processing_warnings.extend(dimensional_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Dimensional analysis failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 8. Vector Graphics Analysis
            if request.analysis_types.get("vector_graphics", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Analyzing vector graphics and CAD symbols...")
                
                try:
                    logger.info(f"🎨 Running vector graphics analysis for {analysis_id}")
                    # For vector graphics, we need image data from the document
                    # This is a simplified approach - in practice, you'd extract images from PDF
                    vector_result = await self._run_vector_graphics_analysis(document_path, request)
                    
                    # Add vector graphics to core results
                    if not result.core_results:
                        result.core_results = {}
                    result.core_results['vector_graphics'] = vector_result
                    processing_warnings.extend(vector_result.get('processing_warnings', []))
                    
                except Exception as e:
                    error_msg = f"Vector graphics analysis failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 9. AI Consensus Analysis
            if request.analysis_types.get("ai_consensus", False):
                current_step += 1
                self._update_progress(analysis_id, current_step / total_steps, "Running AI consensus analysis...")
                
                try:
                    logger.info(f"🤖 Running AI consensus analysis for {analysis_id}")
                    ai_consensus = await self._run_ai_consensus(result, request)
                    result.ai_consensus = ai_consensus
                    
                except Exception as e:
                    error_msg = f"AI consensus analysis failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 10. Final Processing and Quality Validation
            current_step += 1
            self._update_progress(analysis_id, current_step / total_steps, "Finalizing results...")
            
            # Generate composite results
            result.composite_results = self._generate_composite_results(result)
            
            # Quality validation if enabled
            if request.analysis_types.get("quality_validation", False):
                try:
                    result.quality_validation = await self._run_quality_validation(result, request)
                except Exception as e:
                    error_msg = f"Quality validation failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # Finalize result
            processing_time = time.time() - start_time
            result.status = "completed"
            result.processing_time = processing_time
            result.processing_warnings = processing_warnings
            result.metadata = {
                'analysis_id': analysis_id,
                'processing_time_seconds': processing_time,
                'total_warnings': len(processing_warnings),
                'extractors_used': [k for k, v in request.analysis_types.items() if v],
                'document_url': request.file_url,
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
            # Clean up
            await self._cleanup_document(document_path)
            self._update_progress(analysis_id, 1.0, "Completed")
            
            logger.info(f"✅ Enhanced analysis {analysis_id} completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"❌ Enhanced analysis {analysis_id} failed: {e}")
            
            # Clean up on error
            if 'document_path' in locals():
                await self._cleanup_document(document_path)
            
            processing_time = time.time() - start_time
            return EnhancedAnalysisResult(
                analysis_id=analysis_id,
                status="failed",
                processing_time=processing_time,
                processing_warnings=[f"Analysis failed: {str(e)}"],
                metadata={'error': str(e)}
            )
        
        finally:
            # Clean up analysis tracking
            if analysis_id in self.active_analyses:
                del self.active_analyses[analysis_id]
    
    async def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an analysis"""
        return self.active_analyses.get(analysis_id)
    
    def get_active_analyses(self) -> List[str]:
        """Get list of active analysis IDs"""
        return list(self.active_analyses.keys())
    
    async def _download_document(self, file_url: str) -> str:
        """Download document from URL to temporary file"""
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(file_url)
            response.raise_for_status()
            
            # Create temporary file
            temp_file = os.path.join(
                tempfile.gettempdir(), 
                f"enhanced_doc_{uuid.uuid4().hex}.pdf"
            )
            
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"📥 Downloaded document to {temp_file}")
            return temp_file
    
    async def _cleanup_document(self, document_path: str):
        """Clean up temporary document file"""
        try:
            if os.path.exists(document_path):
                os.unlink(document_path)
                logger.debug(f"🗑️ Cleaned up {document_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {document_path}: {e}")
    
    def _update_progress(self, analysis_id: str, progress: float, step: str):
        """Update analysis progress"""
        if analysis_id in self.active_analyses:
            self.active_analyses[analysis_id].update({
                'progress': progress,
                'current_step': step
            })
    
    async def _run_ai_consensus(self, result: EnhancedAnalysisResult, request: AnalysisRequest) -> Dict[str, Any]:
        """Run AI consensus analysis on all extracted data"""
        try:
            # Prepare combined context from all extractors
            context_parts = []
            
            if result.stamp_detection:
                context_parts.append(f"Stamps detected: {len(result.stamp_detection.stamps)}")
                
            if result.layout_analysis:
                layout_elements = len(result.layout_analysis.layout_structure.get('elements', []))
                context_parts.append(f"Layout elements: {layout_elements}")
                
            if result.revision_tracking:
                revisions = result.revision_tracking.revision_history.get('all_revisions', [])
                context_parts.append(f"Revisions found: {len(revisions)}")
                
            if result.assembly_detection:
                components = len(result.assembly_detection.assembly_analysis.get('components', []))
                context_parts.append(f"Components detected: {components}")
            
            context = "Document Analysis Summary:\\n" + "\\n".join(context_parts)
            
            # Use free AI services for consensus
            ai_result = await free_services.enhance_with_ai(
                text=context,
                task="document_analysis_consensus"
            )
            
            return {
                'consensus_available': ai_result is not None,
                'consensus_summary': ai_result.get('response', '') if ai_result else None,
                'service_used': ai_result.get('service_name', 'unknown') if ai_result else None,
                'confidence': 0.8 if ai_result else 0.0
            }
            
        except Exception as e:
            logger.warning(f"AI consensus failed: {e}")
            return {
                'consensus_available': False,
                'error': str(e)
            }
    
    async def _run_quality_validation(self, result: EnhancedAnalysisResult, request: AnalysisRequest) -> Dict[str, Any]:
        """Run quality validation on analysis results"""
        try:
            quality_metrics = {
                'overall_confidence': 0.0,
                'data_completeness': 0.0,
                'consistency_score': 0.0,
                'validation_warnings': []
            }
            
            confidence_scores = []
            completeness_scores = []
            
            # Validate stamp detection results
            if result.stamp_detection:
                stamps = result.stamp_detection.stamps
                if stamps:
                    avg_confidence = sum(s.get('confidence', 0) for s in stamps) / len(stamps)
                    confidence_scores.append(avg_confidence)
                    completeness_scores.append(1.0 if len(stamps) > 0 else 0.0)
                else:
                    quality_metrics['validation_warnings'].append("No stamps detected")
            
            # Validate layout analysis results
            if result.layout_analysis:
                elements = result.layout_analysis.layout_structure.get('elements', [])
                if elements:
                    completeness_scores.append(1.0)
                else:
                    quality_metrics['validation_warnings'].append("No layout elements detected")
            
            # Validate revision tracking results
            if result.revision_tracking:
                revisions = result.revision_tracking.revision_history.get('all_revisions', [])
                if revisions:
                    completeness_scores.append(1.0)
                else:
                    quality_metrics['validation_warnings'].append("No revisions detected")
            
            # Validate assembly detection results
            if result.assembly_detection:
                components = result.assembly_detection.assembly_analysis.get('components', [])
                if components:
                    completeness_scores.append(1.0)
                else:
                    quality_metrics['validation_warnings'].append("No components detected")
            
            # Calculate overall metrics
            if confidence_scores:
                quality_metrics['overall_confidence'] = sum(confidence_scores) / len(confidence_scores)
            
            if completeness_scores:
                quality_metrics['data_completeness'] = sum(completeness_scores) / len(completeness_scores)
            
            # Simple consistency score (could be more sophisticated)
            quality_metrics['consistency_score'] = 0.8  # Placeholder
            
            return quality_metrics
            
        except Exception as e:
            logger.warning(f"Quality validation failed: {e}")
            return {
                'validation_available': False,
                'error': str(e)
            }
    
    def _generate_composite_results(self, result: EnhancedAnalysisResult) -> Dict[str, Any]:
        """Generate composite insights from all analysis results"""
        composite = {
            'document_type': 'engineering_document',
            'total_pages': 0,
            'elements_summary': {
                'stamps_count': 0,
                'layout_elements_count': 0,
                'revisions_count': 0,
                'components_count': 0,
                'assemblies_count': 0
            },
            'confidence_summary': {
                'overall_confidence': 0.0,
                'high_confidence_items': 0,
                'low_confidence_items': 0
            },
            'insights': []
        }
        
        # Aggregate counts from all extractors
        if result.stamp_detection:
            composite['elements_summary']['stamps_count'] = len(result.stamp_detection.stamps)
            if result.stamp_detection.stamps:
                composite['insights'].append(f"Found {len(result.stamp_detection.stamps)} engineering stamps")
        
        if result.layout_analysis:
            elements = result.layout_analysis.layout_structure.get('elements', [])
            composite['elements_summary']['layout_elements_count'] = len(elements)
            if elements:
                composite['insights'].append(f"Identified {len(elements)} layout elements")
        
        if result.revision_tracking:
            revisions = result.revision_tracking.revision_history.get('all_revisions', [])
            composite['elements_summary']['revisions_count'] = len(revisions)
            if revisions:
                current_rev = result.revision_tracking.revision_history.get('current_revision')
                composite['insights'].append(f"Document has {len(revisions)} revisions, current: {current_rev}")
        
        if result.assembly_detection:
            components = result.assembly_detection.assembly_analysis.get('components', [])
            assemblies = result.assembly_detection.assembly_analysis.get('assemblies', [])
            composite['elements_summary']['components_count'] = len(components)
            composite['elements_summary']['assemblies_count'] = len(assemblies)
            if components:
                composite['insights'].append(f"Detected {len(components)} components in {len(assemblies)} assemblies")
        
        # Determine document type based on content
        if composite['elements_summary']['components_count'] > 10:
            composite['document_type'] = 'technical_drawing_with_bom'
        elif composite['elements_summary']['revisions_count'] > 3:
            composite['document_type'] = 'engineering_specification'
        elif composite['elements_summary']['stamps_count'] > 0:
            composite['document_type'] = 'approved_engineering_document'
        
        return composite
    
    async def _run_vector_graphics_analysis(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """Run vector graphics analysis on document images"""
        try:
            import fitz  # PyMuPDF for PDF processing
            
            processing_warnings = []
            vector_results = {
                'total_symbols': 0,
                'total_shapes': 0,
                'symbols_by_page': [],
                'shapes_by_page': [],
                'drawing_types': {},
                'symbol_classifications': {},
                'shape_classifications': {},
                'complexity_scores': [],
                'confidence_scores': [],
                'processing_warnings': processing_warnings
            }
            
            # Open PDF document
            doc = fitz.open(document_path)
            
            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    
                    # Convert page to image
                    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    
                    # Convert to PIL Image for extractor
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Run vector graphics extraction
                    result = self.vector_graphics_extractor.extract(
                        image_data=img,
                        text_content="",  # Could extract text from page if needed
                        ai_enhancement=request.ai_enhancement
                    )
                    
                    # Aggregate results
                    vector_results['total_symbols'] += result.total_symbols
                    vector_results['total_shapes'] += result.total_shapes
                    
                    vector_results['symbols_by_page'].append({
                        'page': page_num + 1,
                        'symbols': [{
                            'type': s.symbol_type,
                            'class': s.symbol_class,
                            'confidence': s.confidence,
                            'coordinates': s.coordinates,
                            'standard': s.standard_reference,
                            'description': s.description
                        } for s in result.symbols]
                    })
                    
                    vector_results['shapes_by_page'].append({
                        'page': page_num + 1,
                        'shapes': [{
                            'type': s.shape_type,
                            'dimensions': s.dimensions,
                            'coordinates': s.coordinates,
                            'properties': s.properties
                        } for s in result.shapes]
                    })
                    
                    # Merge classifications
                    for symbol_type, count in result.symbol_classifications.items():
                        vector_results['symbol_classifications'][symbol_type] = \
                            vector_results['symbol_classifications'].get(symbol_type, 0) + count
                    
                    for shape_type, count in result.shape_classifications.items():
                        vector_results['shape_classifications'][shape_type] = \
                            vector_results['shape_classifications'].get(shape_type, 0) + count
                    
                    if result.drawing_type:
                        vector_results['drawing_types'][result.drawing_type] = \
                            vector_results['drawing_types'].get(result.drawing_type, 0) + 1
                    
                    vector_results['complexity_scores'].append(result.complexity_score)
                    vector_results['confidence_scores'].append(result.confidence)
                    
                    if result.processing_notes:
                        processing_warnings.extend([
                            f"Page {page_num + 1}: {note}" for note in result.processing_notes
                        ])
                    
                except Exception as e:
                    error_msg = f"Vector analysis failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # Calculate overall metrics
            if vector_results['complexity_scores']:
                vector_results['average_complexity'] = \
                    sum(vector_results['complexity_scores']) / len(vector_results['complexity_scores'])
            else:
                vector_results['average_complexity'] = 0.0
                
            if vector_results['confidence_scores']:
                vector_results['average_confidence'] = \
                    sum(vector_results['confidence_scores']) / len(vector_results['confidence_scores'])
            else:
                vector_results['average_confidence'] = 0.0
            
            # Determine dominant drawing type
            if vector_results['drawing_types']:
                dominant_type = max(vector_results['drawing_types'].items(), key=lambda x: x[1])
                vector_results['dominant_drawing_type'] = dominant_type[0]
            else:
                vector_results['dominant_drawing_type'] = 'unknown'
            
            # Add summary
            vector_results['summary'] = {
                'total_pages_analyzed': len(doc),
                'pages_with_symbols': len([p for p in vector_results['symbols_by_page'] if p['symbols']]),
                'pages_with_shapes': len([p for p in vector_results['shapes_by_page'] if p['shapes']]),
                'most_common_symbol': max(vector_results['symbol_classifications'].items(), 
                                        key=lambda x: x[1])[0] if vector_results['symbol_classifications'] else None,
                'most_common_shape': max(vector_results['shape_classifications'].items(), 
                                       key=lambda x: x[1])[0] if vector_results['shape_classifications'] else None,
            }
            
            logger.info(f"Vector graphics analysis completed: {vector_results['total_symbols']} symbols, {vector_results['total_shapes']} shapes")
            return vector_results
            
        except ImportError:
            error_msg = "PyMuPDF not available for vector graphics analysis"
            logger.warning(error_msg)
            return {
                'vector_graphics_available': False,
                'processing_warnings': [error_msg]
            }
        except Exception as e:
            error_msg = f"Vector graphics analysis failed: {str(e)}"
            logger.error(error_msg)
            return {
                'vector_graphics_available': False,
                'processing_warnings': [error_msg]
            }
