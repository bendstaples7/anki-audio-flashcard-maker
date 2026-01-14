#!/usr/bin/env python3
"""
Basic GUI functionality test.
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_gui_import():
    """Test that GUI components can be imported."""
    try:
        from cantonese_anki_generator.gui import CantoneseAnkiGeneratorGUI
        from cantonese_anki_generator.gui.shortcut_creator import ShortcutCreator
        
        print("✓ GUI components imported successfully")
        
        # Test GUI class instantiation (without running)
        # We can't actually run the GUI in a test environment, but we can test initialization
        gui = CantoneseAnkiGeneratorGUI()
        assert gui is not None
        
        print("✓ GUI class instantiation successful")
        
        # Test shortcut creator
        creator = ShortcutCreator()
        assert creator is not None
        
        print("✓ ShortcutCreator instantiation successful")
        
    except Exception as e:
        print(f"✗ GUI test failed: {e}")
        assert False, f"GUI test failed: {e}"


if __name__ == "__main__":
    test_gui_import()
    print("🎉 GUI basic tests passed!")