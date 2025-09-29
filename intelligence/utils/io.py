"""
File I/O Utilities
Temporary file handling, validation, and cleanup for PDF processing
"""
import os
import tempfile
from pathlib import Path
from typing import Optional, BinaryIO, Union
import mimetypes
import hashlib
import shutil
from loguru import logger

def create_temp_pdf(raw_bytes: bytes, suffix: str = ".pdf") -> str:
    """Create a temporary PDF file from raw bytes"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(raw_bytes)
        temp_file.flush()
        return temp_file.name
    finally:
        temp_file.close()

def cleanup_temp_file(file_path: Union[str, Path]) -> None:
    """Safely cleanup a temporary file"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temporary file {file_path}: {e}")

def validate_pdf_file(file_path: Union[str, Path]) -> bool:
    """Validate that a file is a valid PDF"""
    try:
        with open(file_path, 'rb') as f:
            # Check PDF header
            header = f.read(5)
            if not header.startswith(b'%PDF-'):
                return False
            
            # Check for PDF footer (simplified check)
            f.seek(-50, 2)  # Seek to near end
            tail = f.read()
            if b'%%EOF' not in tail:
                logger.warning(f"PDF file may be corrupted: {file_path}")
                # Still return True as some valid PDFs might not have proper EOF
        
        return True
    except Exception as e:
        logger.error(f"Error validating PDF file {file_path}: {e}")
        return False

def get_file_size_mb(file_path: Union[str, Path]) -> float:
    """Get file size in megabytes"""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 0.0

def calculate_file_hash(file_path: Union[str, Path]) -> str:
    """Calculate SHA-256 hash of file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return ""

def ensure_directory_exists(directory: Union[str, Path]) -> Path:
    """Ensure a directory exists, create if necessary"""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path

def copy_file_to_temp_dir(source_path: Union[str, Path], temp_dir: Optional[Union[str, Path]] = None) -> str:
    """Copy a file to temporary directory and return new path"""
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    
    ensure_directory_exists(temp_dir)
    
    source = Path(source_path)
    temp_path = Path(temp_dir) / f"temp_{os.getpid()}_{source.name}"
    
    shutil.copy2(source, temp_path)
    return str(temp_path)

def get_mime_type(file_path: Union[str, Path]) -> Optional[str]:
    """Get MIME type of file"""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type

def is_pdf_file(file_path: Union[str, Path]) -> bool:
    """Check if file is a PDF based on extension and MIME type"""
    path = Path(file_path)
    if path.suffix.lower() != '.pdf':
        return False
    
    mime_type = get_mime_type(file_path)
    return mime_type == 'application/pdf'

def safe_filename(filename: str, max_length: int = 255) -> str:
    """Create a safe filename by removing invalid characters"""
    # Remove/replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        filename = name[:max_name_length] + ext
    
    return filename

class TempFileContext:
    """Context manager for temporary file handling"""
    
    def __init__(self, raw_bytes: bytes, suffix: str = ".pdf"):
        self.raw_bytes = raw_bytes
        self.suffix = suffix
        self.file_path: Optional[str] = None
    
    def __enter__(self) -> str:
        self.file_path = create_temp_pdf(self.raw_bytes, self.suffix)
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path:
            cleanup_temp_file(self.file_path)

class TempDirectoryContext:
    """Context manager for temporary directory handling"""
    
    def __init__(self, prefix: str = "pdfxtract_"):
        self.prefix = prefix
        self.dir_path: Optional[str] = None
    
    def __enter__(self) -> str:
        self.dir_path = tempfile.mkdtemp(prefix=self.prefix)
        return self.dir_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.dir_path:
            try:
                shutil.rmtree(self.dir_path)
                logger.debug(f"Cleaned up temporary directory: {self.dir_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary directory {self.dir_path}: {e}")

def read_file_chunks(file_path: Union[str, Path], chunk_size: int = 8192):
    """Generator to read file in chunks"""
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def write_bytes_to_file(data: bytes, file_path: Union[str, Path]) -> bool:
    """Write bytes to file safely"""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            f.write(data)
        
        return True
    except Exception as e:
        logger.error(f"Error writing bytes to file {file_path}: {e}")
        return False

def append_to_log_file(log_path: Union[str, Path], message: str) -> bool:
    """Append message to log file"""
    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'a', encoding='utf-8') as f:
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
        
        return True
    except Exception as e:
        logger.error(f"Error writing to log file {log_path}: {e}")
        return False

def get_disk_usage(path: Union[str, Path]) -> dict:
    """Get disk usage statistics for a path"""
    try:
        stat = shutil.disk_usage(path)
        return {
            'total_gb': stat.total / (1024**3),
            'used_gb': (stat.total - stat.free) / (1024**3),
            'free_gb': stat.free / (1024**3),
            'percent_used': ((stat.total - stat.free) / stat.total) * 100
        }
    except Exception as e:
        logger.error(f"Error getting disk usage for {path}: {e}")
        return {
            'total_gb': 0,
            'used_gb': 0,
            'free_gb': 0,
            'percent_used': 0
        }