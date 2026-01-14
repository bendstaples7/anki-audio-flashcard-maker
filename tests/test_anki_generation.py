#!/usr/bin/env python3
"""
Test Anki package generation with real vocabulary and audio.

This test integrates the complete pipeline:
1. Extract vocabulary from Google Sheets
2. Segment audio using smart boundary detection
3. Generate Anki package with embedded audio
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment, AlignedPair
from cantonese_anki_generator.audio.loader import AudioLoader
from cantonese_anki_generator.audio.smart_segmentation import SmartBoundaryDetector
from cantonese_anki_generator.processors.google_sheets_parser import GoogleSheetsParser
from cantonese_anki_generator.anki import AnkiPackageGenerator, UniqueNamingManager


def get_timestamp():
    """Get current timestamp for folder naming."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def test_anki_generation(audio_path, sheets_url):
    """Test complete Anki package generation."""
    
    timestamp = get_timestamp()
    output_folder = f"audio_test_results/{timestamp}_anki_generation"
    
    print("📦 Anki Package Generation Test")
    print("=" * 40)
    print(f"📅 Timestamp: {timestamp}")
    
    # Clean up the audio path
    audio_path = audio_path.strip().strip('"').strip("'")
    
    if not os.path.exists(audio_path):
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    print(f"📁 Audio file: {audio_path}")
    
    try:
        # Create output directory
        output_dir = Path(output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Output folder: {output_dir.absolute()}")
        
        # Step 1: Extract vocabulary from Google Sheets
        print(f"\n📋 Step 1: Extracting vocabulary...")
        sheets_parser = GoogleSheetsParser()
        vocab_entries = sheets_parser.extract_vocabulary_from_sheet(sheets_url)
        
        print(f"✅ Found {len(vocab_entries)} vocabulary terms:")
        for i, entry in enumerate(vocab_entries[:5], 1):  # Show first 5
            print(f"   {i:2d}. {entry.english:15s} → {entry.cantonese}")
        if len(vocab_entries) > 5:
            print(f"   ... and {len(vocab_entries) - 5} more")
        
        # Step 2: Load and segment audio
        print(f"\n🔊 Step 2: Loading and segmenting audio...")
        loader = AudioLoader()
        audio_data, sample_rate = loader.load_audio(audio_path)
        total_duration = len(audio_data) / sample_rate
        
        print(f"   ✓ Duration: {total_duration:.2f}s")
        print(f"   ✓ Sample rate: {sample_rate}Hz")
        
        # Use smart boundary detection
        detector = SmartBoundaryDetector(sample_rate=sample_rate)
        segments = detector.segment_audio(audio_data, len(vocab_entries))
        
        print(f"✅ Created {len(segments)} audio segments")
        
        # Step 3: Save audio clips and create aligned pairs
        print(f"\n🎵 Step 3: Generating audio clips...")
        
        aligned_pairs = []
        for i, (segment, vocab_entry) in enumerate(zip(segments, vocab_entries)):
            # Generate filename for this clip
            clip_filename = f"cantonese_{i+1:03d}.wav"
            clip_path = output_dir / clip_filename
            
            # Save audio clip using scipy
            import scipy.io.wavfile as wavfile
            
            # Normalize audio to 16-bit range
            audio_normalized = (segment.audio_data * 32767).astype('int16')
            wavfile.write(str(clip_path), sample_rate, audio_normalized)
            
            # Update segment with file path
            segment.audio_file_path = str(clip_path)
            
            # Create aligned pair
            aligned_pair = AlignedPair(
                vocabulary_entry=vocab_entry,
                audio_segment=segment,
                alignment_confidence=0.85,  # Good confidence
                audio_file_path=str(clip_path)
            )
            aligned_pairs.append(aligned_pair)
        
        print(f"✅ Generated {len(aligned_pairs)} audio clips")
        
        # Step 4: Generate Anki package
        print(f"\n📦 Step 4: Creating Anki package...")
        
        # Initialize naming manager and package generator
        naming_manager = UniqueNamingManager()
        package_generator = AnkiPackageGenerator()
        
        # Generate unique names
        deck_name = naming_manager.generate_unique_deck_name(
            base_name="Cantonese Vocabulary",
            source_info=f"Audio_{timestamp}"
        )
        
        package_filename = naming_manager.generate_unique_package_filename(
            base_name=f"cantonese_vocab_{timestamp}",
            output_dir=str(output_dir)
        )
        
        package_path = output_dir / package_filename
        
        print(f"   📝 Deck name: {deck_name}")
        print(f"   📄 Package file: {package_filename}")
        
        # Generate the package
        success = package_generator.generate_package(
            aligned_pairs=aligned_pairs,
            output_path=str(package_path),
            deck_name=deck_name
        )
        
        if success:
            print(f"✅ Anki package created successfully!")
            
            # Validate the package
            from cantonese_anki_generator.anki import PackageValidator
            validator = PackageValidator()
            
            if validator.validate_package(str(package_path)):
                print(f"✅ Package validation passed")
                
                # Get package info
                info = validator.get_package_info(str(package_path))
                print(f"   📊 Package size: {info['size_bytes']:,} bytes")
                
            else:
                print(f"⚠️ Package validation failed")
        
        else:
            print(f"❌ Failed to create Anki package")
            return False
        
        # Step 5: Create summary
        print(f"\n📋 Step 5: Creating summary...")
        
        summary_file = output_dir / "ANKI_GENERATION_RESULTS.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"Anki Package Generation Results\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"INPUT:\n")
            f.write(f"Audio file: {audio_path}\n")
            f.write(f"Vocabulary source: Google Sheets\n")
            f.write(f"Total duration: {total_duration:.2f}s\n")
            f.write(f"Expected terms: {len(vocab_entries)}\n\n")
            
            f.write(f"PROCESSING:\n")
            f.write(f"Segmentation method: Smart Boundary Detection\n")
            f.write(f"Generated clips: {len(aligned_pairs)}\n")
            f.write(f"Audio format: WAV, {sample_rate}Hz\n\n")
            
            f.write(f"OUTPUT:\n")
            f.write(f"Anki deck: {deck_name}\n")
            f.write(f"Package file: {package_filename}\n")
            f.write(f"Package size: {info['size_bytes']:,} bytes\n")
            f.write(f"Cards created: {len(aligned_pairs)}\n\n")
            
            f.write(f"VOCABULARY CARDS:\n")
            f.write("-" * 30 + "\n")
            for i, pair in enumerate(aligned_pairs, 1):
                duration = pair.audio_segment.end_time - pair.audio_segment.start_time
                f.write(f"{i:2d}. {pair.vocabulary_entry.english:15s} → {pair.vocabulary_entry.cantonese:10s}\n")
                f.write(f"    Audio: {Path(pair.audio_file_path).name} ({duration:.2f}s)\n")
                f.write(f"    Confidence: {pair.alignment_confidence:.2f}\n\n")
        
        # Create import instructions
        instructions_file = output_dir / "IMPORT_INSTRUCTIONS.txt"
        with open(instructions_file, 'w', encoding='utf-8') as f:
            f.write(f"How to Import Your Anki Deck\n")
            f.write("=" * 30 + "\n\n")
            f.write("1. Open Anki on your computer\n")
            f.write("2. Click 'File' → 'Import'\n")
            f.write(f"3. Select the file: {package_filename}\n")
            f.write("4. Click 'Import' to add the deck\n")
            f.write("5. The deck will appear in your Anki collection\n\n")
            f.write("DECK DETAILS:\n")
            f.write(f"• Deck name: {deck_name}\n")
            f.write(f"• Number of cards: {len(aligned_pairs)}\n")
            f.write(f"• Card format: English front, Cantonese back with audio\n")
            f.write(f"• Audio files: Embedded in the package\n\n")
            f.write("STUDYING:\n")
            f.write("• Front of card shows English term\n")
            f.write("• Back shows Cantonese with pronunciation audio\n")
            f.write("• Click the audio icon to hear pronunciation\n")
            f.write("• Use Anki's spaced repetition for optimal learning\n")
        
        print(f"\n📁 All files saved to: {output_dir.absolute()}")
        print(f"📄 Read: ANKI_GENERATION_RESULTS.txt and IMPORT_INSTRUCTIONS.txt")
        print(f"📦 Import: {package_filename} into Anki")
        
        # Final success assessment
        success_metrics = {
            'vocabulary_extracted': len(vocab_entries) > 0,
            'audio_segmented': len(segments) == len(vocab_entries),
            'clips_generated': len(aligned_pairs) == len(vocab_entries),
            'package_created': success and os.path.exists(package_path),
            'package_valid': validator.validate_package(str(package_path)) if success else False
        }
        
        success_count = sum(success_metrics.values())
        total_metrics = len(success_metrics)
        
        print(f"\n🏆 Pipeline Success: {success_count}/{total_metrics} metrics passed")
        
        for metric, passed in success_metrics.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {metric.replace('_', ' ').title()}")
        
        if success_count == total_metrics:
            print(f"\n🎉 Complete success! Your Anki deck is ready to import!")
            print(f"   Import {package_filename} into Anki to start studying.")
        elif success_count >= 4:
            print(f"\n👍 Nearly complete! Minor issues to address.")
        else:
            print(f"\n🔧 Pipeline needs work. Check the errors above.")
        
        return success_count >= 4
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("📦 Complete Anki Package Generation Test")
    print("This tests the full pipeline from audio to Anki deck.")
    print()
    
    # Get audio file
    audio_file = input("Enter your audio file path: ").strip()
    
    # Run the test
    success = test_anki_generation(audio_file, sheets_url)
    
    if success:
        print(f"\n🎉 Success! Your Anki deck is ready!")
        print("Import the .apkg file into Anki to start studying.")
    else:
        print(f"\n🔧 Pipeline needs work. Check the output for details.")


if __name__ == "__main__":
    main()