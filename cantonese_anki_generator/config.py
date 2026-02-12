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
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/spreadsheets"  # Write access for spreadsheet preparation
    ]
    CREDENTIALS_FILE = "credentials.json"
    TOKEN_FILE = "token.json"
    
    # Web authentication settings
    OAUTH_REDIRECT_URI = os.environ.get(
        'OAUTH_REDIRECT_URI',
        'http://localhost:3000/api/auth/callback'
    )
    """
    OAuth redirect URI for web-based authentication flow.
    
    Can be configured via OAUTH_REDIRECT_URI environment variable.
    Default: http://localhost:3000/api/auth/callback (development)
    Production example: https://yourdomain.com/api/auth/callback
    """
    
    TOKEN_REFRESH_THRESHOLD_HOURS = 24
    """Threshold in hours before token expiration to trigger proactive refresh."""
    
    BACKGROUND_MONITOR_INTERVAL_HOURS = 6
    """Interval in hours for background token monitoring task."""
    
    STATE_TOKEN_EXPIRATION_MINUTES = 10
    """Expiration time in minutes for OAuth state tokens (CSRF protection)."""
    
    # Anki settings
    ANKI_MODEL_NAME = "Cantonese Vocabulary"
    ANKI_DECK_NAME = "Cantonese Learning"
    
    # Processing settings
    MIN_AUDIO_DURATION = 0.1  # seconds
    MAX_AUDIO_DURATION = 10.0  # seconds
    ALIGNMENT_CONFIDENCE_THRESHOLD = 0.5
    
    # Spreadsheet preparation settings
    TRANSLATION_API_TIMEOUT = 30  # seconds
    TRANSLATION_BATCH_SIZE = 50  # max terms per batch
    ROMANIZATION_BACKEND = 'espeak'  # phonemizer backend
    ROMANIZATION_LANGUAGE = 'yue'  # Cantonese language code
    ROMANIZATION_PRESERVE_PUNCTUATION = True
    SPREADSHEET_EXPORT_TIMEOUT = 30  # seconds
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        for directory in [cls.DATA_DIR, cls.OUTPUT_DIR, cls.TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)