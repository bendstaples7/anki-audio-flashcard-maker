"""
Smart boundary detection using silence gap analysis.

This module implements the winning approach from our testing that finds
actual silence gaps between words for precise segmentation.
"""

import logging
from typing import List, Tuple
import numpy as np

from ..models import AudioSegment


logger = logging.getLogger(__name__)


class SmartBoundaryDetector:
    """
    Smart boundary detection that finds actual silence gaps between words.
    
    This is the winning approach that achieved perfect segmentation results
    by analyzing audio energy to find real silence periods.
    """
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize Smart Boundary Detector.
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
        
        # Detection parameters (optimized from testing)
        self.min_gap_duration = 0.05  # Minimum gap to consider (50ms)
        self.silence_threshold = 0.015  # RMS threshold for silence
        self.window_size = int(0.02 * sample_rate)  # 20ms windows
        self.hop_size = int(0.01 * sample_rate)     # 10ms hop
        self.padding = 0.05  # 50ms padding around each segment
    
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
        
        # Find silence regions
        silence_mask = rms_values < self.silence_threshold
        
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
        
        return silence_gaps
    
    def segment_audio(self, audio_data: np.ndarray, expected_count: int, 
                     start_offset: float = 1.0) -> List[AudioSegment]:
        """
        Segment audio using smart boundary detection.
        
        Args:
            audio_data: Audio data array
            expected_count: Expected number of segments
            start_offset: Seconds to skip at beginning
            
        Returns:
            List of AudioSegment objects
        """
        logger.info(f"Smart segmentation: {expected_count} segments expected")
        
        # Find silence gaps
        silence_gaps = self.find_silence_gaps(audio_data)
        
        logger.info(f"Found {len(silence_gaps)} potential silence gaps")
        
        # Filter gaps that are after our start offset
        valid_gaps = [(start, end) for start, end in silence_gaps if start >= start_offset]
        
        logger.info(f"{len(valid_gaps)} gaps after {start_offset}s offset")
        
        # If we have too many gaps, keep the longest ones
        if len(valid_gaps) > expected_count - 1:
            # Sort by gap duration (longest first)
            gap_durations = [(end - start, start, end) for start, end in valid_gaps]
            gap_durations.sort(reverse=True)
            
            # Keep the longest gaps
            selected_gaps = [(start, end) for _, start, end in gap_durations[:expected_count - 1]]
            selected_gaps.sort()  # Sort by time
            valid_gaps = selected_gaps
            
            logger.info(f"Selected {len(valid_gaps)} longest gaps")
        
        # Create segment boundaries
        boundaries = [start_offset]  # Start boundary
        
        for gap_start, gap_end in valid_gaps:
            # Use middle of gap as boundary
            boundary = (gap_start + gap_end) / 2
            boundaries.append(boundary)
        
        # Add end boundary
        total_duration = len(audio_data) / self.sample_rate
        boundaries.append(total_duration - 0.3)  # Leave small buffer at end
        
        logger.info(f"Created {len(boundaries)} boundaries for {len(boundaries)-1} segments")
        
        # Create segments
        segments = []
        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]
            
            # Add small padding to ensure complete words
            padded_start = max(0, start_time - self.padding)
            padded_end = min(total_duration, end_time + self.padding)
            
            # Convert to samples
            start_sample = int(padded_start * self.sample_rate)
            end_sample = int(padded_end * self.sample_rate)
            
            # Extract audio
            segment_audio = audio_data[start_sample:end_sample]
            
            # Create segment
            segment = AudioSegment(
                start_time=padded_start,
                end_time=padded_end,
                audio_data=segment_audio,
                confidence=0.8,  # Good confidence for gap-based detection
                segment_id=f"smart_{i+1:03d}"
            )
            
            segments.append(segment)
        
        logger.info(f"Generated {len(segments)} smart audio segments")
        return segments