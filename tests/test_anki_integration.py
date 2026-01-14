#!/usr/bin/env python3
"""
Simple integration test for Anki package generation.

Tests the Anki module components without requiring real audio files.
"""

import os
import sys
import tempfile
from pathlib import Path
import numpy as np

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment, AlignedPair
from cantonese_anki_generator.anki import (
    CantoneseCardTemplate, 
    CardFormatter, 
    AnkiPackageGenerator,
    UniqueNamingManager,
    PackageValidator
)


def create_test_data():
    """Create test vocabulary and audio data."""
    
    # Create test vocabulary entries
    vocab_entries = [
        VocabularyEntry(english="hello", cantonese="你好", row_index=1, confidence=1.0),
        VocabularyEntry(english="thank you", cantonese="多謝", row_index=2, confidence=1.0),
        VocabularyEntry(english="goodbye", cantonese="再見", row_index=3, confidence=1.0),
    ]
    
    # Create test audio segments (synthetic audio)
    sample_rate = 22050
    duration = 1.0  # 1 second per segment
    
    audio_segments = []
    for i, vocab in enumerate(vocab_entries):
        # Generate simple sine wave as test audio
        t = np.linspace(0, duration, int(sample_rate * duration))
        frequency = 440 + (i * 100)  # Different frequency for each segment
        audio_data = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        segment = AudioSegment(
            start_time=i * duration,
            end_time=(i + 1) * duration,
            audio_data=audio_data,
            confidence=0.9,
            segment_id=f"test_{i+1:03d}"
        )
        
        audio_segments.append(segment)
    
    return vocab_entries, audio_segments


def test_card_template():
    """Test Anki card template creation."""
    print("🧪 Testing card template...")
    
    try:
        # Create model
        model = CantoneseCardTemplate.create_model()
        
        # Verify model properties
        assert model.model_id == CantoneseCardTemplate.MODEL_ID
        assert model.name == 'Cantonese Vocabulary'
        assert len(model.fields) == 4
        assert len(model.templates) == 1
        
        # Check field names
        field_names = [field['name'] for field in model.fields]
        expected_fields = ['English', 'Cantonese', 'Audio', 'Tags']
        assert field_names == expected_fields
        
        print("   ✅ Card template creation successful")
        
    except Exception as e:
        print(f"   ❌ Card template test failed: {e}")
        assert False, f"Card template test failed: {e}"


def test_card_formatter():
    """Test card field formatting."""
    print("🧪 Testing card formatter...")
    
    try:
        formatter = CardFormatter()
        
        # Test field formatting
        fields = formatter.format_card_fields(
            english="hello",
            cantonese="你好", 
            audio_filename="hello_001.wav",
            tags=['test', 'cantonese']
        )
        
        # Verify fields
        assert fields['English'] == 'hello'
        assert fields['Cantonese'] == '你好'
        assert fields['Audio'] == '[sound:hello_001.wav]'
        assert fields['Tags'] == 'test cantonese'
        
        # Test filename generation
        filename = formatter.generate_audio_filename("hello", "你好", 1)
        assert filename == "hello_001.wav"
        
        # Test sanitization
        sanitized = formatter.sanitize_filename("hello/world?")
        assert '/' not in sanitized and '?' not in sanitized
        
        print("   ✅ Card formatter tests successful")
        
    except Exception as e:
        print(f"   ❌ Card formatter test failed: {e}")
        assert False, f"Card formatter test failed: {e}"


def test_unique_naming():
    """Test unique naming functionality."""
    print("🧪 Testing unique naming...")
    
    try:
        naming_manager = UniqueNamingManager()
        
        # Test deck name generation
        deck_name1 = naming_manager.generate_unique_deck_name("Test Deck")
        deck_name2 = naming_manager.generate_unique_deck_name("Test Deck")
        
        # Should be different due to uniqueness
        assert deck_name1 != deck_name2
        
        # Test ID generation
        id1 = naming_manager.generate_unique_deck_id("Test Deck 1")
        id2 = naming_manager.generate_unique_deck_id("Test Deck 2")
        
        # Should be different
        assert id1 != id2
        
        # Test filename generation
        with tempfile.TemporaryDirectory() as temp_dir:
            filename1 = naming_manager.generate_unique_package_filename("test", temp_dir)
            
            # Create the file to test conflict detection
            (Path(temp_dir) / filename1).touch()
            
            filename2 = naming_manager.generate_unique_package_filename("test", temp_dir)
            
            # Should be different due to conflict
            assert filename1 != filename2
        
        print("   ✅ Unique naming tests successful")
        
    except Exception as e:
        print(f"   ❌ Unique naming test failed: {e}")
        assert False, f"Unique naming test failed: {e}"


def test_package_generation():
    """Test Anki package generation."""
    print("🧪 Testing package generation...")
    
    try:
        # Create test data
        vocab_entries, audio_segments = create_test_data()
        
        # Create aligned pairs with temporary audio files
        aligned_pairs = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for i, (vocab, segment) in enumerate(zip(vocab_entries, audio_segments)):
                # Save test audio file
                audio_filename = f"test_audio_{i+1:03d}.wav"
                audio_path = temp_path / audio_filename
                
                # Save using scipy
                import scipy.io.wavfile as wavfile
                audio_normalized = (segment.audio_data * 32767).astype('int16')
                wavfile.write(str(audio_path), 22050, audio_normalized)
                
                # Create aligned pair
                aligned_pair = AlignedPair(
                    vocabulary_entry=vocab,
                    audio_segment=segment,
                    alignment_confidence=0.9,
                    audio_file_path=str(audio_path)
                )
                aligned_pairs.append(aligned_pair)
            
            # Generate package
            generator = AnkiPackageGenerator()
            package_path = temp_path / "test_package.apkg"
            
            success = generator.generate_package(
                aligned_pairs=aligned_pairs,
                output_path=str(package_path),
                deck_name="Test Cantonese Deck"
            )
            
            assert success, "Package generation failed"
            assert package_path.exists(), "Package file not created"
            
            # Validate package
            validator = PackageValidator()
            is_valid = validator.validate_package(str(package_path))
            assert is_valid, "Package validation failed"
            
            # Check package info
            info = validator.get_package_info(str(package_path))
            assert info['exists'], "Package info shows file doesn't exist"
            assert info['size_bytes'] > 0, "Package file is empty"
            assert info['valid'], "Package info shows invalid package"
        
        print("   ✅ Package generation tests successful")
        
    except Exception as e:
        print(f"   ❌ Package generation test failed: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"Package generation test failed: {e}"


def main():
    """Run all integration tests."""
    print("🧪 Anki Integration Tests")
    print("=" * 30)
    
    tests = [
        test_card_template,
        test_card_formatter,
        test_unique_naming,
        test_package_generation
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
        print()
    
    print(f"🏆 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! Anki module is working correctly.")
        return True
    else:
        print("🔧 Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)