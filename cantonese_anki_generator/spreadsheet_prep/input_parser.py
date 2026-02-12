"""
Input parsing utilities for spreadsheet preparation.
"""

from typing import List


def parse_input(input_text: str) -> List[str]:
    """
    Parse multi-line input text into a list of English terms.
    
    Splits input by newlines, filters out empty lines, and trims whitespace
    from each term.
    
    Args:
        input_text: Multi-line string containing English terms
        
    Returns:
        List of non-empty English terms with whitespace trimmed
        
    Examples:
        >>> parse_input("hello\\nworld")
        ['hello', 'world']
        
        >>> parse_input("  hello  \\n\\n  world  \\n")
        ['hello', 'world']
        
        >>> parse_input("\\n\\n")
        []
    """
    # Split input by newlines
    lines = input_text.split('\n')
    
    # Filter out empty lines and trim whitespace
    terms = [line.strip() for line in lines if line.strip()]
    
    return terms
