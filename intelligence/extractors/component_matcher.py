"""
Component Matcher Module
Matches extracted BOM items with the parts database for accurate component identification
"""
import pandas as pd
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger
from dataclasses import dataclass
from fuzzywuzzy import fuzz, process

@dataclass
class ComponentMatch:
    """Represents a matched component from the parts database"""
    codigo: str
    nomenclatura: str
    designacao_completa: str
    category: str
    peso: Optional[float] = None
    confidence: float = 0.0
    match_method: str = ""
    original_text: str = ""

class ComponentMatcher:
    """
    Intelligent component matching using the parts database
    """

    def __init__(self, parts_csv_path: str = "/Users/andreluisce/workspaces/personal/catenary/csv-files/parts.csv"):
        self.parts_csv_path = Path(parts_csv_path)
        self.parts_df = None
        self.nomenclatura_index = {}
        self.codigo_index = {}
        self._load_parts_database()

    def _load_parts_database(self):
        """Load and index the parts database"""
        try:
            if self.parts_csv_path.exists():
                self.parts_df = pd.read_csv(self.parts_csv_path)
                logger.info(f"Loaded {len(self.parts_df)} components from parts database")

                # Create indices for faster lookup
                self._create_indices()
            else:
                logger.warning(f"Parts database not found at {self.parts_csv_path}")

        except Exception as e:
            logger.error(f"Failed to load parts database: {e}")

    def _create_indices(self):
        """Create search indices for faster matching"""
        if self.parts_df is None:
            return

        # Index by nomenclatura (normalized)
        for idx, row in self.parts_df.iterrows():
            if pd.notna(row.get('nomenclatura')):
                key = self._normalize_text(row['nomenclatura'])
                if key not in self.nomenclatura_index:
                    self.nomenclatura_index[key] = []
                self.nomenclatura_index[key].append(idx)

            # Index by codigo
            if pd.notna(row.get('codigo')):
                self.codigo_index[row['codigo'].strip().upper()] = idx

    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        if pd.isna(text):
            return ""
        return re.sub(r'[^a-zA-Z0-9]', '', str(text).upper())

    def match_component(self,
                       nomenclatura: str = None,
                       codigo: str = None,
                       designacao: str = None,
                       ref: str = None) -> Optional[ComponentMatch]:
        """
        Match a BOM component with the parts database

        Args:
            nomenclatura: Component nomenclatura from BOM
            codigo: Component code from BOM
            designacao: Component description from BOM
            ref: Component reference from BOM

        Returns:
            ComponentMatch object if found, None otherwise
        """
        if self.parts_df is None:
            return None

        # Strategy 1: Exact code match
        if codigo:
            match = self._match_by_codigo(codigo)
            if match:
                return match

        # Strategy 2: Exact nomenclatura match
        if nomenclatura:
            match = self._match_by_nomenclatura(nomenclatura)
            if match:
                return match

        # Strategy 3: Fuzzy matching on nomenclatura
        if nomenclatura:
            match = self._fuzzy_match_nomenclatura(nomenclatura)
            if match and match.confidence > 85:
                return match

        # Strategy 4: Fuzzy matching on designacao
        if designacao:
            match = self._fuzzy_match_designacao(designacao)
            if match and match.confidence > 80:
                return match

        # Strategy 5: Reference-based matching
        if ref:
            match = self._match_by_reference(ref)
            if match:
                return match

        return None

    def _match_by_codigo(self, codigo: str) -> Optional[ComponentMatch]:
        """Exact match by component code"""
        normalized_codigo = codigo.strip().upper()

        if normalized_codigo in self.codigo_index:
            idx = self.codigo_index[normalized_codigo]
            row = self.parts_df.iloc[idx]

            return ComponentMatch(
                codigo=row['codigo'],
                nomenclatura=row.get('nomenclatura', ''),
                designacao_completa=row.get('designacao_completa', ''),
                category=row.get('category', ''),
                peso=self._safe_float(row.get('peso')),
                confidence=100.0,
                match_method="exact_code",
                original_text=codigo
            )

        return None

    def _match_by_nomenclatura(self, nomenclatura: str) -> Optional[ComponentMatch]:
        """Exact match by nomenclatura"""
        normalized = self._normalize_text(nomenclatura)

        if normalized in self.nomenclatura_index:
            idx = self.nomenclatura_index[normalized][0]  # Take first match
            row = self.parts_df.iloc[idx]

            return ComponentMatch(
                codigo=row['codigo'],
                nomenclatura=row.get('nomenclatura', ''),
                designacao_completa=row.get('designacao_completa', ''),
                category=row.get('category', ''),
                peso=self._safe_float(row.get('peso')),
                confidence=100.0,
                match_method="exact_nomenclatura",
                original_text=nomenclatura
            )

        return None

    def _fuzzy_match_nomenclatura(self, nomenclatura: str) -> Optional[ComponentMatch]:
        """Fuzzy matching on nomenclatura field"""
        if pd.isna(nomenclatura) or not nomenclatura.strip():
            return None

        # Get all valid nomenclaturas
        valid_nomenclaturas = self.parts_df[
            self.parts_df['nomenclatura'].notna() &
            (self.parts_df['nomenclatura'].str.len() > 0)
        ]['nomenclatura'].tolist()

        if not valid_nomenclaturas:
            return None

        # Find best match
        result = process.extractOne(nomenclatura, valid_nomenclaturas, scorer=fuzz.ratio)

        if result and result[1] > 85:  # Confidence threshold
            matched_nomenclatura = result[0]
            # Find the row with this nomenclatura
            row = self.parts_df[self.parts_df['nomenclatura'] == matched_nomenclatura].iloc[0]

            return ComponentMatch(
                codigo=row['codigo'],
                nomenclatura=row.get('nomenclatura', ''),
                designacao_completa=row.get('designacao_completa', ''),
                category=row.get('category', ''),
                peso=self._safe_float(row.get('peso')),
                confidence=float(result[1]),
                match_method="fuzzy_nomenclatura",
                original_text=nomenclatura
            )

        return None

    def _fuzzy_match_designacao(self, designacao: str) -> Optional[ComponentMatch]:
        """Fuzzy matching on designacao_completa field"""
        if pd.isna(designacao) or not designacao.strip():
            return None

        # Get all valid designacoes
        valid_designacoes = self.parts_df[
            self.parts_df['designacao_completa'].notna() &
            (self.parts_df['designacao_completa'].str.len() > 10)  # Avoid very short descriptions
        ]['designacao_completa'].tolist()

        if not valid_designacoes:
            return None

        # Find best match
        result = process.extractOne(designacao, valid_designacoes, scorer=fuzz.partial_ratio)

        if result and result[1] > 80:  # Lower threshold for descriptions
            matched_designacao = result[0]
            # Find the row with this designacao
            row = self.parts_df[self.parts_df['designacao_completa'] == matched_designacao].iloc[0]

            return ComponentMatch(
                codigo=row['codigo'],
                nomenclatura=row.get('nomenclatura', ''),
                designacao_completa=row.get('designacao_completa', ''),
                category=row.get('category', ''),
                peso=self._safe_float(row.get('peso')),
                confidence=float(result[1]),
                match_method="fuzzy_designacao",
                original_text=designacao
            )

        return None

    def _match_by_reference(self, ref: str) -> Optional[ComponentMatch]:
        """Match by reference number (could be codigo or nomenclatura)"""
        # Try as codigo first
        match = self._match_by_codigo(ref)
        if match:
            match.match_method = "ref_as_codigo"
            return match

        # Try as nomenclatura
        match = self._match_by_nomenclatura(ref)
        if match:
            match.match_method = "ref_as_nomenclatura"
            return match

        return None

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if pd.isna(value):
            return None
        try:
            # Remove 'Kg/m' or similar units and extract number
            if isinstance(value, str):
                # Extract first number found in string
                numbers = re.findall(r'[\d.]+', value.replace(',', '.'))
                if numbers:
                    return float(numbers[0])
            return float(value)
        except (ValueError, TypeError):
            return None

    def batch_match_components(self, bom_items: List[Dict]) -> List[Dict]:
        """
        Match multiple BOM items at once

        Args:
            bom_items: List of dicts with keys like 'nomenclatura', 'codigo', 'designacao', 'ref'

        Returns:
            List of dicts with original data plus matched component info
        """
        matched_items = []

        for item in bom_items:
            match = self.match_component(
                nomenclatura=item.get('nomenclatura'),
                codigo=item.get('codigo'),
                designacao=item.get('designacao'),
                ref=item.get('ref')
            )

            enhanced_item = item.copy()
            if match:
                enhanced_item.update({
                    'matched_codigo': match.codigo,
                    'matched_nomenclatura': match.nomenclatura,
                    'matched_designacao': match.designacao_completa,
                    'matched_category': match.category,
                    'matched_peso': match.peso,
                    'match_confidence': match.confidence,
                    'match_method': match.match_method
                })
            else:
                enhanced_item.update({
                    'matched_codigo': None,
                    'matched_nomenclatura': None,
                    'matched_designacao': None,
                    'matched_category': None,
                    'matched_peso': None,
                    'match_confidence': 0.0,
                    'match_method': 'no_match'
                })

            matched_items.append(enhanced_item)

        return matched_items

    def get_statistics(self) -> Dict:
        """Get statistics about the parts database"""
        if self.parts_df is None:
            return {"error": "Database not loaded"}

        return {
            "total_components": len(self.parts_df),
            "categories": self.parts_df['category'].value_counts().to_dict(),
            "components_with_peso": self.parts_df['peso'].notna().sum(),
            "components_with_nomenclatura": self.parts_df['nomenclatura'].notna().sum(),
            "unique_categories": self.parts_df['category'].nunique()
        }