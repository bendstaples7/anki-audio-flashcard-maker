#!/usr/bin/env python3
"""
Organized audio testing with timestamped results.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry
from cantonese_anki_generator.audio.processor import AudioProcessor
from cantonese_anki_generator.alignment import AudioVocabularyAligner
from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser


def get_timestamp():
    """Get current timestamp for folder naming."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def test_audio_segmentation(audio_path, sheets_url):
    """Test audio segmentation with organized output."""
    
    # Create timestamped output folder
    timestamp = get_timestamp()
    output_folder = f"audio_test_results/{timestamp}_segmentation_test"
    
    print("🎵 Organized Audio Segmentation Test")
    print("=" * 45)
    print(f"📅 Timestamp: {timestamp}")
    
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
        
        print(f"✅ Found {len(vocab_entries)} vocabulary terms:")
        for i, entry in enumerate(vocab_entries, 1):
            print(f"   {i:2d}. {entry.english:15s} → {entry.cantonese}")
        
        # Create output directory
        output_dir = Path(output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Output folder: {output_dir.absolute()}")
        
        # Configure processor with current best settings
        print(f"\n⚡ Configuring segmentation (current best settings)...")
        processor = AudioProcessor()
        
        # Use FINE-TUNED settings: aggressive detection + complete words
        processor.set_processing_parameters(
            vad_aggressiveness=3,        # Keep aggressive
            min_word_duration=0.25,      # Compromise: not too short, not too long
            fade_duration=0.003,         # Minimal fade
            normalize_clips=True
        )
        
        # Fine-tuned segmenter settings
        segmenter = processor.segmenter
        segmenter.min_word_duration = 0.25       # Compromise (was 0.15 too short, 0.4 too long)
        segmenter.max_word_duration = 2.0        # Reasonable maximum
        segmenter.boundary_smoothing = 0.01      # Minimal smoothing for sharp boundaries
        segmenter.energy_weight = 0.7            # High energy weight for boundary detection
        segmenter.spectral_weight = 0.2          # Some spectral info
        segmenter.temporal_weight = 0.1          # Minimal temporal
        
        # Fine-tuned clip generator - minimal padding
        clip_generator = processor.clip_generator
        clip_generator.set_quality_parameters(
            fade_duration=0.003,         # Minimal fade
            padding_duration=0.01,       # Tiny padding for word completion (was 0.0)
            normalize_clips=True,
            target_peak_level=0.85
        )
        
        print(f"   ✓ Settings: fine-tuned for complete words without overlap")
        
        # Process audio
        print(f"\n🔄 Processing audio...")
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
        
        # Analysis
        durations = [pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        print(f"\n📊 Results Summary:")
        print(f"   🎯 Clip count: {len(aligned_pairs)}/{len(vocab_entries)} ({'✅' if len(aligned_pairs) == len(vocab_entries) else '⚠️'})")
        print(f"   📏 Duration range: {min_duration:.2f}s - {max_duration:.2f}s (avg: {avg_duration:.2f}s)")
        
        # Show clips with quality indicators
        print(f"\n📋 Generated Clips:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            # Quality indicator
            if duration <= 1.5:
                quality = "🟢 Excellent"
            elif duration <= 2.0:
                quality = "🟡 Good"
            elif duration <= 2.5:
                quality = "🟠 Fair"
            else:
                quality = "🔴 Long"
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s}")
            print(f"       {quality} ({duration:.2f}s) | {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s")
        
        # Create summary file
        summary_file = output_dir / "RESULTS_SUMMARY.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Audio Segmentation Test Results\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"INPUT:\n")
            f.write(f"Audio file: {audio_path}\n")
            f.write(f"Duration: {stats['audio_duration']:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n\n")
            
            f.write(f"RESULTS:\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n")
            f.write(f"Success rate: {len(aligned_pairs)}/{len(vocab_entries)} ({len(aligned_pairs)/len(vocab_entries)*100:.1f}%)\n")
            f.write(f"Average duration: {avg_duration:.2f}s\n")
            f.write(f"Duration range: {min_duration:.2f}s - {max_duration:.2f}s\n\n")
            
            f.write(f"CLIP DETAILS:\n")
            f.write("-" * 30 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    File: {Path(pair.audio_file_path).name}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)\n\n")
            
            f.write(f"VOCABULARY FROM GOOGLE SHEETS:\n")
            f.write("-" * 30 + "\n")
            for i, entry in enumerate(vocab_entries, 1):
                f.write(f"{i:2d}. {entry.english:15s} → {entry.cantonese}\n")
        
        # Create README for easy navigation
        readme_file = output_dir / "README.txt"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(f"Audio Test Results - {timestamp}\n")
            f.write("=" * 35 + "\n\n")
            f.write("FILES IN THIS FOLDER:\n")
            f.write("- README.txt (this file)\n")
            f.write("- RESULTS_SUMMARY.txt (detailed results)\n")
            f.write(f"- Dec 5 Ben S_001.wav through Dec 5 Ben S_{len(aligned_pairs):03d}.wav (audio clips)\n\n")
            f.write("HOW TO TEST:\n")
            f.write("1. Read RESULTS_SUMMARY.txt for overview\n")
            f.write("2. Listen to each .wav file in order\n")
            f.write("3. Check if each clip contains only the expected word\n")
            f.write("4. Pay special attention to clips marked as 'Long' in the summary\n\n")
            f.write("EXPECTED VOCABULARY ORDER:\n")
            for i, entry in enumerate(vocab_entries, 1):
                f.write(f"{i:2d}. {entry.english} → {entry.cantonese}\n")
        
        print(f"\n📁 All files saved to: {output_dir.absolute()}")
        print(f"📄 Read: README.txt and RESULTS_SUMMARY.txt")
        print(f"🎧 Listen to: Dec 5 Ben S_001.wav through Dec 5 Ben S_{len(aligned_pairs):03d}.wav")
        
        # Success assessment
        success_score = 0
        if len(aligned_pairs) == len(vocab_entries):
            success_score += 50
        if avg_duration <= 2.0:
            success_score += 30
        if min_duration >= 0.3:
            success_score += 20
        
        print(f"\n🏆 Overall Score: {success_score}/100")
        if success_score >= 80:
            print("   🎉 Excellent results!")
        elif success_score >= 60:
            print("   👍 Good results!")
        else:
            print("   🔧 Needs improvement")
        
        return success_score >= 60
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("🎵 Organized Audio Segmentation Test")
    print("Results will be saved with timestamps for easy tracking.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_audio_segmentation(audio_file, sheets_url)
    
    print(f"\n{'🎉 Test completed successfully!' if success else '🔧 Test completed with issues.'}")
    print("Check the audio_test_results folder for your timestamped results.")


if __name__ == "__main__":
    main()