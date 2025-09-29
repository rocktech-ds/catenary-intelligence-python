"""
Text Processing Utilities
Comprehensive text normalization, parsing, and cleaning for Portuguese engineering documents
"""
import re
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import unicodedata

def norm_space(s: str) -> str:
    """Normalize whitespace in text"""
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def clean_text(text: str) -> str:
    """Clean and normalize text for processing"""
    if not text:
        return ""
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Fix common OCR errors in Portuguese
    text = text.replace('ç', 'ç').replace('ã', 'ã').replace('õ', 'õ')
    text = text.replace('á', 'á').replace('é', 'é').replace('í', 'í')
    text = text.replace('ó', 'ó').replace('ú', 'ú').replace('â', 'â')
    text = text.replace('ê', 'ê').replace('ô', 'ô')
    
    # Normalize whitespace and remove control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', text)
    text = norm_space(text)
    
    return text

def extract_numbers(text: str) -> List[str]:
    """Extract all numbers from text"""
    return re.findall(r'\d+(?:\.\d+)?', text)

def extract_codes(text: str) -> Dict[str, List[str]]:
    """Extract various engineering codes from text"""
    codes = {
        'sap_codes': re.findall(r'\b\d{8,12}\b', text),  # 8-12 digit SAP codes
        'project_codes': re.findall(r'\b[A-Z]-\d{2,4}\b', text),  # C-160 format
        'drawing_codes': re.findall(r'\b[A-Z]\d{4,6}\b', text),  # E6190 format
        'ref_codes': re.findall(r'\bREF\.?\s*(\d+[A-Z]?)\b', text, re.I),
        'part_codes': re.findall(r'\b\d{5,8}\b', text)  # 5-8 digit part numbers
    }
    return codes

# Date patterns for Portuguese documents
DATE_PATTERNS = [
    r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b',  # DD/MM/YYYY or DD-MM-YYYY
    r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b',  # YYYY/MM/DD or YYYY-MM-DD
    r'\b(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\b',  # DD de mês de YYYY
]

MONTH_NAMES_PT = {
    'janeiro': '01', 'jan': '01',
    'fevereiro': '02', 'fev': '02',
    'março': '03', 'mar': '03',
    'abril': '04', 'abr': '04',
    'maio': '05', 'mai': '05',
    'junho': '06', 'jun': '06',
    'julho': '07', 'jul': '07',
    'agosto': '08', 'ago': '08',
    'setembro': '09', 'set': '09',
    'outubro': '10', 'out': '10',
    'novembro': '11', 'nov': '11',
    'dezembro': '12', 'dez': '12'
}

def parse_date(text: str) -> Optional[str]:
    """Parse Portuguese date formats and return ISO format (YYYY-MM-DD)"""
    if not text:
        return None
    
    text = text.lower().strip()
    
    # Try DD/MM/YYYY or DD-MM-YYYY
    for pattern in DATE_PATTERNS[:2]:
        match = re.search(pattern, text)
        if match:
            if len(match.group(3)) == 4:  # DD/MM/YYYY
                day, month, year = match.groups()
            else:  # YYYY/MM/DD
                year, month, day = match.groups()
            
            try:
                day = int(day)
                month = int(month)
                year = int(year)
                
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                continue
    
    # Try Portuguese month names
    match = re.search(DATE_PATTERNS[2], text, re.I)
    if match:
        day_str, month_str, year_str = match.groups()
        month_num = MONTH_NAMES_PT.get(month_str.lower())
        if month_num:
            try:
                day = int(day_str)
                year = int(year_str)
                if 1 <= day <= 31 and 1900 <= year <= 2100:
                    return f"{year:04d}-{month_num}-{day:02d}"
            except ValueError:
                pass
    
    return None

def extract_version(text: str) -> Optional[str]:
    """Extract version from text (e.g., '01', 'v1.0', 'Rev A')"""
    patterns = [
        r'versão\s*:?\s*([0-9]+(?:\.[0-9]+)?)',
        r'rev\.?\s*([A-Z0-9]+)',
        r'v\.?\s*([0-9]+(?:\.[0-9]+)?)',
        r'\b([0-9]{2})\b(?=\s*$)',  # Two digits at end
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            return match.group(1)
    
    return None

def extract_sap_number(text: str) -> Optional[str]:
    """Extract SAP number from text"""
    patterns = [
        r'n\.?º?\s*sap\s*:?\s*([0-9]{8,12})',
        r'sap\s*:?\s*([0-9]{8,12})',
        r'\b([0-9]{10,12})\b',  # Standalone 10-12 digit numbers
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.I)
        if match:
            return match.group(1)
    
    return None

def split_sentences(text: str) -> List[str]:
    """Split text into sentences, respecting Portuguese punctuation"""
    if not text:
        return []
    
    # Handle common abbreviations that shouldn't split sentences
    text = re.sub(r'\bN\.º', 'N°', text)  # Temporarily replace
    text = re.sub(r'\bRef\.', 'Ref°', text)
    text = re.sub(r'\bProj\.', 'Proj°', text)
    
    # Split on sentence boundaries
    sentences = re.split(r'[.!?]+\s+', text)
    
    # Restore abbreviations
    sentences = [s.replace('N°', 'N.º').replace('Ref°', 'Ref.').replace('Proj°', 'Proj.') 
                for s in sentences]
    
    return [s.strip() for s in sentences if s.strip()]

def fuzzy_match(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """Simple fuzzy matching for text comparison"""
    if not text1 or not text2:
        return False
    
    # Normalize both texts
    t1 = clean_text(text1.lower())
    t2 = clean_text(text2.lower())
    
    if t1 == t2:
        return True
    
    # Simple character-based similarity
    longer = t1 if len(t1) > len(t2) else t2
    shorter = t2 if len(t1) > len(t2) else t1
    
    if len(longer) == 0:
        return True
    
    # Count matching characters
    matches = sum(1 for a, b in zip(shorter, longer) if a == b)
    similarity = matches / len(longer)
    
    return similarity >= threshold

def extract_title_from_text(text: str) -> Optional[str]:
    """Extract title from engineering drawing text"""
    # Common title patterns in Portuguese engineering drawings
    title_patterns = [
        r'AMARRAÇ[ÕO]ES?\s+.*?ISOLAMENTO.*',
        r'CATEN[ÁA]RIA\s+E\s+ENERGIA.*',
        r'SUBESTAÇÃO.*',
        r'LINHA\s+.*?CONTACTO.*',
        r'SINALIZAÇÃO.*',
        r'VIA\s+.*',
        r'OBRAS\s+DE\s+ARTE.*',
    ]
    
    text_upper = text.upper()
    for pattern in title_patterns:
        match = re.search(pattern, text_upper, re.I)
        if match:
            return clean_text(match.group(0))
    
    return None

def extract_specialty(text: str) -> Optional[str]:
    """Extract engineering specialty from text"""
    specialties = {
        'CATENÁRIA E ENERGIA': ['catenária', 'energia', 'elétric', 'tensão', 'feeder'],
        'SINALIZAÇÃO': ['sinal', 'comando', 'controlo', 'semáforo'],
        'VIA': ['via', 'carril', 'balastro', 'travessa'],
        'OBRAS DE ARTE': ['ponte', 'túnel', 'viaduto', 'estrutura'],
        'TELECOMUNICAÇÕES': ['telecom', 'fibra', 'cabo', 'comunicação'],
    }
    
    text_lower = text.lower()
    for specialty, keywords in specialties.items():
        if any(keyword in text_lower for keyword in keywords):
            return specialty
    
    return None

def clean_table_cell(cell_value: str) -> Optional[str]:
    """Clean and normalize table cell values"""
    if not cell_value:
        return None
    
    cleaned = clean_text(str(cell_value))
    
    # Handle common empty indicators
    if cleaned in ['', '-', '—', '–', 'N/A', 'n/a', 'null', 'NULL']:
        return None
    
    return cleaned

def extract_authors(text: str) -> Dict[str, Optional[str]]:
    """Extract author information from text"""
    authors = {
        'projectist': None,
        'director': None,
        'others': []
    }
    
    # Patterns for different author roles
    patterns = {
        'projectist': [
            r'project[oi]st[ae]?\s*:?\s*([^\n\r,]+)',
            r'proj\.?\s*:?\s*([^\n\r,]+)',
        ],
        'director': [
            r'dire[cç][aã]o\s*:?\s*([^\n\r,]+)',
            r'diretor\s*:?\s*([^\n\r,]+)',
        ]
    }
    
    text_lower = text.lower()
    
    for role, role_patterns in patterns.items():
        for pattern in role_patterns:
            match = re.search(pattern, text_lower, re.I)
            if match:
                name = clean_text(match.group(1))
                if name:
                    authors[role] = name
                break
    
    return authors

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts (0.0 to 1.0)"""
    if not text1 or not text2:
        return 0.0
    
    t1 = set(clean_text(text1.lower()).split())
    t2 = set(clean_text(text2.lower()).split())
    
    if not t1 and not t2:
        return 1.0
    
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    
    return intersection / union if union > 0 else 0.0