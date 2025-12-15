"""
Configuration settings for the Cantonese Anki Generator.
"""

import os
from pathlib import Path


class Config:
    """Configuration class for application settings."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    OUTPUT_DIR = PROJECT_ROOT / "output"
    TEMP_DIR = PROJECT_ROOT / "temp"
    
    # Audio processing settings
    SAMPLE_RATE = 22050
    AUDIO_FORMATS = [".mp3", ".wav", ".m4a"]
    
    # Google Docs API settings
    GOOGLE_DOCS_SCOPES = [
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]
    CREDENTIALS_FILE = "credentials.json"
    TOKEN_FILE = "token.json"
    
    # Anki settings
    ANKI_MODEL_NAME = "Cantonese Vocabulary"
    ANKI_DECK_NAME = "Cantonese Learning"
    
    # Processing settings
    MIN_AUDIO_DURATION = 0.1  # seconds
    MAX_AUDIO_DURATION = 10.0  # seconds
    ALIGNMENT_CONFIDENCE_THRESHOLD = 0.5
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        for directory in [cls.DATA_DIR, cls.OUTPUT_DIR, cls.TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)