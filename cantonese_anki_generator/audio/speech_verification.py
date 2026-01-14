"""
Speech-to-text verification using Whisper for alignment correction.

This module uses OpenAI's Whisper model to transcribe audio segments and
compare them with expected Cantonese text to verify alignment accuracy.
"""

import logging
import tempfile
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable
import numpy as np
import scipy.io.wavfile as wavfile

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False

from ..models import AudioSegment, VocabularyEntry, AlignedPair


logger = logging.getLogger(__name__)


class SpeechVerificationError(Exception):
    """Raised when speech verification fails."""
    pass


class WhisperVerifier:
    """
    Speech-to-text verifier using Whisper for Cantonese audio alignment.
    
    Uses local Whisper model to transcribe audio segments and compare
    with expected Cantonese text to verify and correct alignment.
    """
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize Whisper verifier.
        
        Args:
            model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
        """
        if not WHISPER_AVAILABLE:
            raise SpeechVerificationError(
                "Whisper not available. Install with: pip install openai-whisper"
            )
        
        self.model_size = model_size
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the Whisper model."""
        try:
            logger.info(f"Loading Whisper {self.model_size} model...")
            self.model = whisper.load_model(self.model_size)
            logger.info(f"Whisper {self.model_size} model loaded successfully")
        except Exception as e:
            raise SpeechVerificationError(f"Failed to load Whisper model: {e}")
    
    def transcribe_audio_segment(self, audio_data: np.ndarray, sample_rate: int) -> Dict:
        """
        Transcribe an audio segment using Whisper.
        
        Args:
            audio_data: Audio data array
            sample_rate: Sample rate in Hz
            
        Returns:
            Dictionary with transcription results
        """
        if self.model is None:
            raise SpeechVerificationError("Whisper model not loaded")
        
        # Create temporary WAV file for Whisper
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            try:
                # Normalize and convert to 16-bit
                audio_normalized = (audio_data * 32767).astype(np.int16)
                wavfile.write(temp_file.name, sample_rate, audio_normalized)
                
                # Transcribe with Whisper
                result = self.model.transcribe(
                    temp_file.name,
                    language='zh',  # Chinese (includes Cantonese)
                    task='transcribe',
                    verbose=False
                )
                
                return {
                    'text': result['text'].strip(),
                    'language': result.get('language', 'zh'),
                    'segments': result.get('segments', []),
                    'confidence': self._calculate_confidence(result)
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass
    
    def _calculate_confidence(self, whisper_result: Dict) -> float:
        """
        Calculate confidence score from Whisper result.
        
        Args:
            whisper_result: Whisper transcription result
            
        Returns:
            Confidence score between 0 and 1
        """
        segments = whisper_result.get('segments', [])
        if not segments:
            return 0.5  # Default confidence if no segments
        
        # Average the confidence scores from all segments
        confidences = []
        for segment in segments:
            # Whisper doesn't always provide confidence, estimate from other factors
            if 'avg_logprob' in segment:
                # Convert log probability to confidence (rough approximation)
                confidence = max(0.0, min(1.0, (segment['avg_logprob'] + 1.0)))
                confidences.append(confidence)
            else:
                confidences.append(0.7)  # Default confidence
        
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    def compare_transcription_with_expected(self, transcribed: str, expected: str) -> Dict:
        """
        Compare transcribed text with expected Cantonese text.
        
        Args:
            transcribed: Transcribed text from Whisper (likely Chinese characters)
            expected: Expected Cantonese text (likely Jyutping/Yale romanization)
            
        Returns:
            Dictionary with comparison results
        """
        # Convert Chinese characters to Jyutping if needed
        transcribed_jyutping = self._convert_chinese_to_jyutping(transcribed)
        
        # Clean and normalize both texts
        transcribed_clean = self._normalize_cantonese_text(transcribed_jyutping)
        expected_clean = self._normalize_cantonese_text(expected)
        
        # Calculate similarity
        similarity = self._calculate_text_similarity(transcribed_clean, expected_clean)
        
        # Determine match quality
        if similarity >= 0.8:
            match_quality = "excellent"
        elif similarity >= 0.6:
            match_quality = "good"
        elif similarity >= 0.4:
            match_quality = "fair"
        else:
            match_quality = "poor"
        
        return {
            'transcribed': transcribed,
            'transcribed_jyutping': transcribed_jyutping,
            'transcribed_clean': transcribed_clean,
            'expected': expected,
            'expected_clean': expected_clean,
            'similarity': similarity,
            'match_quality': match_quality,
            'is_match': similarity >= 0.6  # Consider 60%+ as a match
        }
    
    def _convert_chinese_to_jyutping(self, chinese_text: str) -> str:
        """
        Convert Chinese characters to Jyutping romanization.
        
        Args:
            chinese_text: Chinese text to convert
            
        Returns:
            Jyutping romanization
        """
        if not chinese_text.strip():
            return chinese_text
        
        # Enhanced Cantonese character to Jyutping mapping
        # This is a more comprehensive mapping for common Cantonese characters
        cantonese_char_map = {
            # Numbers
            '一': 'jat1', '二': 'ji6', '三': 'saam1', '四': 'sei3', '五': 'ng5',
            '六': 'luk6', '七': 'cat1', '八': 'baat3', '九': 'gau2', '十': 'sap6',
            '零': 'ling4', '百': 'baak3', '千': 'cin1', '萬': 'maan6',
            
            # Common words from the vocabulary
            '地': 'dei6', '的': 'ge3', '個': 'go3', '蘋': 'ping4', '果': 'gwo2',
            '貓': 'maau1', '褲': 'fu3', '花': 'faa1', '買': 'maai5', '點': 'dim2',
            '啦': 'laa1', '蚊': 'man1', '兩': 'loeng5', '我': 'ngo5', '要': 'jiu3',
            '想': 'soeng2', '隻': 'zek3', '睡': 'fan3', '覺': 'gaau3', '橙': 'caang2',
            '找': 'zaau2', '返': 'faan1', '元': 'jyun4', '不': 'm4', '用': 'jung6',
            '這': 'ni1', '裡': 'dou6', '沒': 'mou5', '有': 'jau5', '人': 'jan4',
            '很': 'hou2', '多': 'do1', '太': 'taai3', '銅': 'tung4', '鑼': 'lo4',
            '灣': 'waan1', '擺': 'baai2', '酒': 'zau2', '海': 'hai2',
            
            # Additional common characters
            '你': 'nei5', '他': 'keoi5', '她': 'keoi5', '我們': 'ngo5dei6',
            '什麼': 'mat1je5', '哪裡': 'bin1dou6', '怎麼': 'dim2joeng2',
            '時候': 'si4hau6', '現在': 'jin4zoi6', '今天': 'gam1jat6',
            '明天': 'ting1jat6', '昨天': 'cam4jat6', '好': 'hou2',
            '壞': 'waai6', '大': 'daai6', '小': 'sai2', '新': 'san1',
            '舊': 'gau6', '快': 'faai3', '慢': 'maan6', '高': 'gou1',
            '低': 'dai1', '長': 'coeng4', '短': 'dyun2', '厚': 'hau5',
            '薄': 'bok6', '重': 'cung5', '輕': 'heng1', '熱': 'jit6',
            '冷': 'laang5', '暖': 'nyun5', '乾': 'gon1', '濕': 'sap1',
            
            # Punctuation and common particles
            '，': '', '。': '', '？': '', '！': '', '：': '', '；': '',
            '「': '', '」': '', '『': '', '』': '', '（': '', '）': '',
            '嘅': 'ge3', '咗': 'zo2', '緊': 'gan2', '住': 'zyu6',
            '喺': 'hai2', '同': 'tung4', '或者': 'waak6ze2',
        }
        
        # Try character-by-character mapping first
        jyutping_parts = []
        i = 0
        while i < len(chinese_text):
            # Try 2-character combinations first
            if i < len(chinese_text) - 1:
                two_char = chinese_text[i:i+2]
                if two_char in cantonese_char_map:
                    jyutping_parts.append(cantonese_char_map[two_char])
                    i += 2
                    continue
            
            # Try single character
            char = chinese_text[i]
            if char in cantonese_char_map:
                jyutping_parts.append(cantonese_char_map[char])
            elif char.isspace():
                # Preserve spaces
                if jyutping_parts and not jyutping_parts[-1].endswith(' '):
                    jyutping_parts.append(' ')
            elif not char.strip():
                # Skip empty characters
                pass
            else:
                # Fallback: try pypinyin for unknown characters
                if PYPINYIN_AVAILABLE:
                    try:
                        pinyin_result = lazy_pinyin(char, style=Style.TONE3, strict=False)
                        if pinyin_result and pinyin_result[0] != char:
                            # Apply basic Mandarin-to-Cantonese sound mapping
                            mandarin_sound = pinyin_result[0].lower()
                            cantonese_sound = self._mandarin_to_cantonese_approximation(mandarin_sound)
                            jyutping_parts.append(cantonese_sound)
                        else:
                            # Keep unknown character as-is
                            jyutping_parts.append(char)
                    except:
                        jyutping_parts.append(char)
                else:
                    # Keep unknown character as-is
                    jyutping_parts.append(char)
            
            i += 1
        
        # Join and clean up
        result = ' '.join(jyutping_parts).strip()
        
        # Clean up multiple spaces
        while '  ' in result:
            result = result.replace('  ', ' ')
        
        # Log the conversion for transparency
        if chinese_text.strip() and result != chinese_text:
            logger.info(f"🔤 Chinese-to-Jyutping conversion: '{chinese_text}' → '{result}'")
            # Also print to console for immediate user visibility
            print(f"🔤 Chinese-to-Jyutping conversion: '{chinese_text}' → '{result}'")
        
        return result
    
    def _mandarin_to_cantonese_approximation(self, mandarin_sound: str) -> str:
        """
        Apply basic Mandarin-to-Cantonese sound mapping approximation.
        
        Args:
            mandarin_sound: Mandarin pinyin sound
            
        Returns:
            Approximate Cantonese sound
        """
        # Basic Mandarin-to-Cantonese sound mapping (very approximate)
        sound_mappings = {
            # Retroflex to non-retroflex
            'zh': 'z', 'ch': 'c', 'sh': 's',
            # Common consonant changes
            'x': 'h', 'q': 'h', 'j': 'z', 'r': 'j',
            # Vowel changes
            'ian': 'in', 'iang': 'ong', 'uang': 'ong', 'uan': 'un',
            'eng': 'ing', 'ong': 'ung', 'ou': 'au', 'ei': 'ai',
            # Tone approximations (very rough)
            '1': '1', '2': '4', '3': '2', '4': '3', '5': '5',
        }
        
        result = mandarin_sound
        for mandarin, cantonese in sound_mappings.items():
            result = result.replace(mandarin, cantonese)
        
        return result
    
    def _normalize_cantonese_text(self, text: str) -> str:
        """
        Normalize Cantonese text for comparison.
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        # Remove whitespace and convert to lowercase
        normalized = text.strip().lower()
        
        # Remove common punctuation
        punctuation = '.,!?;:()[]{}"\'-'
        for p in punctuation:
            normalized = normalized.replace(p, '')
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings with Cantonese-aware matching.
        
        Args:
            text1: First text (converted from Chinese)
            text2: Second text (expected Jyutping/Yale)
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Normalize both texts for comparison
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()
        
        # Exact match bonus
        if text1_norm == text2_norm:
            return 1.0
        
        # Split into syllables/words for comparison
        syllables1 = text1_norm.split()
        syllables2 = text2_norm.split()
        
        # If one is much longer than the other, penalize
        if len(syllables1) == 0 or len(syllables2) == 0:
            return 0.0
        
        # Calculate syllable-level similarity
        matches = 0
        total_comparisons = max(len(syllables1), len(syllables2))
        
        # Compare each syllable
        for i in range(min(len(syllables1), len(syllables2))):
            syl1 = syllables1[i]
            syl2 = syllables2[i]
            
            # Exact match
            if syl1 == syl2:
                matches += 1
            # Similar sounds (ignore tones)
            elif self._syllables_similar(syl1, syl2):
                matches += 0.7  # Partial credit for similar sounds
        
        # Calculate base similarity
        syllable_similarity = matches / total_comparisons
        
        # Character-level similarity as fallback
        chars1 = set(text1_norm.replace(' ', ''))
        chars2 = set(text2_norm.replace(' ', ''))
        
        if len(chars1.union(chars2)) > 0:
            char_similarity = len(chars1.intersection(chars2)) / len(chars1.union(chars2))
        else:
            char_similarity = 0.0
        
        # Combine similarities (favor syllable matching)
        final_similarity = max(syllable_similarity, char_similarity * 0.8)
        
        return min(1.0, final_similarity)
    
    def _syllables_similar(self, syl1: str, syl2: str) -> bool:
        """
        Check if two syllables are similar (ignoring tones and minor variations).
        
        Args:
            syl1: First syllable
            syl2: Second syllable
            
        Returns:
            True if syllables are similar
        """
        # Remove tone numbers
        syl1_no_tone = ''.join(c for c in syl1 if not c.isdigit())
        syl2_no_tone = ''.join(c for c in syl2 if not c.isdigit())
        
        # Exact match without tones
        if syl1_no_tone == syl2_no_tone:
            return True
        
        # Common Mandarin-Cantonese sound mappings
        mappings = [
            ('mao', 'maau'), ('mai', 'maai'), ('wu', 'ng'),
            ('di', 'dei'), ('piao', 'ping'), ('ling', 'leng'),
            ('zh', 'z'), ('ch', 'c'), ('sh', 's'),
            ('j', 'z'), ('q', 'h'), ('x', 'h')
        ]
        
        # Check if syllables match after applying mappings
        for mandarin, cantonese in mappings:
            if (mandarin in syl1_no_tone and cantonese in syl2_no_tone) or \
               (cantonese in syl1_no_tone and mandarin in syl2_no_tone):
                return True
        
        # Check if they start with the same consonant
        if len(syl1_no_tone) > 0 and len(syl2_no_tone) > 0:
            if syl1_no_tone[0] == syl2_no_tone[0]:
                return True
        
        return False


class AlignmentVerifier:
    """
    Verifies and corrects audio-text alignment using speech recognition.
    
    Uses Whisper to transcribe audio segments and compare with expected
    Cantonese text to identify and correct alignment issues.
    """
    
    def __init__(self, whisper_model_size: str = "base"):
        """
        Initialize alignment verifier.
        
        Args:
            whisper_model_size: Whisper model size to use
        """
        self.whisper = WhisperVerifier(whisper_model_size)
        
        # Confidence thresholds
        self.high_confidence_threshold = 0.8  # Auto-accept
        self.low_confidence_threshold = 0.5   # Flag for review
    
    def verify_alignment(self, aligned_pairs: List[AlignedPair], 
                        sample_rate: int, progress_tracker=None) -> Dict:
        """
        Verify alignment of audio segments with vocabulary entries.
        
        Args:
            aligned_pairs: List of aligned pairs to verify
            sample_rate: Audio sample rate
            progress_tracker: Progress tracker instance for updates
            
        Returns:
            Dictionary with verification results
        """
        logger.info(f"Verifying alignment for {len(aligned_pairs)} pairs using Whisper...")
        
        results = {
            'total_pairs': len(aligned_pairs),
            'verified_pairs': [],
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'corrections_suggested': 0,
            'overall_confidence': 0.0
        }
        
        confidence_scores = []
        
        for i, pair in enumerate(aligned_pairs):
            current_term = pair.vocabulary_entry.english
            logger.debug(f"Verifying pair {i+1}/{len(aligned_pairs)}: {current_term}")
            
            # Update progress with current term being verified
            if progress_tracker:
                from ..progress import ProcessingStage
                progress_tracker.update_stage_progress(
                    ProcessingStage.ALIGNMENT,
                    completed_items=i,
                    current_item=f"🎯 Verifying: '{current_term}' ({i+1}/{len(aligned_pairs)})"
                )
            
            try:
                # Transcribe the audio segment
                transcription = self.whisper.transcribe_audio_segment(
                    pair.audio_segment.audio_data, 
                    sample_rate
                )
                
                # Compare with expected Cantonese text
                comparison = self.whisper.compare_transcription_with_expected(
                    transcription['text'],
                    pair.vocabulary_entry.cantonese
                )
                
                # Calculate overall confidence
                whisper_confidence = transcription['confidence']
                match_confidence = comparison['similarity']
                overall_confidence = (whisper_confidence + match_confidence) / 2
                
                # Categorize confidence
                if overall_confidence >= self.high_confidence_threshold:
                    confidence_category = "high"
                    results['high_confidence'] += 1
                elif overall_confidence >= self.low_confidence_threshold:
                    confidence_category = "medium"
                    results['medium_confidence'] += 1
                else:
                    confidence_category = "low"
                    results['low_confidence'] += 1
                
                # Create verification result
                verification_result = {
                    'pair_index': i,
                    'english': pair.vocabulary_entry.english,
                    'expected_cantonese': pair.vocabulary_entry.cantonese,
                    'transcribed_cantonese': transcription['text'],
                    'transcribed_jyutping': comparison.get('transcribed_jyutping', ''),
                    'whisper_confidence': whisper_confidence,
                    'match_similarity': match_confidence,
                    'overall_confidence': overall_confidence,
                    'confidence_category': confidence_category,
                    'is_correct': comparison['is_match'],
                    'needs_review': overall_confidence < self.low_confidence_threshold,
                    'comparison_details': comparison
                }
                
                # ALWAYS display Chinese-to-Jyutping conversion to user
                transcribed_jyutping = comparison.get('transcribed_jyutping', '')
                if transcribed_jyutping and transcribed_jyutping != transcription['text']:
                    print(f"🔍 Term {i+1}: '{pair.vocabulary_entry.english}' → Expected: '{pair.vocabulary_entry.cantonese}'")
                    print(f"   Audio transcribed: '{transcription['text']}' → '{transcribed_jyutping}'")
                    print(f"   Match: {'✅' if comparison['is_match'] else '❌'} (similarity: {match_confidence*100:.1f}%)")
                else:
                    print(f"🔍 Term {i+1}: '{pair.vocabulary_entry.english}' → Expected: '{pair.vocabulary_entry.cantonese}'")
                    print(f"   Audio transcribed: '{transcription['text']}' (no Jyutping conversion)")
                    print(f"   Match: {'✅' if comparison['is_match'] else '❌'} (similarity: {match_confidence*100:.1f}%)")
                
                results['verified_pairs'].append(verification_result)
                confidence_scores.append(overall_confidence)
                
                if not comparison['is_match']:
                    results['corrections_suggested'] += 1
                
                # Update progress with result
                if progress_tracker:
                    from ..progress import ProcessingStage
                    confidence_emoji = "✅" if overall_confidence >= 0.8 else "⚠️" if overall_confidence >= 0.5 else "❌"
                    progress_tracker.update_stage_progress(
                        ProcessingStage.ALIGNMENT,
                        completed_items=i+1,
                        current_item=f"{confidence_emoji} '{current_term}': {overall_confidence*100:.1f}% confidence"
                    )
                
            except Exception as e:
                logger.warning(f"Failed to verify pair {i+1}: {e}")
                
                # Update progress with error
                if progress_tracker:
                    from ..progress import ProcessingStage
                    progress_tracker.update_stage_progress(
                        ProcessingStage.ALIGNMENT,
                        completed_items=i+1,
                        current_item=f"❌ '{current_term}': Verification failed"
                    )
                
                # Add failed verification result
                verification_result = {
                    'pair_index': i,
                    'english': pair.vocabulary_entry.english,
                    'expected_cantonese': pair.vocabulary_entry.cantonese,
                    'transcribed_cantonese': '',
                    'whisper_confidence': 0.0,
                    'match_similarity': 0.0,
                    'overall_confidence': 0.0,
                    'confidence_category': "failed",
                    'is_correct': False,
                    'needs_review': True,
                    'error': str(e)
                }
                results['verified_pairs'].append(verification_result)
                confidence_scores.append(0.0)
        
        # Calculate overall confidence
        results['overall_confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        # Final progress update
        if progress_tracker:
            from ..progress import ProcessingStage
            progress_tracker.update_stage_progress(
                ProcessingStage.ALIGNMENT,
                completed_items=len(aligned_pairs),
                current_item=f"🎯 Speech verification complete: {results['overall_confidence']*100:.1f}% overall confidence"
            )
        
        logger.info(f"Verification complete: {results['high_confidence']} high, "
                   f"{results['medium_confidence']} medium, {results['low_confidence']} low confidence")
        
        return results
    
    def suggest_alignment_corrections(self, verification_results: Dict, 
                                    audio_segments: List[AudioSegment],
                                    vocab_entries: List[VocabularyEntry]) -> List[Dict]:
        """
        Suggest alignment corrections based on verification results.
        
        Args:
            verification_results: Results from verify_alignment
            audio_segments: Available audio segments
            vocab_entries: Vocabulary entries
            
        Returns:
            List of suggested corrections
        """
        corrections = []
        
        # Find pairs that need correction
        low_confidence_pairs = [
            pair for pair in verification_results['verified_pairs']
            if pair['confidence_category'] in ['low', 'failed'] or not pair['is_correct']
        ]
        
        logger.info(f"Analyzing {len(low_confidence_pairs)} pairs for potential corrections...")
        
        for pair in low_confidence_pairs:
            pair_index = pair['pair_index']
            expected_cantonese = pair['expected_cantonese']
            
            # Try adjacent segments to find better match
            best_match = None
            best_score = 0.0
            
            # Check segments within ±2 positions
            for offset in [-2, -1, 1, 2]:
                segment_index = pair_index + offset
                
                if 0 <= segment_index < len(audio_segments):
                    try:
                        # Transcribe alternative segment
                        alt_transcription = self.whisper.transcribe_audio_segment(
                            audio_segments[segment_index].audio_data,
                            22050  # Assume standard sample rate
                        )
                        
                        # Compare with expected text
                        alt_comparison = self.whisper.compare_transcription_with_expected(
                            alt_transcription['text'],
                            expected_cantonese
                        )
                        
                        # Calculate score
                        alt_score = (alt_transcription['confidence'] + alt_comparison['similarity']) / 2
                        
                        if alt_score > best_score and alt_comparison['is_match']:
                            best_match = {
                                'original_index': pair_index,
                                'suggested_index': segment_index,
                                'offset': offset,
                                'score': alt_score,
                                'transcription': alt_transcription['text'],
                                'comparison': alt_comparison
                            }
                            best_score = alt_score
                    
                    except Exception as e:
                        logger.debug(f"Failed to check alternative segment {segment_index}: {e}")
            
            if best_match and best_match['score'] > pair['overall_confidence'] + 0.1:  # Require significant improvement
                corrections.append({
                    'type': 'segment_swap',
                    'english': pair['english'],
                    'expected_cantonese': expected_cantonese,
                    'current_transcription': pair['transcribed_cantonese'],
                    'current_confidence': pair['overall_confidence'],
                    'suggested_transcription': best_match['transcription'],
                    'suggested_confidence': best_match['score'],
                    'original_segment_index': pair_index,
                    'suggested_segment_index': best_match['suggested_index'],
                    'offset': best_match['offset'],
                    'improvement': best_match['score'] - pair['overall_confidence']
                })
        
        logger.info(f"Found {len(corrections)} potential alignment corrections")
        return corrections
    
    def generate_verification_report(self, verification_results: Dict, 
                                   corrections: List[Dict] = None) -> str:
        """
        Generate a human-readable verification report.
        
        Args:
            verification_results: Results from verify_alignment
            corrections: Optional corrections from suggest_alignment_corrections
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("🎯 ALIGNMENT VERIFICATION REPORT")
        report.append("=" * 50)
        
        # Summary statistics
        total = verification_results['total_pairs']
        high = verification_results['high_confidence']
        medium = verification_results['medium_confidence']
        low = verification_results['low_confidence']
        overall = verification_results['overall_confidence']
        
        report.append(f"📊 Summary:")
        report.append(f"   Total pairs: {total}")
        report.append(f"   High confidence (≥80%): {high} ({high/total*100:.1f}%)")
        report.append(f"   Medium confidence (50-80%): {medium} ({medium/total*100:.1f}%)")
        report.append(f"   Low confidence (<50%): {low} ({low/total*100:.1f}%)")
        report.append(f"   Overall confidence: {overall*100:.1f}%")
        report.append("")
        
        # Corrections summary
        if corrections:
            report.append(f"🔧 Suggested corrections: {len(corrections)}")
            for correction in corrections[:5]:  # Show first 5
                report.append(f"   • {correction['english']}: move segment {correction['offset']:+d} positions")
                report.append(f"     Confidence: {correction['current_confidence']*100:.1f}% → {correction['suggested_confidence']*100:.1f}%")
            if len(corrections) > 5:
                report.append(f"   ... and {len(corrections) - 5} more")
            report.append("")
        
        # Low confidence pairs that need review
        needs_review = [p for p in verification_results['verified_pairs'] if p['needs_review']]
        if needs_review:
            report.append(f"⚠️  Pairs needing review ({len(needs_review)}):")
            for pair in needs_review[:3]:  # Show first 3
                report.append(f"   • {pair['english']} (expected: {pair['expected_cantonese']})")
                report.append(f"     Transcribed: {pair['transcribed_cantonese']}")
                if pair.get('transcribed_jyutping'):
                    report.append(f"     As Jyutping: {pair['transcribed_jyutping']}")
                report.append(f"     Confidence: {pair['overall_confidence']*100:.1f}%")
            if len(needs_review) > 3:
                report.append(f"   ... and {len(needs_review) - 3} more")
        
        report.append("=" * 50)
        return "\n".join(report)