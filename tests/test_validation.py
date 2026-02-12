"""
Tests for validation utilities.
"""

import pytest
from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.spreadsheet_prep.validation import validate_entries


class TestValidateEntries:
    """Tests for validate_entries function."""
    
    def test_valid_entries_pass_validation(self):
        """Valid entries should return empty error dictionary."""
        entries = [
            VocabularyEntry(english="hello", cantonese="你好"),
            VocabularyEntry(english="goodbye", cantonese="再見"),
            VocabularyEntry(english="thank you", cantonese="多謝")
        ]
        
        errors = validate_entries(entries)
        
        assert errors == {}
    
    def test_empty_english_term_fails_validation(self):
        """Entry with empty English term should fail validation."""
        entries = [
            VocabularyEntry(english="", cantonese="你好")
        ]
        
        errors = validate_entries(entries)
        
        assert 0 in errors
        assert "English term is empty" in errors[0]
    
    def test_empty_cantonese_text_fails_validation(self):
        """Entry with empty Cantonese text should fail validation."""
        entries = [
            VocabularyEntry(english="hello", cantonese="")
        ]
        
        errors = validate_entries(entries)
        
        assert 0 in errors
        assert "Cantonese text is empty" in errors[0]
    
    def test_whitespace_only_english_fails_validation(self):
        """Entry with whitespace-only English term should fail validation."""
        entries = [
            VocabularyEntry(english="   ", cantonese="你好")
        ]
        
        errors = validate_entries(entries)
        
        assert 0 in errors
        assert "English term is empty" in errors[0]
    
    def test_whitespace_only_cantonese_fails_validation(self):
        """Entry with whitespace-only Cantonese text should fail validation."""
        entries = [
            VocabularyEntry(english="hello", cantonese="   ")
        ]
        
        errors = validate_entries(entries)
        
        assert 0 in errors
        assert "Cantonese text is empty" in errors[0]
    
    def test_both_fields_empty_fails_validation(self):
        """Entry with both fields empty should fail validation with both errors."""
        entries = [
            VocabularyEntry(english="", cantonese="")
        ]
        
        errors = validate_entries(entries)
        
        assert 0 in errors
        assert "English term is empty" in errors[0]
        assert "Cantonese text is empty" in errors[0]
        assert len(errors[0]) == 2
    
    def test_mixed_valid_and_invalid_entries(self):
        """Mix of valid and invalid entries should return errors only for invalid ones."""
        entries = [
            VocabularyEntry(english="hello", cantonese="你好"),  # Valid
            VocabularyEntry(english="", cantonese="再見"),      # Invalid English
            VocabularyEntry(english="thank you", cantonese="多謝"),  # Valid
            VocabularyEntry(english="goodbye", cantonese=""),   # Invalid Cantonese
            VocabularyEntry(english="", cantonese="")           # Both invalid
        ]
        
        errors = validate_entries(entries)
        
        # Should have errors for indices 1, 3, and 4
        assert len(errors) == 3
        assert 0 not in errors  # Index 0 is valid
        assert 1 in errors
        assert 2 not in errors  # Index 2 is valid
        assert 3 in errors
        assert 4 in errors
        
        # Check specific error messages
        assert "English term is empty" in errors[1]
        assert "Cantonese text is empty" in errors[3]
        assert "English term is empty" in errors[4]
        assert "Cantonese text is empty" in errors[4]
    
    def test_empty_list_returns_no_errors(self):
        """Empty list of entries should return empty error dictionary."""
        entries = []
        
        errors = validate_entries(entries)
        
        assert errors == {}
    
    def test_jyutping_field_not_validated(self):
        """Jyutping field should not be validated (it's optional)."""
        entries = [
            VocabularyEntry(english="hello", cantonese="你好", jyutping=""),
            VocabularyEntry(english="goodbye", cantonese="再見", jyutping="zoi3 gin3")
        ]
        
        errors = validate_entries(entries)
        
        # Both should pass validation regardless of jyutping
        assert errors == {}
    
    def test_error_indices_match_entry_positions(self):
        """Error indices should correctly match entry positions in list."""
        entries = [
            VocabularyEntry(english="valid1", cantonese="有效1"),
            VocabularyEntry(english="valid2", cantonese="有效2"),
            VocabularyEntry(english="", cantonese="無效"),
            VocabularyEntry(english="valid3", cantonese="有效3"),
            VocabularyEntry(english="invalid", cantonese="")
        ]
        
        errors = validate_entries(entries)
        
        # Errors should be at indices 2 and 4
        assert list(errors.keys()) == [2, 4]
