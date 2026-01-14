"""
Base classes and interfaces for the validation system.

Provides abstract base classes that define the interface for all validation
components, ensuring consistent behavior across different validation modules.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict
from .models import ValidationResult, ValidationIssue
from .config import ValidationConfig


class BaseValidator(ABC):
    """
    Abstract base class for all validation components.

    Defines the interface that all validators must implement to ensure
    consistent behavior and integration with the validation coordinator.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize the validator with configuration."""
        self.config = config

    @abstractmethod
    def validate(self, data: Any) -> ValidationResult:
        """
        Perform validation on the provided data.

        Args:
            data: The data to validate (format depends on validator type)

        Returns:
            ValidationResult: Result of the validation operation
        """
        pass

    @abstractmethod
    def get_validation_methods(self) -> List[str]:
        """
        Get list of validation methods used by this validator.

        Returns:
            List[str]: Names of validation methods implemented
        """
        pass

    def create_validation_issue(
        self,
        issue_type,
        severity,
        affected_items: List[str],
        description: str,
        suggested_fix: str,
        confidence: float = 1.0,
        context: Dict[str, Any] = None,
    ) -> ValidationIssue:
        """
        Helper method to create validation issues with consistent formatting.

        Args:
            issue_type: Type of the validation issue
            severity: Severity level of the issue
            affected_items: List of items affected by this issue
            description: Human-readable description of the issue
            suggested_fix: Suggested action to resolve the issue
            confidence: Confidence level in the issue detection (0.0-1.0)
            context: Additional context information

        Returns:
            ValidationIssue: Formatted validation issue
        """
        return ValidationIssue(
            issue_type=issue_type,
            severity=severity,
            affected_items=affected_items,
            description=description,
            suggested_fix=suggested_fix,
            confidence=confidence,
            context=context or {},
        )

    def is_enabled(self) -> bool:
        """Check if this validator is enabled in the current configuration."""
        return self.config.enabled


class CountValidator(BaseValidator):
    """Base class for count validation operations."""

    @abstractmethod
    def count_vocabulary_terms(self, data: Any) -> int:
        """Count vocabulary terms in the provided data."""
        pass

    @abstractmethod
    def count_audio_segments(self, data: Any) -> int:
        """Count audio segments in the provided data."""
        pass

    @abstractmethod
    def compare_counts(self, vocab_count: int, audio_count: int) -> ValidationResult:
        """Compare vocabulary and audio counts and generate validation result."""
        pass


class AlignmentValidator(BaseValidator):
    """Base class for alignment validation operations."""

    @abstractmethod
    def calculate_confidence_score(self, term_audio_pair: Any) -> float:
        """Calculate confidence score for a term-audio pairing."""
        pass

    @abstractmethod
    def detect_misalignment(self, term_audio_pair: Any) -> List[ValidationIssue]:
        """Detect misalignment issues in term-audio pairings."""
        pass

    @abstractmethod
    def cross_verify_alignment(self, term_audio_pair: Any) -> float:
        """Perform cross-verification of alignment using multiple methods."""
        pass


class ContentValidator(BaseValidator):
    """Base class for content validation operations."""

    @abstractmethod
    def detect_silence(self, audio_data: Any) -> List[ValidationIssue]:
        """Detect silent or non-speech audio segments."""
        pass

    @abstractmethod
    def detect_duplicates(self, vocabulary_data: Any) -> List[ValidationIssue]:
        """Detect duplicate or empty vocabulary entries."""
        pass

    @abstractmethod
    def validate_duration(self, audio_segments: Any) -> List[ValidationIssue]:
        """Validate audio segment durations for anomalies."""
        pass

    @abstractmethod
    def detect_misaligned_audio(self, aligned_pairs: Any) -> List[ValidationIssue]:
        """Detect audio clips assigned to wrong vocabulary terms."""
        pass

    @abstractmethod
    def analyze_comprehensive_corruption(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive corruption analysis with specific error details."""
        pass


class IntegrityReporter(ABC):
    """Base class for integrity reporting operations."""

    def __init__(self, config: ValidationConfig):
        """Initialize the reporter with configuration."""
        self.config = config

    @abstractmethod
    def compile_validation_results(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """Compile validation results into a structured format."""
        pass

    @abstractmethod
    def generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate actionable recommendations based on detected issues."""
        pass

    @abstractmethod
    def format_detailed_report(self, compiled_results: Dict[str, Any]) -> str:
        """Format compiled results into a detailed report."""
        pass
