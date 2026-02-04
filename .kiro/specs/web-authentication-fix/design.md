# Design Document: Web Authentication Fix

## Overview

This design addresses the authentication failure issue in the Cantonese Anki Generator web application by replacing the CLI-oriented OAuth flow with a web-compatible implementation. The current system uses `flow.run_local_server(port=0)` which conflicts with the already-running Flask server. The solution implements a web-based OAuth callback flow, proactive token refresh, and background monitoring to ensure seamless authentication without CLI intervention.

The design maintains backward compatibility with the CLI application while adding web-specific authentication capabilities. It introduces a dual-mode authentication system that detects the execution context and selects the appropriate OAuth flow.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Web Application                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌─────────────────────────┐  │
│  │  Web Interface   │────────▶│  Authentication Status  │  │
│  │  (Frontend)      │         │  API Endpoint           │  │
│  └──────────────────┘         └─────────────────────────┘  │
│           │                              │                   │
│           │                              ▼                   │
│           │                    ┌─────────────────────────┐  │
│           │                    │  OAuth Callback         │  │
│           └───────────────────▶│  Endpoint               │  │
│                                └─────────────────────────┘  │
│                                          │                   │
└──────────────────────────────────────────┼───────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────┐
                    │   Dual-Mode Authenticator            │
                    │   (Web + CLI Support)                │
                    ├──────────────────────────────────────┤
                    │  • Mode Detection                    │
                    │  • Token Management                  │
                    │  • Automatic Refresh                 │
                    └──────────────────────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
          ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
          │ Web OAuth Flow  │   │ CLI OAuth Flow  │   │ Token Refresh   │
          │ (Authorization  │   │ (Local Server)  │   │ Background Task │
          │  Code)          │   │                 │   │                 │
          └─────────────────┘   └─────────────────┘   └─────────────────┘
                    │                      │                      │
                    └──────────────────────┴──────────────────────┘
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │  token.json     │
                                  │  (Persistent    │
                                  │   Storage)      │
                                  └─────────────────┘
```

### Component Interaction Flow

1. **Startup**: Application initializes authenticator, checks token validity
2. **Token Validation**: Authenticator loads existing tokens and validates expiration
3. **Automatic Refresh**: If tokens expire soon, automatic refresh is attempted
4. **User Request**: When user accesses Google Docs/Sheets, authentication is verified
5. **Re-authentication**: If tokens are invalid, user is directed to OAuth flow
6. **Background Monitoring**: Periodic task checks token health every 6 hours

## Components and Interfaces

### 1. Dual-Mode Authenticator

**Purpose**: Central authentication manager that supports both web and CLI modes.

**Location**: `cantonese_anki_generator/processors/google_docs_auth.py` (enhanced)

**Key Methods**:

```python
class GoogleDocsAuthenticator:
    def __init__(
        self, 
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        mode: str = 'auto'  # 'auto', 'web', 'cli'
    ):
        """Initialize authenticator with mode detection."""
        
    def detect_mode(self) -> str:
        """
        Detect execution mode (web or CLI).
        Returns: 'web' or 'cli'
        """
        
    def authenticate(self) -> bool:
        """
        Perform authentication using appropriate flow for current mode.
        Returns: True if successful, False otherwise
        """
        
    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL for web flow.
        Returns: (authorization_url, state_token)
        """
        
    def exchange_code_for_tokens(self, code: str, state: str) -> bool:
        """
        Exchange authorization code for OAuth tokens.
        Args:
            code: Authorization code from OAuth callback
            state: State token for CSRF protection
        Returns: True if successful, False otherwise
        """
        
    def refresh_tokens(self) -> bool:
        """
        Refresh expired OAuth tokens using refresh token.
        Returns: True if successful, False otherwise
        """
        
    def get_token_status(self) -> Dict[str, Any]:
        """
        Get current token status information.
        Returns: {
            'valid': bool,
            'expired': bool,
            'expires_at': datetime,
            'needs_refresh': bool,
            'has_refresh_token': bool
        }
        """
        
    def is_token_expiring_soon(self, hours: int = 24) -> bool:
        """
        Check if token expires within specified hours.
        Args:
            hours: Number of hours to check ahead
        Returns: True if expiring soon, False otherwise
        """
```

### 2. Authentication Status API

**Purpose**: Provide authentication status to frontend and handle status queries.

**Location**: `cantonese_anki_generator/web/api.py` (new endpoint)

**Endpoint**: `GET /api/auth/status`

**Response Format**:
```json
{
    "authenticated": true,
    "token_valid": true,
    "expires_at": "2024-02-15T10:30:00Z",
    "expires_in_hours": 48,
    "needs_reauth": false,
    "authorization_url": null
}
```

**When authentication needed**:
```json
{
    "authenticated": false,
    "token_valid": false,
    "expires_at": null,
    "expires_in_hours": 0,
    "needs_reauth": true,
    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

### 3. OAuth Callback Endpoint

**Purpose**: Handle OAuth authorization callback and exchange code for tokens.

**Location**: `cantonese_anki_generator/web/api.py` (new endpoint)

**Endpoint**: `GET /api/auth/callback`

**Query Parameters**:
- `code`: Authorization code from Google
- `state`: State token for CSRF validation
- `error`: Error code if authorization failed

**Success Response**:
```json
{
    "success": true,
    "message": "Authentication successful",
    "redirect_url": "/"
}
```

**Error Response**:
```json
{
    "success": false,
    "error": "Authentication failed: invalid state token",
    "error_code": "INVALID_STATE"
}
```

### 4. Token Refresh Background Task

**Purpose**: Periodically check token expiration and refresh proactively.

**Location**: `cantonese_anki_generator/web/token_monitor.py` (new module)

**Implementation**: Uses APScheduler's BackgroundScheduler

**Key Functions**:

```python
class TokenMonitor:
    def __init__(self, authenticator: GoogleDocsAuthenticator):
        """Initialize token monitor with authenticator instance."""
        
    def start(self):
        """Start background monitoring task."""
        
    def stop(self):
        """Stop background monitoring task."""
        
    def check_and_refresh(self):
        """
        Check token expiration and refresh if needed.
        Called every 6 hours by scheduler.
        """
```

### 5. Web Application Integration

**Purpose**: Initialize authentication system on Flask app startup.

**Location**: `cantonese_anki_generator/web/app.py` (enhanced)

**Initialization Flow**:
1. Create authenticator instance in web mode
2. Validate existing tokens on startup
3. Start background token monitor
4. Register authentication endpoints

## Data Models

### Token Status Model

```python
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
    
    authorization_url: Optional[str]
    """OAuth URL for re-authentication (None if authenticated)."""
```

### OAuth State Model

```python
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
        """Check if state token has expired."""
        age = datetime.now() - self.created_at
        return age.total_seconds() > (max_age_minutes * 60)
```

### Authentication Mode Enum

```python
class AuthMode(Enum):
    """Authentication execution modes."""
    
    CLI = "cli"
    """Command-line interface mode using local server."""
    
    WEB = "web"
    """Web application mode using callback endpoint."""
    
    AUTO = "auto"
    """Automatic detection based on execution context."""
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Web Mode Never Uses Local Server

*For any* authentication attempt in web mode, the system should never call `run_local_server` and should instead use the web-based OAuth callback flow.

**Validates: Requirements 1.1**

### Property 2: Authorization URL Generation

*For any* request to initiate web-based authentication, the system should return a valid Google OAuth URL containing required parameters (client_id, redirect_uri, scope, state) and a unique state token for CSRF protection.

**Validates: Requirements 1.2**

### Property 3: Token Persistence After Exchange

*For any* successful authorization code exchange or token refresh, the resulting OAuth tokens should be persisted to the Token_File and be loadable in subsequent sessions.

**Validates: Requirements 1.4, 2.3, 8.4**

### Property 4: CLI Mode Backward Compatibility

*For any* authentication attempt when running in CLI mode, the system should use the `run_local_server` method for OAuth flow.

**Validates: Requirements 1.5, 8.2**

### Property 5: Proactive Token Refresh

*For any* OAuth token that expires within 24 hours and has a valid refresh token, the system should attempt automatic refresh before the token expires.

**Validates: Requirements 2.2**

### Property 6: Refresh Failure Handling

*For any* token refresh attempt that fails, the system should update the authentication status to indicate user intervention is required and should not crash or block operations.

**Validates: Requirements 2.4, 7.4**

### Property 7: Status Response Completeness

*For any* authentication status request, the response should include token validity state, and when tokens are invalid should include an authorization URL, and when tokens are valid should include expiration timestamp.

**Validates: Requirements 3.2, 3.3, 3.4**

### Property 8: Authentication Error Responses

*For any* Google API request that fails due to authentication, the system should return a response containing a specific error code, user-friendly message, and authorization URL for re-authentication.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 9: Unauthenticated Request Rejection

*For any* file processing request when authentication is invalid, the system should reject the request with authentication instructions before attempting to access Google APIs.

**Validates: Requirements 4.4**

### Property 10: File Preservation on Auth Failure

*For any* file processing operation that fails due to authentication, uploaded files should remain accessible for retry after re-authentication.

**Validates: Requirements 4.5**

### Property 11: CSRF State Validation

*For any* OAuth callback request, the system should validate that the state parameter matches a previously generated state token and reject requests with invalid or missing state tokens.

**Validates: Requirements 6.2**

### Property 12: Authorization Code Exchange

*For any* valid authorization code received at the callback endpoint, the system should successfully exchange it for OAuth tokens containing both access_token and refresh_token.

**Validates: Requirements 6.3**

### Property 13: Background Refresh Trigger

*For any* token that the background monitor detects as expiring within 24 hours, the monitor should trigger an automatic refresh attempt.

**Validates: Requirements 7.3**

### Property 14: Mode Detection Consistency

*For any* execution context, the authentication system should correctly detect whether it's running in CLI or web mode and use the appropriate OAuth flow for that mode.

**Validates: Requirements 8.1, 8.2, 8.3**

### Property 15: Cross-Mode Token Reuse

*For any* valid token created in one mode (CLI or web), the system should recognize and use that token when running in the other mode without requiring re-authentication.

**Validates: Requirements 8.5**

## Error Handling

### Error Categories

1. **Token Expiration Errors**
   - **Cause**: OAuth tokens have expired
   - **Handling**: Attempt automatic refresh; if refresh fails, provide authorization URL
   - **User Action**: Click authorization URL to re-authenticate

2. **Missing Credentials Errors**
   - **Cause**: credentials.json file not found
   - **Handling**: Return clear error message with setup instructions
   - **User Action**: Download credentials from Google Cloud Console

3. **Invalid Refresh Token Errors**
   - **Cause**: Refresh token has been revoked or is invalid
   - **Handling**: Mark authentication as requiring full re-authorization
   - **User Action**: Complete full OAuth flow again

4. **CSRF Validation Errors**
   - **Cause**: State token mismatch in OAuth callback
   - **Handling**: Reject callback and log security warning
   - **User Action**: Restart authentication flow

5. **Network Errors**
   - **Cause**: Cannot reach Google OAuth servers
   - **Handling**: Return error with retry suggestion
   - **User Action**: Check internet connection and retry

### Error Response Format

All authentication errors follow a consistent format:

```json
{
    "success": false,
    "error": "Human-readable error message",
    "error_code": "MACHINE_READABLE_CODE",
    "action_required": "Specific user action",
    "authorization_url": "https://accounts.google.com/..." // if applicable
}
```

### Graceful Degradation

The system is designed to degrade gracefully:

1. **Startup without credentials**: Application starts successfully, authentication endpoints return "not configured" status
2. **Expired tokens**: Application continues running, API requests return authentication required errors
3. **Background task failure**: Monitoring continues, errors are logged but don't affect main application
4. **Callback endpoint errors**: Errors are displayed to user with retry instructions

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and integration points
- **Property tests**: Verify universal properties across all inputs

Together, these provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness.

### Unit Testing Focus

Unit tests should cover:

1. **Startup sequence**: Test app initialization with various token states (missing, expired, valid)
2. **API endpoint responses**: Test status and callback endpoints with specific scenarios
3. **Mode detection**: Test detection logic with mocked execution contexts
4. **Error scenarios**: Test specific error conditions (missing credentials, network failures)
5. **Integration**: Test interaction between authenticator and Flask endpoints

### Property-Based Testing

Property tests should be implemented using Hypothesis with minimum 100 iterations per test. Each test must reference its design document property using the tag format:

**Feature: web-authentication-fix, Property {number}: {property_text}**

Property tests should cover:

1. **Token persistence (Property 3)**: Generate random token data, save and reload, verify equivalence
2. **Status responses (Property 7)**: Generate various token states, verify response completeness
3. **CSRF validation (Property 11)**: Generate random state tokens, verify validation logic
4. **Mode detection (Property 14)**: Generate various execution contexts, verify correct mode selection
5. **Cross-mode compatibility (Property 15)**: Generate tokens in one mode, verify usability in other mode

### Test Configuration

- Minimum 100 iterations for each property-based test
- Use pytest markers: `@pytest.mark.unit` and `@pytest.mark.property`
- Mock Google OAuth endpoints to avoid external dependencies
- Use temporary directories for token files during tests
- Clean up test artifacts after each test run

### Testing Tools

- **pytest**: Main testing framework
- **hypothesis**: Property-based testing library
- **pytest-mock**: Mocking Google API calls
- **freezegun**: Time manipulation for token expiration tests
- **responses**: HTTP mocking for OAuth endpoints

## Implementation Notes

### APScheduler Integration

The background token monitor uses APScheduler's `BackgroundScheduler`:

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=check_and_refresh_tokens,
    trigger='interval',
    hours=6,
    id='token_refresh_monitor'
)
scheduler.start()
```

### Mode Detection Logic

Mode detection checks for Flask application context:

```python
def detect_mode(self) -> str:
    """Detect if running in web or CLI mode."""
    try:
        from flask import has_app_context
        if has_app_context():
            return 'web'
    except (ImportError, RuntimeError):
        pass
    return 'cli'
```

### State Token Management

State tokens are generated using secrets module and stored temporarily:

```python
import secrets
from datetime import datetime, timedelta

def generate_state_token() -> str:
    """Generate cryptographically secure state token."""
    return secrets.token_urlsafe(32)

# Store with expiration (10 minutes)
state_storage = {
    'token': generate_state_token(),
    'expires_at': datetime.now() + timedelta(minutes=10)
}
```

### Token Expiration Checking

Token expiration is checked using the credentials object:

```python
from datetime import datetime, timedelta

def is_token_expiring_soon(credentials, hours=24) -> bool:
    """Check if token expires within specified hours."""
    if not credentials or not credentials.expiry:
        return False
    
    threshold = datetime.utcnow() + timedelta(hours=hours)
    return credentials.expiry <= threshold
```

### Web OAuth Flow Sequence

1. User requests authentication status → receives authorization URL
2. User clicks URL → redirected to Google OAuth consent screen
3. User grants permission → Google redirects to callback endpoint with code
4. Callback endpoint validates state → exchanges code for tokens
5. Tokens saved to file → user redirected to main interface
6. Subsequent requests use saved tokens

### Backward Compatibility

The enhanced authenticator maintains full backward compatibility:

- CLI applications continue to work without changes
- Existing token files are recognized by both modes
- No changes required to existing CLI code
- Web mode is opt-in through mode parameter or automatic detection
