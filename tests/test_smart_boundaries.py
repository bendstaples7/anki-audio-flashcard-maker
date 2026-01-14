#!/usr/bin/env python3
"""
Smart boundary detection that finds actual silence gaps between words.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy import signal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.clip_generator import AudioClipGenerator
from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser


def get_timestamp():
    """Get current timestamp for folder naming."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def find_silence_gaps(audio_data, sample_rate, min_gap_duration=0.1, silence_threshold=0.02):
    """
    Find silence gaps in audio that could be word boundaries.
    
    Args:
        audio_data: Audio data array
        sample_rate: Sample rate
        min_gap_duration: Minimum gap duration to consider (seconds)
        silence_threshold: RMS threshold below which audio is considered silence
    
    Returns:
        List of (start_time, end_time) tuples for silence gaps
    """
    # Calculate RMS energy in small windows
    window_size = int(0.02 * sample_rate)  # 20ms windows
    hop_size = int(0.01 * sample_rate)     # 10ms hop
    
    rms_values = []
    times = []
    
    for i in range(0, len(audio_data) - window_size, hop_size):
        window = audio_data[i:i + window_size]
        rms = np.sqrt(np.mean(window ** 2))
        rms_values.append(rms)
        times.append(i / sample_rate)
    
    rms_values = np.array(rms_values)
    times = np.array(times)
    
    # Find silence regions
    silence_mask = rms_values < silence_threshold
    
    # Find continuous silence regions
    silence_gaps = []
    in_silence = False
    silence_start = 0
    
    for i, is_silent in enumerate(silence_mask):
        if is_silent and not in_silence:
            # Start of silence
            in_silence = True
            silence_start = times[i]
        elif not is_silent and in_silence:
            # End of silence
            in_silence = False
            silence_end = times[i]
            
            # Check if gap is long enough
            if silence_end - silence_start >= min_gap_duration:
                silence_gaps.append((silence_start, silence_end))
    
    return silence_gaps


def create_smart_segments(audio_data, sample_rate, expected_count, start_offset=1.0):
    """
    Create segments using smart boundary detection.
    
    Args:
        audio_data: Audio data array
        sample_rate: Sample rate
        expected_count: Expected number of segments
        start_offset: Seconds to skip at beginning
    
    Returns:
        List of AudioSegment objects
    """
    # Find silence gaps
    silence_gaps = find_silence_gaps(audio_data, sample_rate, min_gap_duration=0.05, silence_threshold=0.015)
    
    print(f"   🔍 Found {len(silence_gaps)} potential silence gaps:")
    for i, (start, end) in enumerate(silence_gaps[:10]):  # Show first 10
        duration = end - start
        print(f"      Gap {i+1}: {start:.2f}s - {end:.2f}s ({duration:.3f}s)")
    
    # Filter gaps that are after our start offset
    valid_gaps = [(start, end) for start, end in silence_gaps if start >= start_offset]
    
    print(f"   ✅ {len(valid_gaps)} gaps after {start_offset}s offset")
    
    # If we have too many gaps, keep the longest ones
    if len(valid_gaps) > expected_count - 1:
        # Sort by gap duration (longest first)
        gap_durations = [(end - start, start, end) for start, end in valid_gaps]
        gap_durations.sort(reverse=True)
        
        # Keep the longest gaps
        selected_gaps = [(start, end) for _, start, end in gap_durations[:expected_count - 1]]
        selected_gaps.sort()  # Sort by time
        valid_gaps = selected_gaps
        
        print(f"   📊 Selected {len(valid_gaps)} longest gaps")
    
    # Create segment boundaries
    boundaries = [start_offset]  # Start boundary
    
    for gap_start, gap_end in valid_gaps:
        # Use middle of gap as boundary
        boundary = (gap_start + gap_end) / 2
        boundaries.append(boundary)
    
    # Add end boundary
    total_duration = len(audio_data) / sample_rate
    boundaries.append(total_duration - 0.3)  # Leave small buffer at end
    
    print(f"   🎯 Created {len(boundaries)} boundaries for {len(boundaries)-1} segments")
    
    # Create segments
    segments = []
    for i in range(len(boundaries) - 1):
        start_time = boundaries[i]
        end_time = boundaries[i + 1]
        
        # Add small padding to ensure complete words
        padded_start = max(0, start_time - 0.05)  # 50ms before
        padded_end = min(total_duration, end_time + 0.05)  # 50ms after
        
        # Convert to samples
        start_sample = int(padded_start * sample_rate)
        end_sample = int(padded_end * sample_rate)
        
        # Extract audio
        segment_audio = audio_data[start_sample:end_sample]
        
        # Create segment
        segment = AudioSegment(
            start_time=padded_start,
            end_time=padded_end,
            audio_data=segment_audio,
            confidence=0.8,  # Good confidence for gap-based detection
            segment_id=f"smart_{i+1:03d}"
        )
        
        segments.append(segment)
    
    return segments


def test_smart_boundaries(audio_path, sheets_url):
    """Test smart boundary detection."""
    
    # Create timestamped output folder
    timestamp = get_timestamp()
    output_folder = f"audio_test_results/{timestamp}_smart_boundaries"
    
    print("🧠 Smart Boundary Detection Test")
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
        
        # Load audio
        print(f"\n🔊 Loading audio...")
        loader = AudioLoader()
        audio_data, sample_rate = loader.load_audio(audio_path)
        total_duration = len(audio_data) / sample_rate
        
        print(f"   ✓ Duration: {total_duration:.2f}s")
        print(f"   ✓ Sample rate: {sample_rate}Hz")
        
        # Create smart segments
        print(f"\n🧠 Detecting word boundaries using silence gaps...")
        segments = create_smart_segments(audio_data, sample_rate, len(vocab_entries))
        
        print(f"✅ Created {len(segments)} segments")
        
        # Generate audio clips
        print(f"\n🎵 Generating audio clips...")
        clip_generator = AudioClipGenerator(sample_rate=sample_rate)
        
        # Configure for high quality
        clip_generator.set_quality_parameters(
            fade_duration=0.005,
            padding_duration=0.0,  # We already added padding
            normalize_clips=True,
            target_peak_level=0.8
        )
        
        # Save clips and create aligned pairs
        aligned_pairs = []
        for i, (segment, vocab_entry) in enumerate(zip(segments, vocab_entries)):
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
                    alignment_confidence=segment.confidence,
                    audio_file_path=str(clip_path)
                )
                aligned_pairs.append(aligned_pair)
        
        print(f"✅ Generated {len(aligned_pairs)} clips")
        
        # Analysis
        durations = [pair.audio_segment.end_time - pair.audio_segment.start_time for pair in aligned_pairs]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        print(f"\n📊 Smart Boundary Results:")
        print(f"   🎯 Clip count: {len(aligned_pairs)}/{len(vocab_entries)} ({'✅' if len(aligned_pairs) == len(vocab_entries) else '⚠️'})")
        print(f"   📏 Duration range: {min_duration:.2f}s - {max_duration:.2f}s (avg: {avg_duration:.2f}s)")
        
        # Show clips with timing details
        print(f"\n📋 Smart Boundary Clips:")
        for i, pair in enumerate(aligned_pairs, 1):
            duration = pair.audio_segment.end_time - pair.audio_segment.start_time
            clip_filename = Path(pair.audio_file_path).name
            
            # Quality indicator based on duration
            if 0.8 <= duration <= 2.5:
                quality = "🟢 Good"
            elif 0.5 <= duration <= 3.0:
                quality = "🟡 OK"
            else:
                quality = "🔴 Check"
            
            print(f"   {i:2d}. {clip_filename:25s} | {pair.vocabulary_entry.english:12s} → {pair.vocabulary_entry.cantonese:10s}")
            print(f"       {quality} ({duration:.2f}s) | {pair.audio_segment.start_time:.2f}s - {pair.audio_segment.end_time:.2f}s")
        
        # Create summary files
        summary_file = output_dir / "SMART_BOUNDARY_RESULTS.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Smart Boundary Detection Results\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"APPROACH: Silence Gap Detection\n")
            f.write(f"Audio file: {audio_path}\n")
            f.write(f"Total duration: {total_duration:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n")
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
            f.write(f"Smart Boundary Detection - {timestamp}\n")
            f.write("=" * 40 + "\n\n")
            f.write("APPROACH:\n")
            f.write("This test finds actual silence gaps between words by:\n")
            f.write("1. Analyzing audio energy in small windows\n")
            f.write("2. Identifying regions below silence threshold\n")
            f.write("3. Finding gaps long enough to be word boundaries\n")
            f.write("4. Using gap centers as segment boundaries\n\n")
            f.write("ADVANTAGES:\n")
            f.write("- Adapts to actual word lengths\n")
            f.write("- Finds real silence periods\n")
            f.write("- No uniform timing assumptions\n\n")
            f.write("TEST INSTRUCTIONS:\n")
            f.write("1. Listen to each clip in order\n")
            f.write("2. Check if boundaries align with actual word breaks\n")
            f.write("3. Note any clips that are cut off or contain multiple words\n\n")
            f.write("EXPECTED VOCABULARY:\n")
            for i, entry in enumerate(vocab_entries, 1):
                f.write(f"{i:2d}. {entry.english} → {entry.cantonese}\n")
        
        print(f"\n📁 All files saved to: {output_dir.absolute()}")
        print(f"📄 Read: README.txt and SMART_BOUNDARY_RESULTS.txt")
        print(f"🎧 Listen to: Dec 5 Ben S_001.wav through Dec 5 Ben S_{len(aligned_pairs):03d}.wav")
        
        # Success assessment
        success_score = 0
        if len(aligned_pairs) == len(vocab_entries):
            success_score += 50
        if 1.0 <= avg_duration <= 2.5:
            success_score += 30
        if max_duration - min_duration <= 1.5:  # Reasonable variation
            success_score += 20
        
        print(f"\n🏆 Smart Boundary Score: {success_score}/100")
        if success_score >= 80:
            print("   🎉 Excellent! Smart boundaries work great!")
        elif success_score >= 60:
            print("   👍 Good! Smart boundaries are promising!")
        else:
            print("   🔧 Smart boundaries need adjustment")
        
        print(f"\n💡 Key Advantage:")
        print(f"   This approach adapts to actual word lengths instead of")
        print(f"   assuming uniform timing, which should fix the issues")
        print(f"   you found with the manual timing approach.")
        
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
    
    print("🧠 Smart Boundary Detection Test")
    print("This finds actual silence gaps between words.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_smart_boundaries(audio_file, sheets_url)
    
    print(f"\n{'🎉 Smart boundary detection successful!' if success else '🔧 Smart boundaries need work.'}")
    print("This approach should adapt to different word lengths!")


if __name__ == "__main__":
    main()