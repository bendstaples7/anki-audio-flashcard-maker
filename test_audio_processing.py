#!/usr/bin/env python3
"""
Simple test script to verify audio processing works correctly.
"""

import sys
import argparse
from pathlib import Path
import logging
import numpy as np

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.smart_segmentation import SmartBoundaryDetector


def test_audio_processing(audio_file: Path):
    """
    Test audio processing pipeline to identify issues.
    
    Args:
        audio_file: Path to audio file
    """
    print("🧪 AUDIO PROCESSING TEST")
    print("=" * 50)
    
    try:
        # Test 1: Audio Loading
        print("1️⃣ Testing audio loading...")
        loader = AudioLoader()
        
        # Get audio info first
        try:
            info = loader.get_audio_info(str(audio_file))
            print(f"   ✅ Audio info: {info['duration']:.2f}s, {info['sample_rate']}Hz, {info['format']}")
        except Exception as e:
            print(f"   ⚠️  Audio info failed: {e}")
        
        # Load audio
        audio_data, sample_rate = loader.load_audio(str(audio_file))
        print(f"   ✅ Audio loaded: {len(audio_data)} samples, {sample_rate}Hz")
        print(f"   Duration: {len(audio_data) / sample_rate:.2f}s")
        print(f"   RMS level: {np.sqrt(np.mean(audio_data ** 2)):.6f}")
        
        # Test 2: Smart Segmentation
        print("\n2️⃣ Testing smart segmentation...")
        detector = SmartBoundaryDetector(sample_rate=sample_rate)
        
        # Test with a small number of segments first
        test_segments = 3
        segments = detector.segment_audio(audio_data, test_segments, start_offset=0.0)
        print(f"   ✅ Segmentation successful: {len(segments)} segments created")
        
        for i, segment in enumerate(segments):
            duration = segment.end_time - segment.start_time
            rms = np.sqrt(np.mean(segment.audio_data ** 2))
            print(f"   Segment {i+1}: {segment.start_time:.3f}s - {segment.end_time:.3f}s "
                  f"(duration: {duration:.3f}s, RMS: {rms:.6f})")
        
        print("\n✅ ALL TESTS PASSED!")
        print("Audio processing pipeline is working correctly.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Test audio processing pipeline")
    parser.add_argument("audio_file", type=Path, help="Path to audio file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    if not args.audio_file.exists():
        print(f"❌ Audio file not found: {args.audio_file}")
        return 1
    
    success = test_audio_processing(args.audio_file)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())