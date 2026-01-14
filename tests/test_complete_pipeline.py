#!/usr/bin/env python3
"""
Complete pipeline test using the main module.

This demonstrates the full end-to-end functionality from Google Sheets
and audio file to a complete Anki package.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.main import process_pipeline


def test_complete_pipeline():
    """Test the complete pipeline using real data."""
    
    # Get Google Sheets URL from user
    sheets_url = input("Enter your Google Sheets URL: ").strip()
    
    print("🚀 Complete Pipeline Test")
    print("=" * 30)
    print("This tests the full pipeline from the main module.")
    print()
    
    # Get audio file from user
    audio_file = input("Enter your audio file path: ").strip().strip('"').strip("'")
    
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        return False
    
    # Create output path
    from cantonese_anki_generator.config import Config
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Config.OUTPUT_DIR / f"cantonese_vocab_pipeline_{timestamp}.apkg"
    
    print(f"📋 Google Sheets: {sheets_url}")
    print(f"🔊 Audio file: {audio_file}")
    print(f"📦 Output package: {output_path}")
    print()
    
    # Run the pipeline
    print("🔄 Running complete pipeline...")
    success = process_pipeline(
        google_doc_url=sheets_url,
        audio_file=Path(audio_file),
        output_path=output_path,
        verbose=True
    )
    
    if success:
        print()
        print("🎉 Pipeline completed successfully!")
        print(f"📦 Your Anki deck is ready: {output_path}")
        print()
        print("📋 To use your deck:")
        print("1. Open Anki on your computer")
        print("2. Click 'File' → 'Import'")
        print(f"3. Select the file: {output_path}")
        print("4. Click 'Import' to add the deck")
        print("5. Start studying your Cantonese vocabulary!")
        
        # Show file info
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"\n📊 Package info:")
            print(f"   Size: {file_size:,} bytes")
            print(f"   Location: {output_path.absolute()}")
        
        return True
    else:
        print()
        print("❌ Pipeline failed. Check the logs above for details.")
        return False


def main():
    """Main function."""
    success = test_complete_pipeline()
    
    if success:
        print("\n✨ Test completed successfully!")
        print("Your Anki deck is ready to import and use.")
    else:
        print("\n🔧 Test failed. Please check the error messages above.")
    
    return success


if __name__ == "__main__":
    main()