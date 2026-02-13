"""
Unit tests for input parsing utility.
"""

import pytest
from cantonese_anki_generator.spreadsheet_prep.input_parser import parse_input


def test_parse_input_basic():
    """Test basic input parsing with simple terms."""
    input_text = "hello\nworld"
    result = parse_input(input_text)
    assert result == ['hello', 'world']


def test_parse_input_with_whitespace():
    """Test input parsing trims whitespace from terms."""
    input_text = "  hello  \n  world  "
    result = parse_input(input_text)
    assert result == ['hello', 'world']


def test_parse_input_filters_empty_lines():
    """Test input parsing filters out empty lines."""
    input_text = "hello\n\n\nworld\n"
    result = parse_input(input_text)
    assert result == ['hello', 'world']


def test_parse_input_empty_string():
    """Test input parsing with empty string."""
    input_text = ""
    result = parse_input(input_text)
    assert result == []


def test_parse_input_only_whitespace():
    """Test input parsing with only whitespace and newlines."""
    input_text = "\n\n  \n  \n"
    result = parse_input(input_text)
    assert result == []


def test_parse_input_mixed_whitespace():
    """Test input parsing with mixed whitespace scenarios."""
    input_text = "  apple  \n\n  banana  \n  \n  cherry  "
    result = parse_input(input_text)
    assert result == ['apple', 'banana', 'cherry']


def test_parse_input_single_term():
    """Test input parsing with single term."""
    input_text = "hello"
    result = parse_input(input_text)
    assert result == ['hello']


def test_parse_input_preserves_internal_spaces():
    """Test input parsing preserves spaces within terms."""
    input_text = "hello world\ngood morning"
    result = parse_input(input_text)
    assert result == ['hello world', 'good morning']
