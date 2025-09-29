"""
BOM Post-processor Module
Advanced BOM structuring and validation after extraction
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from loguru import logger
import re

from ..models.schemas import TableData

@dataclass
class BOMItem:
    """Structured BOM item with component information"""
    ref: Optional[str] = None
    codigo: Optional[str] = None
    nomenclatura: Optional[str] = None
    designacao: Optional[str] = None
    quantidade: Optional[str] = None
    peso_unitario: Optional[float] = None
    peso_total: Optional[float] = None
    observacoes: Optional[str] = None

    # Matched component data
    matched_codigo: Optional[str] = None
    matched_nomenclatura: Optional[str] = None
    matched_designacao: Optional[str] = None
    matched_category: Optional[str] = None
    match_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'ref': self.ref,
            'codigo': self.codigo,
            'nomenclatura': self.nomenclatura,
            'designacao': self.designacao,
            'quantidade': self._parse_quantidade(),
            'peso_unitario': self.peso_unitario,
            'peso_total': self.peso_total,
            'observacoes': self.observacoes,
            'matched_component': {
                'codigo': self.matched_codigo,
                'nomenclatura': self.matched_nomenclatura,
                'designacao': self.matched_designacao,
                'category': self.matched_category,
                'confidence': self.match_confidence
            } if self.matched_codigo else None
        }

    def _parse_quantidade(self) -> Optional[int]:
        """Parse quantity from string"""
        if not self.quantidade:
            return None

        try:
            # Extract first number from string
            numbers = re.findall(r'\d+', str(self.quantidade))
            if numbers:
                return int(numbers[0])
        except:
            pass

        return None

@dataclass
class StructuredBOM:
    """Complete structured BOM with metadata"""
    items: List[BOMItem]
    total_items: int
    matched_items: int
    average_confidence: float
    categories: Dict[str, int]  # category -> count
    total_weight: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'items': [item.to_dict() for item in self.items],
            'summary': {
                'total_items': self.total_items,
                'matched_items': self.matched_items,
                'match_rate': self.matched_items / self.total_items if self.total_items > 0 else 0,
                'average_confidence': self.average_confidence,
                'categories': self.categories,
                'total_weight': self.total_weight
            }
        }

class BOMProcessor:
    """Post-processor for extracted BOM tables"""

    def __init__(self):
        pass

    def process_bom_table(self, table: TableData) -> StructuredBOM:
        """
        Process extracted BOM table into structured format

        Args:
            table: TableData with BOM information and component matches

        Returns:
            StructuredBOM with organized component information
        """
        if table.table_type != 'bom':
            raise ValueError(f"Table type must be 'bom', got '{table.table_type}'")

        # Extract component matches from metadata
        component_matches = table.metadata.get('components', []) if table.metadata else []

        # Convert to BOMItem objects
        bom_items = self._create_bom_items(component_matches)

        # Calculate statistics
        total_items = len(bom_items)
        matched_items = sum(1 for item in bom_items if item.matched_codigo)
        avg_confidence = sum(item.match_confidence for item in bom_items) / total_items if total_items > 0 else 0

        # Group by categories
        categories = {}
        for item in bom_items:
            if item.matched_category:
                categories[item.matched_category] = categories.get(item.matched_category, 0) + 1

        # Calculate total weight
        total_weight = self._calculate_total_weight(bom_items)

        return StructuredBOM(
            items=bom_items,
            total_items=total_items,
            matched_items=matched_items,
            average_confidence=avg_confidence,
            categories=categories,
            total_weight=total_weight
        )

    def _create_bom_items(self, component_matches: List[Dict]) -> List[BOMItem]:
        """Create BOMItem objects from component match data"""
        items = []

        for match_data in component_matches:
            item = BOMItem(
                ref=match_data.get('ref'),
                codigo=match_data.get('codigo'),
                nomenclatura=match_data.get('nomenclatura'),
                designacao=match_data.get('designacao'),
                quantidade=match_data.get('quantidade'),
                matched_codigo=match_data.get('matched_codigo'),
                matched_nomenclatura=match_data.get('matched_nomenclatura'),
                matched_designacao=match_data.get('matched_designacao'),
                matched_category=match_data.get('matched_category'),
                match_confidence=match_data.get('match_confidence', 0.0)
            )

            # Parse weight information
            if match_data.get('matched_peso'):
                item.peso_unitario = match_data['matched_peso']
                qty = item._parse_quantidade()
                if qty and item.peso_unitario:
                    item.peso_total = qty * item.peso_unitario

            items.append(item)

        return items

    def _calculate_total_weight(self, items: List[BOMItem]) -> Optional[float]:
        """Calculate total weight of all BOM items"""
        total = 0.0
        has_weights = False

        for item in items:
            if item.peso_total:
                total += item.peso_total
                has_weights = True
            elif item.peso_unitario:
                qty = item._parse_quantidade() or 1
                total += item.peso_unitario * qty
                has_weights = True

        return total if has_weights else None

    def validate_bom(self, bom: StructuredBOM) -> Dict[str, Any]:
        """
        Validate BOM completeness and quality

        Returns:
            Dictionary with validation results
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'completeness': {},
            'quality_score': 0.0
        }

        # Check completeness
        items_with_ref = sum(1 for item in bom.items if item.ref)
        items_with_nomenclatura = sum(1 for item in bom.items if item.nomenclatura or item.matched_nomenclatura)
        items_with_quantity = sum(1 for item in bom.items if item.quantidade)

        validation['completeness'] = {
            'ref_coverage': items_with_ref / bom.total_items if bom.total_items > 0 else 0,
            'nomenclatura_coverage': items_with_nomenclatura / bom.total_items if bom.total_items > 0 else 0,
            'quantity_coverage': items_with_quantity / bom.total_items if bom.total_items > 0 else 0
        }

        # Warnings and errors
        if validation['completeness']['ref_coverage'] < 0.8:
            validation['warnings'].append("Less than 80% of items have reference numbers")

        if validation['completeness']['nomenclatura_coverage'] < 0.5:
            validation['errors'].append("Less than 50% of items have nomenclatura")
            validation['is_valid'] = False

        if bom.matched_items / bom.total_items < 0.3:
            validation['warnings'].append("Low component match rate - less than 30% matched")

        # Calculate quality score (0-100)
        quality_score = (
            validation['completeness']['ref_coverage'] * 30 +
            validation['completeness']['nomenclatura_coverage'] * 40 +
            validation['completeness']['quantity_coverage'] * 20 +
            (bom.matched_items / bom.total_items) * 10
        ) if bom.total_items > 0 else 0

        validation['quality_score'] = quality_score

        return validation

    def export_bom_csv(self, bom: StructuredBOM) -> str:
        """
        Export BOM to CSV format

        Returns:
            CSV string
        """
        import io
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'REF', 'CÓDIGO', 'NOMENCLATURA', 'DESIGNAÇÃO', 'QUANTIDADE',
            'PESO_UNIT', 'PESO_TOTAL', 'CATEGORIA', 'CONFIANÇA_MATCH'
        ])

        # Write data
        for item in bom.items:
            writer.writerow([
                item.ref or '',
                item.matched_codigo or item.codigo or '',
                item.matched_nomenclatura or item.nomenclatura or '',
                item.matched_designacao or item.designacao or '',
                item.quantidade or '',
                item.peso_unitario or '',
                item.peso_total or '',
                item.matched_category or '',
                f"{item.match_confidence:.1f}%" if item.match_confidence > 0 else ''
            ])

        return output.getvalue()

    def get_bom_summary(self, bom: StructuredBOM) -> Dict[str, Any]:
        """Get high-level BOM summary"""
        return {
            'total_components': bom.total_items,
            'identified_components': bom.matched_items,
            'identification_rate': f"{(bom.matched_items / bom.total_items * 100):.1f}%" if bom.total_items > 0 else "0%",
            'average_confidence': f"{bom.average_confidence:.1f}%",
            'categories': bom.categories,
            'total_weight_kg': bom.total_weight,
            'top_categories': sorted(bom.categories.items(), key=lambda x: x[1], reverse=True)[:5]
        }