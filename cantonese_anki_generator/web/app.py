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
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
