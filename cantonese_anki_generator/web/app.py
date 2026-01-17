"""Flask application for manual audio alignment interface."""

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
import os


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates'
    )
    
    # Configure CORS for API endpoints
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Configure upload settings
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'temp', 'uploads')
    app.config['SESSION_FOLDER'] = os.path.join(os.getcwd(), 'temp', 'sessions')
    
    # Ensure required directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SESSION_FOLDER'], exist_ok=True)
    
    # Clear old sessions and uploads on startup to prevent stale data
    # Only do this in the main process, not the reloader process
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        import shutil
        try:
            # Clear sessions
            for item in os.listdir(app.config['SESSION_FOLDER']):
                item_path = os.path.join(app.config['SESSION_FOLDER'], item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            
            # Clear uploads
            for item in os.listdir(app.config['UPLOAD_FOLDER']):
                item_path = os.path.join(app.config['UPLOAD_FOLDER'], item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            
            # Clear audio segments
            audio_segments_dir = os.path.join(os.getcwd(), 'temp', 'audio_segments')
            if os.path.exists(audio_segments_dir):
                for item in os.listdir(audio_segments_dir):
                    item_path = os.path.join(audio_segments_dir, item)
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
            
            print("✓ Cleared old sessions and uploads")
        except Exception as e:
            print(f"⚠️  Warning: Could not clear old data: {e}")
    
    # Set up log streaming
    from cantonese_anki_generator.web.log_streamer import setup_log_streaming, log_streamer
    setup_log_streaming(app)
    
    # Send a test message to verify streaming works
    log_streamer.broadcast_log("Log streaming initialized", "info")
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app):
    """Register all application routes."""
    
    @app.route('/')
    def index():
        """Serve the main alignment review interface."""
        return render_template('index.html')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files (CSS, JS, etc.)."""
        return send_from_directory(app.static_folder, filename)
    
    # API routes will be added in subsequent tasks
    from cantonese_anki_generator.web import api
    app.register_blueprint(api.bp)


if __name__ == '__main__':
    import os
    
    # Security: Use environment variables to control debug mode and host binding
    # Never run with debug=True and host='0.0.0.0' in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    host = '127.0.0.1' if debug_mode else '0.0.0.0'
    port = int(os.environ.get('FLASK_PORT', '3000'))
    
    app = create_app()
    
    if debug_mode:
        print("⚠️  WARNING: Running in DEBUG mode - server restricted to localhost")
        print(f"Server: http://localhost:{port}")
    else:
        print(f"Server: http://0.0.0.0:{port}")
    
    app.run(debug=debug_mode, host=host, port=port)

