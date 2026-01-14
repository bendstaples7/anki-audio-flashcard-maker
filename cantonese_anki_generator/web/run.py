"""Launcher script for the Manual Audio Alignment web interface."""

from cantonese_anki_generator.web.app import create_app


def main():
    """Run the Flask development server."""
    app = create_app()
    print("\n" + "="*60)
    print("Manual Audio Alignment Interface")
    print("="*60)
    print("\nStarting server at http://localhost:3000")
    print("Press Ctrl+C to stop the server\n")
    
    app.run(debug=True, host='0.0.0.0', port=3000)


if __name__ == '__main__':
    main()
