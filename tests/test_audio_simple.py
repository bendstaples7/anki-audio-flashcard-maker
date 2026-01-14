#!/usr/bin/env python3
"""
Simple test script for audio processing with real file.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.audio.processor import AudioProcessor
from cantonese_anki_generator.alignment import AudioVocabularyAligner


def test_audio_with_file(audio_path, vocab_terms):
    """Test audio processing with a specific file and vocabulary."""
    
    print("🎵 Testing Audio Processing")
    print("=" * 40)
    
    # Clean up the path (remove quotes if present)
    audio_path = audio_path.strip().strip('"').strip("'")
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"❌ File not found: {audio_path}")
        return False
    
    print(f"📁 Audio file: {audio_path}")
    
    # Create vocabulary entries
    vocab_entries = [
        VocabularyEntry(english=eng, cantonese=cant, row_index=i)
        for i, (eng, cant) in enumerate(vocab_terms)
    ]
    
    print(f"📝 Vocabulary: {len(vocab_entries)} terms")
    for entry in vocab_entries:
        print(f"   {entry.english} → {entry.cantonese}")
    
    try:
        # Create output directory
        output_dir = tempfile.mkdtemp(prefix='test_clips_')
        print(f"📂 Output directory: {output_dir}")
        
        # Process audio
        print("\n🔄 Processing audio...")
        processor = AudioProcessor()
        
        audio_segments, stats = processor.process_audio_file(
            audio_file_path=audio_path,
            expected_word_count=len(vocab_entries),
            output_dir=output_dir
        )
        
        print(f"✅ Processing completed!")
        print(f"   Duration: {stats['audio_duration']:.2f}s")
        print(f"   Sample rate: {stats['actual_sample_rate']}Hz")
        print(f"   Speech regions: {stats['speech_regions_count']}")
        print(f"   Generated clips: {len(audio_segments)}")
        print(f"   Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        # Show segments
        print(f"\n📊 Audio Segments:")
        for i, segment in enumerate(audio_segments):
            duration = segment.end_time - segment.start_time
            print(f"   {i+1}. {segment.start_time:.2f}s - {segment.end_time:.2f}s ({duration:.2f}s) conf:{segment.confidence:.2f}")
        
        # Test alignment
        print(f"\n🎯 Testing alignment...")
        aligner = AudioVocabularyAligner()
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        
        print(f"✅ Alignment completed: {len(aligned_pairs)} pairs")
        
        # Show aligned results
        print(f"\n📋 Aligned Results:")
        for i, pair in enumerate(aligned_pairs):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            print(f"   {i+1}. {pair.vocabulary_entry.english} → {pair.vocabulary_entry.cantonese}")
            print(f"      Time: {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s ({duration:.2f}s)")
            print(f"      Confidence: {pair.alignment_confidence:.3f}")
            print(f"      Audio file: {pair.audio_file_path}")
            print()
        
        print("🎉 Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Example usage - modify these for your actual file and vocabulary
    
    # Your audio file path
    audio_file = input("Enter audio file path: ").strip()
    
    # Your vocabulary terms (modify these to match your actual vocabulary)
    vocabulary = [
        ("hello", "你好"),
        ("good", "好"),
        ("yes", "係"),
        ("I", "我"),
        ("you", "你"),
        ("he/she", "佢"),
        ("this", "呢個"),
        ("that", "嗰個"),
        ("what", "咩"),
        ("where", "邊度"),
    ]
    
    print(f"\nUsing example vocabulary with {len(vocabulary)} terms.")
    print("Modify the 'vocabulary' list in the script to match your actual terms.")
    
    success = test_audio_with_file(audio_file, vocabulary)
    
    if success:
        print("\n✅ Audio processing test passed!")
        print("The audio segmentation and alignment pipeline is working.")
    else:
        print("\n❌ Audio processing test failed.")
        print("Check the error messages above for details.")