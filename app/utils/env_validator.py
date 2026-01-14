"""Environment variable validation utilities"""
import os
from typing import List, Optional
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_required_env_vars(required_vars: List[str]) -> bool:
    """
    Validate that all required environment variables are set
    
    Args:
        required_vars: List of required environment variable names
        
    Returns:
        True if all variables are set, False otherwise
    """
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True


def get_env_var(var_name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Get environment variable with validation
    
    Args:
        var_name: Name of environment variable
        default: Default value if not set
        required: Whether variable is required
        
    Returns:
        Environment variable value or default
        
    Raises:
        ValueError: If required variable is not set
    """
    value = os.getenv(var_name, default)
    
    if required and not value:
        error_msg = f"Required environment variable '{var_name}' is not set"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return value


def validate_api_keys() -> dict:
    """
    Validate and return status of API keys
    
    Returns:
        Dictionary with API key validation status
    """
    api_keys = {
        'PINECONE_API_KEY': os.getenv('PINECONE_API_KEY'),
        'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY'),
        'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
        'HF_TOKEN': os.getenv('HF_TOKEN')
    }
    
    status = {}
    for key, value in api_keys.items():
        status[key] = bool(value)
        if not value:
            logger.warning(f"API key '{key}' is not set")
    
    return status
