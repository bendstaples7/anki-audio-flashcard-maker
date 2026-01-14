#!/usr/bin/env python3
"""
Test audio processing with real vocabulary from Google Sheets.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.audio.processor import AudioProcessor
from cantonese_anki_generator.alignment import AudioVocabularyAligner
from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser


def test_with_google_sheets_vocab(audio_path, sheets_url, output_folder="real_vocab_clips"):
    """Test audio processing with vocabulary from Google Sheets."""
    
    print("🎵 Real Vocabulary Audio Test")
    print("=" * 40)
    
    # Clean up the audio path
    audio_path = audio_path.strip().strip('"').strip("'")
    
    # Check if audio file exists
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    print(f"📁 Audio file: {audio_path}")
    print(f"📊 Google Sheet: {sheets_url}")
    
    try:
        # Step 1: Extract vocabulary from Google Sheets
        print(f"\n📋 Extracting vocabulary from Google Sheets...")
        sheets_parser = GoogleSheetsParser()
        vocab_entries = sheets_parser.extract_vocabulary_from_sheet(sheets_url)
        
        print(f"✅ Extracted {len(vocab_entries)} vocabulary terms:")
        for i, entry in enumerate(vocab_entries[:10], 1):  # Show first 10
            print(f"   {i:2d}. {entry.english:15s} → {entry.cantonese}")
        if len(vocab_entries) > 10:
            print(f"   ... and {len(vocab_entries) - 10} more terms")
        
        # Step 2: Create output directory
        output_dir = Path(output_folder)
        output_dir.mkdir(exist_ok=True)
        print(f"📂 Output folder: {output_dir.absolute()}")
        
        # Step 3: Process audio
        print(f"\n🔄 Processing audio with {len(vocab_entries)} expected terms...")
        processor = AudioProcessor()
        
        audio_segments, stats = processor.process_audio_file(
            audio_file_path=audio_path,
            expected_word_count=len(vocab_entries),
            output_dir=str(output_dir)
        )
        
        print(f"✅ Audio processing completed!")
        print(f"   📊 Duration: {stats['audio_duration']:.2f}s")
        print(f"   📊 Expected terms: {len(vocab_entries)}")
        print(f"   📊 Generated clips: {len(audio_segments)}")
        print(f"   📊 Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        # Step 4: Align with real vocabulary
        print(f"\n🎯 Aligning audio clips with vocabulary...")
        aligner = AudioVocabularyAligner()
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        
        print(f"✅ Alignment completed: {len(aligned_pairs)} pairs")
        
        # Step 5: Create detailed summary
        summary_file = output_dir / "vocabulary_alignment.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Real Vocabulary Audio Alignment\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Google Sheet: {sheets_url}\n")
            f.write(f"Audio file: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n")
            f.write(f"Generated clips: {len(audio_segments)}\n\n")
            
            f.write("Alignment Results:\n")
            f.write("-" * 30 + "\n")
            
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                clip_filename = Path(pair.audio_file_path).name
                
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    File: {clip_filename}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s ({duration:.2f}s)\n")
                f.write(f"    Confidence: {pair.alignment_confidence:.3f}\n")
                
                # Check for overlaps
                if i < len(aligned_pairs):
                    next_pair = aligned_pairs[i]
                    if pair.audio_segment.end_time > next_pair.audio_segment.start_time:
                        overlap = pair.audio_segment.end_time - next_pair.audio_segment.start_time
                        f.write(f"    ⚠️  OVERLAP with next segment: {overlap:.2f}s\n")
                
                f.write("\n")
        
        # Step 6: Show results and identify issues
        print(f"\n📋 Alignment Results:")
        print(f"   📄 Detailed report: {summary_file.name}")
        print()
        
        overlap_count = 0
        for i, pair in enumerate(aligned_pairs):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            # Check for overlap with next segment
            overlap_indicator = ""
            if i < len(aligned_pairs) - 1:
                next_pair = aligned_pairs[i + 1]
                if pair.audio_segment.end_time > next_pair.audio_segment.start_time:
                    overlap = pair.audio_segment.end_time - next_pair.audio_segment.start_time
                    overlap_indicator = f" ⚠️ +{overlap:.2f}s"
                    overlap_count += 1
            
            print(f"   {i+1:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:8s} | {duration:.2f}s{overlap_indicator}")
        
        # Step 7: Analysis and recommendations
        print(f"\n📊 Quality Analysis:")
        if overlap_count > 0:
            print(f"   ⚠️  Found {overlap_count} overlapping segments")
            print(f"   💡 This means some clips include parts of the next word")
            print(f"   🔧 Segmentation parameters may need adjustment")
        else:
            print(f"   ✅ No overlapping segments detected")
        
        avg_duration = sum(pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs) / len(aligned_pairs)
        print(f"   📏 Average clip duration: {avg_duration:.2f}s")
        
        if len(aligned_pairs) != len(vocab_entries):
            print(f"   ⚠️  Clip count mismatch: {len(aligned_pairs)} clips vs {len(vocab_entries)} vocabulary terms")
        
        print(f"\n🎧 How to test the clips:")
        print(f"   1. Open folder: {output_dir.absolute()}")
        print(f"   2. Play each .wav file and check if it matches the expected word")
        print(f"   3. Look for overlaps (clips that include multiple words)")
        print(f"   4. Check {summary_file.name} for detailed timing info")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("🎵 Real Vocabulary Audio Test")
    print("This will use your actual Google Sheets vocabulary!")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_with_google_sheets_vocab(audio_file, sheets_url)
    
    if success:
        print("\n🎉 Test completed!")
        print("Check the 'real_vocab_clips' folder and listen to the clips.")
        print("Pay attention to any overlap warnings in the output.")
    else:
        print("\n❌ Test failed. Check the error messages above.")