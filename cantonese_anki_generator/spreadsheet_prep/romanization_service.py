"""
Romanization service for converting Cantonese text to Jyutping.

This module provides romanization service implementations using pycantonese
for accurate Cantonese Jyutping romanization.
"""

import logging
from typing import List

from cantonese_anki_generator.models import RomanizationResult
from cantonese_anki_generator.spreadsheet_prep.services import RomanizationService


class PyCantoneseRomanizationService(RomanizationService):
    """
    Romanization service using pycantonese for Cantonese Jyutping.
    
    Uses pycantonese library which provides accurate Cantonese-specific
    Jyutping romanization with tone numbers.
    """
    
    def __init__(self):
        """Initialize the romanization service with pycantonese."""
        self.logger = logging.getLogger(__name__)
        
        try:
            import pycantonese
            self.pycantonese = pycantonese
            self.use_pycantonese = True
            self.logger.info("Romanization service initialized with pycantonese (Cantonese Jyutping)")
        except ImportError:
            self.logger.error("pycantonese library not installed. Install with: pip install pycantonese")
            self.use_pycantonese = False
            self.pycantonese = None
    
    def romanize(self, cantonese_text: str) -> RomanizationResult:
        """
        Convert Cantonese text to Jyutping romanization.
        
        Args:
            cantonese_text: Chinese characters (Cantonese)
            
        Returns:
            RomanizationResult with jyutping or error
        """
        if not cantonese_text or not cantonese_text.strip():
            return RomanizationResult(
                cantonese=cantonese_text,
                jyutping="",
                success=False,
                error="Empty or whitespace-only input"
            )
        
        if not self.use_pycantonese:
            return RomanizationResult(
                cantonese=cantonese_text,
                jyutping="",
                success=False,
                error="Romanization backend not initialized"
            )
        
        try:
            # Use pycantonese to convert Cantonese text to Jyutping
            # characters_to_jyutping returns a list of tuples: (character, jyutping)
            jyutping_data = self.pycantonese.characters_to_jyutping(cantonese_text)
            
            # Extract just the jyutping romanizations and join with spaces
            jyutping_list = []
            for char, jyutping in jyutping_data:
                if jyutping:
                    # Use the jyutping romanization
                    jyutping_list.append(jyutping)
                else:
                    # If no jyutping found for this character, keep the character
                    jyutping_list.append(char)
            
            romanization = ' '.join(jyutping_list)
            
            # Check if romanization produced output
            if not romanization or not romanization.strip():
                return RomanizationResult(
                    cantonese=cantonese_text,
                    jyutping="",
                    success=False,
                    error="Romanization produced no output"
                )
            
            return RomanizationResult(
                cantonese=cantonese_text,
                jyutping=romanization.strip(),
                success=True,
                error=None
            )
            
        except Exception as e:
            self.logger.error(f"Romanization failed for '{cantonese_text}': {e}")
            return RomanizationResult(
                cantonese=cantonese_text,
                jyutping="",
                success=False,
                error=f"Romanization error: {str(e)}"
            )
    
    def romanize_batch(self, texts: List[str]) -> List[RomanizationResult]:
        """
        Romanize multiple texts efficiently.
        
        Args:
            texts: List of Cantonese texts
            
        Returns:
            List of RomanizationResult objects
        """
        if not texts:
            return []
        
        # Process each text individually to ensure error isolation
        # (failures in one text don't affect others)
        results = []
        for text in texts:
            result = self.romanize(text)
            results.append(result)
        
        return results
