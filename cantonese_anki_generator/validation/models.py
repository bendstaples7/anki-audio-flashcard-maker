"""
Core data models for the validation system.

Defines all validation-related data structures including results, issues,
checkpoints, and configuration enums.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from ..models import VocabularyEntry, AudioSegment


class ValidationCheckpoint(Enum):
    """Validation checkpoints in the processing pipeline."""

    DOCUMENT_PARSING = "document_parsing"
    AUDIO_SEGMENTATION = "audio_segmentation"
    ALIGNMENT_PROCESS = "alignment_process"
    PACKAGE_GENERATION = "package_generation"


class IssueType(Enum):
    """Types of validation issues that can be detected."""

    COUNT_MISMATCH = "count_mismatch"
    ALIGNMENT_CONFIDENCE = "alignment_confidence"
    SILENT_AUDIO = "silent_audio"
    DUPLICATE_ENTRY = "duplicate_entry"
    EMPTY_ENTRY = "empty_entry"
    DURATION_ANOMALY = "duration_anomaly"
    MISALIGNMENT = "misalignment"
    CORRUPTION = "corruption"


class IssueSeverity(Enum):
    """Severity levels for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a specific validation issue detected during processing."""

    issue_type: IssueType
    severity: IssueSeverity
    affected_items: List[str]
    description: str
    suggested_fix: str
    confidence: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of a validation operation at a specific checkpoint."""

    checkpoint: ValidationCheckpoint
    success: bool
    confidence_score: float
    issues: List[ValidationIssue]
    recommendations: List[str]
    validation_methods_used: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CountValidationResult:
    """Result of count validation between vocabulary and audio segments."""

    vocabulary_count: int
    audio_segment_count: int
    counts_match: bool
    discrepancy_details: Optional[str] = None
    missing_items: List[str] = field(default_factory=list)
    extra_items: List[str] = field(default_factory=list)
    validation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AlignmentValidationResult:
    """Result of alignment validation for term-audio pairs."""

    term_audio_pair: Tuple[VocabularyEntry, AudioSegment]
    alignment_confidence: float
    validation_methods: Dict[str, float]
    is_valid: bool
    detected_issues: List[str]
    cross_verification_score: float
    validation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IntegrityReport:
    """Comprehensive validation report for the entire processing session."""

    overall_validation_status: bool
    total_items_validated: int
    successful_validations: int
    failed_validations: int
    validation_summary: Dict[str, ValidationResult]
    detailed_issues: List[ValidationIssue]
    recommendations: List[str]
    confidence_distribution: Dict[str, int]
    generation_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of validations."""
        if self.total_items_validated == 0:
            return 0.0
        return (self.successful_validations / self.total_items_validated) * 100.0

    def get_issues_by_severity(self, severity: IssueSeverity) -> List[ValidationIssue]:
        """Get all issues of a specific severity level."""
        return [issue for issue in self.detailed_issues if issue.severity == severity]

    def has_critical_issues(self) -> bool:
        """Check if there are any critical validation issues."""
        return any(issue.severity == IssueSeverity.CRITICAL for issue in self.detailed_issues)
