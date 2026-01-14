#!/usr/bin/env python3
"""
Simple launcher script for the Cantonese Anki Generator GUI.

This can be used as a standalone entry point for the GUI application.
"""

import sys
import argparse
from pathlib import Path

# Add the parent directory to the path so we can import the main package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from cantonese_anki_generator.gui import CantoneseAnkiGeneratorGUI
    from cantonese_anki_generator.gui.shortcut_creator import create_desktop_shortcut
    
    def main():
        """Launch the GUI application with optional shortcut creation."""
        parser = argparse.ArgumentParser(
            description="Launch Cantonese Anki Generator GUI"
        )
        parser.add_argument(
            "--create-shortcut",
            action="store_true",
            help="Create a desktop shortcut for easy access"
        )
        parser.add_argument(
            "--shortcut-name",
            default="Cantonese Anki Generator",
            help="Name for the desktop shortcut"
        )
        
        args = parser.parse_args()
        
        # Create desktop shortcut if requested
        if args.create_shortcut:
            print("Creating desktop shortcut...")
            if create_desktop_shortcut(args.shortcut_name):
                print("✅ Desktop shortcut created successfully!")
            else:
                print("❌ Failed to create desktop shortcut.")
            return
        
        # Launch the GUI application
        app = CantoneseAnkiGeneratorGUI()
        app.run()
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error importing GUI components: {e}")
    print("Make sure you're running this from the correct directory.")
    sys.exit(1)
except Exception as e:
    print(f"Error launching GUI: {e}")
    sys.exit(1)