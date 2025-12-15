"""
Audio clip generation and quality preservation module.

Creates individual audio clips from segmented boundaries with
quality preservation, smoothing, and fade effects.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
import librosa
import soundfile as sf
from scipy import signal

from ..models import AudioSegment
from .segmentation import WordBoundary


logger = logging.getLogger(__name__)


class AudioClipGenerator:
    """
    Generates individual audio clips from word boundaries with quality preservation.
    
    Handles clip extraction, smoothing, fade effects, and format conversion
    to ensure audio quality suitable for pronunciation learning.
    """
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize Audio Clip Generator.
        
        Args:
            sample_rate: Target sample rate for generated clips
        """
        self.sample_rate = sample_rate
        
        # Quality preservation parameters
        self.fade_duration = 0.01  # Fade in/out duration (seconds)
        self.padding_duration = 0.05  # Padding before/after word (seconds)
        self.normalize_clips = True  # Whether to normalize clip volumes
        self.target_peak_level = 0.8  # Target peak level for normalization
        
        # Smoothing parameters
        self.apply_smoothing = True
        self.smoothing_window_size = 5  # Samples for boundary smoothing
        
        # Output format parameters
        self.output_format = 'wav'  # Default output format
        self.bit_depth = 16  # Bit depth for output files
    
    def generate_clips_from_boundaries(self, 
                                     audio_data: np.ndarray,
                                     boundaries: List[WordBoundary],
                                     output_dir: str,
                                     base_filename: str = "word") -> List[AudioSegment]:
        """
        Generate audio clips from word boundaries.
        
        Args:
            audio_data: Full audio data array
            boundaries: List of word boundaries
            output_dir: Directory to save audio clips
            base_filename: Base filename for generated clips
            
        Returns:
            List of AudioSegment objects with file paths
        """
        if len(boundaries) < 2:
            logger.warning("Need at least 2 boundaries to create clips")
            return []
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        clips = []
        
        # Generate clips between consecutive boundaries
        for i in range(len(boundaries) - 1):
            start_boundary = boundaries[i]
            end_boundary = boundaries[i + 1]
            
            # Create audio segment
            segment = self._create_audio_segment(
                audio_data,
                start_boundary.time,
                end_boundary.time,
                segment_id=f"{base_filename}_{i+1:03d}"
            )
            
            if segment is not None:
                # Generate output filename
                output_filename = f"{base_filename}_{i+1:03d}.{self.output_format}"
                output_filepath = output_path / output_filename
                
                # Save audio clip
                success = self._save_audio_clip(
                    segment.audio_data,
                    str(output_filepath)
                )
                
                if success:
                    # Update segment with file path
                    segment.audio_file_path = str(output_filepath)
                    clips.append(segment)
                    
                    logger.debug(
                        f"Generated clip {i+1}: {start_boundary.time:.3f}-{end_boundary.time:.3f}s "
                        f"-> {output_filename}"
                    )
        
        logger.info(f"Generated {len(clips)} audio clips in {output_dir}")
        return clips
    
    def _create_audio_segment(self, 
                            audio_data: np.ndarray,
                            start_time: float,
                            end_time: float,
                            segment_id: str) -> Optional[AudioSegment]:
        """
        Create an audio segment with quality preservation.
        
        Args:
            audio_data: Full audio data array
            start_time: Start time in seconds
            end_time: End time in seconds
            segment_id: Unique identifier for the segment
            
        Returns:
            AudioSegment object or None if creation fails
        """
        # Calculate sample indices with padding
        padding_samples = int(self.padding_duration * self.sample_rate)
        start_sample = max(0, int(start_time * self.sample_rate) - padding_samples)
        end_sample = min(len(audio_data), int(end_time * self.sample_rate) + padding_samples)
        
        if end_sample <= start_sample:
            logger.warning(f"Invalid segment boundaries: {start_time}-{end_time}s")
            return None
        
        # Extract audio segment
        segment_audio = audio_data[start_sample:end_sample].copy()
        
        # Apply quality preservation techniques
        segment_audio = self._preserve_audio_quality(segment_audio)
        
        # Calculate confidence based on segment length and audio quality
        duration = (end_sample - start_sample) / self.sample_rate
        confidence = self._calculate_segment_confidence(segment_audio, duration)
        
        # Adjust times to account for padding
        actual_start_time = start_sample / self.sample_rate
        actual_end_time = end_sample / self.sample_rate
        
        return AudioSegment(
            start_time=actual_start_time,
            end_time=actual_end_time,
            audio_data=segment_audio,
            confidence=confidence,
            segment_id=segment_id
        )
    
    def _preserve_audio_quality(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply quality preservation techniques to audio segment.
        
        Args:
            audio_data: Input audio segment
            
        Returns:
            Quality-preserved audio segment
        """
        processed_audio = audio_data.copy()
        
        # 1. Apply boundary smoothing to reduce clicks/pops
        if self.apply_smoothing and len(processed_audio) > self.smoothing_window_size * 2:
            processed_audio = self._smooth_boundaries(processed_audio)
        
        # 2. Apply fade in/out to prevent abrupt starts/ends
        processed_audio = self._apply_fade_effects(processed_audio)
        
        # 3. Normalize volume if requested
        if self.normalize_clips:
            processed_audio = self._normalize_volume(processed_audio)
        
        # 4. Apply gentle high-pass filter to remove low-frequency noise
        processed_audio = self._apply_high_pass_filter(processed_audio)
        
        return processed_audio
    
    def _smooth_boundaries(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Smooth audio boundaries to reduce clicks and pops.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Smoothed audio data
        """
        smoothed = audio_data.copy()
        window_size = self.smoothing_window_size
        
        # Smooth start boundary
        if len(smoothed) > window_size:
            start_window = smoothed[:window_size]
            smoothed_start = signal.savgol_filter(start_window, window_size, 2)
            smoothed[:window_size] = smoothed_start
        
        # Smooth end boundary
        if len(smoothed) > window_size:
            end_window = smoothed[-window_size:]
            smoothed_end = signal.savgol_filter(end_window, window_size, 2)
            smoothed[-window_size:] = smoothed_end
        
        return smoothed
    
    def _apply_fade_effects(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply fade in/out effects to prevent abrupt starts and ends.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Audio data with fade effects
        """
        if len(audio_data) == 0:
            return audio_data
        
        faded = audio_data.copy()
        fade_samples = int(self.fade_duration * self.sample_rate)
        
        # Ensure fade duration doesn't exceed half the audio length
        fade_samples = min(fade_samples, len(faded) // 4)
        
        if fade_samples > 0:
            # Create fade curves (cosine-based for smooth transition)
            fade_in = 0.5 * (1 - np.cos(np.linspace(0, np.pi, fade_samples)))
            fade_out = 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade_samples)))
            
            # Apply fade in
            faded[:fade_samples] *= fade_in
            
            # Apply fade out
            faded[-fade_samples:] *= fade_out
        
        return faded
    
    def _normalize_volume(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Normalize audio volume to target peak level.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Volume-normalized audio data
        """
        if len(audio_data) == 0:
            return audio_data
        
        # Find current peak level
        current_peak = np.max(np.abs(audio_data))
        
        if current_peak > 1e-8:  # Avoid division by zero
            # Calculate normalization factor
            normalization_factor = self.target_peak_level / current_peak
            
            # Apply normalization (with safety limit)
            normalization_factor = min(normalization_factor, 10.0)  # Max 20dB gain
            normalized = audio_data * normalization_factor
        else:
            normalized = audio_data
        
        return normalized
    
    def _apply_high_pass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply gentle high-pass filter to remove low-frequency noise.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Filtered audio data
        """
        if len(audio_data) < 100:  # Skip filtering for very short clips
            return audio_data
        
        # Design high-pass filter (80 Hz cutoff)
        cutoff_freq = 80.0  # Hz
        nyquist_freq = self.sample_rate / 2
        normalized_cutoff = cutoff_freq / nyquist_freq
        
        # Use a gentle 2nd order Butterworth filter
        b, a = signal.butter(2, normalized_cutoff, btype='high')
        
        # Apply filter with zero-phase filtering to avoid phase distortion
        try:
            filtered = signal.filtfilt(b, a, audio_data)
        except Exception as e:
            logger.warning(f"High-pass filtering failed: {e}")
            filtered = audio_data  # Return original if filtering fails
        
        return filtered
    
    def _calculate_segment_confidence(self, audio_data: np.ndarray, duration: float) -> float:
        """
        Calculate confidence score for audio segment quality.
        
        Args:
            audio_data: Audio segment data
            duration: Segment duration in seconds
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if len(audio_data) == 0:
            return 0.0
        
        confidence_factors = []
        
        # 1. Duration factor (prefer segments of reasonable length)
        ideal_duration = 1.0  # seconds
        duration_factor = 1.0 - abs(duration - ideal_duration) / ideal_duration
        duration_factor = max(0.0, min(1.0, duration_factor))
        confidence_factors.append(duration_factor * 0.3)
        
        # 2. Signal-to-noise ratio estimate
        rms_level = np.sqrt(np.mean(audio_data ** 2))
        if rms_level > 1e-8:
            # Estimate noise floor from quietest 10% of samples
            sorted_abs = np.sort(np.abs(audio_data))
            noise_floor = np.mean(sorted_abs[:len(sorted_abs)//10])
            snr_estimate = 20 * np.log10(rms_level / (noise_floor + 1e-8))
            snr_factor = min(1.0, max(0.0, (snr_estimate - 10) / 30))  # 10-40 dB range
        else:
            snr_factor = 0.0
        confidence_factors.append(snr_factor * 0.4)
        
        # 3. Dynamic range factor
        peak_level = np.max(np.abs(audio_data))
        if peak_level > 1e-8:
            dynamic_range = 20 * np.log10(peak_level / (rms_level + 1e-8))
            range_factor = min(1.0, max(0.0, (dynamic_range - 3) / 15))  # 3-18 dB range
        else:
            range_factor = 0.0
        confidence_factors.append(range_factor * 0.3)
        
        # Combine factors
        total_confidence = sum(confidence_factors)
        return max(0.1, min(1.0, total_confidence))  # Clamp to reasonable range
    
    def _save_audio_clip(self, audio_data: np.ndarray, output_path: str) -> bool:
        """
        Save audio clip to file with appropriate format and quality.
        
        Args:
            audio_data: Audio data to save
            output_path: Output file path
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure audio is in valid range
            audio_data = np.clip(audio_data, -1.0, 1.0)
            
            # Save using soundfile for better format support
            sf.write(
                output_path,
                audio_data,
                self.sample_rate,
                subtype=f'PCM_{self.bit_depth}'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio clip {output_path}: {e}")
            return False
    
    def set_quality_parameters(self, 
                             fade_duration: Optional[float] = None,
                             padding_duration: Optional[float] = None,
                             normalize_clips: Optional[bool] = None,
                             target_peak_level: Optional[float] = None):
        """
        Update quality preservation parameters.
        
        Args:
            fade_duration: Fade in/out duration in seconds
            padding_duration: Padding before/after word in seconds
            normalize_clips: Whether to normalize clip volumes
            target_peak_level: Target peak level for normalization (0.0-1.0)
        """
        if fade_duration is not None:
            self.fade_duration = max(0.0, fade_duration)
        
        if padding_duration is not None:
            self.padding_duration = max(0.0, padding_duration)
        
        if normalize_clips is not None:
            self.normalize_clips = normalize_clips
        
        if target_peak_level is not None:
            self.target_peak_level = max(0.1, min(1.0, target_peak_level))
        
        logger.info(f"Updated quality parameters: fade={self.fade_duration}s, "
                   f"padding={self.padding_duration}s, normalize={self.normalize_clips}")
    
    def get_clip_info(self, audio_segment: AudioSegment) -> dict:
        """
        Get information about an audio clip.
        
        Args:
            audio_segment: AudioSegment to analyze
            
        Returns:
            Dictionary with clip information
        """
        audio_data = audio_segment.audio_data
        
        return {
            'segment_id': audio_segment.segment_id,
            'duration': audio_segment.end_time - audio_segment.start_time,
            'sample_count': len(audio_data),
            'peak_level': np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.0,
            'rms_level': np.sqrt(np.mean(audio_data ** 2)) if len(audio_data) > 0 else 0.0,
            'confidence': audio_segment.confidence,
            'file_path': getattr(audio_segment, 'audio_file_path', None)
        }