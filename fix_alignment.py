#!/usr/bin/env python3
"""
Alignment fix script to help identify and correct audio alignment issues.

This script will test different alignment strategies and show you exactly
which vocabulary terms align with which audio segments.
"""

import sys
import argparse
from pathlib import Path
import logging
import numpy as np

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.smart_segmentation import SmartBoundaryDetector


def test_alignment_strategies(google_doc_url: str, audio_file: Path, num_samples: int = 5):
    """
    Test different alignment strategies to find the best one.
    
    Args:
        google_doc_url: URL of Google Doc/Sheets with vocabulary
        audio_file: Path to audio file
        num_samples: Number of samples to show for each strategy
    """
    print("🔧 ALIGNMENT STRATEGY TESTER")
    print("=" * 60)
    
    try:
        # Parse vocabulary
        print("📋 Extracting vocabulary...")
        parser = GoogleSheetsParser()
        vocab_entries = parser.extract_vocabulary_from_sheet(google_doc_url)
        print(f"Found {len(vocab_entries)} vocabulary entries")
        
        # Load audio
        print("\n🔊 Loading audio...")
        loader = AudioLoader()
        audio_data, sample_rate = loader.load_audio(str(audio_file))
        total_duration = len(audio_data) / sample_rate
        print(f"Audio duration: {total_duration:.2f} seconds")
        print(f"Expected time per word: {total_duration / len(vocab_entries):.2f} seconds")
        
        # Test different start offsets
        print(f"\n🎯 TESTING DIFFERENT START OFFSETS")
        print("=" * 60)
        
        test_offsets = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
        
        for offset in test_offsets:
            print(f"\n📍 Testing start offset: {offset:.1f} seconds")
            print("-" * 40)
            
            try:
                detector = SmartBoundaryDetector(sample_rate=sample_rate)
                segments = detector.segment_audio(audio_data, len(vocab_entries), start_offset=offset)
                
                print(f"Created {len(segments)} segments")
                
                # Show first few alignments
                for i in range(min(num_samples, len(vocab_entries), len(segments))):
                    vocab = vocab_entries[i]
                    segment = segments[i]
                    
                    print(f"  {i+1:2d}. '{vocab.english}' → {segment.start_time:.2f}s-{segment.end_time:.2f}s ({segment.end_time-segment.start_time:.2f}s)")
                
                # Calculate average segment duration
                avg_duration = sum(s.end_time - s.start_time for s in segments) / len(segments)
                expected_duration = total_duration / len(vocab_entries)
                duration_diff = abs(avg_duration - expected_duration)
                
                print(f"  Avg segment: {avg_duration:.2f}s, Expected: {expected_duration:.2f}s, Diff: {duration_diff:.2f}s")
                
                # Score this offset (lower is better)
                score = duration_diff + (0.1 if len(segments) != len(vocab_entries) else 0)
                print(f"  Score: {score:.3f} (lower is better)")
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
        
        print(f"\n🎯 MANUAL ALIGNMENT CHECK")
        print("=" * 60)
        print("Listen to your audio file and note the timestamps where each word starts:")
        print()
        
        for i in range(min(10, len(vocab_entries))):
            vocab = vocab_entries[i]
            print(f"{i+1:2d}. '{vocab.english}' starts at: _____ seconds")
        
        print(f"\nThen run this command with the best offset you identified:")
        print(f"python -m cantonese_anki_generator \"{google_doc_url}\" \"{audio_file}\" --verbose")
        
    except Exception as e:
        print(f"❌ Error during alignment testing: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Test different alignment strategies")
    parser.add_argument("google_doc_url", help="URL of Google Sheets/Docs with vocabulary")
    parser.add_argument("audio_file", type=Path, help="Path to audio file")
    parser.add_argument("-n", "--num-samples", type=int, default=5, 
                       help="Number of samples to show for each strategy (default: 5)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    if not args.audio_file.exists():
        print(f"❌ Audio file not found: {args.audio_file}")
        return 1
    
    test_alignment_strategies(args.google_doc_url, args.audio_file, args.num_samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())