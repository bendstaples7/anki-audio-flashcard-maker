"""
Audio segment extraction for manual audio alignment.

Extracts audio segments for each term and stores them for frontend playback.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict
import numpy as np
import scipy.io.wavfile as wavfile

from cantonese_anki_generator.audio.loader import AudioLoader
from .session_models import TermAlignment, AlignmentSession


logger = logging.getLogger(__name__)


class AudioExtractor:
    """
    Extracts and manages audio segments for alignment sessions.
    
    Handles extraction of audio data for each term based on boundaries,
    generates audio segment files for frontend playback, and manages
    storage in temporary directory.
    """
    
    def __init__(self, temp_dir: str, sample_rate: int = 22050):
        """
        Initialize audio extractor.
        
        Args:
            temp_dir: Directory for storing temporary audio segments
            sample_rate: Target sample rate for audio processing
        """
        self.temp_dir = Path(temp_dir)
        self.sample_rate = sample_rate
        self.audio_loader = AudioLoader(target_sample_rate=sample_rate)
        
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_session_audio_segments(
        self, session: AlignmentSession, audio_data: np.ndarray, sample_rate: int
    ) -> Dict[str, str]:
        """
        Extract audio segments for all terms in a session.
        
        Args:
            session: Alignment session containing term alignments
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            
        Returns:
            Dictionary mapping term_id to audio segment file path
        """
        logger.info(f"Extracting audio segments for session {session.session_id}")
        
        # Create session-specific directory
        session_dir = self.temp_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        segment_paths = {}
        
        for term in session.terms:
            try:
                # Extract audio segment
                segment_path = self._extract_term_segment(
                    term, audio_data, sample_rate, session_dir
                )
                segment_paths[term.term_id] = segment_path
                
                logger.debug(
                    f"Extracted segment for '{term.english}': "
                    f"{term.start_time:.2f}s - {term.end_time:.2f}s"
                )
                
            except Exception as e:
                logger.error(f"Failed to extract segment for term {term.term_id}: {e}")
                # Continue with other segments even if one fails
        
        logger.info(f"Extracted {len(segment_paths)} audio segments")
        return segment_paths
    
    def _extract_term_segment(
        self,
        term: TermAlignment,
        audio_data: np.ndarray,
        sample_rate: int,
        output_dir: Path
    ) -> str:
        """
        Extract audio segment for a single term.
        
        Args:
            term: Term alignment with boundary information
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            output_dir: Directory to save the segment
            
        Returns:
            Path to the saved audio segment file
        """
        # Calculate sample indices
        start_sample = int(term.start_time * sample_rate)
        end_sample = int(term.end_time * sample_rate)
        
        # Ensure indices are within bounds
        start_sample = max(0, start_sample)
        end_sample = min(len(audio_data), end_sample)
        
        # Extract segment
        segment_audio = audio_data[start_sample:end_sample]
        
        # Generate filename
        filename = f"{term.term_id}.wav"
        filepath = output_dir / filename
        
        # Save as WAV file
        self._save_audio_segment(segment_audio, sample_rate, str(filepath))
        
        return str(filepath)
    
    def _save_audio_segment(
        self, audio_data: np.ndarray, sample_rate: int, filepath: str
    ) -> None:
        """
        Save audio segment to WAV file.
        
        Args:
            audio_data: Audio data to save
            sample_rate: Audio sample rate
            filepath: Output file path
        """
        # Normalize and convert to 16-bit PCM
        if audio_data.dtype != np.int16:
            # Normalize to [-1, 1] range
            audio_normalized = audio_data / np.max(np.abs(audio_data) + 1e-8)
            # Convert to 16-bit PCM
            audio_int16 = (audio_normalized * 32767).astype(np.int16)
        else:
            audio_int16 = audio_data
        
        # Save to file
        wavfile.write(filepath, sample_rate, audio_int16)
    
    def update_term_segment(
        self,
        session_id: str,
        term: TermAlignment,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> str:
        """
        Update audio segment for a term after boundary adjustment.
        
        Args:
            session_id: Session ID
            term: Term alignment with updated boundaries
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            
        Returns:
            Path to the updated audio segment file
        """
        logger.debug(
            f"Updating segment for term {term.term_id}: "
            f"{term.start_time:.2f}s - {term.end_time:.2f}s"
        )
        
        # Get session directory
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract and save updated segment
        segment_path = self._extract_term_segment(
            term, audio_data, sample_rate, session_dir
        )
        
        return segment_path
    
    def get_segment_path(self, session_id: str, term_id: str) -> str:
        """
        Get the file path for a term's audio segment.
        
        Args:
            session_id: Session ID
            term_id: Term ID
            
        Returns:
            Path to the audio segment file
        """
        session_dir = self.temp_dir / session_id
        filepath = session_dir / f"{term_id}.wav"
        return str(filepath)
    
    def cleanup_session_audio(self, session_id: str) -> None:
        """
        Clean up audio segments for a session.
        
        Args:
            session_id: Session ID to clean up
        """
        session_dir = self.temp_dir / session_id
        
        if session_dir.exists():
            try:
                import shutil
                shutil.rmtree(session_dir)
                logger.info(f"Cleaned up audio segments for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to clean up session {session_id}: {e}")
    
    def load_audio_for_session(self, audio_file_path: str) -> tuple:
        """
        Load audio file for a session.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        return self.audio_loader.load_audio(audio_file_path)
