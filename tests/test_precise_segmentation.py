#!/usr/bin/env python3
"""
Test precise audio segmentation with no padding and aggressive boundary detection.
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


def test_precise_segmentation(audio_path, sheets_url, output_folder="precise_clips"):
    """Test audio processing with precise segmentation - no overlaps."""
    
    print("🎯 Precise Segmentation Test")
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
        
        # Create output directory
        output_dir = Path(output_folder)
        output_dir.mkdir(exist_ok=True)
        print(f"📂 Output folder: {output_dir.absolute()}")
        
        # Create processor with precise settings
        print(f"\n🎯 Configuring precise segmentation...")
        processor = AudioProcessor()
        
        # Configure for precise, non-overlapping segments
        processor.set_processing_parameters(
            vad_aggressiveness=3,        # Maximum voice detection sensitivity
            min_word_duration=0.2,       # Allow very short words
            fade_duration=0.005,         # Minimal fade to reduce overlap
            normalize_clips=True
        )
        
        # Adjust segmenter for more aggressive boundary detection
        segmenter = processor.segmenter
        segmenter.min_word_duration = 0.2      # Shorter minimum
        segmenter.max_word_duration = 2.0      # Shorter maximum
        segmenter.boundary_smoothing = 0.01    # Minimal smoothing for sharp boundaries
        
        # Emphasize energy changes for better word separation
        segmenter.energy_weight = 0.6          # High energy importance
        segmenter.spectral_weight = 0.25       # Medium spectral importance
        segmenter.temporal_weight = 0.15       # Low temporal importance
        
        # Configure clip generator for no padding/overlap
        clip_generator = processor.clip_generator
        clip_generator.set_quality_parameters(
            fade_duration=0.005,         # Minimal fade
            padding_duration=0.0,        # NO PADDING - this was causing overlaps!
            normalize_clips=True,
            target_peak_level=0.8
        )
        
        print(f"   ✓ Padding duration: {clip_generator.padding_duration}s (NO OVERLAP)")
        print(f"   ✓ Fade duration: {clip_generator.fade_duration}s")
        print(f"   ✓ Min word duration: {segmenter.min_word_duration}s")
        print(f"   ✓ Energy weight: {segmenter.energy_weight}")
        
        # Process audio with precise settings
        print(f"\n🔄 Processing audio with precise segmentation...")
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
        
        # Detailed overlap analysis
        print(f"\n📊 Precise Segmentation Analysis:")
        
        overlap_count = 0
        gap_count = 0
        total_overlap = 0.0
        total_gap = 0.0
        
        for i in range(len(aligned_pairs) - 1):
            current_end = aligned_pairs[i].audio_segment.end_time
            next_start = aligned_pairs[i + 1].audio_segment.start_time
            
            if current_end > next_start:
                overlap = current_end - next_start
                overlap_count += 1
                total_overlap += overlap
                print(f"   ⚠️  Overlap {i+1}→{i+2}: {overlap:.3f}s")
            elif next_start > current_end:
                gap = next_start - current_end
                gap_count += 1
                total_gap += gap
                print(f"   ✅ Gap {i+1}→{i+2}: {gap:.3f}s")
            else:
                print(f"   🎯 Perfect boundary {i+1}→{i+2}: 0.000s")
        
        # Show all clips with precise timing
        print(f"\n📋 Precise Clip Details:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s}")
            print(f"       Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)")
        
        # Calculate average durations
        durations = [pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        # Final assessment
        print(f"\n📊 Precision Summary:")
        print(f"   🎯 Target clips: {len(vocab_entries)}")
        print(f"   📁 Generated clips: {len(aligned_pairs)}")
        print(f"   ⚠️  Total overlaps: {overlap_count} ({total_overlap:.3f}s total)")
        print(f"   ✅ Clean gaps: {gap_count} ({total_gap:.3f}s total)")
        print(f"   📏 Duration range: {min_duration:.3f}s - {max_duration:.3f}s (avg: {avg_duration:.3f}s)")
        
        # Success criteria
        success_score = 0
        if len(aligned_pairs) == len(vocab_entries):
            success_score += 40  # Correct count
            print(f"   ✅ Correct clip count achieved!")
        else:
            print(f"   ⚠️  Clip count mismatch: {abs(len(aligned_pairs) - len(vocab_entries))} difference")
        
        if overlap_count == 0:
            success_score += 40  # No overlaps
            print(f"   ✅ Zero overlaps achieved!")
        elif overlap_count <= 2:
            success_score += 20  # Minimal overlaps
            print(f"   👍 Minimal overlaps: {overlap_count}")
        else:
            print(f"   ⚠️  Still has overlaps: {overlap_count}")
        
        if 0.5 <= avg_duration <= 2.5:
            success_score += 20  # Reasonable durations
            print(f"   ✅ Reasonable clip durations!")
        else:
            print(f"   ⚠️  Unusual clip durations (avg: {avg_duration:.2f}s)")
        
        print(f"\n🏆 Success Score: {success_score}/100")
        
        if success_score >= 80:
            print(f"   🎉 Excellent segmentation!")
        elif success_score >= 60:
            print(f"   👍 Good segmentation with minor issues")
        else:
            print(f"   🔧 Needs more adjustment")
        
        # Create detailed report
        summary_file = output_dir / "precise_segmentation_report.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Precise Segmentation Report\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Audio: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n")
            f.write(f"Success score: {success_score}/100\n\n")
            
            f.write("Configuration:\n")
            f.write(f"- Padding duration: {clip_generator.padding_duration}s\n")
            f.write(f"- Fade duration: {clip_generator.fade_duration}s\n")
            f.write(f"- Min word duration: {segmenter.min_word_duration}s\n")
            f.write(f"- Energy weight: {segmenter.energy_weight}\n\n")
            
            f.write("Results:\n")
            f.write(f"- Overlaps: {overlap_count} ({total_overlap:.3f}s total)\n")
            f.write(f"- Clean gaps: {gap_count} ({total_gap:.3f}s total)\n")
            f.write(f"- Average duration: {avg_duration:.3f}s\n\n")
            
            f.write("Detailed Clips:\n")
            f.write("-" * 20 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)\n")
                f.write(f"    File: {Path(pair.audio_file_path).name}\n\n")
        
        print(f"\n🎧 Test the precise clips:")
        print(f"   📁 Folder: {output_dir.absolute()}")
        print(f"   📄 Report: {summary_file.name}")
        print(f"   🎵 Listen to clip 1 - should contain ONLY 'Sin1 saang1' (Mr.)")
        print(f"   🎵 Listen to clip 2 - should contain ONLY 'Taai3 taai2' (Mrs.)")
        
        return success_score >= 60
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("🎯 Precise Audio Segmentation Test")
    print("This will eliminate padding to prevent overlaps.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_precise_segmentation(audio_file, sheets_url)
    
    if success:
        print("\n🎉 Precise segmentation achieved!")
        print("The clips should now be properly separated without overlaps.")
    else:
        print("\n🔧 Segmentation still needs work, but should be improved.")
        print("Check the clips to see if they're better separated.")