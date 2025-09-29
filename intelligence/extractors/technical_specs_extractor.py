"""
Advanced Technical Specifications Extractor for Engineering Documents

This module provides comprehensive extraction of technical specifications including:
- Material specifications and properties
- Dimensional tolerances and measurements
- Performance parameters and ratings
- Standards compliance references
- Technical properties and characteristics
- Units normalization and validation

Optimized for VPS environments using free services and AI enhancement.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
from collections import defaultdict

from ..models.analysis_models import AnalysisRequest, BoundingBox

logger = logging.getLogger(__name__)

@dataclass
class TechnicalProperty:
    """Represents a single technical property or specification"""
    id: str
    property_type: str  # material, dimension, tolerance, performance, standard
    name: str
    value: str
    unit: Optional[str] = None
    tolerance: Optional[str] = None
    standard_reference: Optional[str] = None
    context: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class MaterialSpecification:
    """Represents material specifications and properties"""
    id: str
    material_name: str
    material_type: str  # steel, aluminum, plastic, composite, etc.
    grade: Optional[str] = None
    properties: List[TechnicalProperty] = None
    standards: List[str] = None
    applications: List[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class DimensionalSpecification:
    """Represents dimensional specifications and tolerances"""
    id: str
    dimension_type: str  # length, width, height, diameter, thickness, angle
    nominal_value: float
    unit: str
    tolerance_upper: Optional[float] = None
    tolerance_lower: Optional[float] = None
    tolerance_type: Optional[str] = None  # ±, +/-, GD&T symbol
    surface_finish: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class PerformanceSpecification:
    """Represents performance parameters and ratings"""
    id: str
    parameter_name: str
    parameter_type: str  # pressure, temperature, flow, power, speed, load
    value: str
    unit: Optional[str] = None
    operating_conditions: Optional[str] = None
    safety_factor: Optional[str] = None
    test_method: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class TechnicalSpecsAnalysis:
    """Complete technical specifications analysis results"""
    materials: List[MaterialSpecification] = None
    dimensions: List[DimensionalSpecification] = None
    performance_specs: List[PerformanceSpecification] = None
    technical_properties: List[TechnicalProperty] = None
    standards_references: List[str] = None
    units_summary: Dict[str, int] = None
    metadata: Dict[str, Any] = None

class TechnicalSpecsExtractor:
    """Advanced technical specifications extractor"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Technical specifications patterns (Portuguese and English)
        self.specs_patterns = {
            'materials': {
                'steel': [
                    r'aço\s+(inox|inoxidável|carbono|liga)',
                    r'steel\s+(stainless|carbon|alloy)',
                    r'AISI\s+(\d{3})',
                    r'DIN\s+(\d+\.\d+)',
                    r'ASTM\s+([A-Z]\d+)',
                ],
                'aluminum': [
                    r'alumínio\s+(série\s+)?(\d{4})',
                    r'aluminum\s+(series\s+)?(\d{4})',
                    r'Al\s*-?\s*(\d{4})',
                    r'liga\s+de\s+alumínio',
                ],
                'plastic': [
                    r'\b(PVC|PE|PP|ABS|PTFE|nylon|teflon)\b',
                    r'plástico\s+(rígido|flexível)',
                    r'polímero',
                    r'termoplástico',
                ],
                'composite': [
                    r'fibra\s+de\s+(vidro|carbono)',
                    r'(glass|carbon)\s+fiber',
                    r'compósito',
                    r'laminado',
                ]
            },
            'dimensions': [
                r'(diâmetro|diameter|Ø|φ)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(comprimento|length|L)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(largura|width|W)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(altura|height|H)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(espessura|thickness|t)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)\s*[x×]\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
            ],
            'tolerances': [
                r'[±]\s*(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'\+(\d+(?:[,.]\d+)?)\s*/\s*-(\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'tolerância\s*[=:]?\s*([±]\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'tolerance\s*[=:]?\s*([±]\d+(?:[,.]\d+)?)\s*([a-zA-Zμ]+)?',
                r'(IT\d+|H\d+|h\d+|G\d+|g\d+)',  # ISO tolerance grades
            ],
            'performance': {
                'pressure': [
                    r'(pressão|pressure)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(bar|psi|kPa|MPa|atm)',
                    r'(press\.|p)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(bar|psi|kPa|MPa)',
                ],
                'temperature': [
                    r'(temperatura|temperature|temp\.)\s*[=:]?\s*(-?\d+(?:[,.]\d+)?)\s*(°C|°F|K)',
                    r'(T)\s*[=:]?\s*(-?\d+(?:[,.]\d+)?)\s*(°C|°F|K)',
                ],
                'flow': [
                    r'(vazão|flow|fluxo)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(l/min|m³/h|gpm|cfm)',
                    r'(Q)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(l/min|m³/h|gpm)',
                ],
                'power': [
                    r'(potência|power)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(kW|HP|CV|W)',
                    r'(P)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(kW|HP|CV)',
                ],
                'speed': [
                    r'(velocidade|speed|rpm)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(rpm|m/s|km/h)',
                    r'(n|N)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(rpm)',
                ],
                'load': [
                    r'(carga|load|força|force)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(kg|N|kN|lbf|ton)',
                    r'(F)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(N|kN|kgf)',
                ]
            },
            'standards': [
                r'\b(ISO\s+\d+(?:-\d+)?(?::\d{4})?)\b',
                r'\b(ANSI\s+[A-Z]\d+\.\d+)\b',
                r'\b(DIN\s+\d+(?:-\d+)?)\b',
                r'\b(ASTM\s+[A-Z]\d+(?:-\d+)?)\b',
                r'\b(IEC\s+\d+(?:-\d+)?)\b',
                r'\b(EN\s+\d+(?:-\d+)?)\b',
                r'\b(JIS\s+[A-Z]\d+)\b',
                r'\b(ABNT\s+NBR\s+\d+)\b',
            ],
            'surface_finish': [
                r'(rugosidade|roughness|Ra)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(μm|µm|microns?)',
                r'(acabamento|finish)\s+(polido|usinado|lixado|natural)',
                r'(surface\s+finish|finish)\s+(\w+)',
            ],
            'units': {
                'length': ['mm', 'cm', 'm', 'km', 'in', 'ft', 'μm', 'µm'],
                'pressure': ['bar', 'psi', 'kPa', 'MPa', 'Pa', 'atm'],
                'temperature': ['°C', '°F', 'K', 'R'],
                'flow': ['l/min', 'l/h', 'm³/h', 'gpm', 'cfm'],
                'power': ['W', 'kW', 'MW', 'HP', 'CV'],
                'speed': ['rpm', 'm/s', 'km/h', 'mph'],
                'mass': ['kg', 'g', 't', 'lb', 'oz'],
                'force': ['N', 'kN', 'kgf', 'lbf', 'ton']
            }
        }
    
    async def extract_technical_specs(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Comprehensive technical specifications extraction
        """
        try:
            # Load document
            import fitz  # PyMuPDF
            doc = fitz.open(document_path)
            
            all_materials = []
            all_dimensions = []
            all_performance = []
            all_properties = []
            all_standards = set()
            units_counter = defaultdict(int)
            processing_warnings = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Extract text for analysis
                    text_dict = page.get_text("dict")
                    page_text = page.get_text()
                    
                    # 1. Extract material specifications
                    page_materials = await self._extract_materials(page_text, page_num)
                    all_materials.extend(page_materials)
                    
                    # 2. Extract dimensional specifications
                    page_dimensions = await self._extract_dimensions(page_text, page_num)
                    all_dimensions.extend(page_dimensions)
                    
                    # 3. Extract performance specifications
                    page_performance = await self._extract_performance_specs(page_text, page_num)
                    all_performance.extend(page_performance)
                    
                    # 4. Extract technical properties
                    page_properties = await self._extract_technical_properties(page_text, page_num)
                    all_properties.extend(page_properties)
                    
                    # 5. Extract standards references
                    page_standards = self._extract_standards_references(page_text)
                    all_standards.update(page_standards)
                    
                    # 6. Count units usage
                    page_units = self._count_units_usage(page_text)
                    for unit, count in page_units.items():
                        units_counter[unit] += count
                    
                except Exception as e:
                    error_msg = f"Technical specs extraction failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # 7. AI enhancement (if enabled)
            if request.use_ai_enhancement:
                try:
                    all_properties = await self._enhance_with_ai(all_properties, request)
                    all_materials = await self._enhance_materials_with_ai(all_materials, request)
                except Exception as e:
                    error_msg = f"AI enhancement failed: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            # 8. Create comprehensive analysis
            specs_analysis = TechnicalSpecsAnalysis(
                materials=all_materials,
                dimensions=all_dimensions,
                performance_specs=all_performance,
                technical_properties=all_properties,
                standards_references=list(all_standards),
                units_summary=dict(units_counter),
                metadata={
                    'total_materials': len(all_materials),
                    'total_dimensions': len(all_dimensions),
                    'total_performance_specs': len(all_performance),
                    'total_properties': len(all_properties),
                    'total_standards': len(all_standards),
                    'units_diversity': len(units_counter),
                    'processing_warnings_count': len(processing_warnings)
                }
            )
            
            return {
                'technical_specs_analysis': asdict(specs_analysis),
                'processing_warnings': processing_warnings,
                'analysis_metadata': {
                    'extraction_methods': ['regex_patterns', 'ai_enhancement', 'units_normalization'],
                    'confidence_summary': self._calculate_confidence_summary(specs_analysis),
                    'completeness_score': self._calculate_completeness_score(specs_analysis)
                }
            }
            
        except Exception as e:
            logger.error(f"Technical specs extraction failed: {e}")
            return {'error': str(e), 'technical_specs_analysis': None}
    
    async def _extract_materials(self, page_text: str, page_num: int) -> List[MaterialSpecification]:
        """Extract material specifications from text"""
        materials = []
        
        for material_type, patterns in self.specs_patterns['materials'].items():
            for pattern in patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                
                for match in matches:
                    # Extract context around material mention
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(page_text), match.end() + 200)
                    context = page_text[context_start:context_end]
                    
                    material_name = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    grade = match.group(2) if len(match.groups()) > 1 else None
                    
                    # Extract properties from context
                    properties = self._extract_material_properties(context, page_num)
                    
                    # Extract standards from context
                    standards = self._extract_standards_references(context)
                    
                    material_spec = MaterialSpecification(
                        id=str(uuid.uuid4()),
                        material_name=material_name,
                        material_type=material_type,
                        grade=grade,
                        properties=properties,
                        standards=list(standards),
                        applications=[],  # Could be enhanced with AI
                        confidence=0.8,
                        metadata={
                            'detection_method': 'pattern_matching',
                            'context': context[:200],
                            'page': page_num
                        }
                    )
                    
                    materials.append(material_spec)
        
        return materials
    
    def _extract_material_properties(self, context: str, page_num: int) -> List[TechnicalProperty]:
        """Extract technical properties from material context"""
        properties = []
        
        # Common material properties patterns
        property_patterns = {
            'yield_strength': r'(tensão\s+de\s+escoamento|yield\s+strength)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(MPa|kPa|psi)',
            'tensile_strength': r'(resistência\s+à\s+tração|tensile\s+strength)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(MPa|kPa|psi)',
            'hardness': r'(dureza|hardness)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(HRC|HRB|HV|BHN)',
            'density': r'(densidade|density)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(kg/m³|g/cm³)',
            'elastic_modulus': r'(módulo\s+de\s+elasticidade|elastic\s+modulus)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(GPa|MPa)',
        }
        
        for prop_type, pattern in property_patterns.items():
            matches = re.finditer(pattern, context, re.IGNORECASE)
            
            for match in matches:
                prop = TechnicalProperty(
                    id=str(uuid.uuid4()),
                    property_type='material_property',
                    name=prop_type.replace('_', ' ').title(),
                    value=match.group(2),
                    unit=match.group(3) if len(match.groups()) > 2 else None,
                    confidence=0.8,
                    context=match.group(0),
                    metadata={
                        'detection_method': 'material_property_pattern',
                        'page': page_num
                    }
                )
                properties.append(prop)
        
        return properties
    
    async def _extract_dimensions(self, page_text: str, page_num: int) -> List[DimensionalSpecification]:
        """Extract dimensional specifications from text"""
        dimensions = []
        
        for pattern in self.specs_patterns['dimensions']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    groups = match.groups()
                    
                    if len(groups) >= 3:  # dimension_type, value, unit
                        dimension_type = groups[0].lower()
                        value_str = groups[1].replace(',', '.')
                        nominal_value = float(value_str)
                        unit = groups[2] if groups[2] else 'mm'  # Default unit
                        
                        # Look for tolerance in surrounding text
                        tolerance_context = page_text[match.start()-50:match.end()+100]
                        tolerance_info = self._extract_tolerance_info(tolerance_context)
                        
                        dim_spec = DimensionalSpecification(
                            id=str(uuid.uuid4()),
                            dimension_type=dimension_type,
                            nominal_value=nominal_value,
                            unit=unit,
                            tolerance_upper=tolerance_info.get('upper'),
                            tolerance_lower=tolerance_info.get('lower'),
                            tolerance_type=tolerance_info.get('type'),
                            confidence=0.8,
                            metadata={
                                'detection_method': 'dimension_pattern',
                                'raw_match': match.group(0),
                                'page': page_num
                            }
                        )
                        
                        dimensions.append(dim_spec)
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse dimension: {match.group(0)} - {e}")
        
        return dimensions
    
    def _extract_tolerance_info(self, context: str) -> Dict[str, Any]:
        """Extract tolerance information from context"""
        tolerance_info = {}
        
        for pattern in self.specs_patterns['tolerances']:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if '±' in match.group(0):
                    tolerance_info['type'] = '±'
                    tolerance_info['upper'] = float(groups[0].replace(',', '.'))
                    tolerance_info['lower'] = float(groups[0].replace(',', '.'))
                elif '+' in match.group(0) and '-' in match.group(0):
                    tolerance_info['type'] = '+/-'
                    tolerance_info['upper'] = float(groups[0].replace(',', '.'))
                    tolerance_info['lower'] = float(groups[1].replace(',', '.'))
                elif groups[0].startswith(('IT', 'H', 'h', 'G', 'g')):
                    tolerance_info['type'] = 'ISO_grade'
                    tolerance_info['grade'] = groups[0]
                
                break
        
        return tolerance_info
    
    async def _extract_performance_specs(self, page_text: str, page_num: int) -> List[PerformanceSpecification]:
        """Extract performance specifications from text"""
        performance_specs = []
        
        for param_type, patterns in self.specs_patterns['performance'].items():
            for pattern in patterns:
                matches = re.finditer(pattern, page_text, re.IGNORECASE)
                
                for match in matches:
                    try:
                        groups = match.groups()
                        
                        if len(groups) >= 3:
                            parameter_name = groups[0]
                            value = groups[1]
                            unit = groups[2] if groups[2] else None
                            
                            # Extract operating conditions from context
                            context_start = max(0, match.start() - 100)
                            context_end = min(len(page_text), match.end() + 150)
                            context = page_text[context_start:context_end]
                            
                            operating_conditions = self._extract_operating_conditions(context)
                            
                            perf_spec = PerformanceSpecification(
                                id=str(uuid.uuid4()),
                                parameter_name=parameter_name,
                                parameter_type=param_type,
                                value=value,
                                unit=unit,
                                operating_conditions=operating_conditions,
                                confidence=0.8,
                                metadata={
                                    'detection_method': 'performance_pattern',
                                    'context': context[:150],
                                    'page': page_num
                                }
                            )
                            
                            performance_specs.append(perf_spec)
                            
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse performance spec: {match.group(0)} - {e}")
        
        return performance_specs
    
    def _extract_operating_conditions(self, context: str) -> Optional[str]:
        """Extract operating conditions from context"""
        condition_patterns = [
            r'(operação|operating|work(?:ing)?)\s+(?:temp(?:erature)?|temperatura)\s*[=:]?\s*(-?\d+(?:[,.]\d+)?)\s*(°C|°F|K)',
            r'(ambiente|ambient|room)\s+(?:temp(?:erature)?|temperatura)',
            r'(máximo|maximum|max\.?)\s+(\d+(?:[,.]\d+)?)',
            r'(mínimo|minimum|min\.?)\s+(\d+(?:[,.]\d+)?)',
        ]
        
        for pattern in condition_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    async def _extract_technical_properties(self, page_text: str, page_num: int) -> List[TechnicalProperty]:
        """Extract general technical properties from text"""
        properties = []
        
        # General technical property patterns
        general_patterns = [
            r'(peso|weight|massa|mass)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(kg|g|lb|oz)',
            r'(volume|volume)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(l|m³|ft³|gal)',
            r'(área|area)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(m²|cm²|ft²|in²)',
            r'(eficiência|efficiency)\s*[=:]?\s*(\d+(?:[,.]\d+)?)\s*(%)',
            r'(fator\s+de\s+segurança|safety\s+factor)\s*[=:]?\s*(\d+(?:[,.]\d+)?)',
        ]
        
        for pattern in general_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                groups = match.groups()
                
                prop = TechnicalProperty(
                    id=str(uuid.uuid4()),
                    property_type='general',
                    name=groups[0],
                    value=groups[1],
                    unit=groups[2] if len(groups) > 2 else None,
                    confidence=0.7,
                    context=match.group(0),
                    metadata={
                        'detection_method': 'general_property_pattern',
                        'page': page_num
                    }
                )
                
                properties.append(prop)
        
        return properties
    
    def _extract_standards_references(self, text: str) -> set:
        """Extract standards references from text"""
        standards = set()
        
        for pattern in self.specs_patterns['standards']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                standards.add(match.group(1))
        
        return standards
    
    def _count_units_usage(self, text: str) -> Dict[str, int]:
        """Count usage of different units in text"""
        unit_counts = {}
        
        for unit_type, units_list in self.specs_patterns['units'].items():
            for unit in units_list:
                # Use word boundaries to avoid partial matches
                pattern = rf'\b{re.escape(unit)}\b'
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    unit_counts[unit] = len(matches)
        
        return unit_counts
    
    async def _enhance_with_ai(self, properties: List[TechnicalProperty],
                             request: AnalysisRequest) -> List[TechnicalProperty]:
        """Enhance technical properties with AI analysis"""
        enhanced_properties = []
        
        for prop in properties[:20]:  # Limit for performance
            try:
                context = f"""
                Technical Property Analysis:
                Type: {prop.property_type}
                Name: {prop.name}
                Value: {prop.value}
                Unit: {prop.unit or 'Unknown'}
                Context: {prop.context or 'N/A'}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_technical_property"
                )
                
                if ai_result and ai_result.get('response'):
                    prop.confidence = min(prop.confidence + 0.1, 1.0)
                    if prop.metadata is None:
                        prop.metadata = {}
                    prop.metadata['ai_enhanced'] = True
                    prop.metadata['ai_analysis'] = ai_result.get('response', '')[:200]
                
                enhanced_properties.append(prop)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for property {prop.name}: {e}")
                enhanced_properties.append(prop)
        
        # Add remaining properties without AI enhancement
        enhanced_properties.extend(properties[20:])
        return enhanced_properties
    
    async def _enhance_materials_with_ai(self, materials: List[MaterialSpecification], 
                                       request: AnalysisRequest) -> List[MaterialSpecification]:
        """Enhance material specifications with AI analysis"""
        enhanced_materials = []
        
        for material in materials:
            try:
                context = f"""
                Material Specification Analysis:
                Name: {material.material_name}
                Type: {material.material_type}
                Grade: {material.grade or 'Unknown'}
                Properties Count: {len(material.properties)}
                Standards: {', '.join(material.standards[:3])}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_material_specification"
                )
                
                if ai_result and ai_result.get('response'):
                    material.confidence = min(material.confidence + 0.1, 1.0)
                    if material.metadata is None:
                        material.metadata = {}
                    material.metadata['ai_enhanced'] = True
                    material.metadata['ai_analysis'] = ai_result.get('response', '')[:200]
                
                enhanced_materials.append(material)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for material {material.material_name}: {e}")
                enhanced_materials.append(material)
        
        return enhanced_materials
    
    def _calculate_confidence_summary(self, analysis: TechnicalSpecsAnalysis) -> Dict[str, float]:
        """Calculate confidence summary for all extracted specs"""
        all_items = []
        all_items.extend([m.confidence for m in analysis.materials])
        all_items.extend([d.confidence for d in analysis.dimensions])
        all_items.extend([p.confidence for p in analysis.performance_specs])
        all_items.extend([t.confidence for t in analysis.technical_properties])
        
        if not all_items:
            return {'average_confidence': 0.0, 'high_confidence_ratio': 0.0}
        
        avg_confidence = sum(all_items) / len(all_items)
        high_confidence_count = sum(1 for c in all_items if c > 0.8)
        high_confidence_ratio = high_confidence_count / len(all_items)
        
        return {
            'average_confidence': round(avg_confidence, 3),
            'high_confidence_ratio': round(high_confidence_ratio, 3),
            'total_items_analyzed': len(all_items)
        }
    
    def _calculate_completeness_score(self, analysis: TechnicalSpecsAnalysis) -> Dict[str, Any]:
        """Calculate completeness score for the analysis"""
        completeness = {
            'has_materials': len(analysis.materials) > 0,
            'has_dimensions': len(analysis.dimensions) > 0,
            'has_performance_specs': len(analysis.performance_specs) > 0,
            'has_standards': len(analysis.standards_references) > 0,
            'units_diversity': len(analysis.units_summary) > 3,
        }
        
        completeness_score = sum(completeness.values()) / len(completeness)
        
        return {
            'overall_completeness': round(completeness_score, 3),
            'categories_found': sum(completeness.values()),
            'total_categories': len(completeness),
            'detailed_completeness': completeness
        }