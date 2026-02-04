"""API endpoints for manual audio alignment."""

import os
import re
import logging
import traceback
from typing import Dict, Tuple, Optional
from pathlib import Path
from datetime import datetime
import numpy as np
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from cantonese_anki_generator.config import Config
from cantonese_anki_generator.processors.google_docs_auth import GoogleDocsAuthenticator
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

# Create logger
logger = logging.getLogger(__name__)

# Create API blueprint
bp = Blueprint('api', __name__, url_prefix='/api')

# In-memory progress tracking for generation tasks
generation_progress = {}

# In-memory progress tracking for regeneration tasks
regeneration_progress = {}


# Task 19.2: Add backend error handling
# Custom error handler for request entity too large
@bp.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    """Handle file upload size limit exceeded."""
    logger.warning(f"File upload size limit exceeded: {e}")
    return file_too_large_response()


# Custom error handler for general exceptions
@bp.errorhandler(Exception)
def handle_unexpected_error(e):
    """Handle unexpected errors with proper logging."""
    logger.error(f"Unexpected error: {e}", exc_info=True)
    
    # In development, include more details
    include_details = current_app.debug
    
    return unexpected_error_response(
        error_details=str(e),
        include_details=include_details
    )


@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'message': 'Manual Audio Alignment API is running'
    })


@bp.route('/auth/status', methods=['GET'])
def auth_status():
    """
    Get current authentication status.
    
    Returns JSON with:
        - authenticated: bool - Whether user is authenticated
        - token_valid: bool - Whether tokens are currently valid
        - expires_at: str - ISO timestamp when tokens expire (None if no tokens)
        - expires_in_hours: int - Hours until expiration (0 if expired/missing)
        - needs_reauth: bool - Whether re-authentication is required
        - authorization_url: str - OAuth URL for authentication (None if authenticated)
        
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(Config.CREDENTIALS_FILE):
            logger.warning("Credentials file not found")
            return missing_credentials_response()
        
        # Initialize authenticator in web mode
        try:
            authenticator = GoogleDocsAuthenticator(mode='web')
        except Exception as e:
            logger.error(f"Failed to initialize authenticator: {e}", exc_info=True)
            response = format_error_response(
                error_message=f'Failed to initialize authentication: {str(e)}',
                error_code=ErrorCode.AUTH_INIT_ERROR,
                action_required=ActionRequired.CONTACT_SUPPORT
            )
            return jsonify(response), 500
        
        # Get token status
        token_status = authenticator.get_token_status()
        
        # Check if tokens are valid
        if token_status['valid'] and not token_status['expired']:
            # Calculate hours until expiration
            expires_in_hours = 0
            if token_status['expires_at']:
                time_until_expiry = token_status['expires_at'] - datetime.utcnow()
                expires_in_hours = max(0, int(time_until_expiry.total_seconds() / 3600))
            
            return jsonify({
                'authenticated': True,
                'token_valid': True,
                'expires_at': token_status['expires_at'].isoformat() if token_status['expires_at'] else None,
                'expires_in_hours': expires_in_hours,
                'needs_reauth': False,
                'authorization_url': None
            }), 200
        
        # Tokens are missing, expired, or invalid - need re-authentication
        # Generate authorization URL
        try:
            authorization_url, state_token = authenticator.get_authorization_url()
            
            # Store state token in app context for later validation
            # In production, this should be stored in a more persistent way (Redis, database, etc.)
            if not hasattr(current_app, 'oauth_states'):
                current_app.oauth_states = {}
            current_app.oauth_states[state_token] = {
                'created_at': datetime.now(),
                'authenticator': authenticator
            }
            
            return jsonify({
                'authenticated': False,
                'token_valid': False,
                'expires_at': None,
                'expires_in_hours': 0,
                'needs_reauth': True,
                'authorization_url': authorization_url
            }), 200
            
        except FileNotFoundError as e:
            logger.error(f"Credentials file error: {e}")
            return missing_credentials_response()
        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {e}", exc_info=True)
            response = format_error_response(
                error_message=f'Failed to generate authorization URL: {str(e)}',
                error_code=ErrorCode.AUTH_URL_ERROR,
                action_required=ActionRequired.CONTACT_SUPPORT
            )
            return jsonify(response), 500
        
    except Exception as e:
        logger.error(f"Authentication status check failed: {e}", exc_info=True)
        response = format_error_response(
            error_message=f'Failed to check authentication status: {str(e)}',
            error_code=ErrorCode.STATUS_CHECK_ERROR,
            action_required=ActionRequired.RETRY
        )
        return jsonify(response), 500


@bp.route('/auth/callback', methods=['GET'])
def auth_callback():
    """
    OAuth callback endpoint for handling Google OAuth authorization responses.
    
    Query Parameters:
        - code: Authorization code from Google OAuth
        - state: State token for CSRF validation
        - error: Error code if authorization failed
        
    Returns:
        JSON response with success/error status and appropriate messages
        
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    try:
        # Check for error parameter (user denied authorization or other OAuth error)
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', 'Authorization failed')
            logger.warning(f"OAuth authorization error: {error} - {error_description}")
            
            response = format_error_response(
                error_message=f'Authorization failed: {error_description}',
                error_code=ErrorCode.OAUTH_ERROR,
                action_required=ActionRequired.RETRY,
                additional_data={
                    'message': 'Please try authenticating again. If the problem persists, check your Google account permissions.'
                }
            )
            return jsonify(response), 400
        
        # Get authorization code and state from query parameters
        code = request.args.get('code')
        state = request.args.get('state')
        
        # Validate required parameters
        if not code:
            logger.warning("OAuth callback missing authorization code")
            response = format_error_response(
                error_message='Missing authorization code',
                error_code=ErrorCode.MISSING_CODE,
                action_required=ActionRequired.RETRY,
                additional_data={
                    'message': 'Authorization code not received. Please try authenticating again.'
                }
            )
            return jsonify(response), 400
        
        if not state:
            logger.warning("OAuth callback missing state token")
            response = format_error_response(
                error_message='Missing state token',
                error_code=ErrorCode.MISSING_STATE,
                action_required=ActionRequired.RETRY,
                additional_data={
                    'message': 'State token not received. This may indicate a security issue. Please try authenticating again.'
                }
            )
            return jsonify(response), 400
        
        # Retrieve stored state from app context
        if not hasattr(current_app, 'oauth_states') or state not in current_app.oauth_states:
            logger.error(f"Invalid or expired state token: {state}")
            return invalid_state_response(expired=False)
        
        # Get authenticator from stored state
        state_data = current_app.oauth_states[state]
        
        # Check state expiration (10 minutes)
        created_at = state_data.get('created_at')
        if created_at:
            age = datetime.now() - created_at
            if age.total_seconds() > 600:  # 10 minutes
                logger.error(f"Expired state token: {state}")
                # Clean up expired state
                del current_app.oauth_states[state]
                return invalid_state_response(expired=True)
        
        # Initialize authenticator for token exchange
        try:
            authenticator = GoogleDocsAuthenticator(mode='web')
        except Exception as e:
            logger.error(f"Failed to initialize authenticator for token exchange: {e}", exc_info=True)
            response = format_error_response(
                error_message=f'Failed to initialize authentication: {str(e)}',
                error_code=ErrorCode.AUTH_INIT_ERROR,
                action_required=ActionRequired.RETRY,
                additional_data={
                    'message': 'An error occurred while setting up authentication. Please try again.'
                }
            )
            return jsonify(response), 500
        
        # Set the OAuth state in the authenticator for validation
        from cantonese_anki_generator.config import Config
        redirect_uri = Config.OAUTH_REDIRECT_URI
        
        authenticator._oauth_state = {
            'token': state,
            'created_at': created_at,
            'redirect_uri': redirect_uri
        }
        
        # Exchange authorization code for tokens
        try:
            success = authenticator.exchange_code_for_tokens(
                code=code,
                state=state,
                redirect_uri=redirect_uri
            )
            
            if not success:
                logger.error("Token exchange failed")
                return token_exchange_failed_response()
            
            # Clean up state token after successful exchange
            if state in current_app.oauth_states:
                del current_app.oauth_states[state]
            
            logger.info("OAuth authentication successful")
            
            # Return HTML page with auto-redirect instead of JSON
            html_response = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }
                    .container {
                        text-align: center;
                        padding: 40px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 12px;
                        backdrop-filter: blur(10px);
                    }
                    h1 { margin: 0 0 20px 0; font-size: 2em; }
                    p { margin: 10px 0; font-size: 1.1em; opacity: 0.9; }
                    .spinner {
                        border: 3px solid rgba(255, 255, 255, 0.3);
                        border-top: 3px solid white;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
                <script>
                    // Redirect after 2 seconds
                    setTimeout(function() {
                        window.location.href = '/';
                    }, 2000);
                </script>
            </head>
            <body>
                <div class="container">
                    <h1>✓ Authentication Successful!</h1>
                    <p>You can now use Google Docs and Sheets.</p>
                    <div class="spinner"></div>
                    <p>Redirecting you back to the application...</p>
                </div>
            </body>
            </html>
            """
            return html_response, 200
            
        except ValueError as e:
            # State validation error
            logger.error(f"State validation error during token exchange: {e}")
            response = format_error_response(
                error_message=str(e),
                error_code=ErrorCode.STATE_VALIDATION_ERROR,
                action_required=ActionRequired.RETRY,
                additional_data={
                    'message': 'Authentication validation failed. This may indicate a security issue. Please try authenticating again.'
                }
            )
            return jsonify(response), 400
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found during token exchange: {e}")
            return missing_credentials_response()
        except Exception as e:
            logger.error(f"Token exchange failed with unexpected error: {e}", exc_info=True)
            return token_exchange_failed_response(reason=str(e))
        
    except Exception as e:
        logger.error(f"OAuth callback failed with unexpected error: {e}", exc_info=True)
        response = format_error_response(
            error_message=f'Authentication callback failed: {str(e)}',
            error_code=ErrorCode.CALLBACK_ERROR,
            action_required=ActionRequired.RETRY,
            additional_data={
                'message': 'An unexpected error occurred. Please try authenticating again.'
            }
        )
        return jsonify(response), 500


@bp.route('/logs/stream', methods=['GET'])
def stream_logs():
    """
    Server-Sent Events endpoint for streaming processing logs.
    
    Returns:
        SSE stream of log messages
    """
    from cantonese_anki_generator.web.log_streamer import log_streamer
    import uuid
    
    client_id = str(uuid.uuid4())
    
    def generate():
        return log_streamer.generate_stream(client_id)
    
    return current_app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


def validate_google_url(url: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validate Google Docs or Sheets URL format and accessibility.
    Task 7.1: Enhanced with authentication-specific error codes and authorization URLs
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_valid, error_message, doc_type, authorization_url)
        - is_valid: True if URL is valid and accessible
        - error_message: Error message if validation fails, None otherwise
        - doc_type: 'docs' or 'sheets' if valid, None otherwise
        - authorization_url: OAuth URL for authentication if auth fails, None otherwise
        
    Requirements: 4.1, 4.2, 4.3
    """
    if not url or not isinstance(url, str):
        return False, "URL is required", None, None
    
    # Check for Google Docs URL pattern
    docs_pattern = r'https://docs\.google\.com/document/d/([a-zA-Z0-9-_]+)'
    sheets_pattern = r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)'
    
    docs_match = re.match(docs_pattern, url)
    sheets_match = re.match(sheets_pattern, url)
    
    if not docs_match and not sheets_match:
        error_msg = (
            "Invalid URL format. Please provide a valid Google Docs or Google Sheets URL "
            "(e.g., https://docs.google.com/document/d/... or "
            "https://docs.google.com/spreadsheets/d/...)"
        )
        return False, error_msg, None, None
    
    doc_type = 'docs' if docs_match else 'sheets'
    doc_id = docs_match.group(1) if docs_match else sheets_match.group(1)
    
    # Check accessibility by attempting to access the document
    try:
        # Initialize authenticator in web mode
        authenticator = GoogleDocsAuthenticator(mode='web')
        
        # Check if tokens are valid before attempting authentication
        token_status = authenticator.get_token_status()
        
        if not token_status['valid'] or token_status['expired']:
            # Tokens are invalid or expired - need authentication
            logger.warning("Authentication required: tokens are invalid or expired")
            
            # Generate authorization URL
            try:
                authorization_url, state_token = authenticator.get_authorization_url()
                
                # Store state token in app context for later validation
                if not hasattr(current_app, 'oauth_states'):
                    current_app.oauth_states = {}
                current_app.oauth_states[state_token] = {
                    'created_at': datetime.now(),
                    'authenticator': authenticator
                }
                
                error_message = (
                    "Authentication required to access Google Docs/Sheets. "
                    "Please authenticate first:\n"
                    "1. Click the authorization link provided\n"
                    "2. Sign in with your Google account\n"
                    "3. Grant the requested permissions\n"
                    "4. You will be redirected back automatically"
                )
                
                return False, error_message, None, authorization_url
                
            except Exception as e:
                logger.error(f"Failed to generate authorization URL: {e}", exc_info=True)
                error_message = (
                    "Authentication required but failed to generate authorization URL. "
                    "Please ensure credentials.json is configured correctly."
                )
                return False, error_message, None, None
        
        # Tokens are valid - attempt to authenticate
        if not authenticator.authenticate():
            logger.error("Failed to authenticate with Google API despite valid tokens")
            
            # Try to generate authorization URL for re-authentication
            try:
                authorization_url, state_token = authenticator.get_authorization_url()
                
                if not hasattr(current_app, 'oauth_states'):
                    current_app.oauth_states = {}
                current_app.oauth_states[state_token] = {
                    'created_at': datetime.now(),
                    'authenticator': authenticator
                }
                
                error_message = (
                    "Authentication failed. Your session may have expired. "
                    "Please re-authenticate by clicking the authorization link."
                )
                
                return False, error_message, None, authorization_url
                
            except Exception as e:
                logger.error(f"Failed to generate authorization URL: {e}", exc_info=True)
                error_message = "Failed to authenticate with Google API. Please ensure credentials are configured correctly."
                return False, error_message, None, None
        
        # Authentication successful - validate document access
        if doc_type == 'docs':
            service = authenticator.get_docs_service()
            # Try to get document metadata
            service.documents().get(documentId=doc_id).execute()
        else:  # sheets
            # Build sheets service
            service = build('sheets', 'v4', credentials=authenticator._credentials)
            # Try to get spreadsheet metadata
            service.spreadsheets().get(spreadsheetId=doc_id).execute()
        
        logger.info(f"Successfully validated {doc_type} URL: {doc_id}")
        return True, None, doc_type, None
        
    except HttpError as e:
        logger.warning(f"HTTP error validating URL: {e.resp.status} - {e}")
        
        # Check if error is authentication-related
        if e.resp.status == 401:
            # Unauthorized - authentication issue
            try:
                authenticator = GoogleDocsAuthenticator(mode='web')
                authorization_url, state_token = authenticator.get_authorization_url()
                
                if not hasattr(current_app, 'oauth_states'):
                    current_app.oauth_states = {}
                current_app.oauth_states[state_token] = {
                    'created_at': datetime.now(),
                    'authenticator': authenticator
                }
                
                error_message = (
                    "Authentication expired or invalid. "
                    "Please re-authenticate by clicking the authorization link."
                )
                
                return False, error_message, None, authorization_url
                
            except Exception as auth_error:
                logger.error(f"Failed to generate authorization URL: {auth_error}", exc_info=True)
                return False, "Authentication required. Please ensure credentials are configured correctly.", None, None
        
        elif e.resp.status == 404:
            return False, "Document not found. Please check the URL and ensure the document exists.", None, None
        elif e.resp.status == 403:
            return False, "Access denied. Please ensure the document is shared with your Google account or is publicly accessible.", None, None
        else:
            return False, f"Failed to access document (HTTP {e.resp.status}). Please check the URL and your permissions.", None, None
            
    except Exception as e:
        logger.error(f"Unexpected error validating URL: {e}", exc_info=True)
        return False, f"Error validating URL: {str(e)}. Please check your internet connection and try again.", None, None


def validate_audio_file(file) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded audio file format and size.
    
    Args:
        file: The uploaded file object from Flask request
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file is valid
        - error_message: Error message if validation fails, None otherwise
    """
    if not file:
        return False, "No audio file provided"
    
    if file.filename == '':
        return False, "No audio file selected"
    
    # Check file extension
    filename = file.filename.lower()
    file_ext = os.path.splitext(filename)[1]
    
    if file_ext not in Config.AUDIO_FORMATS:
        supported_formats = ', '.join(Config.AUDIO_FORMATS)
        return False, f"Unsupported audio format '{file_ext}'. Supported formats: {supported_formats}"
    
    # File size validation is handled by Flask's MAX_CONTENT_LENGTH
    # If we reach here, the file size is acceptable
    
    return True, None


@bp.route('/upload', methods=['POST'])
def upload_files():
    """
    Handle file upload and validation.
    Task 19.2: Catch and handle processing errors with appropriate HTTP status codes
    
    Expects:
        - 'url': Google Docs/Sheets URL (form field)
        - 'audio': Audio file (file upload)
        
    Returns:
        JSON response with upload status and file metadata
    """
    try:
        # Get URL from form data
        url = request.form.get('url', '').strip()
        
        # Validate URL
        url_valid, url_error, doc_type, authorization_url = validate_google_url(url)
        if not url_valid:
            logger.warning(f"URL validation failed: {url_error}")
            
            if authorization_url:
                # Authentication required
                return authentication_required_response(
                    message=url_error,
                    authorization_url=authorization_url
                )
            else:
                # Invalid URL format
                response = format_error_response(
                    error_message=url_error,
                    error_code=ErrorCode.INVALID_URL,
                    action_required=ActionRequired.UPLOAD_FILES,
                    additional_data={'field': 'url'}
                )
                return jsonify(response), 400
        
        # Get audio file from request
        if 'audio' not in request.files:
            logger.warning("No audio file provided in request")
            response = format_error_response(
                error_message='No audio file provided',
                error_code=ErrorCode.MISSING_AUDIO,
                action_required=ActionRequired.UPLOAD_FILES,
                additional_data={'field': 'audio'}
            )
            return jsonify(response), 400
        
        audio_file = request.files['audio']
        
        # Validate audio file
        audio_valid, audio_error = validate_audio_file(audio_file)
        if not audio_valid:
            logger.warning(f"Audio validation failed: {audio_error}")
            response = format_error_response(
                error_message=audio_error,
                error_code=ErrorCode.INVALID_AUDIO,
                action_required=ActionRequired.UPLOAD_FILES,
                additional_data={'field': 'audio'}
            )
            return jsonify(response), 400
        
        # Save audio file to temporary directory
        filename = secure_filename(audio_file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        
        # Handle duplicate filenames by adding a counter
        base_name, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            filename = f"{base_name}_{counter}{ext}"
            filepath = os.path.join(upload_folder, filename)
            counter += 1
        
        # Save file with error handling
        try:
            audio_file.save(filepath)
            logger.info(f"Audio file saved: {filepath}")
        except IOError as e:
            logger.error(f"Failed to save audio file: {e}", exc_info=True)
            response = format_error_response(
                error_message='Failed to save audio file. Please check disk space and try again.',
                error_code=ErrorCode.SAVE_FAILED,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 500
        
        # Get file metadata
        try:
            file_size = os.path.getsize(filepath)
        except OSError as e:
            logger.error(f"Failed to get file size: {e}")
            file_size = 0
        
        logger.info(f"Upload successful: {filename} ({file_size} bytes)")
        
        return jsonify({
            'success': True,
            'message': 'Files uploaded and validated successfully',
            'data': {
                'url': url,
                'doc_type': doc_type,
                'audio_filename': filename,
                'audio_filepath': filepath,
                'audio_size_bytes': file_size,
                'audio_size_mb': round(file_size / (1024 * 1024), 2)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Upload failed with unexpected error: {e}", exc_info=True)
        response = format_error_response(
            error_message=f'Upload failed: {str(e)}. Please try again.',
            error_code=ErrorCode.UPLOAD_ERROR,
            action_required=ActionRequired.RETRY
        )
        return jsonify(response), 500


@bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    Retrieve complete session data including all term alignments.
    Task 19.2: Return appropriate HTTP status codes and detailed error messages
    
    Args:
        session_id: The session identifier
        
    Returns:
        JSON response with session data including:
        - All term alignments with boundaries
        - Audio segment URLs for each term
        - Confidence scores and adjustment flags
        - Session metadata
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Validate session_id format
        if not session_id or not isinstance(session_id, str):
            logger.warning(f"Invalid session_id format: {session_id}")
            response = format_error_response(
                error_message='Invalid session ID format',
                error_code=ErrorCode.INVALID_SESSION_ID,
                action_required=ActionRequired.UPLOAD_FILES
            )
            return jsonify(response), 400
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Retrieve session
        try:
            session = session_manager.get_session(session_id)
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}", exc_info=True)
            response = format_error_response(
                error_message='Failed to retrieve session data. Please try again.',
                error_code=ErrorCode.SESSION_RETRIEVAL_ERROR,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 500
        
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return session_not_found_response(session_id)
        
        # Build response with all session data
        # Convert numpy types to Python native types for JSON serialization
        response_data = {
            'success': True,
            'data': {
                'session_id': session.session_id,
                'doc_url': session.doc_url,
                'audio_file_path': session.audio_file_path,
                'audio_duration': convert_numpy_types(session.audio_duration),
                'status': session.status,
                'created_at': session.created_at.isoformat(),
                'last_modified': session.last_modified.isoformat(),
                'terms': [
                    {
                        'term_id': term.term_id,
                        'english': term.english,
                        'cantonese': term.cantonese,
                        'start_time': convert_numpy_types(term.start_time),
                        'end_time': convert_numpy_types(term.end_time),
                        'original_start': convert_numpy_types(term.original_start),
                        'original_end': convert_numpy_types(term.original_end),
                        'is_manually_adjusted': term.is_manually_adjusted,
                        'confidence_score': convert_numpy_types(term.confidence_score),
                        'audio_segment_url': f'/api/audio/{session_id}/{term.term_id}'
                    }
                    for term in session.terms
                ],
                'total_terms': len(session.terms),
                'manually_adjusted_count': sum(1 for term in session.terms if term.is_manually_adjusted)
            }
        }
        
        logger.info(f"Session retrieved successfully: {session_id}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve session with unexpected error: {e}", exc_info=True)
        return unexpected_error_response(
            error_details=str(e),
            include_details=current_app.debug
        )


@bp.route('/session/<session_id>/update', methods=['POST'])
def update_session(session_id: str):
    """
    Update boundary for a specific term in the session.
    
    Args:
        session_id: The session identifier
        
    Expects JSON body:
        {
            "term_id": "term_0_hello",
            "start_time": 1.5,
            "end_time": 2.3
        }
        
    Returns:
        JSON response with updated session state
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        term_id = data.get('term_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # Validate required fields
        if not term_id:
            return jsonify({
                'success': False,
                'error': 'term_id is required'
            }), 400
        
        if start_time is None or end_time is None:
            return jsonify({
                'success': False,
                'error': 'start_time and end_time are required'
            }), 400
        
        # Validate time values
        try:
            start_time = float(start_time)
            end_time = float(end_time)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'start_time and end_time must be numeric values'
            }), 400
        
        if start_time < 0 or end_time < 0:
            return jsonify({
                'success': False,
                'error': 'Time values must be non-negative'
            }), 400
        
        if start_time >= end_time:
            return jsonify({
                'success': False,
                'error': 'start_time must be less than end_time'
            }), 400
        
        # Get session to validate term exists and check audio duration
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Find the term being updated
        term_found = False
        for term in session.terms:
            if term.term_id == term_id:
                term_found = True
                break
        
        if not term_found:
            return jsonify({
                'success': False,
                'error': f'Term not found: {term_id}'
            }), 404
        
        # Check boundaries are within audio duration
        if end_time > session.audio_duration:
            return jsonify({
                'success': False,
                'error': f'End time exceeds audio duration ({session.audio_duration:.2f}s)'
            }), 400
        
        # Update boundaries (overlapping is allowed for language learning context)
        success = session_manager.update_boundaries(
            session_id, term_id, start_time, end_time
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to update boundaries'
            }), 500
        
        # Regenerate audio segment with new boundaries
        try:
            from cantonese_anki_generator.web.audio_extractor import AudioExtractor
            
            audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
            if not audio_extractor:
                audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            
            # Load full audio data
            audio_data, sample_rate = audio_extractor.load_audio_for_session(
                session.audio_file_path
            )
            
            # Get updated term
            updated_session = session_manager.get_session(session_id)
            updated_term = None
            for term in updated_session.terms:
                if term.term_id == term_id:
                    updated_term = term
                    break
            
            if updated_term:
                # Regenerate audio segment with new boundaries
                audio_extractor.update_term_segment(
                    session_id, updated_term, audio_data, sample_rate
                )
        except Exception as e:
            # Log error but don't fail the request
            # The boundary update was successful, audio regeneration is secondary
            logger.warning(f"Failed to regenerate audio segment: {e}")
        
        # Get updated session
        updated_session = session_manager.get_session(session_id)
        
        # Find the updated term
        updated_term = None
        for term in updated_session.terms:
            if term.term_id == term_id:
                updated_term = term
                break
        
        return jsonify({
            'success': True,
            'message': 'Boundaries updated successfully',
            'data': {
                'term_id': updated_term.term_id,
                'start_time': convert_numpy_types(updated_term.start_time),
                'end_time': convert_numpy_types(updated_term.end_time),
                'is_manually_adjusted': updated_term.is_manually_adjusted,
                'audio_segment_url': f'/api/audio/{session_id}/{term_id}'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update session: {str(e)}'
        }), 500


@bp.route('/audio/<session_id>/<term_id>', methods=['GET'])
def get_audio_segment(session_id: str, term_id: str):
    """
    Serve audio segment for a specific term.
    
    Args:
        session_id: The session identifier
        term_id: The term identifier (or 'full' for full audio file)
        
    Returns:
        Audio file with appropriate content-type headers
        Supports range requests for audio streaming
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from flask import send_file
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Check if requesting full audio file
        if term_id == 'full':
            # Serve the full audio file
            audio_file_path = session.audio_file_path
            
            if not os.path.exists(audio_file_path):
                return jsonify({
                    'success': False,
                    'error': 'Audio file not found'
                }), 404
            
            # Determine mimetype from file extension
            file_ext = os.path.splitext(audio_file_path)[1].lower()
            mimetype_map = {
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4'
            }
            mimetype = mimetype_map.get(file_ext, 'audio/mpeg')
            
            return send_file(
                audio_file_path,
                mimetype=mimetype,
                as_attachment=False,
                download_name=f'full_audio{file_ext}'
            )
        
        # Get audio extractor from app context
        audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
        if not audio_extractor:
            audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
        
        # Verify term exists in session
        term_found = False
        for term in session.terms:
            if term.term_id == term_id:
                term_found = True
                break
        
        if not term_found:
            return jsonify({
                'success': False,
                'error': f'Term not found: {term_id}'
            }), 404
        
        # Get audio segment file path
        segment_path = audio_extractor.get_segment_path(session_id, term_id)
        
        logger.info(f"Looking for audio segment at: {segment_path}")
        logger.info(f"File exists: {os.path.exists(segment_path)}")
        
        if not os.path.exists(segment_path):
            logger.error(f"Audio segment file not found for term {term_id}: {segment_path}")
            return jsonify({
                'success': False,
                'error': f'Audio segment not found for term: {term_id}'
            }), 404
        
        # Serve the audio file
        # Flask's send_file automatically handles range requests for audio streaming
        logger.info(f"Serving audio segment: {segment_path}")
        
        # Convert to absolute path for Flask
        abs_segment_path = os.path.abspath(segment_path)
        logger.info(f"Absolute path: {abs_segment_path}")
        
        return send_file(
            abs_segment_path,
            mimetype='audio/wav',
            as_attachment=False,
            download_name=f'{term_id}.wav'
        )
        
    except Exception as e:
        logger.error(f"Failed to serve audio segment {term_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to serve audio segment: {str(e)}'
        }), 500


@bp.route('/process', methods=['POST'])
def process_files():
    """
    Process uploaded files and create alignment session.
    Task 7.2: Enhanced with authentication validation before processing
    
    Expects JSON body:
        {
            "doc_url": "https://docs.google.com/...",
            "audio_filepath": "/path/to/audio.mp3"
        }
        
    Returns:
        JSON response with session ID
        
    Requirements: 4.4, 4.5
    """
    try:
        from cantonese_anki_generator.web.processing_controller import ProcessingController
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Parse request data
        try:
            data = request.get_json()
        except Exception as e:
            logger.warning(f"Failed to parse JSON data: {e}")
            response = format_error_response(
                error_message='Invalid JSON data provided',
                error_code=ErrorCode.INVALID_JSON,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 400
        
        if not data:
            logger.warning("No JSON data provided in process request")
            response = format_error_response(
                error_message='No JSON data provided',
                error_code=ErrorCode.MISSING_DATA,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 400
        
        doc_url = data.get('doc_url')
        audio_filepath = data.get('audio_filepath')
        
        if not doc_url or not audio_filepath:
            logger.warning(f"Missing required fields: doc_url={bool(doc_url)}, audio_filepath={bool(audio_filepath)}")
            response = format_error_response(
                error_message='doc_url and audio_filepath are required',
                error_code=ErrorCode.MISSING_FIELDS,
                action_required=ActionRequired.UPLOAD_FILES
            )
            return jsonify(response), 400
        
        # Task 7.2: Check authentication before processing
        # This prevents processing from starting if authentication is invalid
        try:
            authenticator = GoogleDocsAuthenticator(mode='web')
            token_status = authenticator.get_token_status()
            
            if not token_status['valid'] or token_status['expired']:
                # Tokens are invalid or expired - need authentication
                logger.warning("Processing blocked: authentication required")
                
                # Generate authorization URL
                try:
                    authorization_url, state_token = authenticator.get_authorization_url()
                    
                    # Store state token in app context for later validation
                    if not hasattr(current_app, 'oauth_states'):
                        current_app.oauth_states = {}
                    current_app.oauth_states[state_token] = {
                        'created_at': datetime.now(),
                        'authenticator': authenticator
                    }
                    
                    error_message = (
                        "Authentication required to process Google Docs/Sheets. "
                        "Please authenticate first:\n"
                        "1. Click the authorization link below\n"
                        "2. Sign in with your Google account\n"
                        "3. Grant the requested permissions\n"
                        "4. Return here and try processing again\n\n"
                        "Your uploaded files have been preserved and will be available after authentication."
                    )
                    
                    return authentication_required_response(
                        message=error_message,
                        authorization_url=authorization_url,
                        files_preserved=True
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to generate authorization URL: {e}", exc_info=True)
                    response = format_error_response(
                        error_message='Authentication required but failed to generate authorization URL. Please ensure credentials.json is configured correctly.',
                        error_code=ErrorCode.AUTH_URL_ERROR,
                        action_required=ActionRequired.CONFIGURE_CREDENTIALS,
                        files_preserved=True
                    )
                    return jsonify(response), 500
                    
        except Exception as e:
            logger.error(f"Authentication check failed: {e}", exc_info=True)
            response = format_error_response(
                error_message=f'Failed to check authentication status: {str(e)}. Please try again.',
                error_code=ErrorCode.AUTH_CHECK_ERROR,
                action_required=ActionRequired.RETRY,
                files_preserved=True
            )
            return jsonify(response), 500
        
        # Verify audio file exists
        if not os.path.exists(audio_filepath):
            logger.error(f"Audio file not found: {audio_filepath}")
            response = format_error_response(
                error_message='Audio file not found. Please upload the file again.',
                error_code=ErrorCode.FILE_NOT_FOUND,
                action_required=ActionRequired.UPLOAD_FILES
            )
            return jsonify(response), 404
        
        # Get or create processing controller
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
            current_app.config['SESSION_MANAGER'] = session_manager
        
        audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
        if not audio_extractor:
            audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            current_app.config['AUDIO_EXTRACTOR'] = audio_extractor
        
        processing_controller = ProcessingController(
            session_manager=session_manager,
            temp_dir='temp/audio_segments'
        )
        
        # Process files and create session
        logger.info(f"Starting processing for doc_url={doc_url}, audio={audio_filepath}")
        
        try:
            session_id = processing_controller.process_upload(doc_url, audio_filepath)
        except ValueError as e:
            # Handle validation errors from processing
            logger.warning(f"Processing validation error: {e}")
            response = format_error_response(
                error_message=str(e),
                error_code=ErrorCode.PROCESSING_VALIDATION_ERROR,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 400
        except FileNotFoundError as e:
            logger.error(f"File not found during processing: {e}")
            response = format_error_response(
                error_message='Required file not found during processing. Please try uploading again.',
                error_code=ErrorCode.PROCESSING_FILE_NOT_FOUND,
                action_required=ActionRequired.UPLOAD_FILES
            )
            return jsonify(response), 404
        except HttpError as e:
            # Handle Google API errors (including authentication errors)
            logger.error(f"Google API error during processing: {e.resp.status} - {e}")
            
            if e.resp.status == 401:
                # Authentication error during processing
                try:
                    authenticator = GoogleDocsAuthenticator(mode='web')
                    authorization_url, state_token = authenticator.get_authorization_url()
                    
                    if not hasattr(current_app, 'oauth_states'):
                        current_app.oauth_states = {}
                    current_app.oauth_states[state_token] = {
                        'created_at': datetime.now(),
                        'authenticator': authenticator
                    }
                    
                    error_message = (
                        "Authentication expired during processing. "
                        "Please re-authenticate and try again. "
                        "Your uploaded files have been preserved."
                    )
                    
                    return authentication_expired_response(
                        authorization_url=authorization_url,
                        files_preserved=True
                    )
                    
                except Exception as auth_error:
                    logger.error(f"Failed to generate authorization URL: {auth_error}", exc_info=True)
                    return authentication_expired_response(files_preserved=True)
            else:
                response = format_error_response(
                    error_message=f'Google API error (HTTP {e.resp.status}): {str(e)}. Please check your document permissions.',
                    error_code=ErrorCode.GOOGLE_API_ERROR,
                    action_required=ActionRequired.CHECK_PERMISSIONS,
                    files_preserved=True
                )
                return jsonify(response), 500
                
        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            return processing_error_response(
                error_details=str(e),
                files_preserved=True
            )
        
        # Get session data
        session = session_manager.get_session(session_id)
        
        if not session:
            logger.error(f"Session not found after creation: {session_id}")
            response = format_error_response(
                error_message='Failed to create session',
                error_code=ErrorCode.SESSION_CREATION_FAILED,
                action_required=ActionRequired.RETRY
            )
            return jsonify(response), 500
        
        logger.info(f"Processing complete: session_id={session_id}, terms={len(session.terms)}")
        
        return jsonify({
            'success': True,
            'message': 'Processing complete',
            'data': {
                'session_id': session_id,
                'total_terms': len(session.terms),
                'audio_duration': convert_numpy_types(session.audio_duration),
                'low_confidence_count': sum(1 for term in session.terms if convert_numpy_types(term.confidence_score) < 0.6)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Processing failed with unexpected error: {e}", exc_info=True)
        return processing_error_response(
            error_details=str(e),
            files_preserved=True
        )


@bp.route('/session/<session_id>/save', methods=['POST'])
def save_session(session_id: str):
    """
    Save current session state with all boundary adjustments.
    
    Args:
        session_id: The session identifier
        
    Returns:
        JSON response with save confirmation
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Session is already persisted to disk by SessionManager
        # Just need to confirm it's saved
        return jsonify({
            'success': True,
            'message': 'Session saved successfully',
            'data': {
                'session_id': session.session_id,
                'last_modified': session.last_modified.isoformat(),
                'total_terms': len(session.terms),
                'manually_adjusted_count': sum(1 for term in session.terms if term.is_manually_adjusted)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to save session: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/reset/<term_id>', methods=['POST'])
def reset_term(session_id: str, term_id: str):
    """
    Reset a term's boundaries to the original automatic alignment.
    
    Args:
        session_id: The session identifier
        term_id: The term identifier
        
    Returns:
        JSON response with reset confirmation and original boundaries
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Verify term exists
        term_found = False
        original_start = None
        original_end = None
        for term in session.terms:
            if term.term_id == term_id:
                term_found = True
                original_start = term.original_start
                original_end = term.original_end
                break
        
        if not term_found:
            return jsonify({
                'success': False,
                'error': f'Term not found: {term_id}'
            }), 404
        
        # Reset boundaries
        success = session_manager.reset_term_boundaries(session_id, term_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to reset term boundaries'
            }), 500
        
        # Regenerate audio segment with original boundaries
        try:
            audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
            if not audio_extractor:
                audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            
            # Load full audio data
            audio_data, sample_rate = audio_extractor.load_audio_for_session(
                session.audio_file_path
            )
            
            # Get updated term
            updated_session = session_manager.get_session(session_id)
            updated_term = None
            for term in updated_session.terms:
                if term.term_id == term_id:
                    updated_term = term
                    break
            
            if updated_term:
                # Regenerate audio segment with original boundaries
                audio_extractor.update_term_segment(
                    session_id, updated_term, audio_data, sample_rate
                )
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Failed to regenerate audio segment: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Term boundaries reset to original alignment',
            'data': {
                'term_id': term_id,
                'start_time': convert_numpy_types(original_start),
                'end_time': convert_numpy_types(original_end),
                'is_manually_adjusted': False,
                'audio_segment_url': f'/api/audio/{session_id}/{term_id}'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to reset term: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/reset-all', methods=['POST'])
def reset_all_terms(session_id: str):
    """
    Reset all terms' boundaries to their original automatic alignments.
    
    Args:
        session_id: The session identifier
        
    Returns:
        JSON response with reset confirmation
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Count manually adjusted terms before reset
        manually_adjusted_count = sum(1 for term in session.terms if term.is_manually_adjusted)
        
        # Reset all terms
        reset_count = 0
        for term in session.terms:
            if term.is_manually_adjusted:
                success = session_manager.reset_term_boundaries(session_id, term.term_id)
                if success:
                    reset_count += 1
        
        # Regenerate all audio segments with original boundaries
        try:
            audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
            if not audio_extractor:
                audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            
            # Load full audio data
            audio_data, sample_rate = audio_extractor.load_audio_for_session(
                session.audio_file_path
            )
            
            # Get updated session
            updated_session = session_manager.get_session(session_id)
            
            # Regenerate audio segments for all terms
            for term in updated_session.terms:
                audio_extractor.update_term_segment(
                    session_id, term, audio_data, sample_rate
                )
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Failed to regenerate audio segments: {e}")
        
        return jsonify({
            'success': True,
            'message': f'All terms reset to original alignment ({reset_count} terms affected)',
            'data': {
                'session_id': session_id,
                'reset_count': reset_count,
                'total_terms': len(session.terms)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to reset all terms: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/regenerate/<term_id>', methods=['POST'])
def regenerate_term(session_id: str, term_id: str):
    """
    Regenerate alignment for a single term.
    
    Re-runs the automatic alignment algorithm for just this term.
    
    Args:
        session_id: The session identifier
        term_id: The term identifier
        
    Returns:
        JSON response with updated term alignment
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.processing_controller import ProcessingController
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Get session manager and processing controller
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        processing_controller = current_app.config.get('PROCESSING_CONTROLLER')
        if not processing_controller:
            audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            processing_controller = ProcessingController(
                session_manager=session_manager,
                temp_dir='temp/audio_segments'
            )
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Load audio data
        audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
        audio_data, sample_rate = audio_extractor.load_audio_for_session(
            session.audio_file_path
        )
        
        # Regenerate term alignment
        updated_term = processing_controller.regenerate_term_alignment(
            session_id, term_id, audio_data, sample_rate
        )
        
        return jsonify({
            'success': True,
            'message': f'Term "{updated_term.english}" regenerated successfully',
            'data': {
                'term': {
                    'term_id': updated_term.term_id,
                    'english': updated_term.english,
                    'cantonese': updated_term.cantonese,
                    'start_time': convert_numpy_types(updated_term.start_time),
                    'end_time': convert_numpy_types(updated_term.end_time),
                    'confidence_score': convert_numpy_types(updated_term.confidence_score),
                    'is_manually_adjusted': updated_term.is_manually_adjusted,
                    'audio_segment_url': f'/api/audio/{session_id}/{term_id}'
                }
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to regenerate term: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/regenerate-from/<term_id>', methods=['POST'])
def regenerate_from_term(session_id: str, term_id: str):
    """
    Regenerate alignment for a term and all following terms.
    
    Re-runs the automatic alignment algorithm starting from the specified term,
    using the provided start time as the beginning point.
    
    Args:
        session_id: The session identifier
        term_id: The term identifier to start from
        
    Expects JSON body:
        {
            "start_from_time": 12.5  # Time in seconds to start alignment from
        }
        
    Returns:
        JSON response with updated term alignments
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.processing_controller import ProcessingController
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from cantonese_anki_generator.web.session_models import convert_numpy_types
        
        # Initialize progress
        regeneration_progress[session_id] = {
            'percent': 0,
            'stage': 'Starting regeneration...',
            'status': 'processing'
        }
        
        # Parse request body
        data = request.get_json()
        if not data or 'start_from_time' not in data:
            regeneration_progress[session_id] = {
                'percent': 0,
                'stage': 'Error: Missing start_from_time',
                'status': 'error'
            }
            return jsonify({
                'success': False,
                'error': 'Missing required field: start_from_time'
            }), 400
        
        start_from_time = float(data['start_from_time'])
        
        # Get session manager and processing controller
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        processing_controller = current_app.config.get('PROCESSING_CONTROLLER')
        if not processing_controller:
            audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
            processing_controller = ProcessingController(
                session_manager=session_manager,
                temp_dir='temp/audio_segments'
            )
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            regeneration_progress[session_id] = {
                'percent': 0,
                'stage': 'Error: Session not found',
                'status': 'error'
            }
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        regeneration_progress[session_id] = {
            'percent': 10,
            'stage': 'Loading audio...',
            'status': 'processing'
        }
        
        # Load audio data
        audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
        audio_data, sample_rate = audio_extractor.load_audio_for_session(
            session.audio_file_path
        )
        
        regeneration_progress[session_id] = {
            'percent': 20,
            'stage': 'Regenerating alignments...',
            'status': 'processing'
        }
        
        # Create a progress callback
        def progress_callback(current, total, message):
            percent = 20 + int((current / total) * 70)  # 20-90%
            regeneration_progress[session_id] = {
                'percent': percent,
                'stage': message,
                'status': 'processing'
            }
        
        # Store progress callback in processing controller
        processing_controller.regeneration_progress_callback = progress_callback
        
        # Regenerate from term onwards
        updated_terms = processing_controller.regenerate_from_term(
            session_id, term_id, start_from_time, audio_data, sample_rate
        )
        
        regeneration_progress[session_id] = {
            'percent': 100,
            'stage': 'Complete!',
            'status': 'complete'
        }
        
        # Convert terms to JSON
        terms_data = []
        for term in updated_terms:
            terms_data.append({
                'term_id': term.term_id,
                'english': term.english,
                'cantonese': term.cantonese,
                'start_time': convert_numpy_types(term.start_time),
                'end_time': convert_numpy_types(term.end_time),
                'confidence_score': convert_numpy_types(term.confidence_score),
                'is_manually_adjusted': term.is_manually_adjusted,
                'audio_segment_url': f'/api/audio/{session_id}/{term.term_id}'
            })
        
        return jsonify({
            'success': True,
            'message': f'{len(updated_terms)} term(s) regenerated successfully',
            'data': {
                'terms': terms_data,
                'count': len(updated_terms)
            }
        }), 200
        
    except ValueError as e:
        regeneration_progress[session_id] = {
            'percent': 0,
            'stage': f'Error: {str(e)}',
            'status': 'error'
        }
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        regeneration_progress[session_id] = {
            'percent': 0,
            'stage': f'Error: {str(e)}',
            'status': 'error'
        }
        return jsonify({
            'success': False,
            'error': f'Failed to regenerate terms: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/regenerate/progress', methods=['GET'])
def get_regeneration_progress(session_id: str):
    """
    Get the progress of regeneration for a session.
    
    Args:
        session_id: The session identifier
        
    Returns:
        JSON response with progress information
    """
    progress = regeneration_progress.get(session_id, {
        'percent': 0,
        'stage': 'Not started',
        'status': 'idle'
    })
    
    return jsonify({
        'success': True,
        'data': progress
    }), 200


@bp.route('/session/<session_id>/generate', methods=['POST'])
def generate_anki_package(session_id: str):
    """
    Generate Anki package with manual boundary adjustments.
    
    Args:
        session_id: The session identifier
        
    Expects JSON body (optional):
        {
            "deck_name": "Custom Deck Name"  # Optional, auto-generated if not provided
        }
        
    Returns:
        JSON response with generation progress and download URL
    """
    try:
        from cantonese_anki_generator.web.session_manager import SessionManager
        from cantonese_anki_generator.web.audio_extractor import AudioExtractor
        from cantonese_anki_generator.anki.package_generator import AnkiPackageGenerator
        from cantonese_anki_generator.models import VocabularyEntry, AudioSegment, AlignedPair
        import time
        
        # Initialize progress tracking
        generation_progress[session_id] = {
            'percent': 0,
            'stage': 'Initializing...',
            'status': 'in_progress',
            'error': None
        }
        
        # Get session manager from app context
        session_manager = current_app.config.get('SESSION_MANAGER')
        if not session_manager:
            session_manager = SessionManager(storage_dir=current_app.config.get('SESSION_FOLDER'))
        
        # Verify session exists
        session = session_manager.get_session(session_id)
        if not session:
            generation_progress[session_id] = {
                'percent': 0,
                'stage': 'Error',
                'status': 'error',
                'error': f'Session not found: {session_id}'
            }
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Update session status to generating
        session.status = 'generating'
        session_manager._save_session(session)
        
        # Parse optional deck name from request
        data = request.get_json() or {}
        deck_name = data.get('deck_name')
        
        # Get audio extractor
        audio_extractor = current_app.config.get('AUDIO_EXTRACTOR')
        if not audio_extractor:
            audio_extractor = AudioExtractor(temp_dir='temp/audio_segments')
        
        # Stage 1: Prepare aligned pairs with adjusted boundaries
        generation_progress[session_id] = {
            'percent': 10,
            'stage': 'Preparing vocabulary entries...',
            'status': 'in_progress',
            'error': None
        }
        logger.info(f"Preparing aligned pairs for session {session_id}")
        aligned_pairs = []
        
        total_terms = len(session.terms)
        for i, term in enumerate(session.terms):
            # Update progress for each term
            progress_percent = 10 + int((i / total_terms) * 30)  # 10-40%
            generation_progress[session_id]['percent'] = progress_percent
            generation_progress[session_id]['stage'] = f'Processing term {i+1}/{total_terms}...'
            
            # Create vocabulary entry
            vocab_entry = VocabularyEntry(
                english=term.english,
                cantonese=term.cantonese,
                row_index=i
            )
            
            # Get audio segment path (already extracted with current boundaries)
            segment_path = audio_extractor.get_segment_path(session_id, term.term_id)
            
            # Verify segment exists
            if not os.path.exists(segment_path):
                logger.warning(f"Audio segment not found for term {term.term_id}, regenerating...")
                # Regenerate segment if missing
                audio_data, sample_rate = audio_extractor.load_audio_for_session(
                    session.audio_file_path
                )
                segment_path = audio_extractor.update_term_segment(
                    session_id, term, audio_data, sample_rate
                )
            
            # Create audio segment with current (possibly adjusted) boundaries
            audio_segment = AudioSegment(
                start_time=term.start_time,
                end_time=term.end_time,
                audio_data=np.array([]),  # Not needed for package generation
                confidence=term.confidence_score,
                segment_id=term.term_id
            )
            
            # Create aligned pair
            aligned_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=audio_segment,
                alignment_confidence=term.confidence_score,
                audio_file_path=segment_path
            )
            
            aligned_pairs.append(aligned_pair)
        
        logger.info(f"Prepared {len(aligned_pairs)} aligned pairs")
        
        # Stage 2: Generate Anki package
        generation_progress[session_id] = {
            'percent': 50,
            'stage': 'Creating Anki package...',
            'status': 'in_progress',
            'error': None
        }
        logger.info("Generating Anki package...")
        
        # Create output directory if it doesn't exist (use absolute path from project root)
        project_root = Path(__file__).parent.parent.parent  # Go up from web/api.py to project root
        output_dir = project_root / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        if not deck_name:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            deck_name = f"Cantonese_Vocabulary_{timestamp}"
        
        output_filename = f"{deck_name}.apkg"
        output_path = output_dir / output_filename
        
        # Update progress
        generation_progress[session_id] = {
            'percent': 70,
            'stage': 'Writing package file...',
            'status': 'in_progress',
            'error': None
        }
        
        # Generate the package
        generator = AnkiPackageGenerator()
        success = generator.generate_package(
            aligned_pairs=aligned_pairs,
            output_path=str(output_path),
            deck_name=deck_name
        )
        
        if not success:
            session.status = 'ready'
            session_manager._save_session(session)
            generation_progress[session_id] = {
                'percent': 0,
                'stage': 'Error',
                'status': 'error',
                'error': 'Failed to generate Anki package'
            }
            return jsonify({
                'success': False,
                'error': 'Failed to generate Anki package'
            }), 500
        
        # Get file size
        file_size = os.path.getsize(output_path)
        
        # Update session status to complete
        session.status = 'complete'
        session_manager._save_session(session)
        
        # Count manually adjusted terms
        manually_adjusted_count = sum(1 for term in session.terms if term.is_manually_adjusted)
        
        # Update progress to complete
        generation_progress[session_id] = {
            'percent': 100,
            'stage': 'Complete!',
            'status': 'complete',
            'error': None,
            'download_url': f'/api/download/{session_id}/{output_filename}',
            'filename': output_filename,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'total_terms': len(session.terms),
            'manually_adjusted_count': manually_adjusted_count,
            'card_count': len(aligned_pairs)
        }
        
        logger.info(f"Successfully generated Anki package: {output_path}")
        
        return jsonify({
            'success': True,
            'message': 'Anki package generated successfully',
            'data': {
                'session_id': session_id,
                'download_url': f'/api/download/{session_id}/{output_filename}',
                'filename': output_filename,
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'total_terms': len(session.terms),
                'manually_adjusted_count': manually_adjusted_count,
                'card_count': len(aligned_pairs)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to generate Anki package: {e}", exc_info=True)
        
        # Update progress with error
        generation_progress[session_id] = {
            'percent': 0,
            'stage': 'Error',
            'status': 'error',
            'error': str(e)
        }
        
        # Reset session status on error
        try:
            session = session_manager.get_session(session_id)
            if session:
                session.status = 'ready'
                session_manager._save_session(session)
        except Exception as e:
            logger.error(f"Failed to reset session status for session {session_id}: {str(e)}")
        
        return jsonify({
            'success': False,
            'error': f'Failed to generate Anki package: {str(e)}'
        }), 500


@bp.route('/session/<session_id>/generate/progress', methods=['GET'])
def get_generation_progress(session_id: str):
    """
    Get the current progress of Anki package generation.
    
    Args:
        session_id: The session identifier
        
    Returns:
        JSON response with current progress information
    """
    try:
        # Check if generation is in progress for this session
        if session_id not in generation_progress:
            return jsonify({
                'success': False,
                'error': 'No generation in progress for this session'
            }), 404
        
        progress_data = generation_progress[session_id]
        
        return jsonify({
            'success': True,
            'data': progress_data
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get generation progress: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get generation progress: {str(e)}'
        }), 500


@bp.route('/download/<session_id>/<filename>', methods=['GET'])
def download_package(session_id: str, filename: str):
    """
    Download generated Anki package.
    
    Args:
        session_id: The session identifier
        filename: The package filename
        
    Returns:
        The .apkg file for download
    """
    try:
        from flask import send_file
        from werkzeug.utils import secure_filename
        
        # Secure the filename
        filename = secure_filename(filename)
        
        # Construct file path (use absolute path from project root)
        project_root = Path(__file__).parent.parent.parent  # Go up from web/api.py to project root
        output_dir = project_root / 'output'
        filepath = output_dir / filename
        
        if not filepath.exists():
            return jsonify({
                'success': False,
                'error': f'File not found: {filename}'
            }), 404
        
        # Send file for download
        return send_file(
            filepath,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Failed to download package: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download package: {str(e)}'
        }), 500
