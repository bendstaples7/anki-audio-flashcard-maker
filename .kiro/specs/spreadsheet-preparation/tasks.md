# Implementation Plan: Spreadsheet Preparation Tool

## Overview

This implementation plan breaks down the Spreadsheet Preparation Tool into discrete coding tasks. The feature adds a new mode to the existing web UI that allows users to create vocabulary spreadsheets by inputting English terms, automatically generating Cantonese translations and Jyutping romanization, reviewing/editing the results, and exporting to Google Sheets.

The implementation follows a bottom-up approach: core services first, then API endpoints, then frontend components, and finally integration.

## Tasks

- [x] 1. Set up data models and service interfaces
  - Create extended VocabularyEntry model with jyutping field
  - Define TranslationResult, RomanizationResult, SheetCreationResult models
  - Create base service interfaces for translation and romanization
  - _Requirements: 3.2, 4.1, 6.2_

- [x] 2. Implement translation service
  - [x] 2.1 Create TranslationService class with API client integration
    - Implement translate() method for single term translation
    - Implement translate_batch() method for efficient batch processing
    - Add error handling for API failures and timeouts
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x]* 2.2 Write property test for translation service
    - **Property 2: Translation Service Handles All Terms**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    - Test that all terms receive results (success or error)
    - Test that failures don't stop processing of remaining terms

- [x] 3. Implement romanization service
  - [x] 3.1 Create RomanizationService class using phonemizer library
    - Implement romanize() method for single text conversion
    - Implement romanize_batch() method for batch processing
    - Configure phonemizer for Cantonese (yue) with tone preservation
    - Add error handling for unsupported characters
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ]* 3.2 Write property test for romanization service
    - **Property 3: Romanization Preserves Tone Numbers**
    - **Validates: Requirements 4.5**
    - Test that Jyutping output contains tone numbers (1-6)
  
  - [ ]* 3.3 Write property test for romanization error handling
    - **Property 4: Romanization Service Handles All Texts**
    - **Validates: Requirements 4.1, 4.3, 4.4**
    - Test that all texts receive results (success or error)

- [x] 4. Implement sheet exporter service
  - [x] 4.1 Create SheetExporter class with Google Sheets API integration
    - Reuse existing GoogleDocsAuthenticator from google_docs_auth module
    - Implement create_vocabulary_sheet() method
    - Add header row with "English", "Cantonese", "Jyutping" labels
    - Write vocabulary entries to sheet in correct column order
    - _Requirements: 6.1, 6.2, 6.5, 10.1_
  
  - [x] 4.2 Implement format_for_parser_compatibility() method
    - Ensure sheet format matches google_sheets_parser expectations
    - Validate column order and header row format
    - _Requirements: 6.3, 10.2_
  
  - [ ]* 4.3 Write property test for sheet export round-trip
    - **Property 8: Sheet Export Round-Trip Compatibility**
    - **Validates: Requirements 6.2, 6.3, 10.2**
    - Test that exporting then parsing produces equivalent entries

- [x] 5. Implement input parsing utility
  - [x] 5.1 Create parse_input() function
    - Split input by newlines
    - Filter out empty lines
    - Trim whitespace from each term
    - _Requirements: 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 5.2 Write property test for input parsing
    - **Property 1: Input Parsing Preserves Non-Empty Lines**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5**
    - Test that non-empty lines are preserved with whitespace trimmed

- [x] 6. Implement validation logic
  - [x] 6.1 Create validate_entries() function
    - Check that all entries have non-empty English terms
    - Check that all entries have non-empty Cantonese text
    - Return validation errors with entry indices
    - _Requirements: 7.1, 7.2, 7.3, 7.5_
  
  - [ ]* 6.2 Write property test for validation
    - **Property 6: Validation Rejects Empty Required Fields**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.5**
    - Test that entries with empty required fields fail validation

- [x] 7. Implement API endpoints
  - [x] 7.1 Create /api/spreadsheet-prep/translate endpoint
    - Accept list of English terms in request body
    - Call TranslationService.translate_batch()
    - Call RomanizationService.romanize_batch() for successful translations
    - Return results with success/error indicators
    - Include summary with total/successful/failed counts
    - Add progress tracking support
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.3, 4.4, 8.2_
  
  - [x] 7.2 Create /api/spreadsheet-prep/export endpoint
    - Accept list of vocabulary entries in request body
    - Validate entries using validate_entries()
    - Call SheetExporter.create_vocabulary_sheet()
    - Return sheet URL and ID on success
    - Return validation errors if validation fails
    - _Requirements: 6.1, 6.2, 6.4, 6.6, 7.1, 7.2, 7.3_
  
  - [ ]* 7.3 Write unit tests for API endpoints
    - Test translate endpoint with valid input
    - Test translate endpoint with API failures
    - Test export endpoint with valid entries
    - Test export endpoint with validation failures
    - Test export endpoint with auth failures

- [x] 8. Implement error handling
  - [x] 8.1 Add spreadsheet preparation error classes to errors.py
    - Create SpreadsheetPrepError base class
    - Create TranslationServiceError class
    - Create RomanizationServiceError class
    - Create SheetExportError class
    - Follow existing error handling patterns
    - _Requirements: 9.1, 9.2, 9.3, 10.3_
  
  - [x] 8.2 Add error messages and suggested actions
    - Define error messages for translation API unavailable
    - Define error messages for auth failures
    - Define error messages for validation failures
    - Define error messages for network issues
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [ ]* 8.3 Write property test for error logging
    - **Property 9: Error Logging Captures All Failures**
    - **Validates: Requirements 9.4**
    - Test that all errors are logged with details

- [x] 9. Checkpoint - Ensure backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement frontend mode selector
  - [x] 10.1 Add mode selection UI to index.html
    - Create two buttons: "Prepare Spreadsheet" and "Link Spreadsheet + Upload Audio"
    - Add styling consistent with existing UI
    - _Requirements: 1.1_
  
  - [x] 10.2 Add navigation logic in app.js
    - Handle "Prepare Spreadsheet" button click
    - Handle "Link Spreadsheet + Upload Audio" button click
    - Show/hide appropriate interfaces based on mode
    - _Requirements: 1.2, 1.3_
  
  - [ ]* 10.3 Write unit tests for mode selection
    - Test that mode selection UI is displayed
    - Test navigation to prepare mode
    - Test navigation to upload mode

- [x] 11. Implement input interface component
  - [x] 11.1 Create input interface HTML in index.html
    - Add text area for English term input
    - Add "Generate" button
    - Add placeholder text with instructions
    - _Requirements: 2.1_
  
  - [x] 11.2 Add input interface logic in app.js
    - Handle text input changes
    - Parse input on Generate button click
    - Call /api/spreadsheet-prep/translate endpoint
    - Handle API responses and errors
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 3.1_

- [x] 12. Implement progress indicator component
  - [x] 12.1 Create progress indicator HTML
    - Add progress bar element
    - Add status text elements for total/completed/failed counts
    - _Requirements: 8.1, 8.4, 8.5_
  
  - [x] 12.2 Add progress tracking logic in app.js
    - Show progress indicator when translation starts
    - Update progress as translations complete
    - Hide progress indicator when complete
    - Display final summary
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [ ]* 12.3 Write property test for progress tracking
    - **Property 7: Progress Tracking Reflects Completion State**
    - **Validates: Requirements 8.2**
    - Test that progress accurately reflects completed/failed counts

- [x] 13. Implement review table component
  - [x] 13.1 Create review table HTML structure
    - Add table with three columns: English, Cantonese, Jyutping
    - Make Cantonese and Jyutping cells editable
    - Add error indicator styling
    - Add "Generate Google Sheet" button
    - _Requirements: 5.1, 5.5_
  
  - [x] 13.2 Add table rendering logic in app.js
    - Render vocabulary entries in table
    - Display error indicators for failed translations
    - Populate cells with translation results
    - _Requirements: 3.5, 5.1, 5.5_
  
  - [x] 13.3 Add cell editing logic in app.js
    - Handle cell edit events
    - Update vocabulary entry data immediately
    - Revalidate entry after edit
    - _Requirements: 5.2, 5.3, 5.4, 5.6_
  
  - [ ]* 13.4 Write property test for cell edits
    - **Property 5: Cell Edits Update Underlying Data**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.6**
    - Test that edits immediately update application state
  
  - [x] 13.5 Add validation and export logic
    - Validate entries when "Generate Google Sheet" is clicked
    - Highlight entries with validation errors
    - Call /api/spreadsheet-prep/export endpoint if valid
    - Display sheet URL on success
    - _Requirements: 7.3, 7.4, 7.5, 6.4, 6.6_

- [x] 14. Implement error handling in frontend
  - [x] 14.1 Add error display components
    - Create error message display area
    - Add styling for error messages
    - Add suggested actions display
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 14.2 Add error handling logic in app.js
    - Handle translation API errors
    - Handle authentication errors
    - Handle validation errors
    - Handle network errors
    - Preserve user data on recoverable errors
    - _Requirements: 9.1, 9.2, 9.3, 9.5_
  
  - [ ]* 14.3 Write property test for data persistence
    - **Property 10: Data Persistence After Recoverable Errors**
    - **Validates: Requirements 9.5**
    - Test that user data remains after recoverable errors

- [x] 15. Add configuration and integration
  - [x] 15.1 Add configuration to config.py
    - Add translation API configuration settings
    - Add romanization service settings
    - Follow existing configuration patterns
    - _Requirements: 10.4_
  
  - [x] 15.2 Register API blueprint in app.py
    - Import spreadsheet preparation API blueprint
    - Register blueprint with Flask app
    - _Requirements: 10.5_
  
  - [x] 15.3 Add CSS styling
    - Style mode selection interface
    - Style input interface
    - Style progress indicator
    - Style review table
    - Match existing UI design patterns
    - _Requirements: 10.5_

- [x] 16. Checkpoint - Ensure integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. End-to-end integration testing
  - [ ]* 17.1 Write integration test for complete workflow
    - Test mode selection → input → translation → review → export
    - Test with valid input
    - Test with translation failures
    - Test with validation errors
    - Test with authentication flow
    - _Requirements: All requirements_

- [x] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- Frontend uses JavaScript, backend uses Python
- Reuses existing authentication, error handling, and configuration infrastructure
