#!/usr/bin/env python3
"""
Manual timing approach - divide audio mathematically into equal segments.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import numpy as np

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.clip_generator import AudioClipGenerator
from cantonese_anki_generator.alignment import AudioVocabularyAligner
from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser


def get_timestamp():
    """Get current timestamp for folder naming."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def create_manual_segments(audio_data, sample_rate, num_segments, start_offset=0.5, end_offset=0.5, gap_ratio=0.1):
    """
    Create audio segments by dividing the audio mathematically with gaps.
    
    Args:
        audio_data: Audio data array
        sample_rate: Sample rate
        num_segments: Number of segments to create
        start_offset: Seconds to skip at the beginning
        end_offset: Seconds to skip at the end
        gap_ratio: Fraction of each segment to use as gap (0.1 = 10% gap)
    
    Returns:
        List of AudioSegment objects
    """
    total_duration = len(audio_data) / sample_rate
    usable_duration = total_duration - start_offset - end_offset
    segment_duration = usable_duration / num_segments
    
    # Calculate actual clip duration (shorter than segment to leave gaps)
    clip_duration = segment_duration * (1.0 - gap_ratio)
    gap_duration = segment_duration * gap_ratio
    
    segments = []
    
    for i in range(num_segments):
        # Calculate timing with gaps
        segment_start = start_offset + (i * segment_duration)
        clip_start = segment_start + (gap_duration / 2)  # Center the clip in the segment
        clip_end = clip_start + clip_duration
        
        # Convert to samples
        start_sample = int(clip_start * sample_rate)
        end_sample = int(clip_end * sample_rate)
        
        # Extract audio
        segment_audio = audio_data[start_sample:end_sample]
        
        # Create segment
        segment = AudioSegment(
            start_time=clip_start,
            end_time=clip_end,
            audio_data=segment_audio,
            confidence=0.9,  # High confidence for manual segmentation
            segment_id=f"manual_{i+1:03d}"
        )
        
        segments.append(segment)
    
    return segments


def test_manual_timing(audio_path, sheets_url):
    """Test manual timing approach."""
    
    # Create timestamped output folder
    timestamp = get_timestamp()
    output_folder = f"audio_test_results/{timestamp}_manual_timing"
    
    print("📐 Manual Timing Segmentation Test")
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
        
        # Load audio manually
        print(f"\n🔊 Loading audio...")
        loader = AudioLoader()
        audio_data, sample_rate = loader.load_audio(audio_path)
        total_duration = len(audio_data) / sample_rate
        
        print(f"   ✓ Duration: {total_duration:.2f}s")
        print(f"   ✓ Sample rate: {sample_rate}Hz")
        
        # Create manual segments
        print(f"\n📐 Creating manual segments...")
        print(f"   Strategy: Divide {total_duration:.2f}s into {len(vocab_entries)} equal parts")
        
        # Try different gap strategies
        strategies = [
            ("Small gaps", 1.0, 0.5, 0.15),    # 15% gaps
            ("Medium gaps", 1.0, 0.5, 0.20),   # 20% gaps  
            ("Large gaps", 1.0, 0.5, 0.25),    # 25% gaps
        ]
        
        best_segments = None
        best_strategy = None
        
        for strategy_name, start_offset, end_offset, gap_ratio in strategies:
            segments = create_manual_segments(audio_data, sample_rate, len(vocab_entries), start_offset, end_offset, gap_ratio)
            
            usable_duration = total_duration - start_offset - end_offset
            segment_duration = usable_duration / len(vocab_entries)
            clip_duration = segment_duration * (1.0 - gap_ratio)
            
            print(f"   📊 {strategy_name}: {start_offset}s + {usable_duration:.1f}s + {end_offset}s")
            print(f"      → {clip_duration:.2f}s clips + {segment_duration * gap_ratio:.2f}s gaps")
            
            # Choose strategy with reasonable clip length (1-2.5 seconds)
            if 1.0 <= clip_duration <= 2.5:
                best_segments = segments
                best_strategy = strategy_name
                break
        
        if not best_segments:
            # Fallback to small gaps
            best_segments = create_manual_segments(audio_data, sample_rate, len(vocab_entries), 1.0, 0.5, 0.15)
            best_strategy = "Fallback"
        
        print(f"   ✅ Using {best_strategy} strategy")
        
        # Generate audio clips
        print(f"\n🎵 Generating audio clips...")
        clip_generator = AudioClipGenerator(sample_rate=sample_rate)
        
        # Configure for high quality
        clip_generator.set_quality_parameters(
            fade_duration=0.01,      # Small fade to prevent clicks
            padding_duration=0.0,    # No padding - we're manually controlling timing
            normalize_clips=True,
            target_peak_level=0.8
        )
        
        # Save clips manually
        aligned_pairs = []
        for i, (segment, vocab_entry) in enumerate(zip(best_segments, vocab_entries)):
            # Generate filename
            clip_filename = f"Dec 5 Ben S_{i+1:03d}.wav"
            clip_path = output_dir / clip_filename
            
            # Save audio clip
            success = clip_generator._save_audio_clip(segment.audio_data, str(clip_path))
            
            if success:
                # Update segment with file path
                segment.audio_file_path = str(clip_path)
                
                # Create aligned pair
                from cantonese_anki_generator.models import AlignedPair
                aligned_pair = AlignedPair(
                    vocabulary_entry=vocab_entry,
                    audio_segment=segment,
                    alignment_confidence=0.9,  # High confidence for manual
                    audio_file_path=str(clip_path)
                )
                aligned_pairs.append(aligned_pair)
        
        print(f"✅ Generated {len(aligned_pairs)} clips")
        
        # Analysis
        durations = [pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        print(f"\n📊 Manual Timing Results:")
        print(f"   🎯 Clip count: {len(aligned_pairs)}/{len(vocab_entries)} ({'✅' if len(aligned_pairs) == len(vocab_entries) else '⚠️'})")
        print(f"   📏 Duration range: {min_duration:.2f}s - {max_duration:.2f}s (avg: {avg_duration:.2f}s)")
        print(f"   📐 Strategy: {best_strategy}")
        
        # Show clips
        print(f"\n📋 Generated Clips:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            # Quality indicator
            if 1.0 <= duration <= 2.5:
                quality = "🟢 Good"
            elif 0.5 <= duration <= 3.0:
                quality = "🟡 OK"
            else:
                quality = "🔴 Check"
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s}")
            print(f"       {quality} ({duration:.2f}s) | {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s")
        
        # Create summary files
        summary_file = output_dir / "MANUAL_TIMING_RESULTS.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Manual Timing Segmentation Results\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 45 + "\n\n")
            
            f.write(f"APPROACH: Mathematical Division\n")
            f.write(f"Audio file: {audio_path}\n")
            f.write(f"Total duration: {total_duration:.2f}s\n")
            f.write(f"Strategy: {best_strategy}\n")
            f.write(f"Vocabulary terms: {len(vocab_entries)}\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n\n")
            
            f.write(f"RESULTS:\n")
            f.write(f"Average duration: {avg_duration:.2f}s\n")
            f.write(f"Duration range: {min_duration:.2f}s - {max_duration:.2f}s\n\n")
            
            f.write(f"CLIP DETAILS:\n")
            f.write("-" * 30 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    File: {Path(pair.audio_file_path).name}\n")
                f.write(f"    Time: {pair.audio_segment.start_time:.3f}s - {pair.audio_segment.end_time:.3f}s ({duration:.3f}s)\n\n")
        
        # Create README
        readme_file = output_dir / "README.txt"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(f"Manual Timing Test - {timestamp}\n")
            f.write("=" * 35 + "\n\n")
            f.write("APPROACH:\n")
            f.write("Instead of trying to detect word boundaries automatically,\n")
            f.write("this test divides the audio mathematically into equal segments.\n\n")
            f.write("THEORY:\n")
            f.write("Since you can see clear gaps in the waveform, and we know\n")
            f.write("there are exactly 8 terms, we can divide the audio duration\n")
            f.write("by 8 to get approximately equal segments.\n\n")
            f.write("TEST INSTRUCTIONS:\n")
            f.write("1. Listen to each clip in order\n")
            f.write("2. Check if each contains exactly one vocabulary term\n")
            f.write("3. Note if any clips are cut off or contain multiple terms\n")
            f.write("4. This will tell us if mathematical division works better\n")
            f.write("   than automatic boundary detection\n\n")
            f.write("EXPECTED VOCABULARY:\n")
            for i, entry in enumerate(vocab_entries, 1):
                f.write(f"{i:2d}. {entry.english} → {entry.cantonese}\n")
        
        print(f"\n📁 All files saved to: {output_dir.absolute()}")
        print(f"📄 Read: README.txt and MANUAL_TIMING_RESULTS.txt")
        print(f"🎧 Listen to: Dec 5 Ben S_001.wav through Dec 5 Ben S_{len(aligned_pairs):03d}.wav")
        
        # Success assessment
        success_score = 0
        if len(aligned_pairs) == len(vocab_entries):
            success_score += 50  # Perfect count
        if 1.0 <= avg_duration <= 2.5:
            success_score += 30  # Good duration
        if max_duration - min_duration <= 1.0:
            success_score += 20  # Consistent durations
        
        print(f"\n🏆 Manual Timing Score: {success_score}/100")
        if success_score >= 80:
            print("   🎉 Excellent! Manual timing works great!")
        elif success_score >= 60:
            print("   👍 Good! Manual timing is promising!")
        else:
            print("   🔧 Manual timing needs adjustment")
        
        print(f"\n💡 Next Steps:")
        print(f"   1. Listen to the clips to see if they're properly separated")
        print(f"   2. If they work well, we can use this approach instead of boundary detection")
        print(f"   3. If not, we can adjust the start/end offsets")
        
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
    
    print("📐 Manual Timing Segmentation Test")
    print("This uses mathematical division instead of boundary detection.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_manual_timing(audio_file, sheets_url)
    
    print(f"\n{'🎉 Manual timing successful!' if success else '🔧 Manual timing needs work.'}")
    print("Check the results to see if mathematical division works better!")


if __name__ == "__main__":
    main()