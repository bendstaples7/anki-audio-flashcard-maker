"""
Count validation implementation for the validation system.

Provides vocabulary term counting, audio segment counting, and count comparison
with detailed discrepancy reporting to ensure data integrity.
"""

from typing import List, Dict, Any, Set
from datetime import datetime
import logging

from .base import CountValidator as BaseCountValidator
from .models import (
    ValidationResult,
    ValidationIssue,
    CountValidationResult,
    ValidationCheckpoint,
    IssueType,
    IssueSeverity,
)
from .config import ValidationConfig
from ..models import VocabularyEntry, AudioSegment


logger = logging.getLogger(__name__)


class CountValidator(BaseCountValidator):
    """
    Validates counts between vocabulary terms and audio segments.

    Implements comprehensive counting with duplicate detection, detailed
    discrepancy analysis, and actionable error reporting with processing halt logic.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize the count validator with configuration."""
        super().__init__(config)
        self._validation_methods = [
            "vocabulary_term_counting",
            "audio_segment_counting",
            "duplicate_detection",
            "count_comparison",
            "discrepancy_analysis",
            "critical_failure_detection",
        ]

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Perform count validation on vocabulary and audio data.

        Args:
            data: Dictionary containing 'vocabulary_entries' and 'audio_segments'

        Returns:
            ValidationResult: Complete validation result with issues and recommendations
        """
        if not self.is_enabled():
            return self._create_disabled_result()

        try:
            vocabulary_entries = data.get("vocabulary_entries", [])
            audio_segments = data.get("audio_segments", [])

            # Count vocabulary terms with duplicate detection
            vocab_count = self.count_vocabulary_terms(vocabulary_entries)

            # Count audio segments with validation
            audio_count = self.count_audio_segments(audio_segments)

            # Compare counts and generate detailed result
            count_result = self.compare_counts(vocab_count, audio_count)

            # Create validation result
            issues = []
            recommendations = []
            success = count_result.counts_match

            if not success:
                # Create count mismatch issue with enhanced analysis
                discrepancy_analysis = self._analyze_count_discrepancy(vocab_count, audio_count)
                severity = discrepancy_analysis["severity_level"]

                issue = self.create_validation_issue(
                    issue_type=IssueType.COUNT_MISMATCH,
                    severity=severity,
                    affected_items=[
                        f"vocabulary_count:{vocab_count}",
                        f"audio_count:{audio_count}",
                    ],
                    description=discrepancy_analysis["description"],
                    suggested_fix=self._generate_count_fix_suggestion(count_result),
                    confidence=1.0,
                    context={
                        "vocabulary_count": vocab_count,
                        "audio_count": audio_count,
                        "missing_items": count_result.missing_items,
                        "extra_items": count_result.extra_items,
                        "percentage_difference": discrepancy_analysis["percentage_difference"],
                    },
                )
                issues.append(issue)
                recommendations.extend(self._generate_count_recommendations(count_result))

                # Add actionable error messages
                actionable_messages = self.generate_actionable_error_messages(
                    ValidationResult(
                        checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                        success=False,
                        confidence_score=0.0,
                        issues=[issue],
                        recommendations=[],
                        validation_methods_used=[],
                    )
                )
                recommendations.extend(actionable_messages)

            # Add duplicate detection issues if any
            duplicate_issues = self._detect_vocabulary_duplicates(vocabulary_entries)
            issues.extend(duplicate_issues)

            # Generate actionable messages for all issues
            if duplicate_issues:
                temp_result = ValidationResult(
                    checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                    success=False,
                    confidence_score=0.0,
                    issues=duplicate_issues,
                    recommendations=[],
                    validation_methods_used=[],
                )
                actionable_messages = self.generate_actionable_error_messages(temp_result)
                recommendations.extend(actionable_messages)

            # Determine final success status
            final_success = success and len(duplicate_issues) == 0

            # Create final validation result
            result = ValidationResult(
                checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
                success=final_success,
                confidence_score=1.0 if final_success else 0.0,
                issues=issues,
                recommendations=recommendations,
                validation_methods_used=self._validation_methods,
                context={"count_validation_result": count_result},
            )

            # Log processing halt decision if applicable
            if self.should_halt_processing(result):
                logger.critical(
                    "Count validation failed with critical issues - processing must halt"
                )
                result.context["should_halt_processing"] = True

            return result

        except Exception as e:
            logger.error(f"Count validation failed: {e}")
            return self._create_error_result(str(e))

    def count_vocabulary_terms(self, vocabulary_entries: List[VocabularyEntry]) -> int:
        """
        Count vocabulary terms with duplicate detection.

        Args:
            vocabulary_entries: List of vocabulary entries to count

        Returns:
            int: Number of unique vocabulary terms
        """
        if not vocabulary_entries:
            return 0

        # Count unique terms based on English-Cantonese pairs
        unique_terms = set()
        for entry in vocabulary_entries:
            # Create a normalized key for uniqueness checking
            term_key = (entry.english.strip().lower(), entry.cantonese.strip())
            unique_terms.add(term_key)

        logger.debug(
            f"Counted {len(unique_terms)} unique vocabulary terms from {len(vocabulary_entries)} entries"
        )
        return len(unique_terms)

    def count_audio_segments(self, audio_segments: List[AudioSegment]) -> int:
        """
        Count audio segments with validation.

        Args:
            audio_segments: List of audio segments to count

        Returns:
            int: Number of valid audio segments
        """
        if not audio_segments:
            return 0

        # Count segments that have valid audio data and timing
        valid_segments = 0
        for segment in audio_segments:
            if self._is_valid_audio_segment(segment):
                valid_segments += 1
            else:
                logger.warning(f"Invalid audio segment detected: {segment.segment_id}")

        logger.debug(
            f"Counted {valid_segments} valid audio segments from {len(audio_segments)} total"
        )
        return valid_segments

    def compare_counts(self, vocab_count: int, audio_count: int) -> CountValidationResult:
        """
        Compare vocabulary and audio counts with detailed discrepancy analysis.

        Args:
            vocab_count: Number of vocabulary terms
            audio_count: Number of audio segments

        Returns:
            CountValidationResult: Detailed comparison result
        """
        counts_match = vocab_count == audio_count
        discrepancy_details = None
        missing_items = []
        extra_items = []

        if not counts_match:
            difference = abs(vocab_count - audio_count)
            tolerance = int(
                max(vocab_count, audio_count) * self.config.thresholds.count_mismatch_tolerance
            )

            # Perform specific discrepancy analysis
            discrepancy_analysis = self._analyze_count_discrepancy(vocab_count, audio_count)
            discrepancy_details = discrepancy_analysis["description"]
            missing_items = discrepancy_analysis["missing_items"]
            extra_items = discrepancy_analysis["extra_items"]

            # Check if within tolerance for lenient validation
            if self.config.strictness.value == "lenient" and difference <= tolerance:
                logger.info(f"Count mismatch within tolerance ({tolerance}): {discrepancy_details}")

        return CountValidationResult(
            vocabulary_count=vocab_count,
            audio_segment_count=audio_count,
            counts_match=counts_match,
            discrepancy_details=discrepancy_details,
            missing_items=missing_items,
            extra_items=extra_items,
        )

    def get_validation_methods(self) -> List[str]:
        """Get list of validation methods used by this validator."""
        return self._validation_methods.copy()

    def _is_valid_audio_segment(self, segment: AudioSegment) -> bool:
        """
        Check if an audio segment is valid for counting.

        Args:
            segment: Audio segment to validate

        Returns:
            bool: True if segment is valid
        """
        # Check basic timing validity
        if segment.start_time < 0 or segment.end_time <= segment.start_time:
            return False

        # Check if audio data exists and is not empty
        if segment.audio_data is None or len(segment.audio_data) == 0:
            return False

        # Check segment duration is reasonable (not too short or too long)
        duration = segment.end_time - segment.start_time
        if duration < 0.1 or duration > 30.0:  # 0.1s to 30s reasonable range
            return False

        return True

    def _detect_vocabulary_duplicates(
        self, vocabulary_entries: List[VocabularyEntry]
    ) -> List[ValidationIssue]:
        """
        Detect duplicate vocabulary entries.

        Args:
            vocabulary_entries: List of vocabulary entries to check

        Returns:
            List[ValidationIssue]: List of duplicate-related issues
        """
        issues = []
        seen_terms = {}

        for entry in vocabulary_entries:
            # Create normalized key for duplicate detection
            term_key = (entry.english.strip().lower(), entry.cantonese.strip())

            if term_key in seen_terms:
                # Found duplicate
                original_row = seen_terms[term_key]
                issue = self.create_validation_issue(
                    issue_type=IssueType.DUPLICATE_ENTRY,
                    severity=IssueSeverity.WARNING,
                    affected_items=[f"row_{original_row}", f"row_{entry.row_index}"],
                    description=f"Duplicate vocabulary entry found: '{entry.english}' -> '{entry.cantonese}'",
                    suggested_fix="Remove duplicate entries or verify if they are intentionally different",
                    confidence=0.95,
                    context={
                        "original_row": original_row,
                        "duplicate_row": entry.row_index,
                        "english_term": entry.english,
                        "cantonese_term": entry.cantonese,
                    },
                )
                issues.append(issue)
            else:
                seen_terms[term_key] = entry.row_index

            # Check for empty entries
            if not entry.english.strip() or not entry.cantonese.strip():
                issue = self.create_validation_issue(
                    issue_type=IssueType.EMPTY_ENTRY,
                    severity=IssueSeverity.ERROR,
                    affected_items=[f"row_{entry.row_index}"],
                    description=f"Empty vocabulary entry at row {entry.row_index}",
                    suggested_fix="Fill in missing English or Cantonese text, or remove empty row",
                    confidence=1.0,
                    context={
                        "row_index": entry.row_index,
                        "english_empty": not entry.english.strip(),
                        "cantonese_empty": not entry.cantonese.strip(),
                    },
                )
                issues.append(issue)

        return issues

    def _generate_count_fix_suggestion(self, count_result: CountValidationResult) -> str:
        """Generate specific fix suggestion for count mismatches."""
        if count_result.vocabulary_count > count_result.audio_segment_count:
            return (
                "Check if audio file contains all vocabulary terms. "
                "Consider re-recording missing segments or removing extra vocabulary entries."
            )
        else:
            return (
                "Check if vocabulary document contains all terms corresponding to audio segments. "
                "Consider adding missing vocabulary entries or trimming extra audio."
            )

    def _generate_count_recommendations(self, count_result: CountValidationResult) -> List[str]:
        """Generate actionable recommendations for count validation issues."""
        recommendations = []

        if not count_result.counts_match:
            recommendations.append(
                f"Verify that vocabulary document has {count_result.audio_segment_count} entries "
                f"to match {count_result.audio_segment_count} audio segments"
            )

            if count_result.missing_items:
                recommendations.append(
                    f"Add {len(count_result.missing_items)} missing audio segments or "
                    f"remove corresponding vocabulary entries"
                )

            if count_result.extra_items:
                recommendations.append(
                    f"Remove {len(count_result.extra_items)} extra audio segments or "
                    f"add corresponding vocabulary entries"
                )

        return recommendations

    def _create_disabled_result(self) -> ValidationResult:
        """Create result for when validation is disabled."""
        return ValidationResult(
            checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
            success=True,
            confidence_score=1.0,
            issues=[],
            recommendations=["Count validation is disabled"],
            validation_methods_used=[],
        )

    def _create_error_result(self, error_message: str) -> ValidationResult:
        """Create result for validation errors."""
        issue = self.create_validation_issue(
            issue_type=IssueType.CORRUPTION,
            severity=IssueSeverity.CRITICAL,
            affected_items=["validation_system"],
            description=f"Count validation failed: {error_message}",
            suggested_fix="Check input data format and validation configuration",
            confidence=1.0,
        )

        return ValidationResult(
            checkpoint=ValidationCheckpoint.DOCUMENT_PARSING,
            success=False,
            confidence_score=0.0,
            issues=[issue],
            recommendations=["Fix validation system error before proceeding"],
            validation_methods_used=self._validation_methods,
        )

    def _analyze_count_discrepancy(self, vocab_count: int, audio_count: int) -> Dict[str, Any]:
        """
        Perform specific discrepancy analysis between vocabulary and audio counts.

        Args:
            vocab_count: Number of vocabulary terms
            audio_count: Number of audio segments

        Returns:
            Dict containing detailed discrepancy analysis
        """
        difference = abs(vocab_count - audio_count)
        percentage_diff = (
            (difference / max(vocab_count, audio_count)) * 100
            if max(vocab_count, audio_count) > 0
            else 0
        )

        missing_items = []
        extra_items = []
        description = ""

        if vocab_count > audio_count:
            # Missing audio segments
            missing_count = vocab_count - audio_count
            missing_items = [f"audio_segment_{i+audio_count+1}" for i in range(missing_count)]

            description = (
                f"CRITICAL MISMATCH: Found {vocab_count} vocabulary terms but only {audio_count} audio segments. "
                f"Missing {missing_count} audio segments ({percentage_diff:.1f}% discrepancy). "
                f"This indicates incomplete audio recording or segmentation failure."
            )

        elif audio_count > vocab_count:
            # Extra audio segments
            extra_count = audio_count - vocab_count
            extra_items = [f"audio_segment_{i+vocab_count+1}" for i in range(extra_count)]

            description = (
                f"CRITICAL MISMATCH: Found {audio_count} audio segments but only {vocab_count} vocabulary terms. "
                f"Extra {extra_count} audio segments detected ({percentage_diff:.1f}% discrepancy). "
                f"This indicates incomplete vocabulary extraction or over-segmentation."
            )

        return {
            "description": description,
            "missing_items": missing_items,
            "extra_items": extra_items,
            "difference": difference,
            "percentage_difference": percentage_diff,
            "severity_level": self._determine_discrepancy_severity(percentage_diff),
        }

    def _determine_discrepancy_severity(self, percentage_diff: float) -> IssueSeverity:
        """
        Determine severity level based on percentage difference.

        Args:
            percentage_diff: Percentage difference between counts

        Returns:
            IssueSeverity: Appropriate severity level
        """
        if percentage_diff >= 50.0:
            return IssueSeverity.CRITICAL
        elif percentage_diff >= 20.0:
            return IssueSeverity.ERROR
        elif percentage_diff >= 10.0:
            return IssueSeverity.WARNING
        else:
            return IssueSeverity.INFO

    def should_halt_processing(self, validation_result: ValidationResult) -> bool:
        """
        Determine if processing should be halted based on validation results.

        Args:
            validation_result: Result of count validation

        Returns:
            bool: True if processing should halt
        """
        if not self.config.halt_on_critical:
            return False

        # Check for critical issues
        critical_issues = [
            issue for issue in validation_result.issues if issue.severity == IssueSeverity.CRITICAL
        ]

        if critical_issues:
            logger.critical(
                f"Processing halted due to {len(critical_issues)} critical count validation issues"
            )
            return True

        # Check for multiple error-level issues
        error_issues = [
            issue for issue in validation_result.issues if issue.severity == IssueSeverity.ERROR
        ]

        if len(error_issues) >= 3:  # Multiple errors indicate systemic issues
            logger.error(
                f"Processing halted due to {len(error_issues)} error-level count validation issues"
            )
            return True

        return False

    def generate_actionable_error_messages(self, validation_result: ValidationResult) -> List[str]:
        """
        Generate actionable error messages for count mismatches.

        Args:
            validation_result: Result of count validation

        Returns:
            List[str]: Actionable error messages
        """
        messages = []

        for issue in validation_result.issues:
            if issue.issue_type == IssueType.COUNT_MISMATCH:
                context = issue.context
                vocab_count = context.get("vocabulary_count", 0)
                audio_count = context.get("audio_count", 0)

                if vocab_count > audio_count:
                    messages.append(
                        f"ACTION REQUIRED: Add {vocab_count - audio_count} audio segments or "
                        f"remove {vocab_count - audio_count} vocabulary entries to resolve count mismatch."
                    )
                    messages.append(
                        "SUGGESTED STEPS:\n"
                        "1. Check if audio recording is complete\n"
                        "2. Verify audio segmentation parameters\n"
                        "3. Consider re-recording missing segments\n"
                        "4. Or remove extra vocabulary entries from document"
                    )
                else:
                    messages.append(
                        f"ACTION REQUIRED: Add {audio_count - vocab_count} vocabulary entries or "
                        f"remove {audio_count - vocab_count} audio segments to resolve count mismatch."
                    )
                    messages.append(
                        "SUGGESTED STEPS:\n"
                        "1. Check if vocabulary document is complete\n"
                        "2. Verify document parsing parameters\n"
                        "3. Add missing vocabulary entries to document\n"
                        "4. Or adjust audio segmentation to remove extra segments"
                    )

            elif issue.issue_type == IssueType.DUPLICATE_ENTRY:
                messages.append(
                    f"ACTION REQUIRED: Remove duplicate vocabulary entry at {issue.affected_items}. "
                    f"Duplicates can cause alignment issues and incorrect flashcard generation."
                )

            elif issue.issue_type == IssueType.EMPTY_ENTRY:
                messages.append(
                    f"ACTION REQUIRED: Fill in or remove empty vocabulary entry at {issue.affected_items}. "
                    f"Empty entries will cause processing failures."
                )

        return messages
