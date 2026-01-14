#!/usr/bin/env python3
"""
Find the perfect alignment offset for your audio file.

This script will test many different start offsets and show you the results
so you can pick the one that aligns "the flowers" correctly.
"""

import sys
import argparse
from pathlib import Path
import logging

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.smart_segmentation import SmartBoundaryDetector


def find_perfect_alignment(google_doc_url: str, audio_file: Path):
    """
    Find the perfect alignment offset by testing many different values.
    
    Args:
        google_doc_url: URL of Google Doc/Sheets with vocabulary
        audio_file: Path to audio file
    """
    print("🎯 FINDING PERFECT ALIGNMENT")
    print("=" * 50)
    
    try:
        # Parse vocabulary
        print("📋 Extracting vocabulary...")
        parser = GoogleSheetsParser()
        vocab_entries = parser.extract_vocabulary_from_sheet(google_doc_url)
        print(f"Found {len(vocab_entries)} vocabulary entries")
        
        # Show first few vocabulary entries
        print("\nFirst few vocabulary entries:")
        for i in range(min(10, len(vocab_entries))):
            vocab = vocab_entries[i]
            print(f"  {i+1:2d}. '{vocab.english}' → '{vocab.cantonese}'")
        
        # Load audio
        print("\n🔊 Loading audio...")
        loader = AudioLoader()
        audio_data, sample_rate = loader.load_audio(str(audio_file))
        total_duration = len(audio_data) / sample_rate
        print(f"Audio duration: {total_duration:.2f} seconds")
        
        # Test many different start offsets
        print(f"\n🎯 TESTING DIFFERENT START OFFSETS")
        print("=" * 80)
        print("Look for the offset where 'the flowers' gets the right audio segment")
        print()
        
        # Test offsets from 0 to 8 seconds in 0.2 second increments
        test_offsets = [i * 0.2 for i in range(41)]  # 0.0 to 8.0 seconds
        
        detector = SmartBoundaryDetector(sample_rate=sample_rate)
        
        for offset in test_offsets:
            try:
                segments = detector.segment_audio(audio_data, len(vocab_entries), 
                                                start_offset=offset, force_start_offset=True)
                
                if len(segments) >= len(vocab_entries):
                    # Find "the flowers" in vocabulary
                    flowers_index = None
                    for i, vocab in enumerate(vocab_entries):
                        if 'flower' in vocab.english.lower():
                            flowers_index = i
                            break
                    
                    print(f"Offset {offset:4.1f}s:", end="")
                    
                    # Show first few alignments
                    for i in range(min(5, len(vocab_entries), len(segments))):
                        vocab = vocab_entries[i]
                        segment = segments[i]
                        
                        # Highlight "the flowers" if found
                        if i == flowers_index:
                            print(f" 🌸'{vocab.english}'→{segment.start_time:.1f}-{segment.end_time:.1f}s", end="")
                        else:
                            print(f" '{vocab.english}'→{segment.start_time:.1f}-{segment.end_time:.1f}s", end="")
                    
                    print()  # New line
                else:
                    print(f"Offset {offset:4.1f}s: ❌ Only created {len(segments)} segments")
                    
            except Exception as e:
                print(f"Offset {offset:4.1f}s: ❌ Error: {e}")
        
        print(f"\n🎯 INSTRUCTIONS:")
        print("=" * 50)
        print("1. Look at the output above and find the offset where 'the flowers' 🌸")
        print("   gets a reasonable time range (should be 1-3 seconds long)")
        print("2. Listen to your audio at that time range to verify it's correct")
        print("3. Use that offset with the --start-offset parameter:")
        print()
        print(f"   python -m cantonese_anki_generator \\")
        print(f"     \"{google_doc_url}\" \\")
        print(f"     \"{audio_file}\" \\")
        print(f"     --start-offset X.X \\")
        print(f"     --verbose")
        print()
        print("   Replace X.X with the best offset you found above")
        
    except Exception as e:
        print(f"❌ Error during alignment testing: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Find perfect alignment offset")
    parser.add_argument("google_doc_url", help="URL of Google Sheets/Docs with vocabulary")
    parser.add_argument("audio_file", type=Path, help="Path to audio file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)  # Reduce noise
    
    if not args.audio_file.exists():
        print(f"❌ Audio file not found: {args.audio_file}")
        return 1
    
    find_perfect_alignment(args.google_doc_url, args.audio_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())