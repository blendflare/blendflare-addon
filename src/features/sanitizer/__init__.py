"""Blend file sanitization module.

This module provides tools for removing potentially dangerous scripts and drivers
from .blend files before importing them into the current session.
"""

from .sanitizer import BlendSanitizer, get_sanitizer
from .post_import import cleanup_after_import

__all__ = ["BlendSanitizer", "get_sanitizer", "cleanup_after_import"]
