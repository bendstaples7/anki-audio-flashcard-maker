"""
Content validation module for audio and text quality validation.

Implements detection of silent audio, duplicate vocabulary entries,
duration anomalies, and other content quality issues.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import librosa
from datetime import datetime

from .base import ContentValidator
from .models import (
    ValidationResult,
    ValidationIssue,
    IssueType,
    IssueSeverity,
    ValidationCheckpoint,
)
from .config import ValidationConfig
from ..models import VocabularyEntry, AudioSegment, AlignedPair


logger = logging.getLogger(__name__)


class ContentValidatorImpl(ContentValidator):
    """
    Implementation of content validation for audio and text quality.

    Validates audio content for silence, non-speech content, and duration
    anomalies. Validates vocabulary entries for duplicates and empty content.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize content validator with configuration."""
        super().__init__(config)

        # Audio analysis parameters
        self.silence_threshold_db = config.thresholds.silence_threshold_db
        self.duration_anomaly_factor = config.thresholds.duration_anomaly_factor

        # Text validation parameters
        self.min_text_length = 1
        self.max_text_length = 200

        # Audio feature extraction parameters
        self.sample_rate = 22050
        self.frame_length = 2048
        self.hop_length = 512

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Perform comprehensive content validation.

        Args:
            data: Dictionary containing 'audio_segments' and 'vocabulary_entries'

        Returns:
            ValidationResult: Comprehensive validation result
        """
        logger.info("Starting content validation")

        issues = []
        validation_methods = []

        # Extract data components
        audio_segments = data.get("audio_segments", [])
        vocabulary_entries = data.get("vocabulary_entries", [])

        # Validate audio content
        if audio_segments:
            audio_issues = self._validate_audio_content(audio_segments)
            issues.extend(audio_issues)
            validation_methods.extend(
                ["silence_detection", "duration_analysis", "speech_content_analysis"]
            )

        # Validate vocabulary content
        if vocabulary_entries:
            vocab_issues = self._validate_vocabulary_content(vocabulary_entries)
            issues.extend(vocab_issues)
            validation_methods.extend(
                ["duplicate_detection", "empty_entry_detection", "text_quality_analysis"]
            )

        # Calculate overall confidence
        confidence_score = self._calculate_content_confidence(
            issues, len(audio_segments) + len(vocabulary_entries)
        )

        # Generate recommendations
        recommendations = self._generate_content_recommendations(issues)

        success = not any(
            issue.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL] for issue in issues
        )

        logger.info(f"Content validation completed: {len(issues)} issues found, success={success}")

        return ValidationResult(
            checkpoint=ValidationCheckpoint.AUDIO_SEGMENTATION,
            success=success,
            confidence_score=confidence_score,
            issues=issues,
            recommendations=recommendations,
            validation_methods_used=validation_methods,
            context={
                "audio_segments_validated": len(audio_segments),
                "vocabulary_entries_validated": len(vocabulary_entries),
                "validation_timestamp": datetime.now().isoformat(),
            },
        )

    def detect_silence(self, audio_data: Any) -> List[ValidationIssue]:
        """
        Detect silent or non-speech audio segments.

        Args:
            audio_data: Audio segments to analyze

        Returns:
            List of validation issues for silent audio
        """
        if isinstance(audio_data, list):
            # Handle list of AudioSegment objects
            issues = []
            for i, segment in enumerate(audio_data):
                if hasattr(segment, "audio_data") and isinstance(segment.audio_data, np.ndarray):
                    segment_issues = self._detect_silence_in_segment(segment, i)
                    issues.extend(segment_issues)
            return issues
        elif isinstance(audio_data, np.ndarray):
            # Handle single audio array
            return self._detect_silence_in_array(audio_data, "audio_data")
        else:
            logger.warning(f"Unsupported audio data type: {type(audio_data)}")
            return []

    def detect_duplicates(self, vocabulary_data: Any) -> List[ValidationIssue]:
        """
        Detect duplicate or empty vocabulary entries.

        Args:
            vocabulary_data: Vocabulary entries to analyze

        Returns:
            List of validation issues for duplicates and empty entries
        """
        if not isinstance(vocabulary_data, list):
            logger.warning(f"Expected list of vocabulary entries, got {type(vocabulary_data)}")
            return []

        issues = []

        # Track seen entries for duplicate detection
        seen_entries = {}
        empty_entries = []

        for i, entry in enumerate(vocabulary_data):
            if not hasattr(entry, "english") or not hasattr(entry, "cantonese"):
                continue

            # Check for empty entries
            if self._is_empty_entry(entry):
                empty_entries.append(f"Entry {i}: '{entry.english}' -> '{entry.cantonese}'")
                continue

            # Check for duplicates
            entry_key = (entry.english.strip().lower(), entry.cantonese.strip())
            if entry_key in seen_entries:
                duplicate_indices = seen_entries[entry_key]
                duplicate_indices.append(i)

                if len(duplicate_indices) == 2:  # First time we detect this duplicate
                    issues.append(
                        self.create_validation_issue(
                            issue_type=IssueType.DUPLICATE_ENTRY,
                            severity=IssueSeverity.WARNING,
                            affected_items=[f"Entries {duplicate_indices[0]} and {i}"],
                            description=f"Duplicate vocabulary entry found: '{entry.english}' -> '{entry.cantonese}'",
                            suggested_fix="Remove duplicate entries or verify they are intentionally different",
                            confidence=0.95,
                        )
                    )
                else:
                    # Update existing issue with additional duplicate
                    for issue in issues:
                        if (
                            issue.issue_type == IssueType.DUPLICATE_ENTRY
                            and entry.english.lower() in issue.description.lower()
                        ):
                            issue.affected_items[0] = (
                                f"Entries {', '.join(map(str, duplicate_indices))}"
                            )
                            break
            else:
                seen_entries[entry_key] = [i]

        # Add issues for empty entries
        if empty_entries:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.EMPTY_ENTRY,
                    severity=IssueSeverity.ERROR,
                    affected_items=empty_entries,
                    description=f"Found {len(empty_entries)} empty or invalid vocabulary entries",
                    suggested_fix="Remove empty entries or add missing content",
                    confidence=1.0,
                )
            )

        return issues

    def validate_duration(self, audio_segments: Any) -> List[ValidationIssue]:
        """
        Validate audio segment durations for anomalies.

        Args:
            audio_segments: Audio segments to analyze

        Returns:
            List of validation issues for duration anomalies
        """
        if not isinstance(audio_segments, list):
            logger.warning(f"Expected list of audio segments, got {type(audio_segments)}")
            return []

        issues = []
        durations = []

        # Calculate durations
        for segment in audio_segments:
            if hasattr(segment, "start_time") and hasattr(segment, "end_time"):
                duration = segment.end_time - segment.start_time
                durations.append(duration)
            elif hasattr(segment, "audio_data") and isinstance(segment.audio_data, np.ndarray):
                # Estimate duration from audio data length
                duration = len(segment.audio_data) / self.sample_rate
                durations.append(duration)

        if not durations:
            return issues

        # Calculate statistics
        mean_duration = np.mean(durations)
        std_duration = np.std(durations)
        median_duration = np.median(durations)

        # Define anomaly thresholds
        upper_threshold = mean_duration + (self.duration_anomaly_factor * std_duration)
        lower_threshold = max(0.1, mean_duration - (self.duration_anomaly_factor * std_duration))

        # Find anomalous segments
        anomalous_segments = []
        for i, duration in enumerate(durations):
            if duration > upper_threshold or duration < lower_threshold:
                anomalous_segments.append(
                    {
                        "index": i,
                        "duration": duration,
                        "type": "too_long" if duration > upper_threshold else "too_short",
                    }
                )

        # Create issues for anomalous durations
        if anomalous_segments:
            long_segments = [s for s in anomalous_segments if s["type"] == "too_long"]
            short_segments = [s for s in anomalous_segments if s["type"] == "too_short"]

            if long_segments:
                affected_items = [
                    f"Segment {s['index']} ({s['duration']:.2f}s)" for s in long_segments
                ]
                issues.append(
                    self.create_validation_issue(
                        issue_type=IssueType.DURATION_ANOMALY,
                        severity=IssueSeverity.WARNING,
                        affected_items=affected_items,
                        description=f"Found {len(long_segments)} segments significantly longer than average ({mean_duration:.2f}s)",
                        suggested_fix="Review long segments for potential segmentation errors or multiple words",
                        confidence=0.8,
                        context={
                            "mean_duration": mean_duration,
                            "threshold": upper_threshold,
                            "anomaly_type": "too_long",
                        },
                    )
                )

            if short_segments:
                affected_items = [
                    f"Segment {s['index']} ({s['duration']:.2f}s)" for s in short_segments
                ]
                issues.append(
                    self.create_validation_issue(
                        issue_type=IssueType.DURATION_ANOMALY,
                        severity=IssueSeverity.WARNING,
                        affected_items=affected_items,
                        description=f"Found {len(short_segments)} segments significantly shorter than average ({mean_duration:.2f}s)",
                        suggested_fix="Review short segments for potential segmentation errors or missing content",
                        confidence=0.8,
                        context={
                            "mean_duration": mean_duration,
                            "threshold": lower_threshold,
                            "anomaly_type": "too_short",
                        },
                    )
                )

        return issues

    def get_validation_methods(self) -> List[str]:
        """Get list of validation methods used by this validator."""
        return [
            "silence_detection",
            "duration_analysis",
            "speech_content_analysis",
            "duplicate_detection",
            "empty_entry_detection",
            "text_quality_analysis",
        ]

    def _validate_audio_content(self, audio_segments: List[AudioSegment]) -> List[ValidationIssue]:
        """Validate audio content quality."""
        issues = []

        # Detect silence in audio segments
        silence_issues = self.detect_silence(audio_segments)
        issues.extend(silence_issues)

        # Validate duration anomalies
        duration_issues = self.validate_duration(audio_segments)
        issues.extend(duration_issues)

        # Analyze speech content quality
        speech_issues = self._analyze_speech_content(audio_segments)
        issues.extend(speech_issues)

        return issues

    def _validate_vocabulary_content(
        self, vocabulary_entries: List[VocabularyEntry]
    ) -> List[ValidationIssue]:
        """Validate vocabulary content quality."""
        issues = []

        # Detect duplicates and empty entries
        duplicate_issues = self.detect_duplicates(vocabulary_entries)
        issues.extend(duplicate_issues)

        # Analyze text quality
        text_issues = self._analyze_text_quality(vocabulary_entries)
        issues.extend(text_issues)

        return issues

    def _detect_silence_in_segment(
        self, segment: AudioSegment, index: int
    ) -> List[ValidationIssue]:
        """Detect silence in a single audio segment."""
        if not hasattr(segment, "audio_data") or not isinstance(segment.audio_data, np.ndarray):
            return []

        return self._detect_silence_in_array(segment.audio_data, f"Segment {index}")

    def _detect_silence_in_array(
        self, audio_data: np.ndarray, identifier: str
    ) -> List[ValidationIssue]:
        """Detect silence in an audio array."""
        issues = []

        if len(audio_data) == 0:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.SILENT_AUDIO,
                    severity=IssueSeverity.CRITICAL,
                    affected_items=[identifier],
                    description=f"Empty audio data in {identifier}",
                    suggested_fix="Ensure audio data is properly loaded and not empty",
                    confidence=1.0,
                )
            )
            return issues

        # Calculate RMS energy
        rms_energy = librosa.feature.rms(
            y=audio_data, frame_length=self.frame_length, hop_length=self.hop_length
        )[0]

        # Convert to dB
        rms_db = librosa.amplitude_to_db(rms_energy, ref=np.max)

        # Check for silence (energy below threshold)
        silent_frames = np.sum(rms_db < self.silence_threshold_db)
        total_frames = len(rms_db)
        silence_ratio = silent_frames / total_frames if total_frames > 0 else 1.0

        if silence_ratio > 0.8:  # More than 80% silent
            severity = IssueSeverity.CRITICAL if silence_ratio > 0.95 else IssueSeverity.ERROR
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.SILENT_AUDIO,
                    severity=severity,
                    affected_items=[identifier],
                    description=f"{identifier} contains {silence_ratio*100:.1f}% silence (threshold: {self.silence_threshold_db}dB)",
                    suggested_fix="Check audio quality, adjust recording levels, or verify correct audio segmentation",
                    confidence=0.9,
                    context={
                        "silence_ratio": silence_ratio,
                        "threshold_db": self.silence_threshold_db,
                        "mean_energy_db": np.mean(rms_db),
                    },
                )
            )
        elif silence_ratio > 0.5:  # 50-80% silent - warning
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.SILENT_AUDIO,
                    severity=IssueSeverity.WARNING,
                    affected_items=[identifier],
                    description=f"{identifier} contains {silence_ratio*100:.1f}% silence - may indicate low audio quality",
                    suggested_fix="Review audio quality and consider re-recording if necessary",
                    confidence=0.7,
                    context={
                        "silence_ratio": silence_ratio,
                        "threshold_db": self.silence_threshold_db,
                        "mean_energy_db": np.mean(rms_db),
                    },
                )
            )

        return issues

    def _analyze_speech_content(self, audio_segments: List[AudioSegment]) -> List[ValidationIssue]:
        """Analyze speech content quality in audio segments."""
        issues = []

        for i, segment in enumerate(audio_segments):
            if not hasattr(segment, "audio_data") or not isinstance(segment.audio_data, np.ndarray):
                continue

            # Analyze spectral characteristics for speech content
            speech_issues = self._analyze_spectral_content(segment.audio_data, f"Segment {i}")
            issues.extend(speech_issues)

        return issues

    def _analyze_spectral_content(
        self, audio_data: np.ndarray, identifier: str
    ) -> List[ValidationIssue]:
        """Analyze spectral content to detect non-speech audio."""
        issues = []

        if len(audio_data) == 0:
            return issues

        try:
            # Calculate spectral features
            spectral_centroids = librosa.feature.spectral_centroid(
                y=audio_data, sr=self.sample_rate, hop_length=self.hop_length
            )[0]

            spectral_rolloff = librosa.feature.spectral_rolloff(
                y=audio_data, sr=self.sample_rate, hop_length=self.hop_length
            )[0]

            zero_crossing_rate = librosa.feature.zero_crossing_rate(
                audio_data, frame_length=self.frame_length, hop_length=self.hop_length
            )[0]

            # Analyze spectral characteristics
            mean_centroid = np.mean(spectral_centroids)
            mean_rolloff = np.mean(spectral_rolloff)
            mean_zcr = np.mean(zero_crossing_rate)

            # Check for non-speech characteristics
            # Very low spectral centroid might indicate noise or silence
            if mean_centroid < 500:  # Hz
                issues.append(
                    self.create_validation_issue(
                        issue_type=IssueType.CORRUPTION,
                        severity=IssueSeverity.WARNING,
                        affected_items=[identifier],
                        description=f"{identifier} has very low spectral centroid ({mean_centroid:.0f}Hz) - may contain noise or low-quality audio",
                        suggested_fix="Review audio quality and consider filtering or re-recording",
                        confidence=0.6,
                        context={
                            "spectral_centroid": mean_centroid,
                            "spectral_rolloff": mean_rolloff,
                            "zero_crossing_rate": mean_zcr,
                        },
                    )
                )

            # Very high zero crossing rate might indicate noise
            if mean_zcr > 0.3:
                issues.append(
                    self.create_validation_issue(
                        issue_type=IssueType.CORRUPTION,
                        severity=IssueSeverity.WARNING,
                        affected_items=[identifier],
                        description=f"{identifier} has high zero crossing rate ({mean_zcr:.3f}) - may contain noise",
                        suggested_fix="Check for background noise or audio artifacts",
                        confidence=0.6,
                        context={
                            "zero_crossing_rate": mean_zcr,
                            "spectral_centroid": mean_centroid,
                        },
                    )
                )

        except Exception as e:
            logger.warning(f"Error analyzing spectral content for {identifier}: {e}")

        return issues

    def _analyze_text_quality(
        self, vocabulary_entries: List[VocabularyEntry]
    ) -> List[ValidationIssue]:
        """Analyze text quality in vocabulary entries."""
        issues = []

        suspicious_entries = []
        encoding_issues = []

        for i, entry in enumerate(vocabulary_entries):
            if not hasattr(entry, "english") or not hasattr(entry, "cantonese"):
                continue

            # Check for suspicious characters or encoding issues
            if self._has_encoding_issues(entry.english) or self._has_encoding_issues(
                entry.cantonese
            ):
                encoding_issues.append(f"Entry {i}: '{entry.english}' -> '{entry.cantonese}'")

            # Check for suspicious patterns
            if self._is_suspicious_entry(entry):
                suspicious_entries.append(f"Entry {i}: '{entry.english}' -> '{entry.cantonese}'")

        # Create issues for encoding problems
        if encoding_issues:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.CORRUPTION,
                    severity=IssueSeverity.WARNING,
                    affected_items=encoding_issues,
                    description=f"Found {len(encoding_issues)} entries with potential encoding issues",
                    suggested_fix="Check text encoding and ensure proper character support",
                    confidence=0.8,
                )
            )

        # Create issues for suspicious entries
        if suspicious_entries:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.CORRUPTION,
                    severity=IssueSeverity.INFO,
                    affected_items=suspicious_entries,
                    description=f"Found {len(suspicious_entries)} entries that may need review",
                    suggested_fix="Manually review flagged entries for accuracy",
                    confidence=0.5,
                )
            )

        return issues

    def _is_empty_entry(self, entry: VocabularyEntry) -> bool:
        """Check if a vocabulary entry is empty or invalid."""
        if not hasattr(entry, "english") or not hasattr(entry, "cantonese"):
            return True

        english = str(entry.english).strip()
        cantonese = str(entry.cantonese).strip()

        return (
            len(english) < self.min_text_length
            or len(cantonese) < self.min_text_length
            or len(english) > self.max_text_length
            or len(cantonese) > self.max_text_length
        )

    def _has_encoding_issues(self, text: str) -> bool:
        """Check if text has encoding issues."""
        if not isinstance(text, str):
            return True

        # Check for common encoding issue indicators
        encoding_indicators = ["�", "\ufffd", "?", "???"]
        return any(indicator in text for indicator in encoding_indicators)

    def _is_suspicious_entry(self, entry: VocabularyEntry) -> bool:
        """Check if entry has suspicious patterns."""
        if not hasattr(entry, "english") or not hasattr(entry, "cantonese"):
            return True

        english = str(entry.english).strip().lower()
        cantonese = str(entry.cantonese).strip()

        # Check for suspicious patterns
        suspicious_patterns = [
            english == cantonese.lower(),  # Same text in both fields
            len(english.split()) > 10,  # Very long English text
            english.isdigit(),  # Only numbers
            not english.replace(" ", "")
            .replace("-", "")
            .replace("_", "")
            .isalnum(),  # Non-alphanumeric characters
        ]

        return any(suspicious_patterns)

    def _calculate_content_confidence(
        self, issues: List[ValidationIssue], total_items: int
    ) -> float:
        """Calculate overall confidence score for content validation."""
        if total_items == 0:
            return 0.0

        # Weight issues by severity
        severity_weights = {
            IssueSeverity.INFO: 0.1,
            IssueSeverity.WARNING: 0.3,
            IssueSeverity.ERROR: 0.7,
            IssueSeverity.CRITICAL: 1.0,
        }

        total_penalty = sum(severity_weights.get(issue.severity, 0.5) for issue in issues)
        max_possible_penalty = total_items * 1.0  # Assuming worst case (all critical)

        confidence = max(0.0, 1.0 - (total_penalty / max_possible_penalty))
        return confidence

    def _generate_content_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate actionable recommendations based on detected issues."""
        recommendations = []

        # Group issues by type
        issue_types = {}
        for issue in issues:
            if issue.issue_type not in issue_types:
                issue_types[issue.issue_type] = []
            issue_types[issue.issue_type].append(issue)

        # Generate type-specific recommendations
        if IssueType.SILENT_AUDIO in issue_types:
            recommendations.append("Review audio recording quality and adjust microphone levels")
            recommendations.append("Consider re-recording segments with excessive silence")

        if IssueType.DURATION_ANOMALY in issue_types:
            recommendations.append(
                "Review audio segmentation parameters for better word boundary detection"
            )
            recommendations.append("Manually verify segments with unusual durations")

        if IssueType.DUPLICATE_ENTRY in issue_types:
            recommendations.append(
                "Remove duplicate vocabulary entries or verify intentional differences"
            )

        if IssueType.EMPTY_ENTRY in issue_types:
            recommendations.append("Complete missing vocabulary entries or remove empty rows")

        if IssueType.CORRUPTION in issue_types:
            recommendations.append("Check text encoding and audio file integrity")
            recommendations.append("Manually review flagged entries for accuracy")

        return recommendations[: self.config.max_recommendations]

    def detect_misaligned_audio(self, aligned_pairs: List[AlignedPair]) -> List[ValidationIssue]:
        """
        Detect audio clips assigned to wrong vocabulary terms.

        Args:
            aligned_pairs: List of term-audio pairs to analyze

        Returns:
            List of validation issues for misaligned audio
        """
        issues = []

        if not aligned_pairs:
            return issues

        logger.info(f"Analyzing {len(aligned_pairs)} aligned pairs for misalignment")

        # Analyze alignment confidence patterns
        confidence_issues = self._analyze_alignment_confidence_patterns(aligned_pairs)
        issues.extend(confidence_issues)

        # Detect duration mismatches between expected and actual
        duration_issues = self._detect_duration_mismatches(aligned_pairs)
        issues.extend(duration_issues)

        # Analyze spectral consistency within pairs
        spectral_issues = self._analyze_spectral_consistency(aligned_pairs)
        issues.extend(spectral_issues)

        # Cross-validate pairs for potential swaps
        swap_issues = self._detect_potential_swaps(aligned_pairs)
        issues.extend(swap_issues)

        return issues

    def analyze_comprehensive_corruption(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive corruption analysis with specific error details.

        Args:
            data: Dictionary containing all validation data

        Returns:
            Dictionary with detailed corruption analysis
        """
        analysis = {
            "corruption_types": {},
            "affected_items": {},
            "severity_distribution": {},
            "suggested_corrections": {},
            "confidence_scores": {},
        }

        # Extract components
        aligned_pairs = data.get("aligned_pairs", [])
        audio_segments = data.get("audio_segments", [])
        vocabulary_entries = data.get("vocabulary_entries", [])

        # Analyze different corruption types
        if aligned_pairs:
            misalignment_analysis = self._analyze_misalignment_corruption(aligned_pairs)
            analysis["corruption_types"]["misalignment"] = misalignment_analysis

        if audio_segments:
            audio_analysis = self._analyze_audio_corruption(audio_segments)
            analysis["corruption_types"]["audio"] = audio_analysis

        if vocabulary_entries:
            text_analysis = self._analyze_text_corruption(vocabulary_entries)
            analysis["corruption_types"]["text"] = text_analysis

        # Generate comprehensive recommendations
        analysis["suggested_corrections"] = self._generate_corruption_corrections(analysis)

        return analysis

    def _analyze_alignment_confidence_patterns(
        self, aligned_pairs: List[AlignedPair]
    ) -> List[ValidationIssue]:
        """Analyze alignment confidence patterns to detect systematic issues."""
        issues = []

        confidences = [
            pair.alignment_confidence
            for pair in aligned_pairs
            if hasattr(pair, "alignment_confidence")
        ]

        if not confidences:
            return issues

        mean_confidence = np.mean(confidences)
        std_confidence = np.std(confidences)

        # Detect systematically low confidence
        if mean_confidence < 0.5:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.MISALIGNMENT,
                    severity=IssueSeverity.ERROR,
                    affected_items=[f"Overall alignment (mean confidence: {mean_confidence:.3f})"],
                    description=f"Systematically low alignment confidence across all pairs (mean: {mean_confidence:.3f})",
                    suggested_fix="Review alignment parameters, audio quality, or vocabulary-audio correspondence",
                    confidence=0.9,
                    context={
                        "mean_confidence": mean_confidence,
                        "std_confidence": std_confidence,
                        "total_pairs": len(aligned_pairs),
                    },
                )
            )

        # Detect outlier pairs with very low confidence
        low_confidence_threshold = max(0.3, mean_confidence - 2 * std_confidence)
        low_confidence_pairs = []

        for i, pair in enumerate(aligned_pairs):
            if (
                hasattr(pair, "alignment_confidence")
                and pair.alignment_confidence < low_confidence_threshold
            ):
                vocab_text = (
                    getattr(pair.vocabulary_entry, "english", f"Entry {i}")
                    if hasattr(pair, "vocabulary_entry")
                    else f"Pair {i}"
                )
                low_confidence_pairs.append(
                    f"{vocab_text} (confidence: {pair.alignment_confidence:.3f})"
                )

        if low_confidence_pairs:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.MISALIGNMENT,
                    severity=IssueSeverity.WARNING,
                    affected_items=low_confidence_pairs,
                    description=f"Found {len(low_confidence_pairs)} pairs with unusually low alignment confidence",
                    suggested_fix="Manually review flagged pairs for potential misalignment or audio quality issues",
                    confidence=0.8,
                    context={
                        "threshold": low_confidence_threshold,
                        "mean_confidence": mean_confidence,
                    },
                )
            )

        return issues

    def _detect_duration_mismatches(
        self, aligned_pairs: List[AlignedPair]
    ) -> List[ValidationIssue]:
        """Detect duration mismatches between expected and actual audio lengths."""
        issues = []

        duration_mismatches = []

        for i, pair in enumerate(aligned_pairs):
            if not (hasattr(pair, "vocabulary_entry") and hasattr(pair, "audio_segment")):
                continue

            vocab_entry = pair.vocabulary_entry
            audio_segment = pair.audio_segment

            # Estimate expected duration based on text length
            if hasattr(vocab_entry, "english"):
                # Rough estimate: 0.3-0.5 seconds per syllable/word
                word_count = len(vocab_entry.english.split())
                expected_duration = word_count * 0.4  # seconds per word

                # Get actual duration
                if hasattr(audio_segment, "start_time") and hasattr(audio_segment, "end_time"):
                    actual_duration = audio_segment.end_time - audio_segment.start_time
                elif hasattr(audio_segment, "audio_data") and isinstance(
                    audio_segment.audio_data, np.ndarray
                ):
                    actual_duration = len(audio_segment.audio_data) / self.sample_rate
                else:
                    continue

                # Check for significant mismatch
                duration_ratio = (
                    actual_duration / expected_duration if expected_duration > 0 else float("inf")
                )

                if duration_ratio > 3.0 or duration_ratio < 0.3:
                    mismatch_type = "too_long" if duration_ratio > 3.0 else "too_short"
                    duration_mismatches.append(
                        {
                            "index": i,
                            "vocab_text": vocab_entry.english,
                            "expected_duration": expected_duration,
                            "actual_duration": actual_duration,
                            "ratio": duration_ratio,
                            "type": mismatch_type,
                        }
                    )

        if duration_mismatches:
            affected_items = [
                f"{m['vocab_text']} (expected: {m['expected_duration']:.1f}s, actual: {m['actual_duration']:.1f}s)"
                for m in duration_mismatches
            ]

            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.MISALIGNMENT,
                    severity=IssueSeverity.WARNING,
                    affected_items=affected_items,
                    description=f"Found {len(duration_mismatches)} pairs with significant duration mismatches",
                    suggested_fix="Review audio segmentation and alignment for flagged pairs",
                    confidence=0.7,
                    context={"mismatches": duration_mismatches},
                )
            )

        return issues

    def _analyze_spectral_consistency(
        self, aligned_pairs: List[AlignedPair]
    ) -> List[ValidationIssue]:
        """Analyze spectral consistency within aligned pairs."""
        issues = []

        spectral_outliers = []

        # Calculate spectral features for all pairs
        spectral_features = []
        for i, pair in enumerate(aligned_pairs):
            if not (
                hasattr(pair, "audio_segment")
                and hasattr(pair.audio_segment, "audio_data")
                and isinstance(pair.audio_segment.audio_data, np.ndarray)
            ):
                continue

            audio_data = pair.audio_segment.audio_data
            if len(audio_data) == 0:
                continue

            try:
                # Calculate key spectral features
                spectral_centroid = np.mean(
                    librosa.feature.spectral_centroid(y=audio_data, sr=self.sample_rate)[0]
                )

                spectral_rolloff = np.mean(
                    librosa.feature.spectral_rolloff(y=audio_data, sr=self.sample_rate)[0]
                )

                mfccs = librosa.feature.mfcc(y=audio_data, sr=self.sample_rate, n_mfcc=13)
                mfcc_mean = np.mean(mfccs, axis=1)

                spectral_features.append(
                    {
                        "index": i,
                        "centroid": spectral_centroid,
                        "rolloff": spectral_rolloff,
                        "mfcc_mean": mfcc_mean,
                        "vocab_text": (
                            getattr(pair.vocabulary_entry, "english", f"Entry {i}")
                            if hasattr(pair, "vocabulary_entry")
                            else f"Pair {i}"
                        ),
                    }
                )

            except Exception as e:
                logger.warning(f"Error calculating spectral features for pair {i}: {e}")
                continue

        if len(spectral_features) < 3:  # Need at least 3 samples for outlier detection
            return issues

        # Detect spectral outliers
        centroids = [f["centroid"] for f in spectral_features]
        rolloffs = [f["rolloff"] for f in spectral_features]

        centroid_mean = np.mean(centroids)
        centroid_std = np.std(centroids)
        rolloff_mean = np.mean(rolloffs)
        rolloff_std = np.std(rolloffs)

        for feature in spectral_features:
            centroid_z = abs(feature["centroid"] - centroid_mean) / (centroid_std + 1e-8)
            rolloff_z = abs(feature["rolloff"] - rolloff_mean) / (rolloff_std + 1e-8)

            # Flag as outlier if z-score > 2.5 for either feature
            if centroid_z > 2.5 or rolloff_z > 2.5:
                spectral_outliers.append(
                    {
                        "index": feature["index"],
                        "vocab_text": feature["vocab_text"],
                        "centroid_z": centroid_z,
                        "rolloff_z": rolloff_z,
                    }
                )

        if spectral_outliers:
            affected_items = [
                f"{o['vocab_text']} (spectral anomaly score: {max(o['centroid_z'], o['rolloff_z']):.2f})"
                for o in spectral_outliers
            ]

            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.CORRUPTION,
                    severity=IssueSeverity.WARNING,
                    affected_items=affected_items,
                    description=f"Found {len(spectral_outliers)} pairs with unusual spectral characteristics",
                    suggested_fix="Review flagged pairs for audio quality issues or potential misalignment",
                    confidence=0.6,
                    context={
                        "outliers": spectral_outliers,
                        "centroid_stats": {"mean": centroid_mean, "std": centroid_std},
                        "rolloff_stats": {"mean": rolloff_mean, "std": rolloff_std},
                    },
                )
            )

        return issues

    def _detect_potential_swaps(self, aligned_pairs: List[AlignedPair]) -> List[ValidationIssue]:
        """Detect potential swaps between audio clips and vocabulary terms."""
        issues = []

        if len(aligned_pairs) < 2:
            return issues

        # This is a simplified heuristic - in practice, you might use more sophisticated
        # cross-correlation or similarity measures
        potential_swaps = []

        # Look for pairs where confidence is very low and might benefit from swapping
        low_confidence_pairs = []
        for i, pair in enumerate(aligned_pairs):
            if hasattr(pair, "alignment_confidence") and pair.alignment_confidence < 0.4:
                low_confidence_pairs.append((i, pair))

        # Check if swapping any low-confidence pairs might improve alignment
        # This is a placeholder for more sophisticated swap detection logic
        if len(low_confidence_pairs) >= 2:
            potential_swaps.extend(
                [
                    f"Pairs {pair1[0]} and {pair2[0]} may benefit from audio swap verification"
                    for pair1, pair2 in zip(low_confidence_pairs[::2], low_confidence_pairs[1::2])
                ]
            )

        if potential_swaps:
            issues.append(
                self.create_validation_issue(
                    issue_type=IssueType.MISALIGNMENT,
                    severity=IssueSeverity.INFO,
                    affected_items=potential_swaps,
                    description=f"Detected {len(potential_swaps)} potential audio-vocabulary swaps",
                    suggested_fix="Manually verify the alignment of flagged pairs and consider swapping if appropriate",
                    confidence=0.4,
                    context={
                        "detection_method": "low_confidence_heuristic",
                        "low_confidence_threshold": 0.4,
                    },
                )
            )

        return issues

    def _analyze_misalignment_corruption(self, aligned_pairs: List[AlignedPair]) -> Dict[str, Any]:
        """Analyze misalignment-specific corruption patterns."""
        analysis = {
            "total_pairs": len(aligned_pairs),
            "low_confidence_count": 0,
            "duration_mismatches": 0,
            "spectral_outliers": 0,
            "potential_swaps": 0,
            "confidence_distribution": {},
        }

        confidences = []
        for pair in aligned_pairs:
            if hasattr(pair, "alignment_confidence"):
                confidence = pair.alignment_confidence
                confidences.append(confidence)
                if confidence < 0.5:
                    analysis["low_confidence_count"] += 1

        if confidences:
            analysis["confidence_distribution"] = {
                "mean": np.mean(confidences),
                "std": np.std(confidences),
                "min": np.min(confidences),
                "max": np.max(confidences),
                "percentiles": {
                    "25": np.percentile(confidences, 25),
                    "50": np.percentile(confidences, 50),
                    "75": np.percentile(confidences, 75),
                },
            }

        return analysis

    def _analyze_audio_corruption(self, audio_segments: List[AudioSegment]) -> Dict[str, Any]:
        """Analyze audio-specific corruption patterns."""
        analysis = {
            "total_segments": len(audio_segments),
            "silent_segments": 0,
            "duration_anomalies": 0,
            "spectral_anomalies": 0,
            "empty_segments": 0,
        }

        durations = []
        for segment in audio_segments:
            if hasattr(segment, "audio_data") and isinstance(segment.audio_data, np.ndarray):
                if len(segment.audio_data) == 0:
                    analysis["empty_segments"] += 1
                    continue

                # Check for silence
                silence_issues = self._detect_silence_in_array(segment.audio_data, "temp")
                if silence_issues:
                    analysis["silent_segments"] += 1

                # Track duration
                duration = len(segment.audio_data) / self.sample_rate
                durations.append(duration)

        if durations:
            mean_duration = np.mean(durations)
            std_duration = np.std(durations)

            # Count duration anomalies
            for duration in durations:
                if abs(duration - mean_duration) > 2 * std_duration:
                    analysis["duration_anomalies"] += 1

        return analysis

    def _analyze_text_corruption(self, vocabulary_entries: List[VocabularyEntry]) -> Dict[str, Any]:
        """Analyze text-specific corruption patterns."""
        analysis = {
            "total_entries": len(vocabulary_entries),
            "empty_entries": 0,
            "duplicate_entries": 0,
            "encoding_issues": 0,
            "suspicious_entries": 0,
        }

        seen_entries = set()
        for entry in vocabulary_entries:
            if not hasattr(entry, "english") or not hasattr(entry, "cantonese"):
                continue

            # Check for empty entries
            if self._is_empty_entry(entry):
                analysis["empty_entries"] += 1
                continue

            # Check for duplicates
            entry_key = (entry.english.strip().lower(), entry.cantonese.strip())
            if entry_key in seen_entries:
                analysis["duplicate_entries"] += 1
            else:
                seen_entries.add(entry_key)

            # Check for encoding issues
            if self._has_encoding_issues(entry.english) or self._has_encoding_issues(
                entry.cantonese
            ):
                analysis["encoding_issues"] += 1

            # Check for suspicious patterns
            if self._is_suspicious_entry(entry):
                analysis["suspicious_entries"] += 1

        return analysis

    def _generate_corruption_corrections(self, analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate specific corrections for each type of detected corruption."""
        corrections = {}

        # Misalignment corrections
        if "misalignment" in analysis["corruption_types"]:
            misalignment = analysis["corruption_types"]["misalignment"]
            corrections["misalignment"] = []

            if misalignment["low_confidence_count"] > 0:
                corrections["misalignment"].append(
                    f"Review {misalignment['low_confidence_count']} low-confidence alignments manually"
                )

            if misalignment["duration_mismatches"] > 0:
                corrections["misalignment"].append(
                    "Adjust audio segmentation parameters to better match vocabulary length"
                )

        # Audio corrections
        if "audio" in analysis["corruption_types"]:
            audio = analysis["corruption_types"]["audio"]
            corrections["audio"] = []

            if audio["silent_segments"] > 0:
                corrections["audio"].append(
                    f"Re-record or filter {audio['silent_segments']} silent audio segments"
                )

            if audio["empty_segments"] > 0:
                corrections["audio"].append(
                    f"Investigate {audio['empty_segments']} empty audio segments"
                )

        # Text corrections
        if "text" in analysis["corruption_types"]:
            text = analysis["corruption_types"]["text"]
            corrections["text"] = []

            if text["empty_entries"] > 0:
                corrections["text"].append(
                    f"Complete or remove {text['empty_entries']} empty vocabulary entries"
                )

            if text["duplicate_entries"] > 0:
                corrections["text"].append(
                    f"Remove or verify {text['duplicate_entries']} duplicate entries"
                )

            if text["encoding_issues"] > 0:
                corrections["text"].append(
                    f"Fix encoding for {text['encoding_issues']} entries with character issues"
                )

        return corrections
