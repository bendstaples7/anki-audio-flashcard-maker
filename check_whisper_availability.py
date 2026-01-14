#!/usr/bin/env python3
"""
Check if Whisper is available for speech verification.
"""

import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

def check_whisper():
    """Check Whisper availability and provide installation instructions."""
    print("🔍 CHECKING WHISPER AVAILABILITY")
    print("=" * 50)
    
    try:
        import whisper
        print("✅ Whisper is available!")
        
        # Check available models
        available_models = whisper.available_models()
        print(f"📦 Available models: {', '.join(available_models)}")
        
        # Test loading a small model
        try:
            print("🧪 Testing model loading...")
            model = whisper.load_model("tiny")
            print("✅ Model loading successful!")
            print("🎯 Speech verification should work properly")
            
        except Exception as e:
            print(f"⚠️  Model loading failed: {e}")
            print("💡 This might be a temporary issue - speech verification may still work")
            
    except ImportError:
        print("❌ Whisper is NOT available")
        print("\n🔧 INSTALLATION INSTRUCTIONS:")
        print("=" * 50)
        print("To enable speech verification, install Whisper:")
        print()
        print("Option 1 - Standard installation:")
        print("  pip install openai-whisper")
        print()
        print("Option 2 - With additional dependencies:")
        print("  pip install openai-whisper[dev]")
        print()
        print("Option 3 - If you have conda:")
        print("  conda install -c conda-forge openai-whisper")
        print()
        print("📋 Model sizes and download requirements:")
        print("  • tiny   (~39 MB)   - Fastest, least accurate")
        print("  • base   (~142 MB)  - Good balance (recommended)")
        print("  • small  (~244 MB)  - Better accuracy")
        print("  • medium (~769 MB)  - High accuracy")
        print("  • large  (~1550 MB) - Best accuracy, slowest")
        print()
        print("💡 The first time you use speech verification, Whisper will")
        print("   download the selected model automatically.")
        print()
        print("🎯 After installation, speech verification will:")
        print("  • Automatically detect alignment issues")
        print("  • Test multiple offsets to find the best alignment")
        print("  • Provide confidence scores for each vocabulary term")
        print("  • Help fix issues like 'di fa' getting wrong audio")
        
    # Check the current GUI setting
    try:
        from cantonese_anki_generator.audio.speech_verification import WHISPER_AVAILABLE
        print(f"\n🔧 Current system status:")
        print(f"   WHISPER_AVAILABLE = {WHISPER_AVAILABLE}")
        
        if WHISPER_AVAILABLE:
            print("   ✅ Speech verification is ready to use")
        else:
            print("   ❌ Speech verification is disabled")
            print("   💡 Install Whisper to enable automatic alignment correction")
            
    except ImportError as e:
        print(f"\n⚠️  Could not check system status: {e}")


if __name__ == "__main__":
    check_whisper()