"""
Main GUI window for Cantonese Anki Generator.

Provides a desktop interface using Tkinter for vocabulary processing.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import threading
import os
import time
import logging
import shutil

# Add FFmpeg to PATH if available (for M4A support)
def _ensure_ffmpeg_available():
    """Ensure FFmpeg is available in PATH for M4A support."""
    # Check if already available
    if shutil.which('ffmpeg'):
        return True
    
    # Try to find FFmpeg in common Windows installation locations
    possible_paths = [
        # WinGet installation path
        Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
        # Chocolatey path  
        Path("C:/ProgramData/chocolatey/bin"),
        # Manual installation paths
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
    ]
    
    for base_path in possible_paths:
        if base_path.exists():
            # Look for FFmpeg in WinGet packages
            if "WinGet" in str(base_path):
                for pkg_dir in base_path.glob("*ffmpeg*"):
                    ffmpeg_bins = list(pkg_dir.glob("ffmpeg-*/bin"))
                    if ffmpeg_bins:
                        ffmpeg_bin = ffmpeg_bins[0]
                        if (ffmpeg_bin / "ffmpeg.exe").exists():
                            # Add to PATH for this session
                            current_path = os.environ.get("PATH", "")
                            if str(ffmpeg_bin) not in current_path:
                                os.environ["PATH"] += f";{ffmpeg_bin}"
                            return True
            else:
                # Direct path check
                if (base_path / "ffmpeg.exe").exists():
                    current_path = os.environ.get("PATH", "")
                    if str(base_path) not in current_path:
                        os.environ["PATH"] += f";{base_path}"
                    return True
    
    return False

# Configure FFmpeg for M4A support
_ensure_ffmpeg_available()

# Import the naming manager for unique filename generation
from ..anki.naming import UniqueNamingManager
# Import error handling system
from ..errors import ErrorHandler, ProcessingError, ErrorCategory, ErrorSeverity


@dataclass
class ApplicationState:
    """Manages the current state of the GUI application."""
    google_docs_url: str = ""
    audio_file_path: str = ""
    output_directory: str = ""
    is_processing: bool = False
    current_stage: str = ""
    progress_percentage: float = 0.0
    
    # Enhanced progress tracking
    processing_start_time: Optional[float] = None
    estimated_total_time: Optional[float] = None
    current_stage_name: str = ""
    items_completed: int = 0
    total_items: int = 0


class CantoneseAnkiGeneratorGUI:
    """
    Main GUI application for Cantonese Anki Generator.
    
    Provides a user-friendly desktop interface for converting Google Docs
    vocabulary tables and audio files into Anki flashcard decks.
    """
    
    def __init__(self):
        """Initialize the GUI application."""
        self.root = tk.Tk()
        self.state = ApplicationState()
        self.logger = logging.getLogger(__name__)
        
        # Initialize error handler for comprehensive error management
        self.error_handler = ErrorHandler()
        
        # Initialize retry mechanism
        self._current_retry_count = 0
        self._max_retries = 3
        
        # Initialize naming manager for unique filename generation
        self.naming_manager = UniqueNamingManager()
        
        # Progress callback system
        self.progress_callback_queue = []
        self.processing_thread = None
        
        # Store last processing results for reference
        self._last_result_data = None
        
        # Configure main window
        self._setup_window()
        
        # Initialize UI components
        self._create_widgets()
        self._setup_layout()
        self._configure_styles()
        
        # Set default output directory to Downloads folder
        downloads_dir = Path.home() / "Downloads"
        if downloads_dir.exists() and downloads_dir.is_dir():
            self.state.output_directory = str(downloads_dir)
        else:
            # Fallback to current directory if Downloads doesn't exist
            self.state.output_directory = str(Path.cwd() / "output")
        self._ensure_output_directory_exists()
        
        # Start progress update polling
        self._start_progress_polling()
        
    def _setup_window(self):
        """Configure the main window properties."""
        self.root.title("Cantonese Anki Generator")
        
        # Set appropriate window size and positioning
        self.root.geometry("800x700")  # Increased from 700x600
        self.root.minsize(700, 600)    # Increased minimum size
        self.root.maxsize(1200, 900)   # Prevent window from becoming too large
        
        # Add scroll indicator
        self._add_scroll_indicator()
        
        # Set application icon if available
        self._set_application_icon()
        
        # Create menu bar
        self._create_menu_bar()
        
        # Center the window on screen
        self._center_window()
        
        # Configure window behavior and cleanup
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Make window resizable but maintain aspect ratio
        self.root.resizable(True, True)
        
        # Set window state to normal (not minimized or maximized)
        self.root.state('normal')
        
    def _set_application_icon(self):
        """Set the application icon if available."""
        try:
            # Try to set icon from common locations
            icon_paths = [
                Path(__file__).parent / "icon.ico",
                Path(__file__).parent / "icon.png", 
                Path(__file__).parent.parent / "icon.ico",
                Path(__file__).parent.parent / "icon.png"
            ]
            
            for icon_path in icon_paths:
                if icon_path.exists():
                    if icon_path.suffix.lower() == '.ico':
                        self.root.iconbitmap(str(icon_path))
                    else:
                        # For PNG files, we'd need to convert to PhotoImage
                        # For now, just log that we found an icon
                        self.logger.debug(f"Found icon file: {icon_path}")
                    break
            else:
                # No icon file found, use default
                self.logger.debug("No application icon found, using system default")
                
        except Exception as e:
            # Icon setting failed, continue without icon
            self.logger.debug(f"Could not set application icon: {e}")
            
    def _center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        
        # Get window dimensions
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate position to center the window
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        # Ensure window doesn't go off-screen
        x = max(0, min(x, screen_width - width))
        y = max(0, min(y, screen_height - height))
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
    def _create_menu_bar(self):
        """Create the application menu bar with help options."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        help_menu.add_command(label="Getting Started", command=self._show_getting_started_help)
        help_menu.add_command(label="Document Format Guide", command=self._show_document_format_help)
        help_menu.add_command(label="Audio Recording Tips", command=self._show_audio_recording_help)
        help_menu.add_separator()
        help_menu.add_command(label="Troubleshooting", command=self._show_troubleshooting_help)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_keyboard_shortcuts_help)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about_dialog)
        
    def _create_widgets(self):
        """Create all GUI widgets with scrolling capability."""
        # Create main canvas and scrollbar for scrolling
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        
        # Create scrollable frame inside canvas
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        self.canvas_frame_id = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Main container with padding (now inside scrollable frame)
        self.main_frame = ttk.Frame(self.scrollable_frame, padding="20")
        
        # Title section
        self.title_label = ttk.Label(
            self.main_frame,
            text="Cantonese Anki Generator",
            font=("Arial", 16, "bold")
        )
        
        self.subtitle_label = ttk.Label(
            self.main_frame,
            text="Convert vocabulary tables and audio into Anki flashcards",
            font=("Arial", 10)
        )
        
        # Step-by-step instructions with enhanced clarity
        self.instructions_label = ttk.Label(
            self.main_frame,
            text="📋 Step 1: Enter your Google Docs/Sheets URL  →  🎵 Step 2: Select your audio file  →  🚀 Step 3: Generate your Anki deck",
            font=("Arial", 9),
            foreground="gray"
        )
        
        # Input section with clearer labeling
        self.input_frame = ttk.LabelFrame(self.main_frame, text="📝 Step 1 & 2: Provide Your Input Files", padding="10")
        
        # Google Docs URL input with enhanced description
        self.url_label = ttk.Label(
            self.input_frame, 
            text="📋 Step 1: Google Docs/Sheets URL (containing your vocabulary table):",
            font=("Arial", 9, "bold")
        )
        self.url_var = tk.StringVar()
        
        # Create a simple, clean Entry widget
        self.url_entry = ttk.Entry(
            self.input_frame,
            width=60,
            font=("Arial", 9)
        )
        # Manually bind the StringVar after creation to avoid any initialization issues
        self.url_entry.config(textvariable=self.url_var)
        
        # No placeholder text - just a clean, empty text box
        
        self.url_status_label = ttk.Label(
            self.input_frame, 
            text="📋 Paste the complete URL from your browser's address bar (must contain a vocabulary table)", 
            foreground="gray"
        )
        
        # URL help text with more specific guidance
        self.url_help_label = ttk.Label(
            self.input_frame,
            text="💡 Required: Your document must have a table with English and Cantonese columns (e.g., 'English | Cantonese')",
            font=("Arial", 8),
            foreground="blue"
        )
        
        # Audio file selection with enhanced description
        self.audio_label = ttk.Label(
            self.input_frame, 
            text="🎵 Step 2: Audio File (recording of you pronouncing each vocabulary word):",
            font=("Arial", 9, "bold")
        )
        self.audio_frame = ttk.Frame(self.input_frame)
        self.audio_var = tk.StringVar()
        self.audio_entry = ttk.Entry(
            self.audio_frame,
            textvariable=self.audio_var,
            width=45,
            state="readonly",
            font=("Arial", 9)
        )
        self.audio_browse_btn = ttk.Button(
            self.audio_frame,
            text="📁 Browse for Audio File...",
            command=self._browse_audio_file
        )
        self.audio_status_label = ttk.Label(
            self.input_frame, 
            text="🎵 Choose an audio file where you pronounce each vocabulary word clearly (MP3, WAV, M4A supported)", 
            foreground="gray"
        )
        
        # Audio help text with specific recording instructions
        self.audio_help_label = ttk.Label(
            self.input_frame,
            text="💡 Recording tip: Say each word clearly with a 1-2 second pause between words, in the same order as your document",
            font=("Arial", 8),
            foreground="blue"
        )
        
        # Output section with clearer step indication
        self.output_frame = ttk.LabelFrame(self.main_frame, text="📁 Step 3: Choose Where to Save Your Anki Deck", padding="10")
        
        self.output_label = ttk.Label(
            self.output_frame, 
            text="📁 Output Directory (folder where your Anki deck file will be saved):",
            font=("Arial", 9, "bold")
        )
        self.output_dir_frame = ttk.Frame(self.output_frame)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(
            self.output_dir_frame,
            textvariable=self.output_var,
            width=45,
            state="readonly"
        )
        self.output_browse_btn = ttk.Button(
            self.output_dir_frame,
            text="📂 Choose Output Folder",
            command=self._browse_output_directory
        )
        
        # Output directory status label with clearer explanation
        self.output_status_label = ttk.Label(
            self.output_frame, 
            text="📁 Using default location (optional: click 'Choose Output Folder' to change where files are saved)", 
            foreground="gray"
        )
        
        # Output help text with import instructions
        self.output_help_label = ttk.Label(
            self.output_frame,
            text="💡 Next step: After generation, import the .apkg file into Anki using File → Import",
            font=("Arial", 8),
            foreground="blue"
        )
        
        # Advanced Options section
        self.advanced_frame = ttk.LabelFrame(self.main_frame, text="🔧 Advanced Options (Optional)", padding="10")
        
        # Speech verification checkbox (default to enabled)
        self.speech_verification_var = tk.BooleanVar(value=True)
        self.speech_verification_check = ttk.Checkbutton(
            self.advanced_frame,
            text="🎯 Enable Speech Verification (AI-powered alignment checking)",
            variable=self.speech_verification_var,
            command=self._on_speech_verification_changed
        )
        
        # Speech verification help text
        self.speech_verification_help = ttk.Label(
            self.advanced_frame,
            text="💡 Uses Whisper AI to verify audio-text alignment and suggest corrections (requires internet for first-time model download)",
            font=("Arial", 8),
            foreground="blue",
            wraplength=600
        )
        
        # Debug alignment checkbox
        self.debug_alignment_var = tk.BooleanVar(value=False)
        self.debug_alignment_check = ttk.Checkbutton(
            self.advanced_frame,
            text="🔍 Enable Debug Alignment (show detailed alignment analysis)",
            variable=self.debug_alignment_var
        )
        
        # Debug alignment help text
        self.debug_alignment_help = ttk.Label(
            self.advanced_frame,
            text="💡 Shows detailed timing information and tests multiple offsets to help identify alignment issues",
            font=("Arial", 8),
            foreground="blue",
            wraplength=600
        )
        
        # Whisper model selection (initially hidden)
        self.whisper_model_frame = ttk.Frame(self.advanced_frame)
        self.whisper_model_label = ttk.Label(
            self.whisper_model_frame,
            text="Model size:",
            font=("Arial", 8)
        )
        self.whisper_model_var = tk.StringVar(value="base")
        self.whisper_model_combo = ttk.Combobox(
            self.whisper_model_frame,
            textvariable=self.whisper_model_var,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly",
            width=10
        )
        
        # Model size help text
        self.whisper_model_help = ttk.Label(
            self.whisper_model_frame,
            text="tiny=fastest/least accurate (~39MB), base=balanced (~142MB), large=slowest/most accurate (~1550MB)",
            font=("Arial", 7),
            foreground="gray"
        )
        
        # Progress section with clearer labeling
        self.progress_frame = ttk.LabelFrame(self.main_frame, text="🚀 Step 4: Processing Progress", padding="10")
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        
        self.status_var = tk.StringVar(value="✅ Ready to process! Complete steps 1-3 above, then click 'Generate Anki Deck' to begin")
        self.status_label = ttk.Label(
            self.progress_frame,
            textvariable=self.status_var,
            font=("Arial", 9)
        )
        
        # Progress details frame for additional information
        self.progress_details_frame = ttk.Frame(self.progress_frame)
        
        # Progress percentage display
        self.progress_percent_var = tk.StringVar(value="0%")
        self.progress_percent_label = ttk.Label(
            self.progress_details_frame,
            textvariable=self.progress_percent_var,
            font=("Arial", 8),
            foreground="gray"
        )
        
        # Estimated time remaining display
        self.time_remaining_var = tk.StringVar(value="")
        self.time_remaining_label = ttk.Label(
            self.progress_details_frame,
            textvariable=self.time_remaining_var,
            font=("Arial", 8),
            foreground="gray"
        )
        
        # Current stage display
        self.current_stage_var = tk.StringVar(value="")
        self.current_stage_label = ttk.Label(
            self.progress_frame,
            textvariable=self.current_stage_var,
            font=("Arial", 8, "italic"),
            foreground="blue"
        )
        
        # Control buttons
        self.button_frame = ttk.Frame(self.main_frame)
        
        self.process_btn = ttk.Button(
            self.button_frame,
            text="🚀 Generate My Anki Deck",
            command=self._start_processing,
            state="disabled"
        )
        
        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="Cancel",
            command=self._cancel_processing,
            state="disabled"
        )
        
        self.clear_btn = ttk.Button(
            self.button_frame,
            text="🗑️ Clear All Inputs",
            command=self._clear_inputs
        )
        
        # Help button for quick access with clearer label
        self.help_btn = ttk.Button(
            self.button_frame,
            text="❓ Need Help?",
            command=self._show_getting_started_help
        )
        
        # Results section with clearer labeling
        self.results_frame = ttk.LabelFrame(self.main_frame, text="📊 Your Generated Anki Deck", padding="10")
        self.results_text = tk.Text(
            self.results_frame,
            height=4,
            width=60,
            wrap=tk.WORD,
            state="disabled"
        )
        self.results_scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical")
        self.results_text.config(yscrollcommand=self.results_scrollbar.set)
        self.results_scrollbar.config(command=self.results_text.yview)
        
        self.open_folder_btn = ttk.Button(
            self.results_frame,
            text="📂 Open Output Folder",
            command=self._open_output_folder,
            state="disabled"
        )
        
        # Add copy path button for convenience with clearer label
        self.copy_path_btn = ttk.Button(
            self.results_frame,
            text="📋 Copy File Path",
            command=self._copy_output_path,
            state="disabled"
        )
        
    def _setup_layout(self):
        """Arrange widgets in the window layout with scrolling capability."""
        # Configure main canvas and scrollbar
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Configure root grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Configure scrollable frame
        self.scrollable_frame.grid_rowconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Main frame inside scrollable frame
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Title section
        self.title_label.grid(row=0, column=0, pady=(0, 5))
        self.subtitle_label.grid(row=1, column=0, pady=(0, 5))
        self.instructions_label.grid(row=2, column=0, pady=(0, 20))
        
        # Input section
        self.input_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # URL input
        self.url_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.url_entry.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        self.url_status_label.grid(row=2, column=0, sticky="w", pady=(0, 2))
        self.url_help_label.grid(row=3, column=0, sticky="w", pady=(0, 10))
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        # Audio file input
        self.audio_label.grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.audio_frame.grid(row=5, column=0, sticky="ew", pady=(0, 2))
        self.audio_entry.grid(row=0, column=0, sticky="ew")
        self.audio_browse_btn.grid(row=0, column=1, padx=(5, 0))
        self.audio_frame.grid_columnconfigure(0, weight=1)
        self.audio_status_label.grid(row=6, column=0, sticky="w", pady=(0, 2))
        self.audio_help_label.grid(row=7, column=0, sticky="w")
        
        # Output section
        self.output_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        
        self.output_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.output_dir_frame.grid(row=1, column=0, sticky="ew")
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_browse_btn.grid(row=0, column=1, padx=(5, 0))
        self.output_dir_frame.grid_columnconfigure(0, weight=1)
        self.output_status_label.grid(row=2, column=0, sticky="w", pady=(2, 2))
        self.output_help_label.grid(row=3, column=0, sticky="w", pady=(0, 0))
        self.output_frame.grid_columnconfigure(0, weight=1)
        
        # Advanced Options section
        self.advanced_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        
        self.speech_verification_check.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.speech_verification_help.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        # Debug alignment checkbox layout
        self.debug_alignment_check.grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.debug_alignment_help.grid(row=3, column=0, sticky="w", pady=(0, 10))
        
        # Whisper model selection (initially shown since speech verification is enabled by default)
        self.whisper_model_frame.grid(row=4, column=0, sticky="w", pady=(0, 5))
        # Don't hide initially since speech verification is enabled by default
        
        self.whisper_model_label.grid(row=0, column=0, sticky="w", padx=(20, 5))
        self.whisper_model_combo.grid(row=0, column=1, padx=(0, 10))
        self.whisper_model_help.grid(row=0, column=2, sticky="w")
        
        self.advanced_frame.grid_columnconfigure(0, weight=1)
        
        # Progress section
        self.progress_frame.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.status_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
        self.current_stage_label.grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        # Progress details layout
        self.progress_details_frame.grid(row=3, column=0, sticky="ew")
        self.progress_percent_label.grid(row=0, column=0, sticky="w")
        self.time_remaining_label.grid(row=0, column=1, sticky="e")
        self.progress_details_frame.grid_columnconfigure(1, weight=1)
        
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        # Control buttons
        self.button_frame.grid(row=7, column=0, pady=(0, 10))
        
        self.process_btn.grid(row=0, column=0, padx=(0, 10))
        self.cancel_btn.grid(row=0, column=1, padx=(0, 10))
        self.clear_btn.grid(row=0, column=2, padx=(0, 10))
        self.help_btn.grid(row=0, column=3)
        
        # Results section (initially hidden)
        self.results_frame.grid(row=8, column=0, sticky="ew")
        self.results_frame.grid_remove()  # Hide initially
        
        self.results_text.grid(row=0, column=0, sticky="nsew")
        self.results_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Button frame for results actions
        self.results_button_frame = ttk.Frame(self.results_frame)
        self.results_button_frame.grid(row=1, column=0, pady=(5, 0), sticky="w")
        
        self.open_folder_btn.grid(row=0, column=0, padx=(0, 10))
        self.copy_path_btn.grid(row=0, column=1)
        
        self.results_frame.grid_columnconfigure(0, weight=1)
        self.results_frame.grid_rowconfigure(0, weight=1)
        
        # Configure scrolling
        self._configure_scrolling()
    
    def _configure_scrolling(self):
        """Configure canvas scrolling behavior with robust mouse wheel support."""
        # Update scroll region when frame size changes
        def _on_frame_configure(event):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        
        # Update canvas window size when canvas size changes
        def _on_canvas_configure(event):
            # Make the scrollable frame fill the canvas width
            canvas_width = event.width
            self.main_canvas.itemconfig(self.canvas_frame_id, width=canvas_width)
        
        # Bind events
        self.scrollable_frame.bind('<Configure>', _on_frame_configure)
        self.main_canvas.bind('<Configure>', _on_canvas_configure)
        
        # Mouse wheel scrolling function with better platform support
        def _on_mousewheel(event):
            # Don't scroll if an Entry widget has focus
            focused_widget = self.root.focus_get()
            if isinstance(focused_widget, ttk.Entry):
                return
                
            # Check if we need to scroll (content is larger than visible area)
            try:
                # Get the current scroll region
                scroll_region = self.main_canvas.cget("scrollregion")
                if not scroll_region:
                    return
                
                # Parse scroll region (x1, y1, x2, y2)
                x1, y1, x2, y2 = map(float, scroll_region.split())
                content_height = y2 - y1
                canvas_height = self.main_canvas.winfo_height()
                
                if content_height > canvas_height:
                    # Handle different platforms - Windows uses event.delta, Linux uses event.num
                    if hasattr(event, 'delta') and event.delta:
                        # Windows and MacOS
                        delta = event.delta
                        self.main_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
                    elif hasattr(event, 'num'):
                        # Linux
                        if event.num == 4:
                            self.main_canvas.yview_scroll(-1, "units")
                        elif event.num == 5:
                            self.main_canvas.yview_scroll(1, "units")
            except:
                pass  # Ignore any errors in scrolling
        
        # Bind mouse wheel to root window but with Entry widget check
        def _bind_mousewheel():
            # Use root binding but with focus check to avoid interfering with Entry widgets
            self.root.bind("<MouseWheel>", _on_mousewheel, add="+")  # Windows/Mac
            self.root.bind("<Button-4>", _on_mousewheel, add="+")    # Linux scroll up
            self.root.bind("<Button-5>", _on_mousewheel, add="+")    # Linux scroll down
        
        # Apply binding
        _bind_mousewheel()
        
        # Store the binding function for later use
        self._mousewheel_handler = _on_mousewheel
        
        # Focus management - ensure the canvas can receive focus for keyboard events
        def _on_focus_in(event):
            # Only set canvas focus if no Entry widget is focused
            focused_widget = self.root.focus_get()
            if not isinstance(focused_widget, ttk.Entry):
                self.main_canvas.focus_set()
        
        # Bind focus events - but don't interfere with Entry widgets
        self.main_canvas.bind("<Button-1>", lambda e: self.main_canvas.focus_set(), add="+")
        
        # Keyboard scrolling with better key handling
        def _on_key_scroll(event):
            # Don't scroll if any Entry widget has focus
            focused_widget = self.root.focus_get()
            if isinstance(focused_widget, ttk.Entry):
                return
            try:
                if event.keysym == 'Up':
                    self.main_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.main_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Prior':  # Page Up
                    self.main_canvas.yview_scroll(-1, "pages")
                elif event.keysym == 'Next':   # Page Down
                    self.main_canvas.yview_scroll(1, "pages")
                elif event.keysym == 'Home':
                    self.main_canvas.yview_moveto(0)
                elif event.keysym == 'End':
                    self.main_canvas.yview_moveto(1)
            except:
                pass  # Ignore any errors in keyboard scrolling
        
        # Bind keyboard scrolling to both canvas and root with focus checks
        self.main_canvas.bind("<Up>", _on_key_scroll)
        self.main_canvas.bind("<Down>", _on_key_scroll)
        self.main_canvas.bind("<Prior>", _on_key_scroll)
        self.main_canvas.bind("<Next>", _on_key_scroll)
        self.main_canvas.bind("<Home>", _on_key_scroll)
        self.main_canvas.bind("<End>", _on_key_scroll)
        
        # Also bind to root for when canvas doesn't have focus, but with Entry check
        self.root.bind("<Up>", _on_key_scroll, add="+")
        self.root.bind("<Down>", _on_key_scroll, add="+")
        self.root.bind("<Prior>", _on_key_scroll, add="+")
        self.root.bind("<Next>", _on_key_scroll, add="+")
        self.root.bind("<Home>", _on_key_scroll, add="+")
        self.root.bind("<End>", _on_key_scroll, add="+")
        
        # Make canvas focusable for keyboard scrolling
        self.main_canvas.config(takefocus=True)
    
    def _add_scroll_indicator(self):
        """Add visual indicator for scrolling capability."""
        # Create a small status bar at the bottom (but don't show scroll text)
        self.status_bar = ttk.Frame(self.root)
        
        # Position status bar at bottom
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        
        # Update root grid configuration
        self.root.grid_rowconfigure(1, weight=0)  # Status bar doesn't expand
    
    def _bind_mousewheel_to_widget(self, widget):
        """Bind mouse wheel scrolling to a widget and all its children."""
        # With the new global binding approach, we don't need to bind to individual widgets
        # The global binding will handle all mouse wheel events
        pass
    
    def _update_scroll_region(self):
        """Update the scroll region to match current content size."""
        self.root.update_idletasks()
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
    
    def _scroll_to_top(self):
        """Scroll to the top of the window."""
        self.main_canvas.yview_moveto(0)
    
    def _scroll_to_bottom(self):
        """Scroll to the bottom of the window."""
        self.main_canvas.yview_moveto(1)
        
        # Set initial output directory display
        self.output_var.set(self.state.output_directory)
        
        # Update output status label
        self._update_output_status_label()
        
        # Initialize clear button state
        self.clear_btn.config(state="disabled")
        
    def _configure_styles(self):
        """Configure widget styles and appearance."""
        style = ttk.Style()
        
        # Configure button styles
        style.configure("Process.TButton", font=("Arial", 10, "bold"))
        self.process_btn.configure(style="Process.TButton")
        
        # Bind events for input validation - use simpler approach
        self.url_var.trace_add("write", self._on_input_change)
        self.audio_var.trace_add("write", self._on_input_change)
        
        # Add simple key release validation
        self.url_entry.bind("<KeyRelease>", self._on_url_key_release)
        
        # Set up keyboard shortcuts and accessibility
        self._setup_keyboard_shortcuts()
        
        # Configure tab order for accessibility
        self._setup_tab_order()
        
    def _setup_tab_order(self):
        """Set up proper tab navigation order for accessibility."""
        # Define the tab order for main interactive elements
        tab_order = [
            self.url_entry,
            self.audio_browse_btn,
            self.output_browse_btn,
            self.process_btn,
            self.cancel_btn,
            self.clear_btn,
            self.help_btn
        ]
        
        # Set tab order by configuring each widget
        for i, widget in enumerate(tab_order):
            # Ensure widget can receive focus
            if hasattr(widget, 'configure'):
                try:
                    widget.configure(takefocus=True)
                except tk.TclError:
                    # Some widgets don't support takefocus
                    pass
        
        # Set initial focus to URL entry
        self.root.after(100, lambda: self.url_entry.focus_set())
        
        # Ensure URL entry is enabled and ready for input
        self.url_entry.config(state="normal")
        
        # Force the URL entry to be ready for input
        self.root.after(200, lambda: self._ensure_url_entry_ready())
        
    def _ensure_url_entry_ready(self):
        """Ensure the URL entry is ready for input."""
        try:
            self.url_entry.config(state="normal")
            self.url_entry.focus_set()
            # Test that the entry can accept input
            self.url_entry.insert(0, "")  # Insert empty string to test
        except Exception as e:
            print(f"URL entry setup error: {e}")
        
    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for the application."""
        # Help shortcuts
        self.root.bind("<F1>", lambda e: self._show_keyboard_shortcuts_help())
        self.root.bind("<Control-h>", lambda e: self._show_getting_started_help())
        self.root.bind("<Control-question>", lambda e: self._show_troubleshooting_help())
        
        # File operation shortcuts
        self.root.bind("<Control-o>", lambda e: self._browse_audio_file() if not self.state.is_processing else None)
        self.root.bind("<Control-s>", lambda e: self._browse_output_directory() if not self.state.is_processing else None)
        self.root.bind("<Control-l>", lambda e: self.url_entry.focus_set() if not self.state.is_processing else None)
        
        # Processing shortcuts
        self.root.bind("<Control-r>", lambda e: self._start_processing() if self.process_btn['state'] == 'normal' else None)
        self.root.bind("<Control-g>", lambda e: self._start_processing() if self.process_btn['state'] == 'normal' else None)
        self.root.bind("<Escape>", lambda e: self._cancel_processing() if self.state.is_processing else None)
        
        # Interface shortcuts
        self.root.bind("<Control-Delete>", lambda e: self._clear_inputs() if not self.state.is_processing else None)
        self.root.bind("<Control-e>", lambda e: self._open_output_folder() if self.open_folder_btn['state'] == 'normal' else None)
        
        # Accessibility shortcuts
        self.root.bind("<Alt-1>", lambda e: self.url_entry.focus_set())
        self.root.bind("<Alt-2>", lambda e: self.audio_browse_btn.focus_set())
        self.root.bind("<Alt-3>", lambda e: self.output_browse_btn.focus_set())
        self.root.bind("<Alt-4>", lambda e: self.process_btn.focus_set())
        
        # Navigation shortcuts
        self.root.bind("<Control-Tab>", self._focus_next_widget)
        self.root.bind("<Control-Shift-Tab>", self._focus_previous_widget)
        
        # Quick access shortcuts
        self.root.bind("<Control-comma>", lambda e: self._show_preferences() if hasattr(self, '_show_preferences') else None)
        
    def _focus_next_widget(self, event):
        """Move focus to the next widget in tab order."""
        event.widget.tk_focusNext().focus_set()
        return "break"
        
    def _focus_previous_widget(self, event):
        """Move focus to the previous widget in tab order."""
        event.widget.tk_focusPrev().focus_set()
        return "break"
    
    def _on_speech_verification_changed(self):
        """Handle speech verification checkbox change."""
        if self.speech_verification_var.get():
            # Show the model selection options
            self.whisper_model_frame.grid()
        else:
            # Hide the model selection options
            self.whisper_model_frame.grid_remove()
    
    def _on_url_key_release(self, event):
        """Handle real-time URL validation as user types."""
        url_value = self.url_entry.get()
        
        # Only validate if there's actual content
        if url_value.strip():
            self._validate_url(url_value)
        else:
            self.url_status_label.config(text="📋 Paste the complete URL from your browser's address bar (must contain a vocabulary table)", foreground="gray")
        
    def _browse_audio_file(self):
        """Open file dialog to select audio file with enhanced validation."""
        filetypes = [
            ("Supported Audio", "*.mp3 *.wav *.m4a"),  # Primary supported formats
            ("MP3 files", "*.mp3"),
            ("WAV files", "*.wav"),
            ("M4A files", "*.m4a"),
            ("Other Audio", "*.flac *.ogg"),  # Additional formats
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=filetypes,
            initialdir=str(Path.home())
        )
        
        if filename:
            # Store the full path in both places
            self.audio_var.set(filename)
            self.state.audio_file_path = filename
            
            # Validate immediately after selection
            is_valid = self._validate_audio_file(filename)
            
            # Update UI based on validation result - show filename but keep full path in variable
            if is_valid:
                # Show just the filename in the entry for better UX, but don't bind to audio_var
                display_name = Path(filename).name
                if len(display_name) > 40:  # Truncate very long filenames
                    display_name = display_name[:37] + "..."
                
                # Temporarily disconnect the textvariable to avoid overwriting the full path
                self.audio_entry.config(textvariable="")
                self.audio_entry.config(state="normal")
                self.audio_entry.delete(0, tk.END)
                self.audio_entry.insert(0, display_name)
                self.audio_entry.config(state="readonly")
                # Don't reconnect textvariable - we want to keep the full path in audio_var
            
            # Update button state after file selection
            self._update_process_button_state()
        else:
            # User cancelled - reset status if no file was previously selected
            if not self.audio_var.get():
                self.audio_status_label.config(text="🎵 Choose an audio file where you pronounce each vocabulary word clearly (MP3, WAV, M4A supported)", foreground="gray")
            
    def _browse_output_directory(self):
        """Open dialog to select output directory with validation."""
        directory = filedialog.askdirectory(
            title="Choose Output Folder",
            initialdir=self.state.output_directory
        )
        
        if directory:
            # Validate and ensure the directory exists
            if self._validate_output_directory(directory):
                self.output_var.set(directory)
                self.state.output_directory = directory
                
                # Update status label with success feedback
                dir_path = Path(directory)
                if dir_path == Path.cwd() / "output":
                    self.output_status_label.config(text="📁 Using default output location", foreground="green")
                else:
                    self.output_status_label.config(text="📁 Custom output location selected", foreground="green")
            else:
                messagebox.showerror(
                    "Invalid Directory",
                    f"Cannot use the selected directory:\n{directory}\n\n"
                    "Please choose a different location or check permissions."
                )
            
    def _validate_output_directory(self, directory: str) -> bool:
        """
        Validate the selected output directory.
        
        Args:
            directory: Path to the directory to validate
            
        Returns:
            True if directory is valid and usable, False otherwise
        """
        try:
            dir_path = Path(directory)
            
            # Check if directory exists
            if not dir_path.exists():
                # Try to create it
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError):
                    return False
            
            # Check if it's actually a directory
            if not dir_path.is_dir():
                return False
                
            # Check if we can write to it
            test_file = dir_path / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()  # Clean up test file
            except (OSError, PermissionError):
                return False
                
            return True
            
        except Exception:
            return False
    
    def _ensure_output_directory_exists(self):
        """Ensure the default output directory exists and is writable."""
        try:
            output_path = Path(self.state.output_directory)
            
            # Create directory if it doesn't exist
            if not output_path.exists():
                output_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created output directory: {output_path}")
            
            # Validate the directory
            if not self._validate_output_directory(str(output_path)):
                # Fall back to user's home directory if default fails
                fallback_dir = Path.home() / "CantoneseAnkiGenerator" / "output"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                
                self.state.output_directory = str(fallback_dir)
                self.logger.warning(f"Default output directory not accessible, using: {fallback_dir}")
                
        except Exception as e:
            # Ultimate fallback to current directory
            self.state.output_directory = str(Path.cwd())
            self.logger.error(f"Could not create output directory, using current directory: {e}")
    
    def _update_output_status_label(self):
        """Update the output directory status label based on current selection."""
        try:
            current_dir = Path(self.state.output_directory)
            default_dir = Path.cwd() / "output"
            
            if current_dir == default_dir:
                self.output_status_label.config(text="📁 Using default output location", foreground="green")
            else:
                # Check if directory exists and is writable
                if self._validate_output_directory(str(current_dir)):
                    self.output_status_label.config(text="📁 Custom output location", foreground="green")
                else:
                    self.output_status_label.config(text="⚠️ Output location may not be accessible", foreground="orange")
                    
        except Exception:
            self.output_status_label.config(text="⚠️ Output location status unknown", foreground="orange")
            
    def _validate_audio_file(self, filepath: str) -> bool:
        """Validate the selected audio file with comprehensive checks."""
        try:
            path = Path(filepath)
            
            if not path.exists():
                self.audio_status_label.config(text="❌ File not found", foreground="red")
                return False
                
            # Check file format (MP3, WAV, M4A as specified in requirements)
            supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg']
            if not path.suffix.lower() in supported_formats:
                self.audio_status_label.config(
                    text=f"❌ Unsupported format. Use: {', '.join(supported_formats)}", 
                    foreground="red"
                )
                return False
                
            # Check file size
            size_bytes = path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            # Warn if file is too small (likely not a real audio file)
            if size_bytes < 1024:  # Less than 1KB
                self.audio_status_label.config(text="❌ File too small to be valid audio", foreground="red")
                return False
                
            # Warn if file is very large
            if size_mb > 500:  # More than 500MB
                self.audio_status_label.config(
                    text=f"⚠️ Very large file ({size_mb:.1f}MB) - may cause memory issues", 
                    foreground="orange"
                )
                return True
            elif size_mb > 100:  # More than 100MB
                self.audio_status_label.config(
                    text=f"⚠️ Large file ({size_mb:.1f}MB) - processing may take longer",
                    foreground="orange"
                )
                return True
            else:
                # Show file size for user reference
                if size_mb >= 1:
                    size_text = f"{size_mb:.1f}MB"
                else:
                    size_text = f"{size_bytes / 1024:.1f}KB"
                    
                self.audio_status_label.config(
                    text="✅ Valid audio file ({}) - ready to process".format(size_text), 
                    foreground="green"
                )
                
            return True
            
        except Exception as e:
            self.audio_status_label.config(text=f"❌ Error: {str(e)}", foreground="red")
            return False
            
    def _validate_url(self, url: str) -> bool:
        """Validate the Google Docs/Sheets URL with real-time feedback."""
        if not url.strip():
            self.url_status_label.config(text="📋 Paste the complete URL from your browser's address bar (must contain a vocabulary table)", foreground="gray")
            return False
            
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            self.url_status_label.config(text="❌ URL must start with http:// or https://", foreground="red")
            return False
            
        # Check if it's a Google Docs or Sheets URL
        if 'docs.google.com' not in url and 'sheets.google.com' not in url:
            self.url_status_label.config(text="❌ Must be a Google Docs or Sheets URL", foreground="red")
            return False
            
        # Check for proper document ID format
        if 'docs.google.com' in url:
            # Check if it's a Google Docs document or Google Sheets spreadsheet
            if '/document/d/' not in url and '/spreadsheets/d/' not in url:
                self.url_status_label.config(text="❌ Invalid Google Docs/Sheets URL format", foreground="red")
                return False
        elif 'sheets.google.com' in url:
            if '/spreadsheets/d/' not in url:
                self.url_status_label.config(text="❌ Invalid Google Sheets URL format", foreground="red")
                return False
                
        # Check if URL appears to have a valid document ID
        try:
            if '/document/d/' in url:
                doc_id = url.split('/document/d/')[1].split('/')[0]
            elif '/spreadsheets/d/' in url:
                doc_id = url.split('/spreadsheets/d/')[1].split('/')[0]
            else:
                self.url_status_label.config(text="❌ Could not find document or spreadsheet ID", foreground="red")
                return False
                
            if len(doc_id) < 20:  # Google doc IDs are typically much longer
                self.url_status_label.config(text="❌ Invalid document ID format", foreground="red")
                return False
                
        except (IndexError, AttributeError):
            self.url_status_label.config(text="❌ Could not extract document ID", foreground="red")
            return False
            
        self.url_status_label.config(text="✅ Valid Google Docs/Sheets URL - ready to process", foreground="green")
        return True
        
    def _on_input_change(self, *args):
        """Handle input field changes and update UI state."""
        # Get URL value
        url_value = self.url_var.get()
            
        # Update state
        self.state.google_docs_url = url_value
        
        # Update UI state using centralized method
        self._update_process_button_state()
            
    def _clear_inputs(self):
        """Clear all input fields and reset to initial state."""
        # Don't allow clearing during processing
        if self.state.is_processing:
            messagebox.showwarning(
                "Cannot Clear",
                "Cannot clear inputs while processing is in progress. Please cancel processing first."
            )
            return
            
        # Clear URL input
        self.url_entry.config(foreground="black")
        self.url_entry.delete(0, tk.END)
        self.url_status_label.config(text="📋 Paste the complete URL from your browser's address bar (must contain a vocabulary table)", foreground="gray")
        
        # Clear audio input
        self.audio_var.set("")
        self.audio_entry.config(state="normal")
        self.audio_entry.delete(0, tk.END)
        self.audio_entry.config(state="readonly")
        self.audio_status_label.config(text="🎵 Choose an audio file where you pronounce each vocabulary word clearly (MP3, WAV, M4A supported)", foreground="gray")
        
        # Reset state
        self.state.google_docs_url = ""
        self.state.audio_file_path = ""
        
        # Reset progress indicators
        self.progress_var.set(0)
        self.status_var.set("Ready to process - complete all steps above then click 'Generate Anki Deck'")
        self.current_stage_var.set("")
        self.progress_percent_var.set("0%")
        self.time_remaining_var.set("")
        self.state.current_stage = ""
        self.state.progress_percentage = 0.0
        self.state.processing_start_time = None
        self.state.estimated_total_time = None
        self.state.current_stage_name = ""
        self.state.items_completed = 0
        self.state.total_items = 0
        
        # Update UI state
        self._update_process_button_state()
        
        # Hide results if visible
        self.results_frame.grid_remove()
        
        # Clear results text
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state="disabled")
        self.open_folder_btn.config(state="disabled")
        self.copy_path_btn.config(state="disabled")
        
        # Clear last result data
        self._last_result_data = None
        
    def _preserve_inputs_during_error(self):
        """Preserve user inputs when an error occurs."""
        # Store current values in case we need to restore them
        preserved_state = {
            'url': self.url_var.get().strip(),
            'audio': self.state.audio_file_path,  # Use full path, not display name
            'output': self.output_var.get(),
            'url_valid': self._is_url_valid(),
            'audio_valid': self._is_audio_valid()
        }
        return preserved_state
        
    def _restore_inputs_from_preserved(self, preserved_state):
        """Restore inputs from preserved state after error recovery."""
        # Restore URL
        if preserved_state['url']:
            self.url_entry.config(foreground="black")
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, preserved_state['url'])
            self.state.google_docs_url = preserved_state['url']
            if preserved_state['url_valid']:
                self._validate_url(preserved_state['url'])
        
        # Restore audio file
        if preserved_state['audio']:
            self.audio_var.set(preserved_state['audio'])
            self.state.audio_file_path = preserved_state['audio']
            if preserved_state['audio_valid']:
                self._validate_audio_file(preserved_state['audio'])
                # Update display name for audio file
                display_name = Path(preserved_state['audio']).name
                if len(display_name) > 40:
                    display_name = display_name[:37] + "..."
                self.audio_entry.config(state="normal")
                self.audio_entry.delete(0, tk.END)
                self.audio_entry.insert(0, display_name)
                self.audio_entry.config(state="readonly")
            
        # Restore output directory
        if preserved_state['output']:
            self.output_var.set(preserved_state['output'])
            self.state.output_directory = preserved_state['output']
            
        # Update UI state
        self._update_process_button_state()
        
    def _is_url_valid(self) -> bool:
        """Check if current URL is valid without updating UI."""
        url_value = self.url_var.get()
        return self._validate_url_silent(url_value)
        
    def _is_audio_valid(self) -> bool:
        """Check if current audio file is valid without updating UI."""
        return bool(self.state.audio_file_path and self._validate_audio_file_silent(self.state.audio_file_path))
        
    def _validate_url_silent(self, url: str) -> bool:
        """Validate URL without updating UI status labels."""
        if not url.strip():
            return False
            
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return False
            
        # Check if it's a Google Docs or Sheets URL
        if 'docs.google.com' not in url and 'sheets.google.com' not in url:
            return False
            
        # Check for proper document ID format
        if 'docs.google.com' in url:
            # Check if it's a Google Docs document or Google Sheets spreadsheet
            if '/document/d/' not in url and '/spreadsheets/d/' not in url:
                return False
        elif 'sheets.google.com' in url:
            if '/spreadsheets/d/' not in url:
                return False
                
        # Check if URL appears to have a valid document ID
        try:
            if '/document/d/' in url:
                doc_id = url.split('/document/d/')[1].split('/')[0]
            elif '/spreadsheets/d/' in url:
                doc_id = url.split('/spreadsheets/d/')[1].split('/')[0]
            else:
                return False
                
            if len(doc_id) < 20:  # Google doc IDs are typically much longer
                return False
                
        except (IndexError, AttributeError):
            return False
            
        return True
        
    def _validate_audio_file_silent(self, filepath: str) -> bool:
        """Validate audio file without updating UI status labels."""
        try:
            path = Path(filepath)
            
            if not path.exists():
                return False
                
            # Check file format
            supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg']
            if not path.suffix.lower() in supported_formats:
                return False
                
            # Check file size
            size_bytes = path.stat().st_size
            if size_bytes < 1024:  # Less than 1KB
                return False
                
            return True
            
        except Exception:
            return False
        
    def _update_process_button_state(self):
        """Update the process button state based on current inputs and processing status."""
        # Get URL value
        url_value = self.url_var.get()
            
        # Check if inputs are valid
        url_valid = bool(url_value) and self._validate_url_silent(url_value)
        audio_valid = bool(self.state.audio_file_path) and self._validate_audio_file_silent(self.state.audio_file_path)
        
        # Enable/disable process button based on input completeness and processing state
        if url_valid and audio_valid and not self.state.is_processing:
            self.process_btn.config(state="normal")
        else:
            self.process_btn.config(state="disabled")
            
        # Update clear button state - enable if there are any inputs
        has_inputs = bool(url_value or self.state.audio_file_path)
        self.clear_btn.config(state="normal" if has_inputs and not self.state.is_processing else "disabled")
        
        # Update cancel button state - enable only during processing
        self.cancel_btn.config(state="normal" if self.state.is_processing else "disabled")
        
    def _set_processing_state(self, is_processing: bool, stage: str = ""):
        """Set the processing state and update UI accordingly."""
        self.state.is_processing = is_processing
        self.state.current_stage = stage
        
        if is_processing:
            # Disable input controls during processing
            self.url_entry.config(state="disabled")
            self.audio_browse_btn.config(state="disabled")
            self.output_browse_btn.config(state="disabled")
            
            # Initialize processing timing
            if not self.state.processing_start_time:
                self.state.processing_start_time = time.time()
            
            # Update status
            self.status_var.set(stage if stage else "Processing...")
            self.current_stage_var.set(stage if stage else "")
        else:
            # Re-enable input controls after processing
            self.url_entry.config(state="normal")
            self.audio_browse_btn.config(state="normal")
            self.output_browse_btn.config(state="normal")
            
            # Reset progress if not processing
            if not stage:  # Only reset if no specific stage provided
                self.progress_var.set(0)
                self.status_var.set("✅ Ready to process! Complete steps 1-3 above, then click 'Generate Anki Deck' to begin")
                self.current_stage_var.set("")
                self.progress_percent_var.set("0%")
                self.time_remaining_var.set("")
                self.state.progress_percentage = 0.0
                self.state.processing_start_time = None
                self.state.estimated_total_time = None
        
        # Update button states
        self._update_process_button_state()
        
    def _update_progress_display(self, percentage: float, stage_name: str = "", 
                               items_completed: int = 0, total_items: int = 0,
                               current_item: str = ""):
        """
        Update the progress display with percentage, stage, and time estimation.
        
        Args:
            percentage: Progress percentage (0-100)
            stage_name: Current processing stage name
            items_completed: Number of items completed in current stage
            total_items: Total items in current stage
            current_item: Description of current item being processed
        """
        # Update progress bar and percentage
        self.progress_var.set(percentage)
        self.progress_percent_var.set(f"{percentage:.1f}%")
        self.state.progress_percentage = percentage
        
        # Update stage information
        if stage_name:
            self.state.current_stage_name = stage_name
            self.current_stage_var.set(stage_name)
            
        # Update item counts
        self.state.items_completed = items_completed
        self.state.total_items = total_items
        
        # Calculate and display estimated time remaining
        if self.state.processing_start_time and percentage > 0:
            elapsed_time = time.time() - self.state.processing_start_time
            
            if percentage < 100:
                # Estimate total time based on current progress
                estimated_total = elapsed_time / (percentage / 100)
                remaining_time = estimated_total - elapsed_time
                
                # Store estimated total time for consistency
                if not self.state.estimated_total_time:
                    self.state.estimated_total_time = estimated_total
                else:
                    # Use weighted average to smooth estimates
                    self.state.estimated_total_time = (
                        0.7 * self.state.estimated_total_time + 0.3 * estimated_total
                    )
                
                # Format time remaining
                if remaining_time > 0:
                    self.time_remaining_var.set(self._format_time_remaining(remaining_time))
                else:
                    self.time_remaining_var.set("Almost done...")
            else:
                # Processing complete
                self.time_remaining_var.set(f"Completed in {self._format_time_remaining(elapsed_time)}")
        
        # Update status with item progress if available
        if current_item:
            # Show current item being processed
            if total_items > 0:
                status_text = f"{stage_name}: {current_item} ({items_completed}/{total_items})"
            else:
                status_text = f"{stage_name}: {current_item}"
            self.status_var.set(status_text)
        elif total_items > 0:
            # Show item count progress
            status_text = f"{stage_name} ({items_completed}/{total_items})"
            self.status_var.set(status_text)
        elif stage_name:
            # Show just stage name
            self.status_var.set(stage_name)
        
        # Force UI update
        self.root.update_idletasks()
    
    def _format_time_remaining(self, seconds: float) -> str:
        """
        Format time remaining in a user-friendly way.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 60:
            return f"~{int(seconds)}s remaining"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"~{minutes}m remaining"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"~{hours}h {minutes}m remaining"
    
    def _start_progress_polling(self):
        """Start polling for progress updates from background thread."""
        self._check_progress_updates()
    
    def _check_progress_updates(self):
        """Check for progress updates from background thread and update UI."""
        # Process any queued progress updates
        while self.progress_callback_queue:
            try:
                update = self.progress_callback_queue.pop(0)
                self._process_progress_update(update)
            except IndexError:
                break
        
        # Schedule next check
        self.root.after(100, self._check_progress_updates)  # Check every 100ms
    
    def _process_progress_update(self, update):
        """
        Process a progress update from the background thread.
        
        Args:
            update: Dictionary containing progress information
        """
        update_type = update.get('type', 'progress')
        
        if update_type == 'progress':
            # Standard progress update
            percentage = update.get('percentage', 0)
            stage_name = update.get('stage_name', '')
            items_completed = update.get('items_completed', 0)
            total_items = update.get('total_items', 0)
            current_item = update.get('current_item', '')
            stage_percentage = update.get('stage_percentage', 0)
            
            # Update progress display
            self._update_progress_display(percentage, stage_name, items_completed, total_items)
            
            # Update detailed status with current item if available
            if current_item:
                detailed_status = f"{stage_name}: {current_item}"
                if total_items > 0:
                    detailed_status += f" ({items_completed}/{total_items})"
                self.status_var.set(detailed_status)
            
        elif update_type == 'stage_start':
            # New stage starting
            stage_name = update.get('stage_name', '')
            total_items = update.get('total_items', 0)
            percentage = update.get('percentage', 0)
            user_message = update.get('user_message', f"Starting: {stage_name}")
            
            # Update progress display for new stage
            self._update_progress_display(percentage, stage_name, 0, total_items)
            
            # Show user-friendly stage transition message
            self.status_var.set(user_message)
            
            # Log stage transition for debugging
            self.logger.debug(f"Stage transition: Starting {stage_name} with {total_items} items")
            
        elif update_type == 'stage_complete':
            # Stage completed
            stage_name = update.get('stage_name', '')
            success = update.get('success', True)
            percentage = update.get('percentage', 0)
            user_message = update.get('user_message', f"{'✅ Completed' if success else '❌ Failed'}: {stage_name}")
            
            if success:
                # Update status with user-friendly completion message
                self.status_var.set(user_message)
                
                # Brief pause to show completion before next stage
                self.root.after(500, lambda: None)  # 500ms pause
            else:
                # Show failure status
                self.status_var.set(user_message)
                
            # Log stage completion
            self.logger.debug(f"Stage completed: {stage_name} ({'success' if success else 'failed'})")
                
        elif update_type == 'error':
            # Error occurred
            error_message = update.get('message', 'Unknown error')
            self._handle_processing_error(error_message)
            
        elif update_type == 'complete':
            # Processing completed
            success = update.get('success', True)
            result_data = update.get('result_data', {})
            self._handle_processing_completion(success, result_data)
            
        elif update_type == 'warning':
            # Warning message
            warning_message = update.get('message', '')
            stage_name = update.get('stage_name', '')
            
            # Show warning in status (temporarily)
            if warning_message:
                self.status_var.set(f"⚠️ {stage_name}: {warning_message}")
                # Revert to normal status after 3 seconds
                self.root.after(3000, lambda: self._revert_to_normal_status(stage_name))
                
        elif update_type == 'info':
            # Informational message
            info_message = update.get('message', '')
            stage_name = update.get('stage_name', '')
            
            # Show info in current stage display
            if info_message:
                self.current_stage_var.set(f"{stage_name}: {info_message}")
    
    def _revert_to_normal_status(self, stage_name):
        """
        Revert status display to normal after showing temporary message.
        
        Args:
            stage_name: Current stage name to revert to
        """
        if self.state.is_processing:
            # Only revert if still processing
            if self.state.total_items > 0:
                status_text = f"{stage_name} ({self.state.items_completed}/{self.state.total_items})"
            else:
                status_text = stage_name
            self.status_var.set(status_text)
    
    def _create_progress_callback(self):
        """
        Create a thread-safe progress callback function.
        
        Returns:
            Callback function that can be used by background processing
        """
        def progress_callback(stage_progress):
            """
            Thread-safe progress callback for background processing.
            
            Args:
                stage_progress: StageProgress object from progress tracker
            """
            # Convert processing stage to user-friendly description
            stage_descriptions = {
                'initialization': 'Initializing and validating inputs',
                'authentication': 'Connecting to Google services',
                'document_parsing': 'Reading vocabulary from document',
                'audio_loading': 'Loading and analyzing audio file',
                'audio_segmentation': 'Segmenting audio into word clips',
                'alignment': 'Aligning vocabulary with audio (AI verification)',
                'anki_generation': 'Creating Anki flashcard deck',
                'finalization': 'Finalizing and saving package'
            }
            
            # Get user-friendly stage name
            stage_name = stage_descriptions.get(
                stage_progress.stage.value, 
                stage_progress.stage.value.replace('_', ' ').title()
            )
            
            # Calculate overall pipeline progress based on stage completion
            overall_percentage = self._calculate_overall_progress(stage_progress)
            
            # Convert stage progress to update dictionary
            update = {
                'type': 'progress',
                'percentage': overall_percentage,
                'stage_name': stage_name,
                'items_completed': stage_progress.completed_items,
                'total_items': stage_progress.total_items,
                'current_item': stage_progress.current_item,
                'status': stage_progress.status,
                'stage_percentage': stage_progress.progress_percentage
            }
            
            # Handle stage transitions
            if stage_progress.status == "in_progress" and stage_progress.progress_percentage == 0.0:
                # Stage just started
                update['type'] = 'stage_start'
                # Add user-friendly stage start messages
                stage_start_messages = {
                    'initialization': 'Preparing to process your files...',
                    'authentication': 'Connecting to Google Docs/Sheets...',
                    'document_parsing': 'Reading vocabulary from your document...',
                    'audio_loading': 'Loading your audio file...',
                    'audio_segmentation': 'Analyzing audio and creating word segments...',
                    'alignment': 'Matching vocabulary words with audio clips...',
                    'anki_generation': 'Creating your Anki flashcard deck...',
                    'finalization': 'Saving your deck and cleaning up...'
                }
                update['user_message'] = stage_start_messages.get(stage_progress.stage.value, stage_name)
                
            elif stage_progress.status in ["completed", "failed"]:
                # Stage completed or failed
                update['type'] = 'stage_complete'
                update['success'] = stage_progress.status == "completed"
                
                # Add completion messages
                if stage_progress.status == "completed":
                    stage_complete_messages = {
                        'initialization': 'Setup complete ✓',
                        'authentication': 'Connected to Google services ✓',
                        'document_parsing': f'Found {stage_progress.details.get("vocab_count", "vocabulary")} words ✓',
                        'audio_loading': f'Audio loaded ({stage_progress.details.get("duration", "N/A")}s) ✓',
                        'audio_segmentation': f'Created {stage_progress.details.get("segment_count", "audio")} segments ✓',
                        'alignment': f'Aligned {stage_progress.details.get("aligned_pairs", "vocabulary")} pairs ✓',
                        'anki_generation': 'Anki deck created ✓',
                        'finalization': 'Processing complete ✓'
                    }
                    update['user_message'] = stage_complete_messages.get(stage_progress.stage.value, f'{stage_name} complete ✓')
                else:
                    update['user_message'] = f'{stage_name} failed ✗'
            
            # Add to queue for UI thread to process
            self.progress_callback_queue.append(update)
            
        return progress_callback
    
    def _calculate_overall_progress(self, current_stage_progress):
        """
        Calculate overall pipeline progress based on current stage.
        
        Args:
            current_stage_progress: StageProgress object for current stage
            
        Returns:
            Overall progress percentage (0-100)
        """
        # Define stage weights (approximate time each stage takes)
        stage_weights = {
            'initialization': 5,
            'authentication': 5,
            'document_parsing': 10,
            'audio_loading': 15,
            'audio_segmentation': 25,
            'alignment': 30,
            'anki_generation': 8,
            'finalization': 2
        }
        
        # Calculate cumulative progress
        total_weight = sum(stage_weights.values())
        completed_weight = 0
        current_stage_name = current_stage_progress.stage.value
        
        # Add weight for completed stages and partial progress for current stage
        for stage_name, weight in stage_weights.items():
            if stage_name == current_stage_name:
                # Add partial progress for current stage
                stage_progress = current_stage_progress.progress_percentage / 100.0
                completed_weight += weight * stage_progress
                break
            else:
                # Check if this stage was completed (assume completed if we're past it)
                stage_order = list(stage_weights.keys())
                current_index = stage_order.index(current_stage_name) if current_stage_name in stage_order else -1
                stage_index = stage_order.index(stage_name)
                
                if stage_index < current_index:
                    # This stage was completed
                    completed_weight += weight
        
        # Calculate overall percentage
        overall_percentage = (completed_weight / total_weight) * 100
        return min(100, max(0, overall_percentage))
        
        # Calculate overall percentage
        overall_percentage = (completed_weight / total_weight) * 100
        return min(100, max(0, overall_percentage))
    
    def _queue_progress_update(self, update_type: str, **kwargs):
        """
        Queue a progress update for the UI thread to process.
        
        Args:
            update_type: Type of update ('progress', 'stage_start', 'stage_complete', 'error', 'complete', 'warning', 'info')
            **kwargs: Additional update data
        """
        update = {'type': update_type, **kwargs}
        self.progress_callback_queue.append(update)
    
    def _queue_stage_start(self, stage_name: str, total_items: int = 0, percentage: float = 0):
        """
        Queue a stage start update.
        
        Args:
            stage_name: Name of the starting stage
            total_items: Total items in the stage
            percentage: Overall progress percentage
        """
        self._queue_progress_update(
            'stage_start',
            stage_name=stage_name,
            total_items=total_items,
            percentage=percentage
        )
    
    def _queue_stage_progress(self, stage_name: str, percentage: float, 
                            items_completed: int = 0, total_items: int = 0, 
                            current_item: str = "", stage_percentage: float = 0):
        """
        Queue a stage progress update.
        
        Args:
            stage_name: Name of the current stage
            percentage: Overall progress percentage
            items_completed: Items completed in current stage
            total_items: Total items in current stage
            current_item: Description of current item being processed
            stage_percentage: Progress percentage within current stage
        """
        self._queue_progress_update(
            'progress',
            stage_name=stage_name,
            percentage=percentage,
            items_completed=items_completed,
            total_items=total_items,
            current_item=current_item,
            stage_percentage=stage_percentage
        )
    
    def _queue_stage_complete(self, stage_name: str, success: bool = True, percentage: float = 0):
        """
        Queue a stage completion update.
        
        Args:
            stage_name: Name of the completed stage
            success: Whether the stage completed successfully
            percentage: Overall progress percentage
        """
        self._queue_progress_update(
            'stage_complete',
            stage_name=stage_name,
            success=success,
            percentage=percentage
        )
    
    def _queue_warning(self, stage_name: str, message: str):
        """
        Queue a warning message update.
        
        Args:
            stage_name: Name of the stage where warning occurred
            message: Warning message
        """
        self._queue_progress_update(
            'warning',
            stage_name=stage_name,
            message=message
        )
    
    def _queue_info(self, stage_name: str, message: str):
        """
        Queue an informational message update.
        
        Args:
            stage_name: Name of the stage for the info
            message: Informational message
        """
        self._queue_progress_update(
            'info',
            stage_name=stage_name,
            message=message
        )
    
    def _queue_error(self, message: str):
        """
        Queue an error update.
        
        Args:
            message: Error message
        """
        self._queue_progress_update(
            'error',
            message=message
        )
    
    def _queue_completion(self, success: bool = True, result_data: dict = None):
        """
        Queue a processing completion update.
        
        Args:
            success: Whether processing completed successfully
            result_data: Results from processing
        """
        self._queue_progress_update(
            'complete',
            success=success,
            result_data=result_data or {}
        )
    
    def _handle_stage_transition(self, from_stage: str, to_stage: str, total_items: int = 0):
        """
        Handle transition between processing stages.
        
        Args:
            from_stage: Previous stage name
            to_stage: New stage name
            total_items: Total items in new stage
        """
        # Complete previous stage
        if from_stage:
            self._queue_progress_update(
                'stage_complete',
                stage_name=from_stage,
                success=True
            )
        
        # Start new stage
        self._queue_progress_update(
            'stage_start',
            stage_name=to_stage,
            total_items=total_items,
            percentage=0
        )
        
    def _handle_processing_error(self, error_message: str, preserved_state=None):
        """Handle processing errors while preserving user inputs and providing comprehensive guidance."""
        # Stop processing state
        self._set_processing_state(False)
        
        # Import error handler to get detailed error information
        try:
            from ..errors import error_handler
            
            # Check if we have detailed error information from the core engine
            if error_handler.has_errors():
                error_summary = error_handler.get_error_summary()
                
                # Use the most recent error for detailed guidance
                if error_summary['errors']:
                    latest_error = error_summary['errors'][-1]  # Most recent error
                    self._display_core_engine_error(latest_error, preserved_state)
                    return
                elif error_summary['warnings']:
                    # If only warnings, treat as a processing issue
                    latest_warning = error_summary['warnings'][-1]
                    error_message = f"Processing completed with warnings: {latest_warning['message']}"
            
        except ImportError:
            # Fallback if error handler not available
            pass
        
        # Determine if this is a retry scenario
        if self._current_retry_count > 0:
            # This is a retry failure - show comprehensive troubleshooting
            self._show_processing_failure_guidance_dialog(error_message, self.state.current_stage)
        else:
            # First failure - categorize and display the error using comprehensive error system
            self._display_categorized_error(error_message, preserved_state)
        
        # Restore inputs if preserved state is provided
        if preserved_state:
            self._restore_inputs_from_preserved(preserved_state)
        
        # Update status based on retry count
        if self._current_retry_count >= self._max_retries:
            self.status_var.set(f"Processing failed after {self._max_retries} attempts - see troubleshooting guide")
        else:
            self.status_var.set("Processing failed - error guidance available")
    
    def _display_core_engine_error(self, error_info: dict, preserved_state=None):
        """
        Display error from the core processing engine with enhanced user guidance.
        
        Args:
            error_info: Error information from the core engine error handler
            preserved_state: Preserved input state for error recovery
        """
        error_category = error_info.get('category', 'unknown')
        error_message = error_info.get('message', 'Unknown error')
        error_details = error_info.get('details', '')
        suggested_actions = error_info.get('suggested_actions', [])
        
        # Convert core engine error categories to user-friendly guidance
        if error_category == 'authentication':
            self._show_authentication_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'document_parsing':
            self._show_document_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'audio_processing':
            self._show_audio_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'alignment':
            self._show_alignment_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'anki_generation':
            self._show_anki_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'network':
            self._show_network_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'file_system':
            self._show_filesystem_error_dialog_enhanced(error_message, error_details, suggested_actions)
        elif error_category == 'input_validation':
            self._show_input_error_dialog_enhanced(error_message, error_details, suggested_actions)
        else:
            # Fallback to generic error dialog with core engine details
            self._show_generic_error_dialog_enhanced(error_message, error_details, suggested_actions)
    
    def _show_authentication_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced authentication error dialog with core engine details."""
        title = "Google Services Connection Error"
        
        guidance = f"""Connection to Google services failed:

Error Details: {details if details else message}

🔧 Quick Solutions:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
📋 Additional Steps:
• Ensure your Google Docs/Sheets URL is accessible in your browser
• Check that the document is shared with your Google account
• Verify you have 'View' permissions for the document
• Try refreshing your Google authentication

🏢 Corporate/School Networks:
• Contact IT about Google API access restrictions
• Check if proxy settings need configuration
• Verify Google services aren't blocked

💡 Authentication Reset:
1. Close this application
2. Delete 'token.json' file if it exists (forces re-authentication)
3. Restart the application and try again"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_document_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced document error dialog with core engine details."""
        title = "Document Processing Error"
        
        guidance = f"""Failed to process your vocabulary document:

Error Details: {details if details else message}

🔧 Recommended Actions:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
📋 Document Requirements:
• Must be a Google Docs document or Google Sheets spreadsheet
• Should contain a clear table with vocabulary data
• First column: English words/phrases
• Second column: Cantonese words/phrases
• Include column headers (e.g., "English", "Cantonese")

🔍 Troubleshooting Steps:
1. Open the document in your browser to verify it loads
2. Check that it contains a properly formatted table
3. Ensure vocabulary entries are in separate rows
4. Remove any merged cells or complex formatting
5. Verify the document isn't password protected

📝 Example Format:
| English    | Cantonese |
|------------|-----------|
| Hello      | 你好      |
| Thank you  | 多謝      |"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_audio_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced audio error dialog with core engine details."""
        title = "Audio Processing Error"
        
        guidance = f"""Failed to process your audio file:

Error Details: {details if details else message}

🔧 Immediate Solutions:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
🎵 Audio Requirements:
• Supported formats: WAV, MP3, M4A, FLAC, OGG
• Clear speech with minimal background noise
• Each vocabulary word pronounced distinctly
• 1-2 second pauses between words
• Words spoken in same order as document

🔧 Audio Fixes:
1. Convert to WAV format for best compatibility
2. Use audio editing software to:
   - Increase volume if too quiet
   - Remove background noise
   - Ensure proper format encoding
3. Re-record if audio quality is poor

📱 Recording Tips:
• Use a good quality microphone
• Record in a quiet environment
• Speak clearly at normal volume
• Keep microphone 6-12 inches from mouth
• Test recording levels before starting"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_alignment_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced alignment error dialog with core engine details."""
        title = "Audio-Vocabulary Alignment Issue"
        
        guidance = f"""Problem aligning your vocabulary with audio:

Error Details: {details if details else message}

🔧 Alignment Solutions:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
🎯 Common Alignment Issues:
• Number of vocabulary words doesn't match audio segments
• Audio contains extra words not in document
• Document has words not spoken in audio
• Audio quality makes word boundaries unclear

✅ How to Fix:
1. Verify vocabulary count matches audio:
   - Count words in your document
   - Count words spoken in audio
   - Ensure they match exactly

2. Check word order:
   - Audio should follow document order
   - No skipped or repeated words

3. Improve audio quality:
   - Clearer pronunciation
   - Better pauses between words
   - Less background noise

4. Simplify vocabulary:
   - Start with fewer words (5-10)
   - Use single words rather than phrases
   - Test with simple vocabulary first"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_anki_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced Anki generation error dialog with core engine details."""
        title = "Anki Deck Creation Error"
        
        guidance = f"""Failed to create your Anki deck:

Error Details: {details if details else message}

🔧 Quick Fixes:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
💾 Common Issues:
• Insufficient disk space in output directory
• Output file is open in Anki or another program
• No write permissions for output location
• Audio files became inaccessible during processing

🛠️ Solutions:
1. Check disk space:
   - Ensure at least 100MB free space
   - Clear temporary files if needed

2. Close other programs:
   - Close Anki if it's running
   - Close any media players using audio files

3. Try different output location:
   - Use Desktop or Documents folder
   - Avoid network drives or cloud folders

4. Run as administrator (Windows):
   - Right-click application → "Run as administrator"
   - This can resolve permission issues"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_network_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced network error dialog with core engine details."""
        title = "Network Connection Error"
        
        guidance = f"""Network connection problem:

Error Details: {details if details else message}

🔧 Connection Fixes:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
🌐 Network Troubleshooting:
1. Check internet connection:
   - Try opening Google Docs in your browser
   - Verify other websites work normally

2. Firewall/Antivirus:
   - Temporarily disable to test
   - Add application to allowed programs

3. Corporate networks:
   - Contact IT about Google API access
   - Check proxy settings
   - Verify Google services aren't blocked

4. Retry timing:
   - Wait a few minutes and try again
   - Google services may be temporarily unavailable"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_filesystem_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced filesystem error dialog with core engine details."""
        title = "File System Error"
        
        guidance = f"""File system problem:

Error Details: {details if details else message}

🔧 File System Fixes:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
💾 Common Solutions:
1. Check disk space:
   - Ensure sufficient free space (at least 100MB)
   - Clear temporary files and recycle bin

2. File permissions:
   - Try running as administrator (Windows)
   - Check folder write permissions
   - Use a different output location

3. File paths:
   - Avoid very long file paths
   - Use simple folder names without special characters
   - Don't use network drives or cloud sync folders

4. System issues:
   - Restart the application
   - Restart your computer if problems persist"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_input_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced input validation error dialog with core engine details."""
        title = "Input Validation Error"
        
        guidance = f"""Problem with your input files:

Error Details: {details if details else message}

🔧 Input Fixes:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
📋 Input Checklist:
✓ Google Docs/Sheets URL:
  - Starts with https://docs.google.com/ or https://sheets.google.com/
  - Document is accessible (try opening in browser)
  - Contains vocabulary table with clear structure

✓ Audio File:
  - Supported format (WAV, MP3, M4A, FLAC, OGG)
  - File exists and isn't corrupted
  - Contains clear speech
  - Reasonable file size (not too large or small)

🔍 Quick Tests:
1. Open document URL in your browser
2. Play audio file in media player
3. Verify both files are accessible"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_generic_error_dialog_enhanced(self, message: str, details: str, actions: list):
        """Show enhanced generic error dialog with core engine details."""
        title = "Processing Error"
        
        guidance = f"""An error occurred during processing:

Error Details: {details if details else message}

🔧 Suggested Actions:
"""
        
        # Add specific actions from core engine
        for i, action in enumerate(actions[:3], 1):
            guidance += f"{i}. {action}\n"
        
        guidance += """
🛠️ General Troubleshooting:
1. Verify inputs:
   - Check document URL works in browser
   - Test audio file plays correctly
   - Ensure both files are accessible

2. System resources:
   - Close other applications to free memory
   - Ensure sufficient disk space
   - Check system performance

3. Retry strategies:
   - Try again with the same inputs
   - Test with simpler inputs (fewer vocabulary words)
   - Restart the application

4. Get help:
   - Use verbose mode for detailed error information
   - Check application logs for technical details"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _display_categorized_error(self, error_message: str, preserved_state=None):
        """
        Display error using categorized error system with user-friendly formatting.
        
        Args:
            error_message: The error message to categorize and display
            preserved_state: Preserved input state for error recovery
        """
        # Categorize the error based on message content
        error_category, error_details = self._categorize_error_message(error_message)
        
        # Create appropriate error dialog based on category
        if error_category == ErrorCategory.INPUT_VALIDATION:
            self._show_input_error_dialog(error_details)
        elif error_category == ErrorCategory.AUTHENTICATION:
            self._show_authentication_error_dialog(error_details)
        elif error_category == ErrorCategory.DOCUMENT_PARSING:
            self._show_document_error_dialog(error_details)
        elif error_category == ErrorCategory.AUDIO_PROCESSING:
            self._show_audio_error_dialog(error_details)
        elif error_category == ErrorCategory.ALIGNMENT:
            self._show_alignment_error_dialog(error_details)
        elif error_category == ErrorCategory.ANKI_GENERATION:
            self._show_anki_error_dialog(error_details)
        elif error_category == ErrorCategory.NETWORK:
            self._show_network_error_dialog(error_details)
        elif error_category == ErrorCategory.FILE_SYSTEM:
            self._show_filesystem_error_dialog(error_details)
        else:
            # Fallback to generic error dialog
            self._show_generic_error_dialog(error_message)
    
    def _categorize_error_message(self, error_message: str) -> tuple[ErrorCategory, dict]:
        """
        Categorize error message and extract relevant details.
        
        Args:
            error_message: The error message to categorize
            
        Returns:
            Tuple of (ErrorCategory, error_details_dict)
        """
        error_lower = error_message.lower()
        
        # Alignment errors (check before audio processing to catch alignment-specific terms)
        if any(keyword in error_lower for keyword in ['alignment', 'mismatch', 'segments', 'sync']):
            return ErrorCategory.ALIGNMENT, {
                'message': error_message,
                'type': 'alignment',
                'severity': 'warning' if 'mismatch' in error_lower else 'error'
            }
        
        # Input validation errors
        elif any(keyword in error_lower for keyword in ['url', 'invalid format', 'file not found', 'unsupported format']):
            return ErrorCategory.INPUT_VALIDATION, {
                'message': error_message,
                'type': 'input_validation',
                'severity': 'error'
            }
        
        # File system errors (check before authentication to catch file permission issues)
        elif any(keyword in error_lower for keyword in ['disk space', 'write', 'read', 'directory']):
            return ErrorCategory.FILE_SYSTEM, {
                'message': error_message,
                'type': 'file_system',
                'severity': 'error'
            }
        
        # Authentication errors
        elif any(keyword in error_lower for keyword in ['authentication', 'credentials', 'permission', 'access denied', '403']):
            return ErrorCategory.AUTHENTICATION, {
                'message': error_message,
                'type': 'authentication',
                'severity': 'error'
            }
        
        # Document parsing errors
        elif any(keyword in error_lower for keyword in ['document', 'parsing', 'table', 'vocabulary', '404', 'not found']):
            return ErrorCategory.DOCUMENT_PARSING, {
                'message': error_message,
                'type': 'document_parsing',
                'severity': 'error'
            }
        
        # Audio processing errors
        elif any(keyword in error_lower for keyword in ['audio', 'sound', 'wav', 'mp3', 'duration', 'silent', 'codec']):
            return ErrorCategory.AUDIO_PROCESSING, {
                'message': error_message,
                'type': 'audio_processing',
                'severity': 'error'
            }
        
        # Anki generation errors
        elif any(keyword in error_lower for keyword in ['anki', 'package', 'generation', 'cards', 'deck']):
            return ErrorCategory.ANKI_GENERATION, {
                'message': error_message,
                'type': 'anki_generation',
                'severity': 'error'
            }
        
        # Network errors
        elif any(keyword in error_lower for keyword in ['network', 'connection', 'timeout', 'internet', 'offline']):
            return ErrorCategory.NETWORK, {
                'message': error_message,
                'type': 'network',
                'severity': 'error'
            }
        
        # File system errors (remaining cases)
        elif any(keyword in error_lower for keyword in ['disk space']):
            return ErrorCategory.FILE_SYSTEM, {
                'message': error_message,
                'type': 'file_system',
                'severity': 'error'
            }
        
        # Default to generic system error
        else:
            return ErrorCategory.FILE_SYSTEM, {
                'message': error_message,
                'type': 'system',
                'severity': 'error'
            }
    
    def _show_input_error_dialog(self, error_details: dict):
        """Show input validation error dialog with specific guidance."""
        title = "Input Validation Error"
        message = error_details['message']
        
        # Provide specific guidance based on error content
        if 'url' in message.lower():
            guidance = """Please check your Google Docs/Sheets URL:

• Ensure it starts with 'https://docs.google.com/' or 'https://sheets.google.com/'
• Copy the URL directly from your browser address bar
• Make sure the document is shared with appropriate permissions
• Verify the document exists and is accessible

Example valid URLs:
• Google Docs: https://docs.google.com/document/d/1ABC...XYZ/edit
• Google Sheets: https://sheets.google.com/spreadsheets/d/1ABC...XYZ/edit

Common URL Issues:
• Missing 'https://' at the beginning
• Using shortened URLs (bit.ly, tinyurl) - use the full URL instead
• Document is private or has restricted access
• Document has been deleted or moved

Quick Test: Try opening the URL in your browser to verify it works."""
        
        elif 'file not found' in message.lower():
            guidance = """Audio file could not be found:

• Check that the file path is correct
• Ensure the file has not been moved or deleted
• Try browsing for the file again using the 'Browse...' button
• Use the full file path if the relative path is not working

Troubleshooting Steps:
1. Navigate to the file location in your file explorer
2. Verify the file still exists at that location
3. Check if the file has been moved to a different folder
4. Ensure you have read permissions for the file
5. Try copying the file to a simpler path (like Desktop) and select it again

File Path Tips:
• Avoid paths with special characters or spaces
• Use shorter folder names when possible
• Ensure the file isn't on a network drive that's disconnected"""
        
        elif 'unsupported format' in message.lower():
            guidance = """Audio file format is not supported:

Supported Formats: MP3, WAV, M4A, FLAC, OGG

Conversion Options:
• Free Software: Audacity, VLC Media Player, FFmpeg
• Online Converters: CloudConvert, Online-Audio-Converter
• Built-in Tools: Windows Media Player, iTunes

Conversion Steps:
1. Open your audio file in conversion software
2. Choose 'Export' or 'Convert' from the menu
3. Select MP3 or WAV as the output format
4. Save the converted file
5. Use the converted file in this application

Quality Recommendations:
• MP3: 128 kbps or higher for good quality
• WAV: Uncompressed for best quality (larger file size)
• Ensure the file extension matches the actual format"""
        
        else:
            guidance = """Please check your inputs:

Input Checklist:
• ✓ Google Docs/Sheets URL is correct and accessible
• ✓ Audio file exists and is in a supported format (MP3, WAV, M4A, FLAC, OGG)
• ✓ All required fields are filled out
• ✓ You have internet connection for Google Docs access
• ✓ Output directory has write permissions

Quick Validation:
1. Test the Google Docs URL by opening it in your browser
2. Play the audio file to ensure it works
3. Check that you can create files in the output directory

If problems persist, try using different input files to isolate the issue."""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_authentication_error_dialog(self, error_details: dict):
        """Show authentication error dialog with specific guidance."""
        title = "Authentication Error"
        message = error_details['message']
        
        guidance = """Google API authentication failed:

Initial Setup (First Time):
1. Ensure 'credentials.json' file is present in the application directory
2. Check that the Google Docs/Sheets API is enabled in your Google Cloud project
3. Verify your credentials have the necessary permissions
4. Run the authentication flow when prompted

Document Access Issues:
• Check that the document is shared with your Google account
• Ensure the document has 'View' or 'Edit' permissions for your account
• Make sure the document is not private or restricted
• Try accessing the document in your browser first to verify access

Authentication Troubleshooting:
1. Delete 'token.json' file if it exists (forces re-authentication)
2. Clear browser cookies for Google accounts
3. Try logging out and back into your Google account
4. Ensure you're using the correct Google account

Corporate/School Networks:
• Contact your IT administrator about Google API access
• Check if proxy settings need to be configured
• Verify that Google services are not blocked by your network
• Some organizations require special permissions for API access

Error Code Reference:
• 401 Unauthorized: Invalid or expired credentials
• 403 Forbidden: Insufficient permissions or document access denied
• 404 Not Found: Document doesn't exist or you don't have access

Quick Fix: Try opening the document URL in your browser. If you can't access it there, the problem is with document permissions, not the application."""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_document_error_dialog(self, error_details: dict):
        """Show document parsing error dialog with specific guidance."""
        title = "Document Processing Error"
        message = error_details['message']
        
        if '404' in message or 'not found' in message.lower():
            guidance = """Document could not be found:

URL Verification:
• Verify the document URL is correct and complete
• Check that the document has not been deleted or moved
• Ensure the document ID in the URL is valid
• Try accessing the document in your browser to confirm it exists

Common Causes:
• Document was deleted by the owner
• Document URL was copied incorrectly (missing parts)
• Document is in a different Google account
• Document was moved to trash

Troubleshooting Steps:
1. Copy the URL again directly from your browser address bar
2. Check your Google Drive to see if the document still exists
3. Contact the document owner if it's not your document
4. Look in your Google Drive trash if you accidentally deleted it

Document Sharing:
• Ensure the document is shared with 'Anyone with the link' or your specific account
• Check that sharing permissions haven't been revoked
• Verify you're logged into the correct Google account"""
        
        elif 'table' in message.lower() or 'vocabulary' in message.lower():
            guidance = """No vocabulary table found in the document:

Required Document Structure:
• Document must contain a table with vocabulary data
• Table should have at least two columns (English and Cantonese)
• First row should contain column headers (e.g., "English", "Cantonese")
• Subsequent rows should contain vocabulary entries

Table Format Requirements:
• Use a proper table (Insert > Table in Google Docs/Sheets)
• Avoid using spaces or tabs to align text (use actual table cells)
• Each vocabulary word should be in its own row
• Keep one word/phrase per cell

Common Issues:
• Text is formatted as paragraphs instead of a table
• Table has merged cells or complex formatting
• Headers are missing or in wrong format
• Empty rows between vocabulary entries
• Table contains only headers without actual vocabulary

Google Docs Example:
| English | Cantonese |
|---------|-----------|
| Hello   | 你好      |
| Thank you | 多謝    |

Google Sheets Example:
A1: English    B1: Cantonese
A2: Hello      B2: 你好
A3: Thank you  B3: 多謝

Verification Steps:
1. Open the document and locate the vocabulary table
2. Ensure it has clear column headers
3. Check that vocabulary entries are in separate rows
4. Verify there are no empty cells in the vocabulary area"""
        
        else:
            guidance = """Document processing failed:

Document Format Issues:
• Check that the document format is supported (Google Docs or Sheets)
• Ensure the document is not corrupted or has formatting issues
• Try accessing the document manually to verify it loads correctly
• Make sure the document contains the expected vocabulary table structure

Document Content Requirements:
• Must be a Google Docs document or Google Sheets spreadsheet
• Should contain a clear table with vocabulary data
• Table must have identifiable column headers
• Vocabulary entries should be properly formatted

Troubleshooting Steps:
1. Open the document in your browser to check if it loads properly
2. Verify the document contains a vocabulary table
3. Check that the table format matches requirements
4. Try creating a simple test document with a few vocabulary words
5. Ensure the document isn't password protected or has restricted access

If the document works in your browser but fails here:
• The document might have complex formatting that's hard to parse
• Try simplifying the table structure
• Remove any merged cells or complex formatting
• Use a basic table with simple text entries"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_audio_error_dialog(self, error_details: dict):
        """Show audio processing error dialog with specific guidance."""
        title = "Audio Processing Error"
        message = error_details['message']
        
        if 'duration' in message.lower() or 'short' in message.lower():
            guidance = """Audio duration issue detected:

Minimum Requirements:
• Audio file must be at least 1 second long
• Should contain clear speech content
• Avoid files that are just silence or very brief sounds

Common Causes:
• Audio file is corrupted or truncated
• Recording was stopped too early
• File contains only silence or background noise
• Audio codec issues preventing proper duration detection

Solutions:
1. Check the audio file by playing it in a media player
2. Verify the file actually contains speech
3. Re-record the audio if it's too short
4. Use audio editing software to check the actual duration
5. Try converting to a different format (MP3 or WAV)

Recording Tips for Next Time:
• Record at least 2-3 seconds of audio per vocabulary word
• Leave small pauses between words
• Ensure clear pronunciation
• Test your recording setup before recording all vocabulary"""
        
        elif 'format' in message.lower() or 'codec' in message.lower():
            guidance = """Audio format issue detected:

Supported Formats: MP3, WAV, M4A, FLAC, OGG

Format Conversion Solutions:
• Free Software: Audacity, VLC Media Player, FFmpeg
• Online Tools: CloudConvert, Online-Audio-Converter.com
• Built-in Tools: Windows Media Player, iTunes, QuickTime

Step-by-Step Conversion:
1. Download and install Audacity (free audio editor)
2. Open your audio file in Audacity
3. Go to File > Export > Export as MP3 (or WAV)
4. Choose quality settings (128 kbps MP3 is usually sufficient)
5. Save the converted file
6. Use the converted file in this application

Troubleshooting Codec Issues:
• Try converting to WAV format (most compatible)
• Check if the file plays properly in other media players
• Ensure the file isn't corrupted during transfer
• Avoid proprietary formats like WMA or AAC when possible

Quality Recommendations:
• MP3: 128-320 kbps for speech
• WAV: 44.1 kHz, 16-bit for best compatibility
• Keep original file as backup before converting"""
        
        elif 'silent' in message.lower() or 'amplitude' in message.lower():
            guidance = """Audio appears to be silent or too quiet:

Volume Issues:
• Check that the audio file contains audible speech
• Increase the recording volume if the audio is too quiet
• Verify the microphone was working during recording
• Ensure speakers/headphones are working to test the file

Audio Enhancement Solutions:
1. Use Audacity to amplify quiet audio:
   - Open the audio file in Audacity
   - Select all audio (Ctrl+A)
   - Go to Effect > Amplify
   - Increase the amplification (try 6-12 dB)
   - Export the enhanced audio

2. Check recording levels:
   - Test your microphone before recording
   - Speak at normal volume, close to the microphone
   - Avoid background noise and echo
   - Record in a quiet environment

3. Verify audio content:
   - Play the file in a media player with volume at maximum
   - Check if there's any sound at all
   - Look for visual waveforms in audio editing software

Recording Best Practices:
• Record in a quiet room
• Speak clearly and at normal volume
• Keep microphone 6-12 inches from your mouth
• Test recording levels before starting
• Monitor audio levels during recording"""
        
        else:
            guidance = """Audio processing failed:

General Audio Troubleshooting:
1. File Integrity Check:
   - Try playing the audio file in different media players
   - Check if the file opens without errors
   - Verify the file size is reasonable (not 0 bytes)

2. Format Compatibility:
   - Convert to WAV or MP3 format for best compatibility
   - Ensure the file extension matches the actual format
   - Avoid unusual or proprietary audio formats

3. Audio Content Verification:
   - Confirm the audio contains clear speech
   - Check that vocabulary words are pronounced distinctly
   - Ensure audio corresponds to the vocabulary in your document

4. Technical Requirements:
   - Sample rate: 44.1 kHz or 48 kHz recommended
   - Bit depth: 16-bit or 24-bit
   - Channels: Mono or stereo both work
   - Duration: At least 1 second per vocabulary word

5. Common Solutions:
   - Re-encode the audio file using Audacity or similar software
   - Try a different audio file to test if the issue is file-specific
   - Check available disk space and memory
   - Restart the application and try again

If problems persist, try creating a simple test audio file with just 2-3 vocabulary words to isolate the issue."""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_alignment_error_dialog(self, error_details: dict):
        """Show alignment error dialog with specific guidance."""
        title = "Audio-Vocabulary Alignment Issue"
        message = error_details['message']
        severity = error_details.get('severity', 'error')
        
        if 'mismatch' in message.lower():
            if severity == 'warning':
                guidance = """Alignment mismatch detected (this may still work):

• Review the generated cards for accuracy after processing
• The number of audio segments doesn't exactly match vocabulary entries
• Consider adjusting audio segmentation parameters if results are poor
• Verify that the audio and vocabulary correspond to each other

You can proceed with processing, but check the results carefully."""
            else:
                guidance = """Severe alignment mismatch detected:

• Verify that the audio contains all vocabulary words from the document
• Check that the vocabulary table is complete and matches the audio
• Ensure the audio and document correspond to each other
• Consider re-recording the audio with clearer pronunciation
• Make sure vocabulary is spoken in the same order as listed in the document"""
        
        elif 'segments' in message.lower():
            guidance = """Audio segmentation issue:

• Check that the audio contains clear speech
• Ensure the audio is not too quiet or noisy
• Try adjusting audio processing parameters
• Verify the audio file contains the expected vocabulary
• Consider using higher quality audio recording"""
        
        else:
            guidance = """Audio-vocabulary alignment failed:

• Ensure audio and vocabulary document match each other
• Check that both inputs contain the same vocabulary items
• Verify the audio quality is sufficient for processing
• Consider re-recording with clearer pronunciation"""
        
        show_retry = severity != 'warning'  # Allow proceeding for warnings
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=show_retry)
    
    def _show_anki_error_dialog(self, error_details: dict):
        """Show Anki generation error dialog with specific guidance."""
        title = "Anki Package Generation Error"
        message = error_details['message']
        
        if 'permission' in message.lower() or 'access' in message.lower():
            guidance = """File permission error:

• Check write permissions for the output directory
• Ensure the output file is not open in another application (like Anki)
• Try saving to a different location
• Run the application as administrator if necessary (Windows)"""
        
        elif 'space' in message.lower() or 'disk' in message.lower():
            guidance = """Insufficient disk space:

• Free up disk space on your computer
• Choose a different output location with more space
• Remove temporary files and clear your recycle bin
• Check available disk space in the output directory"""
        
        else:
            guidance = """Anki package generation failed:

• Check that all audio files are accessible
• Verify output directory permissions
• Ensure sufficient disk space is available
• Try generating the package again
• Check that no other application is using the output files"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_network_error_dialog(self, error_details: dict):
        """Show network error dialog with specific guidance."""
        title = "Network Connection Error"
        message = error_details['message']
        
        guidance = """Network connection issue:

• Check your internet connection
• Verify you can access Google Docs in your browser
• Try again in a few minutes (temporary network issues)
• Check if your firewall or antivirus is blocking the connection
• Ensure Google services are not blocked by your network

If using a corporate network:
• Contact your IT administrator about Google API access
• Check if proxy settings need to be configured"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_filesystem_error_dialog(self, error_details: dict):
        """Show file system error dialog with specific guidance."""
        title = "File System Error"
        message = error_details['message']
        
        guidance = """File system issue detected:

• Check available disk space
• Verify file and directory permissions
• Ensure the output directory is accessible
• Try using a different output location
• Close any applications that might be using the files
• Check that the file path is not too long (Windows limitation)

If the problem persists:
• Restart the application
• Try running as administrator (Windows)
• Check system logs for additional error details"""
        
        self._show_error_dialog_with_guidance(title, message, guidance, show_retry=True)
    
    def _show_generic_error_dialog(self, error_message: str):
        """Show generic error dialog for uncategorized errors."""
        title = "Processing Error"
        
        guidance = """An unexpected error occurred:

• Try the operation again
• Check that all inputs are valid
• Ensure sufficient system resources are available
• Restart the application if the problem persists

If this error continues to occur:
• Check the application logs for more details
• Try with different input files
• Contact support with the error details"""
        
        self._show_error_dialog_with_guidance(title, error_message, guidance, show_retry=True)
    
    def _show_error_dialog_with_guidance(self, title: str, message: str, guidance: str, show_retry: bool = True):
        """
        Show a comprehensive error dialog with guidance and retry options.
        
        Args:
            title: Dialog title
            message: Error message
            guidance: Detailed guidance text
            show_retry: Whether to show retry button
        """
        # Create custom dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x500")
        dialog.resizable(True, True)
        
        # Center the dialog on the parent window
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dialog layout
        dialog.grid_rowconfigure(1, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        
        # Error icon and title frame
        title_frame = ttk.Frame(dialog, padding="20 20 20 10")
        title_frame.grid(row=0, column=0, sticky="ew")
        
        # Error icon (using Unicode symbol)
        icon_label = ttk.Label(title_frame, text="⚠️", font=("Arial", 24))
        icon_label.grid(row=0, column=0, padx=(0, 15))
        
        # Title and message
        title_label = ttk.Label(title_frame, text=title, font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w")
        
        message_label = ttk.Label(title_frame, text=message, font=("Arial", 10), wraplength=500)
        message_label.grid(row=1, column=1, sticky="w", pady=(5, 0))
        
        title_frame.grid_columnconfigure(1, weight=1)
        
        # Guidance text frame
        guidance_frame = ttk.LabelFrame(dialog, text="How to Fix This", padding="15")
        guidance_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        guidance_frame.grid_rowconfigure(0, weight=1)
        guidance_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable text widget for guidance
        guidance_text = tk.Text(
            guidance_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#f8f9fa",
            relief="flat",
            padx=10,
            pady=10
        )
        guidance_scrollbar = ttk.Scrollbar(guidance_frame, orient="vertical")
        
        guidance_text.config(yscrollcommand=guidance_scrollbar.set)
        guidance_scrollbar.config(command=guidance_text.yview)
        
        guidance_text.grid(row=0, column=0, sticky="nsew")
        guidance_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Insert guidance text
        guidance_text.insert(1.0, guidance)
        guidance_text.config(state="disabled")  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(dialog, padding="20 10 20 20")
        button_frame.grid(row=2, column=0, sticky="ew")
        
        # Buttons
        if show_retry:
            retry_btn = ttk.Button(
                button_frame,
                text="Try Again",
                command=lambda: self._handle_retry_from_dialog(dialog)
            )
            retry_btn.grid(row=0, column=0, padx=(0, 10))
        
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy
        )
        close_btn.grid(row=0, column=1 if show_retry else 0)
        
        # Focus on close button
        close_btn.focus_set()
        
        # Handle dialog closing
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _handle_retry_from_dialog(self, dialog):
        """
        Handle retry action from error dialog with enhanced recovery.
        
        Args:
            dialog: The error dialog window to close
        """
        dialog.destroy()
        
        # Clear any previous errors
        self.error_handler.clear_errors()
        
        # Reset UI state for retry
        self._set_processing_state(False)
        
        # Preserve current inputs for potential restoration
        preserved_state = self._preserve_inputs_during_error()
        
        # Perform comprehensive input validation before retry
        validation_errors = self._validate_inputs_comprehensive()
        
        if validation_errors:
            # Show validation errors and guidance
            self.status_var.set("Please fix input issues before retrying")
            self._display_validation_errors(validation_errors)
            
            # Restore inputs after showing errors
            self._restore_inputs_from_preserved(preserved_state)
        else:
            # Inputs are valid, ready to retry
            self.status_var.set("Ready to retry - inputs validated successfully")
            
            # Re-validate current inputs to provide immediate feedback
            self._validate_current_inputs()
            
            # Show retry confirmation if user wants to proceed immediately
            self._show_retry_confirmation_dialog()
    
    def _show_retry_confirmation_dialog(self):
        """Show confirmation dialog for immediate retry after error recovery."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ready to Retry")
        dialog.geometry("450x300")
        dialog.resizable(False, False)
        
        # Center and configure dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Success icon and message
        success_frame = ttk.Frame(main_frame)
        success_frame.pack(fill="x", pady=(0, 20))
        
        success_icon = ttk.Label(success_frame, text="✅", font=("Arial", 24))
        success_icon.pack(side="left", padx=(0, 15))
        
        success_label = ttk.Label(
            success_frame,
            text="Inputs Validated Successfully",
            font=("Arial", 14, "bold")
        )
        success_label.pack(side="left")
        
        # Message
        message_label = ttk.Label(
            main_frame,
            text="Your inputs have been validated and appear to be correct. Would you like to try processing again now?",
            wraplength=400,
            font=("Arial", 10)
        )
        message_label.pack(pady=(0, 20))
        
        # Options frame
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill="x", pady=(0, 20))
        
        # Retry now button
        retry_now_btn = ttk.Button(
            options_frame,
            text="Yes, Try Processing Now",
            command=lambda: self._handle_immediate_retry_confirmed(dialog)
        )
        retry_now_btn.pack(fill="x", pady=(0, 10))
        
        # Review inputs button
        review_btn = ttk.Button(
            options_frame,
            text="Let Me Review Inputs First",
            command=lambda: self._handle_review_inputs_first(dialog)
        )
        review_btn.pack(fill="x")
        
        # Tips
        tips_label = ttk.Label(
            main_frame,
            text="Tip: If processing fails again, check your internet connection and ensure the Google document is accessible.",
            wraplength=400,
            font=("Arial", 9),
            foreground="gray"
        )
        tips_label.pack()
        
        # Focus on retry button
        retry_now_btn.focus_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _handle_immediate_retry_confirmed(self, dialog):
        """Handle confirmed immediate retry."""
        dialog.destroy()
        
        # Reset retry count for fresh attempt
        self._current_retry_count = 0
        
        # Start processing immediately
        self._start_processing()
    
    def _handle_review_inputs_first(self, dialog):
        """Handle user choice to review inputs before retry."""
        dialog.destroy()
        
        # Update status to encourage review
        self.status_var.set("Please review your inputs and click 'Generate Anki Deck' when ready")
        
        # Highlight the process button to draw attention
        self.process_btn.focus_set()
    
    def _show_processing_failure_guidance_dialog(self, error_message: str, stage_name: str = ""):
        """
        Show comprehensive guidance for processing failures.
        
        Args:
            error_message: The error that occurred during processing
            stage_name: The processing stage where the error occurred
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Processing Failed - Troubleshooting Guide")
        dialog.geometry("700x600")
        dialog.resizable(True, True)
        
        # Center and configure dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dialog layout
        dialog.grid_rowconfigure(1, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        
        # Header frame
        header_frame = ttk.Frame(dialog, padding="20 20 20 10")
        header_frame.grid(row=0, column=0, sticky="ew")
        
        # Error icon and title
        icon_label = ttk.Label(header_frame, text="🔧", font=("Arial", 24))
        icon_label.grid(row=0, column=0, padx=(0, 15))
        
        title_label = ttk.Label(header_frame, text="Processing Troubleshooting Guide", font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w")
        
        if stage_name:
            stage_label = ttk.Label(header_frame, text=f"Failed at: {stage_name}", font=("Arial", 10), foreground="red")
            stage_label.grid(row=1, column=1, sticky="w", pady=(5, 0))
        
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Notebook for organized guidance
        notebook = ttk.Notebook(dialog, padding="20 0 20 10")
        notebook.grid(row=1, column=0, sticky="nsew")
        
        # Quick Fixes tab
        quick_frame = ttk.Frame(notebook, padding="15")
        notebook.add(quick_frame, text="Quick Fixes")
        
        quick_text = tk.Text(
            quick_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#f8f9fa",
            relief="flat",
            padx=10,
            pady=10
        )
        quick_scrollbar = ttk.Scrollbar(quick_frame, orient="vertical")
        quick_text.config(yscrollcommand=quick_scrollbar.set)
        quick_scrollbar.config(command=quick_text.yview)
        
        quick_text.pack(side="left", fill="both", expand=True)
        quick_scrollbar.pack(side="right", fill="y")
        
        quick_fixes = self._get_quick_fixes_for_stage(stage_name, error_message)
        quick_text.insert(1.0, quick_fixes)
        quick_text.config(state="disabled")
        
        # Detailed Troubleshooting tab
        detailed_frame = ttk.Frame(notebook, padding="15")
        notebook.add(detailed_frame, text="Detailed Steps")
        
        detailed_text = tk.Text(
            detailed_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#f8f9fa",
            relief="flat",
            padx=10,
            pady=10
        )
        detailed_scrollbar = ttk.Scrollbar(detailed_frame, orient="vertical")
        detailed_text.config(yscrollcommand=detailed_scrollbar.set)
        detailed_scrollbar.config(command=detailed_text.yview)
        
        detailed_text.pack(side="left", fill="both", expand=True)
        detailed_scrollbar.pack(side="right", fill="y")
        
        detailed_steps = self._get_detailed_troubleshooting_steps(stage_name, error_message)
        detailed_text.insert(1.0, detailed_steps)
        detailed_text.config(state="disabled")
        
        # Common Issues tab
        common_frame = ttk.Frame(notebook, padding="15")
        notebook.add(common_frame, text="Common Issues")
        
        common_text = tk.Text(
            common_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#f8f9fa",
            relief="flat",
            padx=10,
            pady=10
        )
        common_scrollbar = ttk.Scrollbar(common_frame, orient="vertical")
        common_text.config(yscrollcommand=common_scrollbar.set)
        common_scrollbar.config(command=common_text.yview)
        
        common_text.pack(side="left", fill="both", expand=True)
        common_scrollbar.pack(side="right", fill="y")
        
        common_issues = self._get_common_issues_for_stage(stage_name, error_message)
        common_text.insert(1.0, common_issues)
        common_text.config(state="disabled")
        
        # Button frame
        button_frame = ttk.Frame(dialog, padding="20 10 20 20")
        button_frame.grid(row=2, column=0, sticky="ew")
        
        # Buttons
        retry_btn = ttk.Button(
            button_frame,
            text="Try Again",
            command=lambda: self._handle_retry_from_troubleshooting(dialog)
        )
        retry_btn.grid(row=0, column=0, padx=(0, 10))
        
        test_inputs_btn = ttk.Button(
            button_frame,
            text="Test My Inputs",
            command=lambda: self._handle_test_inputs_from_troubleshooting(dialog)
        )
        test_inputs_btn.grid(row=0, column=1, padx=(0, 10))
        
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy
        )
        close_btn.grid(row=0, column=2)
        
        # Focus on retry button
        retry_btn.focus_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _get_quick_fixes_for_stage(self, stage_name: str, error_message: str) -> str:
        """Get quick fixes based on processing stage and error."""
        stage_lower = stage_name.lower() if stage_name else ""
        error_lower = error_message.lower()
        
        if "authentication" in stage_lower or "auth" in error_lower:
            return """Quick Authentication Fixes:

1. ✓ Check Internet Connection
   - Ensure you have a stable internet connection
   - Try opening Google Docs in your browser
   
2. ✓ Re-authenticate
   - Delete 'token.json' file if it exists
   - Restart the application to trigger re-authentication
   
3. ✓ Verify Document Access
   - Open the document URL in your browser
   - Ensure you can view/edit the document
   
4. ✓ Check Credentials
   - Ensure 'credentials.json' file is in the application folder
   - Verify the file is not corrupted or empty"""
        
        elif "document" in stage_lower or "parsing" in stage_lower:
            return """Quick Document Fixes:

1. ✓ Verify Document URL
   - Copy the URL again from your browser
   - Ensure it's a Google Docs or Sheets URL
   
2. ✓ Check Document Structure
   - Open the document and verify it contains a vocabulary table
   - Ensure the table has clear headers (English, Cantonese)
   
3. ✓ Simplify Table Format
   - Remove any merged cells or complex formatting
   - Use a basic table with simple text entries
   
4. ✓ Test Document Access
   - Try opening the document in an incognito browser window
   - Verify the document is publicly accessible or shared with your account"""
        
        elif "audio" in stage_lower:
            return """Quick Audio Fixes:

1. ✓ Test Audio File
   - Play the audio file in a media player to verify it works
   - Check that it contains clear speech
   
2. ✓ Convert Audio Format
   - Convert to MP3 or WAV format using Audacity or online converter
   - Ensure the file extension matches the actual format
   
3. ✓ Check Audio Quality
   - Verify the audio is not too quiet or silent
   - Ensure it's at least 1 second long
   
4. ✓ Simplify File Path
   - Move the audio file to a simple location (like Desktop)
   - Avoid paths with special characters or very long names"""
        
        elif "alignment" in stage_lower:
            return """Quick Alignment Fixes:

1. ✓ Verify Content Match
   - Ensure audio contains all words from the vocabulary table
   - Check that words are spoken in the same order as listed
   
2. ✓ Improve Audio Quality
   - Use clear pronunciation for each word
   - Leave small pauses between words
   
3. ✓ Simplify Vocabulary
   - Start with a smaller vocabulary list (5-10 words)
   - Use single words rather than phrases initially
   
4. ✓ Check Audio Duration
   - Ensure audio is long enough for all vocabulary words
   - Verify each word has sufficient time for pronunciation"""
        
        else:
            return """General Quick Fixes:

1. ✓ Restart Application
   - Close and restart the Cantonese Anki Generator
   - This clears any temporary issues
   
2. ✓ Check System Resources
   - Ensure sufficient disk space (at least 1GB free)
   - Close other applications to free up memory
   
3. ✓ Verify All Inputs
   - Test the Google Docs URL in your browser
   - Play the audio file to ensure it works
   
4. ✓ Try Simpler Inputs
   - Use a smaller vocabulary list for testing
   - Try with a shorter, clearer audio file
   
5. ✓ Check Internet Connection
   - Ensure stable connection for Google Docs access
   - Try accessing other Google services to verify connectivity"""
    
    def _get_detailed_troubleshooting_steps(self, stage_name: str, error_message: str) -> str:
        """Get detailed troubleshooting steps for the specific stage."""
        return f"""Detailed Troubleshooting for {stage_name or 'Processing'} Stage:

Step 1: Identify the Root Cause
• Error Message Analysis: {error_message}
• Check if this is a recurring issue or first occurrence
• Note any patterns in when the error occurs

Step 2: Verify Prerequisites
• Internet connection is stable and working
• Google account has access to the specified document
• Audio file is accessible and in correct format
• Sufficient disk space available (minimum 1GB recommended)

Step 3: Test Components Individually
• Open Google Docs URL in browser - does it load correctly?
• Play audio file in media player - does it play without issues?
• Check output directory - can you create files there?

Step 4: Systematic Validation
• Re-enter the Google Docs URL by copying from browser
• Re-select the audio file using the Browse button
• Verify all input fields show green checkmarks
• Ensure no warning messages are displayed

Step 5: Environment Check
• Close other applications that might be using system resources
• Disable antivirus temporarily if it might be interfering
• Check Windows/Mac system requirements are met
• Verify no network restrictions are blocking Google API access

Step 6: Progressive Testing
• Try with a minimal test case (2-3 vocabulary words)
• Use a simple, short audio file for initial testing
• Gradually increase complexity once basic functionality works

Step 7: Log Analysis
• Check application logs for additional error details
• Note the exact sequence of actions that led to the error
• Document any error codes or technical messages

If all steps above don't resolve the issue, the problem may be:
• Temporary Google API service disruption
• Network configuration blocking API access
• Corrupted application installation
• System-specific compatibility issue

Contact support with the detailed error information and steps you've tried."""
    
    def _get_common_issues_for_stage(self, stage_name: str, error_message: str) -> str:
        """Get common issues and solutions for the specific stage."""
        stage_lower = stage_name.lower() if stage_name else ""
        
        if "authentication" in stage_lower:
            return """Common Authentication Issues:

Issue: "Access Denied" or "403 Forbidden"
Solution: 
• Document is not shared with your Google account
• Open document in browser and check sharing settings
• Ensure document has "Anyone with link can view" or is shared with your email

Issue: "Invalid Credentials" or "401 Unauthorized"
Solution:
• credentials.json file is missing or corrupted
• Download fresh credentials from Google Cloud Console
• Ensure Google Docs API is enabled in your project

Issue: "Token Expired" or Authentication Loop
Solution:
• Delete token.json file to force re-authentication
• Clear browser cookies for Google accounts
• Try logging out and back into Google account

Issue: Corporate/School Network Blocking
Solution:
• Contact IT administrator about Google API access
• Check if proxy configuration is needed
• Try using personal network/mobile hotspot for testing

Issue: Wrong Google Account
Solution:
• Ensure you're logged into the correct Google account
• Document may be in a different account than you're using
• Check account switching in browser before copying URL"""
        
        elif "document" in stage_lower:
            return """Common Document Issues:

Issue: "Document Not Found" or "404 Error"
Solution:
• Document URL is incomplete or incorrect
• Document has been deleted or moved to trash
• Copy URL directly from browser address bar
• Check document exists in your Google Drive

Issue: "No Vocabulary Table Found"
Solution:
• Document doesn't contain a proper table structure
• Table is formatted as text instead of actual table
• Use Insert > Table in Google Docs to create proper table
• Ensure first row contains headers like "English" and "Cantonese"

Issue: "Table Format Not Recognized"
Solution:
• Table has merged cells or complex formatting
• Remove all formatting and use simple table structure
• Avoid empty rows between vocabulary entries
• Each vocabulary word should be in its own table cell

Issue: "Permission Denied" for Document
Solution:
• Document sharing settings are too restrictive
• Change sharing to "Anyone with link can view"
• Ensure document is not password protected
• Check if document owner has revoked access

Issue: "Document Contains No Data"
Solution:
• Table exists but contains only headers, no vocabulary
• Add actual vocabulary entries below the header row
• Ensure each row has both English and Cantonese entries
• Remove any completely empty rows in the table"""
        
        elif "audio" in stage_lower:
            return """Common Audio Issues:

Issue: "Audio File Not Found" or "File Access Error"
Solution:
• File has been moved or deleted since selection
• File path contains special characters or is too long
• Move file to simple location like Desktop
• Re-select file using Browse button

Issue: "Unsupported Audio Format"
Solution:
• File format is not MP3, WAV, M4A, FLAC, or OGG
• Convert using Audacity, VLC, or online converter
• Ensure file extension matches actual format
• Avoid proprietary formats like WMA or AAC

Issue: "Audio Too Short" or "Duration Error"
Solution:
• Audio file is less than 1 second long
• File is corrupted or truncated
• Re-record with proper duration
• Check file plays correctly in media player

Issue: "Audio Appears Silent" or "No Speech Detected"
Solution:
• Recording volume was too low
• Microphone wasn't working during recording
• Use Audacity to amplify quiet audio
• Re-record with proper microphone setup

Issue: "Audio Processing Failed"
Solution:
• File is corrupted or has encoding issues
• Convert to WAV format for maximum compatibility
• Try different audio file to isolate issue
• Check available system memory and disk space"""
        
        else:
            return """Common General Issues:

Issue: "Network Connection Error"
Solution:
• Check internet connection stability
• Try accessing Google Docs in browser
• Disable VPN if using one
• Check firewall/antivirus settings

Issue: "Insufficient Disk Space"
Solution:
• Free up at least 1GB of disk space
• Choose different output directory with more space
• Clear temporary files and empty recycle bin
• Check disk space in output location

Issue: "Application Crashes or Freezes"
Solution:
• Close other applications to free memory
• Restart the Cantonese Anki Generator
• Check system meets minimum requirements
• Try with smaller input files initially

Issue: "Processing Takes Too Long"
Solution:
• Large audio files take more time to process
• Complex vocabulary tables require more processing
• Be patient - processing can take several minutes
• Check system resources aren't being used by other apps

Issue: "Generated Anki Package Won't Import"
Solution:
• Anki application may be outdated
• Package file may be corrupted during generation
• Try generating package again
• Check Anki import settings and compatibility

Issue: "Partial Results or Missing Cards"
Solution:
• Audio-vocabulary alignment wasn't perfect
• Some vocabulary words may not have been detected in audio
• Review generated cards for completeness
• Consider re-recording audio with clearer pronunciation"""
    
    def _handle_retry_from_troubleshooting(self, dialog):
        """Handle retry from troubleshooting dialog."""
        dialog.destroy()
        
        # Clear errors and reset retry count
        self.error_handler.clear_errors()
        self._current_retry_count = 0
        
        # Start processing again
        self._start_processing()
    
    def _handle_test_inputs_from_troubleshooting(self, dialog):
        """Handle input testing from troubleshooting dialog."""
        dialog.destroy()
        
        # Perform comprehensive input validation
        validation_errors = self._validate_inputs_comprehensive()
        
        if validation_errors:
            self._display_validation_errors(validation_errors)
        else:
            # Show success message
            messagebox.showinfo(
                "Input Validation Success",
                "All inputs are valid and ready for processing!\n\n"
                "✓ Google Docs URL is accessible\n"
                "✓ Audio file is in supported format\n"
                "✓ Output directory is writable\n\n"
                "You can now try processing again."
            )
            self.status_var.set("All inputs validated successfully - ready to process")
    
    def _validate_current_inputs(self):
        """Validate current inputs and provide immediate feedback."""
        # Validate URL if present
        url_value = self.url_var.get()
        if url_value:
            self._validate_url(url_value)
        
        # Validate audio file if present
        if self.state.audio_file_path:
            self._validate_audio_file(self.state.audio_file_path)
        
    def _start_processing(self):
        """Start the processing in a background thread with enhanced error handling."""
        # Clear any previous errors
        self.error_handler.clear_errors()
        
        # Reset retry count for fresh processing attempt
        self._current_retry_count = 0
        
        # Validate inputs before processing
        validation_errors = self._validate_inputs_comprehensive()
        if validation_errors:
            self._display_validation_errors(validation_errors)
            return
        
        # Preserve inputs before starting processing
        preserved_state = self._preserve_inputs_during_error()
        
        try:
            # Set processing state
            self._set_processing_state(True, "Initializing...")
            
            # Create progress callback
            progress_callback = self._create_progress_callback()
            
            # Start processing in background thread
            self.processing_thread = threading.Thread(
                target=self._run_processing_thread,
                args=(progress_callback, preserved_state),
                daemon=True
            )
            self.processing_thread.start()
            
        except Exception as e:
            # Handle any errors during processing setup
            self._handle_processing_error(f"Failed to start processing: {str(e)}", preserved_state)
    
    def _validate_inputs_comprehensive(self) -> list[ProcessingError]:
        """
        Perform comprehensive input validation using the error handler.
        
        Returns:
            List of validation errors, empty if all inputs are valid
        """
        errors = []
        
        # Validate Google Docs URL
        url_value = self.url_var.get()
        
        url_error = self.error_handler.validate_google_doc_url(url_value)
        if url_error:
            errors.append(url_error)
        
        # Validate audio file
        audio_error = self.error_handler.validate_audio_file_path(self.state.audio_file_path)
        if audio_error:
            errors.append(audio_error)
        
        # Validate output directory
        if not self._validate_output_directory(self.state.output_directory):
            errors.append(ProcessingError(
                category=ErrorCategory.FILE_SYSTEM,
                severity=ErrorSeverity.ERROR,
                message="Output directory is not accessible",
                details=f"Cannot write to output directory: {self.state.output_directory}",
                suggested_actions=[
                    "Choose a different output directory",
                    "Check directory permissions",
                    "Ensure sufficient disk space is available"
                ],
                error_code="OUTPUT_001"
            ))
        
        return errors
    
    def _display_validation_errors(self, errors: list[ProcessingError]):
        """
        Display validation errors in a comprehensive dialog.
        
        Args:
            errors: List of validation errors to display
        """
        if len(errors) == 1:
            # Single error - use specific error dialog
            error = errors[0]
            error_details = {
                'message': error.message,
                'type': error.category.value,
                'severity': error.severity.value
            }
            self._display_categorized_error(error.message)
        else:
            # Multiple errors - show summary dialog
            self._show_multiple_validation_errors_dialog(errors)
    
    def _show_multiple_validation_errors_dialog(self, errors: list[ProcessingError]):
        """
        Show dialog for multiple validation errors.
        
        Args:
            errors: List of validation errors
        """
        title = f"Multiple Input Issues ({len(errors)} problems found)"
        
        # Build error summary
        error_summary = "Please fix the following issues before processing:\n\n"
        for i, error in enumerate(errors, 1):
            error_summary += f"{i}. {error.message}\n"
        
        # Build comprehensive guidance
        guidance = "To fix these issues:\n\n"
        
        for i, error in enumerate(errors, 1):
            guidance += f"Issue {i}: {error.message}\n"
            for action in error.suggested_actions:
                guidance += f"  • {action}\n"
            guidance += "\n"
        
        guidance += "Once you've addressed these issues, try processing again."
        
        self._show_error_dialog_with_guidance(title, error_summary, guidance, show_retry=False)
    
    def _add_retry_mechanism_to_processing(self):
        """Add retry mechanism for failed processing operations."""
        # This will be integrated into the processing thread
        pass
    
    def _create_processing_retry_dialog(self, error_message: str, retry_count: int = 0):
        """
        Create a retry dialog for processing failures.
        
        Args:
            error_message: The error that occurred
            retry_count: Number of previous retry attempts
        """
        max_retries = 3
        
        if retry_count >= max_retries:
            # Max retries reached, show final error
            self._show_generic_error_dialog(f"Processing failed after {max_retries} attempts: {error_message}")
            return
        
        # Create retry dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Processing Failed - Retry Options")
        dialog.geometry("500x400")
        dialog.resizable(False, False)
        
        # Center and configure dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Error info
        error_frame = ttk.LabelFrame(main_frame, text="What Happened", padding="15")
        error_frame.pack(fill="x", pady=(0, 15))
        
        error_label = ttk.Label(
            error_frame,
            text=error_message,
            wraplength=450,
            font=("Arial", 10)
        )
        error_label.pack()
        
        # Retry options
        options_frame = ttk.LabelFrame(main_frame, text="What Would You Like to Do?", padding="15")
        options_frame.pack(fill="x", pady=(0, 15))
        
        # Retry immediately
        retry_immediate_btn = ttk.Button(
            options_frame,
            text=f"Try Again Immediately (Attempt {retry_count + 1}/{max_retries})",
            command=lambda: self._handle_immediate_retry(dialog, retry_count)
        )
        retry_immediate_btn.pack(fill="x", pady=(0, 10))
        
        # Check inputs and retry
        check_retry_btn = ttk.Button(
            options_frame,
            text="Check My Inputs and Try Again",
            command=lambda: self._handle_check_and_retry(dialog)
        )
        check_retry_btn.pack(fill="x", pady=(0, 10))
        
        # Cancel
        cancel_btn = ttk.Button(
            options_frame,
            text="Cancel and Fix Issues Manually",
            command=lambda: self._handle_cancel_retry(dialog)
        )
        cancel_btn.pack(fill="x")
        
        # Tips frame
        tips_frame = ttk.LabelFrame(main_frame, text="Troubleshooting Tips", padding="15")
        tips_frame.pack(fill="both", expand=True)
        
        tips_text = tk.Text(
            tips_frame,
            height=6,
            wrap=tk.WORD,
            font=("Arial", 9),
            bg="#f8f9fa"
        )
        tips_scrollbar = ttk.Scrollbar(tips_frame, orient="vertical")
        
        tips_text.config(yscrollcommand=tips_scrollbar.set)
        tips_scrollbar.config(command=tips_text.yview)
        
        tips_text.pack(side="left", fill="both", expand=True)
        tips_scrollbar.pack(side="right", fill="y")
        
        # Add troubleshooting tips
        tips_content = """Common solutions for processing failures:

• Check your internet connection for Google Docs access
• Verify the document URL is correct and accessible
• Ensure the audio file is not corrupted or too large
• Try using a different audio file format (MP3, WAV, M4A)
• Check that you have sufficient disk space
• Close other applications that might be using system resources
• Restart the application if problems persist"""
        
        tips_text.insert(1.0, tips_content)
        tips_text.config(state="disabled")
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def _handle_immediate_retry(self, dialog, retry_count: int):
        """
        Handle immediate retry without changing inputs.
        
        Args:
            dialog: Retry dialog to close
            retry_count: Current retry count
        """
        dialog.destroy()
        
        # Store retry count for processing thread
        self._current_retry_count = retry_count + 1
        
        # Restart processing with same inputs
        self._start_processing()
    
    def _handle_check_and_retry(self, dialog):
        """
        Handle check inputs and retry option.
        
        Args:
            dialog: Retry dialog to close
        """
        dialog.destroy()
        
        # Reset retry count
        self._current_retry_count = 0
        
        # Validate inputs and show feedback
        self._validate_current_inputs()
        
        # Update status to encourage user to check inputs
        self.status_var.set("Please review your inputs and try again when ready")
    
    def _handle_cancel_retry(self, dialog):
        """
        Handle cancel retry option.
        
        Args:
            dialog: Retry dialog to close
        """
        dialog.destroy()
        
        # Reset processing state
        self._set_processing_state(False)
        self.status_var.set("Processing cancelled - please check inputs and try again")
        
        # Reset retry count
        self._current_retry_count = 0
    
    def _provide_contextual_error_guidance(self, error_category: ErrorCategory, context: dict = None):
        """
        Provide contextual guidance based on error category and context.
        
        Args:
            error_category: Category of the error
            context: Additional context information
        """
        guidance_map = {
            ErrorCategory.INPUT_VALIDATION: self._get_input_validation_guidance,
            ErrorCategory.AUTHENTICATION: self._get_authentication_guidance,
            ErrorCategory.DOCUMENT_PARSING: self._get_document_parsing_guidance,
            ErrorCategory.AUDIO_PROCESSING: self._get_audio_processing_guidance,
            ErrorCategory.ALIGNMENT: self._get_alignment_guidance,
            ErrorCategory.ANKI_GENERATION: self._get_anki_generation_guidance,
            ErrorCategory.NETWORK: self._get_network_guidance,
            ErrorCategory.FILE_SYSTEM: self._get_filesystem_guidance
        }
        
        guidance_func = guidance_map.get(error_category, self._get_generic_guidance)
        return guidance_func(context or {})
    
    def _get_input_validation_guidance(self, context: dict) -> str:
        """Get guidance for input validation errors."""
        return """Input Validation Issues:

1. Google Docs/Sheets URL:
   • Must start with 'https://docs.google.com/' or 'https://sheets.google.com/'
   • Copy URL directly from browser address bar
   • Ensure document is shared with appropriate permissions

2. Audio File:
   • Supported formats: MP3, WAV, M4A, FLAC, OGG
   • File must exist and be accessible
   • Minimum duration: 1 second
   • Maximum recommended size: 500MB

3. Output Directory:
   • Must have write permissions
   • Sufficient disk space required
   • Directory must be accessible"""
    
    def _get_authentication_guidance(self, context: dict) -> str:
        """Get guidance for authentication errors."""
        return """Authentication Issues:

1. Google API Setup:
   • Ensure 'credentials.json' file is present
   • Check Google Docs/Sheets API is enabled
   • Verify credentials have necessary permissions

2. Document Access:
   • Document must be shared with your Google account
   • Check 'View' or 'Edit' permissions
   • Ensure document is not private/restricted

3. Network Access:
   • Check internet connection
   • Verify firewall/antivirus settings
   • Corporate networks may need proxy configuration"""
    
    def _get_document_parsing_guidance(self, context: dict) -> str:
        """Get guidance for document parsing errors."""
        return """Document Processing Issues:

1. Document Structure:
   • Must contain a table with vocabulary data
   • At least two columns (English and Cantonese)
   • First row should contain headers
   • Subsequent rows contain vocabulary entries

2. Document Access:
   • Verify URL is correct and accessible
   • Check document hasn't been deleted
   • Ensure document loads in browser

3. Format Requirements:
   • Google Docs or Google Sheets format
   • Table must be properly formatted
   • No merged cells in vocabulary area"""
    
    def _get_audio_processing_guidance(self, context: dict) -> str:
        """Get guidance for audio processing errors."""
        return """Audio Processing Issues:

1. Audio Quality:
   • Clear speech without excessive noise
   • Adequate volume levels
   • No silent or corrupted sections

2. File Format:
   • Use supported formats: MP3, WAV, M4A, FLAC, OGG
   • Avoid proprietary or compressed formats
   • Re-encode if format issues persist

3. Content Matching:
   • Audio should contain vocabulary from document
   • Words spoken in same order as document
   • Clear pronunciation of each word"""
    
    def _get_alignment_guidance(self, context: dict) -> str:
        """Get guidance for alignment errors."""
        return """Audio-Vocabulary Alignment Issues:

1. Content Synchronization:
   • Audio must contain all vocabulary words
   • Words should be in same order as document
   • Clear pauses between words help segmentation

2. Audio Quality for Alignment:
   • Consistent volume levels
   • Minimal background noise
   • Clear pronunciation

3. Vocabulary Matching:
   • Document vocabulary must match audio content
   • Check for missing or extra words
   • Verify pronunciation matches spelling"""
    
    def _get_anki_generation_guidance(self, context: dict) -> str:
        """Get guidance for Anki generation errors."""
        return """Anki Package Generation Issues:

1. File System:
   • Check write permissions for output directory
   • Ensure sufficient disk space
   • Close Anki if it's using the output file

2. Resource Access:
   • All audio files must be accessible
   • Temporary files need space
   • No file locks from other applications

3. Package Creation:
   • Verify all vocabulary entries are valid
   • Check audio clips are properly generated
   • Ensure no corrupted data"""
    
    def _get_network_guidance(self, context: dict) -> str:
        """Get guidance for network errors."""
        return """Network Connection Issues:

1. Internet Connection:
   • Check basic internet connectivity
   • Verify Google services are accessible
   • Try accessing Google Docs in browser

2. Firewall/Security:
   • Check firewall settings
   • Verify antivirus isn't blocking connection
   • Corporate networks may need special configuration

3. Service Availability:
   • Google services may be temporarily unavailable
   • Try again in a few minutes
   • Check Google Workspace status page"""
    
    def _get_filesystem_guidance(self, context: dict) -> str:
        """Get guidance for file system errors."""
        return """File System Issues:

1. Permissions:
   • Check read/write permissions
   • Try running as administrator (Windows)
   • Verify directory ownership

2. Disk Space:
   • Ensure sufficient free space
   • Clear temporary files
   • Choose different output location

3. File Access:
   • Close applications using the files
   • Check for file locks
   • Verify paths are not too long"""
    
    def _get_generic_guidance(self, context: dict) -> str:
        """Get generic guidance for unspecified errors."""
        return """General Troubleshooting:

1. Basic Checks:
   • Verify all inputs are correct
   • Check system resources
   • Restart application if needed

2. Input Validation:
   • Ensure files exist and are accessible
   • Check network connectivity
   • Verify permissions

3. System Resources:
   • Close unnecessary applications
   • Check available memory and disk space
   • Ensure stable system operation"""
    
    def _run_processing_thread(self, progress_callback, preserved_state):
        """
        Run the actual processing in a background thread with retry support.
        
        Args:
            progress_callback: Callback function for progress updates
            preserved_state: Preserved input state for error recovery
        """
        try:
            # Import the core processing engine
            from ..main import process_pipeline
            from ..progress import progress_tracker
            
            # Get URL value
            url_value = self.url_var.get()
            
            # Generate unique filename for the output
            unique_filename = self._generate_output_filename()
            output_path = Path(self.state.output_directory) / unique_filename
            
            # Set up progress tracking with our callback
            progress_tracker.add_progress_callback(progress_callback)
            
            # Execute the actual processing pipeline
            success = process_pipeline(
                google_doc_url=url_value,
                audio_file=Path(self.state.audio_file_path),
                output_path=output_path,
                verbose=False,  # GUI mode doesn't need verbose console output
                enable_speech_verification=self.speech_verification_var.get(),
                whisper_model=self.whisper_model_var.get(),
                debug_alignment=self.debug_alignment_var.get()
            )
            
            if success:
                # Get processing summary from progress tracker
                summary = progress_tracker.generate_completion_summary()
                
                result_data = {
                    'output_file': str(output_path),
                    'card_count': summary.get('cards_created', 0),
                    'processing_time': summary.get('pipeline_duration', 0),
                    'vocab_entries': summary.get('vocabulary_entries', 0),
                    'audio_clips': summary.get('audio_clips', 0)
                }
                
                self._queue_completion(success=True, result_data=result_data)
            else:
                # Processing failed - get error details from error handler
                from ..errors import error_handler
                
                if error_handler.has_errors():
                    error_summary = error_handler.get_error_summary()
                    if error_summary['errors']:
                        # Use the first error message
                        error_message = error_summary['errors'][0]['message']
                    else:
                        error_message = "Processing failed for unknown reasons"
                else:
                    error_message = "Processing failed - no specific error information available"
                
                self._queue_error(error_message)
            
        except Exception as e:
            # Handle processing errors with retry mechanism
            error_message = f"Processing failed: {str(e)}"
            
            if self._current_retry_count < self._max_retries:
                # Offer retry
                self.root.after(100, lambda: self._create_processing_retry_dialog(error_message, self._current_retry_count))
            else:
                # Max retries reached
                self._queue_error(f"Processing failed after {self._max_retries} attempts: {error_message}")
    
    def _handle_processing_completion(self, success: bool, result_data: dict):
        """
        Handle processing completion and update UI.
        
        Args:
            success: Whether processing completed successfully
            result_data: Results from processing
        """
        # Stop processing state
        self._set_processing_state(False)
        
        if success:
            # Update progress to 100%
            self._update_progress_display(100, "Processing Complete", 0, 0)
            
            # Show success message and results
            self._show_processing_results(result_data)
            
            # Show success notification
            messagebox.showinfo(
                "Success",
                f"Anki deck created successfully!\n\n"
                f"Cards: {result_data.get('card_count', 0)}\n"
                f"File: {Path(result_data.get('output_file', '')).name}"
            )
            
        else:
            # Show error state
            self.status_var.set("❌ Processing failed")
            self.current_stage_var.set("See error details below")
            self.progress_var.set(0)
            self.progress_percent_var.set("0%")
            self.time_remaining_var.set("")
            
            # Show error results
            self._show_processing_error_results(result_data.get('error_message', 'Unknown error'))
    
    def _show_processing_error_results(self, error_message: str):
        """
        Show error results in the results section.
        
        Args:
            error_message: The error message to display
        """
        # Show results frame
        self.results_frame.grid()
        
        # Bind mouse wheel events to the newly shown results frame
        self._bind_mousewheel_to_widget(self.results_frame)
        
        # Update scroll region to accommodate new content
        self._update_scroll_region()
        
        # Format error text
        error_text = f"""Processing failed with the following error:

{error_message}

Please check your inputs and try again. If the problem persists:
1. Verify your Google Docs/Sheets URL is accessible
2. Check that your audio file is valid and not corrupted
3. Ensure you have sufficient disk space in the output directory

You can retry processing with the same inputs or modify them as needed."""
        
        # Update results display with error styling
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, error_text)
        self.results_text.config(state="disabled")
        
        # Disable action buttons since no output was created
        self.open_folder_btn.config(state="disabled")
        self.copy_path_btn.config(state="disabled")
    
    def _show_processing_results(self, result_data: dict):
        """
        Show processing results in the results section.
        
        Args:
            result_data: Dictionary containing processing results
        """
        # Show results frame
        self.results_frame.grid()
        
        # Bind mouse wheel events to the newly shown results frame
        self._bind_mousewheel_to_widget(self.results_frame)
        
        # Update scroll region to accommodate new content
        self._update_scroll_region()
        
        # Extract result information
        output_file = result_data.get('output_file', 'Unknown')
        card_count = result_data.get('card_count', 0)
        processing_time = result_data.get('processing_time', 0)
        vocab_entries = result_data.get('vocab_entries', card_count)
        audio_clips = result_data.get('audio_clips', card_count)
        
        # Get file information
        output_path = Path(output_file)
        file_size_str = self._get_file_size_string(output_file)
        
        # Format processing time
        if processing_time < 60:
            time_str = f"{processing_time:.1f} seconds"
        else:
            minutes = int(processing_time / 60)
            seconds = processing_time % 60
            time_str = f"{minutes}m {seconds:.1f}s"
        
        # Format creation timestamp
        import datetime
        creation_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create detailed results text with enhanced formatting
        results_text = f"""✅ Processing completed successfully!

📁 Generated File Information:
   Filename: {output_path.name}
   Full Path: {output_path}
   File Size: {file_size_str}
   Created: {creation_time}

📊 Content Summary:
   Vocabulary Entries: {vocab_entries}
   Anki Cards Created: {card_count}
   Audio Clips Generated: {audio_clips}
   
⏱️ Processing Statistics:
   Total Processing Time: {time_str}
   Average Time per Card: {processing_time/max(card_count, 1):.2f} seconds

🎯 Next Steps:
   1. Click "Open Output Folder" below to view the file
   2. Import the .apkg file into Anki (File → Import)
   3. Start studying your Cantonese vocabulary!

📝 Import Instructions:
   • Open Anki on your computer
   • Go to File → Import
   • Select the generated .apkg file
   • Choose your preferred deck options
   • Click Import to add the cards

The Anki deck is ready for import and contains all vocabulary with audio pronunciations."""
        
        # Update results display
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, results_text)
        self.results_text.config(state="disabled")
        
        # Enable action buttons
        self.open_folder_btn.config(state="normal")
        self.copy_path_btn.config(state="normal")
        
        # Update status with comprehensive summary
        self.status_var.set(f"✅ Complete - {card_count} cards created ({file_size_str}) in {time_str}")
        
        # Log successful completion for debugging
        self.logger.info(f"Processing completed successfully: {card_count} cards, {file_size_str}, {time_str}")
        
        # Store result data for potential future use
        self._last_result_data = result_data
    
    def _generate_output_filename(self) -> str:
        """
        Generate a unique output filename based on current inputs.
        
        Returns:
            Unique filename for the Anki package
        """
        # Extract source information from Google Docs URL for better naming
        source_info = None
        url = self.state.google_docs_url
        
        if url:
            try:
                # Try to extract document ID for source info
                if 'docs.google.com' in url:
                    doc_id = url.split('/document/d/')[1].split('/')[0]
                    source_info = f"doc_{doc_id[:8]}"  # Use first 8 chars of doc ID
                elif 'sheets.google.com' in url:
                    doc_id = url.split('/spreadsheets/d/')[1].split('/')[0]
                    source_info = f"sheet_{doc_id[:8]}"  # Use first 8 chars of doc ID
            except (IndexError, AttributeError):
                # If extraction fails, use timestamp
                pass
        
        # Generate base filename with source info if available
        if source_info:
            base_name = f"cantonese_vocab_{source_info}"
        else:
            base_name = "cantonese_vocabulary_deck"
        
        # Check if the base name would conflict
        base_filename = f"{base_name}.apkg"
        original_path = Path(self.state.output_directory) / base_filename
        
        # Generate unique filename
        unique_filename = self.naming_manager.generate_unique_package_filename(
            base_name=base_name,
            output_dir=self.state.output_directory
        )
        
        # If the unique filename is different from the base, log the conflict resolution
        if unique_filename != base_filename:
            self.logger.info(f"Filename conflict resolved: {base_filename} -> {unique_filename}")
            # Queue a warning message for the user
            self._queue_info(
                "Finalization", 
                f"Filename adjusted to prevent conflicts: {unique_filename}"
            )
        
        return unique_filename
    
    def _show_filename_conflict_warning(self, original_name: str, unique_name: str):
        """
        Show a warning when filename conflicts are resolved.
        
        Args:
            original_name: Original filename that had conflicts
            unique_name: Unique filename that was generated
        """
        messagebox.showinfo(
            "Filename Conflict Resolved",
            f"A file with the name '{original_name}' already exists.\n\n"
            f"The output will be saved as:\n'{unique_name}'\n\n"
            f"This prevents overwriting existing files."
        )
    
    def _check_filename_conflicts(self, filename: str) -> bool:
        """
        Check if a filename would conflict with existing files.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if conflict exists, False otherwise
        """
        from ..anki.naming import ConflictDetector
        return ConflictDetector.check_package_conflicts(
            self.state.output_directory, 
            filename
        )
    
    def _get_file_size_string(self, file_path: str) -> str:
        """
        Get a human-readable file size string.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Formatted file size string
        """
        try:
            path = Path(file_path)
            
            # Check if file exists
            if not path.exists():
                return "File not found"
            
            size_bytes = path.stat().st_size
            
            # Handle zero-size files
            if size_bytes == 0:
                return "0 bytes (empty file)"
            
            # Format size with appropriate units
            if size_bytes < 1024:
                return f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_kb = size_bytes / 1024
                return f"{size_kb:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_mb = size_bytes / (1024 * 1024)
                return f"{size_mb:.1f} MB"
            else:
                size_gb = size_bytes / (1024 * 1024 * 1024)
                return f"{size_gb:.2f} GB"
                
        except (OSError, FileNotFoundError) as e:
            self.logger.warning(f"Could not get file size for {file_path}: {e}")
            return "Unknown size"
        except Exception as e:
            self.logger.error(f"Unexpected error getting file size for {file_path}: {e}")
            return "Error reading size"
        
    def _cancel_processing(self):
        """Cancel the current processing operation."""
        if not self.state.is_processing:
            return
            
        # Ask for confirmation
        if messagebox.askyesno("Cancel Processing", "Are you sure you want to cancel the current processing?"):
            # Set processing state to false
            self._set_processing_state(False)
            
            # Update status
            self.status_var.set("Processing cancelled")
            
            # Reset progress
            self.progress_var.set(0)
            self.progress_percent_var.set("0%")
            self.time_remaining_var.set("")
            self.current_stage_var.set("")
            self.state.progress_percentage = 0.0
            self.state.processing_start_time = None
            self.state.estimated_total_time = None
            
            # Note: The processing thread will check self.state.is_processing
            # and exit gracefully when it detects cancellation
    
    def _open_output_folder(self):
        """Open the output folder in the system file manager."""
        try:
            import subprocess
            import platform
            
            output_path = Path(self.state.output_directory)
            
            # Ensure the directory exists
            if not output_path.exists():
                messagebox.showerror(
                    "Folder Not Found", 
                    f"Output directory does not exist:\n{output_path}"
                )
                return
            
            system = platform.system()
            
            if system == "Windows":
                # Use explorer to open the folder
                subprocess.run(['explorer', str(output_path)], check=True)
            elif system == "Darwin":  # macOS
                # Use open command
                subprocess.run(['open', str(output_path)], check=True)
            elif system == "Linux":
                # Try common file managers
                try:
                    subprocess.run(['xdg-open', str(output_path)], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback to nautilus, dolphin, or thunar
                    for file_manager in ['nautilus', 'dolphin', 'thunar', 'pcmanfm']:
                        try:
                            subprocess.run([file_manager, str(output_path)], check=True)
                            break
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            continue
                    else:
                        # If no file manager works, show path in message
                        messagebox.showinfo(
                            "Output Location",
                            f"Output folder location:\n{output_path}\n\n"
                            "Please open this location manually in your file manager."
                        )
            else:
                # Unknown system - show path
                messagebox.showinfo(
                    "Output Location",
                    f"Output folder location:\n{output_path}\n\n"
                    "Please open this location manually in your file manager."
                )
                
        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "Error Opening Folder", 
                f"Could not open output folder.\n\n"
                f"Location: {self.state.output_directory}\n"
                f"Error: {str(e)}\n\n"
                "Please navigate to this location manually."
            )
        except Exception as e:
            messagebox.showerror(
                "Error", 
                f"Could not open folder: {str(e)}\n\n"
                f"Output location: {self.state.output_directory}"
            )
            
    def _copy_output_path(self):
        """Copy the output file path to clipboard."""
        try:
            if self._last_result_data and 'output_file' in self._last_result_data:
                output_file = self._last_result_data['output_file']
                
                # Copy to clipboard
                self.root.clipboard_clear()
                self.root.clipboard_append(str(output_file))
                self.root.update()  # Ensure clipboard is updated
                
                # Show confirmation
                messagebox.showinfo(
                    "Path Copied",
                    f"File path copied to clipboard:\n\n{Path(output_file).name}"
                )
            else:
                messagebox.showwarning(
                    "No File Path",
                    "No output file path available to copy."
                )
        except Exception as e:
            messagebox.showerror(
                "Copy Error",
                f"Could not copy path to clipboard: {str(e)}"
            )
            
    def _show_getting_started_help(self):
        """Show the getting started help dialog."""
        help_text = """Getting Started with Cantonese Anki Generator

STEP 1: Prepare Your Vocabulary Document
• Create a Google Docs document or Google Sheets spreadsheet
• Add a table with at least two columns: English and Cantonese
• First row should contain headers (e.g., "English", "Cantonese")
• Add your vocabulary entries in subsequent rows
• Share the document publicly or ensure it's accessible with your Google account

Example table format:
| English    | Cantonese |
|------------|-----------|
| Hello      | 你好      |
| Thank you  | 多謝      |
| Goodbye    | 再見      |

STEP 2: Record Your Audio
• Record yourself pronouncing each vocabulary word clearly
• Speak each word with small pauses between them
• Use the same order as in your vocabulary table
• Save as MP3, WAV, or M4A format
• Ensure good audio quality (clear, not too quiet)

STEP 3: Generate Your Anki Deck
• Enter your Google Docs/Sheets URL in the first field
• Select your audio file using the Browse button
• Choose an output location (or use the default)
• Click "Generate Anki Deck" and wait for processing
• Import the generated .apkg file into Anki

TIPS FOR SUCCESS:
• Keep vocabulary lists manageable (10-50 words for first attempts)
• Test with a small list before creating large decks
• Ensure your internet connection is stable
• Make sure you have sufficient disk space"""
        
        self._show_help_dialog("Getting Started Guide", help_text)
        
    def _show_document_format_help(self):
        """Show document format help dialog."""
        help_text = """Document Format Requirements

SUPPORTED DOCUMENT TYPES:
• Google Docs documents
• Google Sheets spreadsheets

REQUIRED TABLE STRUCTURE:
• Must contain a proper table (not just text aligned with spaces)
• At least two columns for English and Cantonese text
• First row should contain clear column headers
• Each vocabulary entry should be in its own row

GOOGLE DOCS FORMAT:
1. Insert a table using Insert → Table
2. Set up headers in the first row:
   - Column 1: "English" (or similar)
   - Column 2: "Cantonese" (or similar)
3. Add vocabulary entries in subsequent rows
4. Keep formatting simple (avoid merged cells)

GOOGLE SHEETS FORMAT:
1. Use the first row for headers
2. Put English words in column A
3. Put Cantonese words in column B
4. Each vocabulary word gets its own row

SHARING REQUIREMENTS:
• Document must be accessible via the URL
• Set sharing to "Anyone with the link can view" OR
• Ensure the document is shared with your Google account
• Document should not be password protected

COMMON MISTAKES TO AVOID:
• Using spaces or tabs instead of actual table cells
• Merged cells or complex table formatting
• Empty rows between vocabulary entries
• Missing or unclear column headers
• Private documents without proper sharing settings

EXAMPLE URLS:
• Google Docs: https://docs.google.com/document/d/1ABC...XYZ/edit
• Google Sheets: https://sheets.google.com/spreadsheets/d/1ABC...XYZ/edit"""
        
        self._show_help_dialog("Document Format Guide", help_text)
        
    def _show_audio_recording_help(self):
        """Show audio recording tips dialog."""
        help_text = """Audio Recording Best Practices

RECORDING SETUP:
• Use a quiet room with minimal background noise
• Position microphone 6-12 inches from your mouth
• Test recording levels before starting
• Use a decent quality microphone if available

RECORDING TECHNIQUE:
• Speak clearly and at normal volume
• Pronounce each word distinctly
• Leave 1-2 second pauses between words
• Maintain consistent volume throughout
• Record words in the same order as your vocabulary table

AUDIO FORMAT REQUIREMENTS:
• Supported formats: MP3, WAV, M4A, FLAC, OGG
• Recommended: MP3 (128 kbps or higher) or WAV
• Minimum duration: 1 second per vocabulary word
• Maximum recommended file size: 500MB

QUALITY GUIDELINES:
• Audio should be clearly audible (not too quiet)
• Avoid clipping (audio too loud causing distortion)
• Minimize background noise, echo, and reverb
• Ensure consistent pronunciation for each word

RECORDING SOFTWARE SUGGESTIONS:
• Free: Audacity, GarageBand (Mac), Voice Recorder (Windows)
• Online: Vocaroo, Online Voice Recorder
• Mobile: Voice Memos (iOS), Voice Recorder (Android)

EDITING TIPS:
• Trim silence from beginning and end
• Normalize volume levels if needed
• Remove background noise if possible
• Export in a supported format

TROUBLESHOOTING AUDIO ISSUES:
• If audio is too quiet: Increase recording gain or amplify in editing
• If there's background noise: Record in a quieter location
• If words run together: Re-record with longer pauses
• If file won't load: Check format and file integrity

TESTING YOUR RECORDING:
• Play back the entire recording before processing
• Verify each word is clearly audible
• Check that pauses between words are adequate
• Ensure the recording matches your vocabulary list order"""
        
        self._show_help_dialog("Audio Recording Tips", help_text)
        
    def _show_troubleshooting_help(self):
        """Show troubleshooting help dialog."""
        help_text = """Common Issues and Solutions

AUTHENTICATION PROBLEMS:
Problem: "Access Denied" or "Authentication Failed"
Solutions:
• Check that your Google document is properly shared
• Ensure you have internet connectivity
• Try opening the document URL in your browser first
• Delete token.json file if it exists to force re-authentication

DOCUMENT PROCESSING ERRORS:
Problem: "Document not found" or "No vocabulary table found"
Solutions:
• Verify the document URL is complete and correct
• Check that the document contains a proper table structure
• Ensure the document is accessible (not private)
• Try copying the URL again from your browser

AUDIO PROCESSING ISSUES:
Problem: "Audio file not supported" or "Audio processing failed"
Solutions:
• Convert audio to MP3 or WAV format
• Check that the audio file is not corrupted
• Ensure the file is not too large (under 500MB recommended)
• Try playing the file in a media player to verify it works

ALIGNMENT PROBLEMS:
Problem: "Audio-vocabulary mismatch" or poor card quality
Solutions:
• Verify audio contains all vocabulary words from the document
• Check that words are spoken in the same order as the document
• Ensure clear pronunciation with pauses between words
• Try with a smaller vocabulary list first

NETWORK AND CONNECTIVITY:
Problem: "Network error" or "Connection timeout"
Solutions:
• Check your internet connection
• Try again in a few minutes (temporary network issues)
• Disable VPN if using one
• Check firewall settings

FILE SYSTEM ERRORS:
Problem: "Permission denied" or "Cannot save file"
Solutions:
• Choose a different output directory
• Check that you have write permissions
• Ensure sufficient disk space is available
• Close Anki if it's running and using the output file

PERFORMANCE ISSUES:
Problem: Processing is very slow or application freezes
Solutions:
• Close other applications to free up memory
• Try with smaller input files
• Ensure sufficient disk space
• Restart the application

GETTING ADDITIONAL HELP:
• Check the application logs for detailed error messages
• Try with minimal test data to isolate the problem
• Ensure your system meets the minimum requirements
• Contact support with specific error messages and steps to reproduce"""
        
        self._show_help_dialog("Troubleshooting Guide", help_text)
        
    def _show_keyboard_shortcuts_help(self):
        """Show keyboard shortcuts help dialog."""
        help_text = """Keyboard Shortcuts

GENERAL NAVIGATION:
• Tab / Shift+Tab - Navigate between input fields
• Ctrl+Tab / Ctrl+Shift+Tab - Advanced navigation
• Enter - Activate focused button
• Escape - Cancel processing or close dialogs
• Ctrl+A - Select all text in focused field

FILE OPERATIONS:
• Ctrl+O - Open audio file browser
• Ctrl+S - Choose output folder
• Ctrl+L - Focus on URL input field

PROCESSING CONTROLS:
• Ctrl+R - Start processing (if inputs are valid)
• Ctrl+G - Generate Anki deck (same as Ctrl+R)
• Escape - Cancel processing (during processing only)
• Ctrl+E - Open output folder (after successful processing)

INTERFACE ACTIONS:
• F1 - Show this help dialog
• Ctrl+H - Show getting started guide
• Ctrl+Delete - Clear all inputs

QUICK ACCESS:
• Alt+1 - Focus URL input field
• Alt+2 - Focus audio file button
• Alt+3 - Focus output folder button
• Alt+4 - Focus process button

ACCESSIBILITY:
• All buttons and fields are accessible via Tab navigation
• Screen reader compatible labels and descriptions
• High contrast mode support
• Keyboard-only operation supported
• Proper focus indicators for all interactive elements

TIPS:
• Use Tab to quickly navigate between fields
• Press Enter on buttons instead of clicking
• Use Ctrl+A to select all text for easy replacement
• Alt+number shortcuts provide quick access to main sections
• Keyboard shortcuts work even when fields are disabled during processing"""
        
        self._show_help_dialog("Keyboard Shortcuts", help_text)
        
    def _show_about_dialog(self):
        """Show about dialog with application information."""
        about_text = """Cantonese Anki Generator
Version 1.0

DESCRIPTION:
An automated tool that transforms Google Docs/Sheets containing Cantonese vocabulary tables and corresponding audio recordings into complete Anki flashcard decks.

KEY FEATURES:
• Automatic audio segmentation with voice activity detection
• Smart boundary detection for word separation
• Format compatibility checking and adaptation
• Comprehensive error handling and progress tracking
• Interactive GUI with validation and guidance
• Support for real-world audio conditions

SUPPORTED FORMATS:
• Documents: Google Docs, Google Sheets
• Audio: MP3, WAV, M4A, FLAC, OGG
• Output: Anki package files (.apkg)

TARGET USERS:
• Cantonese language learners
• Language teachers creating study materials
• Anyone wanting to convert vocabulary lists + audio into flashcards

SYSTEM REQUIREMENTS:
• Windows, macOS, or Linux
• Python 3.8 or higher
• Internet connection for Google Docs access
• Sufficient disk space for audio processing

GETTING HELP:
• Use the Help menu for guides and troubleshooting
• Review error messages for specific guidance

© 2024 Cantonese Anki Generator
Open source software for language learning"""
        
        self._show_help_dialog("About Cantonese Anki Generator", about_text)
        
    def _show_help_dialog(self, title: str, content: str):
        """
        Show a help dialog with the specified title and content.
        
        Args:
            title: Dialog title
            content: Help content text
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("700x600")
        dialog.resizable(True, True)
        
        # Center and configure dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dialog layout
        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        
        # Main frame with scrollable text
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable text widget
        text_widget = tk.Text(
            main_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="white",
            relief="flat",
            padx=15,
            pady=15
        )
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical")
        
        text_widget.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=text_widget.yview)
        
        text_widget.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Insert content
        text_widget.insert(1.0, content)
        text_widget.config(state="disabled")  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(dialog, padding="20 10 20 20")
        button_frame.grid(row=1, column=0, sticky="ew")
        
        # Close button
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy
        )
        close_btn.pack(side="right")
        
        # Focus on close button
        close_btn.focus_set()
        
        # Handle dialog closing
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
            
    def _on_closing(self):
        """Handle window closing event with proper cleanup."""
        if self.state.is_processing:
            # Ask user to confirm if processing is in progress
            if messagebox.askokcancel(
                "Quit", 
                "Processing is in progress. Quitting now will cancel the operation.\n\n"
                "Do you want to quit?"
            ):
                # Cancel processing
                self._cancel_processing()
                
                # Give processing thread time to clean up
                if self.processing_thread and self.processing_thread.is_alive():
                    self.processing_thread.join(timeout=2.0)
                
                # Perform cleanup
                self._cleanup_resources()
                
                # Destroy window
                self.root.destroy()
        else:
            # No processing in progress, just clean up and close
            self._cleanup_resources()
            self.root.destroy()
            
    def _cleanup_resources(self):
        """Clean up resources before closing the application."""
        try:
            # Clear any temporary files if needed
            temp_dir = Path("temp")
            if temp_dir.exists():
                # Don't delete the temp directory itself, just log
                self.logger.debug("Temporary files may remain in temp/ directory")
            
            # Clear progress callback queue
            self.progress_callback_queue.clear()
            
            # Log application closure
            self.logger.info("Application closed successfully")
            
        except Exception as e:
            # Log cleanup errors but don't prevent closing
            self.logger.error(f"Error during cleanup: {e}")
            
    def run(self):
        """Start the GUI application main loop."""
        self.root.mainloop()


def main():
    """Entry point for the GUI application."""
    app = CantoneseAnkiGeneratorGUI()
    app.run()


if __name__ == "__main__":
    main()