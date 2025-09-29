"""
Target JSON Schemas for Engineering Drawing Extraction
Matches your exact requirements from the example JSON
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

# Target schemas matching your example JSON exactly

class AuthorBlock(BaseModel):
    """Authors section of the document"""
    projectist: Optional[str] = None
    director: Optional[str] = None
    others: List[str] = Field(default_factory=list)

class TitleBlock(BaseModel):
    """Title block key-value pairs"""
    fields: Dict[str, Optional[str]] = Field(default_factory=dict)

class TableRow(BaseModel):
    """Single row in BOM table"""
    # Using exact column names from your example
    pass  # Will be Dict[str, Optional[str]] with dynamic keys

class TableBlock(BaseModel):
    """Table structure (BOM, parts list, etc.)"""
    name: str
    columns: List[str]
    rows: List[Dict[str, Optional[str]]] = Field(default_factory=list)

class CalloutGeometry(BaseModel):
    """Callout position geometry"""
    x: float
    y: float

class Callout(BaseModel):
    """Drawing callout/annotation"""
    text: str
    targets: List[str] = Field(default_factory=list)
    geometry: CalloutGeometry

class Assembly(BaseModel):
    """Assembly or component group"""
    name: str
    code: Optional[str] = None

class RevisionEntry(BaseModel):
    """Revision history entry"""
    change: str
    by: Optional[str] = None
    date: Optional[str] = None

class PageResult(BaseModel):
    """Single page analysis results"""
    page_index: int
    title_block: Optional[TitleBlock] = None
    tables: List[TableBlock] = Field(default_factory=list)
    callouts: List[Callout] = Field(default_factory=list)
    assemblies: List[Assembly] = Field(default_factory=list)
    revision_history: List[RevisionEntry] = Field(default_factory=list)

class DocumentResult(BaseModel):
    """Document-level metadata"""
    file_name: str
    language: Optional[str] = "pt"
    title: Optional[str] = None
    specialty: Optional[str] = None
    sap_number: Optional[str] = None
    version: Optional[str] = None
    project_code: Optional[str] = None
    date: Optional[str] = None  # Format: YYYY-MM-DD
    authors: Optional[AuthorBlock] = None

class FinalResult(BaseModel):
    """Complete extraction result matching your exact JSON format"""
    document: DocumentResult
    pages: List[PageResult]

# LLM-specific schemas for structured extraction

TITLE_BLOCK_SCHEMA = {
    "sap_number": "string|null",
    "version": "string|null", 
    "date": "YYYY-MM-DD|null",
    "project_code": "string|null",
    "specialty": "string|null",
    "title": "string|null",
    "fields": {
        "N.º SAP": "string|null",
        "Versão": "string|null", 
        "Data": "string|null"
    }
}

TABLE_HEADER_SCHEMA = {
    "canonical_headers": ["REF.", "DESIGNAÇÃO", "Nº DESENHO", "NOMENCLAT.", "OBSERVAÇÕES", "PESO (Kg)", "CÓDIGO", "QUANTIDADE"],
    "mapping": {"original_header": "canonical_header"},
    "confidence": "number"
}

CALLOUT_SCHEMA = {
    "callouts": [
        {
            "text": "string",
            "normalized": "string|null", 
            "ref": "string|null",
            "geometry": {"x": "number", "y": "number"}
        }
    ]
}

ASSEMBLY_SCHEMA = {
    "assemblies": [
        {
            "name": "string",
            "code": "string|null"
        }
    ]
}

REVISION_SCHEMA = {
    "revisions": [
        {
            "change": "string",
            "by": "string|null",
            "date": "string|null"
        }
    ]
}

# Portuguese engineering patterns for LLM prompts
PORTUGUESE_PATTERNS = {
    "title_cues": [
        r"AMARRAÇ(ÕES|AO).*ISOLAMENTO",
        r"CATEN[ÁA]RIA.*ENERGIA",
        r"SUBESTAÇÃO",
        r"LINHA.*CONTACTO",
        r"SINALIZAÇÃO"
    ],
    "specialty_terms": {
        "CATENÁRIA E ENERGIA": ["catenária", "energia", "elétric", "tensão"],
        "SINALIZAÇÃO": ["sinal", "comando", "controlo"],
        "VIA": ["via", "carril", "balastro"],
        "OBRAS DE ARTE": ["ponte", "túnel", "viaduto"]
    },
    "revision_verbs": [
        "Substituição", "Retirada", "Correções", "Alteração",
        "Adição", "Modificação", "Atualização"
    ]
}

# Standard BOM column mappings
BOM_COLUMN_MAPPINGS = {
    # Portuguese variations to canonical
    "REF": "REF.",
    "REFERÊNCIA": "REF.", 
    "DESIGNAÇÃO": "DESIGNAÇÃO",
    "DESCRIÇÃO": "DESIGNAÇÃO",
    "N.º DESENHO": "Nº DESENHO",
    "DESENHO": "Nº DESENHO",
    "NOMENCLAT": "NOMENCLAT.",
    "NOMENCLATURA": "NOMENCLAT.",
    "OBSERVAÇÕES": "OBSERVAÇÕES",
    "OBS": "OBSERVAÇÕES",
    "PESO": "PESO (Kg)",
    "PESO (KG)": "PESO (Kg)",
    "CÓDIGO": "CÓDIGO",
    "COD": "CÓDIGO",
    "QUANTIDADE": "QUANTIDADE",
    "QTD": "QUANTIDADE",
    "QUANT": "QUANTIDADE"
}