# Technology Stack

## Core Technologies
- **Python 3.8+** - Main programming language
- **setuptools** - Package management and distribution

## Key Libraries

### Audio Processing
- **librosa** - Audio analysis and feature extraction
- **scipy** - Scientific computing and audio I/O
- **webrtcvad** - Voice activity detection
- **montreal-forced-alignment** - Audio-text alignment
- **phonemizer** - Text-to-phoneme conversion

### Google APIs
- **google-auth** - Authentication framework
- **google-auth-oauthlib** - OAuth2 flow handling
- **google-api-python-client** - Google Docs/Sheets API client

### Anki Integration
- **genanki** - Anki package (.apkg) generation

### Development Tools
- **pytest** - Testing framework
- **hypothesis** - Property-based testing
- **black** - Code formatting
- **flake8** - Linting
- **mypy** - Type checking

## Build System
- Uses standard Python setuptools
- Development dependencies managed via extras_require

## Common Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Development setup with dev dependencies
pip install -e .[dev]
```

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m property      # Property-based tests only
```

### Code Quality
```bash
# Format code
black cantonese_anki_generator/

# Lint code
flake8 cantonese_anki_generator/

# Type checking
mypy cantonese_anki_generator/
```

### Running the Application
```bash
# Interactive mode
python -m cantonese_anki_generator

# Direct usage
python -m cantonese_anki_generator "https://docs.google.com/..." audio.wav

# With custom output
python -m cantonese_anki_generator "https://docs.google.com/..." audio.wav -o my_deck.apkg

# Verbose mode for debugging
python -m cantonese_anki_generator "https://docs.google.com/..." audio.wav --verbose

# Check input formats without processing
python -m cantonese_anki_generator "https://docs.google.com/..." audio.wav --check-formats
```

## Configuration
- Main config in `cantonese_anki_generator/config.py`
- Google API credentials in `credentials.json`
- OAuth tokens stored in `token.json`
- Test configuration in `pytest.ini`