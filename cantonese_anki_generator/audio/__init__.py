"""
Audio processing module for segmentation and voice activity detection.
"""

from .loader import AudioLoader, AudioValidationError
from .vad import VoiceActivityDetector, SpeechRegion
from .segmentation import WordSegmenter, WordBoundary
from .clip_generator import AudioClipGenerator
from .processor import AudioProcessor

__all__ = [
    'AudioLoader',
    'AudioValidationError', 
    'VoiceActivityDetector',
    'SpeechRegion',
    'WordSegmenter',
    'WordBoundary',
    'AudioClipGenerator',
    'AudioProcessor'
]