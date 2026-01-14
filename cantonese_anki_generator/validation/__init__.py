"""
Robust Validation System for the Cantonese Anki Generator.

This module provides comprehensive validation framework that ensures data integrity
between vocabulary terms and their corresponding audio clips throughout the processing pipeline.
"""

from .models import (
    ValidationResult,
    ValidationIssue,
    CountValidationResult,
    AlignmentValidationResult,
    IntegrityReport,
    ValidationCheckpoint,
    IssueType,
    IssueSeverity,
)

from .coordinator import ValidationCoordinator
from .config import ValidationConfig, ValidationStrictness, ValidationThresholds
from .base import (
    BaseValidator,
    CountValidator as BaseCountValidator,
    AlignmentValidator,
    ContentValidator,
    IntegrityReporter as BaseIntegrityReporter,
)
from .count_validator import CountValidator
from .content_validator import ContentValidatorImpl
from .integrity_reporter import IntegrityReporter

__all__ = [
    "ValidationResult",
    "ValidationIssue",
    "CountValidationResult",
    "AlignmentValidationResult",
    "IntegrityReport",
    "ValidationCheckpoint",
    "IssueType",
    "IssueSeverity",
    "ValidationCoordinator",
    "ValidationConfig",
    "ValidationStrictness",
    "ValidationThresholds",
    "BaseValidator",
    "CountValidator",
    "AlignmentValidator",
    "ContentValidator",
    "ContentValidatorImpl",
    "BaseIntegrityReporter",
    "IntegrityReporter",
]
