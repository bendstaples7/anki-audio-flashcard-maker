# Web Authentication Guide

## Overview

The Cantonese Anki Generator web application uses Google OAuth 2.0 to access Google Docs and Sheets on your behalf. This guide explains how to set up authentication, understand the authentication flow, and troubleshoot common issues.

## Quick Start

### First-Time Setup

1. **Get Google Cloud Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Docs API and Google Sheets API
   - Create OAuth 2.0 credentials (see detailed steps below)
   - Download the credentials file as `credentials.json`
   - Place `credentials.json` in the project root directory

2. **Configure OAuth Callback URL**
   - In Google Cloud Console, go to your OAuth 2.0 Client ID
   - Add authorized redirect URI: `http://localhost:3000/api/auth/callback`
   - For production deployments, add: `https://yourdomain.com/api/auth/callback`
   - Save the changes

3. **Start the Application**
   ```bash
   python -m cantonese_anki_generator.web.run
   ```

4. **Authenticate**
   - Open the web interface in your browser
   - The application will prompt you to authenticate if needed
   - Click the authentication link to authorize access
   - You'll be redirected back to the application after authorization

## Detailed Setup Instructions

### Creating Google Cloud OAuth Credentials

1. **Access Google Cloud Console**
   - Navigate to https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create or Select a Project**
   - Click the project dropdown at the top
   - Click "New Project" or select an existing project
   - Give your project a name (e.g., "Cantonese Anki Generator")

3. **Enable Required APIs**
   - Go to "APIs & Services" > "Library"
   - Search for "Google Docs API" and click "Enable"
   - Search for "Google Sheets API" and click "Enable"

4. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - If prompted, configure the OAuth consent screen:
     - Choose "External" user type
     - Fill in application name and support email
     - Add your email to test users
     - Save and continue through all steps
   
5. **Configure OAuth Client**
   - Application type: "Web application"
   - Name: "Cantonese Anki Generator Web"
   - Authorized redirect URIs:
     - Development: `http://localhost:3000/api/auth/callback`
     - Production: `https://yourdomain.com/api/auth/callback`
   - Click "Create"

6. **Download Credentials**
   - Click the download icon next to your newly created OAuth client
   - Save the file as `credentials.json` in your project root directory

### OAuth Callback URL Configuration

The OAuth callback URL is where Google redirects users after they authorize your application.

**Development Environment:**
```text
http://localhost:3000/api/auth/callback
```

**Production Environment:**
```text
https://yourdomain.com/api/auth/callback
```

**Important Notes:**
- The callback URL must exactly match what's configured in Google Cloud Console
- Include the protocol (http:// or https://)
- Do not include trailing slashes
- For custom ports, include the port number: `http://localhost:8080/api/auth/callback`

## Authentication Flow

### Web-Based Authentication Flow

1. **Initial Request**
   - User accesses the web application
   - Application checks for valid OAuth tokens
   - If tokens are missing or expired, authentication is required

2. **Authorization Request**
   - Application generates an authorization URL with:
     - Client ID from credentials.json
     - Redirect URI (callback endpoint)
     - Required scopes (Google Docs, Google Sheets)
     - State token for CSRF protection
   - User clicks the authorization link

3. **User Authorization**
   - User is redirected to Google's OAuth consent screen
   - User reviews requested permissions
   - User clicks "Allow" to grant access

4. **Authorization Callback**
   - Google redirects back to the callback URL with:
     - Authorization code
     - State token (for validation)
   - Application validates the state token
   - Application exchanges the code for OAuth tokens

5. **Token Storage**
   - Application receives access token and refresh token
   - Tokens are saved to `token.json`
   - User is redirected back to the main interface

6. **Authenticated Requests**
   - Subsequent API requests use the stored access token
   - Application automatically refreshes tokens when they expire

### Automatic Token Refresh

The application includes proactive token management:

- **Startup Check**: Validates tokens when the application starts
- **Proactive Refresh**: Refreshes tokens 24 hours before expiration
- **Background Monitoring**: Checks token health every 6 hours
- **Automatic Retry**: Attempts refresh before marking authentication as failed

## Authentication Status API

### Checking Authentication Status

**Endpoint:** `GET /api/auth/status`

**Response when authenticated:**
```json
{
  "authenticated": true,
  "token_valid": true,
  "expires_at": "2026-02-11T10:30:00Z",
  "expires_in_hours": 48,
  "needs_reauth": false,
  "authorization_url": null
}
```

**Response when authentication needed:**
```json
{
  "authenticated": false,
  "token_valid": false,
  "expires_at": null,
  "expires_in_hours": 0,
  "needs_reauth": true,
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."
}
```

**Response when credentials missing:**
```json
{
  "authenticated": false,
  "error": "Credentials file not found",
  "error_code": "MISSING_CREDENTIALS",
  "action_required": "Download credentials.json from Google Cloud Console"
}
```

**Using the Status Endpoint**

**JavaScript Example:**
```javascript
async function checkAuthStatus() {
  const response = await fetch('/api/auth/status');
  const status = await response.json();
  
  if (status.needs_reauth) {
    // Show authentication prompt with authorization URL
    window.location.href = status.authorization_url;
  } else if (status.authenticated) {
    // Proceed with normal operations
    console.log(`Token expires in ${status.expires_in_hours} hours`);
  }
}
```

**Python Example:**
```python
import requests

response = requests.get('http://localhost:3000/api/auth/status')
status = response.json()

if status['needs_reauth']:
    print(f"Please authenticate: {status['authorization_url']}")
elif status['authenticated']:
    print(f"Authenticated. Token expires at {status['expires_at']}")
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "Credentials file not found"

**Symptom:** Application starts but shows authentication error

**Cause:** The `credentials.json` file is missing or in the wrong location

**Solution:**
1. Download credentials from Google Cloud Console
2. Save as `credentials.json` in the project root directory
3. Verify the file exists: `ls credentials.json` (Unix) or `dir credentials.json` (Windows)
4. Restart the application

#### 2. "Redirect URI mismatch"

**Symptom:** OAuth error page showing "redirect_uri_mismatch"

**Cause:** The callback URL doesn't match what's configured in Google Cloud Console

**Solution:**
1. Check the error message for the actual redirect URI being used
2. Go to Google Cloud Console > Credentials
3. Edit your OAuth 2.0 Client ID
4. Add the exact redirect URI shown in the error
5. Save and wait a few minutes for changes to propagate
6. Try authentication again

**Common mismatches:**
- Missing protocol: Add `http://` or `https://`
- Wrong port: Ensure port matches (e.g., `:5000`)
- Trailing slash: Remove any trailing slashes
- Localhost vs 127.0.0.1: Use the same format in both places

#### 3. "Invalid state token" or CSRF validation error

**Symptom:** Callback fails with state validation error

**Cause:** State token expired or browser session issue

**Solution:**
1. Clear browser cookies for the application
2. Start a fresh authentication flow
3. Complete the OAuth flow within 10 minutes
4. Don't open multiple authentication tabs simultaneously

#### 4. "Token has been expired or revoked"

**Symptom:** Application shows authentication required despite recent authorization

**Cause:** Refresh token was revoked or expired

**Solution:**
1. Delete the `token.json` file
2. Restart the application
3. Complete the OAuth flow again
4. This will generate a new refresh token

**Why tokens get revoked:**
- User revoked access in Google Account settings
- Too many tokens issued (Google limits to 50 per user per client)
- Security concerns detected by Google
- Long period of inactivity (6 months+)

#### 5. "Access blocked: This app's request is invalid"

**Symptom:** OAuth consent screen shows error

**Cause:** OAuth consent screen not properly configured

**Solution:**
1. Go to Google Cloud Console > OAuth consent screen
2. Ensure app name and support email are filled in
3. Add your email address to "Test users" section
4. Save changes and try again

#### 6. Application starts but authentication doesn't work

**Symptom:** No authentication prompts appear

**Cause:** Application may not be in web mode

**Solution:**
1. Check application logs for mode detection
2. Verify Flask application is running
3. Ensure you're accessing through the web interface, not CLI
4. Check that `app.py` properly initializes the authenticator

#### 7. "Background token refresh failed"

**Symptom:** Logs show refresh failures every 6 hours

**Cause:** Refresh token is invalid or network issues

**Solution:**
1. Check internet connectivity
2. Verify `token.json` contains a refresh_token field
3. If refresh_token is missing, re-authenticate
4. Check Google Cloud Console for API quota limits

#### 8. Tokens expire too quickly

**Symptom:** Need to re-authenticate frequently

**Cause:** Access tokens naturally expire after 1 hour

**Solution:**
- This is normal behavior
- The application should automatically refresh tokens
- If automatic refresh isn't working:
  1. Check that `token.json` has a refresh_token
  2. Verify background monitor is running
  3. Check application logs for refresh errors

### Debugging Tips

#### Enable Verbose Logging

Add logging to see authentication details:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Check Token File

Inspect `token.json` to verify token structure:

```bash
cat token.json
```

Should contain:
```json
{
  "token": "ya29.a0...",
  "refresh_token": "1//0g...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/documents.readonly", ...],
  "expiry": "2026-02-04T12:00:00Z"
}
```

#### Test Authentication Manually

Use the status endpoint to check authentication:

```bash
curl http://localhost:3000/api/auth/status
```

#### Verify Credentials File

Check that `credentials.json` is valid JSON:

```bash
python -c "import json; print(json.load(open('credentials.json')))"
```

## Security Best Practices

### Protecting Credentials

1. **Never commit credentials to version control**
   - Add `credentials.json` to `.gitignore`
   - Add `token.json` to `.gitignore`

2. **Restrict file permissions**
   ```bash
   chmod 600 credentials.json
   chmod 600 token.json
   ```

3. **Use environment-specific credentials**
   - Different credentials for development and production
   - Separate OAuth clients for each environment

### OAuth Security

1. **State Token Validation**
   - Application validates state tokens to prevent CSRF attacks
   - State tokens expire after 10 minutes
   - Never disable state validation

2. **Redirect URI Validation**
   - Only add trusted redirect URIs to Google Cloud Console
   - Use HTTPS in production
   - Avoid wildcard redirect URIs

3. **Token Storage**
   - Tokens are stored locally in `token.json`
   - Never expose tokens in logs or error messages
   - Rotate tokens if compromised

### Production Deployment

1. **Use HTTPS**
   - Always use HTTPS in production
   - Configure SSL/TLS certificates
   - Update redirect URI to use `https://`

2. **Secure Token Storage**
   - Consider encrypting `token.json` at rest
   - Use secure file permissions
   - Regular token rotation

3. **Monitor Authentication**
   - Log authentication events
   - Alert on repeated failures
   - Track token refresh patterns

4. **Multi-Worker Deployments**
   
   When running with multiple workers (Gunicorn, uWSGI, etc.):
   
   **Background Token Monitor:**
   - Set `RUN_TOKEN_MONITOR=false` on all workers EXCEPT one
   - Only ONE worker should run the background token monitor
   - This prevents race conditions on `token.json`
   
   Example Gunicorn configuration:
   ```bash
   # Worker 1 (with token monitor)
   RUN_TOKEN_MONITOR=true gunicorn -w 1 -b 0.0.0.0:3000 "cantonese_anki_generator.web.app:create_app()"
   
   # Workers 2-4 (without token monitor)
   RUN_TOKEN_MONITOR=false gunicorn -w 3 -b 0.0.0.0:3001 "cantonese_anki_generator.web.app:create_app()"
   ```
   
   **File Locking:**
   - Token file operations use file locking to prevent corruption
   - Thread-safe locks prevent race conditions within a process
   - File locks (fcntl on Unix/Linux) prevent race conditions across processes
   - On Windows, only thread-level locking is available
   
   **Alternative: Single Worker with Sticky Sessions:**
   - Run with a single worker: `gunicorn -w 1`
   - Or use sticky sessions to route users to the same worker

## CLI Mode Compatibility

The authentication system supports both web and CLI modes:

### CLI Mode

When running from command line:
```bash
python -m cantonese_anki_generator "https://docs.google.com/..." audio.wav
```

- Uses local server OAuth flow (`run_local_server`)
- Opens browser automatically for authorization
- Stores tokens in the same `token.json` file

### Web Mode

When running as web application:
```bash
python -m cantonese_anki_generator.web.run
```

- Uses web-based OAuth callback flow
- Provides authorization URL in the interface
- Shares tokens with CLI mode

### Switching Between Modes

Tokens are shared between modes:
- Authenticate in CLI mode → tokens work in web mode
- Authenticate in web mode → tokens work in CLI mode
- No re-authentication needed when switching modes

## Advanced Configuration

### Custom Token Refresh Threshold

Modify token refresh timing in `config.py`:

```python
# Refresh tokens this many hours before expiration
TOKEN_REFRESH_THRESHOLD_HOURS = 24

# Background monitor check interval (hours between token health checks)
BACKGROUND_MONITOR_INTERVAL_HOURS = 6
```

### Custom OAuth Scopes

Add additional Google API scopes in `google_docs_auth.py`:

```python
SCOPES = [
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    # Add more scopes as needed
]
```

### Custom Redirect URI

**Using Environment Variable (Recommended for Production):**

Set the `OAUTH_REDIRECT_URI` environment variable:

```bash
# Linux/Mac
export OAUTH_REDIRECT_URI='https://yourdomain.com/api/auth/callback'

# Windows (Command Prompt)
set OAUTH_REDIRECT_URI=https://yourdomain.com/api/auth/callback

# Windows (PowerShell)
$env:OAUTH_REDIRECT_URI='https://yourdomain.com/api/auth/callback'

# Docker
docker run -e OAUTH_REDIRECT_URI='https://yourdomain.com/api/auth/callback' ...

# Docker Compose
environment:
  - OAUTH_REDIRECT_URI=https://yourdomain.com/api/auth/callback
```

**Modifying config.py (Alternative):**

Override the default redirect URI directly in code:

```python
# In config.py
OAUTH_REDIRECT_URI = 'http://localhost:8080/api/auth/callback'
```

**Important:** Remember to update Google Cloud Console with the new URI in both cases.

## FAQ

**Q: How long do tokens last?**
A: Access tokens expire after 1 hour. Refresh tokens can last indefinitely but may be revoked after 6 months of inactivity.

**Q: Do I need to re-authenticate every time I start the application?**
A: No. Tokens are saved to `token.json` and reused across sessions. You only need to re-authenticate if tokens are revoked or deleted.

**Q: Can multiple users use the same application instance?**
A: The current implementation uses a single set of tokens. For multi-user support, you would need to implement per-user token storage.

**Q: What happens if I revoke access in my Google Account?**
A: The application will detect invalid tokens and prompt for re-authentication.

**Q: Can I use this with a Google Workspace account?**
A: Yes, but your workspace administrator must allow the application. You may need to request approval.

**Q: How do I reset authentication completely?**
A: Delete `token.json`, restart the application, and complete the OAuth flow again.

**Q: Is my data secure?**
A: The application only requests read-only access to Google Docs and Sheets. Tokens are stored locally and never transmitted except to Google's OAuth servers.

## Support

If you encounter issues not covered in this guide:

1. Check application logs for detailed error messages
2. Verify your Google Cloud Console configuration
3. Ensure all required APIs are enabled
4. Try deleting `token.json` and re-authenticating
5. Check that `credentials.json` is valid and in the correct location

For additional help, refer to:
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
- Project README.md for general setup instructions
