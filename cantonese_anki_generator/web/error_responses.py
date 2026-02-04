"""Centralized error response formatting for web API endpoints.

This module provides consistent error response formatting across all API endpoints,
including error codes, messages, and action_required fields.

Requirements: 4.1, 4.2, 4.3
"""

from typing import Dict, Any, Optional, Tuple
from flask import jsonify
import logging

logger = logging.getLogger(__name__)


class ErrorCode:
    """Standard error codes for API responses."""
    
    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_INIT_ERROR = "AUTH_INIT_ERROR"
    AUTH_URL_ERROR = "AUTH_URL_ERROR"
    AUTH_CHECK_ERROR = "AUTH_CHECK_ERROR"
    MISSING_CREDENTIALS = "MISSING_CREDENTIALS"
    INVALID_STATE = "INVALID_STATE"
    STATE_EXPIRED = "STATE_EXPIRED"
    STATE_VALIDATION_ERROR = "STATE_VALIDATION_ERROR"
    TOKEN_EXCHANGE_FAILED = "TOKEN_EXCHANGE_FAILED"
    TOKEN_EXCHANGE_ERROR = "TOKEN_EXCHANGE_ERROR"
    OAUTH_ERROR = "OAUTH_ERROR"
    MISSING_CODE = "MISSING_CODE"
    MISSING_STATE = "MISSING_STATE"
    CALLBACK_ERROR = "CALLBACK_ERROR"
    STATUS_CHECK_ERROR = "STATUS_CHECK_ERROR"
    
    # File and upload errors
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_URL = "INVALID_URL"
    MISSING_AUDIO = "MISSING_AUDIO"
    INVALID_AUDIO = "INVALID_AUDIO"
    SAVE_FAILED = "SAVE_FAILED"
    UPLOAD_ERROR = "UPLOAD_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    
    # Session errors
    INVALID_SESSION_ID = "INVALID_SESSION_ID"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_RETRIEVAL_ERROR = "SESSION_RETRIEVAL_ERROR"
    SESSION_CREATION_FAILED = "SESSION_CREATION_FAILED"
    
    # Processing errors
    PROCESSING_VALIDATION_ERROR = "PROCESSING_VALIDATION_ERROR"
    PROCESSING_FILE_NOT_FOUND = "PROCESSING_FILE_NOT_FOUND"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    GOOGLE_API_ERROR = "GOOGLE_API_ERROR"
    
    # Data validation errors
    INVALID_JSON = "INVALID_JSON"
    MISSING_DATA = "MISSING_DATA"
    MISSING_FIELDS = "MISSING_FIELDS"
    
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class ActionRequired:
    """Standard action_required values for error responses."""
    
    AUTHENTICATION = "authentication"
    RE_AUTHENTICATION = "re_authentication"
    UPLOAD_FILES = "upload_files"
    CHECK_PERMISSIONS = "check_permissions"
    RETRY = "retry"
    CONTACT_SUPPORT = "contact_support"
    CONFIGURE_CREDENTIALS = "configure_credentials"


def format_error_response(
    error_message: str,
    error_code: str,
    action_required: Optional[str] = None,
    authorization_url: Optional[str] = None,
    files_preserved: bool = False,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format a consistent error response for API endpoints.
    
    Args:
        error_message: Human-readable error message
        error_code: Machine-readable error code (use ErrorCode constants)
        action_required: Specific user action needed (use ActionRequired constants)
        authorization_url: OAuth URL for authentication (if applicable)
        files_preserved: Whether uploaded files were preserved after error
        additional_data: Additional data to include in response
        
    Returns:
        Dictionary formatted for JSON response
        
    Example:
        >>> format_error_response(
        ...     "Authentication required",
        ...     ErrorCode.AUTH_REQUIRED,
        ...     action_required=ActionRequired.AUTHENTICATION,
        ...     authorization_url="https://accounts.google.com/..."
        ... )
        {
            'success': False,
            'error': 'Authentication required',
            'error_code': 'AUTH_REQUIRED',
            'action_required': 'authentication',
            'authorization_url': 'https://accounts.google.com/...'
        }
    """
    response = {
        'success': False,
        'error': error_message,
        'error_code': error_code
    }
    
    if action_required:
        response['action_required'] = action_required
    
    if authorization_url:
        response['authorization_url'] = authorization_url
    
    if files_preserved:
        response['files_preserved'] = files_preserved
    
    if additional_data:
        response.update(additional_data)
    
    return response


def authentication_required_response(
    message: Optional[str] = None,
    authorization_url: Optional[str] = None,
    files_preserved: bool = False
) -> Tuple[Any, int]:
    """
    Create a standardized authentication required error response.
    
    Args:
        message: Custom error message (uses default if None)
        authorization_url: OAuth URL for authentication
        files_preserved: Whether uploaded files were preserved
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if not message:
        message = (
            "Authentication required to access Google Docs/Sheets. "
            "Please follow these steps:\n"
            "1. Click the authorization link provided\n"
            "2. Sign in with your Google account\n"
            "3. Grant the requested permissions\n"
            "4. You will be redirected back automatically"
        )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.AUTH_REQUIRED,
        action_required=ActionRequired.AUTHENTICATION,
        authorization_url=authorization_url,
        files_preserved=files_preserved
    )
    
    return jsonify(response), 401


def authentication_expired_response(
    authorization_url: Optional[str] = None,
    files_preserved: bool = False
) -> Tuple[Any, int]:
    """
    Create a standardized authentication expired error response.
    
    Args:
        authorization_url: OAuth URL for re-authentication
        files_preserved: Whether uploaded files were preserved
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = (
        "Authentication expired. Your session has timed out. "
        "Please re-authenticate by clicking the authorization link."
    )
    
    if files_preserved:
        message += " Your uploaded files have been preserved."
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.AUTH_EXPIRED,
        action_required=ActionRequired.RE_AUTHENTICATION,
        authorization_url=authorization_url,
        files_preserved=files_preserved
    )
    
    return jsonify(response), 401


def missing_credentials_response() -> Tuple[Any, int]:
    """
    Create a standardized missing credentials error response.
    
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = (
        "Credentials not configured. Please add credentials.json file. "
        "Follow these steps:\n"
        "1. Go to Google Cloud Console\n"
        "2. Create OAuth 2.0 credentials\n"
        "3. Download credentials.json\n"
        "4. Place it in the project root directory"
    )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.MISSING_CREDENTIALS,
        action_required=ActionRequired.CONFIGURE_CREDENTIALS
    )
    
    return jsonify(response), 500


def invalid_state_response(expired: bool = False) -> Tuple[Any, int]:
    """
    Create a standardized invalid/expired state token error response.
    
    Args:
        expired: Whether the state token expired (vs being invalid)
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if expired:
        message = (
            "Authentication session expired (10 minute limit). "
            "Please start the authentication process again."
        )
        error_code = ErrorCode.STATE_EXPIRED
    else:
        message = (
            "Invalid or expired state token. "
            "This may indicate a security issue. "
            "Please start the authentication process again."
        )
        error_code = ErrorCode.INVALID_STATE
    
    response = format_error_response(
        error_message=message,
        error_code=error_code,
        action_required=ActionRequired.AUTHENTICATION
    )
    
    return jsonify(response), 400


def token_exchange_failed_response(
    reason: Optional[str] = None
) -> Tuple[Any, int]:
    """
    Create a standardized token exchange failure error response.
    
    Args:
        reason: Specific reason for failure (optional)
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = "Failed to exchange authorization code for tokens. "
    
    if reason:
        message += f"{reason}. "
    
    message += "Please try again or check your Google account permissions."
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.TOKEN_EXCHANGE_FAILED,
        action_required=ActionRequired.RETRY
    )
    
    return jsonify(response), 500


def file_too_large_response(max_size_mb: int = 500) -> Tuple[Any, int]:
    """
    Create a standardized file too large error response.
    
    Args:
        max_size_mb: Maximum file size in MB
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = (
        f"File too large. Maximum upload size is {max_size_mb}MB. "
        "Please compress your audio file and try again."
    )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.FILE_TOO_LARGE,
        action_required=ActionRequired.UPLOAD_FILES
    )
    
    return jsonify(response), 413


def invalid_url_response(
    authorization_url: Optional[str] = None
) -> Tuple[Any, int]:
    """
    Create a standardized invalid URL error response.
    
    Args:
        authorization_url: OAuth URL if authentication is needed
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if authorization_url:
        # URL validation failed due to authentication
        return authentication_required_response(
            authorization_url=authorization_url
        )
    
    message = (
        "Invalid URL format. Please provide a valid Google Docs or Google Sheets URL "
        "(e.g., https://docs.google.com/document/d/... or "
        "https://docs.google.com/spreadsheets/d/...)"
    )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.INVALID_URL,
        action_required=ActionRequired.UPLOAD_FILES
    )
    
    return jsonify(response), 400


def session_not_found_response(session_id: str) -> Tuple[Any, int]:
    """
    Create a standardized session not found error response.
    
    Args:
        session_id: The session ID that was not found
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = (
        f"Session not found: {session_id}. "
        "It may have expired or been deleted. "
        "Please upload your files again to create a new session."
    )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.SESSION_NOT_FOUND,
        action_required=ActionRequired.UPLOAD_FILES
    )
    
    return jsonify(response), 404


def processing_error_response(
    error_details: str,
    files_preserved: bool = True
) -> Tuple[Any, int]:
    """
    Create a standardized processing error response.
    
    Args:
        error_details: Details about the processing error
        files_preserved: Whether uploaded files were preserved
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    message = f"Processing failed: {error_details}. "
    
    if files_preserved:
        message += "Your uploaded files have been preserved. "
    
    message += "Please check your document format and audio file, then try again."
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.PROCESSING_ERROR,
        action_required=ActionRequired.RETRY,
        files_preserved=files_preserved
    )
    
    return jsonify(response), 500


def unexpected_error_response(
    error_details: Optional[str] = None,
    include_details: bool = False
) -> Tuple[Any, int]:
    """
    Create a standardized unexpected error response.
    
    Args:
        error_details: Details about the error (for logging)
        include_details: Whether to include error details in response (dev mode)
        
    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if include_details and error_details:
        message = f"An unexpected error occurred: {error_details}"
    else:
        message = (
            "An unexpected error occurred. "
            "Please try again or contact support if the problem persists."
        )
    
    response = format_error_response(
        error_message=message,
        error_code=ErrorCode.UNEXPECTED_ERROR,
        action_required=ActionRequired.CONTACT_SUPPORT
    )
    
    return jsonify(response), 500
