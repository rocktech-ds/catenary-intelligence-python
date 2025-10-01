"""
Advanced Dimensional Analysis Extractor for Engineering Documents

This module provides comprehensive dimensional analysis including:
- Geometric Dimensioning and Tolerancing (GD&T) interpretation
- Coordinate system detection and transformation
- Measurement extraction and validation
- Scale analysis and conversion
- Tolerance stack-up calculations
- Dimensional relationships mapping

Optimized for VPS environments using free services and AI enhancement.
"""

import logging
import re
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
from collections import defaultdict

from ..models.analysis_models import AnalysisRequest, BoundingBox

logger = logging.getLogger(__name__)

@dataclass
class Dimension:
    """Represents a single dimension with tolerance information"""
    id: str
    dimension_type: str  # linear, angular, radial, diametral
    nominal_value: float
    unit: str
    tolerance_type: str  # bilateral, unilateral, geometric
    upper_tolerance: Optional[float] = None
    lower_tolerance: Optional[float] = None
    gdt_symbol: Optional[str] = None  # GD&T symbol
    datum_reference: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class GeometricTolerance:
    """Represents GD&T (Geometric Dimensioning and Tolerancing) information"""
    id: str
    symbol: str  # ⌖, ⟂, ∥, ⌒, ⌓, etc.
    symbol_name: str  # Position, Perpendicularity, Parallelism, etc.
    tolerance_value: float
    datum_system: List[str] = None  # Primary, secondary, tertiary datums
    material_condition: Optional[str] = None  # MMC, LMC, RFS
    feature_type: str = "surface"  # surface, axis, plane
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class CoordinateSystem:
    """Represents coordinate system information"""
    id: str
    system_type: str  # cartesian, polar, cylindrical
    origin_point: Optional[Tuple[float, float]] = None
    rotation_angle: Optional[float] = None
    scale_factor: Optional[float] = None
    units: str = "mm"
    datum_features: List[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class ScaleInformation:
    """Represents drawing scale information"""
    id: str
    scale_ratio: str  # "1:50", "2:1", etc.
    scale_factor: float  # numerical factor
    scale_type: str  # reduction, enlargement, full_size
    applies_to: str  # entire_drawing, specific_view
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class DimensionalRelationship:
    """Represents relationships between dimensions"""
    id: str
    relationship_type: str  # parallel, perpendicular, concentric, reference
    primary_dimension: str  # ID of first dimension
    secondary_dimension: str  # ID of second dimension
    constraint_type: Optional[str] = None
    offset_value: Optional[float] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class DimensionalAnalysis:
    """Complete dimensional analysis results"""
    dimensions: List[Dimension] = None
    geometric_tolerances: List[GeometricTolerance] = None
    coordinate_systems: List[CoordinateSystem] = None
    scale_information: List[ScaleInformation] = None
    dimensional_relationships: List[DimensionalRelationship] = None
    units_summary: Dict[str, int] = None
    tolerance_summary: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

class DimensionalAnalyzer:
    """Advanced dimensional analysis extractor"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # GD&T symbols mapping
        self.gdt_symbols = {
            # Form tolerances
            '⌖': {'name': 'Position', 'type': 'location'},
            '○': {'name': 'Concentricity', 'type': 'location'},
            '◎': {'name': 'Circular Runout', 'type': 'runout'},
            '◉': {'name': 'Total Runout', 'type': 'runout'},
            '—': {'name': 'Straightness', 'type': 'form'},
            '○': {'name': 'Flatness', 'type': 'form'},
            '◯': {'name': 'Circularity', 'type': 'form'},
            '⌒': {'name': 'Cylindricity', 'type': 'form'},
            
            # Orientation tolerances
            '⟂': {'name': 'Perpendicularity', 'type': 'orientation'},
            '∥': {'name': 'Parallelism', 'type': 'orientation'},
            '∠': {'name': 'Angularity', 'type': 'orientation'},
            
            # Profile tolerances
            '⌓': {'name': 'Profile of Line', 'type': 'profile'},
            '⌢': {'name': 'Profile of Surface', 'type': 'profile'},
            
            # Text alternatives for common GD&T symbols
            'POS': {'name': 'Position', 'type': 'location'},
            'PERP': {'name': 'Perpendicularity', 'type': 'orientation'},
            'PARA': {'name': 'Parallelism', 'type': 'orientation'},
            'FLAT': {'name': 'Flatness', 'type': 'form'},
            'ROUND': {'name': 'Circularity', 'type': 'form'},
            'CYL': {'name': 'Cylindricity', 'type': 'form'},
        }
        
        # Dimensional analysis patterns
        self.dimensional_patterns = {
            'linear_dimensions': [
                r'(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?\s*[±]\s*(\d+(?:[,.]\d+)?)',
                r'(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?\s*\+(\d+(?:[,.]\d+)?)\s*-(\d+(?:[,.]\d+)?)',
                r'(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?(?:\s*NOM)?',
                r'(Ø|φ|DIA)\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(R)\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',  # Radius
            ],
            'angular_dimensions': [
                r'(\d+(?:[,.]\d+)?)\s*°\s*(\d+(?:[,.]\d+)?)\s*\'?\s*(\d+(?:[,.]\d+)?)\s*\"?',  # DMS
                r'(\d+(?:[,.]\d+)?)\s*°',  # Decimal degrees
                r'(\d+(?:[,.]\d+)?)\s*(rad|RAD)',  # Radians
            ],
            'coordinate_points': [
                r'[XY]\s*[=:]?\s*(\d+(?:[,.]\d+)?)',
                r'\(\s*(\d+(?:[,.]\d+)?)\s*[,;]\s*(\d+(?:[,.]\d+)?)\s*\)',
                r'COORD[ENADA]*[:\s]*(\d+(?:[,.]\d+)?)[,\s]+(\d+(?:[,.]\d+)?)',
            ],
            'scale_patterns': [
                r'ESCALA[:\s]+1[:\s]*(\d+)',
                r'SCALE[:\s]+1[:\s]*(\d+)',
                r'ESC[:\.\s]+1[:\s]*(\d+)',
                r'(\d+)[:\s]*1',  # Enlargement scales
                r'FULL\s+SIZE|TAMANHO\s+REAL|1:1',
            ],
            'tolerance_grades': [
                r'\b(IT\d{1,2}|H\d{1,2}|h\d{1,2}|G\d{1,2}|g\d{1,2}|F\d{1,2}|f\d{1,2})\b',
                r'\b(js\d{1,2}|JS\d{1,2}|k\d{1,2}|K\d{1,2}|m\d{1,2}|M\d{1,2})\b',
            ],
            'surface_finish': [
                r'Ra\s*(\d+(?:[,.]\d+)?)\s*(μm|µm|microns?)',
                r'Rz\s*(\d+(?:[,.]\d+)?)\s*(μm|µm|microns?)',
                r'N\s*(\d+)',  # Surface roughness class
            ],
            'datum_references': [
                r'\|\s*([A-Z])\s*\|',  # |A|
                r'DATUM[:\s]*([A-Z])',
                r'REF[:\s]*([A-Z])',
            ]
        }
    
    async def analyze_dimensions(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Comprehensive dimensional analysis of engineering document
        """
        try:
            # Load document
            import fitz  # PyMuPDF
            doc = fitz.open(document_path)
            
            all_dimensions = []
            all_geometric_tolerances = []
            all_coordinate_systems = []
            all_scale_info = []
            all_relationships = []
            units_counter = defaultdict(int)
            processing_warnings = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Extract text for analysis
                    text_dict = page.get_text("dict")
                    page_text = page.get_text()
                    
                    # 1. Extract linear and angular dimensions
                    page_dimensions = await self._extract_dimensions(page_text, page_num)
                    all_dimensions.extend(page_dimensions)
                    
                    # 2. Extract GD&T information
                    page_gdt = await self._extract_geometric_tolerances(page_text, page_num)
                    all_geometric_tolerances.extend(page_gdt)
                    
                    # 3. Detect coordinate systems
                    page_coords = await self._detect_coordinate_systems(page_text, text_dict, page_num)
                    all_coordinate_systems.extend(page_coords)
                    
                    # 4. Extract scale information
                    page_scales = await self._extract_scale_information(page_text, page_num)
                    all_scale_info.extend(page_scales)
                    
                    # 5. Analyze dimensional relationships
                    page_relationships = await self._analyze_dimensional_relationships(
                        all_dimensions, page_text, page_num
                    )
                    all_relationships.extend(page_relationships)
                    
                    # 6. Count units usage
                    page_units = self._count_dimensional_units(page_text)
                    for unit, count in page_units.items():
                        units_counter[unit] += count
                    
                except Exception as e:
                    error_msg = f"Dimensional analysis failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # 7. AI enhancement (if enabled)
            if request.use_ai_enhancement:
                try:
                    all_dimensions = await self._enhance_dimensions_with_ai(all_dimensions, request)
                    all_geometric_tolerances = await self._enhance_gdt_with_ai(all_geometric_tolerances, request)
                except Exception as e:
                    error_msg = f"AI enhancement failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 8. Calculate tolerance summary
            tolerance_summary = self._calculate_tolerance_summary(all_dimensions, all_geometric_tolerances)
            
            # 9. Create comprehensive analysis
            dimensional_analysis = DimensionalAnalysis(
                dimensions=all_dimensions,
                geometric_tolerances=all_geometric_tolerances,
                coordinate_systems=all_coordinate_systems,
                scale_information=all_scale_info,
                dimensional_relationships=all_relationships,
                units_summary=dict(units_counter),
                tolerance_summary=tolerance_summary,
                metadata={
                    'total_dimensions': len(all_dimensions),
                    'total_gdt_features': len(all_geometric_tolerances),
                    'coordinate_systems_found': len(all_coordinate_systems),
                    'scales_detected': len(all_scale_info),
                    'dimensional_relationships': len(all_relationships),
                    'processing_warnings_count': len(processing_warnings)
                }
            )
            
            return {
                'dimensional_analysis': asdict(dimensional_analysis),
                'processing_warnings': processing_warnings,
                'analysis_metadata': {
                    'extraction_methods': ['pattern_matching', 'gdt_recognition', 'coordinate_detection', 'ai_enhancement'],
                    'accuracy_estimates': self._estimate_accuracy(dimensional_analysis),
                    'completeness_score': self._calculate_completeness_score(dimensional_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Dimensional analysis failed: {e}")
            return {'error': str(e), 'dimensional_analysis': None}
    
    async def _extract_dimensions(self, page_text: str, page_num: int) -> List[Dimension]:
        """Extract linear and angular dimensions from text"""
        dimensions = []
        
        # Extract linear dimensions
        for pattern in self.dimensional_patterns['linear_dimensions']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    groups = match.groups()
                    
                    if groups[0]:  # Has a numerical value
                        value_str = groups[0].replace(',', '.')
                        nominal_value = float(value_str)
                        
                        # Determine dimension type from context
                        dimension_type = self._classify_dimension_type(match.group(0), page_text, match.start())
                        
                        # Extract unit (default to mm)
                        unit = groups[1] if len(groups) > 1 and groups[1] else 'mm'
                        
                        # Extract tolerance information
                        tolerance_info = self._extract_tolerance_from_match(groups)
                        
                        dimension = Dimension(
                            id=str(uuid.uuid4()),
                            dimension_type=dimension_type,
                            nominal_value=nominal_value,
                            unit=unit,
                            tolerance_type=tolerance_info['type'],
                            upper_tolerance=tolerance_info.get('upper'),
                            lower_tolerance=tolerance_info.get('lower'),
                            confidence=0.8,
                            metadata={
                                'detection_method': 'linear_pattern',
                                'raw_match': match.group(0),
                                'page': page_num
                            }
                        )
                        
                        dimensions.append(dimension)
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse dimension: {match.group(0)} - {e}")
        
        # Extract angular dimensions
        for pattern in self.dimensional_patterns['angular_dimensions']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    groups = match.groups()
                    
                    if '°' in match.group(0):
                        # Convert to decimal degrees
                        degrees = float(groups[0].replace(',', '.'))
                        
                        if len(groups) >= 2 and groups[1]:  # Minutes
                            degrees += float(groups[1].replace(',', '.')) / 60
                        
                        if len(groups) >= 3 and groups[2]:  # Seconds
                            degrees += float(groups[2].replace(',', '.')) / 3600
                        
                        dimension = Dimension(
                            id=str(uuid.uuid4()),
                            dimension_type='angular',
                            nominal_value=degrees,
                            unit='degrees',
                            tolerance_type='none',
                            confidence=0.8,
                            metadata={
                                'detection_method': 'angular_pattern',
                                'raw_match': match.group(0),
                                'page': page_num
                            }
                        )
                        
                        dimensions.append(dimension)
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse angular dimension: {match.group(0)} - {e}")
        
        return dimensions
    
    def _classify_dimension_type(self, match_text: str, context: str, position: int) -> str:
        """Classify the type of dimension based on context"""
        match_lower = match_text.lower()
        
        # Check for specific indicators
        if any(indicator in match_lower for indicator in ['ø', 'φ', 'dia']):
            return 'diametral'
        elif 'r' == match_lower[0] or 'radius' in match_lower:
            return 'radial'
        elif '°' in match_text:
            return 'angular'
        
        # Check surrounding context
        context_window = context[max(0, position-50):position+100].lower()
        
        if any(word in context_window for word in ['altura', 'height', 'h=']):
            return 'height'
        elif any(word in context_window for word in ['largura', 'width', 'w=']):
            return 'width'
        elif any(word in context_window for word in ['comprimento', 'length', 'l=']):
            return 'length'
        elif any(word in context_window for word in ['espessura', 'thickness', 't=']):
            return 'thickness'
        else:
            return 'linear'
    
    def _extract_tolerance_from_match(self, groups: tuple) -> Dict[str, Any]:
        """Extract tolerance information from regex match groups"""
        tolerance_info = {'type': 'none'}
        
        if len(groups) >= 3 and groups[2]:  # Bilateral tolerance ±
            tolerance_value = float(groups[2].replace(',', '.'))
            tolerance_info = {
                'type': 'bilateral',
                'upper': tolerance_value,
                'lower': tolerance_value
            }
        elif len(groups) >= 4 and groups[2] and groups[3]:  # Unilateral tolerance +/-
            upper_tol = float(groups[2].replace(',', '.'))
            lower_tol = float(groups[3].replace(',', '.'))
            tolerance_info = {
                'type': 'unilateral',
                'upper': upper_tol,
                'lower': lower_tol
            }
        
        return tolerance_info
    
    async def _extract_geometric_tolerances(self, page_text: str, page_num: int) -> List[GeometricTolerance]:
        """Extract GD&T (Geometric Dimensioning and Tolerancing) information"""
        geometric_tolerances = []
        
        # Look for GD&T symbols and associated information
        for symbol, info in self.gdt_symbols.items():
            # Create pattern to find symbol with tolerance value
            pattern = rf'{re.escape(symbol)}\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?'
            matches = re.finditer(pattern, page_text)
            
            for match in matches:
                try:
                    tolerance_value = float(match.group(1).replace(',', '.'))
                    unit = match.group(2) if match.group(2) else 'mm'
                    
                    # Extract datum system from surrounding context
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(page_text), match.end() + 100)
                    context = page_text[context_start:context_end]
                    
                    datum_system = self._extract_datum_system(context)
                    material_condition = self._extract_material_condition(context)
                    
                    gdt = GeometricTolerance(
                        id=str(uuid.uuid4()),
                        symbol=symbol,
                        symbol_name=info['name'],
                        tolerance_value=tolerance_value,
                        datum_system=datum_system,
                        material_condition=material_condition,
                        feature_type=info['type'],
                        confidence=0.8,
                        metadata={
                            'detection_method': 'gdt_symbol',
                            'context': context[:200],
                            'page': page_num
                        }
                    )
                    
                    geometric_tolerances.append(gdt)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse GD&T: {match.group(0)} - {e}")
        
        return geometric_tolerances
    
    def _extract_datum_system(self, context: str) -> List[str]:
        """Extract datum references from context"""
        datums = []
        
        for pattern in self.dimensional_patterns['datum_references']:
            matches = re.findall(pattern, context, re.IGNORECASE)
            datums.extend(matches)
        
        # Remove duplicates while preserving order
        unique_datums = []
        seen = set()
        for datum in datums:
            if datum not in seen:
                unique_datums.append(datum)
                seen.add(datum)
        
        return unique_datums[:3]  # Primary, secondary, tertiary
    
    def _extract_material_condition(self, context: str) -> Optional[str]:
        """Extract material condition (MMC, LMC, RFS) from context"""
        context_upper = context.upper()
        
        if 'MMC' in context_upper or 'MAXIMUM MATERIAL CONDITION' in context_upper:
            return 'MMC'
        elif 'LMC' in context_upper or 'LEAST MATERIAL CONDITION' in context_upper:
            return 'LMC'
        elif 'RFS' in context_upper or 'REGARDLESS OF FEATURE SIZE' in context_upper:
            return 'RFS'
        
        return None
    
    async def _detect_coordinate_systems(self, page_text: str, text_dict: Dict, page_num: int) -> List[CoordinateSystem]:
        """Detect coordinate systems in the document"""
        coordinate_systems = []
        
        # Look for coordinate points to infer coordinate systems
        coordinate_points = []
        
        for pattern in self.dimensional_patterns['coordinate_points']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    groups = match.groups()
                    
                    if len(groups) >= 2:  # X, Y coordinates
                        x = float(groups[0].replace(',', '.'))
                        y = float(groups[1].replace(',', '.'))
                        coordinate_points.append((x, y))
                    elif len(groups) == 1:  # Single coordinate
                        coord = float(groups[0].replace(',', '.'))
                        # Determine if X or Y based on preceding text
                        preceding_text = page_text[max(0, match.start()-20):match.start()]
                        if 'X' in preceding_text.upper():
                            coordinate_points.append((coord, None))
                        elif 'Y' in preceding_text.upper():
                            coordinate_points.append((None, coord))
                            
                except (ValueError, IndexError):
                    continue
        
        # If we found coordinate points, create a coordinate system
        if coordinate_points:
            # Find potential origin (point closest to 0,0)
            origin_candidates = [(x, y) for x, y in coordinate_points if x is not None and y is not None]
            
            if origin_candidates:
                origin = min(origin_candidates, key=lambda p: math.sqrt(p[0]**2 + p[1]**2))
                
                coord_system = CoordinateSystem(
                    id=str(uuid.uuid4()),
                    system_type='cartesian',
                    origin_point=origin,
                    units='mm',  # Default assumption
                    confidence=0.7,
                    metadata={
                        'detection_method': 'coordinate_inference',
                        'total_points_found': len(coordinate_points),
                        'page': page_num
                    }
                )
                
                coordinate_systems.append(coord_system)
        
        return coordinate_systems
    
    async def _extract_scale_information(self, page_text: str, page_num: int) -> List[ScaleInformation]:
        """Extract drawing scale information"""
        scale_info = []
        
        for pattern in self.dimensional_patterns['scale_patterns']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    if '1:1' in match.group(0) or 'FULL' in match.group(0).upper():
                        scale_ratio = '1:1'
                        scale_factor = 1.0
                        scale_type = 'full_size'
                    elif len(match.groups()) >= 1 and match.group(1):
                        scale_value = int(match.group(1))
                        
                        if ':1' in match.group(0):  # Enlargement (e.g., 2:1)
                            scale_ratio = f'{scale_value}:1'
                            scale_factor = scale_value
                            scale_type = 'enlargement'
                        else:  # Reduction (e.g., 1:50)
                            scale_ratio = f'1:{scale_value}'
                            scale_factor = 1.0 / scale_value
                            scale_type = 'reduction'
                        
                        scale = ScaleInformation(
                            id=str(uuid.uuid4()),
                            scale_ratio=scale_ratio,
                            scale_factor=scale_factor,
                            scale_type=scale_type,
                            applies_to='entire_drawing',  # Could be enhanced with context analysis
                            confidence=0.9,
                            metadata={
                                'detection_method': 'scale_pattern',
                                'raw_match': match.group(0),
                                'page': page_num
                            }
                        )
                        
                        scale_info.append(scale)
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse scale: {match.group(0)} - {e}")
        
        return scale_info
    
    async def _analyze_dimensional_relationships(self, dimensions: List[Dimension], 
                                               page_text: str, page_num: int) -> List[DimensionalRelationship]:
        """Analyze relationships between dimensions"""
        relationships = []
        
        # Look for explicit relationship indicators in text
        relationship_patterns = [
            r'(parallel|paralelo|∥)\s+to\s+([A-Z0-9\-_]+)',
            r'(perpendicular|perpendicular|⟂)\s+to\s+([A-Z0-9\-_]+)',
            r'(concentric|concêntrico)\s+with\s+([A-Z0-9\-_]+)',
            r'reference\s+([A-Z0-9\-_]+)',
        ]
        
        for pattern in relationship_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                relationship_type = match.group(1).lower()
                reference_id = match.group(2) if len(match.groups()) > 1 else None
                
                # Create relationship (simplified - would need more sophisticated matching)
                if dimensions:  # If we have dimensions to relate
                    relationship = DimensionalRelationship(
                        id=str(uuid.uuid4()),
                        relationship_type=relationship_type,
                        primary_dimension=dimensions[0].id,  # Simplified
                        secondary_dimension=reference_id or 'unknown',
                        confidence=0.6,
                        metadata={
                            'detection_method': 'relationship_pattern',
                            'raw_match': match.group(0),
                            'page': page_num
                        }
                    )
                    
                    relationships.append(relationship)
        
        return relationships
    
    def _count_dimensional_units(self, text: str) -> Dict[str, int]:
        """Count usage of dimensional units in text"""
        unit_counts = {}
        
        dimensional_units = [
            'mm', 'cm', 'm', 'km', 'in', 'ft', 'yd',
            '°', 'deg', 'degrees', 'rad', 'radians',
            'μm', 'µm', 'microns', 'mil'
        ]
        
        for unit in dimensional_units:
            pattern = rf'\b{re.escape(unit)}\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                unit_counts[unit] = len(matches)
        
        return unit_counts
    
    async def _enhance_dimensions_with_ai(self, dimensions: List[Dimension], 
                                        request: AnalysisRequest) -> List[Dimension]:
        """Enhance dimensional information with AI analysis"""
        enhanced_dimensions = []
        
        for dimension in dimensions[:15]:  # Limit for performance
            try:
                context = f"""
                Dimensional Analysis:
                Type: {dimension.dimension_type}
                Value: {dimension.nominal_value} {dimension.unit}
                Tolerance Type: {dimension.tolerance_type}
                Upper Tolerance: {dimension.upper_tolerance}
                Lower Tolerance: {dimension.lower_tolerance}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_dimensional_analysis"
                )
                
                if ai_result and ai_result.get('response'):
                    dimension.confidence = min(dimension.confidence + 0.1, 1.0)
                    if dimension.metadata is None:
                        dimension.metadata = {}
                    dimension.metadata['ai_enhanced'] = True
                    dimension.metadata['ai_analysis'] = ai_result.get('response', '')[:200]
                
                enhanced_dimensions.append(dimension)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for dimension {dimension.id}: {e}")
                enhanced_dimensions.append(dimension)
        
        # Add remaining dimensions without AI enhancement
        enhanced_dimensions.extend(dimensions[15:])
        return enhanced_dimensions
    
    async def _enhance_gdt_with_ai(self, geometric_tolerances: List[GeometricTolerance], 
                                 request: AnalysisRequest) -> List[GeometricTolerance]:
        """Enhance GD&T information with AI analysis"""
        enhanced_gdt = []
        
        for gdt in geometric_tolerances:
            try:
                context = f"""
                GD&T Analysis:
                Symbol: {gdt.symbol_name}
                Tolerance Value: {gdt.tolerance_value}
                Datum System: {', '.join(gdt.datum_system)}
                Material Condition: {gdt.material_condition or 'Not specified'}
                Feature Type: {gdt.feature_type}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_gdt_analysis"
                )
                
                if ai_result and ai_result.get('response'):
                    gdt.confidence = min(gdt.confidence + 0.1, 1.0)
                    if gdt.metadata is None:
                        gdt.metadata = {}
                    gdt.metadata['ai_enhanced'] = True
                    gdt.metadata['ai_analysis'] = ai_result.get('response', '')[:200]
                
                enhanced_gdt.append(gdt)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for GD&T {gdt.symbol_name}: {e}")
                enhanced_gdt.append(gdt)
        
        return enhanced_gdt
    
    def _calculate_tolerance_summary(self, dimensions: List[Dimension], 
                                   geometric_tolerances: List[GeometricTolerance]) -> Dict[str, Any]:
        """Calculate summary of tolerance information"""
        summary = {
            'dimensional_tolerances': {
                'bilateral': len([d for d in dimensions if d.tolerance_type == 'bilateral']),
                'unilateral': len([d for d in dimensions if d.tolerance_type == 'unilateral']),
                'none': len([d for d in dimensions if d.tolerance_type == 'none']),
            },
            'geometric_tolerances': {
                'form': len([g for g in geometric_tolerances if g.feature_type == 'form']),
                'orientation': len([g for g in geometric_tolerances if g.feature_type == 'orientation']),
                'location': len([g for g in geometric_tolerances if g.feature_type == 'location']),
                'profile': len([g for g in geometric_tolerances if g.feature_type == 'profile']),
                'runout': len([g for g in geometric_tolerances if g.feature_type == 'runout']),
            },
            'tolerance_tightness': self._analyze_tolerance_tightness(dimensions, geometric_tolerances),
            'datum_usage': self._analyze_datum_usage(geometric_tolerances)
        }
        
        return summary
    
    def _analyze_tolerance_tightness(self, dimensions: List[Dimension], 
                                   geometric_tolerances: List[GeometricTolerance]) -> Dict[str, Any]:
        """Analyze overall tolerance tightness"""
        dimensional_tolerances = []
        
        for dim in dimensions:
            if dim.upper_tolerance is not None:
                dimensional_tolerances.append(dim.upper_tolerance)
            if dim.lower_tolerance is not None:
                dimensional_tolerances.append(dim.lower_tolerance)
        
        geometric_tolerance_values = [g.tolerance_value for g in geometric_tolerances]
        
        analysis = {}
        
        if dimensional_tolerances:
            analysis['dimensional_avg_tolerance'] = sum(dimensional_tolerances) / len(dimensional_tolerances)
            analysis['dimensional_tightest'] = min(dimensional_tolerances)
            analysis['dimensional_loosest'] = max(dimensional_tolerances)
        
        if geometric_tolerance_values:
            analysis['geometric_avg_tolerance'] = sum(geometric_tolerance_values) / len(geometric_tolerance_values)
            analysis['geometric_tightest'] = min(geometric_tolerance_values)
            analysis['geometric_loosest'] = max(geometric_tolerance_values)
        
        # Classify overall tightness
        all_tolerances = dimensional_tolerances + geometric_tolerance_values
        if all_tolerances:
            avg_tolerance = sum(all_tolerances) / len(all_tolerances)
            if avg_tolerance < 0.1:
                analysis['overall_classification'] = 'very_tight'
            elif avg_tolerance < 0.5:
                analysis['overall_classification'] = 'tight'
            elif avg_tolerance < 2.0:
                analysis['overall_classification'] = 'moderate'
            else:
                analysis['overall_classification'] = 'loose'
        
        return analysis
    
    def _analyze_datum_usage(self, geometric_tolerances: List[GeometricTolerance]) -> Dict[str, Any]:
        """Analyze datum system usage"""
        all_datums = []
        
        for gdt in geometric_tolerances:
            all_datums.extend(gdt.datum_system)
        
        if not all_datums:
            return {'total_datums': 0, 'most_common': None}
        
        # Count datum frequency
        datum_counts = {}
        for datum in all_datums:
            datum_counts[datum] = datum_counts.get(datum, 0) + 1
        
        most_common = max(datum_counts.items(), key=lambda x: x[1])
        
        return {
            'total_datums': len(set(all_datums)),
            'most_common': most_common[0],
            'datum_frequency': datum_counts,
            'avg_datums_per_tolerance': len(all_datums) / len(geometric_tolerances) if geometric_tolerances else 0
        }
    
    def _estimate_accuracy(self, analysis: DimensionalAnalysis) -> Dict[str, float]:
        """Estimate accuracy of dimensional analysis"""
        total_items = len(analysis.dimensions) + len(analysis.geometric_tolerances)
        
        if total_items == 0:
            return {'overall_accuracy': 0.0}
        
        confidence_scores = []
        confidence_scores.extend([d.confidence for d in analysis.dimensions])
        confidence_scores.extend([g.confidence for g in analysis.geometric_tolerances])
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Adjust based on completeness
        completeness_factor = min(1.0, total_items / 10)  # Assume 10 items for full completeness
        
        return {
            'overall_accuracy': round(avg_confidence * completeness_factor, 3),
            'average_confidence': round(avg_confidence, 3),
            'completeness_factor': round(completeness_factor, 3)
        }
    
    def _calculate_completeness_score(self, analysis: DimensionalAnalysis) -> Dict[str, Any]:
        """Calculate completeness score for dimensional analysis"""
        completeness = {
            'has_dimensions': len(analysis.dimensions) > 0,
            'has_tolerances': any(d.tolerance_type != 'none' for d in analysis.dimensions),
            'has_geometric_tolerances': len(analysis.geometric_tolerances) > 0,
            'has_coordinate_system': len(analysis.coordinate_systems) > 0,
            'has_scale_info': len(analysis.scale_information) > 0,
            'has_relationships': len(analysis.dimensional_relationships) > 0,
        }
        
        completeness_score = sum(completeness.values()) / len(completeness)
        
        return {
            'overall_completeness': round(completeness_score, 3),
            'categories_found': sum(completeness.values()),
            'total_categories': len(completeness),
            'detailed_completeness': completeness
        }