"""
Anki package generation module for Cantonese vocabulary cards.

This module provides functionality to create complete .apkg files with
embedded audio and proper card templates.
"""

from .templates import CantoneseCardTemplate, CardFormatter
from .package_generator import AnkiPackageGenerator, PackageValidator
from .naming import UniqueNamingManager, ConflictDetector

__all__ = [
    'CantoneseCardTemplate',
    'CardFormatter', 
    'AnkiPackageGenerator',
    'PackageValidator',
    'UniqueNamingManager',
    'ConflictDetector'
]