"""
Tests for the error handling and progress tracking systems.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from cantonese_anki_generator.errors import (
    ErrorHandler, ProcessingError, ErrorCategory, ErrorSeverity,
    InputValidationError, AuthenticationError
)
from cantonese_anki_generator.progress import (
    ProgressTracker, ProcessingStage, StageProgress
)


class TestErrorHandler:
    """Test the error handling system."""
    
    def test_error_handler_initialization(self):
        """Test error handler initializes correctly."""
        handler = ErrorHandler()
        assert handler.errors == []
        assert handler.warnings == []
        assert not handler.has_errors()
        assert not handler.has_warnings()
    
    def test_add_error(self):
        """Test adding errors to the handler."""
        handler = ErrorHandler()
        
        error = ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            details="Test details",
            suggested_actions=["Test action"],
            error_code="TEST_001"
        )
        
        handler.add_error(error)
        assert handler.has_errors()
        assert len(handler.errors) == 1
        assert handler.errors[0] == error
    
    def test_add_warning(self):
        """Test adding warnings to the handler."""
        handler = ErrorHandler()
        
        warning = ProcessingError(
            category=ErrorCategory.ALIGNMENT,
            severity=ErrorSeverity.WARNING,
            message="Test warning",
            details="Test details",
            suggested_actions=["Test action"],
            error_code="TEST_002"
        )
        
        handler.add_error(warning)
        assert handler.has_warnings()
        assert len(handler.warnings) == 1
        assert handler.warnings[0] == warning
    
    def test_validate_google_doc_url_valid(self):
        """Test validation of valid Google Doc URL."""
        handler = ErrorHandler()
        
        valid_url = "https://docs.google.com/spreadsheets/d/1234567890/edit"
        error = handler.validate_google_doc_url(valid_url)
        assert error is None
    
    def test_validate_google_doc_url_invalid(self):
        """Test validation of invalid Google Doc URL."""
        handler = ErrorHandler()
        
        # Test empty URL
        error = handler.validate_google_doc_url("")
        assert error is not None
        assert error.error_code == "INPUT_001"
        
        # Test invalid URL format
        error = handler.validate_google_doc_url("https://example.com/document")
        assert error is not None
        assert error.error_code == "INPUT_002"
    
    def test_validate_audio_file_path_valid(self, tmp_path):
        """Test validation of valid audio file path."""
        handler = ErrorHandler()
        
        # Create a temporary audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("dummy audio content")
        
        error = handler.validate_audio_file_path(str(audio_file))
        assert error is None
    
    def test_validate_audio_file_path_invalid(self):
        """Test validation of invalid audio file path."""
        handler = ErrorHandler()
        
        # Test empty path
        error = handler.validate_audio_file_path("")
        assert error is not None
        assert error.error_code == "INPUT_003"
        
        # Test non-existent file
        error = handler.validate_audio_file_path("/nonexistent/file.wav")
        assert error is not None
        assert error.error_code == "INPUT_004"
    
    def test_handle_alignment_error(self):
        """Test alignment error handling."""
        handler = ErrorHandler()
        
        # Test severe mismatch (>50% difference)
        error = handler.handle_alignment_error(10, 3)  # 70% mismatch
        assert error is not None
        assert error.severity == ErrorSeverity.ERROR
        assert error.error_code == "ALIGN_003"
        
        # Test moderate mismatch (20-50% difference)
        error = handler.handle_alignment_error(10, 7)  # 30% mismatch
        assert error is not None
        assert error.severity == ErrorSeverity.WARNING
        assert error.error_code == "ALIGN_004"
        
        # Test good alignment (<20% difference)
        error = handler.handle_alignment_error(10, 9)  # 10% mismatch
        assert error is None
        
        # Test perfect alignment
        error = handler.handle_alignment_error(10, 10)
        assert error is None
    
    def test_error_summary(self):
        """Test error summary generation."""
        handler = ErrorHandler()
        
        # Add some errors and warnings
        error = ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            details="Test details",
            suggested_actions=["Test action"],
            error_code="TEST_001"
        )
        
        warning = ProcessingError(
            category=ErrorCategory.ALIGNMENT,
            severity=ErrorSeverity.WARNING,
            message="Test warning",
            details="Test details",
            suggested_actions=["Test action"],
            error_code="TEST_002"
        )
        
        handler.add_error(error)
        handler.add_error(warning)
        
        summary = handler.get_error_summary()
        assert summary['error_count'] == 1
        assert summary['warning_count'] == 1
        assert len(summary['errors']) == 1
        assert len(summary['warnings']) == 1


class TestProgressTracker:
    """Test the progress tracking system."""
    
    def test_progress_tracker_initialization(self):
        """Test progress tracker initializes correctly."""
        tracker = ProgressTracker(enable_console_output=False)
        assert len(tracker.stages) == len(ProcessingStage)
        assert tracker.current_stage is None
        assert tracker.pipeline_start_time is None
    
    def test_start_pipeline(self):
        """Test starting pipeline tracking."""
        tracker = ProgressTracker(enable_console_output=False)
        tracker.start_pipeline()
        assert tracker.pipeline_start_time is not None
    
    def test_stage_lifecycle(self):
        """Test complete stage lifecycle."""
        tracker = ProgressTracker(enable_console_output=False)
        
        # Start stage
        tracker.start_stage(ProcessingStage.INITIALIZATION, total_items=5)
        stage = tracker.stages[ProcessingStage.INITIALIZATION]
        
        assert stage.status == "in_progress"
        assert stage.start_time is not None
        assert stage.total_items == 5
        assert tracker.current_stage == ProcessingStage.INITIALIZATION
        
        # Update progress
        tracker.update_stage_progress(ProcessingStage.INITIALIZATION, completed_items=3)
        assert stage.completed_items == 3
        assert stage.progress_percentage == 60.0
        
        # Complete stage
        tracker.complete_stage(ProcessingStage.INITIALIZATION, success=True)
        assert stage.status == "completed"
        assert stage.end_time is not None
        assert stage.progress_percentage == 100.0
    
    def test_progress_callbacks(self):
        """Test progress callbacks are called."""
        tracker = ProgressTracker(enable_console_output=False)
        
        callback_calls = []
        def test_callback(stage_progress):
            callback_calls.append(stage_progress.stage)
        
        tracker.add_progress_callback(test_callback)
        
        # Start and complete a stage
        tracker.start_stage(ProcessingStage.INITIALIZATION)
        tracker.complete_stage(ProcessingStage.INITIALIZATION, success=True)
        
        # Callback should be called twice (start and complete)
        assert len(callback_calls) == 2
        assert callback_calls[0] == ProcessingStage.INITIALIZATION
        assert callback_calls[1] == ProcessingStage.INITIALIZATION
    
    def test_completion_summary(self):
        """Test completion summary generation."""
        tracker = ProgressTracker(enable_console_output=False)
        tracker.start_pipeline()
        
        # Complete some stages
        tracker.start_stage(ProcessingStage.INITIALIZATION)
        tracker.complete_stage(ProcessingStage.INITIALIZATION, success=True)
        
        tracker.start_stage(ProcessingStage.AUTHENTICATION)
        tracker.complete_stage(ProcessingStage.AUTHENTICATION, success=False)
        
        # Update summary data
        tracker.update_summary_data(vocab_entries=10, cards_created=8)
        
        tracker.complete_pipeline(success=False)
        
        summary = tracker.generate_completion_summary()
        assert summary['stages_completed'] == 1
        assert summary['stages_failed'] == 1
        assert summary['vocabulary_entries'] == 10
        assert summary['cards_created'] == 8
        assert summary['success_rate'] < 100.0
    
    def test_current_progress(self):
        """Test current progress reporting."""
        tracker = ProgressTracker(enable_console_output=False)
        tracker.start_pipeline()
        
        # Initially no current stage
        progress = tracker.get_current_progress()
        assert progress['pipeline_running'] is True
        assert progress['current_stage'] is None
        
        # Start a stage
        tracker.start_stage(ProcessingStage.AUDIO_LOADING, total_items=5)
        tracker.update_stage_progress(ProcessingStage.AUDIO_LOADING, completed_items=2)
        
        progress = tracker.get_current_progress()
        assert progress['current_stage'] is not None
        assert progress['current_stage']['stage'] == ProcessingStage.AUDIO_LOADING.value
        assert progress['current_stage']['completed_items'] == 2
        assert progress['current_stage']['total_items'] == 5


class TestIntegration:
    """Test integration between error handling and progress tracking."""
    
    def test_error_and_progress_integration(self):
        """Test that errors and progress work together."""
        from cantonese_anki_generator.errors import error_handler
        from cantonese_anki_generator.progress import progress_tracker
        
        # Clear any existing state
        error_handler.clear_errors()
        
        # Simulate a processing scenario
        progress_tracker.start_pipeline()
        progress_tracker.start_stage(ProcessingStage.INITIALIZATION)
        
        # Add an error
        error = ProcessingError(
            category=ErrorCategory.INPUT_VALIDATION,
            severity=ErrorSeverity.ERROR,
            message="Integration test error",
            details="Test details",
            suggested_actions=["Test action"],
            error_code="INT_001"
        )
        error_handler.add_error(error)
        
        # Complete stage with failure
        progress_tracker.complete_stage(ProcessingStage.INITIALIZATION, success=False)
        progress_tracker.complete_pipeline(success=False)
        
        # Verify both systems have recorded the failure
        assert error_handler.has_errors()
        summary = progress_tracker.generate_completion_summary()
        assert summary['stages_failed'] > 0