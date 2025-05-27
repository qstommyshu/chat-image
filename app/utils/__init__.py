"""
Utilities Package

Contains utility functions and helper classes for HTML processing
and image extraction in direct memory processing mode.
"""

from .html_utils import *

# Core functions for direct memory processing
__all__ = [
    'fix_image_paths',          # Essential: Converts relative to absolute URLs
    'get_image_format',         # Essential: Detects image file formats  
    'extract_context',          # Essential: Extracts context from img tags
    'extract_context_from_source',  # Essential: Extracts context from source tags
] 