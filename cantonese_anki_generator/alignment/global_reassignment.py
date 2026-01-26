"""
Global transcription-based segment reassignment module.

This module implements global optimization for audio-vocabulary alignment
using Whisper transcriptions and the Hungarian algorithm to find the optimal
one-to-one mapping between audio segments and vocabulary terms.
"""

import logging
from typing import List, Dict, Tuple, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment

from ..models import AudioSegment, VocabularyEntry, AlignedPair


logger = logging.getLogger(__name__)


class SimilarityMatrixBuilder:
    """
    Builds similarity matrices between transcriptions and expected terms.
    
    Computes Jyutping similarity between all Whisper transcriptions and all
    expected vocabulary terms, weighted by Whisper confidence scores.
    """
    
    def __init__(self):
        """Initialize the similarity matrix builder."""
        pass
    
    def build_similarity_matrix(
        self,
        transcriptions: List[Dict],
        vocabulary_entries: List[VocabularyEntry]
    ) -> np.ndarray:
        """
        Build NxN similarity matrix between transcriptions and vocabulary terms.
        
        Args:
            transcriptions: List of transcription dictionaries from Whisper verification
                Each dict should contain: 'transcribed_jyutping', 'whisper_confidence'
            vocabulary_entries: List of vocabulary entries with expected Cantonese text
            
        Returns:
            NxN numpy array where element [i,j] is the weighted similarity between
            transcription i and vocabulary term j
        """
        n = len(transcriptions)
        m = len(vocabulary_entries)
        
        if n != m:
            logger.warning(
                f"Transcription count ({n}) != vocabulary count ({m}). "
                f"Using min({n}, {m}) for matrix size."
            )
            size = min(n, m)
        else:
            size = n
        
        # Initialize similarity matrix
        similarity_matrix = np.zeros((size, size))
        
        # Compute similarity for each transcription-term pair
        for i in range(size):
            transcription = transcriptions[i]
            transcribed_text = transcription.get('transcribed_jyutping', '')
            whisper_confidence = transcription.get('whisper_confidence', 0.5)
            
            for j in range(size):
                expected_text = vocabulary_entries[j].cantonese
                
                # Calculate Jyutping similarity
                jyutping_similarity = self._calculate_jyutping_similarity(
                    transcribed_text,
                    expected_text
                )
                
                # Weight by Whisper confidence
                weighted_similarity = jyutping_similarity * whisper_confidence
                
                similarity_matrix[i, j] = weighted_similarity
        
        logger.info(f"Built {size}x{size} similarity matrix")
        return similarity_matrix
    
    def _calculate_jyutping_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two Jyutping/Cantonese text strings.
        
        Uses syllable-level matching with tone-insensitive comparison and
        character-level fallback for robustness.
        
        Args:
            text1: First text (transcribed Jyutping)
            text2: Second text (expected Cantonese/Jyutping)
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Normalize both texts
        text1_norm = self._normalize_text(text1)
        text2_norm = self._normalize_text(text2)
        
        # Exact match bonus
        if text1_norm == text2_norm:
            return 1.0
        
        # Split into syllables/words
        syllables1 = text1_norm.split()
        syllables2 = text2_norm.split()
        
        if len(syllables1) == 0 or len(syllables2) == 0:
            return 0.0
        
        # Calculate syllable-level similarity
        syllable_similarity = self._calculate_syllable_similarity(syllables1, syllables2)
        
        # Character-level similarity as fallback
        char_similarity = self._calculate_character_similarity(text1_norm, text2_norm)
        
        # Combine similarities (favor syllable matching)
        final_similarity = max(syllable_similarity, char_similarity * 0.8)
        
        return min(1.0, final_similarity)
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Args:
            text: Input text
            
        Returns:
            Normalized text (lowercase, no punctuation, trimmed whitespace)
        """
        # Convert to lowercase
        normalized = text.strip().lower()
        
        # Remove common punctuation
        punctuation = '.,!?;:()[]{}"\'-'
        for p in punctuation:
            normalized = normalized.replace(p, '')
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _calculate_syllable_similarity(
        self,
        syllables1: List[str],
        syllables2: List[str]
    ) -> float:
        """
        Calculate syllable-level similarity between two syllable lists.
        
        Args:
            syllables1: First list of syllables
            syllables2: Second list of syllables
            
        Returns:
            Similarity score between 0 and 1
        """
        matches = 0
        total_comparisons = max(len(syllables1), len(syllables2))
        
        # Compare each syllable position
        for i in range(min(len(syllables1), len(syllables2))):
            syl1 = syllables1[i]
            syl2 = syllables2[i]
            
            # Exact match
            if syl1 == syl2:
                matches += 1
            # Similar sounds (ignore tones)
            elif self._syllables_similar(syl1, syl2):
                matches += 0.7  # Partial credit for similar sounds
        
        return matches / total_comparisons if total_comparisons > 0 else 0.0
    
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
    
    def _calculate_character_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate character-level similarity using Jaccard index.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        chars1 = set(text1.replace(' ', ''))
        chars2 = set(text2.replace(' ', ''))
        
        if len(chars1.union(chars2)) == 0:
            return 0.0
        
        return len(chars1.intersection(chars2)) / len(chars1.union(chars2))
    
    def get_top_matches(
        self,
        similarity_matrix: np.ndarray,
        transcriptions: List[Dict],
        vocabulary_entries: List[VocabularyEntry],
        top_k: int = 3
    ) -> List[Dict]:
        """
        Get top K matches for each transcription.
        
        Args:
            similarity_matrix: NxN similarity matrix
            transcriptions: List of transcription dictionaries
            vocabulary_entries: List of vocabulary entries
            top_k: Number of top matches to return per transcription
            
        Returns:
            List of dictionaries with top matches for each transcription
        """
        n = similarity_matrix.shape[0]
        top_matches = []
        
        for i in range(n):
            # Get top K indices for this transcription
            top_indices = np.argsort(similarity_matrix[i])[::-1][:top_k]
            
            matches = []
            for j in top_indices:
                matches.append({
                    'vocab_index': int(j),
                    'english': vocabulary_entries[j].english,
                    'cantonese': vocabulary_entries[j].cantonese,
                    'similarity': float(similarity_matrix[i, j])
                })
            
            top_matches.append({
                'transcription_index': i,
                'transcribed_text': transcriptions[i].get('transcribed_cantonese', ''),
                'transcribed_jyutping': transcriptions[i].get('transcribed_jyutping', ''),
                'top_matches': matches
            })
        
        return top_matches



class HungarianAssigner:
    """
    Uses the Hungarian algorithm to find optimal segment-to-term assignment.
    
    Solves the assignment problem to maximize total similarity between
    transcriptions and expected vocabulary terms.
    """
    
    def __init__(self):
        """Initialize the Hungarian assigner."""
        pass
    
    def find_optimal_assignment(
        self,
        similarity_matrix: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find optimal one-to-one assignment using the Hungarian algorithm.
        
        The Hungarian algorithm minimizes cost by default, so we negate the
        similarity matrix to maximize similarity.
        
        Args:
            similarity_matrix: NxN matrix where element [i,j] is the similarity
                between segment i and term j
                
        Returns:
            Tuple of (row_indices, col_indices) representing the optimal assignment
            where row_indices[k] is assigned to col_indices[k]
        """
        if similarity_matrix.size == 0:
            logger.warning("Empty similarity matrix provided")
            return np.array([]), np.array([])
        
        # Negate similarity matrix for maximization (algorithm minimizes by default)
        cost_matrix = -similarity_matrix
        
        logger.info(f"Running Hungarian algorithm on {cost_matrix.shape[0]}x{cost_matrix.shape[1]} matrix")
        
        # Apply Hungarian algorithm
        row_indices, col_indices = linear_sum_assignment(cost_matrix)
        
        # Calculate total similarity achieved
        total_similarity = similarity_matrix[row_indices, col_indices].sum()
        max_possible_similarity = similarity_matrix.shape[0]  # If all were 1.0
        
        logger.info(
            f"Optimal assignment found: total similarity = {total_similarity:.2f} "
            f"({total_similarity/max_possible_similarity*100:.1f}% of maximum)"
        )
        
        return row_indices, col_indices
    
    def extract_assignment_mapping(
        self,
        row_indices: np.ndarray,
        col_indices: np.ndarray,
        similarity_matrix: np.ndarray
    ) -> List[Dict]:
        """
        Extract segment-to-term mappings from Hungarian algorithm output.
        
        Args:
            row_indices: Row indices from Hungarian algorithm
            col_indices: Column indices from Hungarian algorithm
            similarity_matrix: Original similarity matrix
            
        Returns:
            List of assignment dictionaries with segment index, term index, and similarity
        """
        assignments = []
        
        for i, (segment_idx, term_idx) in enumerate(zip(row_indices, col_indices)):
            similarity = similarity_matrix[segment_idx, term_idx]
            
            assignments.append({
                'segment_index': int(segment_idx),
                'term_index': int(term_idx),
                'similarity': float(similarity),
                'assignment_order': i
            })
        
        logger.debug(f"Extracted {len(assignments)} assignment mappings")
        return assignments
    
    def calculate_assignment_quality(
        self,
        assignments: List[Dict],
        similarity_matrix: np.ndarray
    ) -> Dict:
        """
        Calculate quality metrics for the assignment.
        
        Args:
            assignments: List of assignment dictionaries
            similarity_matrix: Original similarity matrix
            
        Returns:
            Dictionary with quality metrics
        """
        if not assignments:
            return {
                'total_similarity': 0.0,
                'average_similarity': 0.0,
                'min_similarity': 0.0,
                'max_similarity': 0.0,
                'high_quality_count': 0,
                'medium_quality_count': 0,
                'low_quality_count': 0
            }
        
        similarities = [a['similarity'] for a in assignments]
        
        # Count quality levels
        high_quality = sum(1 for s in similarities if s >= 0.8)
        medium_quality = sum(1 for s in similarities if 0.5 <= s < 0.8)
        low_quality = sum(1 for s in similarities if s < 0.5)
        
        return {
            'total_similarity': sum(similarities),
            'average_similarity': np.mean(similarities),
            'min_similarity': min(similarities),
            'max_similarity': max(similarities),
            'high_quality_count': high_quality,
            'medium_quality_count': medium_quality,
            'low_quality_count': low_quality,
            'quality_distribution': {
                'high': high_quality,
                'medium': medium_quality,
                'low': low_quality
            }
        }



class SegmentReassigner:
    """
    Reassigns audio segments to vocabulary terms based on optimal assignment.
    
    Creates new segment-term mappings, updates confidence scores, and maintains
    temporal ordering of terms by audio segment start times.
    """
    
    def __init__(self, boundary_refiner=None):
        """
        Initialize the segment reassigner.
        
        Args:
            boundary_refiner: Optional BoundaryRefiner instance for finding missing audio
        """
        self.boundary_refiner = boundary_refiner
    
    def reassign_segments(
        self,
        aligned_pairs: List[AlignedPair],
        assignments: List[Dict],
        similarity_matrix: np.ndarray,
        transcriptions: List[Dict],
        audio_data: np.ndarray,
        sample_rate: int,
        min_similarity_threshold: float = 0.3
    ) -> List[AlignedPair]:
        """
        Create new aligned pairs based on optimal assignment.
        
        Maintains vocabulary order from the spreadsheet while reassigning audio segments
        to their optimal terms based on transcription similarity.
        
        ENHANCED: 
        - Rejects assignments below minimum similarity threshold
        - Tracks segment ownership to prevent duplicate assignments
        - Marks terms without valid segments for manual review
        
        Args:
            aligned_pairs: Original aligned pairs (in original order)
            assignments: Assignment mappings from Hungarian algorithm
            similarity_matrix: Similarity matrix used for assignment
            transcriptions: Transcription data with confidence scores
            min_similarity_threshold: Minimum similarity to accept assignment (default 0.3)
            audio_data: Full audio data array (REQUIRED for rebuilding segments)
            sample_rate: Audio sample rate (REQUIRED for rebuilding segments)
            
        Returns:
            New list of aligned pairs in original vocabulary order with reassigned audio
        """
        if not aligned_pairs or not assignments:
            logger.warning("Empty aligned pairs or assignments provided")
            return aligned_pairs
        
        logger.info(f"Reassigning {len(aligned_pairs)} segments based on optimal assignment")
        logger.info(f"Minimum similarity threshold: {min_similarity_threshold}")
        
        # ENHANCED: Track segment ownership to prevent duplicates
        # segment_ownership[segment_idx] = term_idx (or None if unassigned)
        segment_ownership = {i: None for i in range(len(aligned_pairs))}
        
        # Build mapping from term_index to optimal audio segment
        # assignments maps segment_idx -> term_idx
        # We need to invert this to term_idx -> segment_idx
        term_to_segment = {}
        rejected_count = 0
        
        for assignment in assignments:
            segment_idx = assignment['segment_index']
            term_idx = assignment['term_index']
            similarity = assignment['similarity']
            
            # ENHANCED: Reject assignments below threshold
            if similarity < min_similarity_threshold:
                rejected_count += 1
                logger.warning(
                    f"⚠️  REJECTED assignment: Segment #{segment_idx+1} → Term #{term_idx+1} "
                    f"(similarity {similarity:.3f} < {min_similarity_threshold})"
                )
                logger.warning(
                    f"   Term #{term_idx+1} ('{aligned_pairs[term_idx].vocabulary_entry.english}') "
                    f"will attempt to use original segment"
                )
                # Don't add to term_to_segment yet - will check original segment availability later
                continue
            
            # Calculate new confidence for this assignment
            new_confidence = self._calculate_new_confidence(
                similarity,
                transcriptions[segment_idx].get('whisper_confidence', 0.5)
            )
            
            # Mark segment as owned by this term
            segment_ownership[segment_idx] = term_idx
            
            term_to_segment[term_idx] = {
                'segment_idx': segment_idx,
                'audio_segment': aligned_pairs[segment_idx].audio_segment,
                'confidence': new_confidence,
                'similarity': similarity
            }
            
            logger.debug(
                f"✓ ACCEPTED: Segment #{segment_idx+1} → Term #{term_idx+1} "
                f"(similarity {similarity:.3f})"
            )
        
        if rejected_count > 0:
            logger.warning(
                f"⚠️  Rejected {rejected_count} low-similarity assignments "
                f"(< {min_similarity_threshold})"
            )
        
        # Create new aligned pairs in vocabulary order (term 0, 1, 2, ...)
        # ENHANCED: Check segment ownership before using fallback
        new_aligned_pairs = []
        terms_needing_review = []
        
        for term_idx in range(len(aligned_pairs)):
            # Get the vocabulary entry for this term (maintains spreadsheet order)
            vocabulary_entry = aligned_pairs[term_idx].vocabulary_entry
            
            # Get the optimal audio segment assigned to this term
            if term_idx in term_to_segment:
                # Has valid reassignment - use it
                assignment_data = term_to_segment[term_idx]
                audio_segment = assignment_data['audio_segment']
                confidence = assignment_data['confidence']
                similarity = assignment_data['similarity']
                
                logger.debug(
                    f"Term #{term_idx+1} ('{vocabulary_entry.english}'): "
                    f"assigned Segment #{assignment_data['segment_idx']+1} "
                    f"(similarity: {similarity:.3f})"
                )
            else:
                # No valid reassignment - check if original segment is available
                original_segment_idx = term_idx  # In original alignment, term i has segment i
                
                if segment_ownership[original_segment_idx] is None:
                    # Original segment unclaimed - use it
                    audio_segment = aligned_pairs[original_segment_idx].audio_segment
                    confidence = aligned_pairs[term_idx].alignment_confidence
                    segment_ownership[original_segment_idx] = term_idx
                    
                    logger.info(
                        f"Term #{term_idx+1} ('{vocabulary_entry.english}'): "
                        f"using original Segment #{original_segment_idx+1} (available)"
                    )
                
                elif segment_ownership[original_segment_idx] == term_idx:
                    # Already owned by this term (shouldn't happen, but safe)
                    audio_segment = aligned_pairs[original_segment_idx].audio_segment
                    confidence = aligned_pairs[term_idx].alignment_confidence
                    
                    logger.debug(
                        f"Term #{term_idx+1} ('{vocabulary_entry.english}'): "
                        f"using original Segment #{original_segment_idx+1} (already owned)"
                    )
                
                else:
                    # Original segment owned by another term - TRY TO FIND AUDIO
                    owner_term_idx = segment_ownership[original_segment_idx]
                    
                    logger.warning(
                        f"⚠️  Term #{term_idx+1} ('{vocabulary_entry.english}'): "
                        f"original Segment #{original_segment_idx+1} owned by Term #{owner_term_idx+1}"
                    )
                    
                    # Attempt to find audio using boundary refinement
                    found_segment = False
                    if self.boundary_refiner and audio_data is not None and sample_rate is not None:
                        logger.info(f"   🔍 Searching for audio for Term #{term_idx+1}...")
                        
                        # Determine search window
                        prev_end = 0.0
                        if term_idx > 0:
                            prev_end = aligned_pairs[term_idx-1].audio_segment.end_time
                        
                        next_start = None
                        if term_idx < len(aligned_pairs) - 1:
                            next_start = aligned_pairs[term_idx+1].audio_segment.start_time
                        
                        # Search for the audio
                        found_pair = self.boundary_refiner.fix_out_of_order_segment(
                            aligned_pairs[term_idx],
                            term_idx,
                            audio_data,
                            sample_rate,
                            prev_end,
                            next_start
                        )
                        
                        if found_pair:
                            audio_segment = found_pair.audio_segment
                            confidence = found_pair.alignment_confidence
                            found_segment = True
                            logger.info(
                                f"   ✓ Found audio for Term #{term_idx+1} at "
                                f"{audio_segment.start_time:.2f}s-{audio_segment.end_time:.2f}s"
                            )
                    
                    if not found_segment:
                        # Couldn't find it or boundary refiner not available - create empty placeholder
                        if self.boundary_refiner and audio_data is not None:
                            logger.error(f"   ✗ Could not find audio for Term #{term_idx+1}")
                        else:
                            logger.warning(f"   ⚠️  Boundary refinement not available")
                        
                        # Create empty audio segment as placeholder
                        audio_segment = AudioSegment(
                            audio_data=np.array([]),  # Empty audio
                            start_time=0.0,
                            end_time=0.0,
                            confidence=0.0,
                            segment_id=f"EMPTY_PLACEHOLDER_{term_idx}",
                            audio_file_path=aligned_pairs[original_segment_idx].audio_segment.audio_file_path
                        )
                        confidence = 0.0  # Mark for manual review
                        
                        terms_needing_review.append({
                            'term_index': term_idx,
                            'english': vocabulary_entry.english,
                            'cantonese': vocabulary_entry.cantonese,
                            'conflict': f"Segment #{original_segment_idx+1} owned by Term #{owner_term_idx+1}"
                        })
            
            # Create new aligned pair with vocabulary in original order
            new_pair = AlignedPair(
                vocabulary_entry=vocabulary_entry,
                audio_segment=audio_segment,
                alignment_confidence=confidence,
                audio_file_path=audio_segment.audio_file_path
            )
            
            new_aligned_pairs.append(new_pair)
        
        # Report terms needing manual review
        if terms_needing_review:
            logger.error("=" * 80)
            logger.error(f"⚠️  {len(terms_needing_review)} TERMS REQUIRE MANUAL REVIEW")
            logger.error("=" * 80)
            print(f"\n⚠️  {len(terms_needing_review)} TERMS REQUIRE MANUAL REVIEW:")
            print("=" * 80)
            
            for term_info in terms_needing_review:
                msg = (
                    f"Term #{term_info['term_index']+1}: '{term_info['english']}' / "
                    f"'{term_info['cantonese']}'"
                )
                if 'conflict' in term_info:
                    msg += f" - {term_info['conflict']}"
                logger.error(f"   {msg}")
                print(f"   {msg}")
            
            logger.error("=" * 80)
            print("=" * 80)
        
        # ENHANCED: Detect audio duplicates
        duplicates = self._detect_audio_duplicates(new_aligned_pairs)
        if duplicates:
            logger.error("=" * 80)
            logger.error(f"⚠️  AUDIO DUPLICATION DETECTED: {len(duplicates)} duplicate assignments")
            logger.error("=" * 80)
            print(f"\n⚠️  AUDIO DUPLICATION DETECTED: {len(duplicates)} duplicate assignments")
            print("=" * 80)
            
            for dup in duplicates:
                msg = (
                    f"   {dup['severity']}: Term #{dup['term_1_idx']+1} ('{dup['term_1_english']}') "
                    f"and Term #{dup['term_2_idx']+1} ('{dup['term_2_english']}') "
                    f"have identical audio ({dup['type']})"
                )
                logger.error(msg)
                print(msg)
            
            logger.error("=" * 80)
            print("=" * 80)
        
        logger.info(f"Reassignment complete: {len(new_aligned_pairs)} pairs in vocabulary order")
        
        # CRITICAL FIX: Rebuild aligned pairs from scratch to eliminate any shared references
        # This ensures each term has its own independent AudioSegment object with correct boundaries
        
        # Validate that audio_data and sample_rate are provided
        if audio_data is None or sample_rate is None:
            raise ValueError(
                f"CRITICAL: audio_data and sample_rate are REQUIRED for reassign_segments(). "
                f"Got audio_data={type(audio_data).__name__ if audio_data is not None else 'None'}, "
                f"sample_rate={type(sample_rate).__name__ if sample_rate is not None else 'None'}. "
                f"This is a bug - these parameters must always be provided."
            )
        
        logger.info("")
        logger.info("🔧 Rebuilding aligned pairs from scratch to ensure clean state...")
        
        final_aligned_pairs = []
        for term_idx, pair in enumerate(new_aligned_pairs):
            vocab_entry = pair.vocabulary_entry
            old_segment = pair.audio_segment
            
            # Skip empty placeholders - keep them as-is
            if old_segment.segment_id.startswith('EMPTY_PLACEHOLDER_'):
                logger.debug(f"   Term #{term_idx+1}: Keeping empty placeholder")
                final_aligned_pairs.append(pair)
                continue
            
            # Extract fresh audio from original audio_data using the segment's boundaries
            start_sample = int(old_segment.start_time * sample_rate)
            end_sample = int(old_segment.end_time * sample_rate)
            
            # Ensure indices are within bounds
            start_sample = max(0, start_sample)
            end_sample = min(len(audio_data), end_sample)
            
            fresh_audio = audio_data[start_sample:end_sample].copy()  # Copy to avoid shared memory
            
            # Create completely new AudioSegment with fresh audio data
            fresh_segment = AudioSegment(
                audio_data=fresh_audio,
                start_time=old_segment.start_time,
                end_time=old_segment.end_time,
                confidence=old_segment.confidence,
                segment_id=f"final_{term_idx}",  # New unique ID
                audio_file_path=""  # Will be set during audio extraction
            )
            
            # Create completely new AlignedPair
            fresh_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=fresh_segment,
                alignment_confidence=pair.alignment_confidence,
                audio_file_path=""  # Will be set during audio extraction
            )
            
            logger.debug(
                f"   Term #{term_idx+1} '{vocab_entry.english}': "
                f"Rebuilt with boundaries {fresh_segment.start_time:.2f}s - {fresh_segment.end_time:.2f}s"
            )
            
            final_aligned_pairs.append(fresh_pair)
        
        logger.info(f"✓ Rebuilt {len(final_aligned_pairs)} aligned pairs with fresh audio segments")
        
        # Final validation: Check for duplicate boundaries
        seen_boundaries = {}
        duplicate_found = False
        for i, pair in enumerate(final_aligned_pairs):
            # Skip empty placeholders
            if pair.audio_segment.segment_id.startswith('EMPTY_PLACEHOLDER_'):
                continue
                
            boundary_key = (
                round(pair.audio_segment.start_time, 3),  # Round to avoid floating point issues
                round(pair.audio_segment.end_time, 3)
            )
            
            if boundary_key in seen_boundaries:
                logger.error(
                    f"❌ DUPLICATE BOUNDARY: Term #{i+1} ('{pair.vocabulary_entry.english}') "
                    f"and Term #{seen_boundaries[boundary_key]+1} both have boundaries "
                    f"{boundary_key[0]:.2f}s - {boundary_key[1]:.2f}s"
                )
                duplicate_found = True
            else:
                seen_boundaries[boundary_key] = i
        
        if not duplicate_found:
            logger.info("✓ Validation passed: No duplicate boundaries detected")
        
        return final_aligned_pairs
    
    def _detect_audio_duplicates(
        self,
        aligned_pairs: List[AlignedPair]
    ) -> List[Dict]:
        """
        Detect duplicate audio assignments.
        
        Checks both segment IDs and audio content hashes to catch:
        - Same segment assigned to multiple terms (bug)
        - Different segments with identical audio (recording error)
        
        Skips empty placeholder segments (expected when terms have no valid audio).
        
        Args:
            aligned_pairs: List of aligned pairs to check
            
        Returns:
            List of duplicate dictionaries with details
        """
        import hashlib
        
        duplicates = []
        
        # Pass 1: Check segment IDs (skip empty placeholders)
        segment_ids = {}
        for i, pair in enumerate(aligned_pairs):
            seg_id = pair.audio_segment.segment_id
            
            # Skip empty placeholders - they're expected to be "duplicates"
            if seg_id.startswith('EMPTY_PLACEHOLDER_'):
                continue
            
            if seg_id in segment_ids:
                duplicates.append({
                    'type': 'segment_id_duplicate',
                    'severity': 'CRITICAL',
                    'term_1_idx': segment_ids[seg_id],
                    'term_2_idx': i,
                    'term_1_english': aligned_pairs[segment_ids[seg_id]].vocabulary_entry.english,
                    'term_2_english': pair.vocabulary_entry.english,
                    'segment_id': seg_id
                })
            else:
                segment_ids[seg_id] = i
        
        # Pass 2: Check audio content hashes (skip empty audio)
        audio_hashes = {}
        for i, pair in enumerate(aligned_pairs):
            # Skip empty placeholders - they all have empty audio data
            if pair.audio_segment.segment_id.startswith('EMPTY_PLACEHOLDER_'):
                continue
            
            audio_hash = hashlib.md5(pair.audio_segment.audio_data.tobytes()).hexdigest()
            if audio_hash in audio_hashes:
                existing_idx = audio_hashes[audio_hash]
                # Only add if not already caught by segment ID check
                already_detected = any(
                    d['term_1_idx'] == existing_idx and d['term_2_idx'] == i 
                    for d in duplicates
                )
                if not already_detected:
                    duplicates.append({
                        'type': 'audio_content_duplicate',
                        'severity': 'ERROR',
                        'term_1_idx': existing_idx,
                        'term_2_idx': i,
                        'term_1_english': aligned_pairs[existing_idx].vocabulary_entry.english,
                        'term_2_english': pair.vocabulary_entry.english,
                        'audio_hash': audio_hash[:8]  # First 8 chars for logging
                    })
            else:
                audio_hashes[audio_hash] = i
        
        return duplicates
    
    def _calculate_new_confidence(
        self,
        similarity: float,
        whisper_confidence: float
    ) -> float:
        """
        Calculate new confidence score based on similarity and Whisper confidence.
        
        Args:
            similarity: Similarity score from assignment
            whisper_confidence: Original Whisper confidence score
            
        Returns:
            New confidence score between 0 and 1
        """
        # Combine similarity and Whisper confidence
        # Weight similarity more heavily since it's the basis for reassignment
        new_confidence = (similarity * 0.7) + (whisper_confidence * 0.3)
        
        return min(1.0, max(0.0, new_confidence))
    
    def _sort_by_temporal_order(
        self,
        aligned_pairs: List[AlignedPair]
    ) -> List[AlignedPair]:
        """
        Sort aligned pairs by audio segment start time.
        
        Args:
            aligned_pairs: List of aligned pairs to sort
            
        Returns:
            Sorted list of aligned pairs
        """
        return sorted(aligned_pairs, key=lambda p: p.audio_segment.start_time)
    
    def identify_reassignments(
        self,
        original_pairs: List[AlignedPair],
        new_pairs: List[AlignedPair],
        assignments: List[Dict]
    ) -> List[Dict]:
        """
        Identify which segments were reassigned to different terms.
        
        Args:
            original_pairs: Original aligned pairs
            new_pairs: New aligned pairs after reassignment
            assignments: Assignment mappings
            
        Returns:
            List of reassignment details
        """
        reassignments = []
        
        for assignment in assignments:
            segment_idx = assignment['segment_index']
            term_idx = assignment['term_index']
            
            # Check if this is a reassignment (segment_idx != term_idx)
            if segment_idx != term_idx:
                original_term = original_pairs[segment_idx].vocabulary_entry
                new_term = original_pairs[term_idx].vocabulary_entry
                
                reassignments.append({
                    'segment_index': segment_idx,
                    'original_term_index': segment_idx,
                    'new_term_index': term_idx,
                    'original_english': original_term.english,
                    'original_cantonese': original_term.cantonese,
                    'new_english': new_term.english,
                    'new_cantonese': new_term.cantonese,
                    'similarity': assignment['similarity'],
                    'audio_start_time': original_pairs[segment_idx].audio_segment.start_time,
                    'audio_end_time': original_pairs[segment_idx].audio_segment.end_time
                })
        
        logger.info(f"Identified {len(reassignments)} reassignments out of {len(assignments)} total assignments")
        
        return reassignments
    
    def handle_low_confidence_assignments(
        self,
        assignments: List[Dict],
        threshold: float = 0.3
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Separate high and low confidence assignments.
        
        Args:
            assignments: List of assignment dictionaries
            threshold: Minimum similarity threshold for acceptance
            
        Returns:
            Tuple of (accepted_assignments, flagged_assignments)
        """
        accepted = []
        flagged = []
        
        for assignment in assignments:
            if assignment['similarity'] >= threshold:
                accepted.append(assignment)
            else:
                flagged.append(assignment)
        
        if flagged:
            logger.warning(
                f"Flagged {len(flagged)} low-confidence assignments "
                f"(similarity < {threshold}) for manual review"
            )
        
        return accepted, flagged



class ReassignmentLogger:
    """
    Provides comprehensive logging for the reassignment process.
    
    Logs similarity matrices, top matches, reassignments, and confidence improvements.
    """
    
    def __init__(self):
        """Initialize the reassignment logger."""
        pass
    
    def log_similarity_matrix(
        self,
        similarity_matrix: np.ndarray,
        transcriptions: List[Dict],
        vocabulary_entries: List[VocabularyEntry],
        top_k: int = 3
    ):
        """
        Log similarity matrix with top matches for each segment.
        
        Args:
            similarity_matrix: NxN similarity matrix
            transcriptions: List of transcription dictionaries
            vocabulary_entries: List of vocabulary entries
            top_k: Number of top matches to show per segment
        """
        logger.info("=" * 80)
        logger.info("SIMILARITY MATRIX - TOP MATCHES")
        logger.info("=" * 80)
        
        n = similarity_matrix.shape[0]
        
        for i in range(n):
            # Get top K matches for this segment
            top_indices = np.argsort(similarity_matrix[i])[::-1][:top_k]
            
            transcribed = transcriptions[i].get('transcribed_jyutping', '')
            logger.info(f"\nSegment #{i+1}: Transcribed as '{transcribed}'")
            
            for rank, j in enumerate(top_indices, 1):
                similarity = similarity_matrix[i, j]
                expected = vocabulary_entries[j].cantonese
                english = vocabulary_entries[j].english
                
                logger.info(
                    f"  {rank}. Term #{j+1} ('{english}' / '{expected}'): "
                    f"similarity = {similarity:.3f}"
                )
        
        logger.info("=" * 80)
    
    def log_reassignments(
        self,
        reassignments: List[Dict],
        transcriptions: List[Dict]
    ):
        """
        Report which segments were reassigned and why.
        
        Args:
            reassignments: List of reassignment details
            transcriptions: List of transcription dictionaries
        """
        if not reassignments:
            logger.info("✅ No reassignments needed - all segments matched optimally")
            print("✅ No reassignments needed - all segments matched optimally")
            return
        
        logger.info("=" * 80)
        logger.info(f"REASSIGNMENTS: {len(reassignments)} segments reassigned")
        logger.info("=" * 80)
        
        print(f"\n🔄 REASSIGNMENTS: {len(reassignments)} segments reassigned")
        print("=" * 80)
        
        for i, reassignment in enumerate(reassignments, 1):
            segment_idx = reassignment['segment_index']
            transcribed = transcriptions[segment_idx].get('transcribed_jyutping', '')
            
            log_msg = (
                f"\n{i}. Segment #{segment_idx+1} (audio {reassignment['audio_start_time']:.2f}s - "
                f"{reassignment['audio_end_time']:.2f}s)\n"
                f"   Transcribed: '{transcribed}'\n"
                f"   Original assignment: Term #{reassignment['original_term_index']+1} "
                f"('{reassignment['original_english']}' / '{reassignment['original_cantonese']}')\n"
                f"   New assignment: Term #{reassignment['new_term_index']+1} "
                f"('{reassignment['new_english']}' / '{reassignment['new_cantonese']}')\n"
                f"   Similarity: {reassignment['similarity']:.3f}"
            )
            
            logger.info(log_msg)
            print(log_msg)
        
        logger.info("=" * 80)
        print("=" * 80)
    
    def log_before_after_mappings(
        self,
        original_pairs: List[AlignedPair],
        new_pairs: List[AlignedPair],
        assignments: List[Dict],
        similarity_matrix: np.ndarray
    ):
        """
        Show before/after mappings with similarity scores.
        
        Args:
            original_pairs: Original aligned pairs
            new_pairs: New aligned pairs after reassignment
            assignments: Assignment mappings
            similarity_matrix: Similarity matrix
        """
        logger.info("=" * 80)
        logger.info("BEFORE/AFTER COMPARISON")
        logger.info("=" * 80)
        
        print("\n📊 BEFORE/AFTER COMPARISON")
        print("=" * 80)
        
        for assignment in assignments:
            segment_idx = assignment['segment_index']
            term_idx = assignment['term_index']
            
            original_term = original_pairs[segment_idx].vocabulary_entry
            new_term = original_pairs[term_idx].vocabulary_entry
            
            # Calculate original similarity (diagonal element)
            original_similarity = similarity_matrix[segment_idx, segment_idx]
            new_similarity = assignment['similarity']
            
            changed = "🔄" if segment_idx != term_idx else "✓"
            
            log_msg = (
                f"\n{changed} Segment #{segment_idx+1}:\n"
                f"   BEFORE: Term #{segment_idx+1} ('{original_term.english}') - "
                f"similarity: {original_similarity:.3f}\n"
                f"   AFTER:  Term #{term_idx+1} ('{new_term.english}') - "
                f"similarity: {new_similarity:.3f}\n"
                f"   Change: {new_similarity - original_similarity:+.3f}"
            )
            
            logger.info(log_msg)
            
            # Only print changed assignments to console
            if segment_idx != term_idx:
                print(log_msg)
        
        logger.info("=" * 80)
        print("=" * 80)
    
    def log_confidence_improvements(
        self,
        original_pairs: List[AlignedPair],
        new_pairs: List[AlignedPair],
        assignments: List[Dict]
    ):
        """
        Display confidence improvements from reassignment.
        
        Args:
            original_pairs: Original aligned pairs
            new_pairs: New aligned pairs after reassignment
            assignments: Assignment mappings
        """
        logger.info("=" * 80)
        logger.info("CONFIDENCE IMPROVEMENTS")
        logger.info("=" * 80)
        
        print("\n📈 CONFIDENCE IMPROVEMENTS")
        print("=" * 80)
        
        # Calculate overall statistics
        original_confidences = [p.alignment_confidence for p in original_pairs]
        new_confidences = [p.alignment_confidence for p in new_pairs]
        
        original_avg = np.mean(original_confidences)
        new_avg = np.mean(new_confidences)
        
        improvements = []
        degradations = []
        
        for assignment in assignments:
            segment_idx = assignment['segment_index']
            
            # Find the new pair for this segment
            # Note: new_pairs are sorted by time, so we need to find by segment
            original_confidence = original_pairs[segment_idx].alignment_confidence
            
            # Find corresponding new pair (same audio segment)
            new_confidence = None
            for new_pair in new_pairs:
                if new_pair.audio_segment.segment_id == original_pairs[segment_idx].audio_segment.segment_id:
                    new_confidence = new_pair.alignment_confidence
                    break
            
            if new_confidence is not None:
                change = new_confidence - original_confidence
                
                if change > 0.01:  # Significant improvement
                    improvements.append({
                        'segment_idx': segment_idx,
                        'original': original_confidence,
                        'new': new_confidence,
                        'change': change
                    })
                elif change < -0.01:  # Significant degradation
                    degradations.append({
                        'segment_idx': segment_idx,
                        'original': original_confidence,
                        'new': new_confidence,
                        'change': change
                    })
        
        summary = (
            f"\nOverall confidence:\n"
            f"   Before: {original_avg:.3f}\n"
            f"   After:  {new_avg:.3f}\n"
            f"   Change: {new_avg - original_avg:+.3f}\n"
            f"\nImprovements: {len(improvements)}\n"
            f"Degradations: {len(degradations)}\n"
            f"Unchanged: {len(assignments) - len(improvements) - len(degradations)}"
        )
        
        logger.info(summary)
        print(summary)
        
        # Show top improvements
        if improvements:
            improvements_sorted = sorted(improvements, key=lambda x: x['change'], reverse=True)
            logger.info("\nTop improvements:")
            print("\nTop improvements:")
            
            for imp in improvements_sorted[:5]:
                msg = (
                    f"   Segment {imp['segment_idx']}: "
                    f"{imp['original']:.3f} → {imp['new']:.3f} "
                    f"({imp['change']:+.3f})"
                )
                logger.info(msg)
                print(msg)
        
        # Show degradations if any
        if degradations:
            degradations_sorted = sorted(degradations, key=lambda x: x['change'])
            logger.warning("\nConfidence degradations:")
            print("\n⚠️  Confidence degradations:")
            
            for deg in degradations_sorted[:5]:
                msg = (
                    f"   Segment {deg['segment_idx']}: "
                    f"{deg['original']:.3f} → {deg['new']:.3f} "
                    f"({deg['change']:+.3f})"
                )
                logger.warning(msg)
                print(msg)
        
        logger.info("=" * 80)
        print("=" * 80)
    
    def generate_reassignment_report(
        self,
        similarity_matrix: np.ndarray,
        assignments: List[Dict],
        reassignments: List[Dict],
        quality_metrics: Dict,
        transcriptions: List[Dict],
        vocabulary_entries: List[VocabularyEntry]
    ) -> str:
        """
        Generate a comprehensive reassignment report.
        
        Args:
            similarity_matrix: Similarity matrix
            assignments: Assignment mappings
            reassignments: Reassignment details
            quality_metrics: Quality metrics from assignment
            transcriptions: Transcription data
            vocabulary_entries: Vocabulary entries
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("GLOBAL REASSIGNMENT REPORT")
        report.append("=" * 80)
        
        # Summary
        report.append(f"\n📊 SUMMARY:")
        report.append(f"   Total segments: {len(assignments)}")
        report.append(f"   Reassignments: {len(reassignments)}")
        report.append(f"   Unchanged: {len(assignments) - len(reassignments)}")
        report.append(f"   Reassignment rate: {len(reassignments)/len(assignments)*100:.1f}%")
        
        # Quality metrics
        report.append(f"\n📈 ASSIGNMENT QUALITY:")
        report.append(f"   Average similarity: {quality_metrics['average_similarity']:.3f}")
        report.append(f"   Min similarity: {quality_metrics['min_similarity']:.3f}")
        report.append(f"   Max similarity: {quality_metrics['max_similarity']:.3f}")
        report.append(f"   High quality (≥0.8): {quality_metrics['high_quality_count']}")
        report.append(f"   Medium quality (0.5-0.8): {quality_metrics['medium_quality_count']}")
        report.append(f"   Low quality (<0.5): {quality_metrics['low_quality_count']}")
        
        # Reassignment details
        if reassignments:
            report.append(f"\n🔄 REASSIGNMENT DETAILS:")
            for i, r in enumerate(reassignments[:10], 1):  # Show first 10
                report.append(
                    f"   {i}. Segment {r['segment_index']}: "
                    f"'{r['original_english']}' → '{r['new_english']}' "
                    f"(similarity: {r['similarity']:.3f})"
                )
            if len(reassignments) > 10:
                report.append(f"   ... and {len(reassignments) - 10} more")
        
        report.append("=" * 80)
        
        return "\n".join(report)



class BoundaryRefiner:
    """
    Refines segment boundaries after global reassignment.
    
    Detects and fixes temporal inconsistencies, silence segments, and boundary
    conflicts that arise from reassigning fixed segments.
    """
    
    def __init__(self, speech_verifier=None, boundary_detector=None):
        """
        Initialize the boundary refiner.
        
        Args:
            speech_verifier: WhisperVerifier instance for transcription
            boundary_detector: SmartBoundaryDetector for candidate generation
        """
        self.speech_verifier = speech_verifier
        self.boundary_detector = boundary_detector
        self.had_conflicts = False
    
    def detect_boundary_conflicts(
        self,
        aligned_pairs: List[AlignedPair]
    ) -> List[Dict]:
        """
        Identify temporal inconsistencies and silence segments.
        
        Detects:
        - Segments out of temporal order (term N ends before term N-1)
        - Segments containing only silence/noise
        - Large gaps between sequential terms
        
        Args:
            aligned_pairs: List of aligned pairs in vocabulary order
            
        Returns:
            List of conflict dictionaries with type and details
        """
        conflicts = []
        
        for i, pair in enumerate(aligned_pairs):
            segment = pair.audio_segment
            
            # Check 1: Segment contains only silence/noise
            if len(segment.audio_data) > 0:
                rms_energy = np.sqrt(np.mean(segment.audio_data ** 2))
                if rms_energy < 0.01:  # Very low energy threshold
                    conflicts.append({
                        'type': 'silence',
                        'term_index': i,
                        'english': pair.vocabulary_entry.english,
                        'cantonese': pair.vocabulary_entry.cantonese,
                        'start_time': segment.start_time,
                        'end_time': segment.end_time,
                        'energy': rms_energy
                    })
                    logger.warning(
                        f"Conflict detected: Term #{i+1} '{pair.vocabulary_entry.english}' "
                        f"has very low energy ({rms_energy:.4f})"
                    )
            
            # Check 2: Out of temporal order with previous term
            if i > 0:
                prev_segment = aligned_pairs[i-1].audio_segment
                
                if segment.end_time < prev_segment.start_time:
                    conflicts.append({
                        'type': 'out_of_order',
                        'term_index': i,
                        'english': pair.vocabulary_entry.english,
                        'cantonese': pair.vocabulary_entry.cantonese,
                        'start_time': segment.start_time,
                        'end_time': segment.end_time,
                        'prev_start': prev_segment.start_time,
                        'prev_end': prev_segment.end_time
                    })
                    logger.warning(
                        f"Conflict detected: Term #{i+1} '{pair.vocabulary_entry.english}' "
                        f"({segment.start_time:.2f}s-{segment.end_time:.2f}s) ends before "
                        f"Term #{i} starts ({prev_segment.start_time:.2f}s)"
                    )
                
                # Check 3: Large gap between sequential terms
                gap = segment.start_time - prev_segment.end_time
                if gap > 2.0:  # More than 2 seconds gap
                    conflicts.append({
                        'type': 'large_gap',
                        'term_index': i,
                        'english': pair.vocabulary_entry.english,
                        'cantonese': pair.vocabulary_entry.cantonese,
                        'gap_size': gap,
                        'gap_start': prev_segment.end_time,
                        'gap_end': segment.start_time
                    })
                    logger.info(
                        f"Large gap detected: {gap:.2f}s between Term #{i} and Term #{i+1}"
                    )
        
        if conflicts:
            self.had_conflicts = True
            logger.info(f"Detected {len(conflicts)} boundary conflicts")
        
        return conflicts
    
    def fix_out_of_order_segment(
        self,
        pair: AlignedPair,
        term_index: int,
        audio_data: np.ndarray,
        sample_rate: int,
        prev_end_time: float,
        next_start_time: Optional[float] = None
    ) -> Optional[AlignedPair]:
        """
        Search for correct audio in temporally consistent region.
        
        ENHANCED: More aggressive search with wider windows and more candidates.
        
        Args:
            pair: The aligned pair with out-of-order segment
            term_index: Index of the term
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            prev_end_time: End time of previous term
            next_start_time: Start time of next term (if exists)
            
        Returns:
            Updated aligned pair with corrected boundaries, or None if no fix found
        """
        if not self.speech_verifier or not self.boundary_detector:
            logger.warning("Cannot fix out-of-order segment: missing verifier or detector")
            return None
        
        expected_cantonese = pair.vocabulary_entry.cantonese
        expected_english = pair.vocabulary_entry.english
        
        # ENHANCED: Wider search window (±3 seconds)
        search_start = max(0, prev_end_time - 1.0)  # 1s overlap with previous
        search_end = next_start_time if next_start_time else min(
            prev_end_time + 10.0,  # Up to 10s after previous (was 8s)
            len(audio_data) / sample_rate
        )
        
        if search_end <= search_start:
            logger.warning(f"Invalid search window for Term #{term_index+1}")
            return None
        
        logger.info(
            f"Searching for '{expected_english}' in window "
            f"{search_start:.2f}s - {search_end:.2f}s (width: {search_end - search_start:.2f}s)"
        )
        
        # Extract search window audio
        start_sample = int(search_start * sample_rate)
        end_sample = int(search_end * sample_rate)
        search_audio = audio_data[start_sample:end_sample]
        
        # ENHANCED: More candidates with smaller sizes for single words
        window_duration = search_end - search_start
        num_candidates = min(20, max(10, int(window_duration / 0.3)))  # Was 8, now 10-20
        
        logger.info(f"  Testing {num_candidates} candidates in {window_duration:.1f}s window")
        
        candidates = self.boundary_detector.segment_audio(
            search_audio,
            expected_count=num_candidates,
            start_offset=0.0,
            force_start_offset=True
        )
        
        # Test each candidate
        best_segment = None
        best_confidence = 0.0
        
        for j, candidate in enumerate(candidates):
            try:
                # ENHANCED: Accept shorter segments for single words (was 0.3s, now 0.2s)
                cand_duration = candidate.end_time - candidate.start_time
                if cand_duration < 0.2:
                    logger.debug(f"    Candidate {j+1}: Skipped (too short: {cand_duration:.2f}s)")
                    continue
                
                # Transcribe candidate
                transcription = self.speech_verifier.transcribe_audio_segment(
                    candidate.audio_data, sample_rate
                )
                
                # Compare with expected
                comparison = self.speech_verifier.compare_transcription_with_expected(
                    transcription['text'], expected_cantonese
                )
                
                # Calculate combined confidence
                confidence = (
                    comparison['similarity'] * 0.7 +
                    transcription['confidence'] * 0.3
                )
                
                if comparison['is_match'] and confidence > best_confidence:
                    best_segment = candidate
                    best_confidence = confidence
                    # Adjust times to absolute position
                    best_segment.start_time = search_start + candidate.start_time
                    best_segment.end_time = search_start + candidate.end_time
                    logger.info(
                        f"  ✓ Found match: {best_segment.start_time:.2f}s-{best_segment.end_time:.2f}s "
                        f"(confidence: {confidence:.2f}, transcribed: '{transcription['text']}')"
                    )
            
            except Exception as e:
                logger.debug(f"Candidate {j} failed: {e}")
                continue
        
        # ENHANCED: Lower threshold for accepting matches (was 0.5, now 0.4)
        if best_segment and best_confidence > 0.4:
            # Create updated pair
            updated_pair = AlignedPair(
                vocabulary_entry=pair.vocabulary_entry,
                audio_segment=best_segment,
                alignment_confidence=best_confidence,
                audio_file_path=pair.audio_file_path
            )
            logger.info(
                f"✓ Fixed Term #{term_index+1}: "
                f"{updated_pair.audio_segment.start_time:.2f}s - "
                f"{updated_pair.audio_segment.end_time:.2f}s"
            )
            return updated_pair
        
        logger.warning(f"✗ Could not fix Term #{term_index+1} (best confidence: {best_confidence:.2f})")
        return None
    
    def fix_silence_segment(
        self,
        pair: AlignedPair,
        term_index: int,
        audio_data: np.ndarray,
        sample_rate: int,
        aligned_pairs: List[AlignedPair]
    ) -> Optional[AlignedPair]:
        """
        Replace silence segment with actual speech from nearby region.
        
        Args:
            pair: The aligned pair with silence segment
            term_index: Index of the term
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            aligned_pairs: All aligned pairs for context
            
        Returns:
            Updated aligned pair with corrected boundaries, or None if no fix found
        """
        # Determine search constraints from neighbors
        prev_end = 0.0
        next_start = len(audio_data) / sample_rate
        
        if term_index > 0:
            prev_end = aligned_pairs[term_index - 1].audio_segment.end_time
        
        if term_index < len(aligned_pairs) - 1:
            next_start = aligned_pairs[term_index + 1].audio_segment.start_time
        
        # Use the same fix as out-of-order (search after previous term)
        return self.fix_out_of_order_segment(
            pair, term_index, audio_data, sample_rate,
            prev_end, next_start
        )
    
    def refine_boundaries(
        self,
        aligned_pairs: List[AlignedPair],
        audio_data: np.ndarray,
        sample_rate: int,
        max_iterations: int = 2
    ) -> List[AlignedPair]:
        """
        Main refinement loop - detects and fixes boundary conflicts.
        
        Args:
            aligned_pairs: List of aligned pairs after global reassignment
            audio_data: Full audio data array
            sample_rate: Audio sample rate
            max_iterations: Maximum refinement iterations
            
        Returns:
            Refined list of aligned pairs
        """
        if not self.speech_verifier or not self.boundary_detector:
            logger.warning("Boundary refinement skipped: missing verifier or detector")
            return aligned_pairs
        
        refined_pairs = aligned_pairs
        
        for iteration in range(max_iterations):
            logger.info(f"\n🔧 Boundary Refinement Iteration {iteration + 1}/{max_iterations}")
            
            # Detect conflicts
            conflicts = self.detect_boundary_conflicts(refined_pairs)
            
            if not conflicts:
                logger.info("✓ No boundary conflicts detected")
                break
            
            # Fix each conflict
            fixes_applied = 0
            
            for conflict in conflicts:
                term_idx = conflict['term_index']
                conflict_type = conflict['type']
                
                logger.info(f"\nFixing {conflict_type} conflict for Term #{term_idx+1}...")
                
                updated_pair = None
                
                if conflict_type == 'out_of_order':
                    # Get previous term's end time
                    prev_end = conflict['prev_end']
                    
                    # Get next term's start time if exists
                    next_start = None
                    if term_idx < len(refined_pairs) - 1:
                        next_start = refined_pairs[term_idx + 1].audio_segment.start_time
                    
                    updated_pair = self.fix_out_of_order_segment(
                        refined_pairs[term_idx],
                        term_idx,
                        audio_data,
                        sample_rate,
                        prev_end,
                        next_start
                    )
                
                elif conflict_type == 'silence':
                    updated_pair = self.fix_silence_segment(
                        refined_pairs[term_idx],
                        term_idx,
                        audio_data,
                        sample_rate,
                        refined_pairs
                    )
                
                # Apply fix if successful
                if updated_pair:
                    refined_pairs[term_idx] = updated_pair
                    fixes_applied += 1
            
            logger.info(f"\n✓ Applied {fixes_applied} boundary fixes")
            
            if fixes_applied == 0:
                logger.info("No fixes could be applied, stopping refinement")
                break
        
        return refined_pairs


class GlobalReassignmentCoordinator:
    """
    Coordinates the complete global reassignment process.
    
    Orchestrates similarity matrix building, Hungarian algorithm assignment,
    segment reassignment, boundary refinement, and comprehensive logging.
    """
    
    def __init__(self, speech_verifier=None, boundary_detector=None):
        """
        Initialize the global reassignment coordinator.
        
        Args:
            speech_verifier: Optional WhisperVerifier for boundary refinement
            boundary_detector: Optional SmartBoundaryDetector for boundary refinement
        """
        self.similarity_builder = SimilarityMatrixBuilder()
        self.hungarian_assigner = HungarianAssigner()
        self.boundary_refiner = BoundaryRefiner(speech_verifier, boundary_detector)
        self.segment_reassigner = SegmentReassigner(boundary_refiner=self.boundary_refiner)
        self.logger = ReassignmentLogger()
    
    def perform_global_reassignment(
        self,
        aligned_pairs: List[AlignedPair],
        verification_results: Dict,
        audio_data: np.ndarray,
        sample_rate: int,
        enable_logging: bool = True
    ) -> Tuple[List[AlignedPair], Dict]:
        """
        Perform complete global reassignment process with boundary refinement.
        
        Args:
            aligned_pairs: Original aligned pairs from initial alignment
            verification_results: Results from Whisper verification containing transcriptions
            audio_data: Full audio data array (required for boundary refinement)
            sample_rate: Audio sample rate (required for boundary refinement)
            enable_logging: Whether to enable comprehensive logging
            
        Returns:
            Tuple of (reassigned_aligned_pairs, reassignment_report)
        """
        logger.info("=" * 80)
        logger.info("GLOBAL TRANSCRIPTION-BASED REASSIGNMENT")
        logger.info("=" * 80)
        
        # Extract transcriptions and vocabulary entries
        transcriptions = verification_results.get('verified_pairs', [])
        vocabulary_entries = [pair.vocabulary_entry for pair in aligned_pairs]
        
        if not transcriptions or not vocabulary_entries:
            logger.warning("No transcriptions or vocabulary entries available for reassignment")
            return aligned_pairs, {'status': 'skipped', 'reason': 'no_data'}
        
        # Step 1: Build similarity matrix
        logger.info("\n📊 Step 1: Building similarity matrix...")
        
        similarity_matrix = self.similarity_builder.build_similarity_matrix(
            transcriptions,
            vocabulary_entries
        )
        
        # Log similarity matrix if enabled
        if enable_logging:
            self.logger.log_similarity_matrix(
                similarity_matrix,
                transcriptions,
                vocabulary_entries,
                top_k=3
            )
        
        # Step 2: Find optimal assignment using Hungarian algorithm
        logger.info("\n🎯 Step 2: Finding optimal assignment with Hungarian algorithm...")
        
        row_indices, col_indices = self.hungarian_assigner.find_optimal_assignment(
            similarity_matrix
        )
        
        # Extract assignment mappings
        assignments = self.hungarian_assigner.extract_assignment_mapping(
            row_indices,
            col_indices,
            similarity_matrix
        )
        
        # Calculate assignment quality
        quality_metrics = self.hungarian_assigner.calculate_assignment_quality(
            assignments,
            similarity_matrix
        )
        
        logger.info(
            f"Assignment quality: avg={quality_metrics['average_similarity']:.3f}, "
            f"high={quality_metrics['high_quality_count']}, "
            f"medium={quality_metrics['medium_quality_count']}, "
            f"low={quality_metrics['low_quality_count']}"
        )
        
        # Step 3: Reassign segments
        logger.info("\n🔄 Step 3: Reassigning segments to terms...")
        
        new_aligned_pairs = self.segment_reassigner.reassign_segments(
            aligned_pairs,
            assignments,
            similarity_matrix,
            transcriptions,
            min_similarity_threshold=0.3,  # Reject assignments below 0.3
            audio_data=audio_data,
            sample_rate=sample_rate
        )
        
        # Identify which segments were reassigned
        reassignments = self.segment_reassigner.identify_reassignments(
            aligned_pairs,
            new_aligned_pairs,
            assignments
        )
        
        # Step 3.5: POST-REASSIGNMENT VALIDATION
        logger.info("\n🔍 Step 3.5: Validating reassignment quality...")
        print("\n🔍 Step 3.5: Validating reassignment quality...")
        
        reverted_count = 0
        for i, pair in enumerate(new_aligned_pairs):
            new_segment = pair.audio_segment
            new_confidence = pair.alignment_confidence
            
            # Get original segment and confidence for comparison
            original_segment = aligned_pairs[i].audio_segment
            original_confidence = aligned_pairs[i].alignment_confidence
            
            # Check if this segment was actually reassigned
            was_reassigned = (new_segment.segment_id != original_segment.segment_id)
            
            if not was_reassigned:
                # Not reassigned, no need to validate
                continue
            
            # Calculate energy for both segments
            new_energy = 0.0
            if len(new_segment.audio_data) > 0:
                new_energy = np.sqrt(np.mean(new_segment.audio_data ** 2))
            
            original_energy = 0.0
            if len(original_segment.audio_data) > 0:
                original_energy = np.sqrt(np.mean(original_segment.audio_data ** 2))
            
            # Determine if we should revert
            should_revert = False
            revert_reason = ""
            
            # Check 1: New segment is silence (very low energy)
            if new_energy < 0.01:
                should_revert = True
                revert_reason = f"new segment is silence (energy: {new_energy:.4f})"
            
            # Check 2: New confidence is significantly worse than original
            elif new_confidence < original_confidence - 0.15:
                should_revert = True
                revert_reason = f"new confidence ({new_confidence:.2f}) much worse than original ({original_confidence:.2f})"
            
            # Check 3: New segment has much lower energy than original (possible silence)
            elif new_energy < original_energy * 0.3 and original_energy > 0.02:
                should_revert = True
                revert_reason = f"new segment much quieter (energy: {new_energy:.4f} vs {original_energy:.4f})"
            
            if should_revert:
                logger.warning(
                    f"⚠️  Term #{i+1} ('{pair.vocabulary_entry.english}'): "
                    f"Reverting reassignment - {revert_reason}"
                )
                logger.warning(
                    f"   Original: confidence={original_confidence:.2f}, energy={original_energy:.4f}"
                )
                logger.warning(
                    f"   New:      confidence={new_confidence:.2f}, energy={new_energy:.4f}"
                )
                
                # CRITICAL FIX: Check if original segment is available before reverting
                # If original segment is owned by another term, keep the reassigned segment
                # to avoid creating duplicates
                original_segment_idx = i  # In original alignment, term i has segment i
                original_boundaries = (
                    aligned_pairs[original_segment_idx].audio_segment.start_time,
                    aligned_pairs[original_segment_idx].audio_segment.end_time
                )
                
                # Check if any other term is using these boundaries
                segment_is_available = True
                current_segment_owner = None
                for j, check_pair in enumerate(new_aligned_pairs):
                    if j == i:  # Skip self
                        continue
                    check_boundaries = (
                        check_pair.audio_segment.start_time,
                        check_pair.audio_segment.end_time
                    )
                    # Compare boundaries with small tolerance for floating point
                    if (abs(check_boundaries[0] - original_boundaries[0]) < 0.001 and
                        abs(check_boundaries[1] - original_boundaries[1]) < 0.001):
                        segment_is_available = False
                        current_segment_owner = j
                        break
                
                if not segment_is_available:
                    logger.error(
                        f"   ✗ CANNOT REVERT: Original Segment #{original_segment_idx+1} "
                        f"({original_boundaries[0]:.2f}s-{original_boundaries[1]:.2f}s) "
                        f"is now owned by Term #{current_segment_owner+1} ('{new_aligned_pairs[current_segment_owner].vocabulary_entry.english}')"
                    )
                    logger.error(
                        f"   → Keeping reassigned segment to avoid duplicate"
                    )
                    # Don't revert - keep the reassigned segment even if it's poor quality
                else:
                    # Original segment available - safe to revert
                    logger.info(f"   ✓ Reverting to original Segment #{original_segment_idx+1}")
                    new_aligned_pairs[i] = aligned_pairs[i]
                    reverted_count += 1
            else:
                logger.debug(
                    f"✓ Term #{i+1} ('{pair.vocabulary_entry.english}'): "
                    f"Reassignment accepted (confidence: {original_confidence:.2f} → {new_confidence:.2f})"
                )
        
        if reverted_count > 0:
            logger.warning(f"⚠️  Reverted {reverted_count} poor reassignments to original segments")
        else:
            logger.info("✓ All reassignments passed quality validation")
        
        # Step 4: Boundary refinement
        # Run boundary refinement if audio data is available, regardless of whether
        # there were reassignments. Boundary refinement can detect and fix issues
        # like silence segments and out-of-order segments independently.
        logger.info(f"\n🔍 DEBUG: Checking boundary refinement conditions:")
        logger.info(f"   - reassignments: {len(reassignments)} items")
        logger.info(f"   - audio_data: {'present (' + str(len(audio_data)) + ' samples)' if audio_data is not None else 'None'}")
        logger.info(f"   - sample_rate: {sample_rate if sample_rate is not None else 'None'}")
        
        if audio_data is not None and sample_rate is not None:
            logger.info("\n🔧 Step 4: Refining boundaries for segments...")
            print("\n🔧 Step 4: Refining boundaries for segments...")
            
            refined_pairs = self.boundary_refiner.refine_boundaries(
                new_aligned_pairs,
                audio_data,
                sample_rate,
                max_iterations=2
            )
            
            # If refinement made changes, update pairs
            if self.boundary_refiner.had_conflicts:
                logger.info("✓ Boundary refinement completed with fixes applied")
                new_aligned_pairs = refined_pairs
            else:
                logger.info("✓ No boundary conflicts detected")
        else:
            logger.info("\n⚠️  Skipping boundary refinement (audio data not provided)")
        
        # Step 5: Comprehensive logging
        if enable_logging:
            logger.info("\n📝 Step 5: Generating comprehensive logs...")
            print("\n📝 Step 5: Generating comprehensive logs...")
            
            self.logger.log_reassignments(reassignments, transcriptions)
            self.logger.log_before_after_mappings(
                aligned_pairs,
                new_aligned_pairs,
                assignments,
                similarity_matrix
            )
            self.logger.log_confidence_improvements(
                aligned_pairs,
                new_aligned_pairs,
                assignments
            )
        
        # Generate final report
        report = self.logger.generate_reassignment_report(
            similarity_matrix,
            assignments,
            reassignments,
            quality_metrics,
            transcriptions,
            vocabulary_entries
        )
        
        logger.info("\n" + report)
        print("\n" + report)
        
        logger.info("=" * 80)
        logger.info("GLOBAL REASSIGNMENT COMPLETE")
        logger.info("=" * 80)
        
        print("\n" + "=" * 80)
        print("✅ GLOBAL REASSIGNMENT COMPLETE")
        print("=" * 80 + "\n")
        
        # Return reassigned pairs and report data
        return new_aligned_pairs, {
            'status': 'completed',
            'total_segments': len(aligned_pairs),
            'reassignments': len(reassignments),
            'quality_metrics': quality_metrics,
            'reassignment_details': reassignments,
            'report': report,
            'boundary_conflicts_fixed': self.boundary_refiner.had_conflicts
        }
