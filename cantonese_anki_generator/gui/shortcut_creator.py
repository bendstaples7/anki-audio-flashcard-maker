#!/usr/bin/env python3
"""
Desktop shortcut creation utility for Cantonese Anki Generator GUI.

This module provides functionality to create desktop shortcuts for easy access
to the GUI application.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional


class ShortcutCreator:
    """Creates desktop shortcuts for the Cantonese Anki Generator GUI."""
    
    def __init__(self):
        """Initialize the shortcut creator."""
        self.system = platform.system()
        self.desktop_path = self._get_desktop_path()
        
    def _get_desktop_path(self) -> Optional[Path]:
        """Get the desktop directory path for the current system."""
        try:
            if self.system == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                    desktop = winreg.QueryValueEx(key, "Desktop")[0]
                    return Path(desktop)
            elif self.system == "Darwin":  # macOS
                return Path.home() / "Desktop"
            else:  # Linux and other Unix-like systems
                # Try XDG first, then fallback to ~/Desktop
                xdg_desktop = os.environ.get("XDG_DESKTOP_DIR")
                if xdg_desktop:
                    return Path(xdg_desktop)
                return Path.home() / "Desktop"
        except Exception:
            # Fallback to home directory if desktop can't be found
            return Path.home()
    
    def create_shortcut(self, name: str = "Cantonese Anki Generator") -> bool:
        """
        Create a desktop shortcut for the GUI application.
        
        Args:
            name: Name for the shortcut
            
        Returns:
            True if shortcut was created successfully, False otherwise
        """
        if not self.desktop_path or not self.desktop_path.exists():
            print(f"❌ Desktop directory not found: {self.desktop_path}")
            return False
            
        try:
            if self.system == "Windows":
                return self._create_windows_shortcut(name)
            elif self.system == "Darwin":
                return self._create_macos_shortcut(name)
            else:
                return self._create_linux_shortcut(name)
        except Exception as e:
            print(f"❌ Error creating shortcut: {e}")
            return False
    
    def _create_windows_shortcut(self, name: str) -> bool:
        """Create a Windows .lnk shortcut."""
        try:
            import win32com.client
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut_path = self.desktop_path / f"{name}.lnk"
            shortcut = shell.CreateShortCut(str(shortcut_path))
            
            # Set shortcut properties
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'-m cantonese_anki_generator --gui'
            shortcut.WorkingDirectory = str(Path.cwd())
            shortcut.Description = "Cantonese Anki Generator - GUI Mode"
            
            # Try to set icon if available
            icon_path = Path(__file__).parent / "icon.ico"
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
            
            shortcut.save()
            print(f"✅ Windows shortcut created: {shortcut_path}")
            return True
            
        except ImportError:
            print("❌ Windows shortcut creation requires pywin32 package")
            return False
        except Exception as e:
            print(f"❌ Failed to create Windows shortcut: {e}")
            return False
    
    def _create_macos_shortcut(self, name: str) -> bool:
        """Create a macOS application alias."""
        try:
            # Create a simple shell script that launches the GUI
            script_path = self.desktop_path / f"{name}.command"
            
            script_content = f"""#!/bin/bash
cd "{Path.cwd()}"
{sys.executable} -m cantonese_anki_generator --gui
"""
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make the script executable
            os.chmod(script_path, 0o755)
            
            print(f"✅ macOS shortcut created: {script_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create macOS shortcut: {e}")
            return False
    
    def _create_linux_shortcut(self, name: str) -> bool:
        """Create a Linux .desktop file."""
        try:
            desktop_file_path = self.desktop_path / f"{name}.desktop"
            
            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={name}
Comment=Generate Anki flashcards from Google Docs and audio files
Exec={sys.executable} -m cantonese_anki_generator --gui
Path={Path.cwd()}
Terminal=false
Categories=Education;Languages;
StartupNotify=true
"""
            
            # Try to add icon if available
            icon_path = Path(__file__).parent / "icon.png"
            if icon_path.exists():
                desktop_content += f"Icon={icon_path}\n"
            
            with open(desktop_file_path, 'w') as f:
                f.write(desktop_content)
            
            # Make the desktop file executable
            os.chmod(desktop_file_path, 0o755)
            
            print(f"✅ Linux shortcut created: {desktop_file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create Linux shortcut: {e}")
            return False


def create_desktop_shortcut(name: str = "Cantonese Anki Generator") -> bool:
    """
    Convenience function to create a desktop shortcut.
    
    Args:
        name: Name for the shortcut
        
    Returns:
        True if shortcut was created successfully, False otherwise
    """
    creator = ShortcutCreator()
    return creator.create_shortcut(name)


def main():
    """Main function for running the shortcut creator as a script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create desktop shortcut for Cantonese Anki Generator GUI"
    )
    parser.add_argument(
        "--name", 
        default="Cantonese Anki Generator",
        help="Name for the desktop shortcut"
    )
    
    args = parser.parse_args()
    
    print("Creating desktop shortcut for Cantonese Anki Generator GUI...")
    
    if create_desktop_shortcut(args.name):
        print("✅ Desktop shortcut created successfully!")
        print("You can now launch the GUI by double-clicking the shortcut on your desktop.")
    else:
        print("❌ Failed to create desktop shortcut.")
        print("You can still launch the GUI using:")
        print(f"  {sys.executable} -m cantonese_anki_generator --gui")


if __name__ == "__main__":
    main()