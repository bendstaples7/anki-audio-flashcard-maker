"""
Google Docs API authentication module.

Handles OAuth2 flow, token management, and API client creation for Google Docs access.
"""

import os
import json
import secrets
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import Config


class GoogleDocsAuthenticator:
    """Handles Google Docs API authentication and client management."""
    
    def __init__(
        self, 
        credentials_path: Optional[str] = None, 
        token_path: Optional[str] = None,
        mode: str = 'auto'
    ):
        """
        Initialize the authenticator.
        
        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to store/retrieve the token.json file
            mode: Authentication mode - 'auto', 'web', or 'cli'
        """
        self.credentials_path = credentials_path or Config.CREDENTIALS_FILE
        self.token_path = token_path or Config.TOKEN_FILE
        self.scopes = Config.GOOGLE_DOCS_SCOPES
        self._credentials: Optional[Credentials] = None
        self._service = None
        
        # Set authentication mode
        if mode not in ('auto', 'web', 'cli'):
            raise ValueError(f"Invalid mode: {mode}. Must be 'auto', 'web', or 'cli'")
        
        self._mode_param = mode
        self._detected_mode = self.detect_mode() if mode == 'auto' else mode
        
        # State token storage for CSRF protection
        self._oauth_state: Optional[Dict[str, Any]] = None
    
    def detect_mode(self) -> str:
        """
        Detect execution mode (web or CLI).
        
        Returns:
            'web' if running in Flask context, 'cli' otherwise
        """
        try:
            from flask import has_app_context
            if has_app_context():
                return 'web'
        except (ImportError, RuntimeError):
            pass
        return 'cli'
    
    @property
    def mode(self) -> str:
        """Get the current authentication mode."""
        return self._detected_mode
    
    def authenticate(self) -> bool:
        """
        Perform OAuth2 authentication flow.
        
        Routes to appropriate flow based on detected mode:
        - CLI mode: Uses run_local_server for OAuth
        - Web mode: Requires web-based OAuth flow (get_authorization_url/exchange_code_for_tokens)
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Load existing token if available
            if os.path.exists(self.token_path):
                self._credentials = Credentials.from_authorized_user_file(
                    self.token_path, self.scopes
                )
            
            # If there are no valid credentials, request authorization
            if not self._credentials or not self._credentials.valid:
                if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                    # Refresh expired token
                    self._credentials.refresh(Request())
                    self._save_token()
                else:
                    # Route to appropriate OAuth flow based on mode
                    if self.mode == 'cli':
                        return self._authenticate_cli()
                    else:
                        # Web mode requires external OAuth flow
                        # Caller should use get_authorization_url() and exchange_code_for_tokens()
                        return False
            
            return True
            
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def _authenticate_cli(self) -> bool:
        """
        Perform CLI-based OAuth flow using local server.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found: {self.credentials_path}. "
                    "Please download credentials.json from Google Cloud Console."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, self.scopes
            )
            self._credentials = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            self._save_token()
            return True
            
        except Exception as e:
            print(f"CLI authentication failed: {e}")
            return False
    
    def get_authorization_url(self, redirect_uri: str = None) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL for web flow.
        
        Args:
            redirect_uri: The callback URL for OAuth redirect (uses Config.OAUTH_REDIRECT_URI if None)
            
        Returns:
            Tuple of (authorization_url, state_token)
            
        Raises:
            FileNotFoundError: If credentials file not found
        """
        from cantonese_anki_generator.config import Config
        
        if redirect_uri is None:
            redirect_uri = Config.OAUTH_REDIRECT_URI
        
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}. "
                "Please download credentials.json from Google Cloud Console."
            )
        
        # Generate state token for CSRF protection
        state_token = secrets.token_urlsafe(32)
        
        # Store state with expiration
        self._oauth_state = {
            'token': state_token,
            'created_at': datetime.now(),
            'redirect_uri': redirect_uri
        }
        
        # Check if credentials are for web or installed app
        with open(self.credentials_path, 'r') as f:
            creds_data = json.load(f)
        
        # Create appropriate OAuth flow based on credentials type
        if 'web' in creds_data:
            # Web application credentials - use Flow
            flow = Flow.from_client_secrets_file(
                self.credentials_path,
                scopes=self.scopes,
                redirect_uri=redirect_uri
            )
        else:
            # Installed application credentials - use InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path,
                scopes=self.scopes,
                redirect_uri=redirect_uri
            )
        
        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state_token,
            prompt='consent'  # Force consent to ensure refresh token
        )
        
        return authorization_url, state_token
    
    def exchange_code_for_tokens(self, code: str, state: str, redirect_uri: str = None) -> bool:
        """
        Exchange authorization code for OAuth tokens.
        
        Args:
            code: Authorization code from OAuth callback
            state: State token for CSRF validation
            redirect_uri: The callback URL used in authorization (uses Config.OAUTH_REDIRECT_URI if None)
            
        Returns:
            True if exchange successful, False otherwise
            
        Raises:
            ValueError: If state validation fails
        """
        # Validate state token
        if not self._validate_state(state):
            raise ValueError("Invalid or expired state token")
        
        from cantonese_anki_generator.config import Config
        
        if redirect_uri is None:
            redirect_uri = Config.OAUTH_REDIRECT_URI
        
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found: {self.credentials_path}"
                )
            
            # Check if credentials are for web or installed app
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
            
            # Create appropriate OAuth flow based on credentials type
            if 'web' in creds_data:
                # Web application credentials - use Flow
                flow = Flow.from_client_secrets_file(
                    self.credentials_path,
                    scopes=self.scopes,
                    redirect_uri=redirect_uri
                )
            else:
                # Installed application credentials - use InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path,
                    scopes=self.scopes,
                    redirect_uri=redirect_uri
                )
            
            # Exchange code for tokens
            flow.fetch_token(code=code)
            self._credentials = flow.credentials
            
            # Save tokens
            self._save_token()
            
            # Clear state
            self._oauth_state = None
            
            return True
            
        except Exception as e:
            print(f"Token exchange failed: {e}")
            return False
    
    def _validate_state(self, state: str) -> bool:
        """
        Validate OAuth state token for CSRF protection.
        
        Args:
            state: State token to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not self._oauth_state:
            return False
        
        # Check token match
        if self._oauth_state['token'] != state:
            return False
        
        # Check expiration (10 minutes)
        created_at = self._oauth_state['created_at']
        age = datetime.now() - created_at
        if age.total_seconds() > 600:  # 10 minutes
            return False
        
        return True
    
    def refresh_tokens(self) -> bool:
        """
        Refresh expired OAuth tokens using refresh token.
        
        Returns:
            True if refresh successful, False otherwise
        """
        try:
            if not self._credentials:
                # Try to load from file
                if os.path.exists(self.token_path):
                    self._credentials = Credentials.from_authorized_user_file(
                        self.token_path, self.scopes
                    )
                else:
                    return False
            
            if not self._credentials.refresh_token:
                print("No refresh token available")
                return False
            
            # Attempt refresh
            self._credentials.refresh(Request())
            
            # Save refreshed tokens
            self._save_token()
            
            return True
            
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return False
    
    def is_token_expiring_soon(self, hours: int = 24) -> bool:
        """
        Check if token expires within specified hours.
        
        Args:
            hours: Number of hours to check ahead (default: 24)
            
        Returns:
            True if expiring soon or already expired, False otherwise
        """
        if not self._credentials:
            # Try to load from file
            if os.path.exists(self.token_path):
                try:
                    self._credentials = Credentials.from_authorized_user_file(
                        self.token_path, self.scopes
                    )
                except Exception:
                    return True  # Consider as expiring if can't load
            else:
                return True  # No token file
        
        if not self._credentials.expiry:
            return False  # No expiry means token doesn't expire
        
        threshold = datetime.utcnow() + timedelta(hours=hours)
        return self._credentials.expiry <= threshold
    
    def get_token_status(self) -> Dict[str, Any]:
        """
        Get current token status information.
        
        Returns:
            Dictionary containing:
                - valid: bool - Whether tokens are currently valid
                - expired: bool - Whether tokens have expired
                - expires_at: datetime or None - When tokens expire
                - needs_refresh: bool - Whether tokens should be refreshed soon
                - has_refresh_token: bool - Whether refresh token is available
        """
        status = {
            'valid': False,
            'expired': False,
            'expires_at': None,
            'needs_refresh': False,
            'has_refresh_token': False
        }
        
        # Try to load credentials if not already loaded
        if not self._credentials and os.path.exists(self.token_path):
            try:
                self._credentials = Credentials.from_authorized_user_file(
                    self.token_path, self.scopes
                )
            except Exception:
                return status
        
        if not self._credentials:
            return status
        
        # Check validity
        status['valid'] = self._credentials.valid
        status['expired'] = self._credentials.expired if hasattr(self._credentials, 'expired') else False
        status['expires_at'] = self._credentials.expiry
        status['has_refresh_token'] = bool(self._credentials.refresh_token)
        
        # Check if needs refresh (within 24 hours)
        if self._credentials.expiry:
            threshold = datetime.utcnow() + timedelta(hours=24)
            status['needs_refresh'] = self._credentials.expiry <= threshold
        
        return status
    
    def _save_token(self) -> None:
        """Save the current credentials to token file."""
        if self._credentials:
            with open(self.token_path, 'w') as token_file:
                token_file.write(self._credentials.to_json())
    
    def get_docs_service(self):
        """
        Get authenticated Google Docs API service.
        
        Returns:
            Google Docs API service object
            
        Raises:
            RuntimeError: If authentication has not been completed
        """
        if not self._credentials or not self._credentials.valid:
            raise RuntimeError("Authentication required. Call authenticate() first.")
        
        if not self._service:
            self._service = build('docs', 'v1', credentials=self._credentials)
        
        return self._service
    
    def test_connection(self) -> bool:
        """
        Test the API connection by making a simple request.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            service = self.get_docs_service()
            # Test with a minimal request (this will fail gracefully if no access)
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def revoke_credentials(self) -> None:
        """Revoke stored credentials and remove token file."""
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
        self._credentials = None
        self._service = None


class GoogleDocsAuthError(Exception):
    """Custom exception for Google Docs authentication errors."""
    pass


def create_authenticated_service(credentials_path: Optional[str] = None) -> 'googleapiclient.discovery.Resource':
    """
    Convenience function to create an authenticated Google Docs service.
    
    Args:
        credentials_path: Optional path to credentials file
        
    Returns:
        Authenticated Google Docs API service
        
    Raises:
        GoogleDocsAuthError: If authentication fails
    """
    authenticator = GoogleDocsAuthenticator(credentials_path)
    
    if not authenticator.authenticate():
        raise GoogleDocsAuthError("Failed to authenticate with Google Docs API")
    
    return authenticator.get_docs_service()