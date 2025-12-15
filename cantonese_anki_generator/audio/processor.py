"""
Main audio processor that integrates all audio processing components.

Provides a high-level interface for the complete audio processing pipeline:
loading, validation, voice activity detection, segmentation, and clip generation.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np

from ..models import AudioSegment
from .loader import AudioLoader, AudioValidationError
from .vad import VoiceActivityDetector, SpeechRegion
from .segmentation import WordSegmenter, WordBoundary
from .smart_segmentation import SmartBoundaryDetector
from .clip_generator import AudioClipGenerator


logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Main audio processor that orchestrates the complete audio processing pipeline.
    
    Integrates audio loading, voice activity detection, word segmentation,
    and clip generation into a unified interface.
    """
    
    def __init__(self, sample_rate: int = 22050):
        """
        Initialize Audio Processor.
        
        Args:
            sample_rate: Target sample rate for audio processing
        """
        self.sample_rate = sample_rate
        
        # Initialize components
        self.loader = AudioLoader(target_sample_rate=sample_rate)
        self.vad = VoiceActivityDetector(sample_rate=min(sample_rate, 16000))  # WebRTC VAD limitation
        self.segmenter = WordSegmenter(sample_rate=sample_rate)
        self.smart_detector = SmartBoundaryDetector(sample_rate=sample_rate)  # Our winning approach!
        self.clip_generator = AudioClipGenerator(sample_rate=sample_rate)
        
        # Processing statistics
        self.last_processing_stats = {}
    
    def process_audio_file(self, 
                          audio_file_path: str,
                          expected_word_count: int,
                          output_dir: str,
                          base_filename: Optional[str] = None) -> Tuple[List[AudioSegment], Dict]:
        """
        Process an audio file through the complete pipeline.
        
        Args:
            audio_file_path: Path to the audio file
            expected_word_count: Expected number of words in the audio
            output_dir: Directory to save generated clips
            base_filename: Base filename for generated clips (defaults to audio filename)
            
        Returns:
            Tuple of (generated_audio_segments, processing_statistics)
            
        Raises:
            AudioValidationError: If audio file validation fails
        """
        logger.info(f"Processing audio file: {audio_file_path}")
        logger.info(f"Expected words: {expected_word_count}")
        
        # Use audio filename as base if not provided
        if base_filename is None:
            base_filename = Path(audio_file_path).stem
        
        stats = {
            'input_file': audio_file_path,
            'expected_words': expected_word_count,
            'sample_rate': self.sample_rate
        }
        
        try:
            # Step 1: Load and validate audio
            logger.info("Step 1: Loading and validating audio...")
            audio_data, actual_sample_rate = self.loader.load_audio(audio_file_path)
            
            stats.update({
                'audio_duration': len(audio_data) / actual_sample_rate,
                'audio_samples': len(audio_data),
                'actual_sample_rate': actual_sample_rate
            })
            
            # Step 2: Detect speech regions
            logger.info("Step 2: Detecting speech regions...")
            speech_regions = self.vad.detect_speech_regions(audio_data)
            
            stats.update({
                'speech_regions_count': len(speech_regions),
                'total_speech_duration': sum(r.duration for r in speech_regions),
                'speech_ratio': self.vad.get_speech_ratio(audio_data)
            })
            
            logger.info(f"Found {len(speech_regions)} speech regions")
            for i, region in enumerate(speech_regions):
                logger.debug(f"  Region {i+1}: {region}")
            
            # Step 3: Smart segmentation using silence gap detection
            logger.info("Step 3: Smart segmentation using silence gap detection...")
            
            # Use our winning smart boundary detection approach
            audio_segments = self.smart_detector.segment_audio(
                audio_data, expected_word_count, start_offset=1.0
            )
            
            # Generate audio clip files
            logger.info("Step 4: Generating audio clip files...")
            saved_segments = []
            
            for i, segment in enumerate(audio_segments):
                # Generate filename
                clip_filename = f"{base_filename}_{i+1:03d}.wav"
                clip_path = os.path.join(output_dir, clip_filename)
                
                # Save audio clip
                success = self.clip_generator._save_audio_clip(segment.audio_data, clip_path)
                
                if success:
                    # Update segment with file path
                    segment.audio_file_path = clip_path
                    saved_segments.append(segment)
            
            audio_segments = saved_segments
            
            stats.update({
                'generated_clips': len(audio_segments),
                'output_directory': output_dir,
                'success': True
            })
            
            # Calculate quality metrics
            if audio_segments:
                confidences = [seg.confidence for seg in audio_segments]
                durations = [seg.end_time - seg.start_time for seg in audio_segments]
                
                stats.update({
                    'average_confidence': np.mean(confidences),
                    'min_confidence': np.min(confidences),
                    'average_clip_duration': np.mean(durations),
                    'min_clip_duration': np.min(durations),
                    'max_clip_duration': np.max(durations)
                })
            
            self.last_processing_stats = stats
            
            logger.info(f"Successfully generated {len(audio_segments)} audio clips")
            logger.info(f"Average confidence: {stats.get('average_confidence', 0):.2f}")
            
            return audio_segments, stats
            
        except Exception as e:
            stats.update({
                'success': False,
                'error': str(e)
            })
            self.last_processing_stats = stats
            logger.error(f"Audio processing failed: {e}")
            raise
    
    def _distribute_words_across_regions(self, 
                                       speech_regions: List[SpeechRegion],
                                       total_words: int) -> List[int]:
        """
        Distribute expected words across multiple speech regions based on duration.
        
        Args:
            speech_regions: List of detected speech regions
            total_words: Total expected word count
            
        Returns:
            List of word counts for each region
        """
        if not speech_regions:
            return []
        
        # Calculate duration-based distribution
        total_duration = sum(region.duration for region in speech_regions)
        
        if total_duration == 0:
            # Equal distribution if no duration info
            words_per_region = [total_words // len(speech_regions)] * len(speech_regions)
            remainder = total_words % len(speech_regions)
            for i in range(remainder):
                words_per_region[i] += 1
        else:
            # Proportional distribution based on duration
            words_per_region = []
            remaining_words = total_words
            
            for i, region in enumerate(speech_regions):
                if i == len(speech_regions) - 1:
                    # Last region gets remaining words
                    words_per_region.append(remaining_words)
                else:
                    # Proportional allocation
                    proportion = region.duration / total_duration
                    allocated_words = max(1, round(total_words * proportion))
                    words_per_region.append(allocated_words)
                    remaining_words -= allocated_words
        
        # Ensure no region gets 0 words if we have words to distribute
        if total_words > 0:
            for i in range(len(words_per_region)):
                if words_per_region[i] == 0:
                    words_per_region[i] = 1
                    # Take from the largest allocation
                    max_idx = words_per_region.index(max(words_per_region))
                    if max_idx != i and words_per_region[max_idx] > 1:
                        words_per_region[max_idx] -= 1
        
        logger.debug(f"Word distribution: {words_per_region}")
        return words_per_region
    
    def _deduplicate_boundaries(self, boundaries: List[WordBoundary]) -> List[WordBoundary]:
        """
        Remove duplicate boundaries and sort by time.
        
        Args:
            boundaries: List of word boundaries
            
        Returns:
            Deduplicated and sorted boundaries
        """
        if not boundaries:
            return []
        
        # Sort by time
        sorted_boundaries = sorted(boundaries, key=lambda b: b.time)
        
        # Remove duplicates (boundaries within 10ms of each other)
        deduplicated = [sorted_boundaries[0]]
        
        for boundary in sorted_boundaries[1:]:
            if boundary.time - deduplicated[-1].time > 0.01:  # 10ms threshold
                deduplicated.append(boundary)
            else:
                # Keep the boundary with higher confidence
                if boundary.confidence > deduplicated[-1].confidence:
                    deduplicated[-1] = boundary
        
        return deduplicated
    
    def get_audio_info(self, audio_file_path: str) -> Dict:
        """
        Get information about an audio file without full processing.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Dictionary with audio file information
        """
        return self.loader.get_audio_info(audio_file_path)
    
    def validate_audio_file(self, audio_file_path: str) -> bool:
        """
        Validate an audio file without loading it completely.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            self.loader.validate_file_path(audio_file_path)
            return True
        except AudioValidationError:
            return False
    
    def set_processing_parameters(self,
                                vad_aggressiveness: Optional[int] = None,
                                min_word_duration: Optional[float] = None,
                                fade_duration: Optional[float] = None,
                                normalize_clips: Optional[bool] = None):
        """
        Update processing parameters for all components.
        
        Args:
            vad_aggressiveness: VAD aggressiveness level (0-3)
            min_word_duration: Minimum word duration in seconds
            fade_duration: Fade in/out duration for clips
            normalize_clips: Whether to normalize clip volumes
        """
        if vad_aggressiveness is not None:
            self.vad.aggressiveness = max(0, min(3, vad_aggressiveness))
        
        if min_word_duration is not None:
            self.segmenter.min_word_duration = max(0.1, min_word_duration)
        
        if fade_duration is not None or normalize_clips is not None:
            self.clip_generator.set_quality_parameters(
                fade_duration=fade_duration,
                normalize_clips=normalize_clips
            )
        
        logger.info("Updated processing parameters")
    
    def get_processing_stats(self) -> Dict:
        """
        Get statistics from the last processing run.
        
        Returns:
            Dictionary with processing statistics
        """
        return self.last_processing_stats.copy()
    
    def estimate_processing_time(self, audio_file_path: str) -> float:
        """
        Estimate processing time for an audio file.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Estimated processing time in seconds
        """
        try:
            info = self.get_audio_info(audio_file_path)
            duration = info['duration']
            
            # Rough estimate: 2-5x real-time depending on complexity
            base_factor = 3.0  # Base processing factor
            
            # Adjust based on file size and duration
            if duration > 60:  # Long files
                base_factor *= 1.5
            elif duration < 10:  # Short files
                base_factor *= 0.8
            
            return duration * base_factor
            
        except Exception:
            return 30.0  # Default estimate