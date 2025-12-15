"""
Audio file validation and loading module.

Supports multiple audio formats (MP3, WAV, M4A) with quality validation
and preprocessing capabilities.
"""

import os
import logging
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import librosa
import soundfile as sf
from scipy.io import wavfile


logger = logging.getLogger(__name__)


class AudioValidationError(Exception):
    """Raised when audio file validation fails."""
    pass


class AudioLoader:
    """Handles audio file loading, validation, and format conversion."""
    
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
    MIN_DURATION = 1.0  # Minimum duration in seconds
    MAX_DURATION = 3600.0  # Maximum duration in seconds (1 hour)
    MIN_SAMPLE_RATE = 8000  # Minimum sample rate in Hz
    PREFERRED_SAMPLE_RATE = 22050  # Preferred sample rate for processing
    
    def __init__(self, target_sample_rate: int = PREFERRED_SAMPLE_RATE):
        """
        Initialize AudioLoader.
        
        Args:
            target_sample_rate: Target sample rate for loaded audio
        """
        self.target_sample_rate = target_sample_rate
    
    def validate_file_path(self, file_path: str) -> Path:
        """
        Validate that the audio file exists and has a supported format.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Path object for the validated file
            
        Raises:
            AudioValidationError: If file doesn't exist or format not supported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise AudioValidationError(f"Audio file not found: {file_path}")
        
        if not path.is_file():
            raise AudioValidationError(f"Path is not a file: {file_path}")
        
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            supported = ', '.join(self.SUPPORTED_FORMATS)
            raise AudioValidationError(
                f"Unsupported audio format: {path.suffix}. "
                f"Supported formats: {supported}"
            )
        
        return path
    
    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """
        Load and validate audio file with preprocessing.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            AudioValidationError: If loading or validation fails
        """
        path = self.validate_file_path(file_path)
        
        try:
            # Load audio using librosa for robust format support
            audio_data, sample_rate = librosa.load(
                str(path), 
                sr=self.target_sample_rate,
                mono=True  # Convert to mono for consistent processing
            )
            
            # Validate audio properties
            self._validate_audio_properties(audio_data, sample_rate, str(path))
            
            # Normalize audio to prevent clipping
            audio_data = self._normalize_audio(audio_data)
            
            logger.info(
                f"Successfully loaded audio: {path.name}, "
                f"duration: {len(audio_data) / sample_rate:.2f}s, "
                f"sample_rate: {sample_rate}Hz"
            )
            
            return audio_data, sample_rate
            
        except Exception as e:
            if isinstance(e, AudioValidationError):
                raise
            raise AudioValidationError(f"Failed to load audio file {path}: {str(e)}")
    
    def _validate_audio_properties(self, audio_data: np.ndarray, sample_rate: int, file_path: str) -> None:
        """
        Validate audio properties for quality and processing requirements.
        
        Args:
            audio_data: Audio data array
            sample_rate: Sample rate in Hz
            file_path: Original file path for error messages
            
        Raises:
            AudioValidationError: If validation fails
        """
        # Check if audio data is empty
        if len(audio_data) == 0:
            raise AudioValidationError(f"Audio file is empty: {file_path}")
        
        # Check duration
        duration = len(audio_data) / sample_rate
        if duration < self.MIN_DURATION:
            raise AudioValidationError(
                f"Audio too short: {duration:.2f}s (minimum: {self.MIN_DURATION}s)"
            )
        
        if duration > self.MAX_DURATION:
            raise AudioValidationError(
                f"Audio too long: {duration:.2f}s (maximum: {self.MAX_DURATION}s)"
            )
        
        # Check sample rate
        if sample_rate < self.MIN_SAMPLE_RATE:
            raise AudioValidationError(
                f"Sample rate too low: {sample_rate}Hz (minimum: {self.MIN_SAMPLE_RATE}Hz)"
            )
        
        # Check for silent audio (all zeros or very low amplitude)
        max_amplitude = np.max(np.abs(audio_data))
        if max_amplitude < 1e-6:
            raise AudioValidationError("Audio appears to be silent or has very low amplitude")
        
        # Check for clipping (values at or near maximum)
        clipping_threshold = 0.95
        clipped_samples = np.sum(np.abs(audio_data) >= clipping_threshold)
        clipping_percentage = (clipped_samples / len(audio_data)) * 100
        
        if clipping_percentage > 5.0:  # More than 5% clipped
            logger.warning(
                f"Audio may be clipped: {clipping_percentage:.1f}% of samples "
                f"at or above {clipping_threshold} amplitude"
            )
    
    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Normalize audio to prevent clipping and ensure consistent levels.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Normalized audio data
        """
        # Find the maximum absolute value
        max_val = np.max(np.abs(audio_data))
        
        if max_val > 0:
            # Normalize to 90% of maximum to leave headroom
            audio_data = audio_data * (0.9 / max_val)
        
        return audio_data
    
    def get_audio_info(self, file_path: str) -> dict:
        """
        Get audio file information without loading the full audio data.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Dictionary with audio file information
            
        Raises:
            AudioValidationError: If file cannot be read
        """
        path = self.validate_file_path(file_path)
        
        try:
            # Use librosa to get basic info
            duration = librosa.get_duration(filename=str(path))
            
            # Try to get more detailed info using soundfile
            try:
                with sf.SoundFile(str(path)) as f:
                    sample_rate = f.samplerate
                    channels = f.channels
                    frames = f.frames
            except:
                # Fallback to librosa
                y, sample_rate = librosa.load(str(path), sr=None, duration=0.1)
                channels = 1  # librosa loads as mono by default
                frames = int(duration * sample_rate)
            
            return {
                'file_path': str(path),
                'file_size': path.stat().st_size,
                'duration': duration,
                'sample_rate': sample_rate,
                'channels': channels,
                'frames': frames,
                'format': path.suffix.lower()
            }
            
        except Exception as e:
            raise AudioValidationError(f"Failed to get audio info for {path}: {str(e)}")
    
    def convert_format(self, input_path: str, output_path: str, target_format: str = 'wav') -> str:
        """
        Convert audio file to a different format.
        
        Args:
            input_path: Path to input audio file
            output_path: Path for output file
            target_format: Target format ('wav', 'mp3', etc.)
            
        Returns:
            Path to the converted file
            
        Raises:
            AudioValidationError: If conversion fails
        """
        try:
            # Load audio
            audio_data, sample_rate = self.load_audio(input_path)
            
            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save in target format
            if target_format.lower() == 'wav':
                sf.write(str(output_path), audio_data, sample_rate)
            else:
                # For other formats, use librosa
                librosa.output.write_wav(str(output_path), audio_data, sample_rate)
            
            logger.info(f"Converted {input_path} to {output_path} ({target_format})")
            return str(output_path)
            
        except Exception as e:
            raise AudioValidationError(f"Failed to convert audio format: {str(e)}")