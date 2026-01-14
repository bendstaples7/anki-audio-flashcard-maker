"""
Integration tests for the validation system with existing codebase.

Tests that the validation system integrates properly with existing
data models and error handling systems.
"""

import pytest
from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.validation import (
    ValidationCoordinator, ValidationConfig, ValidationCheckpoint,
    ValidationResult, IssueType, IssueSeverity
)
from cantonese_anki_generator.errors import ErrorHandler
import numpy as np


class TestValidationIntegration:
    """Test integration between validation system and existing codebase."""
    
    def test_validation_with_existing_models(self, sample_vocabulary_entries, sample_audio_segments):
        """Test validation system works with existing data models."""
        coordinator = ValidationCoordinator()
        
        # Create a simple validator that works with existing models
        def model_validator(data, config):
            vocab_entries, audio_segments = data
            
            issues = []
            if len(vocab_entries) != len(audio_segments):
                issues.append({
                    'issue_type': IssueType.COUNT_MISMATCH,
                    'severity': IssueSeverity.ERROR,
                    'affected_items': ['vocabulary', 'audio'],
                    'description': f"Count mismatch: {len(vocab_entries)} vocab vs {len(audio_segments)} audio",
                    'suggested_fix': "Ensure vocabulary and audio counts match",
                    'confidence': 0.95
                })
            
            return ValidationResult(
                checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
                success=len(issues) == 0,
                confidence_score=0.95 if len(issues) == 0 else 0.5,
                issues=issues,
                recommendations=["Check data consistency"],
                validation_methods_used=['count_comparison']
            )
        
        # Register the validator
        coordinator.register_checkpoint_validator(
            ValidationCheckpoint.ALIGNMENT_PROCESS,
            model_validator
        )
        
        # Test with matching counts (should pass)
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.ALIGNMENT_PROCESS,
            (sample_vocabulary_entries, sample_audio_segments)
        )
        
        assert result.success is True
        assert len(result.issues) == 0
        
        # Test with mismatched counts (should fail)
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.ALIGNMENT_PROCESS,
            (sample_vocabulary_entries[:3], sample_audio_segments)  # 3 vs 5
        )
        
        assert result.success is False
        assert len(result.issues) > 0
    
    def test_validation_with_error_handler(self):
        """Test validation system integration with existing error handler."""
        error_handler = ErrorHandler()
        coordinator = ValidationCoordinator(error_handler=error_handler)
        
        # Create a validator that always fails with critical issues
        def failing_validator(data, config):
            from cantonese_anki_generator.validation.models import ValidationIssue
            
            critical_issue = ValidationIssue(
                issue_type=IssueType.CORRUPTION,
                severity=IssueSeverity.CRITICAL,
                affected_items=['test_data'],
                description="Critical validation failure",
                suggested_fix="Fix the critical issue",
                confidence=1.0
            )
            
            return ValidationResult(
                checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                success=False,
                confidence_score=0.0,
                issues=[critical_issue],
                recommendations=["Fix critical issue immediately"],
                validation_methods_used=['test_validator']
            )
        
        coordinator.register_checkpoint_validator(
            ValidationCheckpoint.DOCUMENT_PARSING,
            failing_validator
        )
        
        # Validate and check error handling
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.DOCUMENT_PARSING,
            "test_data"
        )
        
        # Check that validation failed
        assert result.success is False
        
        # Check that error handler should halt processing
        should_continue = coordinator.handle_validation_failure(result)
        assert should_continue is False  # Should halt due to critical issue
        
        # Check that error was added to error handler
        assert error_handler.has_errors()
    
    def test_vocabulary_entry_validation(self, sample_vocabulary_entries):
        """Test validation of VocabularyEntry objects."""
        coordinator = ValidationCoordinator()
        
        def vocab_validator(vocab_entries, config):
            from cantonese_anki_generator.validation.models import ValidationIssue
            
            issues = []
            
            # Check for empty entries
            for entry in vocab_entries:
                if not entry.english.strip() or not entry.cantonese.strip():
                    issues.append(ValidationIssue(
                        issue_type=IssueType.EMPTY_ENTRY,
                        severity=IssueSeverity.ERROR,
                        affected_items=[f"row_{entry.row_index}"],
                        description=f"Empty vocabulary entry at row {entry.row_index}",
                        suggested_fix="Fill in missing vocabulary data",
                        confidence=1.0
                    ))
                
                # Check confidence levels
                if entry.confidence < 0.5:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.ALIGNMENT_CONFIDENCE,
                        severity=IssueSeverity.WARNING,
                        affected_items=[f"row_{entry.row_index}"],
                        description=f"Low confidence ({entry.confidence}) for entry at row {entry.row_index}",
                        suggested_fix="Review entry accuracy",
                        confidence=0.8
                    ))
            
            return ValidationResult(
                checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                success=len(issues) == 0,
                confidence_score=1.0 if len(issues) == 0 else 0.7,
                issues=issues,
                recommendations=["Review vocabulary entries for completeness"],
                validation_methods_used=['vocabulary_validation']
            )
        
        coordinator.register_checkpoint_validator(
            ValidationCheckpoint.DOCUMENT_PARSING,
            vocab_validator
        )
        
        # Test with good vocabulary entries
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.DOCUMENT_PARSING,
            sample_vocabulary_entries
        )
        
        assert result.success is True
        
        # Test with problematic entries
        bad_entries = [
            VocabularyEntry(english="", cantonese="", row_index=0, confidence=0.0),
            VocabularyEntry(english="test", cantonese="測試", row_index=1, confidence=0.3)
        ]
        
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.DOCUMENT_PARSING,
            bad_entries
        )
        
        assert result.success is False
        assert len(result.issues) == 3  # Empty entry + 2 low confidence issues (one for each entry)
    
    def test_audio_segment_validation(self, sample_audio_segments, silent_audio_segment):
        """Test validation of AudioSegment objects."""
        coordinator = ValidationCoordinator()
        
        def audio_validator(audio_segments, config):
            from cantonese_anki_generator.validation.models import ValidationIssue
            
            issues = []
            
            for segment in audio_segments:
                # Check for silent audio (very low amplitude)
                max_amplitude = np.max(np.abs(segment.audio_data))
                if max_amplitude < 0.01:  # Very quiet threshold
                    issues.append(ValidationIssue(
                        issue_type=IssueType.SILENT_AUDIO,
                        severity=IssueSeverity.WARNING,
                        affected_items=[segment.segment_id],
                        description=f"Audio segment {segment.segment_id} appears to be silent",
                        suggested_fix="Check audio recording quality",
                        confidence=0.9
                    ))
                
                # Check duration
                duration = segment.end_time - segment.start_time
                if duration < 0.1 or duration > 10.0:  # Too short or too long
                    issues.append(ValidationIssue(
                        issue_type=IssueType.DURATION_ANOMALY,
                        severity=IssueSeverity.WARNING,
                        affected_items=[segment.segment_id],
                        description=f"Unusual duration ({duration:.2f}s) for segment {segment.segment_id}",
                        suggested_fix="Review audio segmentation",
                        confidence=0.8
                    ))
            
            return ValidationResult(
                checkpoint=ValidationCheckpoint.AUDIO_SEGMENTATION,
                success=len(issues) == 0,
                confidence_score=1.0 if len(issues) == 0 else 0.6,
                issues=issues,
                recommendations=["Review audio quality and segmentation"],
                validation_methods_used=['audio_validation']
            )
        
        coordinator.register_checkpoint_validator(
            ValidationCheckpoint.AUDIO_SEGMENTATION,
            audio_validator
        )
        
        # Test with good audio segments
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.AUDIO_SEGMENTATION,
            sample_audio_segments
        )
        
        assert result.success is True
        
        # Test with silent audio
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.AUDIO_SEGMENTATION,
            [silent_audio_segment]
        )
        
        assert result.success is False
        assert any(issue.issue_type == IssueType.SILENT_AUDIO for issue in result.issues)
    
    def test_full_validation_session(self, sample_vocabulary_entries, sample_audio_segments):
        """Test a complete validation session with multiple checkpoints."""
        coordinator = ValidationCoordinator()
        
        # Register validators for multiple checkpoints
        def document_validator(data, config):
            return ValidationResult(
                checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                success=True,
                confidence_score=0.95,
                issues=[],
                recommendations=[],
                validation_methods_used=['document_check']
            )
        
        def audio_validator(data, config):
            return ValidationResult(
                checkpoint=ValidationCheckpoint.AUDIO_SEGMENTATION,
                success=True,
                confidence_score=0.9,
                issues=[],
                recommendations=[],
                validation_methods_used=['audio_check']
            )
        
        coordinator.register_checkpoint_validator(ValidationCheckpoint.DOCUMENT_PARSING, document_validator)
        coordinator.register_checkpoint_validator(ValidationCheckpoint.AUDIO_SEGMENTATION, audio_validator)
        
        # Start validation session
        coordinator.start_validation_session()
        
        # Run validations at different checkpoints
        doc_result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.DOCUMENT_PARSING,
            sample_vocabulary_entries
        )
        
        audio_result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.AUDIO_SEGMENTATION,
            sample_audio_segments
        )
        
        # End session and get report
        report = coordinator.end_validation_session()
        
        assert doc_result.success is True
        assert audio_result.success is True
        assert report.overall_validation_status is True
        assert report.total_items_validated == 2
        assert report.successful_validations == 2
        assert report.success_rate == 100.0