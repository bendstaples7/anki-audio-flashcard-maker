"""Launcher script for the Manual Audio Alignment web interface."""

import os
import webbrowser
import threading
import time
from cantonese_anki_generator.web.app import create_app


def open_browser(url, delay=1.5):
    """Open browser after a short delay to ensure server is ready."""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not automatically open browser: {e}")
        print(f"Please manually open: {url}")


def main():
    """Run the Flask development server."""
    app = create_app()
    print("\n" + "="*60)
    print("Manual Audio Alignment Interface")
    print("="*60)
    
    # Security: Only bind to localhost when debug mode is enabled
    # to prevent exposing the interactive debugger to the network
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    host = '127.0.0.1' if debug_mode else '0.0.0.0'
    port = int(os.environ.get('FLASK_PORT', '3000'))
    
    url = f"http://localhost:{port}"
    
    if debug_mode:
        print("\n⚠️  Running in DEBUG mode - server restricted to localhost only")
        print(f"Starting server at {url}")
    else:
        print(f"\nStarting server at http://0.0.0.0:{port}")
    
    print("Press Ctrl+C to stop the server")
    
    # Only open browser in the main process, not in the reloader process
    # Check if we're in the reloader process by looking for WERKZEUG_RUN_MAIN env var
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        print(f"\n🌐 Opening browser to {url}...\n")
        # Open browser in a separate thread
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    app.run(debug=debug_mode, host=host, port=port)


if __name__ == '__main__':
    main()

