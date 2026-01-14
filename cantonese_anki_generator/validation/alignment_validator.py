"""
Alignment validation implementation for the validation system.

Provides multi-metric confidence calculation for term-audio pairs, threshold-based
flagging for low-confidence alignments, and cross-verification using multiple
validation methods to ensure accurate term-audio pairing.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import logging
import numpy as np

from .base import AlignmentValidator as BaseAlignmentValidator

# Import speech verification for semantic validation
try:
    from ..audio.speech_verification import WhisperVerifier, WHISPER_AVAILABLE
    SPEECH_VERIFICATION_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    SPEECH_VERIFICATION_AVAILABLE = False
from .models import (
    ValidationResult,
    ValidationIssue,
    AlignmentValidationResult,
    ValidationCheckpoint,
    IssueType,
    IssueSeverity,
)
from .config import ValidationConfig
from ..models import VocabularyEntry, AudioSegment, AlignedPair


logger = logging.getLogger(__name__)


class AlignmentValidator(BaseAlignmentValidator):
    """
    Validates alignment between vocabulary terms and audio segments.

    Implements multi-metric confidence calculation, threshold-based flagging,
    cross-verification mechanisms, and misalignment detection with detailed
    reporting for alignment issues.
    """

    def __init__(self, config: ValidationConfig):
        """Initialize the alignment validator with configuration."""
        super().__init__(config)
        self._validation_methods = [
            "duration_consistency_check",
            "timing_overlap_analysis",
            "confidence_score_calculation",
            "cross_verification_scoring",
            "threshold_based_flagging",
            "misalignment_detection",
            "semantic_verification",  # NEW: Semantic validation using Whisper
        ]

        # Initialize speech verifier if available
        self._speech_verifier = None
        if SPEECH_VERIFICATION_AVAILABLE and WHISPER_AVAILABLE:
            try:
                self._speech_verifier = WhisperVerifier(model_size="base")
                logger.info("Speech verifier initialized for semantic validation")
            except Exception as e:
                logger.warning(f"Failed to initialize speech verifier: {e}")
                self._speech_verifier = None

        # Confidence calculation weights for different metrics
        self._confidence_weights = {
            "timing_overlap": 0.25,      # Reduced from 0.35
            "duration_consistency": 0.20, # Reduced from 0.25
            "audio_quality": 0.15,       # Reduced from 0.20
            "vocabulary_confidence": 0.15, # Reduced from 0.20
            "semantic_verification": 0.25, # NEW: Semantic matching weight
        }

        # Thresholds for alignment validation
        self._thresholds = {
            "min_confidence": config.thresholds.alignment_confidence_min,
            "good_confidence": 0.8,  # Fixed threshold for good confidence
            "min_timing_overlap": 0.5,  # Minimum 50% timing overlap
            "max_duration_ratio": 3.0,  # Max 3:1 duration ratio
            "min_audio_quality": 0.3,  # Minimum audio quality score
        }

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Perform alignment validation on term-audio pairs.

        Args:
            data: Dictionary containing 'aligned_pairs' or individual pair data

        Returns:
            ValidationResult: Complete validation result with issues and recommendations
        """
        if not self.is_enabled():
            return self._create_disabled_result()

        try:
            # Extract aligned pairs from data
            aligned_pairs = data.get("aligned_pairs", [])

            # If single pair validation, wrap in list
            if "term_audio_pair" in data:
                term_audio_pair = data["term_audio_pair"]
                aligned_pairs = [
                    AlignedPair(
                        vocabulary_entry=term_audio_pair[0],
                        audio_segment=term_audio_pair[1],
                        alignment_confidence=0.0,  # Will be calculated
                        audio_file_path="",
                    )
                ]

            if not aligned_pairs:
                return self._create_no_data_result()

            # Validate each alignment pair
            validation_results = []
            issues = []
            recommendations = []

            for pair in aligned_pairs:
                # Calculate confidence score using multiple metrics
                confidence_score = self.calculate_confidence_score(pair)

                # Update pair confidence if it was initially 0
                if pair.alignment_confidence == 0.0:
                    pair.alignment_confidence = confidence_score

                # Detect misalignment issues
                misalignment_issues = self.detect_misalignment(pair)
                issues.extend(misalignment_issues)

                # Perform cross-verification
                cross_verification_score = self.cross_verify_alignment(pair)

                # Create individual alignment validation result
                alignment_result = AlignmentValidationResult(
                    term_audio_pair=(pair.vocabulary_entry, pair.audio_segment),
                    alignment_confidence=confidence_score,
                    validation_methods=self._get_validation_method_scores(pair),
                    is_valid=confidence_score >= self._thresholds["min_confidence"],
                    detected_issues=[issue.description for issue in misalignment_issues],
                    cross_verification_score=cross_verification_score,
                )

                validation_results.append(alignment_result)

            # Detect incorrectly paired terms across all pairs
            incorrect_pairing_issues = self.detect_incorrectly_paired_terms(aligned_pairs)
            issues.extend(incorrect_pairing_issues)

            # Generate overall recommendations
            recommendations.extend(self._generate_alignment_recommendations(validation_results))

            # Filter pairs for final package inclusion
            valid_pairs, invalid_pairs = self.filter_invalid_pairs(aligned_pairs)

            # Determine overall success
            valid_alignments = sum(1 for result in validation_results if result.is_valid)
            success_rate = valid_alignments / len(validation_results) if validation_results else 0.0
            overall_success = success_rate >= 0.8  # 80% success rate threshold

            # Calculate overall confidence score
            if validation_results:
                overall_confidence = sum(r.alignment_confidence for r in validation_results) / len(
                    validation_results
                )
            else:
                overall_confidence = 0.0

            # Create final validation result
            result = ValidationResult(
                checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
                success=overall_success,
                confidence_score=overall_confidence,
                issues=issues,
                recommendations=recommendations,
                validation_methods_used=self._validation_methods,
                context={
                    "alignment_results": validation_results,
                    "success_rate": success_rate,
                    "total_pairs": len(validation_results),
                    "valid_pairs": valid_alignments,
                    "filtered_valid_pairs": len(valid_pairs),
                    "filtered_invalid_pairs": len(invalid_pairs),
                    "alignment_report": self.generate_alignment_report(aligned_pairs),
                },
            )

            return result

        except Exception as e:
            logger.error(f"Alignment validation failed: {e}")
            return self._create_error_result(str(e))

    def calculate_confidence_score(self, term_audio_pair: Any) -> float:
        """
        Calculate multi-metric confidence score for a term-audio pairing.

        Args:
            term_audio_pair: AlignedPair or tuple of (VocabularyEntry, AudioSegment)

        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        if isinstance(term_audio_pair, AlignedPair):
            vocab_entry = term_audio_pair.vocabulary_entry
            audio_segment = term_audio_pair.audio_segment
        else:
            vocab_entry, audio_segment = term_audio_pair

        # Calculate individual metric scores
        timing_score = self._calculate_timing_overlap_score(vocab_entry, audio_segment)
        duration_score = self._calculate_duration_consistency_score(vocab_entry, audio_segment)
        audio_quality_score = self._calculate_audio_quality_score(audio_segment)
        vocab_confidence_score = (
            vocab_entry.confidence if hasattr(vocab_entry, "confidence") else 1.0
        )
        
        # NEW: Calculate semantic verification score using Whisper
        semantic_score = self._calculate_semantic_verification_score(vocab_entry, audio_segment)

        # Weighted combination of all metrics
        confidence_score = (
            self._confidence_weights["timing_overlap"] * timing_score
            + self._confidence_weights["duration_consistency"] * duration_score
            + self._confidence_weights["audio_quality"] * audio_quality_score
            + self._confidence_weights["vocabulary_confidence"] * vocab_confidence_score
            + self._confidence_weights["semantic_verification"] * semantic_score
        )

        # Apply penalties for specific issues
        confidence_score = self._apply_confidence_penalties(
            confidence_score, vocab_entry, audio_segment
        )

        return max(0.0, min(1.0, confidence_score))

    def detect_misalignment(self, term_audio_pair: Any) -> List[ValidationIssue]:
        """
        Detect misalignment issues in term-audio pairings.

        Args:
            term_audio_pair: AlignedPair or tuple of (VocabularyEntry, AudioSegment)

        Returns:
            List[ValidationIssue]: List of detected misalignment issues
        """
        issues = []

        if isinstance(term_audio_pair, AlignedPair):
            vocab_entry = term_audio_pair.vocabulary_entry
            audio_segment = term_audio_pair.audio_segment
            pair_confidence = term_audio_pair.alignment_confidence
        else:
            vocab_entry, audio_segment = term_audio_pair
            pair_confidence = self.calculate_confidence_score(term_audio_pair)

        # Check for low confidence alignment
        if pair_confidence < self._thresholds["min_confidence"]:
            severity = IssueSeverity.ERROR if pair_confidence < 0.3 else IssueSeverity.WARNING

            issue = self.create_validation_issue(
                issue_type=IssueType.ALIGNMENT_CONFIDENCE,
                severity=severity,
                affected_items=[
                    f"term:{vocab_entry.english}",
                    f"segment:{audio_segment.segment_id}",
                ],
                description=(
                    f"Low alignment confidence ({pair_confidence:.2f}) for term '{vocab_entry.english}' "
                    f"-> '{vocab_entry.cantonese}' with audio segment {audio_segment.segment_id}"
                ),
                suggested_fix=(
                    "Review audio segmentation boundaries, check for background noise, "
                    "or verify vocabulary term pronunciation"
                ),
                confidence=1.0 - pair_confidence,
                context={
                    "alignment_confidence": pair_confidence,
                    "english_term": vocab_entry.english,
                    "cantonese_term": vocab_entry.cantonese,
                    "segment_id": audio_segment.segment_id,
                    "segment_duration": audio_segment.end_time - audio_segment.start_time,
                },
            )
            issues.append(issue)

        # Check for duration anomalies
        segment_duration = audio_segment.end_time - audio_segment.start_time
        expected_duration = self._estimate_expected_duration(vocab_entry)

        if expected_duration > 0:
            duration_ratio = segment_duration / expected_duration

            if duration_ratio > self._thresholds["max_duration_ratio"] or duration_ratio < (
                1.0 / self._thresholds["max_duration_ratio"]
            ):
                issue = self.create_validation_issue(
                    issue_type=IssueType.DURATION_ANOMALY,
                    severity=IssueSeverity.WARNING,
                    affected_items=[
                        f"term:{vocab_entry.english}",
                        f"segment:{audio_segment.segment_id}",
                    ],
                    description=(
                        f"Duration anomaly detected: segment duration {segment_duration:.2f}s "
                        f"vs expected {expected_duration:.2f}s (ratio: {duration_ratio:.2f})"
                    ),
                    suggested_fix=(
                        "Check audio segmentation boundaries or verify if term requires "
                        "longer/shorter pronunciation time"
                    ),
                    confidence=0.8,
                    context={
                        "segment_duration": segment_duration,
                        "expected_duration": expected_duration,
                        "duration_ratio": duration_ratio,
                    },
                )
                issues.append(issue)

        # Check for silent or low-quality audio
        if hasattr(audio_segment, "audio_data") and audio_segment.audio_data is not None:
            audio_quality = self._calculate_audio_quality_score(audio_segment)

            if audio_quality < self._thresholds["min_audio_quality"]:
                issue = self.create_validation_issue(
                    issue_type=IssueType.SILENT_AUDIO,
                    severity=IssueSeverity.ERROR,
                    affected_items=[f"segment:{audio_segment.segment_id}"],
                    description=(
                        f"Poor audio quality detected (score: {audio_quality:.2f}) "
                        f"for segment {audio_segment.segment_id}"
                    ),
                    suggested_fix=(
                        "Check for silent audio, background noise, or audio processing issues. "
                        "Consider re-recording or adjusting segmentation boundaries."
                    ),
                    confidence=1.0 - audio_quality,
                    context={
                        "audio_quality_score": audio_quality,
                        "segment_id": audio_segment.segment_id,
                    },
                )
                issues.append(issue)

        return issues

    def cross_verify_alignment(self, term_audio_pair: Any) -> float:
        """
        Perform cross-verification of alignment using multiple methods.

        Args:
            term_audio_pair: AlignedPair or tuple of (VocabularyEntry, AudioSegment)

        Returns:
            float: Cross-verification score between 0.0 and 1.0
        """
        if isinstance(term_audio_pair, AlignedPair):
            vocab_entry = term_audio_pair.vocabulary_entry
            audio_segment = term_audio_pair.audio_segment
        else:
            vocab_entry, audio_segment = term_audio_pair

        # Method 1: Duration-based verification
        duration_verification = self._verify_by_duration(vocab_entry, audio_segment)

        # Method 2: Audio energy pattern verification
        energy_verification = self._verify_by_energy_pattern(vocab_entry, audio_segment)

        # Method 3: Phonetic consistency verification (simplified)
        phonetic_verification = self._verify_by_phonetic_consistency(vocab_entry, audio_segment)

        # Method 4: Contextual verification (position in sequence)
        contextual_verification = self._verify_by_context(vocab_entry, audio_segment)

        # Combine verification scores with weights
        verification_weights = {
            "duration": 0.3,
            "energy": 0.25,
            "phonetic": 0.25,
            "contextual": 0.2,
        }

        cross_verification_score = (
            verification_weights["duration"] * duration_verification
            + verification_weights["energy"] * energy_verification
            + verification_weights["phonetic"] * phonetic_verification
            + verification_weights["contextual"] * contextual_verification
        )

        return max(0.0, min(1.0, cross_verification_score))

    def get_validation_methods(self) -> List[str]:
        """Get list of validation methods used by this validator."""
        return self._validation_methods.copy()

    def filter_invalid_pairs(
        self, aligned_pairs: List[AlignedPair]
    ) -> Tuple[List[AlignedPair], List[AlignedPair]]:
        """
        Filter aligned pairs to exclude invalid pairs from final package.

        Args:
            aligned_pairs: List of aligned pairs to filter

        Returns:
            Tuple of (valid_pairs, invalid_pairs) for separate processing
        """
        valid_pairs = []
        invalid_pairs = []

        for pair in aligned_pairs:
            # Calculate confidence if not already set
            if pair.alignment_confidence == 0.0:
                pair.alignment_confidence = self.calculate_confidence_score(pair)

            # Detect misalignment issues
            misalignment_issues = self.detect_misalignment(pair)

            # Determine if pair should be filtered out
            should_filter = self._should_filter_pair(pair, misalignment_issues)

            if should_filter:
                invalid_pairs.append(pair)
                logger.info(
                    f"Filtered out invalid pair: '{pair.vocabulary_entry.english}' -> "
                    f"'{pair.vocabulary_entry.cantonese}' (confidence: {pair.alignment_confidence:.2f})"
                )
            else:
                valid_pairs.append(pair)

        logger.info(
            f"Alignment filtering: {len(valid_pairs)} valid pairs, {len(invalid_pairs)} filtered out"
        )

        return valid_pairs, invalid_pairs

    def generate_alignment_report(self, aligned_pairs: List[AlignedPair]) -> Dict[str, Any]:
        """
        Generate detailed alignment report with confidence scores and issues.

        Args:
            aligned_pairs: List of aligned pairs to analyze

        Returns:
            Dict containing detailed alignment analysis and recommendations
        """
        if not aligned_pairs:
            return {
                "total_pairs": 0,
                "valid_pairs": 0,
                "invalid_pairs": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "issues_summary": {},
                "recommendations": ["No alignment data available"],
            }

        # Calculate statistics
        total_pairs = len(aligned_pairs)
        confidence_scores = []
        all_issues = []

        for pair in aligned_pairs:
            # Ensure confidence is calculated
            if pair.alignment_confidence == 0.0:
                pair.alignment_confidence = self.calculate_confidence_score(pair)

            confidence_scores.append(pair.alignment_confidence)

            # Collect all issues
            issues = self.detect_misalignment(pair)
            all_issues.extend(issues)

        # Calculate confidence distribution
        confidence_distribution = {
            "excellent": sum(1 for c in confidence_scores if c >= 0.9),
            "good": sum(1 for c in confidence_scores if 0.7 <= c < 0.9),
            "acceptable": sum(1 for c in confidence_scores if 0.5 <= c < 0.7),
            "poor": sum(1 for c in confidence_scores if 0.3 <= c < 0.5),
            "critical": sum(1 for c in confidence_scores if c < 0.3),
        }

        # Categorize issues
        issues_summary = {}
        for issue in all_issues:
            issue_type = issue.issue_type.value
            if issue_type not in issues_summary:
                issues_summary[issue_type] = 0
            issues_summary[issue_type] += 1

        # Count valid vs invalid pairs
        valid_pairs = sum(1 for c in confidence_scores if c >= self._thresholds["min_confidence"])
        invalid_pairs = total_pairs - valid_pairs

        # Generate recommendations
        recommendations = self._generate_detailed_recommendations(
            confidence_scores, all_issues, confidence_distribution
        )

        return {
            "total_pairs": total_pairs,
            "valid_pairs": valid_pairs,
            "invalid_pairs": invalid_pairs,
            "average_confidence": sum(confidence_scores) / len(confidence_scores),
            "confidence_distribution": confidence_distribution,
            "issues_summary": issues_summary,
            "recommendations": recommendations,
            "detailed_issues": [
                {
                    "type": issue.issue_type.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "affected_items": issue.affected_items,
                    "suggested_fix": issue.suggested_fix,
                    "confidence": issue.confidence,
                }
                for issue in all_issues
            ],
        }

    def detect_incorrectly_paired_terms(
        self, aligned_pairs: List[AlignedPair]
    ) -> List[ValidationIssue]:
        """
        Detect when audio clips are assigned to wrong vocabulary terms.

        Args:
            aligned_pairs: List of aligned pairs to analyze

        Returns:
            List[ValidationIssue]: Issues related to incorrect pairing
        """
        issues = []

        if len(aligned_pairs) < 2:
            return issues  # Need at least 2 pairs for comparison

        # Sort pairs by audio timing for sequence analysis
        sorted_pairs = sorted(aligned_pairs, key=lambda p: p.audio_segment.start_time)

        for i, current_pair in enumerate(sorted_pairs):
            # Check for timing inconsistencies with neighboring pairs
            timing_issues = self._detect_timing_inconsistencies(current_pair, sorted_pairs, i)
            issues.extend(timing_issues)

            # Check for duration outliers that might indicate wrong pairing
            duration_issues = self._detect_duration_outliers(current_pair, sorted_pairs)
            issues.extend(duration_issues)

            # Check for confidence outliers in sequence
            confidence_issues = self._detect_confidence_outliers(current_pair, sorted_pairs, i)
            issues.extend(confidence_issues)

            # NEW: Check for semantic misalignment patterns
            semantic_issues = self._detect_semantic_misalignment(current_pair, sorted_pairs, i)
            issues.extend(semantic_issues)

        return issues

    def _detect_semantic_misalignment(
        self, current_pair: AlignedPair, all_pairs: List[AlignedPair], index: int
    ) -> List[ValidationIssue]:
        """
        Detect semantic misalignment using speech-to-text verification.
        
        This is the key method that detects when audio content doesn't match
        the vocabulary term (e.g., "flowers" having audio for "buy some").
        """
        issues = []
        
        if not self._speech_verifier:
            return issues  # Skip if speech verification not available
        
        try:
            vocab_entry = current_pair.vocabulary_entry
            audio_segment = current_pair.audio_segment
            
            # Skip if no audio data
            if not hasattr(audio_segment, "audio_data") or audio_segment.audio_data is None:
                return issues
            
            # Transcribe the audio segment
            transcription_result = self._speech_verifier.transcribe_audio_segment(
                audio_segment.audio_data, 22050  # Assume standard sample rate
            )
            
            # Compare transcription with expected Cantonese text
            comparison_result = self._speech_verifier.compare_transcription_with_expected(
                transcription_result['text'], vocab_entry.cantonese
            )
            
            # Check for semantic mismatch
            if not comparison_result['is_match'] or comparison_result['similarity'] < 0.6:
                # Use INFO/WARNING instead of ERROR/CRITICAL for semantic mismatches
                # This allows processing to continue while flagging issues for user review
                if comparison_result['similarity'] < 0.2:
                    severity = IssueSeverity.WARNING  # Changed from CRITICAL
                else:
                    severity = IssueSeverity.INFO     # Changed from WARNING
                
                # Get Jyutping conversion for display
                transcribed_jyutping = comparison_result.get('transcribed_jyutping', '')
                
                issue = self.create_validation_issue(
                    issue_type=IssueType.MISALIGNMENT,
                    severity=severity,
                    affected_items=[
                        f"term:{vocab_entry.english}",
                        f"segment:{audio_segment.segment_id}",
                    ],
                    description=(
                        f"SEMANTIC MISMATCH: '{vocab_entry.english}' → '{vocab_entry.cantonese}' "
                        f"has audio that transcribes to '{transcription_result['text']}' → '{transcribed_jyutping}' "
                        f"(similarity: {comparison_result['similarity']*100:.1f}%)"
                    ),
                    suggested_fix=(
                        f"The audio for '{vocab_entry.english}' appears to contain different content. "
                        f"Expected: '{vocab_entry.cantonese}', but audio transcribes to: '{transcription_result['text']}' → '{transcribed_jyutping}'. "
                        f"The system will attempt dynamic per-term alignment correction. "
                        f"If issues persist, check if vocabulary order matches audio sequence."
                    ),
                    confidence=1.0 - comparison_result['similarity'],
                    context={
                        "expected_cantonese": vocab_entry.cantonese,
                        "transcribed_text": transcription_result['text'],
                        "transcribed_jyutping": transcribed_jyutping,
                        "similarity_score": comparison_result['similarity'],
                        "whisper_confidence": transcription_result['confidence'],
                        "semantic_match": comparison_result['is_match'],
                    },
                )
                issues.append(issue)
                
                # Show both Chinese and Jyutping conversion for transparency
                transcribed_jyutping = comparison_result.get('transcribed_jyutping', '')
                logger.warning(
                    f"Semantic mismatch detected: '{vocab_entry.english}' expected '{vocab_entry.cantonese}' "
                    f"but got '{transcription_result['text']}' → '{transcribed_jyutping}' (similarity: {comparison_result['similarity']*100:.1f}%)"
                )
                
                # ALWAYS log the conversion for user visibility
                if transcribed_jyutping and transcribed_jyutping != transcription_result['text']:
                    logger.info(f"Chinese-to-Jyutping conversion: '{transcription_result['text']}' → '{transcribed_jyutping}'")
                else:
                    logger.info(f"Audio transcription: '{transcription_result['text']}' (no Jyutping conversion available)")
        
        except Exception as e:
            logger.debug(f"Failed semantic verification for pair {index}: {e}")
            # Don't create an issue for verification failures, just log
        
        return issues

    def _calculate_semantic_verification_score(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """
        Calculate semantic verification score using speech-to-text matching.
        
        This is the core semantic validation that detects content mismatches.
        """
        if not self._speech_verifier:
            return 0.7  # Neutral score if speech verification not available
        
        try:
            # Skip if no audio data
            if not hasattr(audio_segment, "audio_data") or audio_segment.audio_data is None:
                return 0.5
            
            # Transcribe the audio segment
            transcription_result = self._speech_verifier.transcribe_audio_segment(
                audio_segment.audio_data, 22050  # Assume standard sample rate
            )
            
            # Compare transcription with expected Cantonese text
            comparison_result = self._speech_verifier.compare_transcription_with_expected(
                transcription_result['text'], vocab_entry.cantonese
            )
            
            # Combine Whisper confidence with semantic similarity
            whisper_confidence = transcription_result['confidence']
            semantic_similarity = comparison_result['similarity']
            
            # Weight semantic similarity more heavily
            semantic_score = (0.3 * whisper_confidence) + (0.7 * semantic_similarity)
            
            logger.debug(
                f"Semantic score for '{vocab_entry.english}': {semantic_score:.2f} "
                f"(whisper: {whisper_confidence:.2f}, similarity: {semantic_similarity:.2f})"
            )
            
            return max(0.0, min(1.0, semantic_score))
        
        except Exception as e:
            logger.debug(f"Failed to calculate semantic score: {e}")
            return 0.5  # Neutral score on failure

    def _should_filter_pair(self, pair: AlignedPair, issues: List[ValidationIssue]) -> bool:
        """
        Determine if a pair should be filtered out based on validation criteria.

        Args:
            pair: Aligned pair to evaluate
            issues: List of validation issues for this pair

        Returns:
            bool: True if pair should be filtered out
        """
        # Filter based on confidence threshold
        if pair.alignment_confidence < self._thresholds["min_confidence"]:
            return True

        # Filter based on critical issues
        critical_issues = [issue for issue in issues if issue.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            return True

        # Filter based on multiple error-level issues
        error_issues = [issue for issue in issues if issue.severity == IssueSeverity.ERROR]
        if len(error_issues) >= 2:  # Multiple errors indicate serious problems
            return True

        # Filter based on audio quality
        if hasattr(pair.audio_segment, "audio_data") and pair.audio_segment.audio_data is not None:
            audio_quality = self._calculate_audio_quality_score(pair.audio_segment)
            if audio_quality < self._thresholds["min_audio_quality"]:
                return True

        # Filter based on cross-verification score
        cross_verification_score = self.cross_verify_alignment(pair)
        if cross_verification_score < 0.3:  # Very low cross-verification
            return True

        return False

    def _detect_timing_inconsistencies(
        self, current_pair: AlignedPair, all_pairs: List[AlignedPair], index: int
    ) -> List[ValidationIssue]:
        """Detect timing inconsistencies that might indicate incorrect pairing."""
        issues = []

        current_segment = current_pair.audio_segment
        current_vocab = current_pair.vocabulary_entry

        # Check for overlapping segments (shouldn't happen in good alignment)
        for other_pair in all_pairs:
            if other_pair == current_pair:
                continue

            other_segment = other_pair.audio_segment

            # Check for significant overlap
            overlap_start = max(current_segment.start_time, other_segment.start_time)
            overlap_end = min(current_segment.end_time, other_segment.end_time)

            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                current_duration = current_segment.end_time - current_segment.start_time

                # If overlap is more than 50% of current segment, it's problematic
                if overlap_duration > current_duration * 0.5:
                    issue = self.create_validation_issue(
                        issue_type=IssueType.MISALIGNMENT,
                        severity=IssueSeverity.ERROR,
                        affected_items=[
                            f"term:{current_vocab.english}",
                            f"segment:{current_segment.segment_id}",
                            f"overlapping_segment:{other_segment.segment_id}",
                        ],
                        description=(
                            f"Significant timing overlap detected between segments "
                            f"{current_segment.segment_id} and {other_segment.segment_id} "
                            f"({overlap_duration:.2f}s overlap)"
                        ),
                        suggested_fix=(
                            "Review audio segmentation boundaries to eliminate overlaps. "
                            "This may indicate incorrect term-audio pairing."
                        ),
                        confidence=0.9,
                        context={
                            "overlap_duration": overlap_duration,
                            "current_segment_duration": current_duration,
                            "overlap_percentage": (overlap_duration / current_duration) * 100,
                        },
                    )
                    issues.append(issue)

        return issues

    def _detect_duration_outliers(
        self, current_pair: AlignedPair, all_pairs: List[AlignedPair]
    ) -> List[ValidationIssue]:
        """Detect duration outliers that might indicate incorrect pairing."""
        issues = []

        if len(all_pairs) < 3:
            return issues  # Need sufficient data for outlier detection

        # Calculate duration statistics
        durations = [p.audio_segment.end_time - p.audio_segment.start_time for p in all_pairs]
        mean_duration = sum(durations) / len(durations)

        # Calculate standard deviation
        variance = sum((d - mean_duration) ** 2 for d in durations) / len(durations)
        std_deviation = variance**0.5

        current_duration = (
            current_pair.audio_segment.end_time - current_pair.audio_segment.start_time
        )

        # Check if current duration is an outlier (more than 2 standard deviations)
        if std_deviation > 0:
            z_score = abs(current_duration - mean_duration) / std_deviation

            if z_score > 2.0:  # Significant outlier
                severity = IssueSeverity.WARNING if z_score < 3.0 else IssueSeverity.ERROR

                issue = self.create_validation_issue(
                    issue_type=IssueType.DURATION_ANOMALY,
                    severity=severity,
                    affected_items=[
                        f"term:{current_pair.vocabulary_entry.english}",
                        f"segment:{current_pair.audio_segment.segment_id}",
                    ],
                    description=(
                        f"Duration outlier detected: segment {current_pair.audio_segment.segment_id} "
                        f"has duration {current_duration:.2f}s (z-score: {z_score:.2f}) "
                        f"vs mean {mean_duration:.2f}s"
                    ),
                    suggested_fix=(
                        "Review this segment for potential misalignment. "
                        "Consider if the audio boundaries are correct for this vocabulary term."
                    ),
                    confidence=min(0.9, z_score / 3.0),
                    context={
                        "duration": current_duration,
                        "mean_duration": mean_duration,
                        "z_score": z_score,
                        "std_deviation": std_deviation,
                    },
                )
                issues.append(issue)

        return issues

    def _detect_confidence_outliers(
        self, current_pair: AlignedPair, all_pairs: List[AlignedPair], index: int
    ) -> List[ValidationIssue]:
        """Detect confidence outliers in sequence that might indicate incorrect pairing."""
        issues = []

        # Look at neighboring pairs for confidence consistency
        window_size = 2  # Check 2 pairs before and after
        start_idx = max(0, index - window_size)
        end_idx = min(len(all_pairs), index + window_size + 1)

        neighbor_confidences = []
        for i in range(start_idx, end_idx):
            if i != index:
                neighbor_pair = all_pairs[i]
                if neighbor_pair.alignment_confidence == 0.0:
                    neighbor_pair.alignment_confidence = self.calculate_confidence_score(
                        neighbor_pair
                    )
                neighbor_confidences.append(neighbor_pair.alignment_confidence)

        if neighbor_confidences:
            avg_neighbor_confidence = sum(neighbor_confidences) / len(neighbor_confidences)
            current_confidence = current_pair.alignment_confidence

            # Check if current confidence is significantly lower than neighbors
            confidence_diff = avg_neighbor_confidence - current_confidence

            if confidence_diff > 0.4 and current_confidence < 0.6:  # Significant drop in confidence
                issue = self.create_validation_issue(
                    issue_type=IssueType.ALIGNMENT_CONFIDENCE,
                    severity=IssueSeverity.WARNING,
                    affected_items=[
                        f"term:{current_pair.vocabulary_entry.english}",
                        f"segment:{current_pair.audio_segment.segment_id}",
                    ],
                    description=(
                        f"Confidence outlier detected: segment {current_pair.audio_segment.segment_id} "
                        f"has confidence {current_confidence:.2f} vs neighbor average {avg_neighbor_confidence:.2f}"
                    ),
                    suggested_fix=(
                        "Review this alignment as it has significantly lower confidence than surrounding pairs. "
                        "May indicate incorrect term-audio pairing."
                    ),
                    confidence=confidence_diff,
                    context={
                        "current_confidence": current_confidence,
                        "neighbor_average": avg_neighbor_confidence,
                        "confidence_difference": confidence_diff,
                    },
                )
                issues.append(issue)

        return issues

    def _generate_detailed_recommendations(
        self,
        confidence_scores: List[float],
        issues: List[ValidationIssue],
        confidence_distribution: Dict[str, int],
    ) -> List[str]:
        """Generate detailed recommendations based on alignment analysis."""
        recommendations = []

        total_pairs = len(confidence_scores)
        if total_pairs == 0:
            return ["No alignment data available for analysis"]

        avg_confidence = sum(confidence_scores) / total_pairs

        # Overall quality assessment
        if avg_confidence < 0.5:
            recommendations.append(
                "CRITICAL: Average alignment confidence is very low. "
                "Consider re-recording audio or completely re-processing the alignment."
            )
        elif avg_confidence < 0.7:
            recommendations.append(
                "WARNING: Alignment quality is below optimal. "
                "Review segmentation parameters and audio quality."
            )

        # Confidence distribution recommendations
        critical_count = confidence_distribution.get("critical", 0)
        poor_count = confidence_distribution.get("poor", 0)

        if critical_count > 0:
            recommendations.append(
                f"URGENT: {critical_count} alignments have critical confidence issues. "
                "These should be manually reviewed or excluded from the final package."
            )

        if poor_count > total_pairs * 0.2:  # More than 20% poor alignments
            recommendations.append(
                f"WARNING: {poor_count} alignments have poor confidence. "
                "Consider adjusting alignment parameters or improving audio quality."
            )

        # Issue-specific recommendations
        issue_counts = {}
        for issue in issues:
            issue_type = issue.issue_type.value
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        if issue_counts.get("alignment_confidence", 0) > total_pairs * 0.3:
            recommendations.append(
                "Many alignments have confidence issues. "
                "Check audio segmentation boundaries and vocabulary accuracy."
            )

        if issue_counts.get("duration_anomaly", 0) > 0:
            recommendations.append(
                f"{issue_counts['duration_anomaly']} duration anomalies detected. "
                "Review audio segmentation for over/under-segmentation issues."
            )

        if issue_counts.get("silent_audio", 0) > 0:
            recommendations.append(
                f"{issue_counts['silent_audio']} silent or low-quality audio segments detected. "
                "Check for recording issues or background noise."
            )

        if issue_counts.get("misalignment", 0) > 0:
            recommendations.append(
                f"{issue_counts['misalignment']} potential misalignments detected. "
                "Review timing overlaps and sequence consistency."
            )

        # Success case
        if avg_confidence >= 0.8 and critical_count == 0 and poor_count <= total_pairs * 0.1:
            recommendations.append(
                "Alignment quality is good. Most pairs have high confidence scores."
            )

        return recommendations

    def _calculate_timing_overlap_score(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Calculate timing overlap score between expected and actual timing."""
        # For now, assume sequential alignment is expected
        # In a real implementation, this would use forced alignment timing

        # Simple heuristic: longer segments get slightly lower scores due to potential over-segmentation
        segment_duration = audio_segment.end_time - audio_segment.start_time

        if segment_duration < 0.5:  # Very short segments
            return 0.6
        elif segment_duration > 5.0:  # Very long segments
            return 0.7
        else:  # Normal duration segments
            return 0.9

    def _calculate_duration_consistency_score(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Calculate duration consistency score based on expected vs actual duration."""
        segment_duration = audio_segment.end_time - audio_segment.start_time
        expected_duration = self._estimate_expected_duration(vocab_entry)

        if expected_duration <= 0:
            return 0.5  # Neutral score if we can't estimate

        duration_ratio = min(segment_duration, expected_duration) / max(
            segment_duration, expected_duration
        )

        # Convert ratio to score (closer to 1.0 is better)
        return duration_ratio**0.5  # Square root to be less harsh on small differences

    def _calculate_audio_quality_score(self, audio_segment: AudioSegment) -> float:
        """Calculate audio quality score based on audio characteristics."""
        if not hasattr(audio_segment, "audio_data") or audio_segment.audio_data is None:
            return 0.5  # Neutral score if no audio data

        try:
            audio_data = audio_segment.audio_data

            # Calculate RMS energy
            rms_energy = np.sqrt(np.mean(audio_data**2))

            # Calculate zero crossing rate (indicator of speech vs silence)
            zero_crossings = np.sum(np.diff(np.sign(audio_data)) != 0)
            zcr = zero_crossings / len(audio_data)

            # Normalize scores
            energy_score = min(1.0, rms_energy * 10)  # Scale RMS to 0-1 range
            zcr_score = min(1.0, zcr * 100)  # Scale ZCR to 0-1 range

            # Combine scores (energy is more important)
            quality_score = 0.7 * energy_score + 0.3 * zcr_score

            return max(0.1, min(1.0, quality_score))

        except Exception as e:
            logger.warning(f"Error calculating audio quality score: {e}")
            return 0.5

    def _estimate_expected_duration(self, vocab_entry: VocabularyEntry) -> float:
        """Estimate expected duration for a vocabulary term."""
        # Simple heuristic based on character count and complexity
        cantonese_chars = len(vocab_entry.cantonese.strip())
        english_chars = len(vocab_entry.english.strip())

        # Base duration per character (in seconds)
        base_duration_per_char = 0.3

        # Cantonese typically takes longer to pronounce
        cantonese_duration = cantonese_chars * base_duration_per_char * 1.2

        # Add some buffer time
        estimated_duration = cantonese_duration + 0.5

        return max(0.5, min(5.0, estimated_duration))  # Clamp between 0.5-5 seconds

    def _apply_confidence_penalties(
        self, base_confidence: float, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Apply penalties to confidence score based on specific issues."""
        penalized_confidence = base_confidence

        # Penalty for very short segments (likely over-segmented)
        segment_duration = audio_segment.end_time - audio_segment.start_time
        if segment_duration < 0.3:
            penalized_confidence *= 0.8

        # Penalty for very long segments (likely under-segmented)
        if segment_duration > 8.0:
            penalized_confidence *= 0.7

        # Penalty for empty or very short vocabulary terms
        if len(vocab_entry.cantonese.strip()) == 0 or len(vocab_entry.english.strip()) == 0:
            penalized_confidence *= 0.5

        return penalized_confidence

    def _get_validation_method_scores(self, pair: AlignedPair) -> Dict[str, float]:
        """Get individual validation method scores for detailed reporting."""
        vocab_entry = pair.vocabulary_entry
        audio_segment = pair.audio_segment

        return {
            "timing_overlap": self._calculate_timing_overlap_score(vocab_entry, audio_segment),
            "duration_consistency": self._calculate_duration_consistency_score(
                vocab_entry, audio_segment
            ),
            "audio_quality": self._calculate_audio_quality_score(audio_segment),
            "vocabulary_confidence": (
                vocab_entry.confidence if hasattr(vocab_entry, "confidence") else 1.0
            ),
            "semantic_verification": self._calculate_semantic_verification_score(vocab_entry, audio_segment),
            "cross_verification": self.cross_verify_alignment(pair),
        }

    def _verify_by_duration(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Verify alignment by comparing expected vs actual duration."""
        return self._calculate_duration_consistency_score(vocab_entry, audio_segment)

    def _verify_by_energy_pattern(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Verify alignment by analyzing audio energy patterns."""
        # Simplified energy pattern analysis
        if not hasattr(audio_segment, "audio_data") or audio_segment.audio_data is None:
            return 0.5

        try:
            # Check if audio has reasonable energy distribution
            audio_data = audio_segment.audio_data
            energy_variance = np.var(audio_data)

            # Higher variance suggests more dynamic audio (speech vs silence)
            normalized_variance = min(1.0, energy_variance * 1000)

            return max(0.2, normalized_variance)

        except Exception:
            return 0.5

    def _verify_by_phonetic_consistency(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Verify alignment by checking phonetic consistency (simplified)."""
        # Simplified phonetic verification based on term complexity
        cantonese_complexity = len(vocab_entry.cantonese.strip())
        segment_duration = audio_segment.end_time - audio_segment.start_time

        # More complex terms should have longer durations
        expected_complexity_duration = cantonese_complexity * 0.4

        if segment_duration > 0:
            consistency_ratio = min(expected_complexity_duration, segment_duration) / max(
                expected_complexity_duration, segment_duration
            )
            return consistency_ratio**0.5

        return 0.5

    def _verify_by_context(
        self, vocab_entry: VocabularyEntry, audio_segment: AudioSegment
    ) -> float:
        """Verify alignment by checking contextual consistency."""
        # Simplified contextual verification
        # In a real implementation, this would check position in sequence, neighboring alignments, etc.

        # For now, give higher scores to segments with reasonable timing
        segment_duration = audio_segment.end_time - audio_segment.start_time

        if 0.5 <= segment_duration <= 3.0:  # Reasonable duration range
            return 0.9
        elif 0.3 <= segment_duration <= 5.0:  # Acceptable range
            return 0.7
        else:  # Outside reasonable range
            return 0.4

    def _generate_alignment_recommendations(
        self, validation_results: List[AlignmentValidationResult]
    ) -> List[str]:
        """Generate actionable recommendations based on alignment validation results."""
        recommendations = []

        if not validation_results:
            return ["No alignment data available for validation"]

        # Calculate statistics
        total_pairs = len(validation_results)
        valid_pairs = sum(1 for result in validation_results if result.is_valid)
        avg_confidence = sum(r.alignment_confidence for r in validation_results) / total_pairs

        # Generate recommendations based on statistics
        if valid_pairs / total_pairs < 0.5:
            recommendations.append(
                f"CRITICAL: Only {valid_pairs}/{total_pairs} alignments are valid. "
                "Consider re-recording audio or adjusting segmentation parameters."
            )
        elif valid_pairs / total_pairs < 0.8:
            recommendations.append(
                f"WARNING: {total_pairs - valid_pairs} alignments need attention. "
                "Review low-confidence pairings and consider manual verification."
            )

        if avg_confidence < 0.6:
            recommendations.append(
                f"Average alignment confidence is low ({avg_confidence:.2f}). "
                "Check audio quality, segmentation boundaries, and vocabulary accuracy."
            )

        # Specific recommendations for common issues
        low_confidence_count = sum(1 for r in validation_results if r.alignment_confidence < 0.5)
        if low_confidence_count > 0:
            recommendations.append(
                f"Review {low_confidence_count} low-confidence alignments. "
                "Consider manual verification or re-processing these segments."
            )

        return recommendations

    def _create_disabled_result(self) -> ValidationResult:
        """Create result for when validation is disabled."""
        return ValidationResult(
            checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
            success=True,
            confidence_score=1.0,
            issues=[],
            recommendations=["Alignment validation is disabled"],
            validation_methods_used=[],
        )

    def _create_no_data_result(self) -> ValidationResult:
        """Create result for when no alignment data is provided."""
        return ValidationResult(
            checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
            success=True,
            confidence_score=1.0,
            issues=[],
            recommendations=["No alignment data provided for validation"],
            validation_methods_used=[],
        )

    def _create_error_result(self, error_message: str) -> ValidationResult:
        """Create result for validation errors."""
        issue = self.create_validation_issue(
            issue_type=IssueType.CORRUPTION,
            severity=IssueSeverity.CRITICAL,
            affected_items=["alignment_validation_system"],
            description=f"Alignment validation failed: {error_message}",
            suggested_fix="Check input data format and validation configuration",
            confidence=1.0,
        )

        return ValidationResult(
            checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
            success=False,
            confidence_score=0.0,
            issues=[issue],
            recommendations=["Fix alignment validation system error before proceeding"],
            validation_methods_used=self._validation_methods,
        )
