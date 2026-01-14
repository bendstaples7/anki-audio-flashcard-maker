"""
Configuration system for the validation framework.

Provides configurable validation strictness levels, performance settings,
and validation bypass functionality.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional


class ValidationStrictness(Enum):
    """Validation strictness levels."""

    LENIENT = "lenient"
    NORMAL = "normal"
    STRICT = "strict"


@dataclass
class ValidationThresholds:
    """Thresholds for various validation checks."""

    alignment_confidence_min: float = 0.7
    count_mismatch_tolerance: float = 0.1  # 10% tolerance
    duration_anomaly_factor: float = 3.0  # 3x expected duration
    silence_threshold_db: float = -40.0
    cross_verification_min_score: float = 0.6


@dataclass
class ValidationConfig:
    """Configuration for the validation system."""

    # Core settings
    strictness: ValidationStrictness = ValidationStrictness.NORMAL
    enabled: bool = True
    halt_on_critical: bool = True

    # Performance settings
    max_validation_time_seconds: float = 300.0  # 5 minutes max
    parallel_validation: bool = True
    cache_validation_results: bool = True

    # Validation thresholds
    thresholds: ValidationThresholds = None

    # Checkpoint configuration
    enabled_checkpoints: Dict[str, bool] = None

    # Reporting settings
    generate_detailed_reports: bool = True
    include_confidence_scores: bool = True
    max_recommendations: int = 10

    def __post_init__(self):
        """Initialize default values based on strictness level."""
        if self.thresholds is None:
            self.thresholds = self._get_default_thresholds()

        if self.enabled_checkpoints is None:
            self.enabled_checkpoints = self._get_default_checkpoints()

    def _get_default_thresholds(self) -> ValidationThresholds:
        """Get default thresholds based on strictness level."""
        if self.strictness == ValidationStrictness.LENIENT:
            return ValidationThresholds(
                alignment_confidence_min=0.5,
                count_mismatch_tolerance=0.2,  # 20% tolerance
                duration_anomaly_factor=5.0,
                silence_threshold_db=-30.0,
                cross_verification_min_score=0.4,
            )
        elif self.strictness == ValidationStrictness.STRICT:
            return ValidationThresholds(
                alignment_confidence_min=0.85,
                count_mismatch_tolerance=0.05,  # 5% tolerance
                duration_anomaly_factor=2.0,
                silence_threshold_db=-50.0,
                cross_verification_min_score=0.8,
            )
        else:  # NORMAL
            return ValidationThresholds()

    def _get_default_checkpoints(self) -> Dict[str, bool]:
        """Get default checkpoint configuration."""
        return {
            "document_parsing": True,
            "audio_segmentation": True,
            "alignment_process": True,
            "package_generation": True,
        }

    def is_checkpoint_enabled(self, checkpoint_name: str) -> bool:
        """Check if a specific checkpoint is enabled."""
        return self.enabled_checkpoints.get(checkpoint_name, True)

    def disable_validation(self) -> None:
        """Disable all validation."""
        self.enabled = False

    def enable_validation(self) -> None:
        """Enable validation with current settings."""
        self.enabled = True

    def set_strictness(self, strictness: ValidationStrictness) -> None:
        """Update strictness level and recalculate thresholds."""
        self.strictness = strictness
        self.thresholds = self._get_default_thresholds()

    def update_threshold(self, threshold_name: str, value: float) -> None:
        """Update a specific threshold value."""
        if hasattr(self.thresholds, threshold_name):
            setattr(self.thresholds, threshold_name, value)
        else:
            raise ValueError(f"Unknown threshold: {threshold_name}")

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration."""
        return {
            "strictness": self.strictness.value,
            "enabled": self.enabled,
            "halt_on_critical": self.halt_on_critical,
            "thresholds": {
                "alignment_confidence_min": self.thresholds.alignment_confidence_min,
                "count_mismatch_tolerance": self.thresholds.count_mismatch_tolerance,
                "duration_anomaly_factor": self.thresholds.duration_anomaly_factor,
                "silence_threshold_db": self.thresholds.silence_threshold_db,
                "cross_verification_min_score": self.thresholds.cross_verification_min_score,
            },
            "enabled_checkpoints": self.enabled_checkpoints,
            "performance": {
                "max_validation_time_seconds": self.max_validation_time_seconds,
                "parallel_validation": self.parallel_validation,
                "cache_validation_results": self.cache_validation_results,
            },
        }


# Default validation configuration instance
default_validation_config = ValidationConfig()
