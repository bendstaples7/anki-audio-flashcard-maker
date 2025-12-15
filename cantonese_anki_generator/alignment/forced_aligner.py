"""
Forced alignment toolkit integration for matching audio to vocabulary terms.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass

from ..models import VocabularyEntry, AudioSegment, AlignedPair


@dataclass
class AlignmentResult:
    """Result of forced alignment process."""
    word: str
    start_time: float
    end_time: float
    confidence: float


class ForcedAligner:
    """
    Handles forced alignment using Montreal Forced Alignment (MFA) toolkit.
    Provides Cantonese pronunciation dictionary support and phonetic transcription.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the forced aligner.
        
        Args:
            model_path: Path to pre-trained MFA model. If None, uses default Cantonese model.
        """
        self.model_path = model_path
        self.logger = logging.getLogger(__name__)
        
        # Cantonese pronunciation dictionary mapping
        self.cantonese_phonemes = self._load_cantonese_phonemes()
        
    def _load_cantonese_phonemes(self) -> Dict[str, str]:
        """
        Load Cantonese phoneme mappings for pronunciation dictionary.
        
        Returns:
            Dictionary mapping Cantonese characters to phonetic representations.
        """
        # Basic Cantonese phoneme mappings - this would be expanded with a full dictionary
        phoneme_dict = {
            # Common Cantonese characters and their Jyutping romanization
            '你': 'nei5',
            '好': 'hou2', 
            '係': 'hai6',
            '我': 'ngo5',
            '佢': 'keoi5',
            '嘅': 'ge3',
            '喺': 'hai2',
            '咗': 'zo2',
            '啲': 'di1',
            '個': 'go3',
            '嗰': 'go2',
            '呢': 'ni1',
            '咁': 'gam2',
            '都': 'dou1',
            '會': 'wui5',
            '可以': 'ho2 ji5',
            '唔': 'm4',
            '冇': 'mou5',
            '有': 'jau5',
            '係咪': 'hai6 mai6',
            '點解': 'dim2 gaai2',
        }
        return phoneme_dict
    
    def create_pronunciation_dictionary(self, vocabulary_entries: List[VocabularyEntry]) -> str:
        """
        Create a pronunciation dictionary file for the given vocabulary.
        
        Args:
            vocabulary_entries: List of vocabulary entries to create pronunciations for.
            
        Returns:
            Path to the created pronunciation dictionary file.
        """
        # Create temporary dictionary file
        dict_file = tempfile.NamedTemporaryFile(mode='w', suffix='.dict', delete=False)
        
        try:
            for entry in vocabulary_entries:
                cantonese_text = entry.cantonese.strip()
                
                # Get phonetic transcription
                phonetic = self._get_phonetic_transcription(cantonese_text)
                
                if phonetic:
                    # Write in MFA dictionary format: WORD PHONEME1 PHONEME2 ...
                    dict_file.write(f"{cantonese_text}\t{phonetic}\n")
                else:
                    self.logger.warning(f"No phonetic transcription found for: {cantonese_text}")
                    
        finally:
            dict_file.close()
            
        return dict_file.name
    
    def _get_phonetic_transcription(self, cantonese_text: str) -> Optional[str]:
        """
        Get phonetic transcription for Cantonese text.
        
        Args:
            cantonese_text: Cantonese text to transcribe.
            
        Returns:
            Phonetic transcription or None if not found.
        """
        # Try exact match first
        if cantonese_text in self.cantonese_phonemes:
            return self.cantonese_phonemes[cantonese_text]
        
        # Try character-by-character transcription for multi-character words
        phonemes = []
        for char in cantonese_text:
            if char in self.cantonese_phonemes:
                phonemes.append(self.cantonese_phonemes[char])
            else:
                # For unknown characters, use a placeholder or skip
                self.logger.warning(f"Unknown Cantonese character: {char}")
                return None
                
        return ' '.join(phonemes) if phonemes else None
    
    def prepare_alignment_files(self, audio_file_path: str, vocabulary_entries: List[VocabularyEntry]) -> Tuple[str, str, str]:
        """
        Prepare files needed for MFA alignment.
        
        Args:
            audio_file_path: Path to the audio file.
            vocabulary_entries: List of vocabulary entries.
            
        Returns:
            Tuple of (corpus_dir, dict_path, transcript_path)
        """
        # Create temporary corpus directory
        corpus_dir = tempfile.mkdtemp(prefix='mfa_corpus_')
        
        # Copy audio file to corpus directory
        audio_filename = Path(audio_file_path).name
        corpus_audio_path = os.path.join(corpus_dir, audio_filename)
        
        # Copy the audio file
        import shutil
        shutil.copy2(audio_file_path, corpus_audio_path)
        
        # Create transcript file with vocabulary words in order
        transcript_path = os.path.join(corpus_dir, Path(audio_filename).stem + '.txt')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            words = [entry.cantonese.strip() for entry in vocabulary_entries]
            f.write(' '.join(words))
        
        # Create pronunciation dictionary
        dict_path = self.create_pronunciation_dictionary(vocabulary_entries)
        
        return corpus_dir, dict_path, transcript_path
    
    def run_mfa_alignment(self, corpus_dir: str, dict_path: str, output_dir: str) -> bool:
        """
        Run MFA alignment process.
        
        Args:
            corpus_dir: Directory containing audio and transcript files.
            dict_path: Path to pronunciation dictionary.
            output_dir: Directory to save alignment results.
            
        Returns:
            True if alignment succeeded, False otherwise.
        """
        try:
            # MFA align command
            cmd = [
                'mfa', 'align',
                corpus_dir,
                dict_path,
                'english_us_arpa',  # Use English acoustic model as fallback
                output_dir,
                '--clean'
            ]
            
            self.logger.info(f"Running MFA alignment: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info("MFA alignment completed successfully")
                return True
            else:
                self.logger.error(f"MFA alignment failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("MFA alignment timed out")
            return False
        except FileNotFoundError:
            self.logger.error("MFA not found. Please install Montreal Forced Alignment toolkit")
            return False
        except Exception as e:
            self.logger.error(f"Error running MFA alignment: {e}")
            return False
    
    def parse_alignment_results(self, output_dir: str, audio_filename: str) -> List[AlignmentResult]:
        """
        Parse MFA alignment results from TextGrid files.
        
        Args:
            output_dir: Directory containing alignment results.
            audio_filename: Name of the audio file (without extension).
            
        Returns:
            List of alignment results.
        """
        textgrid_path = os.path.join(output_dir, f"{audio_filename}.TextGrid")
        
        if not os.path.exists(textgrid_path):
            self.logger.error(f"TextGrid file not found: {textgrid_path}")
            return []
        
        try:
            return self._parse_textgrid(textgrid_path)
        except Exception as e:
            self.logger.error(f"Error parsing TextGrid file: {e}")
            return []
    
    def _parse_textgrid(self, textgrid_path: str) -> List[AlignmentResult]:
        """
        Parse TextGrid file to extract word alignments.
        
        Args:
            textgrid_path: Path to TextGrid file.
            
        Returns:
            List of alignment results.
        """
        alignments = []
        
        try:
            with open(textgrid_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple TextGrid parsing - in production, use a proper TextGrid library
            lines = content.split('\n')
            in_word_tier = False
            current_interval = {}
            
            for line in lines:
                line = line.strip()
                
                if 'name = "words"' in line:
                    in_word_tier = True
                    continue
                
                if in_word_tier:
                    if line.startswith('xmin ='):
                        current_interval['start'] = float(line.split('=')[1].strip())
                    elif line.startswith('xmax ='):
                        current_interval['end'] = float(line.split('=')[1].strip())
                    elif line.startswith('text ='):
                        word = line.split('=')[1].strip().strip('"')
                        if word and word != '':
                            current_interval['word'] = word
                            
                            # Calculate confidence based on duration (simple heuristic)
                            duration = current_interval['end'] - current_interval['start']
                            confidence = min(1.0, max(0.1, duration / 2.0))  # Normalize to 0.1-1.0
                            
                            alignments.append(AlignmentResult(
                                word=word,
                                start_time=current_interval['start'],
                                end_time=current_interval['end'],
                                confidence=confidence
                            ))
                        
                        current_interval = {}
                        
        except Exception as e:
            self.logger.error(f"Error parsing TextGrid content: {e}")
            
        return alignments
    
    def cleanup_temp_files(self, *file_paths: str):
        """
        Clean up temporary files and directories.
        
        Args:
            file_paths: Paths to files/directories to clean up.
        """
        import shutil
        
        for path in file_paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.unlink(path)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {path}: {e}")