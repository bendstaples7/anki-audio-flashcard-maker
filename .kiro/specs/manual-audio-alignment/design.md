# Design Document

## Overview

The Manual Audio Alignment feature provides an interactive web-based interface for reviewing and correcting audio-term alignments in the Cantonese Anki Generator. The system displays vocabulary terms alongside visual waveform representations of their audio segments, allowing users to play back audio clips and manually adjust alignment boundaries through draggable markers. The design leverages modern web technologies including Flask for the backend, WaveSurfer.js for interactive waveform visualization, and a responsive HTML/CSS/JavaScript frontend. The interface integrates seamlessly with the existing processing pipeline, using automatic alignment as a starting point and allowing users to refine results before generating the final Anki package.

## Architecture

The system follows a client-server architecture with clear separation between the web frontend and Python backend:

### Frontend Layer
- **Web Interface**: HTML/CSS/JavaScript single-page application
- **Waveform Visualization**: WaveSurfer.js library for interactive audio waveforms
- **Audio Playback**: Web Audio API for playing audio segments
- **Interactive Controls**: Draggable boundary markers using WaveSurfer.js regions plugin

### Backend Layer
- **Flask Web Server**: Lightweight Python web server for serving the UI and handling API requests
- **Processing Integration**: Direct integration with existing cantonese_anki_generator pipeline
- **Session Management**: Store alignment state and user adjustments per session
- **Audio Processing**: Generate audio clips based on user-adjusted boundaries

### Data Layer
- **Session Storage**: In-memory or file-based storage for alignment sessions
- **Audio File Management**: Temporary storage for uploaded audio and generated clips
- **Alignment State**: JSON-based storage of boundary positions and adjustment flags

## Components and Interfaces

### Frontend Components

#### File Upload Component
- **Purpose**: Handle vocabulary document URL and audio file upload
- **Interface**: HTML form with file input and URL field
- **Key Features**:
  - Drag-and-drop audio file upload
  - Google Docs/Sheets URL validation
  - File format validation (MP3, WAV, M4A)
  - Upload progress indication

#### Alignment Table Component
- **Purpose**: Display all vocabulary terms with their audio segments
- **Interface**: Scrollable table with term rows
- **Key Features**:
  - English term and Cantonese text display
  - Embedded waveform for each term
  - Play button for audio playback
  - Visual indicators for manual adjustments
  - Quality/confidence score display

#### Waveform Viewer Component
- **Purpose**: Render interactive audio waveforms with adjustable boundaries
- **Dependencies**: WaveSurfer.js library
- **Interface**: Canvas-based waveform with draggable region markers
- **Key Methods**:
  - `renderWaveform(audioData, startTime, endTime)`: Display waveform segment
  - `updateBoundaries(newStart, newEnd)`: Update region boundaries
  - `playSegment()`: Play audio for current boundaries
  - `highlightRegion(start, end)`: Visual feedback for selected region

#### Full Waveform Overview Component
- **Purpose**: Display entire audio file with all term boundaries marked
- **Dependencies**: WaveSurfer.js with regions plugin
- **Interface**: Full-width waveform with multiple region overlays
- **Key Features**:
  - Zoom and pan controls
  - Click-to-navigate to specific terms
  - Color-coded boundary markers
  - Visual indication of manual adjustments

#### Boundary Adjuster Component
- **Purpose**: Interactive controls for adjusting alignment boundaries
- **Dependencies**: WaveSurfer.js regions plugin
- **Interface**: Draggable markers on waveform, numeric time inputs
- **Key Methods**:
  - `onDragStart(event)`: Handle drag initiation
  - `onDrag(event)`: Update boundary position during drag
  - `onDragEnd(event)`: Finalize boundary adjustment
  - `validateBoundaries()`: Prevent overlapping segments

### Backend Components

#### Flask Application
- **Purpose**: Serve web interface and handle API requests
- **Dependencies**: Flask, Flask-CORS
- **Routes**:
  - `GET /`: Serve main HTML page
  - `POST /api/upload`: Handle file uploads and initiate processing
  - `GET /api/session/<session_id>`: Retrieve alignment session data
  - `POST /api/session/<session_id>/update`: Save boundary adjustments
  - `POST /api/session/<session_id>/generate`: Generate Anki package with adjustments
  - `GET /api/audio/<session_id>/<term_id>`: Serve audio segment for playback

#### Processing Controller
- **Purpose**: Orchestrate automatic alignment and session creation
- **Dependencies**: Existing cantonese_anki_generator modules
- **Interface**: `process_upload(doc_url, audio_file) -> session_id`
- **Key Methods**:
  - `run_automatic_alignment()`: Execute existing alignment pipeline
  - `create_session()`: Initialize alignment session with results
  - `calculate_confidence_scores()`: Compute alignment quality metrics
  - `extract_audio_segments()`: Generate audio data for frontend

#### Session Manager
- **Purpose**: Manage alignment sessions and user adjustments
- **Dependencies**: JSON file storage or in-memory dict
- **Interface**: `SessionManager` class with CRUD operations
- **Key Methods**:
  - `create_session(alignment_data)`: Create new session
  - `get_session(session_id)`: Retrieve session data
  - `update_boundaries(session_id, term_id, start, end)`: Save adjustment
  - `mark_manual_adjustment(session_id, term_id)`: Flag manual edits
  - `get_all_alignments(session_id)`: Get current alignment state

#### Anki Package Generator
- **Purpose**: Generate final Anki package using adjusted alignments
- **Dependencies**: Existing anki package_generator module
- **Interface**: `generate_with_adjustments(session_id) -> apkg_file`
- **Key Methods**:
  - `apply_boundary_adjustments()`: Use user-adjusted boundaries
  - `generate_audio_clips()`: Create clips from adjusted segments
  - `create_anki_package()`: Build final .apkg file
  - `cleanup_session()`: Remove temporary files

## Data Models

### AlignmentSession
```python
@dataclass
class AlignmentSession:
    session_id: str
    doc_url: str
    audio_file_path: str
    created_at: datetime
    terms: List[TermAlignment]
    audio_duration: float
    status: str  # "processing", "ready", "generating", "complete"
```

### TermAlignment
```python
@dataclass
class TermAlignment:
    term_id: str
    english: str
    cantonese: str
    start_time: float  # seconds
    end_time: float  # seconds
    original_start: float  # for reset functionality
    original_end: float
    is_manually_adjusted: bool
    confidence_score: float  # 0.0 to 1.0
    audio_segment_url: str  # URL to audio file for this term
```

### BoundaryUpdate
```python
@dataclass
class BoundaryUpdate:
    term_id: str
    new_start_time: float
    new_end_time: float
    timestamp: datetime
```

### SessionState
```python
@dataclass
class SessionState:
    session_id: str
    alignments: List[TermAlignment]
    updates: List[BoundaryUpdate]
    last_modified: datetime
```

### GenerationRequest
```python
@dataclass
class GenerationRequest:
    session_id: str
    output_filename: str
    include_manual_adjustments: bool = True
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated:

- Properties 2.1, 2.2, 2.3, and 2.4 all test alignment table display and can be combined into comprehensive display properties
- Properties 3.1, 3.2, 3.3, 3.4, and 3.5 all test audio playback and can be merged into playback management properties
- Properties 4.1, 4.2, 4.3, 4.4, and 4.5 all test boundary adjustment and can be consolidated
- Properties 5.1, 5.2, 5.3, 5.4, and 5.5 all test full waveform display and can be combined
- Properties 8.2, 8.3, 8.4, and 8.5 all test session persistence and can be merged

### Core Properties

**Property 1: URL validation correctness**
*For any* Google Docs or Sheets URL input, the validation system should correctly identify valid URLs as acceptable and invalid URLs as requiring correction, with specific error messages
**Validates: Requirements 1.2, 1.5**

**Property 2: Audio file validation correctness**
*For any* uploaded audio file, the validation system should correctly identify supported formats (MP3, WAV, M4A) as valid and unsupported formats as invalid, with clear error messages
**Validates: Requirements 1.3, 1.5**

**Property 3: UI state management based on input validity**
*For any* combination of URL and audio file inputs, the Process button should be enabled if and only if both inputs are present and valid
**Validates: Requirements 1.4**

**Property 4: Alignment table completeness**
*For any* set of vocabulary terms after automatic alignment, the alignment table should display all terms with their English text, Cantonese text, waveform display, and boundary markers
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

**Property 5: Audio playback isolation**
*For any* term in the alignment table, clicking play should play only that term's audio segment (defined by current boundaries) and stop any other currently playing audio
**Validates: Requirements 3.1, 3.2, 3.5**

**Property 6: Playback state transitions**
*For any* audio playback, the UI should show active playback state while playing and return to ready state when playback completes
**Validates: Requirements 3.3, 3.4**

**Property 7: Boundary adjustment non-overlap constraint**
*For any* boundary adjustment on any term, the new boundaries should not overlap with adjacent terms' boundaries
**Validates: Requirements 4.3**

**Property 8: Boundary adjustment real-time updates**
*For any* boundary adjustment, the waveform display should update in real-time during dragging and playback should use the updated boundaries immediately
**Validates: Requirements 4.2, 4.4**

**Property 9: Manual adjustment visual indicators**
*For any* term with manually adjusted boundaries, the UI should display a visual indicator distinguishing it from automatically aligned terms
**Validates: Requirements 4.5**

**Property 10: Full waveform boundary display**
*For any* set of term alignments, the full waveform view should display all boundary markers for all terms
**Validates: Requirements 5.2**

**Property 11: Full waveform navigation**
*For any* boundary marker clicked in the full waveform view, the UI should scroll to and highlight the corresponding term row in the alignment table
**Validates: Requirements 5.3**

**Property 12: Waveform synchronization**
*For any* boundary adjustment made in the term table, the full waveform display should reflect the updated boundaries immediately
**Validates: Requirements 5.5**

**Property 13: Zoom pan navigation**
*For any* zoomed waveform view, pan controls should allow navigation along the entire audio timeline
**Validates: Requirements 6.3**

**Property 14: Zoom precision preservation**
*For any* boundary adjustment made while zoomed, the adjustment should maintain fine-grained time precision
**Validates: Requirements 6.4**

**Property 15: Zoom state display**
*For any* zoom level, the UI should display the current zoom level and visible time range accurately
**Validates: Requirements 6.5**

**Property 16: Generation uses adjusted boundaries**
*For any* session with manual boundary adjustments, the generated Anki package should use the adjusted boundaries (not original automatic boundaries) for all audio clips
**Validates: Requirements 7.2**

**Property 17: Generation progress feedback**
*For any* Anki package generation, the UI should display progress feedback during the generation process
**Validates: Requirements 7.3**

**Property 18: Generation completion access**
*For any* successfully completed generation, the UI should provide a download link or save dialog for the .apkg file
**Validates: Requirements 7.4**

**Property 19: Generation summary accuracy**
*For any* completed generation, the summary should accurately show the total number of terms and which terms were manually adjusted
**Validates: Requirements 7.5**

**Property 20: Session persistence round-trip**
*For any* alignment session with manual adjustments, saving then reloading the session should restore all boundary positions and manual adjustment flags exactly
**Validates: Requirements 8.2, 8.3**

**Property 21: Session file association**
*For any* saved session, the session should be correctly associated with its specific vocabulary document and audio file combination
**Validates: Requirements 8.4**

**Property 22: Session load validation**
*For any* saved session being loaded, the system should validate that the original files are still accessible and display errors if not
**Validates: Requirements 8.5**

**Property 23: Reset button visibility**
*For any* term in the alignment table, a reset button should be visible if and only if that term has been manually adjusted
**Validates: Requirements 9.1**

**Property 24: Reset restores original boundaries**
*For any* manually adjusted term, clicking reset should restore the original automatic alignment boundaries and remove the manual adjustment indicator
**Validates: Requirements 9.2, 9.3**

**Property 25: Reset all functionality**
*For any* session with multiple manual adjustments, the "Reset All" function should restore all terms to their original automatic alignment boundaries
**Validates: Requirements 9.4**

**Property 26: Reset confirmation**
*For any* reset operation (individual or all), the system should request user confirmation before applying the reset
**Validates: Requirements 9.5**

**Property 27: Quality indicator display**
*For any* term in the alignment table, a confidence score or quality indicator should be displayed
**Validates: Requirements 10.1**

**Property 28: Low confidence highlighting**
*For any* term with a low confidence score, the term row should be visually highlighted to draw attention
**Validates: Requirements 10.2**

**Property 29: Quality-based sorting**
*For any* alignment table with quality indicators, sorting or filtering by confidence score should correctly order terms with low-confidence alignments first
**Validates: Requirements 10.3**

**Property 30: Quality indicator help text**
*For any* quality indicator displayed, tooltip or help text should be available explaining what the indicator means
**Validates: Requirements 10.5**

## Error Handling

The system implements comprehensive error handling across all layers:

### File Upload Errors
- **Invalid URL Format**: Immediate validation feedback with format examples
- **Inaccessible Document**: Clear message about permissions or network issues
- **Unsupported Audio Format**: List of supported formats and conversion suggestions
- **File Size Limits**: Display maximum file size and suggest compression
- **Upload Failures**: Retry mechanism with progress indication

### Processing Errors
- **Alignment Failures**: Fallback to basic segmentation with warning
- **Audio Loading Errors**: Detailed error about file corruption or format issues
- **Insufficient Terms**: Warning if vocabulary list is empty or malformed
- **Memory Limitations**: Graceful handling of large audio files

### Session Errors
- **Session Not Found**: Clear message with option to start new session
- **Session Expired**: Automatic cleanup with user notification
- **Concurrent Modifications**: Conflict resolution or last-write-wins strategy
- **Storage Failures**: Fallback to in-memory storage with warning

### Boundary Adjustment Errors
- **Overlap Detection**: Visual feedback preventing invalid adjustments
- **Out of Bounds**: Constrain adjustments to audio file duration
- **Invalid Time Values**: Validation and correction of manual time inputs
- **Rapid Updates**: Debouncing to prevent performance issues

### Generation Errors
- **Missing Audio Segments**: Skip problematic terms with warning
- **Disk Space Issues**: Check available space before generation
- **Package Creation Failures**: Detailed error with recovery options
- **Cleanup Failures**: Log errors but don't block user workflow

## Testing Strategy

The testing approach combines unit tests for backend logic, integration tests for API endpoints, and property-based tests for correctness validation.

### Unit Testing Approach
Unit tests will focus on:
- **Session Management**: Creating, updating, and retrieving sessions
- **Boundary Validation**: Overlap detection and constraint enforcement
- **Audio Segment Extraction**: Correct time-based audio slicing
- **Confidence Score Calculation**: Alignment quality metrics
- **File Upload Handling**: Validation and storage logic

### Property-Based Testing Approach
Property-based tests will use **Hypothesis** for Python backend testing:
- **Minimum 100 iterations** per property test for statistical confidence
- **Smart generators** for creating realistic alignment data, time boundaries, and user interactions
- **Boundary constraint validation** across random adjustment sequences
- **Session persistence verification** with random state modifications

Each property-based test will be tagged with comments referencing the design document property:
- Format: `# Feature: manual-audio-alignment, Property X: [property description]`
- This ensures traceability between correctness properties and test implementations

### Frontend Testing
- **Waveform Rendering**: Verify correct visualization of audio data
- **Boundary Dragging**: Test interactive marker movement and constraints
- **Audio Playback**: Validate correct segment playback
- **UI State Management**: Test button states and visual feedback
- **Responsive Design**: Verify layout across different screen sizes

### Integration Testing
- **End-to-End Workflows**: Complete flow from upload to Anki generation
- **API Endpoint Testing**: Verify all Flask routes with various inputs
- **Session Lifecycle**: Test creation, modification, and cleanup
- **File Handling**: Upload, storage, and retrieval of audio files
- **Error Scenarios**: Simulate failures at each stage

### Performance Testing
- **Large Audio Files**: Test with 30+ minute audio files
- **Many Terms**: Validate with 100+ vocabulary terms
- **Concurrent Sessions**: Multiple users with separate sessions
- **Waveform Rendering**: Measure rendering time for large waveforms
- **Boundary Adjustment Responsiveness**: Ensure smooth dragging

The dual testing approach ensures both specific functionality (unit tests) and universal correctness (property tests), providing comprehensive validation of the alignment review system's reliability and usability.
