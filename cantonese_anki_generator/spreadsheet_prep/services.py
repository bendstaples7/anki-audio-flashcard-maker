"""
Base service interfaces for spreadsheet preparation.
"""

from abc import ABC, abstractmethod
from typing import List
from cantonese_anki_generator.models import TranslationResult, RomanizationResult


class TranslationService(ABC):
    """Base interface for translation services."""
    
    @abstractmethod
    def translate(self, english_term: str) -> TranslationResult:
        """
        Translate English term to Cantonese.
        
        Args:
            english_term: English word or phrase
            
        Returns:
            TranslationResult with cantonese text or error
        """
        pass
    
    @abstractmethod
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Translate multiple terms efficiently.
        
        Args:
            terms: List of English terms
            
        Returns:
            List of TranslationResult objects
        """
        pass


class RomanizationService(ABC):
    """Base interface for romanization services."""
    
    @abstractmethod
    def romanize(self, cantonese_text: str) -> RomanizationResult:
        """
        Convert Cantonese text to Jyutping romanization.
        
        Args:
            cantonese_text: Chinese characters (Cantonese)
            
        Returns:
            RomanizationResult with jyutping or error
        """
        pass
    
    @abstractmethod
    def romanize_batch(self, texts: List[str]) -> List[RomanizationResult]:
        """
        Romanize multiple texts efficiently.
        
        Args:
            texts: List of Cantonese texts
            
        Returns:
            List of RomanizationResult objects
        """
        pass
