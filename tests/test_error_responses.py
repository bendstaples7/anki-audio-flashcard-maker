"""Tests for centralized error response formatting.

This module tests the error response formatting functions to ensure
consistent error handling across all API endpoints.
"""

import pytest
from flask import Flask, jsonify
from cantonese_anki_generator.web.error_responses import (
    format_error_response,
    authentication_required_response,
    authentication_expired_response,
    missing_credentials_response,
    invalid_state_response,
    token_exchange_failed_response,
    file_too_large_response,
    invalid_url_response,
    session_not_found_response,
    processing_error_response,
    unexpected_error_response,
    ErrorCode,
    ActionRequired
)


class TestErrorResponseFormatting:
    """Test error response formatting functions."""
    
    def test_format_error_response_basic(self):
        """Test basic error response formatting."""
        response = format_error_response(
            error_message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR
        )
        
        assert response['success'] is False
        assert response['error'] == "Test error"
        assert response['error_code'] == ErrorCode.INTERNAL_ERROR
        assert 'action_required' not in response
        assert 'authorization_url' not in response
    
    def test_format_error_response_with_action(self):
        """Test error response with action_required field."""
        response = format_error_response(
            error_message="Auth required",
            error_code=ErrorCode.AUTH_REQUIRED,
            action_required=ActionRequired.AUTHENTICATION
        )
        
        assert response['success'] is False
        assert response['error'] == "Auth required"
        assert response['error_code'] == ErrorCode.AUTH_REQUIRED
        assert response['action_required'] == ActionRequired.AUTHENTICATION
    
    def test_format_error_response_with_auth_url(self):
        """Test error response with authorization URL."""
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?..."
        response = format_error_response(
            error_message="Auth required",
            error_code=ErrorCode.AUTH_REQUIRED,
            authorization_url=auth_url
        )
        
        assert response['success'] is False
        assert response['authorization_url'] == auth_url
    
    def test_format_error_response_with_files_preserved(self):
        """Test error response with files_preserved flag."""
        response = format_error_response(
            error_message="Processing failed",
            error_code=ErrorCode.PROCESSING_ERROR,
            files_preserved=True
        )
        
        assert response['success'] is False
        assert response['files_preserved'] is True
    
    def test_format_error_response_with_additional_data(self):
        """Test error response with additional data."""
        response = format_error_response(
            error_message="Invalid field",
            error_code=ErrorCode.INVALID_JSON,
            additional_data={'field': 'url', 'value': 'invalid'}
        )
        
        assert response['success'] is False
        assert response['field'] == 'url'
        assert response['value'] == 'invalid'


class TestAuthenticationErrorResponses:
    """Test authentication-specific error responses."""
    
    def setup_method(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    def test_authentication_required_response(self):
        """Test authentication required response."""
        with self.app.app_context():
            response, status_code = authentication_required_response(
                authorization_url="https://test.com/auth"
            )
            
            data = response.get_json()
            assert status_code == 401
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.AUTH_REQUIRED
            assert data['action_required'] == ActionRequired.AUTHENTICATION
            assert data['authorization_url'] == "https://test.com/auth"
    
    def test_authentication_required_with_custom_message(self):
        """Test authentication required with custom message."""
        with self.app.app_context():
            custom_msg = "Custom auth message"
            response, _ = authentication_required_response(
                message=custom_msg,
                authorization_url="https://test.com/auth"
            )
            
            data = response.get_json()
            assert data['error'] == custom_msg
    
    def test_authentication_expired_response(self):
        """Test authentication expired response."""
        with self.app.app_context():
            response, status_code = authentication_expired_response(
                authorization_url="https://test.com/auth",
                files_preserved=True
            )
            
            data = response.get_json()
            assert status_code == 401
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.AUTH_EXPIRED
            assert data['action_required'] == ActionRequired.RE_AUTHENTICATION
            assert data['files_preserved'] is True
    
    def test_missing_credentials_response(self):
        """Test missing credentials response."""
        with self.app.app_context():
            response, status_code = missing_credentials_response()
            
            data = response.get_json()
            assert status_code == 500
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.MISSING_CREDENTIALS
            assert data['action_required'] == ActionRequired.CONFIGURE_CREDENTIALS
    
    def test_invalid_state_response_not_expired(self):
        """Test invalid state token response."""
        with self.app.app_context():
            response, status_code = invalid_state_response(expired=False)
            
            data = response.get_json()
            assert status_code == 400
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.INVALID_STATE
    
    def test_invalid_state_response_expired(self):
        """Test expired state token response."""
        with self.app.app_context():
            response, status_code = invalid_state_response(expired=True)
            
            data = response.get_json()
            assert status_code == 400
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.STATE_EXPIRED
    
    def test_token_exchange_failed_response(self):
        """Test token exchange failure response."""
        with self.app.app_context():
            response, status_code = token_exchange_failed_response(
                reason="Invalid code"
            )
            
            data = response.get_json()
            assert status_code == 500
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.TOKEN_EXCHANGE_FAILED
            assert "Invalid code" in data['error']


class TestFileErrorResponses:
    """Test file-related error responses."""
    
    def setup_method(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    def test_file_too_large_response(self):
        """Test file too large response."""
        with self.app.app_context():
            response, status_code = file_too_large_response(max_size_mb=500)
            
            data = response.get_json()
            assert status_code == 413
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.FILE_TOO_LARGE
            assert "500MB" in data['error']
    
    def test_invalid_url_response_without_auth(self):
        """Test invalid URL response without authentication."""
        with self.app.app_context():
            response, status_code = invalid_url_response()
            
            data = response.get_json()
            assert status_code == 400
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.INVALID_URL
    
    def test_invalid_url_response_with_auth(self):
        """Test invalid URL response with authentication needed."""
        with self.app.app_context():
            response, status_code = invalid_url_response(
                authorization_url="https://test.com/auth"
            )
            
            data = response.get_json()
            assert status_code == 401
            assert data['error_code'] == ErrorCode.AUTH_REQUIRED


class TestSessionErrorResponses:
    """Test session-related error responses."""
    
    def setup_method(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    def test_session_not_found_response(self):
        """Test session not found response."""
        with self.app.app_context():
            response, status_code = session_not_found_response("test-session-123")
            
            data = response.get_json()
            assert status_code == 404
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.SESSION_NOT_FOUND
            assert "test-session-123" in data['error']


class TestProcessingErrorResponses:
    """Test processing-related error responses."""
    
    def setup_method(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    def test_processing_error_response(self):
        """Test processing error response."""
        with self.app.app_context():
            response, status_code = processing_error_response(
                error_details="Invalid format",
                files_preserved=True
            )
            
            data = response.get_json()
            assert status_code == 500
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.PROCESSING_ERROR
            assert data['files_preserved'] is True
            assert "Invalid format" in data['error']
    
    def test_unexpected_error_response_without_details(self):
        """Test unexpected error response without details."""
        with self.app.app_context():
            response, status_code = unexpected_error_response(
                error_details="Internal error",
                include_details=False
            )
            
            data = response.get_json()
            assert status_code == 500
            assert data['success'] is False
            assert data['error_code'] == ErrorCode.UNEXPECTED_ERROR
            assert "Internal error" not in data['error']
    
    def test_unexpected_error_response_with_details(self):
        """Test unexpected error response with details (dev mode)."""
        with self.app.app_context():
            response, status_code = unexpected_error_response(
                error_details="Internal error",
                include_details=True
            )
            
            data = response.get_json()
            assert status_code == 500
            assert data['success'] is False
            assert "Internal error" in data['error']


class TestErrorCodeConstants:
    """Test error code constants are defined."""
    
    def test_error_codes_exist(self):
        """Test that all expected error codes are defined."""
        # Authentication errors
        assert hasattr(ErrorCode, 'AUTH_REQUIRED')
        assert hasattr(ErrorCode, 'AUTH_EXPIRED')
        assert hasattr(ErrorCode, 'MISSING_CREDENTIALS')
        assert hasattr(ErrorCode, 'INVALID_STATE')
        assert hasattr(ErrorCode, 'TOKEN_EXCHANGE_FAILED')
        
        # File errors
        assert hasattr(ErrorCode, 'FILE_TOO_LARGE')
        assert hasattr(ErrorCode, 'INVALID_URL')
        assert hasattr(ErrorCode, 'MISSING_AUDIO')
        
        # Session errors
        assert hasattr(ErrorCode, 'SESSION_NOT_FOUND')
        assert hasattr(ErrorCode, 'SESSION_RETRIEVAL_ERROR')
        
        # Processing errors
        assert hasattr(ErrorCode, 'PROCESSING_ERROR')
        assert hasattr(ErrorCode, 'GOOGLE_API_ERROR')
        
        # General errors
        assert hasattr(ErrorCode, 'INTERNAL_ERROR')
        assert hasattr(ErrorCode, 'UNEXPECTED_ERROR')
    
    def test_action_required_constants_exist(self):
        """Test that all expected action_required values are defined."""
        assert hasattr(ActionRequired, 'AUTHENTICATION')
        assert hasattr(ActionRequired, 'RE_AUTHENTICATION')
        assert hasattr(ActionRequired, 'UPLOAD_FILES')
        assert hasattr(ActionRequired, 'CHECK_PERMISSIONS')
        assert hasattr(ActionRequired, 'RETRY')
        assert hasattr(ActionRequired, 'CONTACT_SUPPORT')
        assert hasattr(ActionRequired, 'CONFIGURE_CREDENTIALS')
