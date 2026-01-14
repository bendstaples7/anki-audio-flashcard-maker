# Design Document

## Overview

The Cantonese Anki Generator UI is a local desktop application built using Python's built-in Tkinter library. The design emphasizes simplicity and zero-cost deployment, providing a clean graphical interface that runs entirely on the user's machine. Users can select their vocabulary documents and audio files through familiar file dialogs, monitor processing progress, and save their generated Anki decks locally. The UI acts as a wrapper around the existing command-line functionality, exposing the same powerful features through an intuitive desktop interface.

## Architecture

The system follows a simple desktop application architecture with direct integration to the core processing engine:

### GUI Layer
- **Tkinter Desktop Interface**: Native Python GUI using built-in Tkinter library
- **File Dialog Integration**: Standard OS file selection dialogs for documents and audio
- **Progress Monitoring**: Real-time progress bars and status updates during processing

### Processing Layer  
- **Direct Integration**: Direct calls to existing cantonese_anki_generator functionality
- **Threading**: Background processing using Python threading to keep UI responsive
- **Local File Management**: Simple file handling with user-selected input and output locations

### Integration Layer
- **Core Engine Wrapper**: Direct import and usage of existing processing pipeline
- **Progress Callbacks**: Extract progress information from core processing stages
- **Error Handling**: Convert processing errors to user-friendly dialog messages

## Components and Interfaces

### Desktop GUI Components

#### Main Application Window
- **Purpose**: Primary interface for user interaction and process control
- **Interface**: Tkinter main window with organized layout sections
- **Key Features**:
  - Google Docs URL input field with validation
  - Audio file selection button with file dialog
  - Process start button and progress monitoring
  - Output location selection and results display

#### File Selection Component  
- **Purpose**: Handle Google Docs URL input and audio file selection
- **Interface**: Standard file dialogs and input validation
- **Key Features**:
  - URL input field with real-time validation
  - "Browse" button opening OS file dialog for audio files
  - File format and size validation with immediate feedback
  - Clear display of selected files and validation status

#### Progress Monitor Component
- **Purpose**: Display real-time processing status and progress
- **Interface**: Tkinter progress bar and status label updates
- **Key Features**:
  - Progress bar showing completion percentage
  - Status text describing current processing stage
  - Estimated time remaining display
  - Cancel button for stopping processing

#### Results Display Component
- **Purpose**: Show processing results and provide access to generated files
- **Interface**: Results panel with file information and action buttons
- **Key Features**:
  - Success/failure status with detailed information
  - Generated file location and card count display
  - "Open Folder" button to reveal output location
  - "Open in Anki" button for direct import (if Anki is installed)

### Core Integration Components

#### Processing Controller
- **Purpose**: Orchestrate background processing and UI updates
- **Dependencies**: Threading for async processing, existing core engine
- **Interface**: `start_processing(doc_url, audio_file, output_dir, progress_callback)`
- **Key Methods**:
  - `run_processing_thread()`: Execute core engine in background thread
  - `update_progress()`: Receive progress updates and update UI
  - `handle_completion()`: Process results and update UI state

#### File Manager
- **Purpose**: Handle file validation and output management
- **Dependencies**: OS file system operations, core engine file handling
- **Interface**: `validate_inputs(url, audio_file)` and `manage_outputs(output_dir)`
- **Key Methods**:
  - `validate_google_docs_url()`: Check URL format and accessibility
  - `validate_audio_file()`: Verify file format and basic integrity
  - `select_output_location()`: Handle output directory selection

## Data Models

### ApplicationState
```python
@dataclass
class ApplicationState:
    google_docs_url: str = ""
    audio_file_path: str = ""
    output_directory: str = ""
    is_processing: bool = False
    current_stage: str = ""
    progress_percentage: float = 0.0
```

### ProcessingJob
```python
@dataclass  
class ProcessingJob:
    doc_url: str
    audio_file: str
    output_dir: str
    status: str  # "ready", "processing", "completed", "failed"
    current_stage: str
    progress_percentage: float
    start_time: datetime
    error_message: Optional[str] = None
```

### ProcessingResult
```python
@dataclass
class ProcessingResult:
    success: bool
    output_file_path: str
    card_count: int
    processing_time: float
    error_message: Optional[str] = None
```

### ValidationResult
```python
@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None
    suggestions: List[str] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated to eliminate redundancy:

- Properties 4.1, 4.2, 4.3, and 4.4 all test error handling and can be combined into comprehensive error management properties
- Properties 2.2, 2.3, and 2.4 all test progress indication and can be merged into a single progress tracking property  
- Properties 3.2, 3.3, 3.4, and 3.5 all test download functionality and can be consolidated
- Properties 1.2 and 1.3 both test input validation and can be combined
- Properties 6.1, 6.2, and 6.4 all test user interface guidance and can be merged

### Core Properties

**Property 1: Input validation consistency**
*For any* URL or file input, the validation system should correctly identify valid inputs as acceptable and invalid inputs as requiring correction, with immediate feedback
**Validates: Requirements 1.2, 1.3, 6.4**

**Property 2: UI state management**
*For any* combination of user inputs, the interface should enable or disable controls appropriately based on input completeness and validity
**Validates: Requirements 1.5, 4.5**

**Property 3: Progress tracking accuracy**
*For any* processing job, the progress indicator should advance monotonically and display accurate stage information and completion estimates
**Validates: Requirements 2.2, 2.3, 2.4**

**Property 4: Download functionality reliability**
*For any* successfully generated Anki package, the download system should provide working download links with correct filenames and package information
**Validates: Requirements 3.2, 3.3, 3.4**

**Property 5: Filename uniqueness**
*For any* sequence of package generations, each generated file should have a unique filename to prevent conflicts
**Validates: Requirements 3.5**

**Property 6: Error handling comprehensiveness**
*For any* error condition, the system should display user-friendly messages that categorize the error type and provide specific resolution guidance
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

**Property 7: Cross-device responsiveness**
*For any* screen size or device type, the interface should maintain functionality and appropriate layout adjustments
**Validates: Requirements 5.5**

**Property 8: Interface guidance completeness**
*For any* UI element or feature, the system should provide clear labels, instructions, and contextual help when needed
**Validates: Requirements 6.1, 6.2**

## Error Handling

The UI implements comprehensive error handling to provide clear feedback and recovery options:

### Input Validation Errors
- **URL Validation**: Real-time checking of Google Docs/Sheets URL format and accessibility
- **File Validation**: Immediate feedback on audio file format, size, and integrity
- **Form Completion**: Clear indication of missing required inputs before processing

### Processing Errors  
- **Backend Communication**: Handle network timeouts, server errors, and connection issues
- **Core Engine Errors**: Translate technical processing errors into user-friendly messages
- **Resource Limitations**: Manage file size limits, processing timeouts, and server capacity

### User Experience Errors
- **Browser Compatibility**: Graceful degradation for unsupported features
- **Session Management**: Handle session timeouts and state recovery
- **Download Failures**: Retry mechanisms and alternative download options

### Recovery Strategies
- **Input Preservation**: Maintain user inputs during error states to avoid re-entry
- **Retry Mechanisms**: Allow users to retry failed operations without losing progress
- **Progressive Enhancement**: Ensure basic functionality works even when advanced features fail

## Testing Strategy

The testing approach combines automated UI testing with property-based testing for comprehensive validation.

### Unit Testing Approach
Unit tests will focus on:
- **Component Functionality**: Testing individual UI components and their interactions
- **API Endpoints**: Verifying backend API responses and error handling
- **File Handling**: Testing upload, validation, and download mechanisms
- **Integration Points**: Ensuring proper communication between frontend and backend

### Property-Based Testing Approach
Property-based tests will use **Hypothesis** for Python backend testing and property-based testing principles for frontend validation:
- **Minimum 100 iterations** per property test to ensure statistical confidence
- **Smart input generators** that create realistic URLs, file uploads, and user interactions
- **Cross-browser testing** to verify properties hold across different environments
- **Responsive design validation** across various screen sizes and device types

Each property-based test will be tagged with comments explicitly referencing the design document property:
- Format: `# Feature: cantonese-anki-ui, Property X: [property description]`
- This ensures traceability between correctness properties and their test implementations

### Frontend Testing
- **DOM Manipulation Testing**: Verify UI state changes and element visibility
- **User Interaction Testing**: Simulate clicks, file uploads, and form submissions
- **Responsive Design Testing**: Validate layout across different viewport sizes
- **Accessibility Testing**: Ensure proper ARIA labels and keyboard navigation

### Integration Testing
- **End-to-end User Flows**: Complete workflows from upload to download
- **Backend Integration**: Testing communication between UI and processing engine
- **File Upload/Download**: Verifying complete file handling workflows
- **Error Scenario Testing**: Simulating various failure conditions and recovery

The dual testing approach ensures both specific functionality (unit tests) and universal correctness (property tests), providing comprehensive validation of the UI's reliability and usability.