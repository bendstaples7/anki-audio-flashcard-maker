"""
Voice Activity Detection (VAD) module for identifying speech regions.

Uses webrtcvad and energy-based methods to handle background noise
and varying audio quality conditions.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np
import librosa
from scipy import signal
from scipy.ndimage import binary_dilation, binary_erosion

# Try to import webrtcvad, but make it optional
try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    webrtcvad = None


logger = logging.getLogger(__name__)


class SpeechRegion:
    """Represents a detected speech region with timing and confidence."""
    
    def __init__(self, start_time: float, end_time: float, confidence: float = 1.0):
        self.start_time = start_time
        self.end_time = end_time
        self.confidence = confidence
        self.duration = end_time - start_time
    
    def __repr__(self) -> str:
        return f"SpeechRegion({self.start_time:.3f}s-{self.end_time:.3f}s, conf={self.confidence:.2f})"


class VoiceActivityDetector:
    """
    Voice Activity Detection using multiple methods for robustness.
    
    Combines WebRTC VAD with energy-based detection to handle
    various audio conditions and background noise.
    """
    
    def __init__(self, 
                 sample_rate: int = 16000,
                 frame_duration: int = 30,  # ms
                 aggressiveness: int = 2):
        """
        Initialize Voice Activity Detector.
        
        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000)
            frame_duration: Frame duration in milliseconds (10, 20, or 30)
            aggressiveness: WebRTC VAD aggressiveness (0-3, higher = more aggressive)
        """
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration
        self.aggressiveness = aggressiveness
        
        # Initialize WebRTC VAD if available
        if WEBRTC_AVAILABLE:
            # Validate WebRTC VAD parameters
            if sample_rate not in [8000, 16000, 32000, 48000]:
                logger.warning(f"Unsupported sample rate for WebRTC VAD: {sample_rate}, using energy-based VAD only")
                self.vad = None
            elif frame_duration not in [10, 20, 30]:
                logger.warning(f"Unsupported frame duration for WebRTC VAD: {frame_duration}, using energy-based VAD only")
                self.vad = None
            else:
                self.vad = webrtcvad.Vad(aggressiveness)
        else:
            logger.warning("WebRTC VAD not available, using energy-based VAD only")
            self.vad = None
        
        # Frame size in samples
        self.frame_size = int(sample_rate * frame_duration / 1000)
        
        # Energy-based VAD parameters
        self.energy_threshold_percentile = 20  # Percentile for energy threshold
        self.min_speech_duration = 0.1  # Minimum speech region duration (seconds)
        self.max_silence_gap = 0.2  # Maximum gap to bridge between speech regions
    
    def detect_speech_regions(self, audio_data: np.ndarray, 
                            use_webrtc: bool = True,
                            use_energy: bool = True) -> List[SpeechRegion]:
        """
        Detect speech regions in audio using multiple VAD methods.
        
        Args:
            audio_data: Audio data array
            use_webrtc: Whether to use WebRTC VAD
            use_energy: Whether to use energy-based VAD
            
        Returns:
            List of detected speech regions
        """
        logger.info(f"Detecting speech regions in {len(audio_data)/self.sample_rate:.2f}s audio")
        
        speech_regions = []
        
        # Use WebRTC VAD if available and requested
        if use_webrtc and self.vad is not None and len(audio_data) > 0:
            webrtc_regions = self._webrtc_vad(audio_data)
            speech_regions.extend(webrtc_regions)
            logger.debug(f"WebRTC VAD found {len(webrtc_regions)} regions")
        
        # Energy-based VAD
        if use_energy and len(audio_data) > 0:
            energy_regions = self._energy_vad(audio_data)
            speech_regions.extend(energy_regions)
            logger.debug(f"Energy VAD found {len(energy_regions)} regions")
        
        # Combine and merge overlapping regions
        if speech_regions:
            merged_regions = self._merge_regions(speech_regions)
            logger.info(f"Final merged regions: {len(merged_regions)}")
            return merged_regions
        else:
            # Fallback: treat entire audio as speech if no regions detected
            logger.warning("No speech regions detected, using entire audio")
            return [SpeechRegion(0.0, len(audio_data) / self.sample_rate, confidence=0.5)]
    
    def _webrtc_vad(self, audio_data: np.ndarray) -> List[SpeechRegion]:
        """
        Use WebRTC VAD to detect speech regions.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            List of speech regions detected by WebRTC VAD
        """
        # Convert to 16-bit PCM format required by WebRTC VAD
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Pad audio to ensure complete frames
        num_frames = len(audio_int16) // self.frame_size
        padded_length = num_frames * self.frame_size
        if padded_length < len(audio_int16):
            num_frames += 1
            padded_length = num_frames * self.frame_size
        
        padded_audio = np.zeros(padded_length, dtype=np.int16)
        padded_audio[:len(audio_int16)] = audio_int16
        
        # Process frames
        speech_frames = []
        for i in range(num_frames):
            start_idx = i * self.frame_size
            end_idx = start_idx + self.frame_size
            frame = padded_audio[start_idx:end_idx]
            
            # Convert frame to bytes
            frame_bytes = frame.tobytes()
            
            try:
                is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)
                speech_frames.append(is_speech)
            except Exception as e:
                logger.warning(f"WebRTC VAD error on frame {i}: {e}")
                speech_frames.append(False)
        
        # Convert frame-level decisions to time regions
        regions = self._frames_to_regions(speech_frames)
        return regions
    
    def _energy_vad(self, audio_data: np.ndarray) -> List[SpeechRegion]:
        """
        Use energy-based VAD to detect speech regions.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            List of speech regions detected by energy analysis
        """
        # Calculate frame-wise energy
        hop_length = self.frame_size // 2  # 50% overlap
        frame_length = self.frame_size
        
        # Compute RMS energy for each frame
        rms_energy = librosa.feature.rms(
            y=audio_data,
            frame_length=frame_length,
            hop_length=hop_length
        )[0]
        
        # Calculate adaptive threshold
        energy_threshold = np.percentile(rms_energy, self.energy_threshold_percentile)
        
        # Apply threshold with hysteresis
        high_threshold = energy_threshold * 2.0
        low_threshold = energy_threshold * 0.5
        
        speech_frames = self._apply_hysteresis_threshold(
            rms_energy, high_threshold, low_threshold
        )
        
        # Apply morphological operations to clean up detection
        speech_frames = self._clean_speech_frames(speech_frames)
        
        # Convert to time regions
        frame_times = librosa.frames_to_time(
            np.arange(len(speech_frames)),
            sr=self.sample_rate,
            hop_length=hop_length
        )
        
        regions = []
        in_speech = False
        start_time = 0.0
        
        for i, is_speech in enumerate(speech_frames):
            current_time = frame_times[i]
            
            if is_speech and not in_speech:
                # Start of speech region
                start_time = current_time
                in_speech = True
            elif not is_speech and in_speech:
                # End of speech region
                end_time = current_time
                if end_time - start_time >= self.min_speech_duration:
                    regions.append(SpeechRegion(start_time, end_time, confidence=0.8))
                in_speech = False
        
        # Handle case where speech continues to end of audio
        if in_speech:
            end_time = len(audio_data) / self.sample_rate
            if end_time - start_time >= self.min_speech_duration:
                regions.append(SpeechRegion(start_time, end_time, confidence=0.8))
        
        return regions
    
    def _apply_hysteresis_threshold(self, signal: np.ndarray, 
                                  high_thresh: float, 
                                  low_thresh: float) -> np.ndarray:
        """
        Apply hysteresis thresholding to reduce noise in VAD decisions.
        
        Args:
            signal: Input signal (energy values)
            high_thresh: High threshold for speech detection
            low_thresh: Low threshold for speech continuation
            
        Returns:
            Boolean array indicating speech frames
        """
        speech_frames = np.zeros(len(signal), dtype=bool)
        in_speech = False
        
        for i, value in enumerate(signal):
            if not in_speech and value > high_thresh:
                in_speech = True
            elif in_speech and value < low_thresh:
                in_speech = False
            
            speech_frames[i] = in_speech
        
        return speech_frames
    
    def _clean_speech_frames(self, speech_frames: np.ndarray) -> np.ndarray:
        """
        Clean up speech frame decisions using morphological operations.
        
        Args:
            speech_frames: Boolean array of speech frame decisions
            
        Returns:
            Cleaned speech frame decisions
        """
        # Remove isolated speech frames (erosion followed by dilation)
        cleaned = binary_erosion(speech_frames, iterations=1)
        cleaned = binary_dilation(cleaned, iterations=2)
        
        # Fill small gaps in speech regions
        cleaned = binary_dilation(cleaned, iterations=1)
        cleaned = binary_erosion(cleaned, iterations=1)
        
        return cleaned
    
    def _frames_to_regions(self, speech_frames: List[bool]) -> List[SpeechRegion]:
        """
        Convert frame-level speech decisions to time regions.
        
        Args:
            speech_frames: List of boolean speech decisions per frame
            
        Returns:
            List of speech regions
        """
        regions = []
        in_speech = False
        start_frame = 0
        
        frame_duration_sec = self.frame_duration / 1000.0
        
        for i, is_speech in enumerate(speech_frames):
            if is_speech and not in_speech:
                # Start of speech region
                start_frame = i
                in_speech = True
            elif not is_speech and in_speech:
                # End of speech region
                start_time = start_frame * frame_duration_sec
                end_time = i * frame_duration_sec
                
                if end_time - start_time >= self.min_speech_duration:
                    regions.append(SpeechRegion(start_time, end_time, confidence=0.9))
                in_speech = False
        
        # Handle case where speech continues to end
        if in_speech:
            start_time = start_frame * frame_duration_sec
            end_time = len(speech_frames) * frame_duration_sec
            if end_time - start_time >= self.min_speech_duration:
                regions.append(SpeechRegion(start_time, end_time, confidence=0.9))
        
        return regions
    
    def _merge_regions(self, regions: List[SpeechRegion]) -> List[SpeechRegion]:
        """
        Merge overlapping or nearby speech regions.
        
        Args:
            regions: List of speech regions to merge
            
        Returns:
            List of merged speech regions
        """
        if not regions:
            return []
        
        # Sort regions by start time
        sorted_regions = sorted(regions, key=lambda r: r.start_time)
        
        merged = []
        current = sorted_regions[0]
        
        for next_region in sorted_regions[1:]:
            # Check if regions should be merged
            gap = next_region.start_time - current.end_time
            
            if gap <= self.max_silence_gap:
                # Merge regions
                current = SpeechRegion(
                    current.start_time,
                    max(current.end_time, next_region.end_time),
                    confidence=min(current.confidence, next_region.confidence)
                )
            else:
                # Add current region and start new one
                if current.duration >= self.min_speech_duration:
                    merged.append(current)
                current = next_region
        
        # Add the last region
        if current.duration >= self.min_speech_duration:
            merged.append(current)
        
        return merged
    
    def get_speech_ratio(self, audio_data: np.ndarray) -> float:
        """
        Calculate the ratio of speech to total audio duration.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            Speech ratio (0.0 to 1.0)
        """
        regions = self.detect_speech_regions(audio_data)
        total_speech_duration = sum(region.duration for region in regions)
        total_duration = len(audio_data) / self.sample_rate
        
        return total_speech_duration / total_duration if total_duration > 0 else 0.0