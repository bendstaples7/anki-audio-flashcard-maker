"""
Smart boundary detection using silence gap analysis with speech verification feedback.

This module implements intelligent boundary detection that uses both silence analysis
and speech verification to create precise, non-overlapping segments.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np

from ..models import AudioSegment


logger = logging.getLogger(__name__)


class SmartBoundaryDetector:
    """
    Smart boundary detection that finds actual silence gaps between words.
    
    Enhanced with speech verification feedback to create precise, non-overlapping segments.
    """
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize Smart Boundary Detector.
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
        
        # Detection parameters (optimized for precision)
        self.min_gap_duration = 0.03  # Minimum gap to consider (30ms) - reduced for tighter detection
        self.silence_threshold = 0.01  # RMS threshold for silence - more sensitive
        self.window_size = int(0.015 * sample_rate)  # 15ms windows - smaller for precision
        self.hop_size = int(0.005 * sample_rate)     # 5ms hop - finer resolution
        self.padding = 0.02  # 20ms padding - reduced to prevent overlap
        self.min_segment_duration = 1.0  # Minimum segment duration (1.0s) - single words need at least 1s
        self.max_segment_duration = 8.0  # Maximum segment duration (8s) - allow longer phrases
    
    def find_silence_gaps(self, audio_data: np.ndarray) -> List[Tuple[float, float]]:
        """
        Find silence gaps in audio that could be word boundaries.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            List of (start_time, end_time) tuples for silence gaps
        """
        # Calculate RMS energy in small windows
        rms_values = []
        times = []
        
        for i in range(0, len(audio_data) - self.window_size, self.hop_size):
            window = audio_data[i:i + self.window_size]
            rms = np.sqrt(np.mean(window ** 2))
            rms_values.append(rms)
            times.append(i / self.sample_rate)
        
        rms_values = np.array(rms_values)
        times = np.array(times)
        
        # Adaptive threshold based on audio characteristics
        median_rms = np.median(rms_values)
        adaptive_threshold = min(self.silence_threshold, median_rms * 0.3)
        
        # Find silence regions
        silence_mask = rms_values < adaptive_threshold
        
        # Find continuous silence regions
        silence_gaps = []
        in_silence = False
        silence_start = 0
        
        for i, is_silent in enumerate(silence_mask):
            if is_silent and not in_silence:
                # Start of silence
                in_silence = True
                silence_start = times[i]
            elif not is_silent and in_silence:
                # End of silence
                in_silence = False
                silence_end = times[i]
                
                # Check if gap is long enough
                if silence_end - silence_start >= self.min_gap_duration:
                    silence_gaps.append((silence_start, silence_end))
        
        logger.debug(f"Found {len(silence_gaps)} silence gaps with adaptive threshold {adaptive_threshold:.4f}")
        return silence_gaps
    
    def create_precise_boundaries(self, audio_data: np.ndarray, silence_gaps: List[Tuple[float, float]], 
                                expected_count: int, start_offset: float) -> List[float]:
        """
        Create precise boundaries that avoid overlap between segments.
        
        Args:
            audio_data: Audio data array
            silence_gaps: List of silence gap tuples
            expected_count: Expected number of segments
            start_offset: Start offset in seconds
            
        Returns:
            List of boundary times
        """
        total_duration = len(audio_data) / self.sample_rate
        
        # Filter gaps that are after our start offset
        valid_gaps = [(start, end) for start, end in silence_gaps if start >= start_offset]
        
        # If we have too many gaps, select the most significant ones
        if len(valid_gaps) > expected_count - 1:
            # Score gaps by duration and position
            gap_scores = []
            for start, end in valid_gaps:
                duration = end - start
                # Prefer longer gaps and gaps that are well-spaced
                score = duration
                gap_scores.append((score, start, end))
            
            # Sort by score and select top gaps
            gap_scores.sort(reverse=True)
            selected_gaps = [(start, end) for _, start, end in gap_scores[:expected_count - 1]]
            selected_gaps.sort()  # Sort by time
            valid_gaps = selected_gaps
        
        # Create boundaries at the center of gaps
        boundaries = [start_offset]
        
        for gap_start, gap_end in valid_gaps:
            # Use center of gap as boundary
            boundary = (gap_start + gap_end) / 2
            boundaries.append(boundary)
        
        # Add end boundary
        boundaries.append(total_duration - 0.1)
        
        # Ensure minimum segment durations
        adjusted_boundaries = [boundaries[0]]
        
        for i in range(1, len(boundaries)):
            prev_boundary = adjusted_boundaries[-1]
            current_boundary = boundaries[i]
            
            # Ensure minimum duration
            if current_boundary - prev_boundary < self.min_segment_duration:
                # Extend this boundary
                current_boundary = prev_boundary + self.min_segment_duration
                # But don't exceed total duration
                current_boundary = min(current_boundary, total_duration - 0.1)
            
            adjusted_boundaries.append(current_boundary)
        
        return adjusted_boundaries
    
    def segment_audio(self, audio_data: np.ndarray, expected_count: int, 
                     start_offset: float = 0.0, force_start_offset: bool = False) -> List[AudioSegment]:
        """
        Segment audio using smart boundary detection with precise, non-overlapping segments.
        
        Args:
            audio_data: Audio data array
            expected_count: Expected number of segments
            start_offset: Seconds to skip at beginning
            force_start_offset: If True, don't auto-detect silence, use exact start_offset
            
        Returns:
            List of AudioSegment objects
        """
        logger.info(f"Smart segmentation: {expected_count} segments expected")
        
        # Auto-detect if there's significant silence at the beginning (unless forced)
        original_start_offset = start_offset
        if start_offset == 0.0 and not force_start_offset:
            try:
                # ENHANCED: More aggressive silence detection at the beginning
                # Check first 3 seconds or 30% of audio (whichever is smaller)
                check_duration = min(3.0, len(audio_data) / self.sample_rate * 0.3)
                check_samples = int(check_duration * self.sample_rate)
                
                if check_samples > 0 and check_samples < len(audio_data):
                    # Calculate overall audio RMS for comparison
                    overall_rms = np.sqrt(np.mean(audio_data ** 2))
                    
                    # Use smaller windows for more precise detection
                    window_size = int(0.05 * self.sample_rate)  # 50ms windows (was 100ms)
                    hop_size = int(0.02 * self.sample_rate)     # 20ms hop (was 50ms)
                    
                    if window_size > 0 and hop_size > 0:
                        # Scan from the beginning to find where speech actually starts
                        speech_threshold = max(0.01, overall_rms * 0.15)  # More lenient threshold
                        
                        for i in range(0, len(audio_data) - window_size, hop_size):
                            window = audio_data[i:i + window_size]
                            window_rms = np.sqrt(np.mean(window ** 2))
                            
                            # Found speech when RMS exceeds threshold
                            if window_rms > speech_threshold:
                                detected_start = i / self.sample_rate
                                
                                # Only skip if we detected significant silence (at least 0.2s)
                                if detected_start >= 0.2:
                                    logger.info(f"🔍 Auto-detected {detected_start:.2f}s of silence at beginning")
                                    logger.info(f"   Speech threshold: {speech_threshold:.4f}, Overall RMS: {overall_rms:.4f}")
                                    start_offset = detected_start
                                else:
                                    logger.debug(f"Detected speech at {detected_start:.2f}s (too early to skip)")
                                break
                        
                        # If we scanned the entire check region without finding speech, something is wrong
                        if start_offset == 0.0:
                            logger.warning(f"No speech detected in first {check_duration:.2f}s - audio may be very quiet or silent")
                            
            except Exception as e:
                logger.warning(f"Auto-detection of silence failed, using original offset: {e}")
                start_offset = original_start_offset
        
        if start_offset != original_start_offset:
            logger.info(f"✂️  Skipping {start_offset:.2f}s of initial silence")
            logger.info(f"   Starting segmentation from {start_offset:.2f}s")
        else:
            logger.info(f"✂️  No initial silence detected, starting from {start_offset:.2f}s")
        
        # Find silence gaps
        silence_gaps = self.find_silence_gaps(audio_data)
        logger.info(f"Found {len(silence_gaps)} potential silence gaps")
        
        # Create precise boundaries
        boundaries = self.create_precise_boundaries(audio_data, silence_gaps, expected_count, start_offset)
        logger.info(f"Created {len(boundaries)} boundaries for {len(boundaries)-1} segments")
        
        # Create non-overlapping segments
        segments = []
        total_duration = len(audio_data) / self.sample_rate
        
        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]
            
            # Add minimal padding but ensure no overlap
            if i == 0:
                # First segment: no padding at start
                padded_start = start_time
            else:
                # Other segments: small padding but don't overlap with previous
                prev_end = boundaries[i] - self.padding
                padded_start = max(prev_end, start_time - self.padding)
            
            if i == len(boundaries) - 2:
                # Last segment: no padding at end
                padded_end = end_time
            else:
                # Other segments: small padding but don't overlap with next
                next_start = boundaries[i + 1] + self.padding
                padded_end = min(next_start, end_time + self.padding)
            
            # Ensure we don't exceed audio bounds
            padded_start = max(0, padded_start)
            padded_end = min(total_duration, padded_end)
            
            # Convert to samples
            start_sample = int(padded_start * self.sample_rate)
            end_sample = int(padded_end * self.sample_rate)
            
            # Extract audio
            segment_audio = audio_data[start_sample:end_sample]
            
            # Calculate confidence based on segment characteristics
            segment_duration = padded_end - padded_start
            confidence = 0.9  # High confidence for gap-based detection
            
            # Reduce confidence for very short or very long segments
            if segment_duration < self.min_segment_duration:
                confidence *= 0.7
            elif segment_duration > self.max_segment_duration:
                confidence *= 0.8
            
            # Create segment
            segment = AudioSegment(
                start_time=padded_start,
                end_time=padded_end,
                audio_data=segment_audio,
                confidence=confidence,
                segment_id=f"smart_{i+1:03d}"
            )
            
            segments.append(segment)
            
            logger.debug(f"Segment {i+1}: {padded_start:.3f}s - {padded_end:.3f}s "
                        f"(duration: {segment_duration:.3f}s, confidence: {confidence:.2f})")
        
        # Log summary of segments
        logger.info(f"✂️  Segmentation complete:")
        logger.info(f"   Created {len(segments)} segments from {start_offset:.2f}s to {total_duration:.2f}s")
        if segments:
            durations = [s.end_time - s.start_time for s in segments]
            logger.info(f"   Segment durations: min={min(durations):.2f}s, max={max(durations):.2f}s, avg={sum(durations)/len(durations):.2f}s")
        
        return segments
    
    def refine_boundaries_with_speech_feedback(self, segments: List[AudioSegment], 
                                             verification_results: dict) -> List[AudioSegment]:
        """
        Refine segment boundaries based on speech verification feedback.
        
        This method dynamically adjusts boundaries for low-confidence segments by:
        1. Testing small boundary shifts (±0.1s to ±0.5s)
        2. Using speech verification to check if adjustments improve alignment
        3. Keeping the best boundary positions found
        
        ENHANCED: Now refines ANY segment with semantic mismatches, not just low confidence ones.
        
        Args:
            segments: Current audio segments
            verification_results: Results from speech verification
            
        Returns:
            Refined audio segments with improved boundaries
        """
        if not verification_results or 'verified_pairs' not in verification_results:
            return segments
        
        # Import here to avoid circular imports
        try:
            from .speech_verification import WhisperVerifier
            verifier = WhisperVerifier(model_size="base")
        except ImportError:
            logger.warning("Whisper not available for boundary refinement")
            return segments
        
        refined_segments = []
        verified_pairs = verification_results['verified_pairs']
        
        logger.info(f"Refining boundaries for {len(segments)} segments using speech feedback")
        
        # Count segments that need refinement
        segments_needing_refinement = 0
        for i, segment in enumerate(segments):
            if i < len(verified_pairs):
                pair_result = verified_pairs[i]
                current_confidence = pair_result.get('overall_confidence', segment.confidence)
                is_semantic_match = pair_result.get('comparison_details', {}).get('is_match', True)
                
                # ENHANCED CRITERIA: Refine if low confidence OR semantic mismatch
                needs_refinement = (current_confidence < 0.7 or not is_semantic_match)
                if needs_refinement:
                    segments_needing_refinement += 1
        
        logger.info(f"Found {segments_needing_refinement} segments that need boundary refinement")
        
        for i, segment in enumerate(segments):
            if i < len(verified_pairs):
                pair_result = verified_pairs[i]
                current_confidence = pair_result.get('overall_confidence', segment.confidence)
                expected_cantonese = pair_result.get('expected_cantonese', '')
                is_semantic_match = pair_result.get('comparison_details', {}).get('is_match', True)
                transcribed_text = pair_result.get('transcribed_cantonese', '')
                
                # ENHANCED CRITERIA: Refine if low confidence OR semantic mismatch
                needs_refinement = (current_confidence < 0.7 or not is_semantic_match) and expected_cantonese
                
                if needs_refinement:
                    logger.info(f"Refining segment {i+1}: '{expected_cantonese}' (confidence: {current_confidence:.2f}, "
                              f"semantic_match: {is_semantic_match}, transcribed: '{transcribed_text}')")
                    
                    # Try different boundary adjustments
                    best_segment = segment
                    best_confidence = current_confidence
                    best_semantic_match = is_semantic_match
                    
                    # ENHANCED: Test more aggressive boundary shifts for semantic mismatches
                    if not is_semantic_match:
                        # For semantic mismatches, test larger shifts to find correct audio
                        shift_amounts = [-1.0, -0.8, -0.6, -0.4, -0.2, -0.1, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
                        logger.debug(f"Semantic mismatch detected - testing aggressive boundary shifts")
                    else:
                        # For low confidence, use smaller adjustments
                        shift_amounts = [-0.5, -0.3, -0.2, -0.1, 0.1, 0.2, 0.3, 0.5]
                    
                    improvements_found = 0
                    
                    for start_shift in shift_amounts:
                        for end_shift in shift_amounts:
                            # Calculate new boundaries
                            new_start = max(0, segment.start_time + start_shift)
                            new_end = min(len(segment.audio_data) / self.sample_rate, 
                                        segment.end_time + end_shift)
                            
                            # Ensure minimum duration
                            if new_end - new_start < self.min_segment_duration:
                                continue
                            
                            # Ensure maximum duration
                            if new_end - new_start > self.max_segment_duration:
                                continue
                            
                            # Extract audio for new boundaries
                            start_sample = int(new_start * self.sample_rate)
                            end_sample = int(new_end * self.sample_rate)
                            
                            # Make sure we don't go out of bounds
                            if start_sample >= 0 and end_sample <= len(segment.audio_data):
                                new_audio_data = segment.audio_data[start_sample:end_sample]
                                
                                if len(new_audio_data) > 0:
                                    try:
                                        # Test this boundary adjustment with Whisper
                                        transcription = verifier.transcribe_audio_segment(
                                            new_audio_data, self.sample_rate
                                        )
                                        
                                        comparison = verifier.compare_transcription_with_expected(
                                            transcription['text'], expected_cantonese
                                        )
                                        
                                        # Calculate new confidence
                                        whisper_confidence = transcription['confidence']
                                        match_confidence = comparison['similarity']
                                        new_confidence = (whisper_confidence + match_confidence) / 2
                                        new_semantic_match = comparison['is_match']
                                        
                                        # ENHANCED: Prioritize semantic matches over confidence
                                        is_improvement = False
                                        
                                        if not best_semantic_match and new_semantic_match:
                                            # Found semantic match where there wasn't one before - major improvement
                                            is_improvement = True
                                            logger.debug(f"Found semantic match: {transcription['text']} → {expected_cantonese}")
                                        elif best_semantic_match and new_semantic_match and new_confidence > best_confidence + 0.1:
                                            # Both are semantic matches, but new one has better confidence
                                            is_improvement = True
                                        elif not best_semantic_match and not new_semantic_match and new_confidence > best_confidence + 0.15:
                                            # Neither are semantic matches, but new one has significantly better confidence
                                            is_improvement = True
                                        
                                        if is_improvement:
                                            logger.debug(f"Found better boundaries for segment {i+1}: "
                                                       f"{new_start:.2f}-{new_end:.2f}s "
                                                       f"(confidence: {current_confidence:.2f} → {new_confidence:.2f}, "
                                                       f"semantic: {best_semantic_match} → {new_semantic_match})")
                                            
                                            best_segment = AudioSegment(
                                                start_time=new_start,
                                                end_time=new_end,
                                                audio_data=new_audio_data,
                                                confidence=new_confidence,
                                                segment_id=segment.segment_id,
                                                audio_file_path=segment.audio_file_path
                                            )
                                            best_confidence = new_confidence
                                            best_semantic_match = new_semantic_match
                                            improvements_found += 1
                                    
                                    except Exception as e:
                                        logger.debug(f"Error testing boundary adjustment: {e}")
                                        continue
                    
                    refined_segments.append(best_segment)
                    
                    if improvements_found > 0:
                        logger.info(f"Improved segment {i+1}: confidence {current_confidence:.2f} → {best_confidence:.2f}, "
                                  f"semantic match: {is_semantic_match} → {best_semantic_match}")
                    else:
                        logger.debug(f"No improvements found for segment {i+1}")
                else:
                    # High confidence segment with semantic match, just update confidence from verification
                    refined_segment = AudioSegment(
                        start_time=segment.start_time,
                        end_time=segment.end_time,
                        audio_data=segment.audio_data,
                        confidence=current_confidence,
                        segment_id=segment.segment_id,
                        audio_file_path=segment.audio_file_path
                    )
                    refined_segments.append(refined_segment)
            else:
                refined_segments.append(segment)
        
        logger.info(f"Boundary refinement complete")
        return refined_segments