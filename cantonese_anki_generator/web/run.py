"""Launcher script for the Manual Audio Alignment web interface."""

import os
from cantonese_anki_generator.web.app import create_app


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
    
    if debug_mode:
        print("\n⚠️  Running in DEBUG mode - server restricted to localhost only")
        print(f"Starting server at http://localhost:{port}")
    else:
        print(f"\nStarting server at http://0.0.0.0:{port}")
    
    print("Press Ctrl+C to stop the server\n")
    
    app.run(debug=debug_mode, host=host, port=port)


if __name__ == '__main__':
    main()

