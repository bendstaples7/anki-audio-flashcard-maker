# Implementation Plan: Manual Audio Alignment

## Overview

This implementation plan breaks down the Manual Audio Alignment feature into discrete coding tasks. The approach follows a layered implementation strategy: first establishing the Flask backend infrastructure, then building the core alignment session management, followed by the interactive frontend with WaveSurfer.js, and finally integrating with the existing Anki generation pipeline. Each task builds incrementally on previous work, with checkpoints to validate functionality before proceeding.

## Tasks

- [x] 0. Create feature branch for manual audio alignment
  - Create new git branch named `feature/manual-audio-alignment`
  - Switch to the new branch
  - Verify branch creation with `git branch`
  - _Requirements: All_

- [x] 1. Set up Flask web application infrastructure
  - Create Flask application with basic routing structure
  - Set up CORS configuration for API endpoints
  - Configure static file serving for frontend assets
  - Create project directory structure for backend and frontend
  - _Requirements: 1.1_

- [x] 2. Implement file upload and validation
- [x] 2.1 Create file upload API endpoint
  - Implement POST /api/upload endpoint for audio files
  - Add file size validation and format checking
  - Store uploaded files in temporary directory
  - Return upload confirmation with file metadata
  - _Requirements: 1.3_

- [x] 2.2 Implement URL validation
  - Create URL validation function for Google Docs/Sheets
  - Add accessibility checking for provided URLs
  - Return validation results with specific error messages
  - _Requirements: 1.2_

- [ ]* 2.3 Write property test for URL validation
  - **Property 1: URL validation correctness**
  - **Validates: Requirements 1.2, 1.5**

- [ ]* 2.4 Write property test for audio file validation
  - **Property 2: Audio file validation correctness**
  - **Validates: Requirements 1.3, 1.5**

- [ ]* 2.5 Write unit tests for upload handling
  - Test file upload with various formats
  - Test URL validation with valid and invalid URLs
  - Test error message generation
  - _Requirements: 1.2, 1.3, 1.5_

- [x] 3. Implement alignment session management
- [x] 3.1 Create session data models
  - Define AlignmentSession, TermAlignment, and BoundaryUpdate dataclasses
  - Implement JSON serialization for session data
  - Create session ID generation function
  - _Requirements: 2.1_

- [x] 3.2 Implement SessionManager class
  - Create session creation method
  - Implement session retrieval and update methods
  - Add boundary update tracking
  - Implement session cleanup functionality
  - _Requirements: 8.1, 8.2_

- [ ]* 3.3 Write property test for session persistence
  - **Property 20: Session persistence round-trip**
  - **Validates: Requirements 8.2, 8.3**

- [ ]* 3.4 Write property test for session file association
  - **Property 21: Session file association**
  - **Validates: Requirements 8.4**

- [ ]* 3.5 Write unit tests for session management
  - Test session creation and retrieval
  - Test boundary updates
  - Test session cleanup
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 4. Integrate with existing alignment pipeline
- [x] 4.1 Create processing controller
  - Implement process_upload function to run automatic alignment
  - Extract alignment results into TermAlignment objects
  - Calculate confidence scores for each alignment
  - Create initial alignment session from results
  - _Requirements: 2.1_

- [x] 4.2 Implement audio segment extraction
  - Extract audio data for each term based on boundaries
  - Generate audio segment URLs for frontend playback
  - Store audio segments in temporary directory
  - _Requirements: 2.3, 3.1_

- [ ]* 4.3 Write integration tests for alignment pipeline
  - Test end-to-end processing from upload to session creation
  - Test confidence score calculation
  - Test audio segment extraction
  - _Requirements: 2.1, 2.3_

- [x] 5. Create session API endpoints
- [x] 5.1 Implement GET /api/session/<session_id>
  - Return complete session data including all term alignments
  - Include audio segment URLs for each term
  - Return confidence scores and adjustment flags
  - _Requirements: 2.1, 2.2_

- [x] 5.2 Implement POST /api/session/<session_id>/update
  - Accept boundary updates for specific terms
  - Validate boundaries don't overlap with adjacent terms
  - Mark terms as manually adjusted
  - Return updated session state
  - _Requirements: 4.1, 4.3_

- [ ]* 5.3 Write property test for boundary non-overlap
  - **Property 7: Boundary adjustment non-overlap constraint**
  - **Validates: Requirements 4.3**

- [x] 5.3 Implement GET /api/audio/<session_id>/<term_id>
  - Serve audio segment for specific term
  - Support range requests for audio streaming
  - Return appropriate audio content-type headers
  - _Requirements: 3.2_

- [ ]* 5.4 Write unit tests for session API endpoints
  - Test session retrieval with various session IDs
  - Test boundary updates with valid and invalid data
  - Test audio segment serving
  - _Requirements: 2.1, 2.2, 4.1, 4.3, 3.2_

- [x] 6. Build frontend HTML structure
- [x] 6.1 Create main HTML page
  - Create file upload form with URL input and audio file selector
  - Add alignment table container
  - Add full waveform overview container
  - Include control buttons (Process, Generate, Save, Reset All)
  - _Requirements: 1.1, 2.1, 5.1_

- [x] 6.2 Add CSS styling
  - Style file upload form and validation feedback
  - Style alignment table with term rows
  - Style waveform containers and controls
  - Add responsive design for different screen sizes
  - _Requirements: 1.1, 2.1_

- [x] 7. Implement frontend file upload and validation
- [x] 7.1 Create file upload JavaScript
  - Implement file selection and upload to backend
  - Add URL validation before submission
  - Display upload progress
  - Handle upload errors with user-friendly messages
  - _Requirements: 1.2, 1.3, 1.5_

- [x] 7.2 Implement UI state management for inputs
  - Enable/disable Process button based on input validity
  - Show validation feedback in real-time
  - Display error messages for invalid inputs
  - _Requirements: 1.4, 1.5_

- [ ]* 7.3 Write property test for UI state management
  - **Property 3: UI state management based on input validity**
  - **Validates: Requirements 1.4**

- [x] 8. Integrate WaveSurfer.js for waveform display
- [x] 8.1 Set up WaveSurfer.js library
  - Include WaveSurfer.js and regions plugin in HTML
  - Create WaveSurfer instance initialization function
  - Configure waveform rendering options
  - _Requirements: 2.3_

- [x] 8.2 Implement term waveform rendering
  - Create waveform viewer for each term row
  - Load audio segment data for each term
  - Render waveform with boundary markers
  - Add play button for each term
  - _Requirements: 2.3, 2.4, 3.1_

- [ ]* 8.3 Write property test for alignment table completeness
  - **Property 4: Alignment table completeness**
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 8.3 Implement full waveform overview
  - Create full-length waveform display
  - Overlay all term boundary markers
  - Add zoom and pan controls
  - Display current zoom level and time range
  - _Requirements: 5.1, 5.2, 6.1, 6.5_

- [ ]* 8.4 Write property test for full waveform boundary display
  - **Property 10: Full waveform boundary display**
  - **Validates: Requirements 5.2**

- [ ]* 8.5 Write unit tests for waveform rendering
  - Test waveform initialization
  - Test boundary marker display
  - Test zoom and pan controls
  - _Requirements: 2.3, 2.4, 5.1, 5.2, 6.1_

- [x] 9. Implement audio playback controls
- [x] 9.1 Create playback management system
  - Implement play button click handlers
  - Play audio segment for clicked term
  - Stop any currently playing audio when new audio starts
  - Update UI to show playback state
  - _Requirements: 3.1, 3.2, 3.5_

- [ ]* 9.2 Write property test for audio playback isolation
  - **Property 5: Audio playback isolation**
  - **Validates: Requirements 3.1, 3.2, 3.5**

- [x] 9.2 Implement playback state visualization
  - Show active playback indicator during audio play
  - Return to ready state when playback completes
  - Update button states during playback
  - _Requirements: 3.3, 3.4_

- [ ]* 9.3 Write property test for playback state transitions
  - **Property 6: Playback state transitions**
  - **Validates: Requirements 3.3, 3.4**

- [ ]* 9.4 Write unit tests for playback controls
  - Test play button functionality
  - Test playback state changes
  - Test stopping current audio when switching terms
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 10. Implement interactive boundary adjustment
- [x] 10.1 Create draggable boundary markers
  - Use WaveSurfer.js regions plugin for draggable markers
  - Implement drag event handlers
  - Update boundary positions during drag
  - Validate boundaries don't overlap adjacent terms
  - _Requirements: 4.1, 4.2, 4.3_

- [ ]* 10.2 Write property test for boundary adjustment real-time updates
  - **Property 8: Boundary adjustment real-time updates**
  - **Validates: Requirements 4.2, 4.4**

- [x] 10.2 Implement boundary update synchronization
  - Send boundary updates to backend API
  - Update waveform display in real-time
  - Update playback to use new boundaries immediately
  - Mark term as manually adjusted
  - _Requirements: 4.2, 4.4, 4.5_

- [ ]* 10.3 Write property test for manual adjustment indicators
  - **Property 9: Manual adjustment visual indicators**
  - **Validates: Requirements 4.5**

- [x] 10.3 Synchronize full waveform with table adjustments
  - Update full waveform boundary markers when table boundaries change
  - Ensure both views stay synchronized
  - _Requirements: 5.5_

- [ ]* 10.4 Write property test for waveform synchronization
  - **Property 12: Waveform synchronization**
  - **Validates: Requirements 5.5**

- [ ]* 10.5 Write unit tests for boundary adjustment
  - Test draggable marker functionality
  - Test overlap prevention
  - Test synchronization between views
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.5_

- [x] 11. Checkpoint - Ensure core alignment review works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement zoom and pan functionality
- [x] 12.1 Add zoom controls to full waveform
  - Implement zoom in/out buttons
  - Add zoom slider for precise control
  - Update waveform display at different zoom levels
  - _Requirements: 6.1_

- [x] 12.2 Implement pan navigation
  - Add pan controls for navigating zoomed waveform
  - Implement click-and-drag panning
  - Update visible time range display
  - _Requirements: 6.3, 6.5_

- [ ]* 12.3 Write property test for zoom pan navigation
  - **Property 13: Zoom pan navigation**
  - **Validates: Requirements 6.3**

- [x] 12.3 Maintain adjustment precision while zoomed
  - Ensure boundary adjustments work at all zoom levels
  - Provide fine-grained time precision when zoomed
  - _Requirements: 6.4_

- [ ]* 12.4 Write property test for zoom precision preservation
  - **Property 14: Zoom precision preservation**
  - **Validates: Requirements 6.4**

- [ ]* 12.5 Write property test for zoom state display
  - **Property 15: Zoom state display**
  - **Validates: Requirements 6.5**

- [ ]* 12.6 Write unit tests for zoom and pan
  - Test zoom controls functionality
  - Test pan navigation
  - Test boundary adjustment precision at different zoom levels
  - _Requirements: 6.1, 6.3, 6.4, 6.5_

- [x] 13. Implement full waveform navigation
- [x] 13.1 Add click-to-navigate functionality
  - Implement click handler on full waveform boundary markers
  - Scroll alignment table to corresponding term row
  - Highlight selected term row
  - _Requirements: 5.3_

- [ ]* 13.2 Write property test for full waveform navigation
  - **Property 11: Full waveform navigation**
  - **Validates: Requirements 5.3**

- [ ]* 13.3 Write unit tests for navigation
  - Test clicking boundary markers
  - Test scrolling to term rows
  - Test row highlighting
  - _Requirements: 5.3_

- [x] 14. Implement session save and load
- [x] 14.1 Create save progress functionality
  - Add "Save Progress" button
  - Send current session state to backend
  - Store session with all boundary adjustments
  - Display save confirmation
  - _Requirements: 8.1, 8.2_

- [x] 14.2 Implement session loading
  - Add session ID to URL for sharing/bookmarking
  - Load saved session on page load if session ID present
  - Restore all boundary positions and adjustment flags
  - Validate original files are still accessible
  - _Requirements: 8.3, 8.5_

- [ ]* 14.3 Write property test for session load validation
  - **Property 22: Session load validation**
  - **Validates: Requirements 8.5**

- [ ]* 14.4 Write unit tests for save and load
  - Test save progress functionality
  - Test session loading
  - Test file accessibility validation
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 15. Implement reset functionality
- [x] 15.1 Add individual term reset
  - Display reset button for manually adjusted terms
  - Implement reset button click handler
  - Request confirmation before resetting
  - Restore original automatic alignment boundaries
  - Remove manual adjustment indicator
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [ ]* 15.2 Write property test for reset button visibility
  - **Property 23: Reset button visibility**
  - **Validates: Requirements 9.1**

- [ ]* 15.3 Write property test for reset restores original boundaries
  - **Property 24: Reset restores original boundaries**
  - **Validates: Requirements 9.2, 9.3**

- [x] 15.2 Add reset all functionality
  - Implement "Reset All" button
  - Request confirmation before resetting all
  - Restore all terms to original automatic alignment
  - _Requirements: 9.4, 9.5_

- [ ]* 15.4 Write property test for reset all functionality
  - **Property 25: Reset all functionality**
  - **Validates: Requirements 9.4**

- [ ]* 15.5 Write property test for reset confirmation
  - **Property 26: Reset confirmation**
  - **Validates: Requirements 9.5**

- [ ]* 15.6 Write unit tests for reset functionality
  - Test individual term reset
  - Test reset all
  - Test confirmation dialogs
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 16. Implement quality indicators
- [x] 16.1 Display confidence scores
  - Show confidence score or quality indicator for each term
  - Use visual cues (colors, icons) for different quality levels
  - Highlight low-confidence terms
  - _Requirements: 10.1, 10.2_

- [ ]* 16.2 Write property test for quality indicator display
  - **Property 27: Quality indicator display**
  - **Validates: Requirements 10.1**

- [ ]* 16.3 Write property test for low confidence highlighting
  - **Property 28: Low confidence highlighting**
  - **Validates: Requirements 10.2**

- [x] 16.2 Add sorting and filtering by quality
  - Implement sort by confidence score
  - Add filter to show only low-confidence terms
  - Update table display based on sort/filter
  - _Requirements: 10.3_

- [ ]* 16.4 Write property test for quality-based sorting
  - **Property 29: Quality-based sorting**
  - **Validates: Requirements 10.3**

- [x] 16.3 Add quality indicator help text
  - Add tooltips explaining quality indicators
  - Include help text for confidence scores
  - _Requirements: 10.5_

- [ ]* 16.5 Write property test for quality indicator help text
  - **Property 30: Quality indicator help text**
  - **Validates: Requirements 10.5**

- [ ]* 16.6 Write unit tests for quality indicators
  - Test confidence score display
  - Test sorting and filtering
  - Test tooltip functionality
  - _Requirements: 10.1, 10.2, 10.3, 10.5_

- [x] 17. Checkpoint - Ensure all review features work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Implement Anki package generation with adjustments
- [x] 18.1 Create generation API endpoint
  - Implement POST /api/session/<session_id>/generate
  - Apply all manual boundary adjustments
  - Generate audio clips using adjusted boundaries
  - Create Anki package with adjusted clips
  - Return download URL for .apkg file
  - _Requirements: 7.2_

- [ ]* 18.2 Write property test for generation uses adjusted boundaries
  - **Property 16: Generation uses adjusted boundaries**
  - **Validates: Requirements 7.2**

- [x] 18.2 Add generation progress tracking
  - Display progress bar during generation
  - Show current stage (extracting audio, creating package, etc.)
  - Update progress in real-time
  - _Requirements: 7.3_

- [ ]* 18.3 Write property test for generation progress feedback
  - **Property 17: Generation progress feedback**
  - **Validates: Requirements 7.3**

- [x] 18.3 Implement download functionality
  - Provide download link when generation completes
  - Trigger browser download of .apkg file
  - Display file size and card count
  - _Requirements: 7.4_

- [ ]* 18.4 Write property test for generation completion access
  - **Property 18: Generation completion access**
  - **Validates: Requirements 7.4**

- [x] 18.4 Display generation summary
  - Show total number of terms
  - List which terms were manually adjusted
  - Display generation time and file size
  - _Requirements: 7.5_

- [ ]* 18.5 Write property test for generation summary accuracy
  - **Property 19: Generation summary accuracy**
  - **Validates: Requirements 7.5**

- [ ]* 18.6 Write integration tests for Anki generation
  - Test end-to-end generation with manual adjustments
  - Test progress tracking
  - Test download functionality
  - _Requirements: 7.2, 7.3, 7.4, 7.5_

- [x] 19. Add error handling and user feedback
- [x] 19.1 Implement frontend error handling
  - Display user-friendly error messages for API failures
  - Handle network errors gracefully
  - Provide retry options for failed operations
  - _Requirements: 1.5_

- [x] 19.2 Add backend error handling
  - Catch and handle processing errors
  - Return appropriate HTTP status codes
  - Provide detailed error messages
  - Log errors for debugging
  - _Requirements: 1.5_

- [ ]* 19.3 Write unit tests for error handling
  - Test various error scenarios
  - Test error message display
  - Test retry functionality
  - _Requirements: 1.5_

- [x] 20. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Commit and push feature branch to GitHub
  - Stage all changes with `git add .`
  - Commit changes with descriptive message: "Add manual audio alignment feature with interactive waveform editor"
  - Push branch to GitHub: `git push origin feature/manual-audio-alignment`
  - Verify push was successful
  - _Requirements: All_

- [ ]* 22. Performance optimization
- [ ]* 22.1 Optimize waveform rendering for large files
  - Implement waveform downsampling for display
  - Use Web Workers for audio processing
  - Cache rendered waveforms
  - _Requirements: 2.3_

- [ ]* 22.2 Optimize boundary adjustment responsiveness
  - Debounce boundary update API calls
  - Use optimistic UI updates
  - Batch multiple updates
  - _Requirements: 4.2_

- [ ]* 22.3 Write performance tests
  - Test with large audio files (30+ minutes)
  - Test with many terms (100+)
  - Measure waveform rendering time
  - Measure boundary adjustment responsiveness
  - _Requirements: 2.3, 4.2_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows a layered approach: backend infrastructure → session management → frontend UI → integration
