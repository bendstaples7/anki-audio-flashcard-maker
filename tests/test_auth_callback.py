"""Tests for OAuth callback API endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from cantonese_anki_generator.web.app import create_app


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


class TestAuthCallback:
    """Test GET /api/auth/callback endpoint."""
    
    def test_callback_successful_authorization(self, client, app):
        """Test successful authorization code exchange."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            # Mock authenticator
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock successful token exchange
            mock_auth.exchange_code_for_tokens.return_value = True
            
            # Mock state validation (file-based storage)
            mock_auth._validate_state.return_value = True
            
            # Make request with valid code and state
            response = client.get('/api/auth/callback?code=test_code&state=test_state_token')
            
            assert response.status_code == 200
            
            # Success response is HTML, not JSON
            assert response.content_type == 'text/html; charset=utf-8'
            html_content = response.get_data(as_text=True)
            
            # Verify HTML contains success message
            assert 'Authentication Successful' in html_content
            assert 'You can now use Google Docs and Sheets' in html_content
            assert "window.location.href = '/'" in html_content  # Auto-redirect script
            
            # Verify token exchange was called
            mock_auth.exchange_code_for_tokens.assert_called_once()
    
    def test_callback_missing_code(self, client):
        """Test callback with missing authorization code."""
        response = client.get('/api/auth/callback?state=test_state')
        
        assert response.status_code == 400
        data = response.get_json()
        
        assert data['success'] is False
        assert 'Missing authorization code' in data['error']
        assert data['error_code'] == 'MISSING_CODE'
    
    def test_callback_missing_state(self, client):
        """Test callback with missing state token."""
        response = client.get('/api/auth/callback?code=test_code')
        
        assert response.status_code == 400
        data = response.get_json()
        
        assert data['success'] is False
        assert 'Missing state token' in data['error']
        assert data['error_code'] == 'MISSING_STATE'
    
    def test_callback_invalid_state(self, client, app):
        """Test callback with invalid state token (CSRF protection)."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock invalid state validation (file-based storage returns False)
            mock_auth._validate_state.return_value = False
            
            # Make request with invalid state
            response = client.get('/api/auth/callback?code=test_code&state=invalid_state')
        
        assert response.status_code == 400
        data = response.get_json()
        
        assert data['success'] is False
        assert 'Invalid or expired state token' in data['error']
        assert data['error_code'] == 'INVALID_STATE'
    
    def test_callback_oauth_error(self, client):
        """Test callback when OAuth returns an error."""
        response = client.get('/api/auth/callback?error=access_denied&error_description=User+denied+access')
        
        assert response.status_code == 400
        data = response.get_json()
        
        assert data['success'] is False
        assert 'Authorization failed' in data['error']
        assert data['error_code'] == 'OAUTH_ERROR'
    
    def test_callback_token_exchange_failure(self, client, app):
        """Test callback when token exchange fails."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock valid state but failed token exchange
            mock_auth._validate_state.return_value = True
            mock_auth.exchange_code_for_tokens.return_value = False
            
            response = client.get('/api/auth/callback?code=test_code&state=test_state')
            
            assert response.status_code == 500
            data = response.get_json()
            
            assert data['success'] is False
            assert 'Failed to exchange authorization code' in data['error']
            assert data['error_code'] == 'TOKEN_EXCHANGE_FAILED'
    
    def test_callback_state_validation_error(self, client, app):
        """Test callback when state validation fails during exchange."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock valid state but token exchange raises ValueError
            mock_auth._validate_state.return_value = True
            mock_auth.exchange_code_for_tokens.side_effect = ValueError("Invalid state token")
            
            response = client.get('/api/auth/callback?code=test_code&state=test_state')
            
            assert response.status_code == 400
            data = response.get_json()
            
            assert data['success'] is False
            assert data['error_code'] == 'STATE_VALIDATION_ERROR'
    
    def test_callback_missing_credentials_file(self, client, app):
        """Test callback when credentials file is missing."""
        with patch('cantonese_anki_generator.web.api.GoogleDocsAuthenticator') as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth_class.return_value = mock_auth
            
            # Mock valid state but credentials file not found error
            mock_auth._validate_state.return_value = True
            mock_auth.exchange_code_for_tokens.side_effect = FileNotFoundError("Credentials not found")
            
            response = client.get('/api/auth/callback?code=test_code&state=test_state')
            
            assert response.status_code == 500
            data = response.get_json()
            
            assert data['success'] is False
            # Now uses centralized error response with more detailed message
            assert 'Credentials' in data['error']
            assert data['error_code'] == 'MISSING_CREDENTIALS'
