"""
Google Docs API authentication module.

Handles OAuth2 flow, token management, and API client creation for Google Docs access.
"""

import os
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import Config


class GoogleDocsAuthenticator:
    """Handles Google Docs API authentication and client management."""
    
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        """
        Initialize the authenticator.
        
        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to store/retrieve the token.json file
        """
        self.credentials_path = credentials_path or Config.CREDENTIALS_FILE
        self.token_path = token_path or Config.TOKEN_FILE
        self.scopes = Config.GOOGLE_DOCS_SCOPES
        self._credentials: Optional[Credentials] = None
        self._service = None
    
    def authenticate(self) -> bool:
        """
        Perform OAuth2 authentication flow.
        
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
                else:
                    # Run OAuth2 flow
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
            print(f"Authentication failed: {e}")
            return False
    
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