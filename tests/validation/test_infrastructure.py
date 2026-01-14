"""
Test the core validation system infrastructure.

Tests the basic functionality of validation models, configuration,
and coordinator to ensure the infrastructure is properly set up.
"""

import pytest
from datetime import datetime
from hypothesis import given, strategies as st

from cantonese_anki_generator.validation.models import (
    ValidationResult, ValidationIssue, ValidationCheckpoint,
    IssueType, IssueSeverity, CountValidationResult,
    AlignmentValidationResult, IntegrityReport
)
from cantonese_anki_generator.validation.config import (
    ValidationConfig, ValidationStrictness, ValidationThresholds
)
from cantonese_anki_generator.validation.coordinator import ValidationCoordinator


class TestValidationModels:
    """Test validation data models."""
    
    def test_validation_issue_creation(self):
        """Test creating validation issues."""
        issue = ValidationIssue(
            issue_type=IssueType.COUNT_MISMATCH,
            severity=IssueSeverity.ERROR,
            affected_items=["item1", "item2"],
            description="Test issue",
            suggested_fix="Fix the issue",
            confidence=0.9
        )
        
        assert issue.issue_type == IssueType.COUNT_MISMATCH
        assert issue.severity == IssueSeverity.ERROR
        assert len(issue.affected_items) == 2
        assert issue.confidence == 0.9
    
    def test_validation_result_creation(self):
        """Test creating validation results."""
        issues = [
            ValidationIssue(
                issue_type=IssueType.SILENT_AUDIO,
                severity=IssueSeverity.WARNING,
                affected_items=["audio1"],
                description="Silent audio detected",
                suggested_fix="Check audio quality",
                confidence=0.8
            )
        ]
        
        result = ValidationResult(
            checkpoint=ValidationCheckpoint.AUDIO_SEGMENTATION,
            success=False,
            confidence_score=0.7,
            issues=issues,
            recommendations=["Check audio"],
            validation_methods_used=["silence_detection"]
        )
        
        assert result.checkpoint == ValidationCheckpoint.AUDIO_SEGMENTATION
        assert not result.success
        assert len(result.issues) == 1
        assert result.confidence_score == 0.7
    
    def test_integrity_report_properties(self):
        """Test integrity report calculated properties."""
        report = IntegrityReport(
            overall_validation_status=True,
            total_items_validated=10,
            successful_validations=8,
            failed_validations=2,
            validation_summary={},
            detailed_issues=[],
            recommendations=[],
            confidence_distribution={}
        )
        
        assert report.success_rate == 80.0
        assert not report.has_critical_issues()
        
        # Test with critical issues
        critical_issue = ValidationIssue(
            issue_type=IssueType.CORRUPTION,
            severity=IssueSeverity.CRITICAL,
            affected_items=["item1"],
            description="Critical issue",
            suggested_fix="Fix immediately",
            confidence=1.0
        )
        
        report.detailed_issues = [critical_issue]
        assert report.has_critical_issues()


class TestValidationConfig:
    """Test validation configuration system."""
    
    def test_default_config_creation(self):
        """Test creating default validation configuration."""
        config = ValidationConfig()
        
        assert config.strictness == ValidationStrictness.NORMAL
        assert config.enabled is True
        assert config.halt_on_critical is True
        assert config.thresholds is not None
        assert config.enabled_checkpoints is not None
    
    def test_strictness_levels(self):
        """Test different strictness levels."""
        # Test lenient config
        lenient_config = ValidationConfig(strictness=ValidationStrictness.LENIENT)
        assert lenient_config.thresholds.alignment_confidence_min == 0.5
        assert lenient_config.thresholds.count_mismatch_tolerance == 0.2
        
        # Test strict config
        strict_config = ValidationConfig(strictness=ValidationStrictness.STRICT)
        assert strict_config.thresholds.alignment_confidence_min == 0.85
        assert strict_config.thresholds.count_mismatch_tolerance == 0.05
        
        # Test normal config
        normal_config = ValidationConfig(strictness=ValidationStrictness.NORMAL)
        assert normal_config.thresholds.alignment_confidence_min == 0.7
        assert normal_config.thresholds.count_mismatch_tolerance == 0.1
    
    def test_config_modification(self):
        """Test modifying configuration settings."""
        config = ValidationConfig()
        
        # Test disabling validation
        config.disable_validation()
        assert not config.enabled
        
        # Test enabling validation
        config.enable_validation()
        assert config.enabled
        
        # Test changing strictness
        config.set_strictness(ValidationStrictness.STRICT)
        assert config.strictness == ValidationStrictness.STRICT
        assert config.thresholds.alignment_confidence_min == 0.85
    
    def test_checkpoint_configuration(self):
        """Test checkpoint enable/disable functionality."""
        config = ValidationConfig()
        
        assert config.is_checkpoint_enabled('document_parsing')
        assert config.is_checkpoint_enabled('audio_segmentation')
        
        # Test with non-existent checkpoint (should default to True)
        assert config.is_checkpoint_enabled('non_existent_checkpoint')


class TestValidationCoordinator:
    """Test validation coordinator functionality."""
    
    def test_coordinator_initialization(self):
        """Test creating validation coordinator."""
        coordinator = ValidationCoordinator()
        
        assert coordinator.config is not None
        assert coordinator.error_handler is not None
        assert len(coordinator._checkpoint_validators) == 0
        assert len(coordinator._session_results) == 0
    
    def test_validator_registration(self):
        """Test registering validators for checkpoints."""
        coordinator = ValidationCoordinator()
        
        def dummy_validator(data, config):
            return ValidationResult(
                checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                success=True,
                confidence_score=1.0,
                issues=[],
                recommendations=[],
                validation_methods_used=['dummy']
            )
        
        coordinator.register_checkpoint_validator(
            ValidationCheckpoint.DOCUMENT_PARSING, 
            dummy_validator
        )
        
        assert ValidationCheckpoint.DOCUMENT_PARSING in coordinator._checkpoint_validators
        assert len(coordinator._checkpoint_validators[ValidationCheckpoint.DOCUMENT_PARSING]) == 1
    
    def test_validation_session_lifecycle(self):
        """Test validation session start and end."""
        coordinator = ValidationCoordinator()
        
        # Start session
        coordinator.start_validation_session()
        assert coordinator._session_start_time is not None
        assert len(coordinator._session_results) == 0
        
        # End session
        report = coordinator.end_validation_session()
        assert isinstance(report, IntegrityReport)
        assert coordinator._session_start_time is None
    
    def test_bypassed_validation(self):
        """Test validation bypass functionality."""
        config = ValidationConfig(enabled=False)
        coordinator = ValidationCoordinator(config)
        
        result = coordinator.validate_at_checkpoint(
            ValidationCheckpoint.DOCUMENT_PARSING, 
            "test_data"
        )
        
        assert result.success is True
        assert 'bypass' in result.validation_methods_used
        assert result.context.get('bypassed') is True


# Property-based tests using Hypothesis
class TestValidationPropertiesInfrastructure:
    """Property-based tests for validation infrastructure."""
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    def test_confidence_score_bounds(self, confidence):
        """Test that confidence scores are always within valid bounds."""
        issue = ValidationIssue(
            issue_type=IssueType.ALIGNMENT_CONFIDENCE,
            severity=IssueSeverity.WARNING,
            affected_items=["test"],
            description="Test issue",
            suggested_fix="Test fix",
            confidence=confidence
        )
        
        assert 0.0 <= issue.confidence <= 1.0
    
    @given(st.integers(min_value=0, max_value=1000))
    def test_success_rate_calculation(self, successful_validations):
        """Test success rate calculation for various inputs."""
        total_validations = successful_validations + 10  # Always have some total
        
        report = IntegrityReport(
            overall_validation_status=True,
            total_items_validated=total_validations,
            successful_validations=successful_validations,
            failed_validations=total_validations - successful_validations,
            validation_summary={},
            detailed_issues=[],
            recommendations=[],
            confidence_distribution={}
        )
        
        expected_rate = (successful_validations / total_validations) * 100.0
        assert abs(report.success_rate - expected_rate) < 0.01  # Allow for floating point precision
        assert 0.0 <= report.success_rate <= 100.0
    
    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=10))
    def test_affected_items_handling(self, affected_items):
        """Test that affected items are properly handled in validation issues."""
        issue = ValidationIssue(
            issue_type=IssueType.COUNT_MISMATCH,
            severity=IssueSeverity.ERROR,
            affected_items=affected_items,
            description="Test description",
            suggested_fix="Test fix",
            confidence=0.9
        )
        
        assert len(issue.affected_items) == len(affected_items)
        assert all(isinstance(item, str) for item in issue.affected_items)
        assert issue.affected_items == affected_items