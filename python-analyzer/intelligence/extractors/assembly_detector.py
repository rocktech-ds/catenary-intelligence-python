"""
Advanced Assembly Detector for Engineering Documents

This module provides comprehensive assembly and component analysis:
- Part identification and numbering detection
- Assembly hierarchy mapping
- Component relationship analysis
- Bill of Materials (BOM) extraction
- Mechanical assembly recognition
- AI-powered component classification

Optimized for VPS environments using free services.
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
class Component:
    """Represents a single component or part"""
    id: str
    part_number: Optional[str]
    name: str
    quantity: Optional[int] = None
    description: Optional[str] = None
    material: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class Assembly:
    """Represents an assembly containing components"""
    id: str
    assembly_name: str
    components: List[Component]
    sub_assemblies: List['Assembly']
    bbox: Optional[BoundingBox] = None
    assembly_type: str = "unknown"  # mechanical, electrical, structural
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class BOMEntry:
    """Bill of Materials entry"""
    id: str
    item_number: str
    part_number: Optional[str]
    description: str
    quantity: int
    unit: Optional[str] = None
    material: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class AssemblyAnalysis:
    """Complete assembly analysis results"""
    assemblies: List[Assembly]
    components: List[Component]
    bom_entries: List[BOMEntry]
    part_relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class AdvancedAssemblyDetector:
    """Advanced assembly detection using text analysis and AI enhancement"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Assembly detection patterns
        self.assembly_patterns = {
            'part_numbers': [
                r'\b([A-Z]{1,3}[-_]?\d{3,6}[-_]?[A-Z]?)\b',
                r'\bP/?N[\s:]*([A-Z0-9\-_]{4,15})\b',
                r'\bref[\s:]*([A-Z0-9\-_]{3,12})\b',
                r'\bpeça[\s:]*n?[º°]?[\s]*([A-Z0-9\-_]{3,12})\b',
            ],
            'quantities': [
                r'\b(\d+)\s*(?:un[idade]*s?|pç[s]?|pc[s]?|ea[ch]*|qtd[e]?)\b',
                r'\bqty[\s:]*([0-9]+)\b',
                r'\bquantidade[\s:]*([0-9]+)\b',
            ],
            'materials': [
                r'\b(aço\s+inox|stainless\s+steel|steel|aço|alumin[ií]o|aluminum|bronze|latão|brass|cobre|copper)\b',
                r'\b(PVC|PE|PP|ABS|nylon|teflon|borracha|rubber|plástico|plastic)\b',
                r'\bmaterial[\s:]*([a-záéíóúâêôàç\s]{3,30})\b',
            ],
            'assembly_headers': [
                r'\b(conjunto|assembly|sub[\-_]?assembly|montagem)\s+([a-záéíóúâêôàç0-9\s\-_]{5,50})\b',
                r'\bgrupo[\s:]*([a-záéíóúâêôàç0-9\s\-_]{5,50})\b',
            ],
            'bom_headers': [
                r'\b(bill\s+of\s+materials|lista\s+de\s+materiais|bom|lista\s+de\s+pe[çc]as)\b',
                r'\bitem[\s]*\|[\s]*descri[çc][ãa]o[\s]*\|[\s]*qtd',
                r'\bn[º°][\s]*\|[\s]*pe[çc]a[\s]*\|[\s]*quantidade',
            ],
            'component_descriptions': [
                r'\b(parafuso|screw|porca|nut|arruela|washer|pino|pin|eixo|shaft|mancal|bearing)\b',
                r'\b(vedação|seal|junta|gasket|anel|ring|tampa|cover|flange|conexão|connection)\b',
                r'\b(válvula|valve|bomba|pump|motor|filtro|filter|tubo|pipe|conexão|fitting)\b',
            ]
        }
    
    async def detect_assemblies(self, document_path: str, request: AnalysisRequest) -> Dict[str, Any]:
        """
        Comprehensive assembly detection and analysis
        """
        try:
            # Load document
            import fitz  # PyMuPDF
            doc = fitz.open(document_path)
            
            all_assemblies = []
            all_components = []
            all_bom_entries = []
            part_relationships = []
            processing_warnings = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Extract text for analysis
                    text_dict = page.get_text("dict")
                    page_text = page.get_text()
                    
                    # 1. Detect BOM tables
                    page_bom_entries = await self._detect_bom_tables(text_dict, page_text, page_num)
                    all_bom_entries.extend(page_bom_entries)
                    
                    # 2. Detect assembly structures
                    page_assemblies = await self._detect_assembly_structures(text_dict, page_text, page_num)
                    all_assemblies.extend(page_assemblies)
                    
                    # 3. Detect individual components
                    page_components = await self._detect_individual_components(text_dict, page_text, page_num)
                    all_components.extend(page_components)
                    
                    # 4. Detect part relationships
                    page_relationships = await self._detect_part_relationships(text_dict, page_text, page_num)
                    part_relationships.extend(page_relationships)
                    
                except Exception as e:
                    error_msg = f"Assembly detection failed for page {page_num + 1}: {str(e)}"
                    logger.warning(error_msg)
                    processing_warnings.append(error_msg)
            
            doc.close()
            
            # 5. Deduplicate and organize results
            unique_components = self._deduplicate_components(all_components)
            unique_assemblies = self._deduplicate_assemblies(all_assemblies)
            unique_bom_entries = self._deduplicate_bom_entries(all_bom_entries)
            
            # 6. AI enhancement (if enabled)
            if request.use_ai_enhancement:
                unique_components = await self._enhance_components_with_ai(unique_components, request)
                unique_assemblies = await self._enhance_assemblies_with_ai(unique_assemblies, request)
            
            # 7. Build assembly hierarchy
            assembly_hierarchy = self._build_assembly_hierarchy(unique_assemblies, unique_components)
            
            # 8. Analyze part relationships
            relationship_analysis = self._analyze_part_relationships(part_relationships, unique_components)
            
            # Create final analysis result
            assembly_analysis = AssemblyAnalysis(
                assemblies=assembly_hierarchy,
                components=unique_components,
                bom_entries=unique_bom_entries,
                part_relationships=relationship_analysis,
                metadata={
                    'total_assemblies': len(unique_assemblies),
                    'total_components': len(unique_components),
                    'total_bom_entries': len(unique_bom_entries),
                    'has_complete_bom': len(unique_bom_entries) > 5,
                    'assembly_complexity': self._calculate_assembly_complexity(unique_assemblies, unique_components)
                }
            )
            
            return {
                'assembly_analysis': asdict(assembly_analysis),
                'processing_warnings': processing_warnings,
                'analysis_metadata': {
                    'detection_methods': ['bom_tables', 'assembly_structures', 'component_detection', 'ai_enhancement'],
                    'total_parts_identified': len(unique_components) + len(unique_bom_entries),
                    'assembly_depth': self._calculate_assembly_depth(assembly_hierarchy)
                }
            }
            
        except Exception as e:
            logger.error(f"Assembly detection failed: {e}")
            return {'error': str(e), 'assembly_analysis': None}
    
    async def _detect_bom_tables(self, text_dict: Dict, page_text: str, page_num: int) -> List[BOMEntry]:
        """Detect and parse Bill of Materials tables"""
        bom_entries = []
        
        # Look for BOM headers
        for header_pattern in self.assembly_patterns['bom_headers']:
            header_matches = re.finditer(header_pattern, page_text, re.IGNORECASE)
            
            for header_match in header_matches:
                # Extract table region after header
                table_start = header_match.end()
                table_text = page_text[table_start:table_start + 2000]  # Look ahead 2000 chars
                
                # Parse BOM table rows
                table_entries = self._parse_bom_table(table_text, page_num)
                bom_entries.extend(table_entries)
        
        # Also look for tabular data that might be BOM without explicit header
        bom_entries.extend(self._detect_implicit_bom_tables(page_text, page_num))
        
        return bom_entries
    
    def _parse_bom_table(self, table_text: str, page_num: int) -> List[BOMEntry]:
        """Parse BOM table from text"""
        entries = []
        lines = table_text.split('\n')
        
        for line in lines[:50]:  # Process up to 50 lines
            line = line.strip()
            if len(line) < 10:
                continue
            
            # Pattern for BOM row: ITEM | PART | DESCRIPTION | QTY | UNIT
            bom_patterns = [
                r'(\d+)[\s\|]+(\S+)[\s\|]+([^\|]{10,80})[\s\|]+(\d+)[\s\|]*([\w]*)',
                r'([A-Z0-9\-_]+)[\s\|]+([^\|]{5,60})[\s\|]+(\d+)[\s\|]*([\w]*)',
            ]
            
            for pattern in bom_patterns:
                match = re.search(pattern, line)
                if match:
                    item_number = match.group(1).strip()
                    part_or_desc = match.group(2).strip()
                    description = match.group(3).strip()
                    quantity = int(match.group(4))
                    unit = match.group(5).strip() if len(match.groups()) > 4 else None
                    
                    # Determine if group 2 is part number or part of description
                    part_number = None
                    if re.match(r'^[A-Z0-9\-_]{4,}$', part_or_desc):
                        part_number = part_or_desc
                    else:
                        description = f"{part_or_desc} {description}".strip()
                    
                    entry = BOMEntry(
                        id=str(uuid.uuid4()),
                        item_number=item_number,
                        part_number=part_number,
                        description=description,
                        quantity=quantity,
                        unit=unit,
                        metadata={
                            'detection_method': 'bom_table_parsing',
                            'raw_line': line,
                            'page': page_num
                        }
                    )
                    entries.append(entry)
                    break
        
        return entries
    
    def _detect_implicit_bom_tables(self, page_text: str, page_num: int) -> List[BOMEntry]:
        """Detect BOM-like tables without explicit headers"""
        entries = []
        
        # Look for patterns that suggest tabular component lists
        lines = page_text.split('\n')
        potential_bom_lines = []
        
        for line in lines:
            line = line.strip()
            # Lines with: number, description with quantity
            if re.search(r'\d+\s+[^\d]{10,}\s+\d+\s*(un|pç|pc)', line, re.IGNORECASE):
                potential_bom_lines.append(line)
        
        # If we found several similar lines, treat as BOM
        if len(potential_bom_lines) >= 3:
            for i, line in enumerate(potential_bom_lines[:20]):  # Limit to 20 entries
                match = re.search(r'(\d+)\s+([^\d]{5,})\s+(\d+)\s*(\w*)', line)
                if match:
                    entry = BOMEntry(
                        id=str(uuid.uuid4()),
                        item_number=match.group(1),
                        part_number=None,
                        description=match.group(2).strip(),
                        quantity=int(match.group(3)),
                        unit=match.group(4) if match.group(4) else None,
                        metadata={
                            'detection_method': 'implicit_bom',
                            'raw_line': line,
                            'page': page_num
                        }
                    )
                    entries.append(entry)
        
        return entries
    
    async def _detect_assembly_structures(self, text_dict: Dict, page_text: str, page_num: int) -> List[Assembly]:
        """Detect assembly structures and hierarchies"""
        assemblies = []
        
        # Look for assembly headers
        for header_pattern in self.assembly_patterns['assembly_headers']:
            matches = re.finditer(header_pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                assembly_name = match.group(2).strip()
                
                # Extract context around assembly
                context_start = max(0, match.start() - 200)
                context_end = min(len(page_text), match.end() + 1000)
                context_text = page_text[context_start:context_end]
                
                # Find components in this assembly context
                assembly_components = self._extract_assembly_components(context_text, page_num)
                
                if assembly_components:
                    assembly = Assembly(
                        id=str(uuid.uuid4()),
                        assembly_name=assembly_name,
                        components=assembly_components,
                        sub_assemblies=[],
                        assembly_type=self._classify_assembly_type(assembly_name, context_text),
                        confidence=0.7,
                        metadata={
                            'detection_method': 'header_based',
                            'context_text': context_text[:300],
                            'page': page_num
                        }
                    )
                    assemblies.append(assembly)
        
        return assemblies
    
    def _extract_assembly_components(self, context_text: str, page_num: int) -> List[Component]:
        """Extract components from assembly context"""
        components = []
        
        # Look for part numbers and descriptions in context
        lines = context_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) < 5:
                continue
            
            # Look for component patterns
            component = self._parse_component_line(line, page_num)
            if component:
                components.append(component)
        
        return components[:10]  # Limit to 10 components per assembly
    
    async def _detect_individual_components(self, text_dict: Dict, page_text: str, page_num: int) -> List[Component]:
        """Detect individual components throughout the document"""
        components = []
        
        # Extract all potential part numbers
        for pattern in self.assembly_patterns['part_numbers']:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                part_number = match.group(1)
                
                # Get context around part number
                context_start = max(0, match.start() - 100)
                context_end = min(len(page_text), match.end() + 100)
                context = page_text[context_start:context_end]
                
                # Extract component information from context
                component = self._analyze_component_context(part_number, context, page_num)
                if component:
                    components.append(component)
        
        # Also look for component descriptions without part numbers
        for desc_pattern in self.assembly_patterns['component_descriptions']:
            matches = re.finditer(desc_pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                component_type = match.group(1)
                
                # Get context
                context_start = max(0, match.start() - 50)
                context_end = min(len(page_text), match.end() + 150)
                context = page_text[context_start:context_end]
                
                component = Component(
                    id=str(uuid.uuid4()),
                    part_number=None,
                    name=component_type,
                    description=context.strip(),
                    confidence=0.6,
                    metadata={
                        'detection_method': 'description_based',
                        'context': context,
                        'page': page_num
                    }
                )
                components.append(component)
        
        return components
    
    def _parse_component_line(self, line: str, page_num: int) -> Optional[Component]:
        """Parse a single line for component information"""
        # Pattern: [PART_NUMBER] [QUANTITY] [DESCRIPTION] [MATERIAL]
        component_pattern = r'([A-Z0-9\-_]{3,12})\s+(?:(\d+)\s+)?([a-záéíóúâêôàç\s]{5,50})(?:\s+([a-záéíóúâêôàç\s]{3,20}))?'
        
        match = re.search(component_pattern, line, re.IGNORECASE)
        if match:
            part_number = match.group(1)
            quantity_str = match.group(2)
            description = match.group(3).strip()
            material = match.group(4).strip() if match.group(4) else None
            
            quantity = int(quantity_str) if quantity_str else None
            
            return Component(
                id=str(uuid.uuid4()),
                part_number=part_number,
                name=description.split()[0] if description else 'Unknown',
                quantity=quantity,
                description=description,
                material=material,
                confidence=0.8,
                metadata={
                    'detection_method': 'line_parsing',
                    'raw_line': line,
                    'page': page_num
                }
            )
        
        return None
    
    def _analyze_component_context(self, part_number: str, context: str, page_num: int) -> Optional[Component]:
        """Analyze context around part number to extract component info"""
        # Extract quantity
        quantity = None
        for qty_pattern in self.assembly_patterns['quantities']:
            qty_match = re.search(qty_pattern, context, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                break
        
        # Extract material
        material = None
        for mat_pattern in self.assembly_patterns['materials']:
            mat_match = re.search(mat_pattern, context, re.IGNORECASE)
            if mat_match:
                material = mat_match.group(1)
                break
        
        # Extract description (text near part number that looks descriptive)
        description_pattern = r'[a-záéíóúâêôàç\s]{10,100}'
        desc_match = re.search(description_pattern, context, re.IGNORECASE)
        description = desc_match.group(0).strip() if desc_match else None
        
        # Determine component name from part number or description
        component_name = part_number
        if description:
            # Take first few words as name
            name_words = description.split()[:3]
            component_name = ' '.join(name_words)
        
        return Component(
            id=str(uuid.uuid4()),
            part_number=part_number,
            name=component_name,
            quantity=quantity,
            description=description,
            material=material,
            confidence=0.7,
            metadata={
                'detection_method': 'context_analysis',
                'context': context,
                'page': page_num
            }
        )
    
    async def _detect_part_relationships(self, text_dict: Dict, page_text: str, page_num: int) -> List[Dict[str, Any]]:
        """Detect relationships between parts (assembly, connection, etc.)"""
        relationships = []
        
        # Relationship patterns
        relation_patterns = [
            r'([A-Z0-9\-_]{3,12})\s+(?:conecta|liga|monta|fixa)\s+(?:com|em|a)\s+([A-Z0-9\-_]{3,12})',
            r'([A-Z0-9\-_]{3,12})\s+(?:connects|attaches|mounts)\s+(?:to|with)\s+([A-Z0-9\-_]{3,12})',
            r'assembly\s+([A-Z0-9\-_]{3,12})\s+(?:contains|includes)\s+([A-Z0-9\-_]{3,12})',
        ]
        
        for pattern in relation_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            
            for match in matches:
                part1 = match.group(1)
                part2 = match.group(2)
                
                relationship = {
                    'id': str(uuid.uuid4()),
                    'part1': part1,
                    'part2': part2,
                    'relationship_type': 'connects',  # Could be more sophisticated
                    'context': match.group(0),
                    'page': page_num,
                    'confidence': 0.6
                }
                relationships.append(relationship)
        
        return relationships
    
    def _classify_assembly_type(self, assembly_name: str, context_text: str) -> str:
        """Classify the type of assembly"""
        assembly_name_lower = assembly_name.lower()
        context_lower = context_text.lower()
        
        # Mechanical assembly indicators
        if any(term in assembly_name_lower or term in context_lower for term in [
            'motor', 'bomba', 'válvula', 'eixo', 'mancal', 'engrenagem',
            'pump', 'valve', 'shaft', 'bearing', 'gear', 'mechanical'
        ]):
            return 'mechanical'
        
        # Electrical assembly indicators
        if any(term in assembly_name_lower or term in context_lower for term in [
            'elétrico', 'eletrônico', 'cabo', 'fio', 'circuito',
            'electrical', 'electronic', 'cable', 'wire', 'circuit'
        ]):
            return 'electrical'
        
        # Structural assembly indicators
        if any(term in assembly_name_lower or term in context_lower for term in [
            'estrutura', 'suporte', 'base', 'frame', 'support', 'structural'
        ]):
            return 'structural'
        
        return 'general'
    
    def _deduplicate_components(self, components: List[Component]) -> List[Component]:
        """Remove duplicate components"""
        seen = {}
        unique = []
        
        for component in components:
            # Create key based on part number or name
            key = component.part_number or component.name
            key = key.upper() if key else str(uuid.uuid4())
            
            if key not in seen:
                seen[key] = component
                unique.append(component)
            else:
                # Keep the one with higher confidence or more complete info
                existing = seen[key]
                if (component.confidence > existing.confidence or
                    (component.description and not existing.description) or
                    (component.material and not existing.material)):
                    unique.remove(existing)
                    unique.append(component)
                    seen[key] = component
        
        return unique
    
    def _deduplicate_assemblies(self, assemblies: List[Assembly]) -> List[Assembly]:
        """Remove duplicate assemblies"""
        seen_names = set()
        unique = []
        
        for assembly in assemblies:
            name_key = assembly.assembly_name.upper()
            
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique.append(assembly)
        
        return unique
    
    def _deduplicate_bom_entries(self, bom_entries: List[BOMEntry]) -> List[BOMEntry]:
        """Remove duplicate BOM entries"""
        seen = {}
        unique = []
        
        for entry in bom_entries:
            # Create key based on item number and description
            key = f"{entry.item_number}_{entry.description[:20]}".upper()
            
            if key not in seen:
                seen[key] = entry
                unique.append(entry)
            else:
                # Keep the one with more complete information
                existing = seen[key]
                if (entry.part_number and not existing.part_number) or \
                   (entry.unit and not existing.unit):
                    unique.remove(existing)
                    unique.append(entry)
                    seen[key] = entry
        
        return unique
    
    async def _enhance_components_with_ai(self, components: List[Component], 
                                        request: AnalysisRequest) -> List[Component]:
        """Enhance component information using AI services"""
        enhanced = []
        
        for component in components[:20]:  # Limit to first 20 for performance
            try:
                context = f"""
                Component Analysis:
                Part Number: {component.part_number or 'Unknown'}
                Name: {component.name}
                Description: {component.description or 'Unknown'}
                Material: {component.material or 'Unknown'}
                Quantity: {component.quantity or 'Unknown'}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_component_info"
                )
                
                if ai_result and ai_result.get('response'):
                    component.confidence = min(component.confidence + 0.1, 1.0)
                    if component.metadata is None:
                        component.metadata = {}
                    component.metadata['ai_enhanced'] = True
                    component.metadata['ai_suggestions'] = ai_result.get('response', '')[:200]
                
                enhanced.append(component)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for component {component.name}: {e}")
                enhanced.append(component)
        
        # Add remaining components without AI enhancement
        enhanced.extend(components[20:])
        return enhanced
    
    async def _enhance_assemblies_with_ai(self, assemblies: List[Assembly], 
                                        request: AnalysisRequest) -> List[Assembly]:
        """Enhance assembly information using AI services"""
        enhanced = []
        
        for assembly in assemblies:
            try:
                context = f"""
                Assembly Analysis:
                Name: {assembly.assembly_name}
                Type: {assembly.assembly_type}
                Components Count: {len(assembly.components)}
                Components: {', '.join([c.name for c in assembly.components[:5]])}
                """
                
                from ..services.free_services_manager import free_services
                
                ai_result = await free_services.enhance_with_ai(
                    text=context,
                    task="enhance_assembly_info"
                )
                
                if ai_result and ai_result.get('response'):
                    assembly.confidence = min(assembly.confidence + 0.1, 1.0)
                    if assembly.metadata is None:
                        assembly.metadata = {}
                    assembly.metadata['ai_enhanced'] = True
                    assembly.metadata['ai_analysis'] = ai_result.get('response', '')[:200]
                
                enhanced.append(assembly)
                
            except Exception as e:
                logger.warning(f"AI enhancement failed for assembly {assembly.assembly_name}: {e}")
                enhanced.append(assembly)
        
        return enhanced
    
    def _build_assembly_hierarchy(self, assemblies: List[Assembly], 
                                components: List[Component]) -> List[Assembly]:
        """Build hierarchical assembly structure"""
        # This would implement assembly hierarchy building
        # For now, just return the flat list
        return assemblies
    
    def _analyze_part_relationships(self, relationships: List[Dict[str, Any]], 
                                  components: List[Component]) -> List[Dict[str, Any]]:
        """Analyze and validate part relationships"""
        # Filter relationships to only include known components
        component_parts = {c.part_number for c in components if c.part_number}
        
        valid_relationships = []
        for rel in relationships:
            if rel['part1'] in component_parts and rel['part2'] in component_parts:
                valid_relationships.append(rel)
        
        return valid_relationships
    
    def _calculate_assembly_complexity(self, assemblies: List[Assembly], 
                                     components: List[Component]) -> Dict[str, Any]:
        """Calculate assembly complexity metrics"""
        return {
            'total_unique_parts': len(set(c.part_number for c in components if c.part_number)),
            'avg_components_per_assembly': sum(len(a.components) for a in assemblies) / len(assemblies) if assemblies else 0,
            'assembly_types': list(set(a.assembly_type for a in assemblies)),
            'has_hierarchical_structure': any(a.sub_assemblies for a in assemblies),
            'material_diversity': len(set(c.material for c in components if c.material)),
        }
    
    def _calculate_assembly_depth(self, assemblies: List[Assembly]) -> int:
        """Calculate maximum assembly hierarchy depth"""
        max_depth = 1
        
        def get_depth(assembly: Assembly, current_depth: int) -> int:
            if not assembly.sub_assemblies:
                return current_depth
            
            max_sub_depth = current_depth
            for sub_assembly in assembly.sub_assemblies:
                sub_depth = get_depth(sub_assembly, current_depth + 1)
                max_sub_depth = max(max_sub_depth, sub_depth)
            
            return max_sub_depth
        
        for assembly in assemblies:
            depth = get_depth(assembly, 1)
            max_depth = max(max_depth, depth)
        
        return max_depth