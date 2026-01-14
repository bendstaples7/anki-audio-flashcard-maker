"""
Dynamic per-term alignment system.

This module implements intelligent per-term alignment that searches for the best
matching audio segment for each vocabulary term, rather than using a consistent offset.
"""

import logging
from typing import List, Tuple, Optional, Dict
import numpy as np

from ..models import AudioSegment, VocabularyEntry, AlignedPair


logger = logging.getLogger(__name__)


class DynamicAligner:
    """
    Dynamic alignment system that finds the best audio segment for each vocabulary term.
    
    Instead of using a consistent offset, this system:
    1. For each vocabulary term, tests multiple audio segments
    2. Uses Whisper to transcribe and compare each candidate
    3. Selects the segment with the highest semantic match
    4. Ensures no duplicate segment assignments
    """
    
    def __init__(self, speech_verifier=None):
        """
        Initialize dynamic aligner.
        
        Args:
            speech_verifier: WhisperVerifier instance for transcription
        """
        self.speech_verifier = speech_verifier
        self.sample_rate = 22050  # Standard sample rate
        
        # Search parameters - ULTRA AGGRESSIVE for maximum correction
        self.search_window = len(audio_segments) if hasattr(self, 'audio_segments') else 50  # Search ALL available segments
        self.min_confidence_threshold = 0.15  # Ultra low threshold for desperate matches
        self.similarity_threshold = 0.1  # Ultra low similarity threshold for desperate matches
        self.fallback_threshold = 0.05  # Even lower threshold for last resort matches
        
        # CRITICAL: Ensure we NEVER lose vocabulary entries
        self.preserve_all_vocabulary = True
        self.max_search_attempts = 3  # Try multiple search strategies
    
    def align_vocabulary_to_audio(
        self, 
        vocab_entries: List[VocabularyEntry],
        audio_segments: List[AudioSegment],
        initial_offset: int = 0,
        progress_callback=None
    ) -> List[AlignedPair]:
        """
        Dynamically align vocabulary entries to audio segments with SEMANTIC-FIRST assignment.
        
        This method prioritizes semantic correctness over positional expectations:
        1. Each vocabulary term gets the audio segment that best matches its semantic content
        2. Each audio segment is used by AT MOST one vocabulary term
        3. Semantic matches (detected via Whisper) get highest priority
        4. Iterative refinement to fix detected mismatches
        
        Args:
            vocab_entries: List of vocabulary entries to align
            audio_segments: List of available audio segments
            initial_offset: Starting offset for search (default: 0)
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of aligned pairs with optimal semantic matches and strict uniqueness
        """
        if not self.speech_verifier:
            logger.warning("No speech verifier available - falling back to sequential alignment")
            return self._fallback_sequential_alignment(vocab_entries, audio_segments, initial_offset)
        
        logger.info(f"🎯 Starting SEMANTIC-FIRST dynamic alignment for {len(vocab_entries)} vocabulary entries")
        logger.info(f"   Available audio segments: {len(audio_segments)}")
        logger.info(f"   🧠 SEMANTIC PRIORITY: Terms get audio that matches their content")
        logger.info(f"   🔒 STRICT UNIQUENESS: Each segment used by exactly one term")
        logger.info(f"   🔄 ITERATIVE REFINEMENT: Fix detected mismatches")
        logger.info(f"   Initial offset: {initial_offset:+d}")
        
        # PHASE 1: Calculate semantic matches for all term-segment combinations
        logger.info(f"\n🔍 PHASE 1: Calculating semantic matches for all combinations...")
        semantic_matrix = {}  # (vocab_idx, segment_idx) -> match_data
        
        for vocab_idx, vocab_entry in enumerate(vocab_entries):
            if progress_callback:
                progress_callback(vocab_idx, len(vocab_entries), f"Analyzing '{vocab_entry.english}'")
            
            logger.info(f"   Term {vocab_idx + 1}: '{vocab_entry.english}' → '{vocab_entry.cantonese}'")
            
            # Test ALL segments for semantic match with this term
            for segment_idx in range(len(audio_segments)):
                segment = audio_segments[segment_idx]
                expected_segment_idx = vocab_idx + initial_offset
                
                match_result = self._test_segment_match(segment_idx, segment, vocab_entry, expected_segment_idx)
                if match_result:
                    semantic_matrix[(vocab_idx, segment_idx)] = match_result
        
        # PHASE 2: Create semantic-priority assignment matrix
        logger.info(f"\n🔍 PHASE 2: Creating semantic-priority assignment matrix...")
        
        # Find all semantic matches (high similarity + is_match = True)
        semantic_matches = []
        for (vocab_idx, segment_idx), match_data in semantic_matrix.items():
            if match_data['is_semantic_match'] and match_data['semantic_similarity'] >= 0.6:
                semantic_matches.append((vocab_idx, segment_idx, match_data))
        
        # Sort semantic matches by quality (best first)
        semantic_matches.sort(key=lambda x: x[2]['match_score'], reverse=True)
        
        logger.info(f"   Found {len(semantic_matches)} high-quality semantic matches")
        for i, (vocab_idx, segment_idx, match_data) in enumerate(semantic_matches[:5]):
            vocab_entry = vocab_entries[vocab_idx]
            logger.info(f"      {i+1}. '{vocab_entry.english}' ↔ Segment {segment_idx} (score: {match_data['match_score']:.3f})")
            logger.info(f"         Expected: '{vocab_entry.cantonese}' | Got: '{match_data['transcribed_jyutping']}'")
        
        # PHASE 3: Assign semantic matches first (greedy assignment)
        logger.info(f"\n🔍 PHASE 3: Assigning semantic matches with conflict resolution...")
        
        assigned_pairs = []
        used_segments = set()
        assigned_terms = set()
        
        # Assign semantic matches in order of quality
        for vocab_idx, segment_idx, match_data in semantic_matches:
            if vocab_idx not in assigned_terms and segment_idx not in used_segments:
                vocab_entry = vocab_entries[vocab_idx]
                segment = audio_segments[segment_idx]
                
                aligned_pair = AlignedPair(
                    vocabulary_entry=vocab_entry,
                    audio_segment=segment,
                    alignment_confidence=match_data['match_score'],
                    audio_file_path=""
                )
                assigned_pairs.append(aligned_pair)
                
                used_segments.add(segment_idx)
                assigned_terms.add(vocab_idx)
                
                expected_segment_idx = vocab_idx + initial_offset
                offset_from_expected = segment_idx - expected_segment_idx
                
                logger.info(f"   ✅ SEMANTIC MATCH: Term {vocab_idx + 1} '{vocab_entry.english}' → Segment {segment_idx}")
                logger.info(f"      Score: {match_data['match_score']:.3f}, Offset: {offset_from_expected:+d}")
                logger.info(f"      Expected: '{vocab_entry.cantonese}' | Got: '{match_data['transcribed_jyutping']}'")
        
        # PHASE 4: Assign remaining terms using best available matches
        logger.info(f"\n🔍 PHASE 4: Assigning remaining terms...")
        
        unassigned_terms = [i for i in range(len(vocab_entries)) if i not in assigned_terms]
        logger.info(f"   Unassigned terms: {len(unassigned_terms)}")
        
        # For each unassigned term, find the best available segment
        for vocab_idx in unassigned_terms:
            vocab_entry = vocab_entries[vocab_idx]
            
            # Find best available segment for this term
            best_segment_idx = None
            best_match_data = None
            best_score = 0.0
            
            for segment_idx in range(len(audio_segments)):
                if segment_idx not in used_segments:
                    match_key = (vocab_idx, segment_idx)
                    if match_key in semantic_matrix:
                        match_data = semantic_matrix[match_key]
                        if match_data['match_score'] > best_score:
                            best_score = match_data['match_score']
                            best_segment_idx = segment_idx
                            best_match_data = match_data
            
            if best_segment_idx is not None:
                segment = audio_segments[best_segment_idx]
                
                aligned_pair = AlignedPair(
                    vocabulary_entry=vocab_entry,
                    audio_segment=segment,
                    alignment_confidence=best_match_data['match_score'],
                    audio_file_path=""
                )
                assigned_pairs.append(aligned_pair)
                
                used_segments.add(best_segment_idx)
                assigned_terms.add(vocab_idx)
                
                expected_segment_idx = vocab_idx + initial_offset
                offset_from_expected = best_segment_idx - expected_segment_idx
                
                logger.info(f"   ✅ BEST AVAILABLE: Term {vocab_idx + 1} '{vocab_entry.english}' → Segment {best_segment_idx}")
                logger.info(f"      Score: {best_match_data['match_score']:.3f}, Offset: {offset_from_expected:+d}")
                logger.info(f"      Expected: '{vocab_entry.cantonese}' | Got: '{best_match_data['transcribed_jyutping']}'")
            else:
                logger.warning(f"   ⚠️ No available segment for term {vocab_idx + 1}: '{vocab_entry.english}'")
        
        # PHASE 5: Handle any remaining unassigned terms with fallback
        final_unassigned = [i for i in range(len(vocab_entries)) if i not in assigned_terms]
        if final_unassigned:
            logger.info(f"\n🔍 PHASE 5: Fallback assignment for {len(final_unassigned)} remaining terms...")
            
            remaining_segments = [i for i in range(len(audio_segments)) if i not in used_segments]
            logger.info(f"   Remaining segments: {remaining_segments}")
            
            for vocab_idx in final_unassigned:
                vocab_entry = vocab_entries[vocab_idx]
                
                if remaining_segments:
                    # Use positional preference for fallback
                    expected_segment_idx = vocab_idx + initial_offset
                    
                    # Find closest available segment to expected position
                    best_segment_idx = remaining_segments[0]  # Default to first available
                    min_distance = abs(best_segment_idx - expected_segment_idx)
                    
                    for segment_idx in remaining_segments:
                        distance = abs(segment_idx - expected_segment_idx)
                        if distance < min_distance:
                            min_distance = distance
                            best_segment_idx = segment_idx
                    
                    segment = audio_segments[best_segment_idx]
                    remaining_segments.remove(best_segment_idx)
                    
                    aligned_pair = AlignedPair(
                        vocabulary_entry=vocab_entry,
                        audio_segment=segment,
                        alignment_confidence=0.2,  # Low confidence for fallback
                        audio_file_path=""
                    )
                    assigned_pairs.append(aligned_pair)
                    
                    used_segments.add(best_segment_idx)
                    assigned_terms.add(vocab_idx)
                    
                    offset_from_expected = best_segment_idx - expected_segment_idx
                    
                    logger.info(f"   🔄 FALLBACK: Term {vocab_idx + 1} '{vocab_entry.english}' → Segment {best_segment_idx}")
                    logger.info(f"      Positional fallback (offset: {offset_from_expected:+d})")
                else:
                    logger.error(f"   ❌ CRITICAL: No segments left for term {vocab_idx + 1}: '{vocab_entry.english}'")
        
        # PHASE 6: Verification and iterative refinement
        logger.info(f"\n🔍 PHASE 6: Verification and iterative refinement...")
        
        # Detect remaining semantic mismatches
        mismatches = []
        for pair in assigned_pairs:
            vocab_idx = vocab_entries.index(pair.vocabulary_entry)
            segment_idx = None
            for i, segment in enumerate(audio_segments):
                if segment == pair.audio_segment:
                    segment_idx = i
                    break
            
            if segment_idx is not None:
                match_key = (vocab_idx, segment_idx)
                if match_key in semantic_matrix:
                    match_data = semantic_matrix[match_key]
                    if not match_data['is_semantic_match'] or match_data['semantic_similarity'] < 0.4:
                        mismatches.append((pair, vocab_idx, segment_idx, match_data))
        
        logger.info(f"   Detected {len(mismatches)} potential semantic mismatches")
        
        # Try to fix mismatches through swapping (limited attempts)
        if mismatches and len(mismatches) <= 5:  # Only try to fix a few mismatches
            logger.info(f"   Attempting to fix {len(mismatches)} mismatches through swapping...")
            
            for mismatch_pair, vocab_idx, segment_idx, match_data in mismatches:
                logger.info(f"      Mismatch: '{mismatch_pair.vocabulary_entry.english}' has wrong audio")
                logger.info(f"         Expected: '{mismatch_pair.vocabulary_entry.cantonese}'")
                logger.info(f"         Got: '{match_data['transcribed_jyutping']}' (similarity: {match_data['semantic_similarity']:.2f})")
                
                # Look for a better semantic match for this term among assigned pairs
                best_swap_candidate = None
                best_swap_score = match_data['semantic_similarity']
                
                for other_pair in assigned_pairs:
                    if other_pair == mismatch_pair:
                        continue
                    
                    other_vocab_idx = vocab_entries.index(other_pair.vocabulary_entry)
                    other_segment_idx = None
                    for i, segment in enumerate(audio_segments):
                        if segment == other_pair.audio_segment:
                            other_segment_idx = i
                            break
                    
                    if other_segment_idx is not None:
                        # Test if swapping would improve both pairs
                        swap_key1 = (vocab_idx, other_segment_idx)
                        swap_key2 = (other_vocab_idx, segment_idx)
                        
                        if swap_key1 in semantic_matrix and swap_key2 in semantic_matrix:
                            swap_data1 = semantic_matrix[swap_key1]
                            swap_data2 = semantic_matrix[swap_key2]
                            
                            # Calculate improvement
                            current_total = match_data['semantic_similarity'] + semantic_matrix.get((other_vocab_idx, other_segment_idx), {}).get('semantic_similarity', 0)
                            swap_total = swap_data1['semantic_similarity'] + swap_data2['semantic_similarity']
                            
                            if swap_total > current_total + 0.2:  # Require significant improvement
                                best_swap_candidate = (other_pair, swap_data1, swap_data2)
                                best_swap_score = swap_total
                
                # Perform swap if beneficial
                if best_swap_candidate:
                    other_pair, swap_data1, swap_data2 = best_swap_candidate
                    
                    # Swap the audio segments
                    temp_segment = mismatch_pair.audio_segment
                    mismatch_pair.audio_segment = other_pair.audio_segment
                    other_pair.audio_segment = temp_segment
                    
                    # Update confidences
                    mismatch_pair.alignment_confidence = swap_data1['match_score']
                    other_pair.alignment_confidence = swap_data2['match_score']
                    
                    logger.info(f"      ✅ SWAPPED: Improved semantic alignment for both terms")
                    logger.info(f"         '{mismatch_pair.vocabulary_entry.english}' now gets: '{swap_data1['transcribed_jyutping']}'")
                    logger.info(f"         '{other_pair.vocabulary_entry.english}' now gets: '{swap_data2['transcribed_jyutping']}'")
                else:
                    logger.info(f"      ❌ No beneficial swap found for '{mismatch_pair.vocabulary_entry.english}'")
        
        # PHASE 7: Final verification and summary
        logger.info(f"\n📊 SEMANTIC-FIRST ALIGNMENT COMPLETE:")
        logger.info(f"   Vocabulary entries: {len(vocab_entries)}")
        logger.info(f"   Aligned pairs created: {len(assigned_pairs)}")
        logger.info(f"   Segments used: {len(used_segments)}/{len(audio_segments)}")
        logger.info(f"   Assignment coverage: {len(assigned_pairs)}/{len(vocab_entries)} ({len(assigned_pairs)/len(vocab_entries)*100:.1f}%)")
        
        # Verify uniqueness
        segment_usage = {}
        for pair in assigned_pairs:
            for i, segment in enumerate(audio_segments):
                if segment == pair.audio_segment:
                    segment_usage[i] = segment_usage.get(i, 0) + 1
                    break
        
        duplicates = {seg_idx: count for seg_idx, count in segment_usage.items() if count > 1}
        if duplicates:
            logger.error(f"   🚨 DUPLICATE SEGMENTS DETECTED: {duplicates}")
            logger.error(f"   This should not happen with strict unique assignment!")
        else:
            logger.info(f"   ✅ UNIQUENESS VERIFIED: No duplicate segment assignments")
        
        # Calculate final statistics
        high_confidence = sum(1 for p in assigned_pairs if p.alignment_confidence >= 0.8)
        medium_confidence = sum(1 for p in assigned_pairs if 0.6 <= p.alignment_confidence < 0.8)
        low_confidence = sum(1 for p in assigned_pairs if p.alignment_confidence < 0.6)
        
        # Count semantic matches in final result
        final_semantic_matches = 0
        for pair in assigned_pairs:
            vocab_idx = vocab_entries.index(pair.vocabulary_entry)
            segment_idx = None
            for i, segment in enumerate(audio_segments):
                if segment == pair.audio_segment:
                    segment_idx = i
                    break
            
            if segment_idx is not None:
                match_key = (vocab_idx, segment_idx)
                if match_key in semantic_matrix:
                    match_data = semantic_matrix[match_key]
                    if match_data['is_semantic_match'] and match_data['semantic_similarity'] >= 0.6:
                        final_semantic_matches += 1
        
        logger.info(f"   High confidence (≥80%): {high_confidence}")
        logger.info(f"   Medium confidence (60-80%): {medium_confidence}")
        logger.info(f"   Low confidence (<60%): {low_confidence}")
        logger.info(f"   Semantic matches: {final_semantic_matches} ({final_semantic_matches/len(assigned_pairs)*100:.1f}%)")
        
        if final_semantic_matches > 0:
            logger.info(f"   ✅ {final_semantic_matches} terms have semantically correct audio!")
        
        if low_confidence > 0:
            logger.warning(f"   ⚠️ {low_confidence} pairs have low confidence - review recommended")
        
        return assigned_pairs
    
    def _test_segment_match(self, segment_idx: int, segment: AudioSegment, vocab_entry: VocabularyEntry, expected_segment_idx: int) -> Optional[Dict]:
        """
        Test a single segment for matching with a vocabulary entry.
        
        Args:
            segment_idx: Index of the segment being tested
            segment: Audio segment to test
            vocab_entry: Vocabulary entry to match against
            expected_segment_idx: Expected segment index for this vocabulary entry
            
        Returns:
            Dictionary with match results or None if testing failed
        """
        try:
            # Transcribe this segment
            transcription = self.speech_verifier.transcribe_audio_segment(
                segment.audio_data, self.sample_rate
            )
            
            # Compare with expected Cantonese
            comparison = self.speech_verifier.compare_transcription_with_expected(
                transcription['text'], vocab_entry.cantonese
            )
            
            # Calculate match score - SEMANTIC-FIRST APPROACH
            whisper_confidence = transcription['confidence']
            semantic_similarity = comparison['similarity']
            is_semantic_match = comparison['is_match']
            
            # SEMANTIC-FIRST SCORING: Prioritize semantic correctness heavily
            if is_semantic_match and semantic_similarity >= 0.8:
                # Excellent semantic match - highest priority
                match_score = 0.9 + (0.1 * whisper_confidence)
            elif is_semantic_match and semantic_similarity >= 0.6:
                # Good semantic match - high priority
                match_score = 0.7 + (0.2 * semantic_similarity)
            elif semantic_similarity >= 0.4:
                # Partial semantic match - medium priority
                match_score = 0.4 + (0.3 * semantic_similarity)
            else:
                # Poor semantic match - low priority, mainly based on position
                match_score = 0.1 + (0.1 * whisper_confidence)
                
                # Small bonus for being close to expected position
                distance_from_expected = abs(segment_idx - expected_segment_idx)
                if distance_from_expected <= 2:
                    match_score += 0.1 * (1.0 - distance_from_expected / 2.0)
            
            # Get Jyutping for display
            transcribed_jyutping = comparison.get('transcribed_jyutping', '')
            
            # ALWAYS log semantic analysis for transparency
            if is_semantic_match:
                match_indicator = "✅ SEMANTIC MATCH"
            elif semantic_similarity >= 0.4:
                match_indicator = "🔶 PARTIAL MATCH"
            else:
                match_indicator = "❌ MISMATCH"
            
            # Log detailed analysis for good matches or semantic issues
            if match_score > 0.3 or is_semantic_match or semantic_similarity < 0.3:
                logger.debug(f"      Segment {segment_idx}: {match_indicator} score={match_score:.3f}")
                logger.debug(f"         Expected: '{vocab_entry.cantonese}'")
                logger.debug(f"         Got: '{transcription['text']}' → '{transcribed_jyutping}'")
                logger.debug(f"         Similarity: {semantic_similarity:.3f}, Whisper: {whisper_confidence:.2f}")
            
            return {
                'segment': segment,
                'segment_idx': segment_idx,
                'transcription': transcription,
                'comparison': comparison,
                'match_score': match_score,
                'whisper_confidence': whisper_confidence,
                'semantic_similarity': semantic_similarity,
                'is_semantic_match': is_semantic_match,
                'transcribed_text': transcription['text'],
                'transcribed_jyutping': transcribed_jyutping,
                'distance_from_expected': abs(segment_idx - expected_segment_idx)
            }
        
        except Exception as e:
            logger.debug(f"   Segment {segment_idx}: Error during transcription: {e}")
            return None
    
    def _fallback_sequential_alignment(
        self,
        vocab_entries: List[VocabularyEntry],
        audio_segments: List[AudioSegment],
        offset: int = 0
    ) -> List[AlignedPair]:
        """
        Fallback to sequential alignment when speech verification is unavailable.
        
        Args:
            vocab_entries: List of vocabulary entries
            audio_segments: List of audio segments
            offset: Alignment offset
            
        Returns:
            List of aligned pairs using sequential alignment
        """
        logger.warning("Using fallback sequential alignment (speech verification unavailable)")
        
        aligned_pairs = []
        max_pairs = min(len(audio_segments) - offset, len(vocab_entries)) if offset >= 0 else min(len(audio_segments), len(vocab_entries) + offset)
        
        for i in range(max_pairs):
            if offset >= 0:
                segment_idx = i + offset
                vocab_idx = i
            else:
                segment_idx = i
                vocab_idx = i + abs(offset)
            
            if segment_idx < len(audio_segments) and vocab_idx < len(vocab_entries):
                aligned_pair = AlignedPair(
                    vocabulary_entry=vocab_entries[vocab_idx],
                    audio_segment=audio_segments[segment_idx],
                    alignment_confidence=0.7,  # Default confidence
                    audio_file_path=""
                )
                aligned_pairs.append(aligned_pair)
        
        return aligned_pairs
    
    def verify_alignment_quality(self, aligned_pairs: List[AlignedPair]) -> Dict:
        """
        Verify the quality of dynamic alignment.
        
        Args:
            aligned_pairs: List of aligned pairs to verify
            
        Returns:
            Dictionary with verification statistics
        """
        if not aligned_pairs:
            return {
                'total_pairs': 0,
                'average_confidence': 0.0,
                'high_confidence_count': 0,
                'semantic_matches': 0,
                'quality': 'none'
            }
        
        total_pairs = len(aligned_pairs)
        avg_confidence = sum(p.alignment_confidence for p in aligned_pairs) / total_pairs
        high_confidence = sum(1 for p in aligned_pairs if p.alignment_confidence >= 0.8)
        
        # Determine overall quality
        if avg_confidence >= 0.8:
            quality = 'excellent'
        elif avg_confidence >= 0.6:
            quality = 'good'
        elif avg_confidence >= 0.4:
            quality = 'fair'
        else:
            quality = 'poor'
        
        return {
            'total_pairs': total_pairs,
            'average_confidence': avg_confidence,
            'high_confidence_count': high_confidence,
            'high_confidence_percentage': (high_confidence / total_pairs) * 100,
            'quality': quality
        }
