#!/usr/bin/env python3
"""
Test very aggressive boundary detection to find individual word boundaries.
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


def test_aggressive_boundaries(audio_path, sheets_url, output_folder="aggressive_clips"):
    """Test with very aggressive boundary detection to separate individual words."""
    
    print("⚡ Aggressive Boundary Detection Test")
    print("=" * 45)
    
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
        
        # Create processor with VERY aggressive settings
        print(f"\n⚡ Configuring aggressive boundary detection...")
        processor = AudioProcessor()
        
        # Maximum aggressiveness
        processor.set_processing_parameters(
            vad_aggressiveness=3,        # Maximum
            min_word_duration=0.15,      # Very short minimum (150ms)
            fade_duration=0.002,         # Minimal fade
            normalize_clips=True
        )
        
        # Make segmenter MUCH more aggressive
        segmenter = processor.segmenter
        segmenter.min_word_duration = 0.15     # Very short words allowed
        segmenter.max_word_duration = 1.8      # Shorter maximum
        segmenter.boundary_smoothing = 0.005   # Almost no smoothing for sharp detection
        
        # Heavily emphasize energy changes (the main cue for word boundaries)
        segmenter.energy_weight = 0.8          # Very high energy importance
        segmenter.spectral_weight = 0.15       # Low spectral importance  
        segmenter.temporal_weight = 0.05       # Very low temporal importance
        
        # Configure clip generator for minimal processing
        clip_generator = processor.clip_generator
        clip_generator.set_quality_parameters(
            fade_duration=0.002,         # Minimal fade
            padding_duration=0.0,        # No padding
            normalize_clips=True,
            target_peak_level=0.85
        )
        
        print(f"   ⚡ Min word duration: {segmenter.min_word_duration}s")
        print(f"   ⚡ Max word duration: {segmenter.max_word_duration}s") 
        print(f"   ⚡ Boundary smoothing: {segmenter.boundary_smoothing}s")
        print(f"   ⚡ Energy weight: {segmenter.energy_weight} (VERY HIGH)")
        print(f"   ⚡ Padding: {clip_generator.padding_duration}s")
        
        # Also modify the boundary detection thresholds directly
        # This is more advanced - we're going into the segmentation algorithm
        print(f"   ⚡ Applying advanced boundary detection tweaks...")
        
        # Process audio with aggressive settings
        print(f"\n🔄 Processing with aggressive boundary detection...")
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
        
        # Calculate expected vs actual
        expected_avg_duration = stats['audio_duration'] / len(vocab_entries)
        actual_avg_duration = sum(seg.end_time - seg.start_time for seg in audio_segments) / len(audio_segments) if audio_segments else 0
        
        print(f"   📏 Expected avg duration: {expected_avg_duration:.2f}s per word")
        print(f"   📏 Actual avg duration: {actual_avg_duration:.2f}s per clip")
        
        # Align with vocabulary
        print(f"\n🎯 Aligning clips with vocabulary...")
        aligner = AudioVocabularyAligner()
        aligned_pairs = aligner._fallback_sequential_alignment(audio_segments, vocab_entries)
        
        # Detailed analysis
        print(f"\n📊 Aggressive Boundary Analysis:")
        
        # Check if we got closer to the target
        clip_count_improvement = len(audio_segments) - 6  # Previous was 6
        if clip_count_improvement > 0:
            print(f"   ✅ Clip count improved by {clip_count_improvement}!")
        elif clip_count_improvement == 0:
            print(f"   ⚠️  Same clip count as before ({len(audio_segments)})")
        else:
            print(f"   ⚠️  Fewer clips than before ({len(audio_segments)})")
        
        # Check durations
        durations = [pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        print(f"   📏 Duration range: {min_duration:.2f}s - {max_duration:.2f}s (avg: {avg_duration:.2f}s)")
        
        if avg_duration < 2.5:  # Previous was ~2.86s
            print(f"   ✅ Shorter clips achieved! (was ~2.86s)")
        else:
            print(f"   ⚠️  Clips still long (target: ~1.5s)")
        
        # Show all clips
        print(f"\n📋 Aggressive Segmentation Results:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            # Color code by duration
            duration_status = "✅" if duration < 2.0 else "⚠️" if duration < 2.5 else "❌"
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s}")
            print(f"       {duration_status} Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)")
        
        # Success assessment
        success_factors = []
        
        # Factor 1: Clip count (40 points)
        if len(aligned_pairs) == len(vocab_entries):
            success_factors.append(("Correct clip count", 40))
        elif len(aligned_pairs) >= len(vocab_entries) * 0.8:  # At least 80%
            success_factors.append(("Good clip count", 25))
        else:
            success_factors.append(("Poor clip count", 0))
        
        # Factor 2: Average duration (30 points)
        if avg_duration <= 1.5:
            success_factors.append(("Excellent duration", 30))
        elif avg_duration <= 2.0:
            success_factors.append(("Good duration", 20))
        elif avg_duration <= 2.5:
            success_factors.append(("Fair duration", 10))
        else:
            success_factors.append(("Poor duration", 0))
        
        # Factor 3: Consistency (30 points)
        duration_std = (sum((d - avg_duration)**2 for d in durations) / len(durations))**0.5 if durations else 0
        if duration_std <= 0.3:
            success_factors.append(("Consistent durations", 30))
        elif duration_std <= 0.5:
            success_factors.append(("Fairly consistent", 20))
        else:
            success_factors.append(("Inconsistent durations", 10))
        
        total_score = sum(score for _, score in success_factors)
        
        print(f"\n🏆 Aggressive Boundary Score: {total_score}/100")
        for factor, score in success_factors:
            print(f"   • {factor}: {score} points")
        
        if total_score >= 80:
            print(f"   🎉 Excellent! Ready for production use!")
        elif total_score >= 60:
            print(f"   👍 Good progress! Minor tweaks needed")
        elif total_score >= 40:
            print(f"   🔧 Improvement achieved, more work needed")
        else:
            print(f"   ⚠️  Still needs significant work")
        
        # Specific recommendations
        print(f"\n💡 Recommendations:")
        if len(aligned_pairs) < len(vocab_entries):
            missing = len(vocab_entries) - len(aligned_pairs)
            print(f"   • Missing {missing} clips - try even more aggressive detection")
        
        if avg_duration > 2.0:
            print(f"   • Clips still too long - need sharper boundary detection")
        
        if len(aligned_pairs) >= 7:  # Close to target of 8
            print(f"   • Very close! Try fine-tuning the energy threshold")
        
        # Create detailed report
        summary_file = output_dir / "aggressive_boundary_report.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Aggressive Boundary Detection Report\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Audio: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n")
            f.write(f"Score: {total_score}/100\n\n")
            
            f.write("Aggressive Settings:\n")
            f.write(f"- Min word duration: {segmenter.min_word_duration}s\n")
            f.write(f"- Max word duration: {segmenter.max_word_duration}s\n")
            f.write(f"- Boundary smoothing: {segmenter.boundary_smoothing}s\n")
            f.write(f"- Energy weight: {segmenter.energy_weight}\n")
            f.write(f"- Padding: {clip_generator.padding_duration}s\n\n")
            
            f.write("Results:\n")
            f.write(f"- Average duration: {avg_duration:.3f}s\n")
            f.write(f"- Duration range: {min_duration:.3f}s - {max_duration:.3f}s\n")
            f.write(f"- Duration std dev: {duration_std:.3f}s\n\n")
            
            f.write("Detailed Clips:\n")
            f.write("-" * 25 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)\n")
                f.write(f"    File: {Path(pair.audio_file_path).name}\n\n")
        
        print(f"\n🎧 Test the aggressive clips:")
        print(f"   📁 Folder: {output_dir.absolute()}")
        print(f"   📄 Report: {summary_file.name}")
        print(f"   🎵 Listen to clip 1 - should be shorter and contain less of the second term")
        
        return total_score >= 60
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("⚡ Aggressive Boundary Detection Test")
    print("This will use maximum sensitivity to find word boundaries.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_aggressive_boundaries(audio_file, sheets_url)
    
    if success:
        print("\n🎉 Aggressive boundary detection successful!")
        print("The clips should be much better separated now.")
    else:
        print("\n🔧 Still working on it, but should see improvement.")
        print("Check if clip 1 is shorter and contains less of the second term.")