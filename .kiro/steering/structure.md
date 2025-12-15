# Project Structure

## Root Directory Layout
```
cantonese-anki-generator/
├── cantonese_anki_generator/    # Main package
├── tests/                       # Unit tests
├── data/                        # Input data directory
├── output/                      # Generated Anki packages
├── temp/                        # Temporary processing files
├── audio_test_results/          # Audio processing test outputs
├── requirements.txt             # Dependencies
├── setup.py                     # Package configuration
├── pytest.ini                  # Test configuration
├── credentials.json             # Google API credentials
└── token.json                   # OAuth tokens
```

## Main Package Structure
```
cantonese_anki_generator/
├── __init__.py                  # Package initialization
├── __main__.py                  # CLI entry point
├── main.py                      # Main pipeline orchestration
├── config.py                    # Configuration settings
├── models.py                    # Core data models
├── errors.py                    # Error handling system
├── progress.py                  # Progress tracking
├── format_compatibility.py     # Format validation and adaptation
├── processors/                  # Document processing
│   ├── google_docs_auth.py     # Google API authentication
│   ├── google_docs_parser.py   # Google Docs processing
│   └── google_sheets_parser.py # Google Sheets processing
├── audio/                       # Audio processing pipeline
│   ├── loader.py               # Audio file loading
│   ├── processor.py            # Audio preprocessing
│   ├── vad.py                  # Voice activity detection
│   ├── segmentation.py         # Basic audio segmentation
│   ├── smart_segmentation.py   # Advanced boundary detection
│   └── clip_generator.py       # Audio clip generation
├── alignment/                   # Audio-text alignment
│   ├── aligner.py              # Base alignment interface
│   ├── forced_aligner.py       # Montreal Forced Alignment
│   └── refinement.py           # Alignment refinement
└── anki/                        # Anki package generation
    ├── templates.py            # Anki card templates
    ├── naming.py               # Unique naming management
    └── package_generator.py    # .apkg file creation
```

## Test Structure
```
tests/
├── __init__.py
├── test_models.py              # Core model tests
├── test_error_handling.py      # Error system tests
└── test_google_docs_processor.py # Document processing tests
```

## Test Files (Root Level)
- `test_*.py` - Various integration and feature tests
- Focus on real-world scenarios and end-to-end testing
- Audio processing tests generate results in `audio_test_results/`

## Key Architectural Patterns

### Pipeline Architecture
- Main processing pipeline in `main.py`
- Stage-based processing with progress tracking
- Comprehensive error handling at each stage

### Modular Design
- Clear separation of concerns by functionality
- Each module handles specific domain (audio, docs, anki)
- Shared models and utilities in root package

### Error Handling Strategy
- Centralized error management in `errors.py`
- Categorized errors with suggested actions
- Progress tracking with detailed logging

### Configuration Management
- Single config class in `config.py`
- Environment-specific settings
- Directory structure management

## File Naming Conventions
- Snake_case for Python files and directories
- Descriptive module names indicating functionality
- Test files prefixed with `test_`
- Generated files include timestamps for uniqueness

## Data Flow
1. **Input**: Google Docs/Sheets URL + Audio file
2. **Processing**: Document parsing → Audio segmentation → Alignment
3. **Output**: Anki package (.apkg) in `output/` directory
4. **Temporary**: Audio clips stored in `temp/` during processing