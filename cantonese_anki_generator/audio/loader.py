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

# Try to import pydub for additional M4A support
try:
    from pydub import AudioSegment
    from pydub.utils import which
    import shutil
    PYDUB_AVAILABLE = True
    
    # Auto-configure FFmpeg path for pydub if needed
    def _configure_pydub_ffmpeg():
        """Configure pydub to use FFmpeg if available."""
        # Check if FFmpeg is already available in PATH
        if shutil.which('ffmpeg') and shutil.which('ffprobe'):
            return True
            
        # Try to find FFmpeg in common Windows installation locations
        import os
        from pathlib import Path
        
        possible_paths = [
            # WinGet installation path
            Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
            # Chocolatey path
            Path("C:/ProgramData/chocolatey/bin"),
            # Manual installation paths
            Path("C:/ffmpeg/bin"),
            Path("C:/Program Files/ffmpeg/bin"),
        ]
        
        for base_path in possible_paths:
            if base_path.exists():
                # Look for FFmpeg in WinGet packages
                if "WinGet" in str(base_path):
                    for pkg_dir in base_path.glob("*ffmpeg*"):
                        ffmpeg_bin = pkg_dir / "ffmpeg-*" / "bin"
                        ffmpeg_bins = list(ffmpeg_bin.parent.glob("ffmpeg-*/bin"))
                        if ffmpeg_bins:
                            ffmpeg_path = ffmpeg_bins[0] / "ffmpeg.exe"
                            ffprobe_path = ffmpeg_bins[0] / "ffprobe.exe"
                            if ffmpeg_path.exists() and ffprobe_path.exists():
                                AudioSegment.converter = str(ffmpeg_path)
                                AudioSegment.ffmpeg = str(ffmpeg_path)
                                AudioSegment.ffprobe = str(ffprobe_path)
                                logger.info(f"Configured pydub to use FFmpeg at: {ffmpeg_path}")
                                return True
                else:
                    # Direct path check
                    ffmpeg_path = base_path / "ffmpeg.exe"
                    ffprobe_path = base_path / "ffprobe.exe"
                    if ffmpeg_path.exists() and ffprobe_path.exists():
                        AudioSegment.converter = str(ffmpeg_path)
                        AudioSegment.ffmpeg = str(ffmpeg_path)
                        AudioSegment.ffprobe = str(ffprobe_path)
                        logger.info(f"Configured pydub to use FFmpeg at: {ffmpeg_path}")
                        return True
        
        return False
    
    # Try to configure FFmpeg automatically
    _configure_pydub_ffmpeg()
    
except ImportError:
    PYDUB_AVAILABLE = False


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
    
    def _convert_m4a_to_wav_if_needed(self, file_path: str) -> str:
        """
        Convert M4A file to WAV if needed for better compatibility.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Path to the audio file (original or converted WAV)
        """
        path = Path(file_path)
        
        # If it's not M4A, return as-is
        if path.suffix.lower() not in ['.m4a', '.mp4', '.aac']:
            return str(path)
        
        # Check if we can load it directly first
        try:
            # Quick test load
            librosa.load(str(path), sr=None, duration=0.1)
            return str(path)  # Works fine, no conversion needed
        except Exception:
            pass  # Need to convert
        
        # Create WAV version in temp directory
        temp_dir = Path.cwd() / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        wav_path = temp_dir / f"{path.stem}_converted.wav"
        
        # Try conversion with pydub if available
        if PYDUB_AVAILABLE:
            try:
                logger.info(f"Converting {path.name} to WAV for better compatibility...")
                audio_segment = AudioSegment.from_file(str(path))
                audio_segment.export(str(wav_path), format="wav")
                logger.info(f"Converted to: {wav_path}")
                return str(wav_path)
            except Exception as e:
                logger.warning(f"Pydub conversion failed: {e}")
        
        # If conversion fails, return original and let other methods handle it
        return str(path)

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
        
        # Try to convert M4A to WAV if needed for better compatibility
        working_path = self._convert_m4a_to_wav_if_needed(str(path))
        
        try:
            # Load audio using librosa with multiple fallback methods for M4A support
            audio_data = None
            sample_rate = None
            
            # Method 1: Try standard librosa loading
            try:
                audio_data, sample_rate = librosa.load(
                    working_path, 
                    sr=self.target_sample_rate,
                    mono=True  # Convert to mono for consistent processing
                )
            except Exception as e1:
                # Method 2: Try with different backend for M4A files
                try:
                    # Force audioread backend which handles M4A better
                    audio_data, sample_rate = librosa.load(
                        working_path,
                        sr=self.target_sample_rate,
                        mono=True,
                        res_type='kaiser_fast'  # Faster resampling
                    )
                except Exception as e2:
                    # Method 3: Try loading without resampling first
                    try:
                        audio_data, original_sr = librosa.load(
                            working_path,
                            sr=None,  # Keep original sample rate
                            mono=True
                        )
                        # Resample manually if needed
                        if original_sr != self.target_sample_rate:
                            audio_data = librosa.resample(
                                audio_data, 
                                orig_sr=original_sr, 
                                target_sr=self.target_sample_rate
                            )
                        sample_rate = self.target_sample_rate
                    except Exception as e3:
                        # Method 4: Try pydub for M4A files (if available)
                        if PYDUB_AVAILABLE and Path(working_path).suffix.lower() in ['.m4a', '.mp4', '.aac']:
                            try:
                                # Load with pydub
                                audio_segment = AudioSegment.from_file(working_path)
                                # Convert to mono and get raw audio data
                                audio_segment = audio_segment.set_channels(1)
                                # Convert to numpy array
                                audio_data = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
                                # Normalize to [-1, 1] range
                                audio_data = audio_data / (2**15)  # 16-bit audio normalization
                                original_sr = audio_segment.frame_rate
                                
                                # Resample if needed
                                if original_sr != self.target_sample_rate:
                                    audio_data = librosa.resample(
                                        audio_data, 
                                        orig_sr=original_sr, 
                                        target_sr=self.target_sample_rate
                                    )
                                sample_rate = self.target_sample_rate
                            except Exception as e4:
                                # Check if this is an M4A compatibility issue
                                if Path(str(path)).suffix.lower() in ['.m4a', '.mp4', '.aac']:
                                    raise AudioValidationError(
                                        f"M4A/MP4 audio format compatibility issue with {Path(str(path)).name}.\n\n"
                                        f"🔧 Quick Fix Options:\n"
                                        f"1. Convert to WAV format (recommended):\n"
                                        f"   • Open your M4A file in any audio player\n"
                                        f"   • Export/Save As → WAV format\n"
                                        f"   • Use the WAV file instead\n\n"
                                        f"2. Convert online:\n"
                                        f"   • Visit cloudconvert.com or convertio.co\n"
                                        f"   • Upload your M4A file\n"
                                        f"   • Convert to WAV and download\n\n"
                                        f"3. Use VLC Media Player:\n"
                                        f"   • Media → Convert/Save\n"
                                        f"   • Add your M4A file\n"
                                        f"   • Choose WAV profile → Start\n\n"
                                        f"WAV format provides the best compatibility and will work reliably.\n"
                                        f"Tried methods: librosa, pydub, audioread - all failed with M4A codec issues."
                                    )
                                else:
                                    raise AudioValidationError(
                                        f"Failed to load audio file {path}. Tried all methods:\n"
                                        f"Method 1 (librosa): {str(e1)}\n"
                                        f"Method 2 (librosa fast): {str(e2)}\n" 
                                        f"Method 3 (librosa no resample): {str(e3)}\n"
                                        f"Method 4 (pydub): {str(e4)}\n"
                                        f"Consider converting to WAV format for better compatibility."
                                    )
                        else:
                            # Check if this is an M4A compatibility issue
                            if Path(str(path)).suffix.lower() in ['.m4a', '.mp4', '.aac']:
                                raise AudioValidationError(
                                    f"M4A/MP4 audio format compatibility issue with {Path(str(path)).name}.\n\n"
                                    f"🔧 Quick Fix Options:\n"
                                    f"1. Convert to WAV format (recommended):\n"
                                    f"   • Open your M4A file in any audio player\n"
                                    f"   • Export/Save As → WAV format\n"
                                    f"   • Use the WAV file instead\n\n"
                                    f"2. Convert online:\n"
                                    f"   • Visit cloudconvert.com or convertio.co\n"
                                    f"   • Upload your M4A file\n"
                                    f"   • Convert to WAV and download\n\n"
                                    f"3. Use VLC Media Player:\n"
                                    f"   • Media → Convert/Save\n"
                                    f"   • Add your M4A file\n"
                                    f"   • Choose WAV profile → Start\n\n"
                                    f"WAV format provides the best compatibility and will work reliably."
                                )
                            else:
                                raise AudioValidationError(
                                    f"Failed to load audio file {path}. Tried multiple methods:\n"
                                    f"Method 1: {str(e1)}\n"
                                    f"Method 2: {str(e2)}\n" 
                                    f"Method 3: {str(e3)}\n"
                                    f"Consider converting to WAV format for better compatibility."
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
            # Use updated librosa API to get basic info with multiple fallback methods
            try:
                # Try the new API first
                duration = librosa.get_duration(path=str(path))
            except Exception:
                try:
                    # Fallback to old API for compatibility
                    duration = librosa.get_duration(filename=str(path))
                except Exception:
                    # Last resort: load a small sample to get duration
                    y, sr = librosa.load(str(path), sr=None, duration=1.0)
                    # Estimate total duration from file size and sample rate
                    file_size = path.stat().st_size
                    # Rough estimate: assume 16-bit audio
                    estimated_samples = file_size / 2  # 2 bytes per sample for 16-bit
                    duration = estimated_samples / sr
            
            # Try to get more detailed info using multiple methods
            sample_rate = None
            channels = None
            frames = None
            
            # Method 1: Try soundfile (works well with many formats)
            try:
                with sf.SoundFile(str(path)) as f:
                    sample_rate = f.samplerate
                    channels = f.channels
                    frames = f.frames
            except Exception:
                pass
            
            # Method 2: Fallback to librosa if soundfile failed
            if sample_rate is None:
                try:
                    y, sample_rate = librosa.load(str(path), sr=None, duration=0.1)
                    channels = 1 if len(y.shape) == 1 else y.shape[0]
                    frames = int(duration * sample_rate)
                except Exception:
                    # Default values if all else fails
                    sample_rate = 22050  # librosa default
                    channels = 1
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
            # Check if this is an M4A compatibility issue
            if path.suffix.lower() in ['.m4a', '.mp4', '.aac']:
                raise AudioValidationError(
                    f"M4A/MP4 audio format compatibility issue with {path.name}.\n\n"
                    f"🔧 Quick Fix Options:\n"
                    f"1. Convert to WAV format (recommended):\n"
                    f"   • Open your M4A file in any audio player\n"
                    f"   • Export/Save As → WAV format\n"
                    f"   • Use the WAV file instead\n\n"
                    f"2. Convert online:\n"
                    f"   • Visit cloudconvert.com or convertio.co\n"
                    f"   • Upload your M4A file\n"
                    f"   • Convert to WAV and download\n\n"
                    f"3. Use VLC Media Player:\n"
                    f"   • Media → Convert/Save\n"
                    f"   • Add your M4A file\n"
                    f"   • Choose WAV profile → Start\n\n"
                    f"WAV format provides the best compatibility and will work reliably.\n"
                    f"Technical details: {str(e)}"
                )
            else:
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