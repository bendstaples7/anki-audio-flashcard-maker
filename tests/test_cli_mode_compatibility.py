"""Tests for CLI mode backward compatibility."""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

from cantonese_anki_generator.processors.google_docs_auth import GoogleDocsAuthenticator
from google.oauth2.credentials import Credentials


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def credentials_file(temp_dir):
    """Create mock credentials.json file."""
    creds_path = os.path.join(temp_dir, 'credentials.json')
    creds_data = {
        "installed": {
            "client_id": "test_client_id.apps.googleusercontent.com",
            "project_id": "test_project",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "test_client_secret",
            "redirect_uris": ["http://localhost"]
        }
    }
    with open(creds_path, 'w') as f:
        json.dump(creds_data, f)
    return creds_path


@pytest.fixture
def token_file(temp_dir):
    """Create path for token.json file."""
    return os.path.join(temp_dir, 'token.json')


class TestCLIModeDetection:
    """Test CLI mode detection."""
    
    def test_detect_cli_mode_outside_flask(self, credentials_file, token_file):
        """Test that CLI mode is detected when not in Flask context."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='auto'
        )
        
        # Should detect CLI mode when not in Flask context
        assert auth.mode == 'cli'
    
    def test_detect_web_mode_in_flask(self, credentials_file, token_file):
        """Test that web mode is detected when in Flask context."""
        with patch('flask.has_app_context') as mock_has_context:
            mock_has_context.return_value = True
            
            auth = GoogleDocsAuthenticator(
                credentials_path=credentials_file,
                token_path=token_file,
                mode='auto'
            )
            
            # Should detect web mode when in Flask context
            assert auth.mode == 'web'
    
    def test_explicit_cli_mode(self, credentials_file, token_file):
        """Test explicit CLI mode setting."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        assert auth.mode == 'cli'
    
    def test_explicit_web_mode(self, credentials_file, token_file):
        """Test explicit web mode setting."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='web'
        )
        
        assert auth.mode == 'web'


class TestCLIAuthentication:
    """Test CLI authentication flow."""
    
    def test_cli_mode_uses_run_local_server(self, credentials_file, token_file):
        """Test that CLI mode uses run_local_server for OAuth."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            # Mock the flow
            mock_flow = MagicMock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            # Mock credentials
            mock_creds = MagicMock(spec=Credentials)
            mock_creds.valid = True
            mock_creds.expired = False
            mock_creds.to_json.return_value = '{"token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            
            # Authenticate
            result = auth.authenticate()
            
            # Verify run_local_server was called
            assert result is True
            mock_flow.run_local_server.assert_called_once_with(port=0)
            
            # Verify token was saved
            assert os.path.exists(token_file)
    
    def test_cli_authentication_with_missing_credentials(self, token_file):
        """Test CLI authentication fails gracefully with missing credentials."""
        auth = GoogleDocsAuthenticator(
            credentials_path='/nonexistent/credentials.json',
            token_path=token_file,
            mode='cli'
        )
        
        result = auth.authenticate()
        
        # Should fail but not crash
        assert result is False
    
    def test_cli_authentication_with_valid_existing_token(self, credentials_file, token_file):
        """Test CLI authentication succeeds with valid existing token."""
        # Create valid token file
        expires_at = datetime.utcnow() + timedelta(days=3)
        token_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
            "expiry": expires_at.isoformat() + "Z"
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            result = auth.authenticate()
            
            # Should succeed without calling run_local_server
            assert result is True
            mock_flow_class.from_client_secrets_file.assert_not_called()
    
    def test_cli_authentication_refreshes_expired_token(self, credentials_file, token_file):
        """Test CLI authentication refreshes expired token."""
        # Create expired token file with refresh token
        expires_at = datetime.utcnow() - timedelta(hours=1)
        token_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
            "expiry": expires_at.isoformat() + "Z"
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        with patch('google.auth.transport.requests.Request'):
            with patch.object(Credentials, 'refresh') as mock_refresh:
                result = auth.authenticate()
                
                # Should succeed by refreshing
                assert result is True
                mock_refresh.assert_called_once()


class TestCrossModTokenSharing:
    """Test that CLI and web modes share token files."""
    
    def test_cli_created_token_usable_in_web_mode(self, credentials_file, token_file):
        """Test that tokens created in CLI mode can be used in web mode."""
        # Create token in CLI mode
        expires_at = datetime.utcnow() + timedelta(days=3)
        token_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
            "expiry": expires_at.isoformat() + "Z"
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        # Create authenticator in web mode
        auth_web = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='web'
        )
        
        # Check token status
        status = auth_web.get_token_status()
        
        # Should recognize the token
        assert status['valid'] is True
        assert status['has_refresh_token'] is True
        assert status['expires_at'] is not None
    
    def test_web_created_token_usable_in_cli_mode(self, credentials_file, token_file):
        """Test that tokens created in web mode can be used in CLI mode."""
        # Simulate web mode token creation
        expires_at = datetime.utcnow() + timedelta(days=3)
        token_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
            "expiry": expires_at.isoformat() + "Z"
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        # Create authenticator in CLI mode
        auth_cli = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        # Authenticate should succeed without new OAuth flow
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            result = auth_cli.authenticate()
            
            # Should succeed using existing token
            assert result is True
            # Should not initiate new OAuth flow
            mock_flow_class.from_client_secrets_file.assert_not_called()
    
    def test_both_modes_use_same_token_file(self, credentials_file, token_file):
        """Test that both modes read and write to the same token file."""
        # Create initial token
        expires_at = datetime.utcnow() + timedelta(days=3)
        token_data = {
            "token": "initial_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/documents.readonly"],
            "expiry": expires_at.isoformat() + "Z"
        }
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        
        # Create authenticators for both modes
        auth_cli = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        auth_web = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='web'
        )
        
        # Both should read the same token
        status_cli = auth_cli.get_token_status()
        status_web = auth_web.get_token_status()
        
        assert status_cli['valid'] is True
        assert status_web['valid'] is True
        assert status_cli['expires_at'] == status_web['expires_at']


class TestCLIModeDoesNotUseWebFlow:
    """Test that CLI mode never uses web-based OAuth flow."""
    
    def test_cli_mode_authenticate_does_not_call_web_methods(self, credentials_file, token_file):
        """Test that CLI mode authenticate() doesn't use web OAuth methods."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            mock_creds = MagicMock(spec=Credentials)
            mock_creds.valid = True
            mock_creds.to_json.return_value = '{"token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            
            # Spy on web methods
            with patch.object(auth, 'get_authorization_url') as mock_get_url:
                with patch.object(auth, 'exchange_code_for_tokens') as mock_exchange:
                    result = auth.authenticate()
                    
                    # Should succeed
                    assert result is True
                    
                    # Should not call web methods
                    mock_get_url.assert_not_called()
                    mock_exchange.assert_not_called()
                    
                    # Should call run_local_server
                    mock_flow.run_local_server.assert_called_once()
    
    def test_cli_mode_never_generates_authorization_url_during_auth(self, credentials_file, token_file):
        """Test that CLI mode doesn't generate authorization URLs during authentication."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file,
            mode='cli'
        )
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            mock_creds = MagicMock(spec=Credentials)
            mock_creds.valid = True
            mock_creds.to_json.return_value = '{"token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            
            # Mock authorization_url method to track calls
            mock_flow.authorization_url = MagicMock()
            
            result = auth.authenticate()
            
            # Should succeed
            assert result is True
            
            # Should not generate authorization URL (web flow)
            mock_flow.authorization_url.assert_not_called()


class TestCLIModeBackwardCompatibility:
    """Test backward compatibility with existing CLI applications."""
    
    def test_default_mode_is_cli_outside_flask(self, credentials_file, token_file):
        """Test that default mode is CLI when not in Flask context."""
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file
        )
        
        # Default should be CLI mode
        assert auth.mode == 'cli'
    
    def test_existing_cli_code_continues_to_work(self, credentials_file, token_file):
        """Test that existing CLI code patterns continue to work."""
        # Simulate existing CLI usage pattern
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file
        )
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            mock_creds = MagicMock(spec=Credentials)
            mock_creds.valid = True
            mock_creds.to_json.return_value = '{"token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            
            # Old pattern: just call authenticate()
            result = auth.authenticate()
            
            # Should work as before
            assert result is True
            mock_flow.run_local_server.assert_called_once()
    
    def test_cli_mode_with_no_mode_parameter(self, credentials_file, token_file):
        """Test CLI mode works when mode parameter is not specified."""
        # Old code wouldn't pass mode parameter
        auth = GoogleDocsAuthenticator(
            credentials_path=credentials_file,
            token_path=token_file
        )
        
        # Should default to auto-detect, which is CLI outside Flask
        assert auth.mode == 'cli'
        
        with patch('cantonese_anki_generator.processors.google_docs_auth.InstalledAppFlow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            
            mock_creds = MagicMock(spec=Credentials)
            mock_creds.valid = True
            mock_creds.to_json.return_value = '{"token": "test_token"}'
            mock_flow.run_local_server.return_value = mock_creds
            
            result = auth.authenticate()
            
            assert result is True
            mock_flow.run_local_server.assert_called_once()
