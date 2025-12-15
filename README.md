# Cantonese Anki Generator

An automated tool that transforms Google Docs containing Cantonese vocabulary tables and corresponding audio recordings into complete Anki flashcard decks.

## Features

- Automatic extraction of vocabulary tables from Google Docs
- Audio segmentation and word boundary detection
- Forced alignment of audio clips to vocabulary terms
- Generation of complete Anki packages (.apkg files)
- Support for real-world audio conditions with background noise

## Installation

```bash
pip install -r requirements.txt
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Google API Credentials
**IMPORTANT**: You must set up your own Google API credentials to use this application.

1. Follow the detailed guide in [SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)
2. Create your `credentials.json` file (see `credentials.json.template`)
3. **Never commit credentials to version control!**

### 3. Development Setup (Optional)
```bash
pip install -e .[dev]
```

## Testing

```bash
pytest
```

## Usage

### Interactive Mode
```bash
python -m cantonese_anki_generator
```

### Direct Usage
```bash
python -m cantonese_anki_generator "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit" audio.wav
```

### With Custom Output
```bash
python -m cantonese_anki_generator "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit" audio.wav -o my_deck.apkg
```

## Security Notes

⚠️ **IMPORTANT SECURITY INFORMATION**:
- This repository does NOT include API credentials
- You must set up your own Google API credentials
- Never commit `credentials.json` or `token.json` to version control
- See [SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md) for detailed setup instructions

## Project Structure

```
cantonese_anki_generator/
├── processors/     # Google Docs processing
├── audio/         # Audio segmentation and processing
├── alignment/     # Audio-vocabulary alignment
├── anki/          # Anki package generation
└── models.py      # Core data models
```