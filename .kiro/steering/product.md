# Product Overview

## Cantonese Anki Generator

An automated tool that transforms Google Docs/Sheets containing Cantonese vocabulary tables and corresponding audio recordings into complete Anki flashcard decks (.apkg files).

### Core Functionality
- Extracts vocabulary tables from Google Docs/Sheets (English-Cantonese pairs)
- Segments audio recordings into individual word pronunciations
- Aligns audio clips with vocabulary entries using smart boundary detection
- Generates complete Anki packages with embedded audio for language learning

### Target Users
- Cantonese language learners
- Language teachers creating study materials
- Anyone wanting to convert vocabulary lists + audio into flashcards

### Key Features
- Automatic audio segmentation with voice activity detection
- Smart boundary detection for word separation
- Format compatibility checking and adaptation
- Comprehensive error handling and progress tracking
- Interactive CLI with validation and guidance
- Support for real-world audio conditions with background noise

### Output
Generated .apkg files ready for import into Anki, containing vocabulary cards with:
- English term (front)
- Cantonese text (back)
- Audio pronunciation for each term