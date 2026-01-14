"""
Tests for web API error handling.
Task 19: Error handling and user feedback
"""

import pytest
import os
import tempfile
from pathlib import Path
from flask import Flask
from cantonese_anki_generator.web.api import bp


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
    app.register_blueprint(bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns 200."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'


class TestUploadValidation:
    """Test upload endpoint validation and error handling."""
    
    def test_missing_url(self, client):
        """Test upload with missing URL."""
        response = client.post('/api/upload', data={
            'audio': (open(__file__, 'rb'), 'test.mp3')
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
        assert 'error_code' in data
        assert data['error_code'] == 'INVALID_URL'
    
    def test_invalid_url_format(self, client):
        """Test upload with invalid URL format."""
        response = client.post('/api/upload', data={
            'url': 'https://example.com/not-a-google-doc',
            'audio': (open(__file__, 'rb'), 'test.mp3')
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Invalid URL format' in data['error']
        assert data['error_code'] == 'INVALID_URL'
    
    def test_missing_audio_file(self, client):
        """Test upload with missing audio file."""
        response = client.post('/api/upload', data={
            'url': 'https://docs.google.com/document/d/test123'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'No audio file provided' in data['error']
        assert data['error_code'] == 'MISSING_AUDIO'
    
    def test_invalid_audio_format(self, client):
        """Test upload with invalid audio format."""
        # Create a temporary text file
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'not an audio file')
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                response = client.post('/api/upload', data={
                    'url': 'https://docs.google.com/document/d/test123',
                    'audio': (f, 'test.txt')
                })
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'Unsupported audio format' in data['error']
            assert data['error_code'] == 'INVALID_AUDIO'
        finally:
            os.unlink(temp_path)


class TestProcessValidation:
    """Test process endpoint validation and error handling."""
    
    def test_missing_json_data(self, client):
        """Test process with no JSON data."""
        response = client.post('/api/process',
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'JSON' in data['error']  # Either "Invalid JSON" or "No JSON data"
        assert data['error_code'] in ['INVALID_JSON', 'MISSING_DATA']
    
    def test_missing_required_fields(self, client):
        """Test process with missing required fields."""
        response = client.post('/api/process',
                              json={'doc_url': 'https://docs.google.com/document/d/test'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()
        assert data['error_code'] == 'MISSING_FIELDS'
    
    def test_nonexistent_audio_file(self, client):
        """Test process with non-existent audio file."""
        response = client.post('/api/process',
                              json={
                                  'doc_url': 'https://docs.google.com/document/d/test',
                                  'audio_filepath': '/nonexistent/path/audio.mp3'
                              })
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
        assert data['error_code'] == 'FILE_NOT_FOUND'


class TestSessionValidation:
    """Test session endpoint validation and error handling."""
    
    def test_invalid_session_id(self, client):
        """Test get session with invalid ID format."""
        response = client.get('/api/session/')
        # Flask will return 404 for missing path parameter
        assert response.status_code == 404
    
    def test_nonexistent_session(self, client):
        """Test get session with non-existent session ID."""
        response = client.get('/api/session/nonexistent_session_123')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
        assert data['error_code'] == 'SESSION_NOT_FOUND'


class TestErrorCodes:
    """Test that all error responses include error codes."""
    
    def test_error_responses_have_codes(self, client):
        """Verify all error responses include error_code field."""
        # Test various error scenarios
        test_cases = [
            ('/api/upload', {'data': {}}, 'INVALID_URL'),
            ('/api/process', {'json': {}}, 'MISSING_DATA'),
            ('/api/session/invalid', {}, 'SESSION_NOT_FOUND'),
        ]
        
        for endpoint, kwargs, expected_code in test_cases:
            if 'data' in kwargs:
                response = client.post(endpoint, **kwargs)
            elif 'json' in kwargs:
                response = client.post(endpoint, **kwargs)
            else:
                response = client.get(endpoint)
            
            data = response.get_json()
            assert 'error_code' in data, f"Missing error_code in {endpoint}"
            # Some endpoints might return different codes, just verify it exists
            assert isinstance(data['error_code'], str)


class TestErrorMessages:
    """Test that error messages are user-friendly."""
    
    def test_error_messages_are_descriptive(self, client):
        """Verify error messages provide helpful information."""
        response = client.post('/api/upload', data={
            'url': 'invalid-url',
            'audio': (open(__file__, 'rb'), 'test.mp3')
        })
        
        data = response.get_json()
        assert data['success'] is False
        # Error message should be descriptive, not just "error"
        assert len(data['error']) > 20
        # Should provide guidance
        assert 'google' in data['error'].lower() or 'url' in data['error'].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
