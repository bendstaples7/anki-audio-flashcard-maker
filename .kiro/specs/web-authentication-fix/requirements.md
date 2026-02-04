# Requirements Document: Web Authentication Fix

## Introduction

The Cantonese Anki Generator web application currently fails when OAuth tokens expire because the authentication system was designed for CLI usage. The system uses `flow.run_local_server(port=0)` which attempts to start a local server for OAuth callback, but this conflicts with the already-running Flask web server. This requirement addresses the need for a web-compatible authentication flow that handles token expiration gracefully without requiring CLI intervention.

## Glossary

- **OAuth_Token**: A time-limited credential that grants access to Google APIs, typically expires after 7 days
- **Refresh_Token**: A long-lived credential used to obtain new OAuth tokens without user interaction
- **Authentication_Flow**: The process of obtaining user authorization to access Google APIs
- **Web_Application**: The Flask-based web server that provides the manual audio alignment interface
- **CLI_Application**: The command-line interface version of the Cantonese Anki Generator
- **Google_API_Client**: The service object used to make requests to Google Docs and Sheets APIs
- **Token_File**: The JSON file (token.json) that stores OAuth credentials locally
- **Credentials_File**: The JSON file (credentials.json) containing OAuth client configuration from Google Cloud Console

## Requirements

### Requirement 1: Web-Compatible OAuth Flow

**User Story:** As a web application user, I want the authentication system to work within the web interface, so that I don't need to use the command line when tokens expire.

#### Acceptance Criteria

1. WHEN the authentication system needs user authorization, THE Web_Application SHALL provide a web-based OAuth flow instead of attempting to start a local server
2. WHEN a user initiates web-based authentication, THE Web_Application SHALL generate an authorization URL and display it to the user
3. WHEN a user completes OAuth authorization, THE Web_Application SHALL receive the authorization code through a web callback endpoint
4. WHEN the authorization code is received, THE Web_Application SHALL exchange it for OAuth tokens and store them in the Token_File
5. WHERE the application is running in CLI mode, THE Authentication_Flow SHALL continue to use the local server method for backward compatibility

### Requirement 2: Proactive Token Refresh

**User Story:** As a system administrator, I want tokens to be refreshed automatically before they expire, so that users experience minimal authentication interruptions.

#### Acceptance Criteria

1. WHEN the Web_Application starts, THE Web_Application SHALL check if OAuth_Token exists and validate its expiration status
2. WHEN an OAuth_Token is within 24 hours of expiration, THE Web_Application SHALL attempt to refresh it using the Refresh_Token
3. WHEN a token refresh succeeds, THE Web_Application SHALL save the new OAuth_Token to the Token_File
4. WHEN a token refresh fails due to an invalid Refresh_Token, THE Web_Application SHALL mark authentication as requiring user intervention
5. WHILE the Web_Application is running, THE Web_Application SHALL periodically check token expiration status every 6 hours

### Requirement 3: Authentication Status Monitoring

**User Story:** As a web application user, I want to know the current authentication status, so that I can take action if re-authentication is needed.

#### Acceptance Criteria

1. THE Web_Application SHALL provide an API endpoint that returns the current authentication status
2. WHEN authentication status is requested, THE Web_Application SHALL return whether tokens are valid, expired, or missing
3. WHEN tokens are expired or missing, THE Web_Application SHALL include the authorization URL in the status response
4. WHEN tokens are valid, THE Web_Application SHALL include the expiration timestamp in the status response
5. THE Web_Application SHALL expose authentication status to the frontend interface for display to users

### Requirement 4: Graceful Authentication Failure Handling

**User Story:** As a web application user, I want clear guidance when authentication fails, so that I know exactly what steps to take to resolve the issue.

#### Acceptance Criteria

1. WHEN a Google API request fails due to authentication, THE Web_Application SHALL return a specific error code indicating authentication failure
2. WHEN authentication is required, THE Web_Application SHALL provide a user-friendly error message with step-by-step instructions
3. WHEN displaying authentication errors, THE Web_Application SHALL include the authorization URL for re-authentication
4. WHEN a user attempts to process files without valid authentication, THE Web_Application SHALL prevent the operation and display authentication instructions
5. IF authentication fails during file processing, THEN THE Web_Application SHALL preserve the uploaded files and allow retry after re-authentication

### Requirement 5: Startup Authentication Validation

**User Story:** As a system administrator, I want the application to validate authentication on startup, so that authentication issues are detected early before users attempt operations.

#### Acceptance Criteria

1. WHEN the Web_Application starts, THE Web_Application SHALL attempt to load and validate existing OAuth tokens
2. WHEN tokens are missing on startup, THE Web_Application SHALL log a warning and generate an authorization URL
3. WHEN tokens are expired on startup, THE Web_Application SHALL attempt automatic refresh using the Refresh_Token
4. WHEN startup authentication validation completes, THE Web_Application SHALL log the authentication status
5. THE Web_Application SHALL continue to start successfully even when authentication is not configured, allowing users to authenticate through the web interface

### Requirement 6: OAuth Callback Endpoint

**User Story:** As a web application user, I want to complete OAuth authorization through my browser, so that I can authenticate without leaving the web interface.

#### Acceptance Criteria

1. THE Web_Application SHALL provide a dedicated callback endpoint for OAuth authorization responses
2. WHEN the callback endpoint receives an authorization code, THE Web_Application SHALL validate the state parameter to prevent CSRF attacks
3. WHEN the authorization code is valid, THE Web_Application SHALL exchange it for OAuth tokens
4. WHEN token exchange succeeds, THE Web_Application SHALL display a success message to the user
5. WHEN token exchange fails, THE Web_Application SHALL display an error message with troubleshooting guidance

### Requirement 7: Background Token Monitoring

**User Story:** As a system administrator, I want the application to monitor token health in the background, so that expiration issues are detected and resolved proactively.

#### Acceptance Criteria

1. WHEN the Web_Application starts, THE Web_Application SHALL initialize a background task for token monitoring
2. WHILE the Web_Application is running, THE Background_Task SHALL check token expiration every 6 hours
3. WHEN the Background_Task detects tokens expiring within 24 hours, THE Background_Task SHALL attempt automatic refresh
4. WHEN automatic refresh fails, THE Background_Task SHALL log a warning and update the authentication status
5. THE Background_Task SHALL not block or interfere with normal Web_Application operations

### Requirement 8: Dual-Mode Authentication Support

**User Story:** As a developer, I want the authentication system to support both CLI and web modes, so that existing CLI functionality remains intact while adding web support.

#### Acceptance Criteria

1. THE Authentication_System SHALL detect whether it is running in CLI mode or web mode
2. WHEN running in CLI mode, THE Authentication_System SHALL use the local server OAuth flow
3. WHEN running in web mode, THE Authentication_System SHALL use the web-based OAuth flow
4. THE Authentication_System SHALL share the same Token_File and Credentials_File between both modes
5. WHEN switching between modes, THE Authentication_System SHALL recognize and use existing valid tokens without requiring re-authentication
