"""
Authentication data models for web-based OAuth flow.

This module defines data structures used throughout the authentication system
to represent token status, OAuth state, and authentication modes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class AuthMode(Enum):
    """Authentication execution modes."""
    
    CLI = "cli"
    """Command-line interface mode using local server."""
    
    WEB = "web"
    """Web application mode using callback endpoint."""
    
    AUTO = "auto"
    """Automatic detection based on execution context."""


@dataclass
class TokenStatus:
    """Represents current OAuth token status."""
    
    valid: bool
    """Whether tokens are currently valid."""
    
    expired: bool
    """Whether tokens have expired."""
    
    expires_at: Optional[datetime]
    """When tokens will expire (None if no tokens)."""
    
    needs_refresh: bool
    """Whether tokens should be refreshed soon."""
    
    has_refresh_token: bool
    """Whether a refresh token is available."""
    
    authorization_url: Optional[str] = None
    """OAuth URL for re-authentication (None if authenticated)."""


@dataclass
class OAuthState:
    """Represents OAuth flow state for CSRF protection."""
    
    state_token: str
    """Random state token for CSRF validation."""
    
    created_at: datetime
    """When this state was created."""
    
    redirect_uri: str
    """Callback URI for this OAuth flow."""
    
    def is_expired(self, max_age_minutes: int = 10) -> bool:
        """
        Check if state token has expired.
        
        Args:
            max_age_minutes: Maximum age in minutes before expiration
            
        Returns:
            True if the state token has expired, False otherwise
        """
        age = datetime.now() - self.created_at
        return age.total_seconds() > (max_age_minutes * 60)
