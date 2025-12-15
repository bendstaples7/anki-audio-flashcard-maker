"""
Core data models for the Cantonese Anki Generator.
"""

from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class VocabularyEntry:
    """Represents a vocabulary pair from the Google Docs table."""
    english: str
    cantonese: str
    row_index: int
    confidence: float = 1.0


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