"""Flask application for manual audio alignment interface."""

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
import os
import logging


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_authentication(app):
    """
    Initialize authentication system on Flask app startup.
    
    This function:
    1. Creates GoogleDocsAuthenticator in web mode
    2. Validates existing tokens and logs status
    3. Starts TokenMonitor background task
    4. Handles missing credentials gracefully (allows app to start)
    
    Args:
        app: Flask application instance
    """
    from cantonese_anki_generator.processors.google_docs_auth import GoogleDocsAuthenticator
    from cantonese_anki_generator.web.token_monitor import TokenMonitor
    
    try:
        logger.info("Initializing authentication system...")
        
        # Initialize authenticator in web mode
        authenticator = GoogleDocsAuthenticator(mode='web')
        
        # Store authenticator in app config for access by API endpoints
        app.config['AUTHENTICATOR'] = authenticator
        
        # Check if credentials file exists
        if not os.path.exists(authenticator.credentials_path):
            logger.warning(
                f"⚠️  Credentials file not found: {authenticator.credentials_path}"
            )
            logger.warning(
                "   Authentication will not be available until credentials are configured."
            )
            logger.warning(
                "   Download credentials.json from Google Cloud Console."
            )
            # Allow app to start without credentials
            return
        
        # Validate existing tokens
        token_status = authenticator.get_token_status()
        
        if not token_status['valid']:
            if os.path.exists(authenticator.token_path):
                logger.warning("⚠️  Existing tokens are invalid or expired")
                
                # Attempt automatic refresh if refresh token available
                if token_status['has_refresh_token']:
                    logger.info("   Attempting automatic token refresh...")
                    if authenticator.refresh_tokens():
                        logger.info("✓ Token refresh successful")
                        token_status = authenticator.get_token_status()
                    else:
                        logger.warning("   Token refresh failed - user re-authentication required")
            else:
                logger.warning("⚠️  No authentication tokens found")
                logger.warning("   Users will need to authenticate through the web interface")
        else:
            # Tokens are valid
            if token_status['expires_at']:
                logger.info(f"✓ Authentication valid - expires at {token_status['expires_at']}")
            else:
                logger.info("✓ Authentication valid")
            
            # Check if proactive refresh is needed
            if token_status['needs_refresh']:
                logger.info("   Token expiring soon, attempting proactive refresh...")
                if authenticator.refresh_tokens():
                    logger.info("✓ Proactive token refresh successful")
                else:
                    logger.warning("   Proactive refresh failed - will retry later")
        
        # Start background token monitor only if enabled
        # In multi-worker deployments, set RUN_TOKEN_MONITOR=true on only ONE worker
        # to prevent multiple monitors from running and causing race conditions
        if os.environ.get('RUN_TOKEN_MONITOR', 'true').lower() == 'true':
            logger.info("Starting background token monitor...")
            token_monitor = TokenMonitor(authenticator, check_interval_hours=6)
            token_monitor.start()
            
            # Store monitor in app config for cleanup on shutdown
            app.config['TOKEN_MONITOR'] = token_monitor
            
            logger.info("✓ Background token monitor started")
        else:
            logger.info("⚠️  Background token monitor disabled (RUN_TOKEN_MONITOR=false)")
            logger.info("   Token refresh will only occur on-demand during requests")
        
        logger.info("✓ Authentication system initialized successfully")
        
    except Exception as e:
        logger.error(f"⚠️  Error initializing authentication: {e}")
        logger.warning("   Application will start but authentication may not work correctly")
        # Allow app to start even if authentication initialization fails


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
    
    # Initialize authentication system
    # Only initialize in the reloader child process (or when not using reloader)
    # This prevents duplicate TokenMonitor instances in debug mode
    if os.environ.get('WERKZEUG_RUN_MAIN') or not os.environ.get('FLASK_DEBUG'):
        initialize_authentication(app)
    
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

