"""
Translation service for converting English terms to Cantonese.

This module provides translation service implementations using Google Cloud
Translation API. Falls back to mock implementation if API is not available.
"""

import logging
import os
from typing import List, Optional

from cantonese_anki_generator.models import TranslationResult
from cantonese_anki_generator.spreadsheet_prep.services import TranslationService


class GoogleTranslationService(TranslationService):
    """
    Translation service using Google Translate via googletrans library.
    
    This is a free service that doesn't require an API key.
    Falls back to mock implementation if googletrans is not available.
    """
    
    def __init__(self):
        """Initialize the translation service."""
        self.logger = logging.getLogger(__name__)
        
        try:
            from googletrans import Translator
            self.translator = Translator()
            self.use_real_api = True
            self.logger.info("Google Translation service initialized successfully")
        except ImportError:
            self.logger.warning(
                "googletrans library not installed. Using mock translations. "
                "Install with: pip install googletrans==4.0.0-rc1"
            )
            self.use_real_api = False
            self.translator = None
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Translate: {e}")
            self.use_real_api = False
            self.translator = None
    
    def translate(self, english_term: str) -> TranslationResult:
        """
        Translate English term to Cantonese.
        
        Args:
            english_term: English word or phrase
            
        Returns:
            TranslationResult with cantonese text or error
        """
        if not english_term or not english_term.strip():
            return TranslationResult(
                english=english_term,
                cantonese="",
                success=False,
                error="Empty or whitespace-only input"
            )
        
        if self.use_real_api and self.translator:
            try:
                # Translate to Traditional Chinese (Hong Kong) for Cantonese
                result = self.translator.translate(
                    english_term,
                    src='en',
                    dest='zh-tw'  # Traditional Chinese
                )
                
                return TranslationResult(
                    english=english_term,
                    cantonese=result.text,
                    success=True,
                    confidence=0.9
                )
            except Exception as e:
                self.logger.error(f"Translation failed for '{english_term}': {e}")
                return TranslationResult(
                    english=english_term,
                    cantonese="",
                    success=False,
                    error=f"Translation API error: {str(e)}"
                )
        else:
            # Mock translation fallback
            mock_translation = f"[Mock: {english_term}]"
            return TranslationResult(
                english=english_term,
                cantonese=mock_translation,
                success=True,
                confidence=0.5
            )
    
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Translate multiple terms efficiently.
        
        Args:
            terms: List of English terms
            
        Returns:
            List of TranslationResult objects
        """
        if not terms:
            return []
        
        # Process each term individually to ensure error isolation
        # (failures in one term don't affect others)
        results = []
        for term in terms:
            result = self.translate(term)
            results.append(result)
        
        return results


class MockTranslationService(TranslationService):
    """
    Mock translation service for development and testing.
    
    Returns placeholder text instead of real translations.
    """
    
    def __init__(self):
        """Initialize the translation service."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Mock translation service initialized")
    
    def translate(self, english_term: str) -> TranslationResult:
        """
        Translate English term to Cantonese.
        
        Args:
            english_term: English word or phrase
            
        Returns:
            TranslationResult with cantonese text or error
        """
        if not english_term or not english_term.strip():
            return TranslationResult(
                english=english_term,
                cantonese="",
                success=False,
                error="Empty or whitespace-only input"
            )
        
        # Mock translation - return placeholder
        mock_translation = f"[Mock: {english_term}]"
        
        return TranslationResult(
            english=english_term,
            cantonese=mock_translation,
            success=True,
            confidence=0.9
        )
    
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Translate multiple terms efficiently.
        
        Args:
            terms: List of English terms
            
        Returns:
            List of TranslationResult objects
        """
        if not terms:
            return []
        
        # Process each term individually to ensure error isolation
        # (failures in one term don't affect others)
        results = []
        for term in terms:
            result = self.translate(term)
            results.append(result)
        
        return results
