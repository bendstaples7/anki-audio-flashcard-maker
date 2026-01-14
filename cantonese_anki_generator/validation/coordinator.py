"""
Validation coordinator that orchestrates validation across all pipeline stages.

Manages validation checkpoints, executes validation checks, and handles
validation failures with appropriate error reporting and processing control.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .models import (
    ValidationResult,
    ValidationCheckpoint,
    ValidationIssue,
    IssueSeverity,
    IssueType,
    IntegrityReport,
)
from .config import ValidationConfig, default_validation_config
from ..errors import ErrorHandler, ProcessingError, ErrorCategory, ErrorSeverity


class ValidationCoordinator:
    """
    Orchestrates validation across all pipeline stages and manages validation checkpoints.

    The coordinator is responsible for:
    - Registering validation points in the pipeline
    - Executing validation checks at specified checkpoints
    - Managing processing halt and error reporting for validation failures
    - Coordinating between different validation modules
    """

    def __init__(self, config: ValidationConfig = None, error_handler: ErrorHandler = None):
        """Initialize the validation coordinator."""
        self.config = config or default_validation_config
        self.error_handler = error_handler or ErrorHandler()
        self.logger = logging.getLogger(__name__)

        # Registry of validation functions for each checkpoint
        self._checkpoint_validators: Dict[ValidationCheckpoint, List[Callable]] = {}

        # Cache for validation results
        self._validation_cache: Dict[str, ValidationResult] = {}

        # Validation session data
        self._session_results: List[ValidationResult] = []
        self._session_start_time: Optional[datetime] = None

    def register_checkpoint_validator(
        self, checkpoint: ValidationCheckpoint, validator_func: Callable
    ) -> None:
        """
        Register a validation function for a specific checkpoint.

        Args:
            checkpoint: The checkpoint where validation should occur
            validator_func: Function that performs validation and returns ValidationResult
        """
        if checkpoint not in self._checkpoint_validators:
            self._checkpoint_validators[checkpoint] = []

        self._checkpoint_validators[checkpoint].append(validator_func)
        self.logger.debug(f"Registered validator for checkpoint: {checkpoint.value}")

    def validate_at_checkpoint(
        self, checkpoint: ValidationCheckpoint, data: Any
    ) -> ValidationResult:
        """
        Execute validation checks at a specified checkpoint.

        Args:
            checkpoint: The checkpoint to validate at
            data: Data to validate (format depends on checkpoint)

        Returns:
            ValidationResult: Aggregated result of all validations at this checkpoint
        """
        if not self.config.enabled:
            return self._create_bypassed_result(checkpoint)

        if not self.config.is_checkpoint_enabled(checkpoint.value):
            return self._create_bypassed_result(checkpoint)

        self.logger.info(f"Starting validation at checkpoint: {checkpoint.value}")

        # Check cache if enabled
        cache_key = self._generate_cache_key(checkpoint, data)
        if self.config.cache_validation_results and cache_key in self._validation_cache:
            self.logger.debug(f"Using cached validation result for {checkpoint.value}")
            return self._validation_cache[cache_key]

        # Execute all registered validators for this checkpoint
        validators = self._checkpoint_validators.get(checkpoint, [])
        if not validators:
            self.logger.warning(f"No validators registered for checkpoint: {checkpoint.value}")
            return self._create_no_validators_result(checkpoint)

        validation_results = []
        all_issues = []
        all_recommendations = []
        validation_methods = []

        for validator in validators:
            try:
                result = validator(data, self.config)
                validation_results.append(result)
                all_issues.extend(result.issues)
                all_recommendations.extend(result.recommendations)
                validation_methods.extend(result.validation_methods_used)

            except Exception as e:
                self.logger.error(f"Validator failed at {checkpoint.value}: {e}")
                error_issue = ValidationIssue(
                    issue_type=IssueType.CORRUPTION,
                    severity=IssueSeverity.ERROR,
                    affected_items=[f"validator_{validator.__name__}"],
                    description=f"Validation function failed: {str(e)}",
                    suggested_fix="Check validation function implementation",
                    confidence=0.0,
                )
                all_issues.append(error_issue)

        # Aggregate results
        overall_success = all(result.success for result in validation_results)
        overall_confidence = (
            sum(result.confidence_score for result in validation_results) / len(validation_results)
            if validation_results
            else 0.0
        )

        aggregated_result = ValidationResult(
            checkpoint=checkpoint,
            success=overall_success,
            confidence_score=overall_confidence,
            issues=all_issues,
            recommendations=list(set(all_recommendations)),  # Remove duplicates
            validation_methods_used=list(set(validation_methods)),
            timestamp=datetime.now(),
            context={"validator_count": len(validators)},
        )

        # Cache result if enabled
        if self.config.cache_validation_results:
            self._validation_cache[cache_key] = aggregated_result

        # Store in session results
        self._session_results.append(aggregated_result)

        self.logger.info(
            f"Validation at {checkpoint.value} completed: "
            f"success={overall_success}, confidence={overall_confidence:.2f}"
        )

        return aggregated_result

    def handle_validation_failure(self, result: ValidationResult) -> bool:
        """
        Handle validation failure and determine if processing should continue.

        Args:
            result: The failed validation result

        Returns:
            bool: True if processing should continue, False if it should halt
        """
        critical_issues = [
            issue for issue in result.issues if issue.severity == IssueSeverity.CRITICAL
        ]

        if critical_issues and self.config.halt_on_critical:
            self.logger.critical(
                f"Critical validation failure at {result.checkpoint.value}. "
                f"Halting processing. Issues: {len(critical_issues)}"
            )

            # Create processing error for the error handler
            error = ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                message=f"Critical validation failure at {result.checkpoint.value}",
                details=f"Found {len(critical_issues)} critical issues",
                suggested_actions=result.recommendations,
                error_code="VAL_CRITICAL_001",
                context={
                    "checkpoint": result.checkpoint.value,
                    "issues": [issue.description for issue in critical_issues],
                },
            )
            self.error_handler.add_error(error)
            return False

        # Log warnings for non-critical issues
        warning_issues = [
            issue
            for issue in result.issues
            if issue.severity in [IssueSeverity.WARNING, IssueSeverity.ERROR]
        ]

        if warning_issues:
            self.logger.warning(
                f"Validation issues at {result.checkpoint.value}: {len(warning_issues)} issues"
            )

            error = ProcessingError(
                category=ErrorCategory.INPUT_VALIDATION,
                severity=ErrorSeverity.WARNING,
                message=f"Validation issues at {result.checkpoint.value}",
                details=f"Found {len(warning_issues)} non-critical issues",
                suggested_actions=result.recommendations,
                error_code="VAL_WARNING_001",
                context={
                    "checkpoint": result.checkpoint.value,
                    "issues": [issue.description for issue in warning_issues],
                },
            )
            self.error_handler.add_error(error)

        return True  # Continue processing

    def start_validation_session(self) -> None:
        """Start a new validation session."""
        self._session_start_time = datetime.now()
        self._session_results.clear()
        if self.config.cache_validation_results:
            self._validation_cache.clear()

        self.logger.info("Started new validation session")

    def end_validation_session(self) -> IntegrityReport:
        """
        End the current validation session and generate an integrity report.

        Returns:
            IntegrityReport: Comprehensive report of all validation results
        """
        if not self._session_start_time:
            self.logger.warning("No active validation session to end")
            return self._create_empty_report()

        # Aggregate all session results
        total_validations = len(self._session_results)
        successful_validations = sum(1 for result in self._session_results if result.success)
        failed_validations = total_validations - successful_validations

        # Collect all issues
        all_issues = []
        for result in self._session_results:
            all_issues.extend(result.issues)

        # Collect all recommendations
        all_recommendations = []
        for result in self._session_results:
            all_recommendations.extend(result.recommendations)

        # Create validation summary
        validation_summary = {result.checkpoint.value: result for result in self._session_results}

        # Calculate confidence distribution
        confidence_distribution = self._calculate_confidence_distribution()

        # Determine overall status
        overall_status = all(result.success for result in self._session_results)

        report = IntegrityReport(
            overall_validation_status=overall_status,
            total_items_validated=total_validations,
            successful_validations=successful_validations,
            failed_validations=failed_validations,
            validation_summary=validation_summary,
            detailed_issues=all_issues,
            recommendations=list(set(all_recommendations)),
            confidence_distribution=confidence_distribution,
            generation_timestamp=datetime.now(),
        )

        self.logger.info(
            f"Validation session completed: {successful_validations}/{total_validations} "
            f"successful ({report.success_rate:.1f}%)"
        )

        # Reset session
        self._session_start_time = None

        return report

    def _create_bypassed_result(self, checkpoint: ValidationCheckpoint) -> ValidationResult:
        """Create a result for bypassed validation."""
        return ValidationResult(
            checkpoint=checkpoint,
            success=True,
            confidence_score=1.0,
            issues=[],
            recommendations=[],
            validation_methods_used=["bypass"],
            context={"bypassed": True},
        )

    def _create_no_validators_result(self, checkpoint: ValidationCheckpoint) -> ValidationResult:
        """Create a result when no validators are registered."""
        return ValidationResult(
            checkpoint=checkpoint,
            success=True,
            confidence_score=0.0,
            issues=[],
            recommendations=["Register validators for this checkpoint"],
            validation_methods_used=[],
            context={"no_validators": True},
        )

    def _create_empty_report(self) -> IntegrityReport:
        """Create an empty integrity report."""
        return IntegrityReport(
            overall_validation_status=True,
            total_items_validated=0,
            successful_validations=0,
            failed_validations=0,
            validation_summary={},
            detailed_issues=[],
            recommendations=[],
            confidence_distribution={},
        )

    def _generate_cache_key(self, checkpoint: ValidationCheckpoint, data: Any) -> str:
        """Generate a cache key for validation results."""
        # Simple hash-based cache key - in production might want more sophisticated approach
        data_hash = hash(str(data)) if data is not None else 0
        return f"{checkpoint.value}_{data_hash}"

    def _calculate_confidence_distribution(self) -> Dict[str, int]:
        """Calculate distribution of confidence scores."""
        distribution = {"high": 0, "medium": 0, "low": 0}  # >= 0.8  # 0.5 - 0.8  # < 0.5

        for result in self._session_results:
            if result.confidence_score >= 0.8:
                distribution["high"] += 1
            elif result.confidence_score >= 0.5:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1

        return distribution
