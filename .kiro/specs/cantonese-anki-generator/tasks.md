# Implementation Plan

- [x] 1. Set up project structure and core interfaces





  - Create directory structure for processors, audio, alignment, and anki modules
  - Define core data model classes (VocabularyEntry, AudioSegment, AlignedPair, AnkiCard)
  - Set up Python project with requirements.txt and basic configuration
  - Initialize testing framework with Hypothesis for property-based testing
  - _Requirements: 1.1, 1.4_

- [ ]* 1.1 Write property test for data model validation
  - **Property 1: Complete pipeline processing**
  - **Validates: Requirements 1.1, 1.2, 1.4**


- [x] 2. Implement Google Docs processor



  - [x] 2.1 Create Google Docs API authentication module


    - Implement OAuth2 flow for Google Docs access
    - Handle authentication token management and refresh
    - Create configuration for API credentials
    - _Requirements: 3.1_

  - [x] 2.2 Implement document parsing and table extraction


    - Write functions to retrieve Google Docs content via API
    - Implement table detection and structure analysis
    - Create vocabulary extraction logic for English-Cantonese pairs
    - _Requirements: 3.2, 3.3_

  - [ ]* 2.3 Write property test for Google Docs extraction
    - **Property 4: Google Docs extraction completeness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**

  - [x] 2.4 Add support for various table formats and layouts


    - Handle different table structures and formatting variations
    - Implement robust text extraction with error recovery
    - _Requirements: 3.4, 3.5_

- [ ]* 2.5 Write unit tests for Google Docs processor
  - Test authentication flow and error handling
  - Test table parsing with various document structures
  - Test vocabulary extraction accuracy
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Implement audio processing and segmentation





  - [x] 3.1 Create audio file validation and loading module


    - Support multiple audio formats (MP3, WAV, M4A)
    - Implement audio quality validation and preprocessing
    - Handle file format conversion as needed
    - _Requirements: 4.4, 4.5_

  - [x] 3.2 Implement voice activity detection for speech regions


    - Use webrtcvad or similar library for voice detection
    - Handle background noise and varying audio quality
    - Create speech region identification algorithms
    - _Requirements: 1.5, 4.1_

  - [x] 3.3 Develop word boundary detection algorithms


    - Implement energy-based and spectral analysis for segmentation
    - Create algorithms that work without clear silence boundaries
    - Handle varying speech patterns and speeds
    - _Requirements: 2.4, 4.2, 4.3_

  - [ ]* 3.4 Write property test for audio segmentation
    - **Property 3: Audio segmentation preservation**
    - **Validates: Requirements 1.5, 2.4, 4.1, 4.3**

  - [x] 3.5 Implement audio clip generation and quality preservation


    - Create individual audio clips from segmented boundaries
    - Ensure audio quality suitable for pronunciation learning
    - Handle clip smoothing and fade-in/fade-out
    - _Requirements: 2.1, 2.5_

- [ ]* 3.6 Write unit tests for audio processing
  - Test audio format compatibility and loading
  - Test voice activity detection with various noise levels
  - Test segmentation quality and boundary detection
  - _Requirements: 1.5, 2.1, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement forced alignment module




  - [x] 5.1 Set up forced alignment toolkit integration


    - Integrate Montreal Forced Alignment (MFA) or similar toolkit
    - Create Cantonese pronunciation dictionary support
    - Handle phonetic transcription for alignment
    - _Requirements: 2.2_

  - [x] 5.2 Implement audio-to-vocabulary alignment logic


    - Match segmented audio clips to vocabulary terms
    - Calculate alignment confidence scores
    - Handle alignment validation and quality checks
    - _Requirements: 2.2, 2.3_

  - [ ]* 5.3 Write property test for audio-vocabulary alignment
    - **Property 2: Audio-vocabulary alignment consistency**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 5.4 Add alignment refinement and error recovery


    - Implement alignment quality validation
    - Create fallback strategies for poor alignment results
    - Handle cases where alignment confidence is low
    - _Requirements: 2.2, 2.4_

- [ ]* 5.5 Write unit tests for forced alignment
  - Test alignment accuracy with known audio-text pairs
  - Test confidence score calculation and validation
  - Test error recovery for poor alignment cases
  - _Requirements: 2.2, 2.3, 2.4_

- [x] 6. Implement Anki package generator
  - [x] 6.1 Create Anki card template and formatting
    - Design card templates with English front, Cantonese back
    - Implement audio attachment functionality
    - Create proper card styling and layout
    - _Requirements: 1.3, 5.3_

  - [x] 6.2 Implement .apkg package creation
    - Use genanki library to create valid Anki packages
    - Embed audio files and media in package
    - Generate proper package metadata and structure
    - _Requirements: 1.2, 5.1, 5.4_

  - [ ]* 6.3 Write property test for Anki package validity
    - **Property 5: Anki package validity**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [x] 6.4 Add unique naming and conflict prevention
    - Generate unique deck and package identifiers
    - Prevent naming conflicts during import
    - Handle multiple deck generation scenarios
    - _Requirements: 5.5_

  - [ ]* 6.5 Write property test for unique package generation
    - **Property 7: Unique package generation**
    - **Validates: Requirements 5.5**

- [ ]* 6.6 Write unit tests for Anki package generator
  - Test card template creation and formatting
  - Test .apkg package structure and validity
  - Test audio embedding and file references
  - Test unique naming and conflict prevention
  - _Requirements: 1.2, 1.3, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Implement error handling and user feedback




  - [x] 7.1 Create comprehensive error handling system


    - Implement error detection for all processing stages
    - Create specific error messages with actionable guidance
    - Handle partial success scenarios gracefully
    - _Requirements: 6.2, 6.5_

  - [x] 7.2 Implement progress tracking and user feedback


    - Create progress indicators for major processing steps
    - Implement completion summaries with accurate counts
    - Add detailed logging for troubleshooting
    - _Requirements: 6.1, 6.3, 6.4_

  - [ ]* 7.3 Write property test for error reporting
    - **Property 8: Comprehensive error reporting**
    - **Validates: Requirements 6.2, 6.5**

  - [ ]* 7.4 Write property test for progress tracking
    - **Property 9: Progress tracking completeness**
    - **Validates: Requirements 6.1, 6.3, 6.4**

- [ ]* 7.5 Write unit tests for error handling and feedback
  - Test error message quality and specificity
  - Test progress indicator accuracy
  - Test logging functionality and completeness
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_


- [x] 8. Create main pipeline orchestrator




  - [x] 8.1 Implement main processing pipeline


    - Coordinate all processing stages in sequence
    - Handle data flow between components
    - Implement pipeline error recovery and validation
    - _Requirements: 1.1, 1.2, 1.4_

  - [x] 8.2 Add format compatibility and robustness features


    - Ensure support for all specified audio and document formats
    - Implement quality tolerance and adaptation mechanisms
    - Handle edge cases and format variations
    - _Requirements: 3.4, 4.2, 4.4, 4.5_

  - [ ]* 8.3 Write property test for format compatibility
    - **Property 6: Format compatibility**
    - **Validates: Requirements 3.4, 4.2, 4.4, 4.5**

  - [x] 8.4 Create command-line interface and user interaction


    - Implement CLI for Google Doc URL and audio file input
    - Add user-friendly interface with clear instructions
    - Handle file path validation and input processing
    - _Requirements: 1.1, 1.4_

- [ ]* 8.5 Write integration tests for complete pipeline
  - Test end-to-end processing with real Google Docs and audio
  - Test pipeline robustness with various input combinations
  - Test CLI interface and user interaction flows
  - _Requirements: 1.1, 1.2, 1.3, 1.4_


- [x] 9. Final checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement global transcription-based segment reassignment
  - [x] 10.1 Create similarity matrix builder
    - Implement function to compute Jyutping similarity between all transcriptions and all expected terms
    - Weight similarities by Whisper confidence scores
    - Handle empty transcriptions and missing data gracefully
    - _Requirements: 7.1, 7.2_

  - [x] 10.2 Integrate Hungarian algorithm for optimal assignment
    - Use scipy.optimize.linear_sum_assignment for assignment problem
    - Negate similarity matrix for maximization (algorithm minimizes by default)
    - Extract optimal segment-to-term mappings from algorithm output
    - _Requirements: 7.3, 7.4_

  - [x] 10.3 Implement segment reassignment logic
    - Create new segment-term mappings based on optimal assignment
    - Update confidence scores based on new similarity values
    - Sort reassigned terms by audio segment start times to maintain temporal order
    - Handle edge cases where no good match exists
    - _Requirements: 7.4, 7.5, 7.6_

  - [x] 10.4 Add comprehensive reassignment logging
    - Log similarity matrix with top matches for each segment
    - Report which segments were reassigned and why
    - Show before/after mappings with similarity scores
    - Display confidence improvements from reassignment
    - _Requirements: 7.7_

  - [ ]* 10.5 Write property test for global reassignment correctness
    - **Property 10: Global transcription-based reassignment correctness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8**

  - [ ]* 10.6 Write unit tests for reassignment module
    - Test similarity matrix construction with various transcription qualities
    - Test Hungarian algorithm integration and output correctness
    - Test reassignment logic with known misalignment patterns
    - Test temporal ordering after reassignment
    - Test logging output completeness and accuracy
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 10.7 Integrate reassignment into main alignment pipeline
    - Call reassignment after initial Whisper verification completes
    - Pass transcription data and expected terms to reassignment module
    - Update aligned segments with reassigned mappings
    - Ensure pipeline continues correctly with reassigned data
    - _Requirements: 7.1, 7.3_

- [x] 11. Fix silence detection and initial segmentation failures
  - [x] 11.1 Fix auto-detection of leading silence in smart_segmentation.py
    - Debug why "No speech detected in first 3.00s" is occurring
    - Verify RMS calculation and threshold comparison logic is correct
    - Ensure detected speech position is actually used as start_offset
    - Add detailed logging of RMS values, thresholds, and detection points
    - _Requirements: 4.1, 4.3_

  - [x] 11.2 Revert contradictory parameter changes
    - Revert speech_threshold from 0.10 back to 0.15 (original value)
    - Revert minimum silence to skip from 0.4s back to 0.2s (original value)
    - Document why these original values were correct
    - _Requirements: 4.1, 4.3_

  - [x] 11.3 Test and verify initial segmentation produces correct boundaries
    - Upload test audio file and verify first segment starts at correct position (~1.79s, not 0.36s)
    - Verify "Auto-detected X.XXs of leading silence" log shows correct value
    - Verify Term 1 gets correct audio (not silence/noise)
    - Verify all subsequent terms are correctly aligned
    - _Requirements: 2.4, 4.1, 4.3_

  - [x] 11.4 Improve post-reassignment validation logic
    - Change validation to compare new assignment with original (not absolute threshold)
    - Only revert to original if original was demonstrably better
    - Add logging to explain why reversions occur
    - _Requirements: 7.4, 7.5_

  - [x] 11.5 Fix boundary refinement trigger condition
    - Allow boundary refinement to run even when reassignments list is empty
    - Boundary refinement should detect and fix silence/out-of-order segments independently
    - Update condition from "if reassignments" to "if audio_data is not None"
    - _Requirements: 7.6_

  - [ ]* 11.6 Write integration test for silence detection fix
    - Test with audio file that has leading silence
    - Verify first segment starts after silence is skipped
    - Verify all terms get correct audio segments
    - Test that global reassignment accepts assignments (similarity > 0.3)
    - _Requirements: 4.1, 4.3, 7.4_