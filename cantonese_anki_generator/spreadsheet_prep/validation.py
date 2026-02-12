"""
Validation utilities for spreadsheet preparation.
"""

from typing import List, Dict
from cantonese_anki_generator.models import VocabularyEntry


def validate_entries(entries: List[VocabularyEntry]) -> Dict[int, List[str]]:
    """
    Validate vocabulary entries for required fields.
    
    Checks that all entries have non-empty English terms and non-empty
    Cantonese text. Returns validation errors with entry indices.
    
    Args:
        entries: List of VocabularyEntry objects to validate
        
    Returns:
        Dictionary mapping entry indices to lists of error messages.
        Empty dictionary if all entries are valid.
        
    Examples:
        >>> entry1 = VocabularyEntry(english="hello", cantonese="你好")
        >>> entry2 = VocabularyEntry(english="", cantonese="再見")
        >>> entry3 = VocabularyEntry(english="goodbye", cantonese="")
        >>> errors = validate_entries([entry1, entry2, entry3])
        >>> errors[1]
        ['English term is empty']
        >>> errors[2]
        ['Cantonese text is empty']
    """
    validation_errors: Dict[int, List[str]] = {}
    
    for index, entry in enumerate(entries):
        errors = []
        
        # Check for non-empty English term
        if not entry.english or not entry.english.strip():
            errors.append("English term is empty")
        
        # Check for non-empty Cantonese text
        if not entry.cantonese or not entry.cantonese.strip():
            errors.append("Cantonese text is empty")
        
        # If there are errors for this entry, add to validation_errors
        if errors:
            validation_errors[index] = errors
    
    return validation_errors
