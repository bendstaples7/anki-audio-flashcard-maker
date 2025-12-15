"""
Audio-to-vocabulary alignment logic for matching segmented audio clips to vocabulary terms.
"""

import os
import tempfile
import logging
from typing import List, Tuple, Optional
from pathlib import Path

from ..models import VocabularyEntry, AudioSegment, AlignedPair
from .forced_aligner import ForcedAligner, AlignmentResult


class AudioVocabularyAligner:
    """
    Matches segmented audio clips to vocabulary terms using forced alignment.
    Calculates alignment confidence scores and handles validation.
    """
    
    def __init__(self, forced_aligner: Optional[ForcedAligner] = None):
        """
        Initialize the audio-vocabulary aligner.
        
        Args:
            forced_aligner: ForcedAligner instance. If None, creates a new one.
        """
        self.forced_aligner = forced_aligner or ForcedAligner()
        self.logger = logging.getLogger(__name__)
        
        # Alignment quality thresholds
        self.min_confidence_threshold = 0.3
        self.good_confidence_threshold = 0.7
        
    def align_audio_to_vocabulary(
        self, 
        audio_segments: List[AudioSegment], 
        vocabulary_entries: List[VocabularyEntry],
        original_audio_path: str
    ) -> List[AlignedPair]:
        """
        Match segmented audio clips to vocabulary terms using forced alignment.
        
        Args:
            audio_segments: List of segmented audio clips.
            vocabulary_entries: List of vocabulary entries to match.
            original_audio_path: Path to the original audio file.
            
        Returns:
            List of aligned pairs with confidence scores.
        """
        self.logger.info(f"Aligning {len(audio_segments)} audio segments to {len(vocabulary_entries)} vocabulary terms")
        
        # Validate inputs
        if len(audio_segments) != len(vocabulary_entries):
            self.logger.warning(
                f"Mismatch: {len(audio_segments)} audio segments vs {len(vocabulary_entries)} vocabulary entries"
            )
        
        try:
            # Prepare files for forced alignment
            corpus_dir, dict_path, transcript_path = self.forced_aligner.prepare_alignment_files(
                original_audio_path, vocabulary_entries
            )
            
            # Create output directory for alignment results
            output_dir = tempfile.mkdtemp(prefix='mfa_output_')
            
            # Run forced alignment
            alignment_success = self.forced_aligner.run_mfa_alignment(corpus_dir, dict_path, output_dir)
            
            if alignment_success:
                # Parse alignment results
                audio_filename = Path(original_audio_path).stem
                alignment_results = self.forced_aligner.parse_alignment_results(output_dir, audio_filename)
                
                # Match alignment results to audio segments and vocabulary
                aligned_pairs = self._match_alignments_to_segments(
                    alignment_results, audio_segments, vocabulary_entries
                )
            else:
                # Fallback to simple sequential matching if forced alignment fails
                self.logger.warning("Forced alignment failed, using fallback sequential matching")
                aligned_pairs = self._fallback_sequential_alignment(audio_segments, vocabulary_entries)
            
            # Cleanup temporary files
            self.forced_aligner.cleanup_temp_files(corpus_dir, dict_path, output_dir)
            
            return aligned_pairs
            
        except Exception as e:
            self.logger.error(f"Error during alignment: {e}")
            # Fallback to sequential matching
            return self._fallback_sequential_alignment(audio_segments, vocabulary_entries)
    
    def _match_alignments_to_segments(
        self,
        alignment_results: List[AlignmentResult],
        audio_segments: List[AudioSegment], 
        vocabulary_entries: List[VocabularyEntry]
    ) -> List[AlignedPair]:
        """
        Match forced alignment results to audio segments and vocabulary entries.
        
        Args:
            alignment_results: Results from forced alignment.
            audio_segments: List of audio segments.
            vocabulary_entries: List of vocabulary entries.
            
        Returns:
            List of aligned pairs.
        """
        aligned_pairs = []
        
        # Create vocabulary lookup by Cantonese text
        vocab_lookup = {entry.cantonese.strip(): entry for entry in vocabulary_entries}
        
        for alignment_result in alignment_results:
            # Find matching vocabulary entry
            vocab_entry = vocab_lookup.get(alignment_result.word)
            if not vocab_entry:
                self.logger.warning(f"No vocabulary entry found for aligned word: {alignment_result.word}")
                continue
            
            # Find best matching audio segment based on timing
            best_segment = self._find_best_matching_segment(alignment_result, audio_segments)
            if not best_segment:
                self.logger.warning(f"No audio segment found for alignment: {alignment_result.word}")
                continue
            
            # Calculate combined confidence score
            combined_confidence = self._calculate_combined_confidence(
                alignment_result, best_segment
            )
            
            # Create aligned pair
            aligned_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=best_segment,
                alignment_confidence=combined_confidence,
                audio_file_path=best_segment.audio_file_path
            )
            
            aligned_pairs.append(aligned_pair)
            
        return aligned_pairs
    
    def _find_best_matching_segment(
        self, 
        alignment_result: AlignmentResult, 
        audio_segments: List[AudioSegment]
    ) -> Optional[AudioSegment]:
        """
        Find the audio segment that best matches the alignment timing.
        
        Args:
            alignment_result: Alignment result with timing information.
            audio_segments: List of available audio segments.
            
        Returns:
            Best matching audio segment or None.
        """
        best_segment = None
        best_overlap = 0.0
        
        alignment_center = (alignment_result.start_time + alignment_result.end_time) / 2
        
        for segment in audio_segments:
            segment_center = (segment.start_time + segment.end_time) / 2
            
            # Calculate overlap between alignment and segment
            overlap_start = max(alignment_result.start_time, segment.start_time)
            overlap_end = min(alignment_result.end_time, segment.end_time)
            
            if overlap_end > overlap_start:
                overlap_duration = overlap_end - overlap_start
                
                # Normalize by the shorter duration
                alignment_duration = alignment_result.end_time - alignment_result.start_time
                segment_duration = segment.end_time - segment.start_time
                min_duration = min(alignment_duration, segment_duration)
                
                overlap_ratio = overlap_duration / min_duration if min_duration > 0 else 0
                
                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    best_segment = segment
        
        return best_segment
    
    def _calculate_combined_confidence(
        self, 
        alignment_result: AlignmentResult, 
        audio_segment: AudioSegment
    ) -> float:
        """
        Calculate combined confidence score from alignment and segment quality.
        
        Args:
            alignment_result: Alignment result with confidence.
            audio_segment: Audio segment with confidence.
            
        Returns:
            Combined confidence score (0.0 to 1.0).
        """
        # Weight alignment confidence more heavily than segment confidence
        alignment_weight = 0.7
        segment_weight = 0.3
        
        combined_confidence = (
            alignment_weight * alignment_result.confidence +
            segment_weight * audio_segment.confidence
        )
        
        # Apply penalty for timing mismatch
        alignment_duration = alignment_result.end_time - alignment_result.start_time
        segment_duration = audio_segment.end_time - audio_segment.start_time
        
        if alignment_duration > 0 and segment_duration > 0:
            duration_ratio = min(alignment_duration, segment_duration) / max(alignment_duration, segment_duration)
            timing_penalty = 1.0 - (1.0 - duration_ratio) * 0.5  # Up to 50% penalty for timing mismatch
            combined_confidence *= timing_penalty
        
        return max(0.0, min(1.0, combined_confidence))
    
    def _fallback_sequential_alignment(
        self, 
        audio_segments: List[AudioSegment], 
        vocabulary_entries: List[VocabularyEntry]
    ) -> List[AlignedPair]:
        """
        Fallback method for sequential alignment when forced alignment fails.
        
        Args:
            audio_segments: List of audio segments.
            vocabulary_entries: List of vocabulary entries.
            
        Returns:
            List of aligned pairs using sequential matching.
        """
        self.logger.info("Using fallback sequential alignment")
        
        aligned_pairs = []
        min_length = min(len(audio_segments), len(vocabulary_entries))
        
        for i in range(min_length):
            # Simple sequential matching with reduced confidence
            fallback_confidence = 0.5 * audio_segments[i].confidence
            
            aligned_pair = AlignedPair(
                vocabulary_entry=vocabulary_entries[i],
                audio_segment=audio_segments[i],
                alignment_confidence=fallback_confidence,
                audio_file_path=audio_segments[i].audio_file_path
            )
            
            aligned_pairs.append(aligned_pair)
        
        if len(audio_segments) != len(vocabulary_entries):
            self.logger.warning(
                f"Sequential alignment: {min_length} pairs created from "
                f"{len(audio_segments)} segments and {len(vocabulary_entries)} vocabulary entries"
            )
        
        return aligned_pairs
    
    def validate_alignment_quality(self, aligned_pairs: List[AlignedPair]) -> Tuple[List[AlignedPair], List[AlignedPair]]:
        """
        Validate alignment quality and separate good from poor alignments.
        
        Args:
            aligned_pairs: List of aligned pairs to validate.
            
        Returns:
            Tuple of (good_alignments, poor_alignments).
        """
        good_alignments = []
        poor_alignments = []
        
        for pair in aligned_pairs:
            if pair.alignment_confidence >= self.min_confidence_threshold:
                good_alignments.append(pair)
            else:
                poor_alignments.append(pair)
        
        self.logger.info(
            f"Alignment validation: {len(good_alignments)} good, {len(poor_alignments)} poor alignments"
        )
        
        return good_alignments, poor_alignments
    
    def get_alignment_statistics(self, aligned_pairs: List[AlignedPair]) -> dict:
        """
        Calculate alignment quality statistics.
        
        Args:
            aligned_pairs: List of aligned pairs.
            
        Returns:
            Dictionary with alignment statistics.
        """
        if not aligned_pairs:
            return {
                'total_pairs': 0,
                'average_confidence': 0.0,
                'good_alignments': 0,
                'poor_alignments': 0,
                'success_rate': 0.0
            }
        
        confidences = [pair.alignment_confidence for pair in aligned_pairs]
        good_count = sum(1 for conf in confidences if conf >= self.good_confidence_threshold)
        poor_count = sum(1 for conf in confidences if conf < self.min_confidence_threshold)
        
        return {
            'total_pairs': len(aligned_pairs),
            'average_confidence': sum(confidences) / len(confidences),
            'good_alignments': good_count,
            'poor_alignments': poor_count,
            'success_rate': good_count / len(aligned_pairs) if aligned_pairs else 0.0
        }