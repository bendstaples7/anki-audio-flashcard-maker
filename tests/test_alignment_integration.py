#!/usr/bin/env python3
"""
Simple integration test for the alignment module.
"""

import numpy as np
from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.alignment import AudioVocabularyAligner, AlignmentRefinement


def test_alignment_integration():
    """Test basic alignment functionality."""
    
    # Create test vocabulary entries
    vocab_entries = [
        VocabularyEntry(english="hello", cantonese="你好", row_index=0),
        VocabularyEntry(english="good", cantonese="好", row_index=1),
        VocabularyEntry(english="yes", cantonese="係", row_index=2),
    ]
    
    # Create test audio segments
    audio_segments = [
        AudioSegment(
            start_time=0.0,
            end_time=1.0,
            audio_data=np.random.random(16000),  # 1 second at 16kHz
            confidence=0.8,
            segment_id="seg_0",
            audio_file_path="test_0.wav"
        ),
        AudioSegment(
            start_time=1.0,
            end_time=2.0,
            audio_data=np.random.random(16000),
            confidence=0.9,
            segment_id="seg_1",
            audio_file_path="test_1.wav"
        ),
        AudioSegment(
            start_time=2.0,
            end_time=3.0,
            audio_data=np.random.random(16000),
            confidence=0.7,
            segment_id="seg_2",
            audio_file_path="test_2.wav"
        ),
    ]
    
    # Test aligner initialization
    aligner = AudioVocabularyAligner()
    print("✓ AudioVocabularyAligner initialized successfully")
    
    # Test refinement initialization
    refinement = AlignmentRefinement()
    print("✓ AlignmentRefinement initialized successfully")
    
    # Test fallback alignment (since we don't have real MFA setup)
    aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
    print(f"✓ Fallback alignment created {len(aligned_pairs)} pairs")
    
    # Test alignment validation
    good_alignments, poor_alignments = aligner.validate_alignment_quality(aligned_pairs)
    print(f"✓ Alignment validation: {len(good_alignments)} good, {len(poor_alignments)} poor")
    
    # Test alignment statistics
    stats = aligner.get_alignment_statistics(aligned_pairs)
    print(f"✓ Alignment statistics: {stats['success_rate']:.2f} success rate")
    
    # Test refinement
    refined_pairs = refinement.refine_alignments(aligned_pairs)
    print(f"✓ Alignment refinement completed: {len(refined_pairs)} refined pairs")
    
    # Test refinement report
    report = refinement.get_refinement_report(aligned_pairs, refined_pairs)
    print(f"✓ Refinement report: {report['confidence_improvement']:.3f} confidence improvement")
    
    print("\n🎉 All alignment integration tests passed!")


if __name__ == "__main__":
    test_alignment_integration()