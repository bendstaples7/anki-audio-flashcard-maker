"""Desktop shortcut creation for the web interface."""

import os
import shlex
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
        """Create a Windows .lnk shortcut that auto-updates from GitHub."""
        try:
            import win32com.client
            
            project_dir = Path.cwd()
            launch_bat = project_dir / "launch.bat"
            
            if not launch_bat.exists():
                print(f"❌ launch.bat not found in {project_dir}")
                print("   Run from the project root directory to create the shortcut.")
                return False
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut_path = self.desktop_path / f"{name}.lnk"
            shortcut = shell.CreateShortCut(str(shortcut_path))
            
            # Point to launch.bat which auto-updates from GitHub before starting
            shortcut.Targetpath = str(launch_bat)
            shortcut.WorkingDirectory = str(project_dir)
            shortcut.Description = "Cantonese Anki Generator - Auto-updates from GitHub"
            
            shortcut.save()
            print(f"✅ Windows shortcut created: {shortcut_path}")
            print(f"   Points to: {launch_bat}")
            print("   Will auto-update from GitHub main branch on each launch.")
            return True
            
        except ImportError:
            print("❌ Windows shortcut creation requires pywin32 package")
            return False
        except Exception as e:
            print(f"❌ Failed to create Windows shortcut: {e}")
            return False
    
    def _get_update_script_content(self, quoted_cwd: str, quoted_executable: str) -> str:
        """Return the bash auto-update launcher script body.

        Used by both macOS and Linux shortcut creators so the update
        logic is maintained in a single place.
        """
        return f"""#!/bin/bash
cd {quoted_cwd}

echo "============================================================"
echo "  Cantonese Anki Generator - Auto-Update Launcher"
echo "============================================================"
echo ""

if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null; then
    echo "Checking for updates from GitHub..."
    if ! git fetch origin main 2>/dev/null; then
        echo "WARNING: Could not reach GitHub. Launching with current version."
        echo ""
    else
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        if [ "$CURRENT_BRANCH" != "main" ]; then
            echo "Switching to main branch..."
            if ! git checkout main 2>/dev/null; then
                echo "WARNING: Could not switch to main. Launching with current version."
            fi
        fi
        # Confirm we're on main before pulling
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        if [ "$CURRENT_BRANCH" = "main" ]; then
            LOCAL=$(git rev-parse HEAD)
            REMOTE=$(git rev-parse origin/main)
            if [ "$LOCAL" != "$REMOTE" ]; then
                echo "Pulling latest changes..."
                git pull origin main
                echo "Checking dependencies..."
                {quoted_executable} -m pip install -r requirements.txt -q 2>/dev/null
                {quoted_executable} -m pip install -e . -q 2>/dev/null
                echo "Updated successfully."
            else
                echo "Already up to date."
            fi
        else
            echo "WARNING: Not on main branch. Launching with current version."
        fi
    fi
    echo ""
else
    echo "WARNING: git not available. Launching with current version."
    echo ""
fi

echo "Starting Cantonese Anki Generator..."
echo "============================================================"
echo ""
{quoted_executable} -m cantonese_anki_generator.web.run
"""

    def _create_macos_shortcut(self, name: str) -> bool:
        """Create a macOS application alias that auto-updates from GitHub."""
        try:
            script_path = self.desktop_path / f"{name}.command"
            
            quoted_cwd = shlex.quote(str(Path.cwd()))
            quoted_executable = shlex.quote(sys.executable)
            
            script_content = self._get_update_script_content(quoted_cwd, quoted_executable)
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            os.chmod(script_path, 0o755)
            
            print(f"✅ macOS shortcut created: {script_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create macOS shortcut: {e}")
            return False
    
    def _create_linux_shortcut(self, name: str) -> bool:
        """Create a Linux .desktop file with auto-update wrapper."""
        try:
            # Create a launcher script with auto-update logic
            project_dir = Path.cwd()
            launcher_path = project_dir / "launch.sh"
            
            quoted_executable = shlex.quote(sys.executable)
            quoted_cwd = shlex.quote(str(project_dir))
            
            launcher_content = self._get_update_script_content(quoted_cwd, quoted_executable)
            
            with open(launcher_path, 'w') as f:
                f.write(launcher_content)
            
            os.chmod(launcher_path, 0o755)
            
            # Create .desktop file pointing to the launcher script
            desktop_file_path = self.desktop_path / f"{name}.desktop"
            quoted_launcher = shlex.quote(str(launcher_path))
            
            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={name}
Comment=Web interface for manual audio alignment (auto-updates from GitHub)
Exec={quoted_launcher}
Path={quoted_cwd}
Terminal=true
Categories=Education;Languages;
StartupNotify=true
"""
            
            with open(desktop_file_path, 'w') as f:
                f.write(desktop_content)
            
            os.chmod(desktop_file_path, 0o755)
            
            print(f"✅ Linux shortcut created: {desktop_file_path}")
            print(f"   Launcher script: {launcher_path}")
            print("   Will auto-update from GitHub main branch on each launch.")
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
