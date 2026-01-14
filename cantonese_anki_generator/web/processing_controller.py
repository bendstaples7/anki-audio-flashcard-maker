"""
Processing controller for manual audio alignment.

Integrates with the existing alignment pipeline to run automatic alignment
and create initial alignment sessions.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
import numpy as np

from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.smart_segmentation import SmartBoundaryDetector
from cantonese_anki_generator.models import VocabularyEntry, AudioSegment, AlignedPair
from .session_models import AlignmentSession, TermAlignment, generate_session_id, generate_term_id
from .session_manager import SessionManager
from .audio_extractor import AudioExtractor


logger = logging.getLogger(__name__)


class ProcessingController:
    """
    Controller for processing uploads and creating alignment sessions.
    
    Orchestrates the automatic alignment pipeline and converts results
    into alignment sessions for manual review.
    """
    
    def __init__(self, session_manager: SessionManager, temp_dir: str, sample_rate: int = 22050):
        """
        Initialize processing controller.
        
        Args:
            session_manager: Session manager for storing alignment sessions
            temp_dir: Directory for storing temporary audio segments
            sample_rate: Target sample rate for audio processing
        """
        self.session_manager = session_manager
        self.sample_rate = sample_rate
        self.parser = GoogleSheetsParser()
        self.audio_loader = AudioLoader(target_sample_rate=sample_rate)
        self.boundary_detector = SmartBoundaryDetector(sample_rate=sample_rate)
        self.audio_extractor = AudioExtractor(temp_dir=temp_dir, sample_rate=sample_rate)
    
    def process_upload(self, doc_url: str, audio_file_path: str) -> str:
        """
        Process uploaded files and create an alignment session.
        
        Runs the automatic alignment pipeline and creates an initial
        alignment session with all term alignments.
        
        Args:
            doc_url: URL of Google Docs/Sheets with vocabulary
            audio_file_path: Path to uploaded audio file
            
        Returns:
            Session ID of the created alignment session
            
        Raises:
            Exception: If processing fails at any stage
        """
        logger.info(f"Processing upload: doc_url={doc_url}, audio={audio_file_path}")
        
        # Stage 1: Extract vocabulary from document
        logger.info("Extracting vocabulary from document...")
        vocab_entries = self._extract_vocabulary(doc_url)
        logger.info(f"Extracted {len(vocab_entries)} vocabulary entries")
        
        # Stage 2: Load and process audio
        logger.info("Loading audio file...")
        audio_data, sample_rate = self._load_audio(audio_file_path)
        audio_duration = len(audio_data) / sample_rate
        logger.info(f"Loaded audio: {audio_duration:.2f}s at {sample_rate}Hz")
        
        # Stage 3: Run automatic alignment
        logger.info("Running automatic alignment...")
        segments = self._segment_audio(audio_data, len(vocab_entries))
        logger.info(f"Created {len(segments)} audio segments")
        
        # Stage 4: Create aligned pairs
        logger.info("Creating aligned pairs...")
        aligned_pairs = self._create_aligned_pairs(vocab_entries, segments)
        logger.info(f"Created {len(aligned_pairs)} aligned pairs")
        
        # Stage 5: Calculate confidence scores
        logger.info("Calculating confidence scores...")
        self._calculate_confidence_scores(aligned_pairs, audio_data, sample_rate)
        
        # Stage 6: Create alignment session
        logger.info("Creating alignment session...")
        session_id = self._create_alignment_session(
            doc_url, audio_file_path, aligned_pairs, audio_duration
        )
        logger.info(f"Created alignment session: {session_id}")
        
        # Stage 7: Extract audio segments for frontend playback
        logger.info("Extracting audio segments...")
        session = self.session_manager.get_session(session_id)
        segment_paths = self.audio_extractor.extract_session_audio_segments(
            session, audio_data, sample_rate
        )
        logger.info(f"Extracted {len(segment_paths)} audio segments")
        
        return session_id
    
    def _extract_vocabulary(self, doc_url: str) -> List[VocabularyEntry]:
        """
        Extract vocabulary entries from Google Docs/Sheets.
        
        Args:
            doc_url: URL of the document
            
        Returns:
            List of vocabulary entries
            
        Raises:
            Exception: If extraction fails
        """
        try:
            vocab_entries = self.parser.extract_vocabulary_from_sheet(doc_url)
            
            if not vocab_entries:
                raise ValueError("No vocabulary entries found in document")
            
            return vocab_entries
            
        except Exception as e:
            logger.error(f"Failed to extract vocabulary: {e}")
            raise
    
    def _load_audio(self, audio_file_path: str) -> Tuple[np.ndarray, int]:
        """
        Load and validate audio file.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            Exception: If loading fails
        """
        try:
            audio_data, sample_rate = self.audio_loader.load_audio(audio_file_path)
            
            if len(audio_data) == 0:
                raise ValueError("Audio file is empty")
            
            return audio_data, sample_rate
            
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            raise
    
    def _segment_audio(self, audio_data: np.ndarray, expected_count: int) -> List[AudioSegment]:
        """
        Segment audio into individual term segments.
        
        Args:
            audio_data: Audio data array
            expected_count: Expected number of segments
            
        Returns:
            List of audio segments
            
        Raises:
            Exception: If segmentation fails
        """
        try:
            segments = self.boundary_detector.segment_audio(
                audio_data, expected_count, start_offset=0.0
            )
            
            if not segments:
                raise ValueError("No audio segments created")
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to segment audio: {e}")
            raise
    
    def _create_aligned_pairs(
        self, vocab_entries: List[VocabularyEntry], segments: List[AudioSegment]
    ) -> List[AlignedPair]:
        """
        Create aligned pairs from vocabulary and audio segments.
        
        Args:
            vocab_entries: List of vocabulary entries
            segments: List of audio segments
            
        Returns:
            List of aligned pairs
        """
        aligned_pairs = []
        
        # Create pairs by matching vocabulary entries with segments
        max_pairs = min(len(vocab_entries), len(segments))
        
        for i in range(max_pairs):
            vocab_entry = vocab_entries[i]
            segment = segments[i]
            
            aligned_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=segment,
                alignment_confidence=0.7,  # Default confidence, will be updated
                audio_file_path=""  # Will be set during audio extraction
            )
            aligned_pairs.append(aligned_pair)
        
        return aligned_pairs
    
    def _calculate_confidence_scores(
        self, aligned_pairs: List[AlignedPair], audio_data: np.ndarray, sample_rate: int
    ) -> None:
        """
        Calculate confidence scores for each alignment.
        
        Confidence is based on:
        - Audio segment quality (energy, clarity)
        - Segment duration consistency
        - Boundary sharpness
        
        Args:
            aligned_pairs: List of aligned pairs to score
            audio_data: Full audio data array
            sample_rate: Audio sample rate
        """
        if not aligned_pairs:
            return
        
        # Calculate average segment duration for consistency scoring
        durations = [
            pair.audio_segment.end_time - pair.audio_segment.start_time
            for pair in aligned_pairs
        ]
        avg_duration = sum(durations) / len(durations)
        duration_std = np.std(durations)
        
        for pair in aligned_pairs:
            segment = pair.audio_segment
            duration = segment.end_time - segment.start_time
            
            # Factor 1: Segment duration consistency (0.0 to 1.0)
            # Segments close to average duration get higher scores
            if duration_std > 0:
                duration_score = max(0.0, 1.0 - abs(duration - avg_duration) / (2 * duration_std))
            else:
                duration_score = 1.0
            
            # Factor 2: Audio energy (0.0 to 1.0)
            # Higher energy indicates clearer speech
            segment_audio = segment.audio_data
            if len(segment_audio) > 0:
                rms_energy = np.sqrt(np.mean(segment_audio ** 2))
                # Normalize energy score (typical speech RMS is around 0.1-0.3)
                energy_score = min(1.0, rms_energy / 0.2)
            else:
                energy_score = 0.0
            
            # Factor 3: Segment confidence from detector
            detector_confidence = segment.confidence
            
            # Combine factors with weights
            confidence = (
                0.3 * duration_score +
                0.3 * energy_score +
                0.4 * detector_confidence
            )
            
            # Update alignment confidence
            pair.alignment_confidence = confidence
            
            logger.debug(
                f"Confidence for '{pair.vocabulary_entry.english}': "
                f"{confidence:.2f} (duration={duration_score:.2f}, "
                f"energy={energy_score:.2f}, detector={detector_confidence:.2f})"
            )
    
    def _create_alignment_session(
        self,
        doc_url: str,
        audio_file_path: str,
        aligned_pairs: List[AlignedPair],
        audio_duration: float
    ) -> str:
        """
        Create an alignment session from aligned pairs.
        
        Args:
            doc_url: URL of the vocabulary document
            audio_file_path: Path to the audio file
            aligned_pairs: List of aligned pairs
            audio_duration: Total audio duration in seconds
            
        Returns:
            Session ID of the created session
        """
        # Generate session ID
        session_id = generate_session_id()
        
        # Convert aligned pairs to term alignments
        terms = []
        for i, pair in enumerate(aligned_pairs):
            term_id = generate_term_id(i, pair.vocabulary_entry.english)
            
            term_alignment = TermAlignment(
                term_id=term_id,
                english=pair.vocabulary_entry.english,
                cantonese=pair.vocabulary_entry.cantonese,
                start_time=pair.audio_segment.start_time,
                end_time=pair.audio_segment.end_time,
                original_start=pair.audio_segment.start_time,
                original_end=pair.audio_segment.end_time,
                is_manually_adjusted=False,
                confidence_score=pair.alignment_confidence,
                audio_segment_url=f"/api/audio/{session_id}/{term_id}"
            )
            terms.append(term_alignment)
        
        # Create alignment session
        created_session_id = self.session_manager.create_session(
            doc_url=doc_url,
            audio_file_path=audio_file_path,
            terms=terms,
            audio_duration=audio_duration
        )
        
        return created_session_id
