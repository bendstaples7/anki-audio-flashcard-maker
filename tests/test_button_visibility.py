#!/usr/bin/env python3
"""
Test if the Generate Anki Deck button is visible and working.
"""

import tkinter as tk
from cantonese_anki_generator.gui.main_window import CantoneseAnkiGeneratorGUI

def test_button_visibility():
    """Test button visibility and properties."""
    print("🔍 Testing Button Visibility")
    print("=" * 40)
    
    # Create GUI
    app = CantoneseAnkiGeneratorGUI()
    
    # Set up valid inputs
    test_url = 'https://docs.google.com/spreadsheets/d/1yDO-ZYBiI1jUGLoouDX45LJ97hFBmv2q9Zcd8Kjh-HU/edit?gid=0#gid=0'
    test_audio = r'G:\My Drive\Language Learning\iTalki\Zack\Dec 20 Ben S.m4a'
    
    app.url_var.set(test_url)
    app.audio_var.set(test_audio)
    app._update_process_button_state()
    
    # Check button properties
    print(f"Button exists: {hasattr(app, 'process_btn')}")
    print(f"Button text: '{app.process_btn['text']}'")
    print(f"Button state: {app.process_btn['state']}")
    print(f"Button command: {app.process_btn['command']}")
    
    # Check if button is in the widget hierarchy
    print(f"Button parent: {app.process_btn.master}")
    print(f"Button frame exists: {hasattr(app, 'button_frame')}")
    
    # Check grid info
    try:
        grid_info = app.process_btn.grid_info()
        print(f"Button grid info: {grid_info}")
    except Exception as e:
        print(f"Button grid error: {e}")
    
    try:
        frame_grid_info = app.button_frame.grid_info()
        print(f"Button frame grid info: {frame_grid_info}")
    except Exception as e:
        print(f"Button frame grid error: {e}")
    
    # Test if we can simulate a click
    def test_click():
        print("🎯 Button clicked successfully!")
        return True
    
    # Temporarily replace the command to test
    original_command = app.process_btn['command']
    app.process_btn.config(command=test_click)
    
    print(f"\n🧪 Testing button click simulation...")
    try:
        app.process_btn.invoke()
        print("✅ Button click simulation worked!")
    except Exception as e:
        print(f"❌ Button click failed: {e}")
    
    # Restore original command
    app.process_btn.config(command=original_command)
    
    # Show the window briefly to see if it's visible
    print(f"\n👁️ Showing window for 3 seconds...")
    app.root.after(3000, app.root.quit)  # Close after 3 seconds
    
    try:
        app.root.mainloop()
        print("✅ Window displayed successfully")
    except Exception as e:
        print(f"❌ Window display failed: {e}")

if __name__ == "__main__":
    test_button_visibility()