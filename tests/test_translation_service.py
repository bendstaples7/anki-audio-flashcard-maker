"""
Property-based tests for translation service.

Tests the translation service to ensure it handles all terms correctly,
including error cases and batch processing.
"""

import pytest
from hypothesis import given, strategies as st
from typing import List

from cantonese_anki_generator.models import TranslationResult
from cantonese_anki_generator.spreadsheet_prep.services import TranslationService


class MockTranslationService(TranslationService):
    """Mock translation service for testing."""
    
    def __init__(self, fail_terms: List[str] = None):
        """
        Initialize mock translation service.
        
        Args:
            fail_terms: List of terms that should fail translation
        """
        self.fail_terms = fail_terms or []
    
    def translate(self, english_term: str) -> TranslationResult:
        """
        Mock translate method.
        
        Args:
            english_term: English word or phrase
            
        Returns:
            TranslationResult with cantonese text or error
        """
        if english_term in self.fail_terms:
            return TranslationResult(
                english=english_term,
                cantonese="",
                success=False,
                error="Translation service unavailable",
                confidence=0.0
            )
        
        # Simple mock translation (just add "粵" prefix for testing)
        return TranslationResult(
            english=english_term,
            cantonese=f"粵{english_term}",
            success=True,
            error=None,
            confidence=0.9
        )
    
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Mock batch translate method.
        
        Args:
            terms: List of English terms
            
        Returns:
            List of TranslationResult objects
        """
        return [self.translate(term) for term in terms]


class TestTranslationServiceProperties:
    """Property-based tests for translation service."""
    
    @pytest.mark.property
    @given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=20))
    def test_translation_service_handles_all_terms(self, terms):
        """
        Feature: spreadsheet-preparation, Property 2: Translation Service Handles All Terms
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        
        Test that all terms receive results (success or error) and that
        failures don't stop processing of remaining terms.
        """
        service = MockTranslationService()
        results = service.translate_batch(terms)
        
        # Should have result for each term
        assert len(results) == len(terms), \
            f"Expected {len(terms)} results, got {len(results)}"
        
        # Each result should have english field matching input
        for term, result in zip(terms, results):
            assert result.english == term, \
                f"Result english '{result.english}' doesn't match input '{term}'"
            
            # Should have either success or error
            assert result.success or result.error is not None, \
                f"Result for '{term}' has neither success nor error"
            
            # If success, should have cantonese text
            if result.success:
                assert result.cantonese, \
                    f"Successful result for '{term}' has empty cantonese text"
            
            # If error, should have error message
            if not result.success:
                assert result.error, \
                    f"Failed result for '{term}' has no error message"
    
    @pytest.mark.property
    @given(
        st.lists(st.text(min_size=1, max_size=50), min_size=2, max_size=20),
        st.integers(min_value=1, max_value=5)
    )
    def test_translation_service_continues_after_failures(self, terms, num_failures):
        """
        Feature: spreadsheet-preparation, Property 2: Translation Service Handles All Terms
        
        Validates: Requirements 3.3, 3.4
        
        Test that failures don't stop processing of remaining terms.
        """
        # Ensure we don't try to fail more terms than we have
        num_failures = min(num_failures, len(terms))
        
        # Select unique terms to fail (to avoid duplicate issues)
        unique_terms = list(set(terms))
        num_unique_to_fail = min(num_failures, len(unique_terms))
        fail_terms = unique_terms[:num_unique_to_fail]
        
        service = MockTranslationService(fail_terms=fail_terms)
        results = service.translate_batch(terms)
        
        # Should still have result for each term
        assert len(results) == len(terms), \
            f"Expected {len(terms)} results even with failures, got {len(results)}"
        
        # Count successes and failures
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        
        # Expected failures is the count of terms that match fail_terms
        expected_failures = sum(1 for term in terms if term in fail_terms)
        
        # Should have the expected number of failures
        assert failed == expected_failures, \
            f"Expected {expected_failures} failures, got {failed}"
        
        # Should have processed remaining terms successfully
        assert successful == len(terms) - expected_failures, \
            f"Expected {len(terms) - expected_failures} successes, got {successful}"
        
        # All failed terms should have error messages
        for result in results:
            if not result.success:
                assert result.error is not None, \
                    f"Failed result for '{result.english}' has no error message"
                assert result.english in fail_terms, \
                    f"Unexpected failure for '{result.english}'"
    
    @pytest.mark.property
    @given(st.text(min_size=1, max_size=100))
    def test_single_translation_returns_result(self, term):
        """
        Test that single translation always returns a result.
        
        Validates: Requirements 3.1, 3.2
        """
        service = MockTranslationService()
        result = service.translate(term)
        
        # Should return a TranslationResult
        assert isinstance(result, TranslationResult), \
            f"Expected TranslationResult, got {type(result)}"
        
        # Should have the input term
        assert result.english == term, \
            f"Result english '{result.english}' doesn't match input '{term}'"
        
        # Should have either success or error
        assert result.success or result.error is not None, \
            "Result has neither success nor error"
    
    @pytest.mark.property
    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    def test_empty_and_non_empty_batches(self, terms):
        """
        Test that batch translation handles both empty and non-empty lists.
        
        Validates: Requirements 3.1, 3.2
        """
        service = MockTranslationService()
        results = service.translate_batch(terms)
        
        # Should return list with same length as input
        assert len(results) == len(terms), \
            f"Expected {len(terms)} results, got {len(results)}"
        
        # If empty input, should return empty list
        if len(terms) == 0:
            assert results == [], "Expected empty list for empty input"


class TestTranslationServiceUnitTests:
    """Unit tests for specific translation service scenarios."""
    
    def test_successful_translation(self):
        """Test successful translation scenario."""
        service = MockTranslationService()
        result = service.translate("hello")
        
        assert result.success is True
        assert result.english == "hello"
        assert result.cantonese == "粵hello"
        assert result.error is None
        assert result.confidence > 0
    
    def test_failed_translation(self):
        """Test failed translation scenario."""
        service = MockTranslationService(fail_terms=["hello"])
        result = service.translate("hello")
        
        assert result.success is False
        assert result.english == "hello"
        assert result.cantonese == ""
        assert result.error is not None
        assert "unavailable" in result.error.lower()
    
    def test_batch_with_mixed_results(self):
        """Test batch translation with both successes and failures."""
        terms = ["hello", "goodbye", "thanks"]
        service = MockTranslationService(fail_terms=["goodbye"])
        results = service.translate_batch(terms)
        
        assert len(results) == 3
        
        # First should succeed
        assert results[0].success is True
        assert results[0].english == "hello"
        
        # Second should fail
        assert results[1].success is False
        assert results[1].english == "goodbye"
        assert results[1].error is not None
        
        # Third should succeed
        assert results[2].success is True
        assert results[2].english == "thanks"
    
    def test_batch_all_failures(self):
        """Test batch translation where all terms fail."""
        terms = ["hello", "goodbye"]
        service = MockTranslationService(fail_terms=terms)
        results = service.translate_batch(terms)
        
        assert len(results) == 2
        assert all(not r.success for r in results)
        assert all(r.error is not None for r in results)
    
    def test_batch_all_successes(self):
        """Test batch translation where all terms succeed."""
        terms = ["hello", "goodbye", "thanks"]
        service = MockTranslationService(fail_terms=[])
        results = service.translate_batch(terms)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.cantonese for r in results)
