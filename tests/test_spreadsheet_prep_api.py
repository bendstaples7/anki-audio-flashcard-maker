"""
Tests for spreadsheet preparation API endpoints.
"""

import pytest
from unittest.mock import Mock, patch
from cantonese_anki_generator.models import TranslationResult, RomanizationResult, SheetCreationResult


def test_translate_endpoint_with_valid_input(client):
    """Test translate endpoint with valid English terms."""
    # Mock the services at their source module location
    with patch('cantonese_anki_generator.spreadsheet_prep.translation_service.GoogleTranslationService') as mock_trans, \
         patch('cantonese_anki_generator.spreadsheet_prep.romanization_service.PyCantoneseRomanizationService') as mock_rom:
        
        # Setup mock translation service
        mock_trans_instance = Mock()
        mock_trans.return_value = mock_trans_instance
        mock_trans_instance.translate_batch.return_value = [
            TranslationResult(english="hello", cantonese="你好", success=True),
            TranslationResult(english="goodbye", cantonese="再見", success=True)
        ]
        
        # Setup mock romanization service
        mock_rom_instance = Mock()
        mock_rom.return_value = mock_rom_instance
        mock_rom_instance.romanize.side_effect = [
            RomanizationResult(cantonese="你好", jyutping="nei5 hou2", success=True),
            RomanizationResult(cantonese="再見", jyutping="zoi3 gin3", success=True)
        ]
        
        # Make request
        response = client.post('/api/spreadsheet-prep/translate', json={
            'terms': ['hello', 'goodbye']
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['results']) == 2
        assert data['summary']['total'] == 2
        assert data['summary']['successful'] == 2
        assert data['summary']['failed'] == 0


def test_translate_endpoint_with_empty_terms(client):
    """Test translate endpoint with empty terms list."""
    response = client.post('/api/spreadsheet-prep/translate', json={
        'terms': []
    })
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'terms' in data['error'].lower()


def test_translate_endpoint_with_missing_terms(client):
    """Test translate endpoint with missing terms field."""
    response = client.post('/api/spreadsheet-prep/translate', json={})
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_translate_endpoint_with_too_many_terms(client):
    """Test translate endpoint with terms exceeding max limit."""
    from cantonese_anki_generator.config import Config
    
    # Create a list exceeding the max batch size
    too_many_terms = ['term' + str(i) for i in range(Config.TRANSLATION_BATCH_SIZE + 1)]
    
    response = client.post('/api/spreadsheet-prep/translate', json={
        'terms': too_many_terms
    })
    
    assert response.status_code == 413  # Payload Too Large
    data = response.get_json()
    assert data['success'] is False
    assert 'maximum' in data['error'].lower() or 'too many' in data['error'].lower()


def test_export_endpoint_with_valid_entries(client):
    """Test export endpoint with valid vocabulary entries."""
    with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth, \
         patch('cantonese_anki_generator.spreadsheet_prep.sheet_exporter.SheetExporter') as mock_exporter:
        
        # Setup mock authenticator
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance
        mock_auth_instance.get_token_status.return_value = {
            'valid': True,
            'expired': False
        }
        
        # Setup mock sheet exporter
        mock_exporter_instance = Mock()
        mock_exporter.return_value = mock_exporter_instance
        mock_exporter_instance.create_vocabulary_sheet.return_value = SheetCreationResult(
            success=True,
            sheet_url="https://docs.google.com/spreadsheets/d/test123",
            sheet_id="test123"
        )
        
        # Make request
        response = client.post('/api/spreadsheet-prep/export', json={
            'entries': [
                {'english': 'hello', 'cantonese': '你好', 'jyutping': 'nei5 hou2'},
                {'english': 'goodbye', 'cantonese': '再見', 'jyutping': 'zoi3 gin3'}
            ],
            'title': 'Test Vocabulary'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'sheet_url' in data
        assert 'sheet_id' in data


def test_export_endpoint_with_validation_errors(client):
    """Test export endpoint with entries missing required fields."""
    with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth:
        
        # Setup mock authenticator
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance
        mock_auth_instance.get_token_status.return_value = {
            'valid': True,
            'expired': False
        }
        
        # Make request with invalid entries
        response = client.post('/api/spreadsheet-prep/export', json={
            'entries': [
                {'english': '', 'cantonese': '你好', 'jyutping': 'nei5 hou2'},  # Empty English
                {'english': 'goodbye', 'cantonese': '', 'jyutping': 'zoi3 gin3'}  # Empty Cantonese
            ]
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'validation' in data['error'].lower()


def test_export_endpoint_with_non_dict_entries(client):
    """Test export endpoint with non-dict entries (should return 400, not 500)."""
    with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth:
        
        # Setup mock authenticator
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance
        mock_auth_instance.get_token_status.return_value = {
            'valid': True,
            'expired': False
        }
        
        # Make request with invalid entry types (strings instead of dicts)
        response = client.post('/api/spreadsheet-prep/export', json={
            'entries': [
                {'english': 'hello', 'cantonese': '你好', 'jyutping': 'nei5 hou2'},  # Valid
                'invalid_string_entry',  # Invalid - string instead of dict
                {'english': 'goodbye', 'cantonese': '再見', 'jyutping': 'zoi3 gin3'}  # Valid
            ]
        })
        
        assert response.status_code == 400  # Should be 400, not 500
        data = response.get_json()
        assert data['success'] is False
        assert 'invalid entry' in data['error'].lower()
        assert 'index 1' in data['error'].lower()  # Should mention the offending index
        assert 'invalid_index' in data  # Should include the invalid index in response


def test_export_endpoint_requires_authentication(client):
    """Test export endpoint requires valid authentication."""
    with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth:
        
        # Setup mock authenticator with invalid tokens
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance
        mock_auth_instance.get_token_status.return_value = {
            'valid': False,
            'expired': True
        }
        mock_auth_instance.get_authorization_url.return_value = (
            'https://accounts.google.com/oauth',
            'state123'
        )
        
        # Make request
        response = client.post('/api/spreadsheet-prep/export', json={
            'entries': [
                {'english': 'hello', 'cantonese': '你好', 'jyutping': 'nei5 hou2'}
            ]
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert 'authorization_url' in data


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    from cantonese_anki_generator.web.app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client
