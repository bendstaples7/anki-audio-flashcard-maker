#!/usr/bin/env python3
"""
Test improved audio segmentation with adjusted parameters.
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


def test_improved_segmentation(audio_path, sheets_url, output_folder="improved_clips"):
    """Test audio processing with improved segmentation parameters."""
    
    print("🔧 Improved Segmentation Test")
    print("=" * 40)
    
    # Clean up the audio path
    audio_path = audio_path.strip().strip('"').strip("'")
    
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    print(f"📁 Audio file: {audio_path}")
    
    try:
        # Extract vocabulary from Google Sheets
        print(f"\n📋 Extracting vocabulary...")
        sheets_parser = GoogleSheetsParser()
        vocab_entries = sheets_parser.extract_vocabulary_from_sheet(sheets_url)
        
        print(f"✅ Found {len(vocab_entries)} vocabulary terms")
        for i, entry in enumerate(vocab_entries, 1):
            print(f"   {i:2d}. {entry.english:15s} → {entry.cantonese}")
        
        # Create output directory
        output_dir = Path(output_folder)
        output_dir.mkdir(exist_ok=True)
        print(f"📂 Output folder: {output_dir.absolute()}")
        
        # Create processor with improved settings
        print(f"\n🔧 Configuring improved segmentation...")
        processor = AudioProcessor()
        
        # Adjust segmentation parameters for better boundary detection
        processor.set_processing_parameters(
            vad_aggressiveness=2,        # More aggressive voice detection
            min_word_duration=0.3,       # Shorter minimum word duration
            fade_duration=0.02,          # Shorter fade to reduce overlap
            normalize_clips=True         # Normalize volume
        )
        
        # Also adjust the segmenter directly for more precise boundaries
        segmenter = processor.segmenter
        segmenter.min_word_duration = 0.3      # Allow shorter words
        segmenter.max_word_duration = 2.5      # Limit maximum word length
        segmenter.boundary_smoothing = 0.02    # Less smoothing for sharper boundaries
        
        # Adjust feature weights to emphasize energy changes
        segmenter.energy_weight = 0.5          # Increase energy importance
        segmenter.spectral_weight = 0.3        # Reduce spectral weight
        segmenter.temporal_weight = 0.2        # Reduce temporal weight
        
        print(f"   ✓ Min word duration: {segmenter.min_word_duration}s")
        print(f"   ✓ Max word duration: {segmenter.max_word_duration}s")
        print(f"   ✓ Boundary smoothing: {segmenter.boundary_smoothing}s")
        print(f"   ✓ Energy weight: {segmenter.energy_weight}")
        
        # Process audio with improved settings
        print(f"\n🔄 Processing audio with improved segmentation...")
        audio_segments, stats = processor.process_audio_file(
            audio_file_path=audio_path,
            expected_word_count=len(vocab_entries),
            output_dir=str(output_dir)
        )
        
        print(f"✅ Processing completed!")
        print(f"   📊 Duration: {stats['audio_duration']:.2f}s")
        print(f"   📊 Expected: {len(vocab_entries)} terms")
        print(f"   📊 Generated: {len(audio_segments)} clips")
        print(f"   📊 Average confidence: {stats.get('average_confidence', 0):.3f}")
        
        # Align with vocabulary
        print(f"\n🎯 Aligning clips with vocabulary...")
        aligner = AudioVocabularyAligner()
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        
        # Analyze results
        print(f"\n📊 Segmentation Analysis:")
        
        # Check for overlaps
        overlap_count = 0
        gap_count = 0
        
        for i in range(len(aligned_pairs) - 1):
            current_end = aligned_pairs[i].audio_segment.end_time
            next_start = aligned_pairs[i + 1].audio_segment.start_time
            
            if current_end > next_start:
                overlap = current_end - next_start
                overlap_count += 1
                print(f"   ⚠️  Overlap {i+1}→{i+2}: {overlap:.3f}s")
            elif next_start > current_end:
                gap = next_start - current_end
                gap_count += 1
                print(f"   ✓ Gap {i+1}→{i+2}: {gap:.3f}s")
        
        print(f"\n📋 Clip Details:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s} | {duration:.2f}s")
        
        # Summary
        print(f"\n📊 Improvement Summary:")
        print(f"   🎯 Target clips: {len(vocab_entries)}")
        print(f"   📁 Generated clips: {len(aligned_pairs)}")
        print(f"   ⚠️  Overlaps: {overlap_count}")
        print(f"   ✅ Clean gaps: {gap_count}")
        
        if len(aligned_pairs) == len(vocab_entries) and overlap_count == 0:
            print(f"   🎉 Perfect segmentation achieved!")
        elif len(aligned_pairs) == len(vocab_entries):
            print(f"   👍 Correct clip count, but {overlap_count} overlaps remain")
        else:
            print(f"   🔧 Still need adjustment: {abs(len(aligned_pairs) - len(vocab_entries))} clip count difference")
        
        # Create summary file
        summary_file = output_dir / "improved_segmentation.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Improved Segmentation Results\n")
            f.write("=" * 35 + "\n\n")
            f.write(f"Audio: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n")
            f.write(f"Overlaps: {overlap_count}\n")
            f.write(f"Clean gaps: {gap_count}\n\n")
            
            f.write("Segmentation Parameters:\n")
            f.write(f"- Min word duration: {segmenter.min_word_duration}s\n")
            f.write(f"- Max word duration: {segmenter.max_word_duration}s\n")
            f.write(f"- Boundary smoothing: {segmenter.boundary_smoothing}s\n")
            f.write(f"- Energy weight: {segmenter.energy_weight}\n\n")
            
            f.write("Clip Details:\n")
            f.write("-" * 20 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)\n")
                f.write(f"    File: {Path(pair.audio_file_path).name}\n\n")
        
        print(f"\n🎧 Test the improved clips:")
        print(f"   📁 Folder: {output_dir.absolute()}")
        print(f"   📄 Report: {summary_file.name}")
        print(f"   🎵 Listen to clip 1 - should now contain ONLY 'Sin1 saang1' (Mr.)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("🔧 Improved Audio Segmentation Test")
    print("This will try to fix the overlapping segments issue.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_improved_segmentation(audio_file, sheets_url)
    
    if success:
        print("\n🎉 Improved segmentation test completed!")
        print("Check the 'improved_clips' folder to see if segmentation is better.")
        print("Listen to the first clip - it should now contain only 'Mr.' (Sin1 saang1)")
    else:
        print("\n❌ Test failed. Check the error messages above.")