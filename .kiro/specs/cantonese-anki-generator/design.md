# Design Document

## Overview

The Cantonese Anki Generator is a Python-based automation tool that processes Google Docs vocabulary tables and audio recordings to create complete Anki flashcard decks. The system uses the Google Docs API for document access, advanced audio processing libraries for speech segmentation, and forced alignment techniques to match audio clips with vocabulary terms. The architecture emphasizes reliability and accuracy in handling real-world audio conditions while maintaining a simple user interface.

## Architecture

The system follows a pipeline architecture with four main processing stages:

1. **Input Processing Stage**: Handles Google Docs authentication, document parsing, and audio file validation
2. **Audio Segmentation Stage**: Uses speech processing algorithms to identify word boundaries and create individual clips
3. **Alignment Stage**: Matches segmented audio clips to vocabulary terms using forced alignment techniques
4. **Anki Generation Stage**: Creates properly formatted .apkg files with embedded audio and card templates

The pipeline design allows for error recovery and validation at each stage, ensuring robust processing of varied input conditions.

## Components and Interfaces

### Google Docs Processor
- **Purpose**: Extracts vocabulary tables from Google Docs
- **Dependencies**: Google Docs API, OAuth2 authentication
- **Interface**: `extract_vocabulary_table(doc_url) -> List[VocabularyEntry]`
- **Key Methods**:
  - `authenticate_google_docs()`: Handles OAuth2 flow
  - `parse_document_structure()`: Identifies table elements
  - `extract_table_data()`: Converts table to structured data

### Audio Segmentation Engine
- **Purpose**: Splits continuous audio into individual word clips
- **Dependencies**: librosa, scipy, webrtcvad for voice activity detection
- **Interface**: `segment_audio(audio_file, word_count) -> List[AudioSegment]`
- **Key Methods**:
  - `detect_speech_regions()`: Identifies speech vs silence/noise
  - `estimate_word_boundaries()`: Uses energy and spectral analysis
  - `refine_boundaries()`: Applies smoothing and validation

### Forced Alignment Module
- **Purpose**: Matches audio segments to vocabulary terms
- **Dependencies**: Montreal Forced Alignment (MFA) or similar toolkit
- **Interface**: `align_audio_to_text(segments, vocabulary) -> List[AlignedPair]`
- **Key Methods**:
  - `prepare_pronunciation_dictionary()`: Handles Cantonese phonetics
  - `perform_alignment()`: Executes forced alignment algorithm
  - `validate_alignment_quality()`: Checks alignment confidence scores

### Anki Package Generator
- **Purpose**: Creates .apkg files with cards and media
- **Dependencies**: genanki library for Anki package creation
- **Interface**: `generate_anki_package(aligned_pairs) -> AnkiPackage`
- **Key Methods**:
  - `create_card_templates()`: Defines front/back layouts
  - `embed_audio_files()`: Includes audio clips in package
  - `generate_package_metadata()`: Sets deck properties

## Data Models

### VocabularyEntry
```python
@dataclass
class VocabularyEntry:
    english: str
    cantonese: str
    row_index: int
    confidence: float = 1.0
```

### AudioSegment
```python
@dataclass
class AudioSegment:
    start_time: float
    end_time: float
    audio_data: np.ndarray
    confidence: float
    segment_id: str
```

### AlignedPair
```python
@dataclass
class AlignedPair:
    vocabulary_entry: VocabularyEntry
    audio_segment: AudioSegment
    alignment_confidence: float
    audio_file_path: str
```

### AnkiCard
```python
@dataclass
class AnkiCard:
    front_text: str  # English
    back_text: str   # Cantonese
    audio_file: str
    tags: List[str]
    card_id: str
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated to eliminate redundancy:

- Properties 1.1, 3.1, 3.2, and 3.3 all test aspects of Google Docs processing and can be combined into a comprehensive document processing property
- Properties 2.1 and 2.2 both test audio-vocabulary alignment and can be merged into a single alignment property
- Properties 4.1, 4.3, and 2.4 all test audio segmentation quality and can be consolidated
- Properties 5.1, 5.2, 5.3, and 5.4 all test Anki package validity and can be combined
- Properties related to error handling (6.2, 6.5) can be merged into a comprehensive error reporting property

### Core Properties

**Property 1: Complete pipeline processing**
*For any* valid Google Doc URL and audio file, the system should successfully extract vocabulary data, process audio, and generate a complete Anki package without manual intervention
**Validates: Requirements 1.1, 1.2, 1.4**

**Property 2: Audio-vocabulary alignment consistency**
*For any* vocabulary table and corresponding audio file, each vocabulary term should be matched to exactly one audio segment, and each audio segment should correspond to exactly one vocabulary term
**Validates: Requirements 2.1, 2.2, 2.3**

**Property 3: Audio segmentation preservation**
*For any* continuous audio file, segmentation should produce clips that contain complete words without syllable truncation, regardless of background noise or speech pattern variations
**Validates: Requirements 1.5, 2.4, 4.1, 4.3**

**Property 4: Google Docs extraction completeness**
*For any* Google Doc containing a vocabulary table, the extraction process should retrieve all vocabulary pairs and correctly identify English and Cantonese terms
**Validates: Requirements 3.1, 3.2, 3.3, 3.5**

**Property 5: Anki package validity**
*For any* generated Anki package, it should be a valid .apkg file that imports successfully into Anki with all cards containing correct text fields and functional audio attachments
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

**Property 6: Format compatibility**
*For any* supported audio format (MP3, WAV, M4A) and any Google Docs table layout, the system should process inputs successfully and maintain output quality
**Validates: Requirements 3.4, 4.2, 4.4, 4.5**

**Property 7: Unique package generation**
*For any* set of processing runs, generated Anki packages should have unique identifiers to prevent import conflicts
**Validates: Requirements 5.5**

**Property 8: Comprehensive error reporting**
*For any* processing error or validation failure, the system should provide specific error messages identifying the problematic vocabulary terms or audio segments
**Validates: Requirements 6.2, 6.5**

**Property 9: Progress tracking completeness**
*For any* processing session, the system should provide progress indicators for all major steps and accurate completion summaries
**Validates: Requirements 6.1, 6.3, 6.4**

## Error Handling

The system implements comprehensive error handling across all processing stages:

### Input Validation Errors
- **Google Docs Access**: Handle authentication failures, invalid URLs, and permission issues
- **Audio File Validation**: Verify file format, duration, and audio quality before processing
- **Table Structure**: Detect missing or malformed vocabulary tables and provide specific guidance

### Processing Errors
- **Audio Segmentation Failures**: Handle cases where word boundaries cannot be reliably detected
- **Alignment Errors**: Manage situations where audio segments cannot be matched to vocabulary terms
- **Quality Degradation**: Detect when processing results in unusable audio or data quality

### Output Generation Errors
- **Anki Package Creation**: Handle file system errors, format compliance issues, and media embedding failures
- **File Naming Conflicts**: Ensure unique naming and handle duplicate detection

### Recovery Strategies
- **Partial Success Handling**: Allow users to proceed with successfully processed items when some fail
- **Manual Override Options**: Provide mechanisms for users to correct alignment or segmentation issues
- **Detailed Logging**: Maintain comprehensive logs for troubleshooting and improvement

## Testing Strategy

The testing approach combines unit testing for individual components with property-based testing for system-wide correctness guarantees.

### Unit Testing Approach
Unit tests will focus on:
- **Component Integration**: Testing interfaces between Google Docs processor, audio engine, alignment module, and Anki generator
- **Edge Cases**: Handling empty tables, silent audio, malformed documents, and corrupted files
- **Format Compatibility**: Verifying support for different audio formats and document structures
- **Error Conditions**: Testing specific failure scenarios and error message quality

### Property-Based Testing Approach
Property-based tests will use **Hypothesis** for Python to verify correctness properties across diverse inputs:
- **Minimum 100 iterations** per property test to ensure statistical confidence
- **Smart generators** that create realistic Google Docs structures and audio patterns
- **Constraint-based testing** that respects real-world limitations (audio duration, vocabulary count, etc.)
- **Quality metrics validation** to ensure output meets language learning standards

Each property-based test will be tagged with comments explicitly referencing the design document property:
- Format: `# Feature: cantonese-anki-generator, Property X: [property description]`
- This ensures traceability between correctness properties and their test implementations

### Integration Testing
- **End-to-end pipeline testing** with real Google Docs and audio samples
- **Anki compatibility verification** using actual Anki import processes
- **Performance testing** with various file sizes and vocabulary counts
- **Cross-platform compatibility** testing on different operating systems

The dual testing approach ensures both concrete functionality (unit tests) and universal correctness (property tests), providing comprehensive validation of the system's reliability and accuracy.