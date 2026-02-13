"""
Unit tests for SheetExporter class.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from cantonese_anki_generator.spreadsheet_prep.sheet_exporter import SheetExporter
from cantonese_anki_generator.models import VocabularyEntry, SheetCreationResult


class TestSheetExporter:
    """Test suite for SheetExporter class."""
    
    def test_init_with_authenticator(self):
        """Test initialization with provided authenticator."""
        mock_auth = Mock()
        exporter = SheetExporter(authenticator=mock_auth)
        assert exporter.authenticator == mock_auth
    
    def test_init_without_authenticator(self):
        """Test initialization creates default authenticator."""
        exporter = SheetExporter()
        assert exporter.authenticator is not None
    
    @patch('googleapiclient.discovery.build')
    def test_create_vocabulary_sheet_success(self, mock_build):
        """Test successful sheet creation."""
        # Setup mocks
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_spreadsheet = {
            'spreadsheetId': 'test_id_123',
            'spreadsheetUrl': 'https://docs.google.com/spreadsheets/d/test_id_123'
        }
        
        mock_service.spreadsheets().create().execute.return_value = mock_spreadsheet
        mock_service.spreadsheets().values().update().execute.return_value = {}
        
        # Mock the get() call for format validation
        mock_get_result = {
            'values': [
                ['English', 'Cantonese', 'Jyutping'],
                ['hello', '你好', 'nei5 hou2'],
                ['goodbye', '再見', 'zoi3 gin3']
            ]
        }
        mock_service.spreadsheets().values().get().execute.return_value = mock_get_result
        
        # Create exporter with mocked authenticator
        mock_auth = Mock()
        mock_auth.authenticate.return_value = True
        mock_auth.get_sheets_service.return_value = mock_service
        
        exporter = SheetExporter(authenticator=mock_auth)
        
        # Create test entries
        entries = [
            VocabularyEntry(english="hello", cantonese="你好", jyutping="nei5 hou2"),
            VocabularyEntry(english="goodbye", cantonese="再見", jyutping="zoi3 gin3")
        ]
        
        # Execute
        result = exporter.create_vocabulary_sheet(entries, title="Test Vocab")
        
        # Verify
        assert result.success is True
        assert result.sheet_id == 'test_id_123'
        assert result.sheet_url == 'https://docs.google.com/spreadsheets/d/test_id_123'
        assert result.error is None
        
        # Verify create was called with correct title
        create_call = mock_service.spreadsheets().create.call_args
        assert create_call[1]['body']['properties']['title'] == "Test Vocab"
        
        # Verify data was written with header row
        update_call = mock_service.spreadsheets().values().update.call_args
        values = update_call[1]['body']['values']
        assert values[0] == ['English', 'Cantonese', 'Jyutping']
        assert values[1] == ['hello', '你好', 'nei5 hou2']
        assert values[2] == ['goodbye', '再見', 'zoi3 gin3']
    
    @patch('googleapiclient.discovery.build')
    def test_create_vocabulary_sheet_handles_errors(self, mock_build):
        """Test error handling during sheet creation."""
        # Setup mocks to raise exception
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().create().execute.side_effect = Exception("API Error")
        
        # Create exporter
        mock_auth = Mock()
        mock_auth.authenticate.return_value = True
        mock_auth.get_sheets_service.return_value = mock_service
        
        exporter = SheetExporter(authenticator=mock_auth)
        
        # Create test entries
        entries = [
            VocabularyEntry(english="hello", cantonese="你好", jyutping="nei5 hou2")
        ]
        
        # Execute
        result = exporter.create_vocabulary_sheet(entries)
        
        # Verify error handling
        assert result.success is False
        assert result.error is not None
        assert "Failed to create sheet" in result.error
    
    @patch('googleapiclient.discovery.build')
    def test_format_for_parser_compatibility_valid(self, mock_build):
        """Test format validation with valid sheet."""
        # Setup mocks
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_result = {
            'values': [
                ['English', 'Cantonese', 'Jyutping'],
                ['hello', '你好', 'nei5 hou2']
            ]
        }
        
        mock_service.spreadsheets().values().get().execute.return_value = mock_result
        
        # Create exporter
        mock_auth = Mock()
        mock_auth.authenticate.return_value = True
        mock_auth.get_sheets_service.return_value = mock_service
        
        exporter = SheetExporter(authenticator=mock_auth)
        
        # Execute
        result = exporter.format_for_parser_compatibility('test_id')
        
        # Verify
        assert result is True
    
    @patch('googleapiclient.discovery.build')
    def test_format_for_parser_compatibility_invalid_headers(self, mock_build):
        """Test format validation with invalid headers."""
        # Setup mocks
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_result = {
            'values': [
                ['Word', 'Translation', 'Pronunciation'],  # Wrong headers
                ['hello', '你好', 'nei5 hou2']
            ]
        }
        
        mock_service.spreadsheets().values().get().execute.return_value = mock_result
        
        # Create exporter
        mock_auth = Mock()
        mock_auth.authenticate.return_value = True
        mock_auth.get_sheets_service.return_value = mock_service
        
        exporter = SheetExporter(authenticator=mock_auth)
        
        # Execute
        result = exporter.format_for_parser_compatibility('test_id')
        
        # Verify
        assert result is False
    
    @patch('googleapiclient.discovery.build')
    def test_format_for_parser_compatibility_handles_errors(self, mock_build):
        """Test format validation handles API errors."""
        # Setup mocks to raise exception
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.side_effect = Exception("API Error")
        
        # Create exporter
        mock_auth = Mock()
        mock_auth.authenticate.return_value = True
        mock_auth.get_sheets_service.return_value = mock_service
        
        exporter = SheetExporter(authenticator=mock_auth)
        
        # Execute
        result = exporter.format_for_parser_compatibility('test_id')
        
        # Verify error handling
        assert result is False
