# Implementation Plan: Web Authentication Fix

## Overview

This implementation plan converts the CLI-oriented OAuth authentication system into a dual-mode system that supports both CLI and web-based authentication. The plan focuses on adding web-compatible OAuth flows, proactive token refresh, background monitoring, and comprehensive error handling while maintaining backward compatibility with existing CLI functionality.

## Tasks

- [x] 1. Enhance GoogleDocsAuthenticator for dual-mode support
  - [x] 1.1 Add mode detection and dual-mode initialization
    - Add `mode` parameter to `__init__` (values: 'auto', 'web', 'cli')
    - Implement `detect_mode()` method using Flask context detection
    - Update `authenticate()` to route to appropriate flow based on mode
    - _Requirements: 1.1, 8.1, 8.2, 8.3_
  
  - [ ]* 1.2 Write property test for mode detection
    - **Property 14: Mode Detection Consistency**
    - **Validates: Requirements 8.1, 8.2, 8.3**
  
  - [x] 1.3 Implement web-based OAuth flow methods
    - Add `get_authorization_url()` method to generate OAuth URL with state token
    - Add `exchange_code_for_tokens()` method to exchange authorization code
    - Implement state token generation and validation
    - _Requirements: 1.2, 1.3, 1.4, 6.2, 6.3_
  
  - [ ]* 1.4 Write property tests for web OAuth flow
    - **Property 2: Authorization URL Generation**
    - **Property 3: Token Persistence After Exchange**
    - **Property 11: CSRF State Validation**
    - **Property 12: Authorization Code Exchange**
    - **Validates: Requirements 1.2, 1.4, 6.2, 6.3**
  
  - [x] 1.5 Implement token refresh and expiration checking
    - Add `refresh_tokens()` method with error handling
    - Add `is_token_expiring_soon()` method with configurable threshold
    - Add `get_token_status()` method returning comprehensive status
    - Update token refresh to handle invalid refresh tokens gracefully
    - _Requirements: 2.2, 2.3, 2.4_
  
  - [ ]* 1.6 Write property tests for token refresh
    - **Property 5: Proactive Token Refresh**
    - **Property 6: Refresh Failure Handling**
    - **Validates: Requirements 2.2, 2.4**

- [x] 2. Create authentication status API endpoint
  - [x] 2.1 Implement GET /api/auth/status endpoint
    - Create endpoint in `cantonese_anki_generator/web/api.py`
    - Return JSON with authentication status, token validity, expiration info
    - Include authorization URL when authentication needed
    - Handle missing credentials gracefully
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ]* 2.2 Write property test for status responses
    - **Property 7: Status Response Completeness**
    - **Validates: Requirements 3.2, 3.3, 3.4**
  
  - [ ]* 2.3 Write unit tests for status endpoint
    - Test with valid tokens
    - Test with expired tokens
    - Test with missing tokens
    - Test with missing credentials file
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Create OAuth callback endpoint
  - [x] 3.1 Implement GET /api/auth/callback endpoint
    - Create endpoint in `cantonese_anki_generator/web/api.py`
    - Accept `code`, `state`, and `error` query parameters
    - Validate state token for CSRF protection
    - Exchange authorization code for tokens
    - Return success/error response with appropriate messages
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 3.2 Write unit tests for callback endpoint
    - Test successful authorization code exchange
    - Test CSRF validation with invalid state
    - Test error parameter handling
    - Test missing code parameter
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 4. Implement background token monitoring
  - [x] 4.1 Create TokenMonitor class
    - Create new file `cantonese_anki_generator/web/token_monitor.py`
    - Implement `TokenMonitor` class with APScheduler integration
    - Add `start()`, `stop()`, and `check_and_refresh()` methods
    - Configure scheduler to run every 6 hours
    - Implement token expiration checking and automatic refresh
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ]* 4.2 Write property test for background refresh trigger
    - **Property 13: Background Refresh Trigger**
    - **Validates: Requirements 7.3**
  
  - [ ]* 4.3 Write unit tests for TokenMonitor
    - Test scheduler initialization
    - Test check_and_refresh with expiring tokens
    - Test check_and_refresh with valid tokens
    - Test error handling when refresh fails
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate authentication into Flask app startup
  - [x] 6.1 Update Flask app initialization
    - Modify `cantonese_anki_generator/web/app.py`
    - Initialize GoogleDocsAuthenticator in web mode on startup
    - Validate existing tokens and log status
    - Start TokenMonitor background task
    - Handle missing credentials gracefully (allow app to start)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 7.1_
  
  - [ ]* 6.2 Write unit tests for app startup authentication
    - Test startup with valid tokens
    - Test startup with expired tokens (should trigger refresh)
    - Test startup with missing tokens (should log warning)
    - Test startup without credentials file (should start successfully)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Update existing API endpoints for authentication validation
  - [x] 7.1 Enhance validate_google_url function
    - Update `validate_google_url()` in `cantonese_anki_generator/web/api.py`
    - Return authentication-specific error codes
    - Include authorization URL in authentication errors
    - Improve error messages with step-by-step instructions
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 7.2 Update /api/process endpoint
    - Add authentication check before processing
    - Return authentication required error if tokens invalid
    - Preserve uploaded files when authentication fails
    - Include authorization URL in error response
    - _Requirements: 4.4, 4.5_
  
  - [ ]* 7.3 Write property tests for authentication error handling
    - **Property 8: Authentication Error Responses**
    - **Property 9: Unauthenticated Request Rejection**
    - **Property 10: File Preservation on Auth Failure**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

- [x] 8. Add data models for authentication
  - [x] 8.1 Create authentication data models
    - Create new file `cantonese_anki_generator/web/auth_models.py`
    - Implement `TokenStatus` dataclass
    - Implement `OAuthState` dataclass
    - Implement `AuthMode` enum
    - _Requirements: All (supporting infrastructure)_
  
  - [ ]* 8.2 Write unit tests for data models
    - Test TokenStatus creation and validation
    - Test OAuthState expiration checking
    - Test AuthMode enum values
    - _Requirements: All (supporting infrastructure)_

- [x] 9. Update configuration for web authentication
  - [x] 9.1 Add web authentication configuration
    - Update `cantonese_anki_generator/config.py`
    - Add OAuth redirect URI configuration
    - Add token refresh threshold configuration (24 hours)
    - Add background monitor interval configuration (6 hours)
    - Add state token expiration configuration (10 minutes)
    - _Requirements: All (supporting infrastructure)_

- [x] 10. Ensure backward compatibility with CLI mode
  - [x] 10.1 Verify CLI mode still works
    - Test that CLI applications can still authenticate
    - Verify `run_local_server` is used in CLI mode
    - Test that CLI and web modes share token files
    - _Requirements: 1.5, 8.2, 8.4, 8.5_
  
  - [ ]* 10.2 Write property tests for cross-mode compatibility
    - **Property 4: CLI Mode Backward Compatibility**
    - **Property 15: Cross-Mode Token Reuse**
    - **Validates: Requirements 1.5, 8.2, 8.5**
  
  - [ ]* 10.3 Write integration tests for mode switching
    - Test authenticating in CLI mode, then using in web mode
    - Test authenticating in web mode, then using in CLI mode
    - Test that token files are shared correctly
    - _Requirements: 8.4, 8.5_

- [x] 11. Add comprehensive error handling
  - [x] 11.1 Implement error response formatting
    - Create consistent error response format across all endpoints
    - Include error codes, messages, and action_required fields
    - Add authorization URLs to authentication errors
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [ ]* 11.2 Write unit tests for error scenarios
    - Test missing credentials file error
    - Test expired token error
    - Test invalid refresh token error
    - Test CSRF validation error
    - Test network error handling
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 12. Add APScheduler dependency
  - [x] 12.1 Update requirements.txt
    - Add `APScheduler>=3.10.0` to requirements.txt
    - Document the dependency purpose in comments
    - _Requirements: 7.1, 7.2_

- [x] 13. Final checkpoint - Comprehensive testing
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Update documentation
  - [x] 14.1 Add authentication setup documentation
    - Document web authentication flow for users
    - Add troubleshooting guide for common authentication issues
    - Document OAuth callback URL configuration in Google Cloud Console
    - Add examples of authentication status responses
    - _Requirements: All (documentation)_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases
- Background monitoring uses APScheduler's BackgroundScheduler for non-blocking operation
- All authentication errors follow consistent response format
- Mode detection is automatic but can be overridden for testing
- Token files are shared between CLI and web modes for seamless switching
