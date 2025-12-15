"""
Tests for Google Docs processor functionality.
"""

import pytest
from unittest.mock import Mock, patch
from cantonese_anki_generator.processors import GoogleDocsParser, GoogleDocsAuthenticator
from cantonese_anki_generator.models import VocabularyEntry


class TestGoogleDocsParser:
    """Test cases for GoogleDocsParser."""
    
    def test_extract_document_id_standard_format(self):
        """Test extracting document ID from standard Google Docs URL."""
        parser = GoogleDocsParser()
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
        doc_id = parser.extract_document_id(url)
        assert doc_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    
    def test_extract_document_id_alternative_format(self):
        """Test extracting document ID from alternative URL format."""
        parser = GoogleDocsParser()
        url = "https://docs.google.com/document/u/0/?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        doc_id = parser.extract_document_id(url)
        assert doc_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    
    def test_extract_document_id_invalid_url(self):
        """Test error handling for invalid URL format."""
        parser = GoogleDocsParser()
        with pytest.raises(ValueError, match="Invalid Google Docs URL format"):
            parser.extract_document_id("https://invalid-url.com")
    
    def test_parse_table_structure(self):
        """Test parsing table structure from Google Docs API response."""
        parser = GoogleDocsParser()
        
        # Mock table structure from Google Docs API
        mock_table = {
            "tableRows": [
                {
                    "tableCells": [
                        {
                            "content": [
                                {
                                    "paragraph": {
                                        "elements": [
                                            {
                                                "textRun": {
                                                    "content": "English"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        },
                        {
                            "content": [
                                {
                                    "paragraph": {
                                        "elements": [
                                            {
                                                "textRun": {
                                                    "content": "Cantonese"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "tableCells": [
                        {
                            "content": [
                                {
                                    "paragraph": {
                                        "elements": [
                                            {
                                                "textRun": {
                                                    "content": "hello"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        },
                        {
                            "content": [
                                {
                                    "paragraph": {
                                        "elements": [
                                            {
                                                "textRun": {
                                                    "content": "你好"
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = parser.parse_table_structure(mock_table)
        expected = [
            ["English", "Cantonese"],
            ["hello", "你好"]
        ]
        assert result == expected
    
    def test_extract_vocabulary_pairs(self):
        """Test extracting vocabulary entries from table data."""
        parser = GoogleDocsParser()
        
        table_data = [
            ["English", "Cantonese"],  # Header row
            ["hello", "你好"],
            ["goodbye", "再見"],
            ["", ""],  # Empty row should be skipped
            ["thank you", "謝謝"]
        ]
        
        entries = parser.extract_vocabulary_pairs(table_data)
        
        assert len(entries) == 3
        assert entries[0].english == "hello"
        assert entries[0].cantonese == "你好"
        assert entries[0].row_index == 1
        assert entries[1].english == "goodbye"
        assert entries[1].cantonese == "再見"
        assert entries[2].english == "thank you"
        assert entries[2].cantonese == "謝謝"
    
    def test_looks_like_english(self):
        """Test English text detection."""
        parser = GoogleDocsParser()
        
        assert parser._looks_like_english("hello world") == True
        assert parser._looks_like_english("Hello, how are you?") == True
        assert parser._looks_like_english("你好") == False
        assert parser._looks_like_english("") == False
    
    def test_looks_like_cantonese(self):
        """Test Cantonese/Chinese text detection."""
        parser = GoogleDocsParser()
        
        assert parser._looks_like_cantonese("你好") == True
        assert parser._looks_like_cantonese("再見") == True
        assert parser._looks_like_cantonese("hello") == False
        assert parser._looks_like_cantonese("") == False
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        parser = GoogleDocsParser()
        
        assert parser._clean_text("  hello world  ") == "hello world"
        assert parser._clean_text("hello\n\nworld") == "hello world"
        assert parser._clean_text("hello@#$%world") == "helloworld"
        assert parser._clean_text("") == ""


class TestGoogleDocsAuthenticator:
    """Test cases for GoogleDocsAuthenticator."""
    
    def test_authenticator_initialization(self):
        """Test authenticator initialization."""
        auth = GoogleDocsAuthenticator()
        assert auth.credentials_path == "credentials.json"
        assert auth.token_path == "token.json"
        assert auth.scopes == [
            "https://www.googleapis.com/auth/documents.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly"
        ]
    
    def test_custom_paths(self):
        """Test authenticator with custom file paths."""
        auth = GoogleDocsAuthenticator(
            credentials_path="custom_creds.json",
            token_path="custom_token.json"
        )
        assert auth.credentials_path == "custom_creds.json"
        assert auth.token_path == "custom_token.json"