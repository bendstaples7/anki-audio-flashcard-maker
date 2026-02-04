"""Tests for authentication status API endpoint."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from cantonese_anki_generator.web.app import create_app
from cantonese_anki_generator.config import Config


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestAuthStatus:
    """Test GET /api/auth/status endpoint."""
    
    def test_auth_status_missing_credentials(self, client):
        """Test auth status when credentials file is missing."""
        with patch('os.path.exists') as mock_exists:
            # Mock credentials file as missing
            def exists_side_effect(path):
                if 'credentials.json' in path:
                    return False
                return True
            
            mock_exists.side_effect = exists_side_effect
            
            response = client.get('/api/auth/status')
            
            # Now returns 500 with centralized error response
            assert response.status_code == 500
            data = response.get_json()
            
            assert data['success'] is False
            assert 'error' in data
            assert data['error_code'] == 'MISSING_CREDENTIALS'
            assert 'action_required' in data
    
    def test_auth_status_valid_tokens(self, client):
        """Test auth status when tokens are valid."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            # Mock authenticator with valid tokens
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock token status - valid and not expired
            expires_at = datetime.utcnow() + timedelta(days=3)
            mock_auth.get_token_status.return_value = {
                'valid': True,
                'expired': False,
                'expires_at': expires_at,
                'needs_refresh': False,
                'has_refresh_token': True
            }
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['authenticated'] is True
            assert data['token_valid'] is True
            assert data['expires_at'] is not None
            assert data['expires_in_hours'] > 0
            assert data['needs_reauth'] is False
            assert data['authorization_url'] is None
    
    def test_auth_status_expired_tokens(self, client):
        """Test auth status when tokens are expired."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            # Mock authenticator with expired tokens
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock token status - expired
            mock_auth.get_token_status.return_value = {
                'valid': False,
                'expired': True,
                'expires_at': None,
                'needs_refresh': True,
                'has_refresh_token': True
            }
            
            # Mock authorization URL generation
            mock_auth.get_authorization_url.return_value = (
                'https://accounts.google.com/o/oauth2/v2/auth?...',
                'test_state_token'
            )
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['authenticated'] is False
            assert data['token_valid'] is False
            assert data['expires_at'] is None
            assert data['expires_in_hours'] == 0
            assert data['needs_reauth'] is True
            assert data['authorization_url'] is not None
            assert 'https://accounts.google.com' in data['authorization_url']
    
    def test_auth_status_missing_tokens(self, client):
        """Test auth status when tokens are missing."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            # Mock authenticator with no tokens
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock token status - no tokens
            mock_auth.get_token_status.return_value = {
                'valid': False,
                'expired': False,
                'expires_at': None,
                'needs_refresh': False,
                'has_refresh_token': False
            }
            
            # Mock authorization URL generation
            mock_auth.get_authorization_url.return_value = (
                'https://accounts.google.com/o/oauth2/v2/auth?...',
                'test_state_token'
            )
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['authenticated'] is False
            assert data['token_valid'] is False
            assert data['needs_reauth'] is True
            assert data['authorization_url'] is not None
    
    def test_auth_status_expiring_soon(self, client):
        """Test auth status when tokens are expiring soon but still valid."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            # Mock authenticator with tokens expiring soon
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock token status - valid but expiring in 12 hours
            expires_at = datetime.utcnow() + timedelta(hours=12)
            mock_auth.get_token_status.return_value = {
                'valid': True,
                'expired': False,
                'expires_at': expires_at,
                'needs_refresh': True,
                'has_refresh_token': True
            }
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Should still be authenticated since tokens are valid
            assert data['authenticated'] is True
            assert data['token_valid'] is True
            # Allow for timing variations (11-12 hours due to test execution time)
            assert 11 <= data['expires_in_hours'] <= 12
            assert data['needs_reauth'] is False
    
    def test_auth_status_includes_all_required_fields(self, client):
        """Test that auth status response includes all required fields."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            expires_at = datetime.utcnow() + timedelta(days=3)
            mock_auth.get_token_status.return_value = {
                'valid': True,
                'expired': False,
                'expires_at': expires_at,
                'needs_refresh': False,
                'has_refresh_token': True
            }
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            data = response.get_json()
            
            # Check all required fields are present
            required_fields = [
                'authenticated',
                'token_valid',
                'expires_at',
                'expires_in_hours',
                'needs_reauth',
                'authorization_url'
            ]
            
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
    
    def test_auth_status_handles_auth_url_generation_error(self, client):
        """Test auth status handles errors when generating authorization URL."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock token status - expired
            mock_auth.get_token_status.return_value = {
                'valid': False,
                'expired': True,
                'expires_at': None,
                'needs_refresh': True,
                'has_refresh_token': False
            }
            
            # Mock authorization URL generation to raise error
            mock_auth.get_authorization_url.side_effect = Exception("Failed to generate URL")
            
            with patch('os.path.exists', return_value=True):
                response = client.get('/api/auth/status')
            
            assert response.status_code == 500
            data = response.get_json()
            
            # Now uses centralized error response format
            assert data['success'] is False
            assert 'error' in data
            assert data['error_code'] == 'AUTH_URL_ERROR'
            assert 'action_required' in data
