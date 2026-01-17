"""Desktop shortcut creation for the web interface."""

import os
import sys
import platform
from pathlib import Path
from typing import Optional


class WebShortcutCreator:
    """Creates desktop shortcuts for the web interface."""
    
    def __init__(self):
        self.system = platform.system()
        self.desktop_path = self._get_desktop_path()
        
    def _get_desktop_path(self) -> Optional[Path]:
        """Get the desktop directory path."""
        try:
            if self.system == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                    desktop = winreg.QueryValueEx(key, "Desktop")[0]
                    return Path(desktop)
            elif self.system == "Darwin":
                return Path.home() / "Desktop"
            else:
                xdg_desktop = os.environ.get("XDG_DESKTOP_DIR")
                if xdg_desktop:
                    return Path(xdg_desktop)
                return Path.home() / "Desktop"
        except Exception:
            return Path.home()
    
    def create_shortcut(self, name: str = "Cantonese Anki Generator (Web)") -> bool:
        """Create a desktop shortcut for the web interface."""
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
            shortcut.Arguments = f'-m cantonese_anki_generator.web.run'
            shortcut.WorkingDirectory = str(Path.cwd())
            shortcut.Description = "Cantonese Anki Generator - Web Interface with Manual Alignment"
            
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
            script_path = self.desktop_path / f"{name}.command"
            
            script_content = f"""#!/bin/bash
cd "{Path.cwd()}"
{sys.executable} -m cantonese_anki_generator.web.run
"""
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
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
Comment=Web interface for manual audio alignment
Exec={sys.executable} -m cantonese_anki_generator.web.run
Path={Path.cwd()}
Terminal=true
Categories=Education;Languages;
StartupNotify=true
"""
            
            with open(desktop_file_path, 'w') as f:
                f.write(desktop_content)
            
            os.chmod(desktop_file_path, 0o755)
            
            print(f"✅ Linux shortcut created: {desktop_file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create Linux shortcut: {e}")
            return False


def main():
    """Main function for creating web interface shortcut."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create desktop shortcut for Cantonese Anki Generator Web Interface"
    )
    parser.add_argument(
        "--name", 
        default="Cantonese Anki Generator (Web)",
        help="Name for the desktop shortcut"
    )
    
    args = parser.parse_args()
    
    print("Creating desktop shortcut for web interface...")
    
    creator = WebShortcutCreator()
    if creator.create_shortcut(args.name):
        print("✅ Desktop shortcut created successfully!")
        print("Double-click the shortcut to launch the web interface.")
        print("Your browser will need to navigate to http://localhost:3000")
    else:
        print("❌ Failed to create desktop shortcut.")
        print("You can still launch the web interface using:")
        print(f"  {sys.executable} -m cantonese_anki_generator.web.run")


if __name__ == "__main__":
    main()
