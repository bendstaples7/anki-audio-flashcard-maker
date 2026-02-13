"""
Comprehensive error handling system for the Cantonese Anki Generator.

This module provides centralized error definitions, error detection,
and actionable error messages for all processing stages.
"""

import logging
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors that can occur during processing."""
    INPUT_VALIDATION = "input_validation"
    AUTHENTICATION = "authentication"
    DOCUMENT_PARSING = "document_parsing"
    AUDIO_PROCESSING = "audio_processing"
    ALIGNMENT = "alignment"
    ANKI_GENERATION = "anki_generation"
    FILE_SYSTEM = "file_system"
    NETWORK = "network"


@dataclass
class ProcessingError:
    """Represents a processing error with context and guidance."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: str
    suggested_actions: List[str]
    error_code: str
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


class CantoneseAnkiError(Exception):
    """Base exception for Cantonese Anki Generator errors."""
    
    def __init__(self, processing_error: ProcessingError):
        self.processing_error = processing_error
        super().__init__(processing_error.message)


class InputValidationError(CantoneseAnkiError):
    """Raised when input validation fails."""
    pass


class AuthenticationError(CantoneseAnkiError):
    """Raised when Google API authentication fails."""
    pass


class DocumentParsingError(CantoneseAnkiError):
    """Raised when document parsing fails."""
    pass


class AudioProcessingError(CantoneseAnkiError):
    """Raised when audio processing fails."""
    pass


class AlignmentError(CantoneseAnkiError):
    """Raised when audio-vocabulary alignment fails."""
    pass


class AnkiGenerationError(CantoneseAnkiError):
    """Raised when Anki package generation fails."""
    pass


class SpreadsheetPrepError(CantoneseAnkiError):
    """Base exception for spreadsheet preparation errors."""
    pass


class TranslationServiceError(SpreadsheetPrepError):
    """Raised when translation service fails."""
    pass


class RomanizationServiceError(SpreadsheetPrepError):
    """Raised when romanization service fails."""
    pass


class SheetExportError(SpreadsheetPrepError):
    """Raised when sheet export fails."""
    pass


class ErrorHandler:
    """
    Centralized error handling and reporting system.
    
    Provides error detection, categorization, and actionable guidance
    for all processing stages.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.errors: List[ProcessingError] = []
        self.warnings: List[ProcessingError] = []
    
    def add_error(self, error: ProcessingError) -> None:
        """Add an error to the collection."""
        if error.severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            self.errors.append(error)
        elif error.severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        
        # Log the error
        log_level = {
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }[error.severity]
        
        self.logger.log(log_level, f"[{error.error_code}] {error.message}")
        if error.details:
            self.logger.log(log_level, f"Details: {error.details}")
    
    def has_errors(self) -> bool:
        """Check if any errors have been recorded."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if any warnings have been recorded."""
        return len(self.warnings) > 0
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of all errors and warnings."""
        return {
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'errors': [self._format_error_for_summary(e) for e in self.errors],
            'warnings': [self._format_error_for_summary(e) for e in self.warnings]
        }
    
    def _format_error_for_summary(self, error: ProcessingError) -> Dict[str, Any]:
        """Format error for summary display."""
        return {
            'code': error.error_code,
            'category': error.category.value,
            'severity': error.severity.value,
            'message': error.message,
            'suggested_actions': error.suggested_actions
        }
    
    def clear_errors(self) -> None:
        """Clear all recorded errors and warnings."""
        self.errors.clear()
        self.warnings.clear()
    
    def validate_google_doc_url(self, url: str) -> Optional[ProcessingError]:
        """Validate Google Docs/Sheets URL format."""
        if not url:
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Google Docs URL is required",
                details="No URL was provided for the Google Docs/Sheets document",
                suggested_actions=[
                    "Provide a valid Google Docs or Google Sheets URL",
                    "Ensure the URL starts with 'https://docs.google.com/'"
                ],
                error_code="INPUT_001"
            )
        
        if not url.startswith('https://docs.google.com/'):
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Invalid Google Docs URL format",
                details=f"URL does not appear to be a Google Docs/Sheets URL: {url}",
                suggested_actions=[
                    "Ensure the URL starts with 'https://docs.google.com/'",
                    "Copy the URL directly from your browser address bar",
                    "Make sure the document is shared with appropriate permissions"
                ],
                error_code="INPUT_002"
            )
        
        return None
    
    def validate_audio_file_path(self, file_path: str) -> Optional[ProcessingError]:
        """Validate audio file path and accessibility."""
        from pathlib import Path
        
        if not file_path:
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Audio file path is required",
                details="No audio file path was provided",
                suggested_actions=[
                    "Provide a valid path to an audio file",
                    "Supported formats: MP3, WAV, M4A, FLAC, OGG"
                ],
                error_code="INPUT_003"
            )
        
        path = Path(file_path)
        
        if not path.exists():
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Audio file not found",
                details=f"The specified audio file does not exist: {file_path}",
                suggested_actions=[
                    "Check that the file path is correct",
                    "Ensure the file has not been moved or deleted",
                    "Use an absolute path if relative path is not working"
                ],
                error_code="INPUT_004"
            )
        
        if not path.is_file():
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Path is not a file",
                details=f"The specified path exists but is not a file: {file_path}",
                suggested_actions=[
                    "Ensure the path points to a file, not a directory",
                    "Check file permissions"
                ],
                error_code="INPUT_005"
            )
        
        supported_formats = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
        if path.suffix.lower() not in supported_formats:
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.ERROR,
                message="Unsupported audio format",
                details=f"Audio format '{path.suffix}' is not supported",
                suggested_actions=[
                    f"Convert the file to a supported format: {', '.join(supported_formats)}",
                    "Use audio conversion software like Audacity or online converters"
                ],
                error_code="INPUT_006"
            )
        
        return None
    
    def handle_authentication_error(self, error: Exception) -> ProcessingError:
        """Handle Google API authentication errors."""
        error_str = str(error).lower()
        
        if 'credentials' in error_str or 'token' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.ERROR,
                message="Google API authentication failed",
                details=f"Authentication error: {error}",
                suggested_actions=[
                    "Ensure credentials.json file is present and valid",
                    "Run the authentication flow again",
                    "Check that the Google Docs/Sheets API is enabled in your Google Cloud project",
                    "Verify that your credentials have the necessary permissions"
                ],
                error_code="AUTH_001"
            )
        
        if 'permission' in error_str or 'access' in error_str or '403' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.ERROR,
                message="Access denied to Google document",
                details=f"Permission error: {error}",
                suggested_actions=[
                    "Ensure the document is shared with your Google account",
                    "Check that the document has 'View' or 'Edit' permissions",
                    "Make sure the document is not private or restricted",
                    "Try accessing the document in your browser first"
                ],
                error_code="AUTH_002"
            )
        
        return ProcessingError(
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.ERROR,
            message="Google API authentication error",
            details=f"Unexpected authentication error: {error}",
            suggested_actions=[
                "Check your internet connection",
                "Verify Google API credentials",
                "Try re-authenticating with Google"
            ],
            error_code="AUTH_003"
        )
    
    def handle_document_parsing_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle document parsing errors."""
        error_str = str(error).lower()
        
        if 'not found' in error_str or '404' in error_str:
            return ProcessingError(
                category=ErrorCategory.DOCUMENT_PARSING,
                severity=ErrorSeverity.ERROR,
                message="Document not found",
                details=f"The specified document could not be found: {error}",
                suggested_actions=[
                    "Verify the document URL is correct",
                    "Check that the document has not been deleted",
                    "Ensure the document ID in the URL is valid"
                ],
                error_code="DOC_001",
                context=context
            )
        
        if 'table' in error_str or 'vocabulary' in error_str:
            return ProcessingError(
                category=ErrorCategory.DOCUMENT_PARSING,
                severity=ErrorSeverity.ERROR,
                message="No vocabulary table found",
                details=f"Could not find or parse vocabulary table: {error}",
                suggested_actions=[
                    "Ensure the document contains a table with vocabulary data",
                    "Check that the table has at least two columns (English and Cantonese)",
                    "Verify the table format is supported",
                    "Make sure the table contains actual vocabulary entries"
                ],
                error_code="DOC_002",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.DOCUMENT_PARSING,
            severity=ErrorSeverity.ERROR,
            message="Document parsing failed",
            details=f"Failed to parse document: {error}",
            suggested_actions=[
                "Check document format and structure",
                "Ensure the document is not corrupted",
                "Try accessing the document manually to verify it loads correctly"
            ],
            error_code="DOC_003",
            context=context
        )
    
    def handle_audio_processing_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle audio processing errors."""
        error_str = str(error).lower()
        
        if 'duration' in error_str or 'short' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUDIO_PROCESSING,
                severity=ErrorSeverity.ERROR,
                message="Audio duration issue",
                details=f"Audio duration problem: {error}",
                suggested_actions=[
                    "Ensure audio file is at least 1 second long",
                    "Check that the audio file is not corrupted",
                    "Verify the audio contains actual speech content"
                ],
                error_code="AUDIO_001",
                context=context
            )
        
        if 'format' in error_str or 'codec' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUDIO_PROCESSING,
                severity=ErrorSeverity.ERROR,
                message="Audio format issue",
                details=f"Audio format problem: {error}",
                suggested_actions=[
                    "Convert audio to a supported format (WAV, MP3, M4A)",
                    "Check that the audio file is not corrupted",
                    "Try using a different audio file"
                ],
                error_code="AUDIO_002",
                context=context
            )
        
        if 'silent' in error_str or 'amplitude' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUDIO_PROCESSING,
                severity=ErrorSeverity.ERROR,
                message="Audio appears to be silent",
                details=f"Audio silence detected: {error}",
                suggested_actions=[
                    "Check that the audio file contains audible speech",
                    "Increase the recording volume if too quiet",
                    "Verify the microphone was working during recording"
                ],
                error_code="AUDIO_003",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.AUDIO_PROCESSING,
            severity=ErrorSeverity.ERROR,
            message="Audio processing failed",
            details=f"Audio processing error: {error}",
            suggested_actions=[
                "Check audio file integrity",
                "Try using a different audio file",
                "Ensure audio file is in a supported format"
            ],
            error_code="AUDIO_004",
            context=context
        )
    
    def handle_alignment_error(self, segments_count: int, vocab_count: int, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle audio-vocabulary alignment errors."""
        if segments_count == 0:
            return ProcessingError(
                category=ErrorCategory.ALIGNMENT,
                severity=ErrorSeverity.ERROR,
                message="No audio segments detected",
                details="Audio segmentation produced no segments",
                suggested_actions=[
                    "Check that the audio contains clear speech",
                    "Ensure the audio is not too quiet or noisy",
                    "Try adjusting audio processing parameters",
                    "Verify the audio file contains the expected vocabulary"
                ],
                error_code="ALIGN_001",
                context=context
            )
        
        if vocab_count == 0:
            return ProcessingError(
                category=ErrorCategory.ALIGNMENT,
                severity=ErrorSeverity.ERROR,
                message="No vocabulary entries found",
                details="Document parsing produced no vocabulary entries",
                suggested_actions=[
                    "Check that the document contains a vocabulary table",
                    "Ensure the table has the correct format",
                    "Verify the table contains actual vocabulary data"
                ],
                error_code="ALIGN_002",
                context=context
            )
        
        mismatch_ratio = abs(segments_count - vocab_count) / max(segments_count, vocab_count)
        
        if mismatch_ratio > 0.5:  # More than 50% mismatch
            return ProcessingError(
                category=ErrorCategory.ALIGNMENT,
                severity=ErrorSeverity.ERROR,
                message="Severe alignment mismatch",
                details=f"Large mismatch between audio segments ({segments_count}) and vocabulary entries ({vocab_count})",
                suggested_actions=[
                    "Verify that the audio contains all vocabulary words",
                    "Check that the vocabulary table is complete",
                    "Ensure the audio and document correspond to each other",
                    "Consider re-recording the audio with clearer pronunciation"
                ],
                error_code="ALIGN_003",
                context=context
            )
        
        elif mismatch_ratio > 0.2:  # More than 20% mismatch
            return ProcessingError(
                category=ErrorCategory.ALIGNMENT,
                severity=ErrorSeverity.WARNING,
                message="Alignment mismatch detected",
                details=f"Mismatch between audio segments ({segments_count}) and vocabulary entries ({vocab_count})",
                suggested_actions=[
                    "Review the generated cards for accuracy",
                    "Consider adjusting audio segmentation parameters",
                    "Verify audio and vocabulary correspondence"
                ],
                error_code="ALIGN_004",
                context=context
            )
        
        return None
    
    def handle_anki_generation_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle Anki package generation errors."""
        error_str = str(error).lower()
        
        if 'permission' in error_str or 'access' in error_str:
            return ProcessingError(
                category=ErrorCategory.ANKI_GENERATION,
                severity=ErrorSeverity.ERROR,
                message="File permission error",
                details=f"Cannot write Anki package: {error}",
                suggested_actions=[
                    "Check write permissions for the output directory",
                    "Ensure the output file is not open in another application",
                    "Try saving to a different location"
                ],
                error_code="ANKI_001",
                context=context
            )
        
        if 'space' in error_str or 'disk' in error_str:
            return ProcessingError(
                category=ErrorCategory.ANKI_GENERATION,
                severity=ErrorSeverity.ERROR,
                message="Insufficient disk space",
                details=f"Not enough disk space to create package: {error}",
                suggested_actions=[
                    "Free up disk space",
                    "Choose a different output location",
                    "Remove temporary files"
                ],
                error_code="ANKI_002",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.ANKI_GENERATION,
            severity=ErrorSeverity.ERROR,
            message="Anki package generation failed",
            details=f"Failed to create Anki package: {error}",
            suggested_actions=[
                "Check that all audio files are accessible",
                "Verify output directory permissions",
                "Try generating the package again"
            ],
            error_code="ANKI_003",
            context=context
        )
    
    def create_partial_success_report(self, total_items: int, successful_items: int, 
                                   failed_items: List[str]) -> ProcessingError:
        """Create a report for partial success scenarios."""
        success_rate = (successful_items / total_items) * 100 if total_items > 0 else 0
        
        if success_rate >= 80:
            severity = ErrorSeverity.WARNING
            message = "Processing completed with minor issues"
        elif success_rate >= 50:
            severity = ErrorSeverity.WARNING
            message = "Processing completed with some failures"
        else:
            severity = ErrorSeverity.ERROR
            message = "Processing completed with significant failures"
        
        return ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=severity,
            message=message,
            details=f"Successfully processed {successful_items}/{total_items} items ({success_rate:.1f}%)",
            suggested_actions=[
                f"Review the {len(failed_items)} failed items",
                "Check the specific error messages for each failure",
                "Consider fixing the issues and reprocessing the failed items"
            ],
            error_code="PARTIAL_001",
            context={
                'total_items': total_items,
                'successful_items': successful_items,
                'failed_items': failed_items,
                'success_rate': success_rate
            }
        )
    
    def handle_translation_service_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle translation service errors."""
        error_str = str(error).lower()
        
        if 'timeout' in error_str or 'timed out' in error_str:
            return ProcessingError(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                message="Translation service timeout",
                details=f"Translation request timed out: {error}",
                suggested_actions=[
                    "Check your internet connection",
                    "Try again in a few moments",
                    "Reduce the number of terms being translated at once",
                    "Manually enter translations for failed terms"
                ],
                error_code="TRANS_001",
                context=context
            )
        
        if 'api' in error_str or 'service' in error_str or 'unavailable' in error_str:
            return ProcessingError(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                message="Translation service unavailable",
                details=f"Translation API is currently unavailable: {error}",
                suggested_actions=[
                    "Check your internet connection",
                    "Verify the translation API is configured correctly",
                    "Try again in a few moments",
                    "Manually enter translations for failed terms"
                ],
                error_code="TRANS_002",
                context=context
            )
        
        if 'auth' in error_str or 'key' in error_str or 'credential' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.ERROR,
                message="Translation service authentication failed",
                details=f"Authentication error with translation API: {error}",
                suggested_actions=[
                    "Check that the translation API key is configured",
                    "Verify the API key is valid and not expired",
                    "Ensure the API is enabled in your account",
                    "Check API usage limits and quotas"
                ],
                error_code="TRANS_003",
                context=context
            )
        
        if 'rate' in error_str or 'limit' in error_str or 'quota' in error_str:
            return ProcessingError(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                message="Translation service rate limit exceeded",
                details=f"API rate limit or quota exceeded: {error}",
                suggested_actions=[
                    "Wait a few minutes before trying again",
                    "Reduce the number of terms being translated",
                    "Check your API usage limits",
                    "Consider upgrading your API plan if needed"
                ],
                error_code="TRANS_004",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            message="Translation service error",
            details=f"Translation failed: {error}",
            suggested_actions=[
                "Check your internet connection",
                "Try again in a few moments",
                "Manually enter translations for failed terms"
            ],
            error_code="TRANS_005",
            context=context
        )
    
    def handle_romanization_service_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle romanization service errors."""
        error_str = str(error).lower()
        
        if 'pycantonese' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUDIO_PROCESSING,
                severity=ErrorSeverity.ERROR,
                message="Romanization service initialization failed",
                details=f"pycantonese library error: {error}",
                suggested_actions=[
                    "Ensure pycantonese library is installed correctly: pip install pycantonese",
                    "Verify pycantonese version is 3.4.0 or higher",
                    "Check that the library can access Cantonese character data",
                    "Manually enter Jyutping for failed entries"
                ],
                error_code="ROM_001",
                context=context
            )
        
        if 'unsupported' in error_str or 'character' in error_str:
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.WARNING,
                message="Unsupported characters in text",
                details=f"Romanization encountered unsupported characters: {error}",
                suggested_actions=[
                    "Check that the Cantonese text contains valid Chinese characters",
                    "Remove or replace unsupported characters",
                    "Manually enter Jyutping for affected entries"
                ],
                error_code="ROM_002",
                context=context
            )
        
        if 'empty' in error_str or 'no text' in error_str:
            return ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.WARNING,
                message="Empty text for romanization",
                details=f"Cannot romanize empty text: {error}",
                suggested_actions=[
                    "Ensure Cantonese text is not empty",
                    "Check that translation completed successfully",
                    "Manually enter Jyutping for affected entries"
                ],
                error_code="ROM_003",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.AUDIO_PROCESSING,
            severity=ErrorSeverity.ERROR,
            message="Romanization service error",
            details=f"Romanization failed: {error}",
            suggested_actions=[
                "Check that the Cantonese text is valid",
                "Try romanizing the text manually",
                "Manually enter Jyutping for failed entries"
            ],
            error_code="ROM_004",
            context=context
        )
    
    def handle_sheet_export_error(self, error: Exception, context: Dict[str, Any] = None) -> ProcessingError:
        """Handle Google Sheets export errors."""
        error_str = str(error).lower()
        
        if 'auth' in error_str or 'credential' in error_str or 'token' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.ERROR,
                message="Google Sheets authentication required",
                details=f"Authentication error: {error}",
                suggested_actions=[
                    "Click the authentication link to sign in",
                    "Sign in with your Google account",
                    "Grant the requested permissions",
                    "Ensure credentials.json file is present and valid"
                ],
                error_code="EXPORT_001",
                context=context
            )
        
        if 'permission' in error_str or 'access' in error_str or '403' in error_str:
            return ProcessingError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.ERROR,
                message="Google Sheets permission denied",
                details=f"Permission error: {error}",
                suggested_actions=[
                    "Check that Google Sheets API is enabled",
                    "Verify your Google account has permission to create sheets",
                    "Re-authenticate with Google",
                    "Check API usage limits"
                ],
                error_code="EXPORT_002",
                context=context
            )
        
        if 'network' in error_str or 'connection' in error_str or 'timeout' in error_str:
            return ProcessingError(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                message="Network error during sheet export",
                details=f"Network error: {error}",
                suggested_actions=[
                    "Check your internet connection",
                    "Try exporting again",
                    "Ensure Google services are accessible",
                    "Check firewall settings"
                ],
                error_code="EXPORT_003",
                context=context
            )
        
        if 'quota' in error_str or 'limit' in error_str or 'rate' in error_str:
            return ProcessingError(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                message="Google Sheets API quota exceeded",
                details=f"API quota or rate limit exceeded: {error}",
                suggested_actions=[
                    "Wait a few minutes before trying again",
                    "Check your Google API usage limits",
                    "Consider upgrading your API quota if needed"
                ],
                error_code="EXPORT_004",
                context=context
            )
        
        return ProcessingError(
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            message="Google Sheets export failed",
            details=f"Failed to create Google Sheet: {error}",
            suggested_actions=[
                "Check your internet connection",
                "Verify Google Sheets API is enabled",
                "Try exporting again",
                "Check authentication status"
            ],
            error_code="EXPORT_005",
            context=context
        )
    
    def handle_validation_error(self, validation_errors: List[str], context: Dict[str, Any] = None) -> ProcessingError:
        """Handle validation errors for spreadsheet preparation."""
        error_count = len(validation_errors)
        
        return ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=ErrorSeverity.ERROR,
            message="Validation failed for vocabulary entries",
            details=f"{error_count} validation error(s) found: {', '.join(validation_errors[:3])}{'...' if error_count > 3 else ''}",
            suggested_actions=[
                "Review highlighted entries in the table",
                "Fill in missing English or Cantonese text",
                "Ensure all required fields are completed",
                "Try exporting again after fixing errors"
            ],
            error_code="VALID_001",
            context=context
        )


# Global error handler instance
error_handler = ErrorHandler()