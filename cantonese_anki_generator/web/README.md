# Manual Audio Alignment Web Interface

This directory contains the Flask-based web interface for reviewing and adjusting audio-term alignments.

## Directory Structure

```
web/
├── __init__.py           # Package initialization
├── app.py                # Flask application setup and configuration
├── api.py                # API endpoints for alignment operations
├── run.py                # Development server launcher
├── templates/            # HTML templates
│   └── index.html        # Main interface page
└── static/               # Static assets
    ├── css/
    │   └── styles.css    # Application styles
    └── js/
        └── app.js        # Frontend JavaScript
```

## Running the Application

### Development Server

```bash
# From the project root
python -m cantonese_anki_generator.web.run

# Or directly
python cantonese_anki_generator/web/run.py
```

The application will be available at: http://localhost:3000

## API Endpoints

### Health Check
- **GET** `/api/health` - Check API status

### File Upload
- **POST** `/api/upload` - Upload audio file and vocabulary document (Implemented - tested)

### Session Management
- **GET** `/api/session/<session_id>` - Retrieve session data (Implemented - tested)
- **POST** `/api/session/<session_id>/update` - Update alignment boundaries (Implemented - tested)
- **POST** `/api/session/<session_id>/generate` - Generate Anki package (Implemented - tested)
- **GET** `/api/audio/<session_id>/<term_id>` - Serve audio segment (Implemented - tested)

**Note**: Core API endpoints completed and tested. See [CHECKPOINT_11_SUMMARY.md](../../CHECKPOINT_11_SUMMARY.md) for implementation details.

## Configuration

The Flask app is configured with:
- **CORS**: Enabled for all `/api/*` endpoints
- **Max Upload Size**: 500MB
- **Upload Folder**: `temp/uploads/`
- **Session Folder**: `temp/sessions/`

## Development

The application uses:
- **Flask** for the web framework
- **Flask-CORS** for cross-origin resource sharing
- **WaveSurfer.js** - Implemented: waveform rendering, zoom/pan controls, and library setup complete (see [CHECKPOINT_11_SUMMARY.md](../../CHECKPOINT_11_SUMMARY.md) Task 8)
- **Web Audio API** for audio playback
