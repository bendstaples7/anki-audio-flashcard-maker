"""
Word boundary detection algorithms for audio segmentation.

Implements energy-based and spectral analysis methods that work
without clear silence boundaries between words.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np
import librosa
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from sklearn.preprocessing import StandardScaler

from .vad import SpeechRegion


logger = logging.getLogger(__name__)


class WordBoundary:
    """Represents a detected word boundary with timing and confidence."""
    
    def __init__(self, time: float, confidence: float = 1.0, boundary_type: str = 'detected'):
        self.time = time
        self.confidence = confidence
        self.boundary_type = boundary_type  # 'detected', 'forced', 'silence'
    
    def __repr__(self) -> str:
        return f"WordBoundary({self.time:.3f}s, conf={self.confidence:.2f}, type={self.boundary_type})"


class WordSegmenter:
    """
    Word boundary detection using multiple acoustic features.
    
    Combines energy, spectral, and temporal analysis to identify
    word boundaries even without clear silence gaps.
    """
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize Word Segmenter.
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
        
        # Analysis parameters
        self.frame_length = 2048
        self.hop_length = 512
        self.n_mels = 13  # Number of mel-frequency bands
        
        # Boundary detection parameters
        self.min_word_duration = 0.2  # Minimum word duration (seconds)
        self.max_word_duration = 3.0  # Maximum word duration (seconds)
        self.boundary_smoothing = 0.05  # Gaussian smoothing sigma (seconds)
        
        # Feature weights for boundary detection
        self.energy_weight = 0.3
        self.spectral_weight = 0.4
        self.temporal_weight = 0.3
    
    def segment_speech_region(self, audio_data: np.ndarray, 
                            speech_region: SpeechRegion,
                            expected_word_count: int) -> List[WordBoundary]:
        """
        Segment a speech region into word boundaries.
        
        Args:
            audio_data: Full audio data array
            speech_region: Speech region to segment
            expected_word_count: Expected number of words in the region
            
        Returns:
            List of detected word boundaries
        """
        # Extract audio segment
        start_sample = int(speech_region.start_time * self.sample_rate)
        end_sample = int(speech_region.end_time * self.sample_rate)
        segment = audio_data[start_sample:end_sample]
        
        if len(segment) == 0:
            logger.warning("Empty speech segment")
            return []
        
        logger.info(
            f"Segmenting speech region {speech_region.start_time:.2f}-{speech_region.end_time:.2f}s "
            f"({speech_region.duration:.2f}s) into {expected_word_count} words"
        )
        
        # Extract multiple acoustic features
        features = self._extract_features(segment)
        
        # Detect boundaries using combined features
        boundaries = self._detect_boundaries(features, expected_word_count)
        
        # Convert relative times to absolute times
        absolute_boundaries = []
        for boundary in boundaries:
            absolute_time = speech_region.start_time + boundary.time
            absolute_boundaries.append(WordBoundary(
                absolute_time, 
                boundary.confidence, 
                boundary.boundary_type
            ))
        
        # Ensure we have start and end boundaries
        absolute_boundaries = self._ensure_region_boundaries(
            absolute_boundaries, speech_region
        )
        
        # Validate and adjust boundaries
        absolute_boundaries = self._validate_boundaries(
            absolute_boundaries, expected_word_count
        )
        
        logger.info(f"Detected {len(absolute_boundaries)-1} word segments")
        return absolute_boundaries
    
    def _extract_features(self, audio_segment: np.ndarray) -> dict:
        """
        Extract acoustic features for boundary detection.
        
        Args:
            audio_segment: Audio segment to analyze
            
        Returns:
            Dictionary of extracted features
        """
        # Time axis for features
        times = librosa.frames_to_time(
            np.arange(len(audio_segment) // self.hop_length),
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # 1. Energy-based features
        rms_energy = librosa.feature.rms(
            y=audio_segment,
            frame_length=self.frame_length,
            hop_length=self.hop_length
        )[0]
        
        # Energy derivative (rate of change)
        energy_derivative = np.gradient(rms_energy)
        
        # 2. Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(
            y=audio_segment,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )[0]
        
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio_segment,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )[0]
        
        # Mel-frequency cepstral coefficients
        mfccs = librosa.feature.mfcc(
            y=audio_segment,
            sr=self.sample_rate,
            n_mfcc=self.n_mels,
            hop_length=self.hop_length
        )
        
        # Spectral contrast
        spectral_contrast = librosa.feature.spectral_contrast(
            y=audio_segment,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # 3. Temporal features
        zero_crossing_rate = librosa.feature.zero_crossing_rate(
            audio_segment,
            frame_length=self.frame_length,
            hop_length=self.hop_length
        )[0]
        
        return {
            'times': times,
            'rms_energy': rms_energy,
            'energy_derivative': energy_derivative,
            'spectral_centroids': spectral_centroids,
            'spectral_rolloff': spectral_rolloff,
            'mfccs': mfccs,
            'spectral_contrast': spectral_contrast,
            'zero_crossing_rate': zero_crossing_rate
        }
    
    def _detect_boundaries(self, features: dict, expected_word_count: int) -> List[WordBoundary]:
        """
        Detect word boundaries using combined acoustic features.
        
        Args:
            features: Dictionary of extracted features
            expected_word_count: Expected number of words
            
        Returns:
            List of detected word boundaries
        """
        times = features['times']
        
        # Calculate boundary likelihood from different features
        energy_boundaries = self._energy_based_boundaries(features)
        spectral_boundaries = self._spectral_based_boundaries(features)
        temporal_boundaries = self._temporal_based_boundaries(features)
        
        # Combine boundary likelihoods
        combined_likelihood = (
            self.energy_weight * energy_boundaries +
            self.spectral_weight * spectral_boundaries +
            self.temporal_weight * temporal_boundaries
        )
        
        # Smooth the likelihood function
        sigma_samples = int(self.boundary_smoothing * self.sample_rate / self.hop_length)
        if sigma_samples > 0:
            combined_likelihood = gaussian_filter1d(combined_likelihood, sigma=sigma_samples)
        
        # Find peaks in the likelihood function
        boundaries = self._find_boundary_peaks(
            combined_likelihood, times, expected_word_count
        )
        
        return boundaries
    
    def _energy_based_boundaries(self, features: dict) -> np.ndarray:
        """
        Detect boundaries based on energy changes.
        
        Args:
            features: Dictionary of extracted features
            
        Returns:
            Array of energy-based boundary likelihoods
        """
        rms_energy = features['rms_energy']
        energy_derivative = features['energy_derivative']
        
        # Normalize features
        rms_normalized = (rms_energy - np.mean(rms_energy)) / (np.std(rms_energy) + 1e-8)
        derivative_normalized = (energy_derivative - np.mean(energy_derivative)) / (np.std(energy_derivative) + 1e-8)
        
        # Energy valleys (low energy regions)
        energy_valleys = -rms_normalized
        
        # Energy transitions (high derivative magnitude)
        energy_transitions = np.abs(derivative_normalized)
        
        # Combine energy cues
        energy_boundaries = 0.6 * energy_valleys + 0.4 * energy_transitions
        
        # Apply non-maximum suppression
        energy_boundaries = np.maximum(energy_boundaries, 0)
        
        return energy_boundaries
    
    def _spectral_based_boundaries(self, features: dict) -> np.ndarray:
        """
        Detect boundaries based on spectral changes.
        
        Args:
            features: Dictionary of extracted features
            
        Returns:
            Array of spectral-based boundary likelihoods
        """
        spectral_centroids = features['spectral_centroids']
        mfccs = features['mfccs']
        spectral_contrast = features['spectral_contrast']
        
        # Spectral centroid changes
        centroid_derivative = np.abs(np.gradient(spectral_centroids))
        centroid_normalized = (centroid_derivative - np.mean(centroid_derivative)) / (np.std(centroid_derivative) + 1e-8)
        
        # MFCC changes (spectral shape changes)
        mfcc_derivatives = np.abs(np.gradient(mfccs, axis=1))
        mfcc_change = np.mean(mfcc_derivatives, axis=0)
        mfcc_normalized = (mfcc_change - np.mean(mfcc_change)) / (np.std(mfcc_change) + 1e-8)
        
        # Spectral contrast changes
        contrast_derivatives = np.abs(np.gradient(spectral_contrast, axis=1))
        contrast_change = np.mean(contrast_derivatives, axis=0)
        contrast_normalized = (contrast_change - np.mean(contrast_change)) / (np.std(contrast_change) + 1e-8)
        
        # Combine spectral cues
        spectral_boundaries = (
            0.4 * centroid_normalized +
            0.4 * mfcc_normalized +
            0.2 * contrast_normalized
        )
        
        return np.maximum(spectral_boundaries, 0)
    
    def _temporal_based_boundaries(self, features: dict) -> np.ndarray:
        """
        Detect boundaries based on temporal features.
        
        Args:
            features: Dictionary of extracted features
            
        Returns:
            Array of temporal-based boundary likelihoods
        """
        zero_crossing_rate = features['zero_crossing_rate']
        
        # Zero crossing rate changes
        zcr_derivative = np.abs(np.gradient(zero_crossing_rate))
        zcr_normalized = (zcr_derivative - np.mean(zcr_derivative)) / (np.std(zcr_derivative) + 1e-8)
        
        # Rhythm-based boundaries (periodic patterns)
        # Use autocorrelation to find rhythmic patterns
        if len(zero_crossing_rate) > 20:
            autocorr = np.correlate(zero_crossing_rate, zero_crossing_rate, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            
            # Find periodic peaks
            rhythm_peaks, _ = find_peaks(autocorr, height=np.max(autocorr) * 0.3)
            rhythm_boundaries = np.zeros_like(zcr_normalized)
            
            if len(rhythm_peaks) > 0:
                # Mark rhythmic boundary locations
                for peak in rhythm_peaks:
                    if peak < len(rhythm_boundaries):
                        rhythm_boundaries[peak] = 1.0
        else:
            rhythm_boundaries = np.zeros_like(zcr_normalized)
        
        # Combine temporal cues
        temporal_boundaries = 0.7 * zcr_normalized + 0.3 * rhythm_boundaries
        
        return np.maximum(temporal_boundaries, 0)
    
    def _find_boundary_peaks(self, likelihood: np.ndarray, 
                           times: np.ndarray, 
                           expected_word_count: int) -> List[WordBoundary]:
        """
        Find word boundary peaks in the likelihood function.
        
        Args:
            likelihood: Combined boundary likelihood
            times: Time array corresponding to likelihood
            expected_word_count: Expected number of words
            
        Returns:
            List of detected word boundaries
        """
        # Adaptive threshold based on expected word count
        if expected_word_count > 1:
            # We need (expected_word_count - 1) internal boundaries
            target_boundaries = expected_word_count - 1
            
            # Find peaks with adaptive threshold
            threshold = np.percentile(likelihood, 70)  # Start with 70th percentile
            
            for attempt in range(5):  # Try up to 5 different thresholds
                peaks, properties = find_peaks(
                    likelihood,
                    height=threshold,
                    distance=int(self.min_word_duration * self.sample_rate / self.hop_length)
                )
                
                if len(peaks) >= target_boundaries * 0.7:  # Accept if we get at least 70% of expected
                    break
                
                threshold *= 0.8  # Lower threshold and try again
            
            # If we have too many peaks, keep the strongest ones
            if len(peaks) > target_boundaries * 1.5:
                peak_heights = properties['peak_heights']
                strongest_indices = np.argsort(peak_heights)[-target_boundaries:]
                peaks = peaks[strongest_indices]
                peaks = np.sort(peaks)  # Sort by time
        else:
            # Single word, no internal boundaries needed
            peaks = []
        
        # Convert peaks to boundaries
        boundaries = []
        for peak in peaks:
            if peak < len(times):
                confidence = likelihood[peak] / (np.max(likelihood) + 1e-8)
                boundaries.append(WordBoundary(
                    times[peak], 
                    confidence, 
                    'detected'
                ))
        
        return boundaries
    
    def _ensure_region_boundaries(self, boundaries: List[WordBoundary], 
                                speech_region: SpeechRegion) -> List[WordBoundary]:
        """
        Ensure speech region has start and end boundaries.
        
        Args:
            boundaries: List of detected boundaries
            speech_region: Speech region being segmented
            
        Returns:
            List of boundaries including start and end
        """
        result = boundaries.copy()
        
        # Add start boundary if not present
        if not result or result[0].time > speech_region.start_time + 0.01:
            result.insert(0, WordBoundary(
                speech_region.start_time, 
                1.0, 
                'forced'
            ))
        
        # Add end boundary if not present
        if not result or result[-1].time < speech_region.end_time - 0.01:
            result.append(WordBoundary(
                speech_region.end_time, 
                1.0, 
                'forced'
            ))
        
        # Sort by time
        result.sort(key=lambda b: b.time)
        
        return result
    
    def _validate_boundaries(self, boundaries: List[WordBoundary], 
                           expected_word_count: int) -> List[WordBoundary]:
        """
        Validate and adjust boundaries to meet constraints.
        
        Args:
            boundaries: List of boundaries to validate
            expected_word_count: Expected number of words
            
        Returns:
            Validated and adjusted boundaries
        """
        if len(boundaries) < 2:
            return boundaries
        
        # Remove boundaries that create segments that are too short
        validated = [boundaries[0]]  # Always keep start boundary
        
        for i in range(1, len(boundaries)):
            prev_time = validated[-1].time
            curr_time = boundaries[i].time
            
            # Check minimum duration
            if curr_time - prev_time >= self.min_word_duration:
                validated.append(boundaries[i])
            elif i == len(boundaries) - 1:
                # Always keep end boundary, but adjust if needed
                min_end_time = prev_time + self.min_word_duration
                if curr_time < min_end_time:
                    boundaries[i].time = min_end_time
                validated.append(boundaries[i])
        
        # If we have too few segments, add boundaries by equal division
        num_segments = len(validated) - 1
        if num_segments < expected_word_count and expected_word_count > 1:
            total_duration = validated[-1].time - validated[0].time
            target_duration = total_duration / expected_word_count
            
            # Add evenly spaced boundaries
            new_boundaries = [validated[0]]
            for i in range(1, expected_word_count):
                boundary_time = validated[0].time + i * target_duration
                new_boundaries.append(WordBoundary(
                    boundary_time, 
                    0.5, 
                    'forced'
                ))
            new_boundaries.append(validated[-1])
            
            validated = new_boundaries
        
        return validated