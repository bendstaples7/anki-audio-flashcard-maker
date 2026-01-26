"""
Unit tests for global transcription-based segment reassignment.

Tests the similarity matrix builder, Hungarian algorithm integration,
segment reassignment logic, and logging functionality.
"""

import pytest
import numpy as np
from cantonese_anki_generator.alignment.global_reassignment import (
    SimilarityMatrixBuilder,
    HungarianAssigner,
    SegmentReassigner,
    ReassignmentLogger,
    GlobalReassignmentCoordinator
)
from cantonese_anki_generator.models import (
    VocabularyEntry,
    AudioSegment,
    AlignedPair
)


class TestSimilarityMatrixBuilder:
    """Test the similarity matrix builder."""
    
    def test_build_similarity_matrix_basic(self):
        """Test basic similarity matrix construction."""
        builder = SimilarityMatrixBuilder()
        
        # Create test data
        transcriptions = [
            {'transcribed_jyutping': 'jat1', 'whisper_confidence': 0.9},
            {'transcribed_jyutping': 'ji6', 'whisper_confidence': 0.8},
            {'transcribed_jyutping': 'saam1', 'whisper_confidence': 0.85}
        ]
        
        vocab_entries = [
            VocabularyEntry(english='one', cantonese='jat1', row_index=0),
            VocabularyEntry(english='two', cantonese='ji6', row_index=1),
            VocabularyEntry(english='three', cantonese='saam1', row_index=2)
        ]
        
        # Build matrix
        matrix = builder.build_similarity_matrix(transcriptions, vocab_entries)
        
        # Verify shape
        assert matrix.shape == (3, 3)
        
        # Verify diagonal elements are high (exact matches)
        assert matrix[0, 0] > 0.8  # jat1 matches jat1
        assert matrix[1, 1] > 0.7  # ji6 matches ji6
        assert matrix[2, 2] > 0.8  # saam1 matches saam1
    
    def test_calculate_jyutping_similarity_exact_match(self):
        """Test exact match similarity."""
        builder = SimilarityMatrixBuilder()
        
        similarity = builder._calculate_jyutping_similarity('jat1', 'jat1')
        assert similarity == 1.0
    
    def test_calculate_jyutping_similarity_no_match(self):
        """Test no match similarity."""
        builder = SimilarityMatrixBuilder()
        
        similarity = builder._calculate_jyutping_similarity('jat1', 'completely different')
        assert similarity < 0.5
    
    def test_calculate_jyutping_similarity_partial_match(self):
        """Test partial match similarity."""
        builder = SimilarityMatrixBuilder()
        
        # Similar sounds without tones
        similarity = builder._calculate_jyutping_similarity('jat1', 'jat6')
        assert 0.5 < similarity < 1.0
    
    def test_normalize_text(self):
        """Test text normalization."""
        builder = SimilarityMatrixBuilder()
        
        normalized = builder._normalize_text('  JAT1,  ')
        assert normalized == 'jat1'
    
    def test_handle_empty_transcriptions(self):
        """Test handling of empty transcriptions."""
        builder = SimilarityMatrixBuilder()
        
        transcriptions = [
            {'transcribed_jyutping': '', 'whisper_confidence': 0.5},
            {'transcribed_jyutping': 'jat1', 'whisper_confidence': 0.9}
        ]
        
        vocab_entries = [
            VocabularyEntry(english='one', cantonese='jat1', row_index=0),
            VocabularyEntry(english='two', cantonese='ji6', row_index=1)
        ]
        
        matrix = builder.build_similarity_matrix(transcriptions, vocab_entries)
        
        # Empty transcription should have low similarity
        assert matrix[0, 0] < 0.5
        assert matrix[0, 1] < 0.5


class TestHungarianAssigner:
    """Test the Hungarian algorithm integration."""
    
    def test_find_optimal_assignment_perfect_match(self):
        """Test optimal assignment with perfect diagonal match."""
        assigner = HungarianAssigner()
        
        # Perfect diagonal matrix
        similarity_matrix = np.array([
            [1.0, 0.1, 0.1],
            [0.1, 1.0, 0.1],
            [0.1, 0.1, 1.0]
        ])
        
        row_indices, col_indices = assigner.find_optimal_assignment(similarity_matrix)
        
        # Should assign each row to its diagonal
        assert len(row_indices) == 3
        assert len(col_indices) == 3
        assert list(row_indices) == [0, 1, 2]
        assert list(col_indices) == [0, 1, 2]
    
    def test_find_optimal_assignment_swap_needed(self):
        """Test optimal assignment when swap is needed."""
        assigner = HungarianAssigner()
        
        # Matrix where swapping 0 and 1 is optimal
        similarity_matrix = np.array([
            [0.3, 0.9],
            [0.9, 0.3]
        ])
        
        row_indices, col_indices = assigner.find_optimal_assignment(similarity_matrix)
        
        # Should swap: row 0 -> col 1, row 1 -> col 0
        assert len(row_indices) == 2
        assert len(col_indices) == 2
        
        # Verify the assignment maximizes similarity
        total_similarity = similarity_matrix[row_indices, col_indices].sum()
        assert total_similarity == 1.8  # 0.9 + 0.9
    
    def test_extract_assignment_mapping(self):
        """Test extraction of assignment mappings."""
        assigner = HungarianAssigner()
        
        row_indices = np.array([0, 1, 2])
        col_indices = np.array([1, 2, 0])
        similarity_matrix = np.array([
            [0.5, 0.9, 0.3],
            [0.4, 0.6, 0.8],
            [0.7, 0.5, 0.4]
        ])
        
        assignments = assigner.extract_assignment_mapping(
            row_indices, col_indices, similarity_matrix
        )
        
        assert len(assignments) == 3
        assert assignments[0]['segment_index'] == 0
        assert assignments[0]['term_index'] == 1
        assert assignments[0]['similarity'] == 0.9
    
    def test_calculate_assignment_quality(self):
        """Test assignment quality calculation."""
        assigner = HungarianAssigner()
        
        assignments = [
            {'segment_index': 0, 'term_index': 0, 'similarity': 0.9},
            {'segment_index': 1, 'term_index': 1, 'similarity': 0.7},
            {'segment_index': 2, 'term_index': 2, 'similarity': 0.4}
        ]
        
        similarity_matrix = np.array([[0.9], [0.7], [0.4]])
        
        quality = assigner.calculate_assignment_quality(assignments, similarity_matrix)
        
        assert quality['total_similarity'] == 2.0
        assert quality['average_similarity'] == pytest.approx(0.667, rel=0.01)
        assert quality['high_quality_count'] == 1  # >= 0.8
        assert quality['medium_quality_count'] == 1  # 0.5-0.8
        assert quality['low_quality_count'] == 1  # < 0.5


class TestSegmentReassigner:
    """Test the segment reassignment logic."""
    
    def test_reassign_segments_basic(self):
        """Test basic segment reassignment."""
        reassigner = SegmentReassigner()
        
        # Create test data
        audio_segments = [
            AudioSegment(start_time=0.0, end_time=1.0, audio_data=np.array([0.1]),
                        confidence=0.8, segment_id='seg_0', audio_file_path='seg_0.wav'),
            AudioSegment(start_time=1.0, end_time=2.0, audio_data=np.array([0.2]),
                        confidence=0.7, segment_id='seg_1', audio_file_path='seg_1.wav')
        ]
        
        vocab_entries = [
            VocabularyEntry(english='one', cantonese='jat1', row_index=0),
            VocabularyEntry(english='two', cantonese='ji6', row_index=1)
        ]
        
        aligned_pairs = [
            AlignedPair(vocab_entries[0], audio_segments[0], 0.8, 'seg_0.wav'),
            AlignedPair(vocab_entries[1], audio_segments[1], 0.7, 'seg_1.wav')
        ]
        
        # Swap assignment
        assignments = [
            {'segment_index': 0, 'term_index': 1, 'similarity': 0.9},
            {'segment_index': 1, 'term_index': 0, 'similarity': 0.85}
        ]
        
        similarity_matrix = np.array([[0.5, 0.9], [0.85, 0.6]])
        
        transcriptions = [
            {'whisper_confidence': 0.8},
            {'whisper_confidence': 0.7}
        ]
        
        new_pairs = reassigner.reassign_segments(
            aligned_pairs, assignments, similarity_matrix, transcriptions
        )
        
        # Verify reassignment
        assert len(new_pairs) == 2
        # Pairs should be sorted by start time
        assert new_pairs[0].audio_segment.start_time <= new_pairs[1].audio_segment.start_time
    
    def test_sort_by_temporal_order(self):
        """Test sorting by temporal order."""
        reassigner = SegmentReassigner()
        
        # Create pairs out of temporal order
        audio_seg_1 = AudioSegment(start_time=2.0, end_time=3.0, audio_data=np.array([0.1]),
                                   confidence=0.8, segment_id='seg_1')
        audio_seg_0 = AudioSegment(start_time=0.0, end_time=1.0, audio_data=np.array([0.2]),
                                   confidence=0.7, segment_id='seg_0')
        
        vocab_entry = VocabularyEntry(english='test', cantonese='test', row_index=0)
        
        pairs = [
            AlignedPair(vocab_entry, audio_seg_1, 0.8, 'seg_1.wav'),
            AlignedPair(vocab_entry, audio_seg_0, 0.7, 'seg_0.wav')
        ]
        
        sorted_pairs = reassigner._sort_by_temporal_order(pairs)
        
        assert sorted_pairs[0].audio_segment.start_time == 0.0
        assert sorted_pairs[1].audio_segment.start_time == 2.0
    
    def test_identify_reassignments(self):
        """Test identification of reassignments."""
        reassigner = SegmentReassigner()
        
        audio_segments = [
            AudioSegment(start_time=0.0, end_time=1.0, audio_data=np.array([0.1]),
                        confidence=0.8, segment_id='seg_0'),
            AudioSegment(start_time=1.0, end_time=2.0, audio_data=np.array([0.2]),
                        confidence=0.7, segment_id='seg_1')
        ]
        
        vocab_entries = [
            VocabularyEntry(english='one', cantonese='jat1', row_index=0),
            VocabularyEntry(english='two', cantonese='ji6', row_index=1)
        ]
        
        original_pairs = [
            AlignedPair(vocab_entries[0], audio_segments[0], 0.8, 'seg_0.wav'),
            AlignedPair(vocab_entries[1], audio_segments[1], 0.7, 'seg_1.wav')
        ]
        
        new_pairs = [
            AlignedPair(vocab_entries[1], audio_segments[0], 0.9, 'seg_0.wav'),
            AlignedPair(vocab_entries[0], audio_segments[1], 0.85, 'seg_1.wav')
        ]
        
        assignments = [
            {'segment_index': 0, 'term_index': 1, 'similarity': 0.9},
            {'segment_index': 1, 'term_index': 0, 'similarity': 0.85}
        ]
        
        reassignments = reassigner.identify_reassignments(
            original_pairs, new_pairs, assignments
        )
        
        # Both should be reassignments
        assert len(reassignments) == 2
        assert reassignments[0]['segment_index'] == 0
        assert reassignments[0]['new_term_index'] == 1


class TestGlobalReassignmentCoordinator:
    """Test the global reassignment coordinator."""
    
    def test_perform_global_reassignment_basic(self):
        """Test basic global reassignment workflow."""
        coordinator = GlobalReassignmentCoordinator()
        
        # Create test data
        audio_segments = [
            AudioSegment(start_time=0.0, end_time=1.0, audio_data=np.array([0.1]),
                        confidence=0.8, segment_id='seg_0', audio_file_path='seg_0.wav'),
            AudioSegment(start_time=1.0, end_time=2.0, audio_data=np.array([0.2]),
                        confidence=0.7, segment_id='seg_1', audio_file_path='seg_1.wav')
        ]
        
        vocab_entries = [
            VocabularyEntry(english='one', cantonese='jat1', row_index=0),
            VocabularyEntry(english='two', cantonese='ji6', row_index=1)
        ]
        
        aligned_pairs = [
            AlignedPair(vocab_entries[0], audio_segments[0], 0.8, 'seg_0.wav'),
            AlignedPair(vocab_entries[1], audio_segments[1], 0.7, 'seg_1.wav')
        ]
        
        verification_results = {
            'verified_pairs': [
                {
                    'transcribed_jyutping': 'jat1',
                    'whisper_confidence': 0.9,
                    'transcribed_cantonese': 'jat1'
                },
                {
                    'transcribed_jyutping': 'ji6',
                    'whisper_confidence': 0.8,
                    'transcribed_cantonese': 'ji6'
                }
            ]
        }
        
        # Perform reassignment
        new_pairs, report = coordinator.perform_global_reassignment(
            aligned_pairs, verification_results, enable_logging=False
        )
        
        # Verify results
        assert report['status'] == 'completed'
        assert len(new_pairs) == 2
        assert 'quality_metrics' in report
        assert 'reassignment_details' in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
