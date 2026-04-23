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
    Translation service using Google Translation API.
    
    Translates English to Cantonese (Traditional Chinese) using the
    Google Cloud Translation API.
    
    Initialization order:
    1. Try google-cloud-translate with service account credentials
    2. Fall back to googleapiclient with existing OAuth credentials (token.json)
    3. Report failure if neither is available
    """
    
    def __init__(self):
        """Initialize the translation service."""
        self.logger = logging.getLogger(__name__)
        self.use_real_api = False
        self.translator = None
        self._backend = None  # 'cloud' or 'oauth'
        
        # Try google-cloud-translate first (service account)
        if self._init_cloud_translate():
            return
        
        # Fall back to googleapiclient with OAuth credentials
        if self._init_oauth_translate():
            return
        
        self.logger.warning(
            "No translation backend available. "
            "Install google-cloud-translate or ensure OAuth token.json exists."
        )
    
    def _init_cloud_translate(self) -> bool:
        """Try to initialize google-cloud-translate with service account."""
        try:
            from google.cloud import translate_v2 as translate
            from google.auth import default
            from google.auth.transport.requests import AuthorizedSession
            from requests.adapters import HTTPAdapter
            from cantonese_anki_generator.config import Config
            
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_path:
                return False
            
            credentials, project = default()
            
            class TimeoutHTTPAdapter(HTTPAdapter):
                def __init__(self, timeout, *args, **kwargs):
                    self.timeout = timeout
                    super().__init__(*args, **kwargs)
                
                def send(self, request, **kwargs):
                    kwargs['timeout'] = kwargs.get('timeout') or self.timeout
                    return super().send(request, **kwargs)
            
            http_session = AuthorizedSession(credentials)
            adapter = TimeoutHTTPAdapter(timeout=Config.TRANSLATION_API_TIMEOUT)
            http_session.mount('https://', adapter)
            http_session.mount('http://', adapter)
            
            self.translator = translate.Client(_http=http_session)
            self.target_language = 'yue'
            self.use_real_api = True
            self._backend = 'cloud'
            self.logger.info("Translation service initialized with google-cloud-translate (Cantonese/yue)")
            return True
            
        except ImportError:
            return False
        except Exception as e:
            self.logger.error(f"Failed to initialize google-cloud-translate: {e}")
            return False
    
    def _init_oauth_translate(self) -> bool:
        """Try to initialize translation using existing OAuth credentials."""
        try:
            from cantonese_anki_generator.processors.google_docs_auth import GoogleDocsAuthenticator
            
            auth = GoogleDocsAuthenticator()
            if not auth.authenticate():
                self.logger.warning("OAuth authentication failed for translation service")
                return False
            
            from googleapiclient.discovery import build
            self._translate_service = build('translate', 'v2', credentials=auth._credentials)
            self.use_real_api = True
            self._backend = 'oauth'
            self.logger.info("Translation service initialized with OAuth credentials (translate API v2)")
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize OAuth translation: {e}")
            return False
    
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
        
        if not self.use_real_api:
            return TranslationResult(
                english=english_term,
                cantonese="",
                success=False,
                error=(
                    "Translation API not available. "
                    "Set GOOGLE_APPLICATION_CREDENTIALS to your service account key file, "
                    "or ensure OAuth token.json exists."
                )
            )
        
        try:
            if self._backend == 'cloud':
                return self._translate_cloud(english_term)
            elif self._backend == 'oauth':
                return self._translate_oauth(english_term)
            else:
                return TranslationResult(
                    english=english_term,
                    cantonese="",
                    success=False,
                    error="No translation backend configured"
                )
        except Exception as e:
            self.logger.error(f"Translation failed for '{english_term}': {e}")
            return TranslationResult(
                english=english_term,
                cantonese="",
                success=False,
                error=f"Translation error: {str(e)}"
            )
    
    def _translate_cloud(self, english_term: str) -> TranslationResult:
        """Translate using google-cloud-translate."""
        result = self.translator.translate(
            english_term,
            target_language=self.target_language,
            source_language='en'
        )
        return TranslationResult(
            english=english_term,
            cantonese=result['translatedText'],
            success=True,
            confidence=0.9
        )
    
    def _translate_oauth(self, english_term: str) -> TranslationResult:
        """Translate using googleapiclient with OAuth credentials."""
        result = self._translate_service.translations().list(
            q=english_term,
            target='zh-TW',
            source='en'
        ).execute()
        
        translations = result.get('translations', [])
        if translations:
            translated = translations[0].get('translatedText', '')
            if translated:
                return TranslationResult(
                    english=english_term,
                    cantonese=translated,
                    success=True,
                    confidence=0.85
                )
        
        return TranslationResult(
            english=english_term,
            cantonese="",
            success=False,
            error="Translation returned empty result"
        )
    
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Translate multiple terms efficiently.
        
        Maximum batch size is 50 terms. Larger batches will raise ValueError.
        
        Args:
            terms: List of English terms (max 50)
            
        Returns:
            List of TranslationResult objects
            
        Raises:
            ValueError: If terms list exceeds 50 items
        """
        if not terms:
            return []
        
        # Enforce maximum batch size (Requirement 3.1)
        from cantonese_anki_generator.config import Config
        max_batch_size = Config.TRANSLATION_BATCH_SIZE
        
        if len(terms) > max_batch_size:
            raise ValueError(
                f"Batch size {len(terms)} exceeds maximum allowed size of {max_batch_size} terms. "
                f"Please split your request into smaller batches."
            )
        
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
        
        Maximum batch size is 50 terms. Larger batches will raise ValueError.
        
        Args:
            terms: List of English terms (max 50)
            
        Returns:
            List of TranslationResult objects
            
        Raises:
            ValueError: If terms list exceeds 50 items
        """
        if not terms:
            return []
        
        # Enforce maximum batch size (Requirement 3.1)
        from cantonese_anki_generator.config import Config
        max_batch_size = Config.TRANSLATION_BATCH_SIZE
        
        if len(terms) > max_batch_size:
            raise ValueError(
                f"Batch size {len(terms)} exceeds maximum allowed size of {max_batch_size} terms. "
                f"Please split your request into smaller batches."
            )
        
        # Process each term individually to ensure error isolation
        # (failures in one term don't affect others)
        results = []
        for term in terms:
            result = self.translate(term)
            results.append(result)
        
        return results
