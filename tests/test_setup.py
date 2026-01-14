#!/usr/bin/env python3
"""
Simple setup verification script.
"""

import sys
import importlib.util

def test_imports():
    """Test that our core modules can be imported."""
    try:
        # Test importing our models
        spec = importlib.util.spec_from_file_location(
            "models", 
            "cantonese_anki_generator/models.py"
        )
        models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models)
        
        # Test that our classes exist
        assert hasattr(models, 'VocabularyEntry')
        assert hasattr(models, 'AudioSegment')
        assert hasattr(models, 'AlignedPair')
        assert hasattr(models, 'AnkiCard')
        
        print("✓ Core data models imported successfully")
        
        # Test creating instances
        vocab_entry = models.VocabularyEntry("hello", "你好", 1)
        assert vocab_entry.english == "hello"
        assert vocab_entry.cantonese == "你好"
        assert vocab_entry.row_index == 1
        assert vocab_entry.confidence == 1.0
        
        print("✓ VocabularyEntry creation works")
        
        # Test config import
        spec = importlib.util.spec_from_file_location(
            "config", 
            "cantonese_anki_generator/config.py"
        )
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        
        assert hasattr(config, 'Config')
        print("✓ Configuration module imported successfully")
        
        
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        assert False, f"Import test failed: {e}"

def test_project_structure():
    """Test that all required directories and files exist."""
    import os
    
    required_dirs = [
        "cantonese_anki_generator",
        "cantonese_anki_generator/processors",
        "cantonese_anki_generator/audio", 
        "cantonese_anki_generator/alignment",
        "cantonese_anki_generator/anki",
        "tests"
    ]
    
    required_files = [
        "cantonese_anki_generator/__init__.py",
        "cantonese_anki_generator/models.py",
        "cantonese_anki_generator/config.py",
        "cantonese_anki_generator/main.py",
        "requirements.txt",
        "setup.py",
        "pytest.ini",
        "README.md"
    ]
    
    for directory in required_dirs:
        if not os.path.isdir(directory):
            print(f"✗ Missing directory: {directory}")
            assert False, f"Missing directory: {directory}"
    
    for file_path in required_files:
        if not os.path.isfile(file_path):
            print(f"✗ Missing file: {file_path}")
            assert False, f"Missing file: {file_path}"
    
    print("✓ All required directories and files exist")

if __name__ == "__main__":
    print("Testing Cantonese Anki Generator setup...")
    
    structure_ok = test_project_structure()
    imports_ok = test_imports()
    
    if structure_ok and imports_ok:
        print("\n🎉 Project setup completed successfully!")
        print("✓ Directory structure created")
        print("✓ Core data models defined")
        print("✓ Configuration system set up")
        print("✓ Testing framework initialized")
        print("✓ Dependencies specified in requirements.txt")
        sys.exit(0)
    else:
        print("\n❌ Setup verification failed")
        sys.exit(1)