"""Input validation and sanitization utilities"""
import re
from pathlib import Path
from typing import Optional
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other security issues
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove any directory components
    filename = Path(filename).name
    
    # Remove or replace dangerous characters
    # Keep alphanumeric, dots, hyphens, and underscores
    sanitized = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        sanitized = name[:255-len(ext)] + ext
    
    if not sanitized:
        sanitized = "unnamed_file"
    
    logger.debug(f"Sanitized filename: '{filename}' -> '{sanitized}'")
    return sanitized


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate file extension against allowed list
    
    Args:
        filename: File name to validate
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.docx'])
        
    Returns:
        True if extension is allowed, False otherwise
    """
    ext = Path(filename).suffix.lower()
    is_valid = ext in allowed_extensions
    
    if not is_valid:
        logger.warning(f"Invalid file extension: {ext}. Allowed: {allowed_extensions}")
    
    return is_valid


def sanitize_query(query: str, max_length: int = 1000) -> str:
    """
    Sanitize user query to prevent injection attacks
    
    Args:
        query: User query string
        max_length: Maximum allowed query length
        
    Returns:
        Sanitized query string
    """
    if not query:
        return ""
    
    # Remove null bytes
    query = query.replace('\0', '')
    
    # Limit length
    if len(query) > max_length:
        logger.warning(f"Query truncated from {len(query)} to {max_length} characters")
        query = query[:max_length]
    
    # Strip leading/trailing whitespace
    query = query.strip()
    
    return query


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Session IDs should be UUID4 format (36 characters with hyphens)
    uuid_pattern = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$', re.IGNORECASE)
    
    is_valid = bool(uuid_pattern.match(session_id))
    
    if not is_valid:
        logger.warning(f"Invalid session ID format: {session_id}")
    
    return is_valid


def validate_url(url: str) -> bool:
    """
    Validate URL format and scheme
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Basic URL validation (http/https only)
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    is_valid = bool(url_pattern.match(url))
    
    if not is_valid:
        logger.warning(f"Invalid URL format: {url}")
    
    return is_valid
