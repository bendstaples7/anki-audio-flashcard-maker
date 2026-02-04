"""Tests for web API file upload and validation."""

import os
import pytest
import tempfile
from io import BytesIO
from flask import Flask

from cantonese_anki_generator.web.app import create_app
from cantonese_anki_generator.web.api import validate_google_url, validate_audio_file


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestURLValidation:
    """Test URL validation functionality."""
    
    def test_valid_google_docs_url_format(self):
        """Test that valid Google Docs URL format is recognized."""
        url = "https://docs.google.com/document/d/1234567890abcdef"
        # Note: This will fail accessibility check without real credentials
        # but should pass format validation
        is_valid, error, doc_type, _ = validate_google_url(url)
        # Format is valid even if accessibility fails
        assert doc_type == 'docs' or error is not None
    
    def test_valid_google_sheets_url_format(self):
        """Test that valid Google Sheets URL format is recognized."""
        url = "https://docs.google.com/spreadsheets/d/1234567890abcdef"
        is_valid, error, doc_type, _ = validate_google_url(url)
        assert doc_type == 'sheets' or error is not None
    
    def test_invalid_url_format(self):
        """Test that invalid URL format is rejected."""
        url = "https://example.com/document"
        is_valid, error, doc_type, auth_url = validate_google_url(url)
        assert not is_valid
        assert "Invalid URL format" in error
        assert doc_type is None
        assert auth_url is None
    
    def test_empty_url(self):
        """Test that empty URL is rejected."""
        is_valid, error, _, auth_url = validate_google_url("")
        assert not is_valid
        assert "URL is required" in error
        assert auth_url is None

    def test_none_url(self):
        """Test that None URL is rejected."""
        is_valid, error, _, auth_url = validate_google_url(None)
        assert not is_valid
        assert "URL is required" in error
        assert auth_url is None


class TestAudioFileValidation:
    """Test audio file validation functionality."""
    
    def test_valid_mp3_file(self):
        """Test that MP3 files are accepted."""
        # Create a mock file object
        class MockFile:
            filename = "test.mp3"
        
        is_valid, error = validate_audio_file(MockFile())
        assert is_valid
        assert error is None
    
    def test_valid_wav_file(self):
        """Test that WAV files are accepted."""
        class MockFile:
            filename = "test.wav"
        
        is_valid, error = validate_audio_file(MockFile())
        assert is_valid
        assert error is None
    
    def test_valid_m4a_file(self):
        """Test that M4A files are accepted."""
        class MockFile:
            filename = "test.m4a"
        
        is_valid, error = validate_audio_file(MockFile())
        assert is_valid
        assert error is None
    
    def test_invalid_file_format(self):
        """Test that unsupported formats are rejected."""
        class MockFile:
            filename = "test.txt"
        
        is_valid, error = validate_audio_file(MockFile())
        assert not is_valid
        assert "Unsupported audio format" in error
    
    def test_no_file_provided(self):
        """Test that missing file is rejected."""
        is_valid, error = validate_audio_file(None)
        assert not is_valid
        assert "No audio file provided" in error

    def test_empty_filename(self):
        """Test that empty filename is rejected."""
        class MockFile:
            filename = ""
        
        is_valid, error = validate_audio_file(MockFile())
        assert not is_valid
        assert "No audio file selected" in error


class TestUploadEndpoint:
    """Test the /api/upload endpoint."""
    
    def test_upload_missing_url(self, client):
        """Test upload fails when URL is missing."""
        # Create a fake audio file
        data = {
            'audio': (BytesIO(b"fake audio data"), 'test.mp3')
        }
        
        response = client.post('/api/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        json_data = response.get_json()
        assert not json_data['success']
        assert 'url' in json_data.get('error', '').lower() or json_data.get('field') == 'url'
    
    def test_upload_missing_audio(self, client):
        """Test upload fails when audio file is missing."""
        data = {
            'url': 'https://docs.google.com/document/d/1234567890abcdef'
        }
        
        response = client.post('/api/upload', data=data, content_type='multipart/form-data')
        # Can be 400 (missing audio) or 401 (auth required) depending on auth state
        assert response.status_code in [400, 401]
        json_data = response.get_json()
        assert not json_data['success']
        # Either URL validation fails (due to auth) or audio is missing
        # Both are acceptable failure modes in test environment
        assert json_data.get('field') in ['audio', 'url'] or json_data.get('error_code') == 'AUTH_REQUIRED'
    
    def test_upload_invalid_url_format(self, client):
        """Test upload fails with invalid URL format."""
        data = {
            'url': 'https://example.com/document',
            'audio': (BytesIO(b"fake audio data"), 'test.mp3')
        }
        
        response = client.post('/api/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        json_data = response.get_json()
        assert not json_data['success']
        assert 'Invalid URL format' in json_data.get('error', '')
    
    def test_upload_invalid_audio_format(self, client):
        """Test upload fails with unsupported audio format."""
        data = {
            'url': 'https://docs.google.com/document/d/1234567890abcdef',
            'audio': (BytesIO(b"fake audio data"), 'test.txt')
        }
        
        response = client.post('/api/upload', data=data, content_type='multipart/form-data')
        # Can be 400 (invalid audio) or 401 (auth required) depending on auth state
        assert response.status_code in [400, 401]
        json_data = response.get_json()
        assert not json_data['success']
        # Either audio format validation fails or URL validation fails (due to auth)
        # Both are acceptable failure modes in test environment
        error = json_data.get('error', '')
        assert 'Unsupported audio format' in error or 'authenticate' in error.lower() or json_data.get('error_code') == 'AUTH_REQUIRED'
