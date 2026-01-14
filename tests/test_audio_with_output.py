#!/usr/bin/env python3
"""
Test audio processing and save clips to a specific folder for listening.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.audio.processor import AudioProcessor
from cantonese_anki_generator.alignment import AudioVocabularyAligner


def test_and_save_clips(audio_path, vocab_terms, output_folder="audio_clips_output"):
    """Test audio processing and save clips to a specific folder."""
    
    print("🎵 Audio Processing & Clip Generation Test")
    print("=" * 50)
    
    # Clean up the path
    audio_path = audio_path.strip().strip('"').strip("'")
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"❌ File not found: {audio_path}")
        return False
    
    print(f"📁 Input audio: {audio_path}")
    
    # Create output directory in current folder
    output_dir = Path(output_folder)
    output_dir.mkdir(exist_ok=True)
    
    print(f"📂 Output folder: {output_dir.absolute()}")
    
    # Create vocabulary entries
    vocab_entries = [
        VocabularyEntry(english=eng, cantonese=cant, row_index=i)
        for i, (eng, cant) in enumerate(vocab_terms)
    ]
    
    print(f"📝 Processing {len(vocab_entries)} vocabulary terms:")
    for i, entry in enumerate(vocab_entries, 1):
        print(f"   {i:2d}. {entry.english:10s} → {entry.cantonese}")
    
    try:
        # Process audio
        print(f"\n🔄 Processing audio...")
        processor = AudioProcessor()
        
        audio_segments, stats = processor.process_audio_file(
            audio_file_path=audio_path,
            expected_word_count=len(vocab_entries),
            output_dir=str(output_dir)
        )
        
        print(f"✅ Audio processing completed!")
        print(f"   📊 Duration: {stats['audio_duration']:.2f}s")
        print(f"   📊 Generated clips: {len(audio_segments)}")
        print(f"   📊 Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        # Test alignment
        print(f"\n🎯 Creating vocabulary alignment...")
        aligner = AudioVocabularyAligner()
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        
        # Create a summary file
        summary_file = output_dir / "alignment_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Audio Alignment Summary\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Original audio: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Generated clips: {len(audio_segments)}\n\n")
            
            f.write("Clip Details:\n")
            f.write("-" * 20 + "\n")
            
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                clip_filename = Path(pair.audio_file_path).name
                
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:8s}\n")
                f.write(f"    File: {clip_filename}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s ({duration:.2f}s)\n")
                f.write(f"    Confidence: {pair.alignment_confidence:.3f}\n\n")
        
        # Show results
        print(f"\n📋 Generated Audio Clips:")
        print(f"   📁 Location: {output_dir.absolute()}")
        print(f"   📄 Summary: {summary_file.name}")
        print()
        
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            print(f"   {i:2d}. {clip_filename:20s} | {pair.vocabulary_entry.english:10s} → {pair.vocabulary_entry.cantonese:8s} | {duration:.2f}s")
        
        print(f"\n🎧 How to listen:")
        print(f"   1. Open folder: {output_dir.absolute()}")
        print(f"   2. Double-click any .wav file to play it")
        print(f"   3. Check if the audio matches the expected word")
        print(f"   4. Read {summary_file.name} for detailed timing info")
        
        print(f"\n✅ Test completed successfully!")
        print(f"   Generated {len(aligned_pairs)} audio clips ready for listening!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🎵 Audio Clip Generation Test")
    print("This will create individual audio files you can listen to.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Ask for vocabulary or use defaults
    use_custom = input("Enter custom vocabulary? (y/n, default=n): ").strip().lower()
    
    if use_custom == 'y':
        print("Enter vocabulary pairs (English,Cantonese). Type 'done' when finished:")
        vocabulary = []
        while True:
            term = input("Enter 'English,Cantonese' or 'done': ").strip()
            if term.lower() == 'done':
                break
            try:
                eng, cant = term.split(',', 1)
                vocabulary.append((eng.strip(), cant.strip()))
                print(f"  Added: {eng.strip()} → {cant.strip()}")
            except ValueError:
                print("  Please use format: English,Cantonese")
    else:
        # Use example vocabulary
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
        print(f"Using example vocabulary with {len(vocabulary)} terms.")
    
    if not vocabulary:
        print("❌ No vocabulary provided.")
        exit(1)
    
    # Run the test
    success = test_and_save_clips(audio_file, vocabulary)
    
    if success:
        print("\n🎉 Success! Check the 'audio_clips_output' folder to listen to your clips.")
    else:
        print("\n❌ Test failed. Check the error messages above.")