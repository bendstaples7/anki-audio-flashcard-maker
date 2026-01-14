#!/usr/bin/env python3
"""
Test script for processing real audio file with vocabulary terms.
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.audio.processor import AudioProcessor
from cantonese_anki_generator.alignment import AudioVocabularyAligner, AlignmentRefinement


def setup_logging():
    """Set up logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_real_audio_processing(audio_file_path: str, vocabulary_terms: list):
    """
    Test the complete audio processing pipeline with real data.
    
    Args:
        audio_file_path: Path to the audio file
        vocabulary_terms: List of (english, cantonese) tuples
    """
    print("🎵 Testing Real Audio Processing Pipeline")
    print("=" * 50)
    
    # Convert vocabulary terms to VocabularyEntry objects
    vocab_entries = [
        VocabularyEntry(
            english=english.strip(),
            cantonese=cantonese.strip(),
            row_index=i,
            confidence=1.0
        )
        for i, (english, cantonese) in enumerate(vocabulary_terms)
    ]
    
    print(f"📝 Loaded {len(vocab_entries)} vocabulary terms:")
    for entry in vocab_entries[:5]:  # Show first 5
        print(f"   {entry.english} → {entry.cantonese}")
    if len(vocab_entries) > 5:
        print(f"   ... and {len(vocab_entries) - 5} more")
    
    # Step 1 & 2: Process audio file (load, validate, segment)
    print(f"\n🔊 Processing audio file: {audio_file_path}")
    try:
        # Create temporary output directory for clips
        import tempfile
        output_dir = tempfile.mkdtemp(prefix='audio_clips_')
        
        processor = AudioProcessor()
        audio_segments, stats = processor.process_audio_file(
            audio_file_path=audio_file_path,
            expected_word_count=len(vocab_entries),
            output_dir=output_dir
        )
        
        print(f"   ✓ Audio processed: {stats['audio_duration']:.2f} seconds, {stats['actual_sample_rate']} Hz")
        print(f"   ✓ Created {len(audio_segments)} audio segments")
        print(f"   ✓ Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        # Show segment details
        for i, segment in enumerate(audio_segments[:3]):  # Show first 3
            duration = segment.end_time - segment.start_time
            print(f"   Segment {i}: {segment.start_time:.2f}s - {segment.end_time:.2f}s ({duration:.2f}s)")
        if len(audio_segments) > 3:
            print(f"   ... and {len(audio_segments) - 3} more segments")
            
    except Exception as e:
        print(f"   ❌ Error processing audio: {e}")
        return False
    
    # Step 3: Align audio to vocabulary
    print(f"\n🎯 Aligning audio segments to vocabulary terms")
    try:
        aligner = AudioVocabularyAligner()
        
        # Use fallback alignment since we may not have MFA set up
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        print(f"   ✓ Created {len(aligned_pairs)} aligned pairs")
        
        # Validate alignment quality
        good_alignments, poor_alignments = aligner.validate_alignment_quality(aligned_pairs)
        print(f"   ✓ Quality check: {len(good_alignments)} good, {len(poor_alignments)} poor alignments")
        
        # Show alignment statistics
        stats = aligner.get_alignment_statistics(aligned_pairs)
        print(f"   ✓ Average confidence: {stats['average_confidence']:.3f}")
        
    except Exception as e:
        print(f"   ❌ Error during alignment: {e}")
        return False
    
    # Step 4: Refine alignments
    print(f"\n🔧 Refining alignments")
    try:
        refinement = AlignmentRefinement()
        refined_pairs = refinement.refine_alignments(aligned_pairs)
        
        # Generate refinement report
        report = refinement.get_refinement_report(aligned_pairs, refined_pairs)
        print(f"   ✓ Refinement completed")
        print(f"   ✓ Confidence improvement: {report['confidence_improvement']:.3f}")
        print(f"   ✓ Good alignments: {report['original_good_alignments']} → {report['refined_good_alignments']}")
        
    except Exception as e:
        print(f"   ❌ Error during refinement: {e}")
        return False
    
    # Step 5: Show results
    print(f"\n📊 Final Results")
    print("=" * 30)
    for i, pair in enumerate(refined_pairs[:5]):  # Show first 5 results
        duration = pair.audio_segment.end_time - pair.audio_segment.start_time
        print(f"   {i+1}. {pair.vocabulary_entry.english} → {pair.vocabulary_entry.cantonese}")
        print(f"      Time: {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s ({duration:.2f}s)")
        print(f"      Confidence: {pair.alignment_confidence:.3f}")
        print()
    
    if len(refined_pairs) > 5:
        print(f"   ... and {len(refined_pairs) - 5} more pairs")
    
    print("🎉 Audio processing pipeline test completed successfully!")
    return True


def main():
    """Main function to run the test."""
    setup_logging()
    
    # You can modify these paths and vocabulary terms
    audio_file_path = input("Enter path to your audio file: ").strip()
    
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return
    
    # Example vocabulary - replace with your actual terms
    print("\nEnter your vocabulary terms (English,Cantonese pairs).")
    print("Type 'done' when finished, or press Enter to use example terms.")
    
    vocabulary_terms = []
    while True:
        term_input = input("Enter 'English,Cantonese' or 'done': ").strip()
        
        if term_input.lower() == 'done':
            break
        elif term_input == '':
            # Use example terms
            vocabulary_terms = [
                ("hello", "你好"),
                ("good", "好"),
                ("yes", "係"),
                ("I", "我"),
                ("you", "你"),
            ]
            print("Using example vocabulary terms.")
            break
        else:
            try:
                english, cantonese = term_input.split(',', 1)
                vocabulary_terms.append((english.strip(), cantonese.strip()))
                print(f"Added: {english.strip()} → {cantonese.strip()}")
            except ValueError:
                print("Please use format: English,Cantonese")
    
    if not vocabulary_terms:
        print("❌ No vocabulary terms provided.")
        return
    
    # Run the test
    success = test_real_audio_processing(audio_file_path, vocabulary_terms)
    
    if success:
        print("\n✅ Test completed successfully!")
        print("You can now proceed with implementing the Anki package generation.")
    else:
        print("\n❌ Test failed. Please check the errors above.")


if __name__ == "__main__":
    main()