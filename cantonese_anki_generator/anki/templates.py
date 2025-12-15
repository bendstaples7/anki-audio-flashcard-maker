"""
Anki card templates and formatting for Cantonese vocabulary cards.

This module defines the card templates with English front, Cantonese back,
and audio attachment functionality.
"""

import logging
from typing import Dict, Any
import genanki


logger = logging.getLogger(__name__)


class CantoneseCardTemplate:
    """
    Anki card template for Cantonese vocabulary learning.
    
    Creates cards with:
    - Front: English term
    - Back: Cantonese term with audio playback
    """
    
    # Unique model ID for this card type (generated randomly but fixed)
    MODEL_ID = 1607392319
    
    # CSS styling for the cards
    CSS = """
.card {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
    padding: 20px;
}

.front {
    font-size: 24px;
    font-weight: bold;
    color: black;
    margin-bottom: 20px;
}

.back {
    font-size: 28px;
    font-weight: bold;
    color: black;
    margin: 20px 0;
}

.audio-section {
    margin: 20px 0;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 8px;
    border: 1px solid #dee2e6;
}

.audio-label {
    font-size: 14px;
    color: #6c757d;
    margin-bottom: 10px;
}

.tags {
    display: none;
}

/* Mobile responsiveness */
@media (max-width: 480px) {
    .card {
        font-size: 18px;
        padding: 15px;
    }
    
    .front {
        font-size: 22px;
    }
    
    .back {
        font-size: 24px;
    }
}
"""
    
    # Front template (English)
    FRONT_TEMPLATE = """
<div class="card">
    <div class="front">
        {{English}}
    </div>
</div>
"""
    
    # Back template (Cantonese with audio)
    BACK_TEMPLATE = """
<div class="card">
    <div class="front">
        {{English}}
    </div>
    
    <hr>
    
    <div class="back">
        {{Cantonese}}
    </div>
    
    <div class="audio-section">
        <div class="audio-label">🔊 Pronunciation:</div>
        {{Audio}}
    </div>
</div>
"""
    
    @classmethod
    def create_model(cls) -> genanki.Model:
        """
        Create the Anki model (card template) for Cantonese vocabulary.
        
        Returns:
            genanki.Model: Configured Anki model
        """
        logger.info("Creating Cantonese card template model")
        
        model = genanki.Model(
            model_id=cls.MODEL_ID,
            name='Cantonese Vocabulary',
            fields=[
                {'name': 'English'},
                {'name': 'Cantonese'},
                {'name': 'Audio'},
                {'name': 'Tags'},
            ],
            templates=[
                {
                    'name': 'English → Cantonese',
                    'qfmt': cls.FRONT_TEMPLATE,
                    'afmt': cls.BACK_TEMPLATE,
                },
            ],
            css=cls.CSS,
        )
        
        logger.info(f"Created model with ID {cls.MODEL_ID}")
        return model


class CardFormatter:
    """
    Formats vocabulary data into Anki card fields.
    """
    
    @staticmethod
    def format_card_fields(english: str, cantonese: str, audio_filename: str, 
                          tags: list = None) -> Dict[str, Any]:
        """
        Format vocabulary data into Anki card fields.
        
        Args:
            english: English term
            cantonese: Cantonese term
            audio_filename: Name of the audio file (just filename, not full path)
            tags: List of tags for the card
            
        Returns:
            Dictionary with formatted card fields
        """
        # Format tags
        if tags is None:
            tags = ['cantonese', 'vocabulary']
        
        tag_string = ' '.join(tags)
        
        # Format audio field for Anki
        audio_field = f'[sound:{audio_filename}]'
        
        fields = {
            'English': english.strip(),
            'Cantonese': cantonese.strip(),
            'Audio': audio_field,
            'Tags': tag_string,
        }
        
        logger.debug(f"Formatted card: {english} → {cantonese} ({audio_filename})")
        return fields
    
    @staticmethod
    def sanitize_filename(text: str) -> str:
        """
        Sanitize text for use in filenames.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized filename-safe text
        """
        # Remove or replace problematic characters
        import re
        
        # Replace spaces and special characters
        sanitized = re.sub(r'[^\w\-_.]', '_', text)
        
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = 'audio'
        
        return sanitized
    
    @staticmethod
    def generate_audio_filename(english: str, cantonese: str, index: int) -> str:
        """
        Generate a unique audio filename for a vocabulary pair.
        
        Args:
            english: English term
            cantonese: Cantonese term
            index: Index of the term (for uniqueness)
            
        Returns:
            Generated filename
        """
        # Create base name from English term
        base_name = CardFormatter.sanitize_filename(english)
        
        # Add index for uniqueness
        filename = f"{base_name}_{index:03d}.wav"
        
        logger.debug(f"Generated audio filename: {filename}")
        return filename