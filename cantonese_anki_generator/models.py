"""
Core data models for the Cantonese Anki Generator.
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class VocabularyEntry:
    """Represents a vocabulary pair from the Google Docs table."""
    english: str
    cantonese: str
    row_index: int = 0
    confidence: float = 1.0
    jyutping: str = ""
    translation_error: Optional[str] = None
    romanization_error: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if entry has all required fields with non-whitespace content."""
        return bool(self.english and self.english.strip() and 
                   self.cantonese and self.cantonese.strip())
    
    def has_errors(self) -> bool:
        """Check if entry has any errors."""
        return bool(self.translation_error or self.romanization_error)


@dataclass
class AudioSegment:
    """Represents a segmented audio clip with timing information."""
    start_time: float
    end_time: float
    audio_data: np.ndarray
    confidence: float
    segment_id: str
    audio_file_path: str = ""  # Path to the saved audio clip file


@dataclass
class AlignedPair:
    """Represents a vocabulary entry matched with its corresponding audio segment."""
    vocabulary_entry: VocabularyEntry
    audio_segment: AudioSegment
    alignment_confidence: float
    audio_file_path: str


@dataclass
class AnkiCard:
    """Represents a complete Anki flashcard with all necessary data."""
    front_text: str  # English
    back_text: str   # Cantonese
    audio_file: str
    tags: List[str]
    card_id: str



@dataclass
class TranslationResult:
    """Result of translation operation."""
    english: str
    cantonese: str
    success: bool
    error: Optional[str] = None
    confidence: float = 1.0


@dataclass
class RomanizationResult:
    """Result of romanization operation."""
    cantonese: str
    jyutping: str
    success: bool
    error: Optional[str] = None


@dataclass
class SheetCreationResult:
    """Result of Google Sheet creation."""
    success: bool
    sheet_url: Optional[str] = None
    sheet_id: Optional[str] = None
    error: Optional[str] = None
