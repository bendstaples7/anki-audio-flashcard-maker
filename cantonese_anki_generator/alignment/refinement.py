"""
Alignment refinement and error recovery for improving alignment quality.
"""

import logging
from typing import List, Tuple, Optional, Dict
import numpy as np
from scipy import signal
from scipy.spatial.distance import cosine

from ..models import VocabularyEntry, AudioSegment, AlignedPair


class AlignmentRefinement:
    """
    Handles alignment quality validation, refinement, and error recovery.
    Provides fallback strategies for poor alignment results.
    """
    
    def __init__(self):
        """Initialize the alignment refinement system."""
        self.logger = logging.getLogger(__name__)
        
        # Quality thresholds
        self.min_acceptable_confidence = 0.3
        self.good_confidence_threshold = 0.7
        self.excellent_confidence_threshold = 0.9
        
        # Refinement parameters
        self.max_refinement_iterations = 3
        self.timing_tolerance = 0.2  # 200ms tolerance for timing adjustments
        
    def refine_alignments(self, aligned_pairs: List[AlignedPair]) -> List[AlignedPair]:
        """
        Refine alignment quality through multiple strategies.
        
        Args:
            aligned_pairs: List of aligned pairs to refine.
            
        Returns:
            List of refined aligned pairs.
        """
        self.logger.info(f"Refining {len(aligned_pairs)} alignments")
        
        refined_pairs = aligned_pairs.copy()
        
        # Apply refinement strategies
        refined_pairs = self._adjust_timing_boundaries(refined_pairs)
        refined_pairs = self._resolve_overlapping_alignments(refined_pairs)
        refined_pairs = self._smooth_confidence_scores(refined_pairs)
        
        # Validate final results
        refined_pairs = self._validate_refined_alignments(refined_pairs)
        
        return refined_pairs
    
    def _adjust_timing_boundaries(self, aligned_pairs: List[AlignedPair]) -> List[AlignedPair]:
        """
        Adjust timing boundaries to improve alignment quality.
        
        Args:
            aligned_pairs: List of aligned pairs.
            
        Returns:
            List of pairs with adjusted timing.
        """
        adjusted_pairs = []
        
        for i, pair in enumerate(aligned_pairs):
            adjusted_pair = pair
            
            # Check for timing inconsistencies
            segment = pair.audio_segment
            duration = segment.end_time - segment.start_time
            
            # Adjust very short or very long segments
            if duration < 0.3:  # Less than 300ms
                # Extend segment slightly
                extension = (0.3 - duration) / 2
                new_start = max(0, segment.start_time - extension)
                new_end = segment.end_time + extension
                
                # Check for conflicts with adjacent segments
                if i > 0:
                    prev_end = aligned_pairs[i-1].audio_segment.end_time
                    new_start = max(new_start, prev_end)
                
                if i < len(aligned_pairs) - 1:
                    next_start = aligned_pairs[i+1].audio_segment.start_time
                    new_end = min(new_end, next_start)
                
                # Create adjusted segment
                adjusted_segment = AudioSegment(
                    start_time=new_start,
                    end_time=new_end,
                    audio_data=segment.audio_data,
                    confidence=segment.confidence * 0.9,  # Slight penalty for adjustment
                    segment_id=segment.segment_id,
                    audio_file_path=segment.audio_file_path
                )
                
                adjusted_pair = AlignedPair(
                    vocabulary_entry=pair.vocabulary_entry,
                    audio_segment=adjusted_segment,
                    alignment_confidence=pair.alignment_confidence * 0.95,
                    audio_file_path=pair.audio_file_path
                )
                
                self.logger.debug(f"Adjusted timing for segment {i}: {duration:.3f}s -> {new_end - new_start:.3f}s")
            
            elif duration > 3.0:  # More than 3 seconds
                # Trim segment to reasonable length
                target_duration = min(2.5, duration * 0.8)
                center_time = (segment.start_time + segment.end_time) / 2
                new_start = center_time - target_duration / 2
                new_end = center_time + target_duration / 2
                
                adjusted_segment = AudioSegment(
                    start_time=new_start,
                    end_time=new_end,
                    audio_data=segment.audio_data,
                    confidence=segment.confidence * 0.9,
                    segment_id=segment.segment_id,
                    audio_file_path=segment.audio_file_path
                )
                
                adjusted_pair = AlignedPair(
                    vocabulary_entry=pair.vocabulary_entry,
                    audio_segment=adjusted_segment,
                    alignment_confidence=pair.alignment_confidence * 0.95,
                    audio_file_path=pair.audio_file_path
                )
                
                self.logger.debug(f"Trimmed long segment {i}: {duration:.3f}s -> {target_duration:.3f}s")
            
            adjusted_pairs.append(adjusted_pair)
        
        return adjusted_pairs
    
    def _resolve_overlapping_alignments(self, aligned_pairs: List[AlignedPair]) -> List[AlignedPair]:
        """
        Resolve overlapping audio segments in alignments.
        
        Args:
            aligned_pairs: List of aligned pairs.
            
        Returns:
            List of pairs with resolved overlaps.
        """
        if len(aligned_pairs) <= 1:
            return aligned_pairs
        
        resolved_pairs = []
        
        for i, pair in enumerate(aligned_pairs):
            current_segment = pair.audio_segment
            
            # Check for overlap with next segment
            if i < len(aligned_pairs) - 1:
                next_segment = aligned_pairs[i + 1].audio_segment
                
                if current_segment.end_time > next_segment.start_time:
                    # Overlap detected - split the difference
                    overlap_midpoint = (current_segment.end_time + next_segment.start_time) / 2
                    
                    # Adjust current segment end
                    adjusted_current = AudioSegment(
                        start_time=current_segment.start_time,
                        end_time=overlap_midpoint,
                        audio_data=current_segment.audio_data,
                        confidence=current_segment.confidence * 0.95,  # Small penalty for adjustment
                        segment_id=current_segment.segment_id,
                        audio_file_path=current_segment.audio_file_path
                    )
                    
                    adjusted_pair = AlignedPair(
                        vocabulary_entry=pair.vocabulary_entry,
                        audio_segment=adjusted_current,
                        alignment_confidence=pair.alignment_confidence * 0.95,
                        audio_file_path=pair.audio_file_path
                    )
                    
                    resolved_pairs.append(adjusted_pair)
                    
                    self.logger.debug(f"Resolved overlap between segments {i} and {i+1}")
                else:
                    resolved_pairs.append(pair)
            else:
                resolved_pairs.append(pair)
        
        return resolved_pairs
    
    def _smooth_confidence_scores(self, aligned_pairs: List[AlignedPair]) -> List[AlignedPair]:
        """
        Apply smoothing to confidence scores based on neighboring alignments.
        
        Args:
            aligned_pairs: List of aligned pairs.
            
        Returns:
            List of pairs with smoothed confidence scores.
        """
        if len(aligned_pairs) <= 2:
            return aligned_pairs
        
        smoothed_pairs = []
        confidences = [pair.alignment_confidence for pair in aligned_pairs]
        
        # Apply simple moving average smoothing
        window_size = 3
        for i, pair in enumerate(aligned_pairs):
            # Calculate smoothed confidence
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(confidences), i + window_size // 2 + 1)
            
            window_confidences = confidences[start_idx:end_idx]
            smoothed_confidence = sum(window_confidences) / len(window_confidences)
            
            # Blend original and smoothed confidence (70% original, 30% smoothed)
            final_confidence = 0.7 * pair.alignment_confidence + 0.3 * smoothed_confidence
            
            smoothed_pair = AlignedPair(
                vocabulary_entry=pair.vocabulary_entry,
                audio_segment=pair.audio_segment,
                alignment_confidence=final_confidence,
                audio_file_path=pair.audio_file_path
            )
            
            smoothed_pairs.append(smoothed_pair)
        
        return smoothed_pairs
    
    def _validate_refined_alignments(self, aligned_pairs: List[AlignedPair]) -> List[AlignedPair]:
        """
        Validate refined alignments and mark quality levels.
        
        Args:
            aligned_pairs: List of refined aligned pairs.
            
        Returns:
            List of validated aligned pairs.
        """
        validated_pairs = []
        
        for pair in aligned_pairs:
            # Ensure confidence is within valid range
            confidence = max(0.0, min(1.0, pair.alignment_confidence))
            
            # Apply final quality check
            segment_duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            
            # Penalize very short or very long segments
            if segment_duration < 0.2 or segment_duration > 4.0:
                confidence *= 0.8
            
            validated_pair = AlignedPair(
                vocabulary_entry=pair.vocabulary_entry,
                audio_segment=pair.audio_segment,
                alignment_confidence=confidence,
                audio_file_path=pair.audio_file_path
            )
            
            validated_pairs.append(validated_pair)
        
        return validated_pairs
    
    def handle_low_confidence_alignments(
        self, 
        aligned_pairs: List[AlignedPair],
        audio_segments: List[AudioSegment],
        vocabulary_entries: List[VocabularyEntry]
    ) -> List[AlignedPair]:
        """
        Handle alignments with low confidence using fallback strategies.
        
        Args:
            aligned_pairs: List of aligned pairs.
            audio_segments: Original audio segments.
            vocabulary_entries: Original vocabulary entries.
            
        Returns:
            List of improved aligned pairs.
        """
        improved_pairs = []
        low_confidence_pairs = []
        
        # Separate good and poor alignments
        for pair in aligned_pairs:
            if pair.alignment_confidence >= self.min_acceptable_confidence:
                improved_pairs.append(pair)
            else:
                low_confidence_pairs.append(pair)
        
        if low_confidence_pairs:
            self.logger.info(f"Applying fallback strategies to {len(low_confidence_pairs)} low-confidence alignments")
            
            # Try alternative matching strategies
            recovered_pairs = self._apply_fallback_strategies(
                low_confidence_pairs, audio_segments, vocabulary_entries
            )
            
            improved_pairs.extend(recovered_pairs)
        
        return improved_pairs
    
    def _apply_fallback_strategies(
        self,
        low_confidence_pairs: List[AlignedPair],
        audio_segments: List[AudioSegment],
        vocabulary_entries: List[VocabularyEntry]
    ) -> List[AlignedPair]:
        """
        Apply fallback strategies for low-confidence alignments.
        
        Args:
            low_confidence_pairs: Pairs with low confidence.
            audio_segments: Original audio segments.
            vocabulary_entries: Original vocabulary entries.
            
        Returns:
            List of recovered aligned pairs.
        """
        recovered_pairs = []
        
        for pair in low_confidence_pairs:
            # Strategy 1: Try nearest neighbor matching
            alternative_segment = self._find_nearest_unmatched_segment(
                pair.vocabulary_entry, audio_segments, recovered_pairs
            )
            
            if alternative_segment:
                # Create new pair with moderate confidence
                recovered_pair = AlignedPair(
                    vocabulary_entry=pair.vocabulary_entry,
                    audio_segment=alternative_segment,
                    alignment_confidence=0.4,  # Moderate confidence for fallback
                    audio_file_path=alternative_segment.audio_file_path
                )
                recovered_pairs.append(recovered_pair)
                self.logger.debug(f"Recovered alignment using nearest neighbor for: {pair.vocabulary_entry.cantonese}")
            else:
                # Strategy 2: Keep original with reduced confidence
                fallback_pair = AlignedPair(
                    vocabulary_entry=pair.vocabulary_entry,
                    audio_segment=pair.audio_segment,
                    alignment_confidence=max(0.1, pair.alignment_confidence * 0.5),
                    audio_file_path=pair.audio_file_path
                )
                recovered_pairs.append(fallback_pair)
                self.logger.debug(f"Kept original alignment with reduced confidence: {pair.vocabulary_entry.cantonese}")
        
        return recovered_pairs
    
    def _find_nearest_unmatched_segment(
        self,
        vocabulary_entry: VocabularyEntry,
        audio_segments: List[AudioSegment],
        already_matched: List[AlignedPair]
    ) -> Optional[AudioSegment]:
        """
        Find the nearest unmatched audio segment for a vocabulary entry.
        
        Args:
            vocabulary_entry: Vocabulary entry to match.
            audio_segments: Available audio segments.
            already_matched: Already matched pairs to exclude.
            
        Returns:
            Best unmatched audio segment or None.
        """
        matched_segment_ids = {pair.audio_segment.segment_id for pair in already_matched}
        
        # Find unmatched segments
        unmatched_segments = [
            segment for segment in audio_segments 
            if segment.segment_id not in matched_segment_ids
        ]
        
        if not unmatched_segments:
            return None
        
        # Use vocabulary entry row index as a hint for positioning
        target_position = vocabulary_entry.row_index / max(1, len(audio_segments) - 1)
        
        best_segment = None
        best_score = float('inf')
        
        for segment in unmatched_segments:
            # Calculate position-based score
            segment_position = audio_segments.index(segment) / max(1, len(audio_segments) - 1)
            position_diff = abs(target_position - segment_position)
            
            # Combine with segment confidence
            score = position_diff + (1.0 - segment.confidence) * 0.3
            
            if score < best_score:
                best_score = score
                best_segment = segment
        
        return best_segment
    
    def get_refinement_report(self, original_pairs: List[AlignedPair], refined_pairs: List[AlignedPair]) -> Dict:
        """
        Generate a report on refinement improvements.
        
        Args:
            original_pairs: Original aligned pairs.
            refined_pairs: Refined aligned pairs.
            
        Returns:
            Dictionary with refinement statistics.
        """
        if not original_pairs or not refined_pairs:
            return {'error': 'No pairs to compare'}
        
        original_avg_confidence = sum(p.alignment_confidence for p in original_pairs) / len(original_pairs)
        refined_avg_confidence = sum(p.alignment_confidence for p in refined_pairs) / len(refined_pairs)
        
        original_good = sum(1 for p in original_pairs if p.alignment_confidence >= self.good_confidence_threshold)
        refined_good = sum(1 for p in refined_pairs if p.alignment_confidence >= self.good_confidence_threshold)
        
        return {
            'total_pairs': len(refined_pairs),
            'original_avg_confidence': original_avg_confidence,
            'refined_avg_confidence': refined_avg_confidence,
            'confidence_improvement': refined_avg_confidence - original_avg_confidence,
            'original_good_alignments': original_good,
            'refined_good_alignments': refined_good,
            'good_alignment_improvement': refined_good - original_good,
            'success_rate': refined_good / len(refined_pairs) if refined_pairs else 0.0
        }