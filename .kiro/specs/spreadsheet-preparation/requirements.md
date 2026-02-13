# Requirements Document

## Introduction

The Spreadsheet Preparation Tool is a feature that enables users to create properly formatted Google Sheets for the Cantonese Anki Generator without requiring pre-existing spreadsheets. Users input English terms, and the system automatically generates corresponding Cantonese characters and Jyutping romanization, provides an interactive interface for review and editing, and exports the finalized data to Google Sheets.

## Glossary

- **System**: The Spreadsheet Preparation Tool
- **User**: A person preparing vocabulary data for Cantonese language learning
- **English_Term**: An English word or phrase to be translated
- **Cantonese_Text**: Chinese characters representing the Cantonese translation
- **Jyutping**: The romanization system for Cantonese pronunciation
- **Translation_API**: An external service that provides English to Cantonese translations
- **Vocabulary_Entry**: A complete row containing English term, Cantonese text, and Jyutping
- **Review_Table**: The interactive UI component displaying generated vocabulary entries
- **Google_Sheet**: A spreadsheet document created via Google Sheets API
- **Main_Pipeline**: The existing Cantonese Anki Generator audio processing workflow

## Requirements

### Requirement 1: Mode Selection

**User Story:** As a user, I want to select a spreadsheet preparation mode, so that I can create vocabulary data without having a pre-existing spreadsheet.

#### Acceptance Criteria

1. WHEN the application starts, THE System SHALL display a mode selection interface with "Prepare Spreadsheet" and "Link Spreadsheet + Upload Audio" options
2. WHEN a user selects "Prepare Spreadsheet" mode, THE System SHALL navigate to the spreadsheet preparation interface
3. WHEN a user selects "Link Spreadsheet + Upload Audio" mode, THE System SHALL navigate to the existing main pipeline interface

### Requirement 2: English Term Input

**User Story:** As a user, I want to input a list of English terms, so that I can generate Cantonese translations for multiple vocabulary items at once.

#### Acceptance Criteria

1. THE System SHALL provide a text input area for entering English terms
2. WHEN a user enters text, THE System SHALL accept multiple English terms separated by newlines
3. WHEN a user submits the input, THE System SHALL parse each line as a separate English term
4. WHEN a user submits empty lines, THE System SHALL ignore them and process only non-empty lines
5. THE System SHALL trim whitespace from the beginning and end of each English term

### Requirement 3: Automatic Translation Generation

**User Story:** As a user, I want the system to automatically generate Cantonese translations, so that I don't have to manually look up each term.

#### Operational Constraints

1. **Batch Processing**: THE System SHALL support batch translation via `translate_batch()` method with a maximum of 50 terms per batch
2. **Single-Term Fallback**: THE System SHALL support single-term translation via `translate()` method for individual requests
3. **Rate Limiting**: THE System SHALL process terms sequentially to avoid overwhelming the Translation_API (no concurrent requests)
4. **Timeout Handling**: THE System SHALL enforce a 30-second timeout per translation request (single or batch)
5. **Retry Strategy**: THE System SHALL NOT automatically retry failed translations; failures SHALL be marked as errors and displayed to the user
6. **Error Isolation**: THE System SHALL continue processing remaining terms when individual translations fail (failure of one term does not stop the batch)
7. **API Selection**: THE System SHALL use Google Cloud Translation API (google-cloud-translate library) for English to Cantonese ('yue') translation, with GOOGLE_APPLICATION_CREDENTIALS environment variable for authentication

#### Acceptance Criteria

1. WHEN a user clicks the "Generate" button, THE System SHALL send English terms to the Translation_API using `translate_batch()` with up to 50 terms per batch
2. FOR each English_Term, THE System SHALL retrieve the corresponding Cantonese_Text from the Translation_API
3. WHEN the Translation_API returns a translation, THE System SHALL store it with the corresponding English_Term and map it correctly in the Review_Table
4. IF the Translation_API fails for a specific term (timeout, network error, or API error), THEN THE System SHALL mark that entry with an error indicator and continue processing remaining terms
5. WHEN all translations are complete or failed, THE System SHALL display the results in the Review_Table with proper English_Term to Cantonese_Text mapping
6. THE System SHALL enforce the 30-second timeout constraint per translation request
7. THE System SHALL process terms in the order they were entered by the user

### Requirement 4: Automatic Jyutping Generation

**User Story:** As a user, I want the system to automatically generate Jyutping romanization, so that I can include pronunciation information in my flashcards.

#### Acceptance Criteria

1. WHEN Cantonese_Text is generated for an English_Term, THE System SHALL generate the corresponding Jyutping romanization
2. THE System SHALL use a phonemizer or romanization service to convert Cantonese_Text to Jyutping
3. WHEN Jyutping generation succeeds, THE System SHALL store it with the corresponding Vocabulary_Entry
4. IF Jyutping generation fails for a specific entry, THEN THE System SHALL mark that entry with an error indicator and leave the Jyutping field empty
5. THE System SHALL preserve tone numbers in the Jyutping output

### Requirement 5: Interactive Review Interface

**User Story:** As a user, I want to review and edit generated translations, so that I can correct any errors or adjust translations to match my specific needs.

#### Acceptance Criteria

1. WHEN generation completes, THE System SHALL display all Vocabulary_Entry items in a Review_Table with three columns: English, Cantonese, and Jyutping
2. THE Review_Table SHALL allow users to edit the Cantonese_Text field for any entry
3. THE Review_Table SHALL allow users to edit the Jyutping field for any entry
4. WHEN a user edits a field, THE System SHALL update the corresponding Vocabulary_Entry immediately
5. THE Review_Table SHALL display error indicators for entries where translation or Jyutping generation failed
6. THE System SHALL allow users to manually fill in Cantonese_Text and Jyutping for entries marked with errors

### Requirement 6: Google Sheets Export

**User Story:** As a user, I want to export my reviewed vocabulary to Google Sheets, so that I can use it with the main Anki generator pipeline.

#### Acceptance Criteria

1. WHEN a user clicks "Generate Google Sheet", THE System SHALL create a new Google_Sheet via the Google Sheets API
2. THE System SHALL write all Vocabulary_Entry items to the Google_Sheet with columns: English, Cantonese, Jyutping
3. THE System SHALL format the Google_Sheet to be compatible with the existing google_sheets_parser module
4. WHEN the Google_Sheet is created successfully, THE System SHALL display the Google_Sheet URL to the user
5. THE System SHALL include a header row in the Google_Sheet with column labels: "English", "Cantonese", "Jyutping"
6. IF Google_Sheet creation fails, THEN THE System SHALL display an error message with suggested actions

### Requirement 7: Data Validation

**User Story:** As a user, I want the system to validate my data before export, so that I can ensure compatibility with the main pipeline.

#### Acceptance Criteria

1. WHEN a user clicks "Generate Google Sheet", THE System SHALL validate that all Vocabulary_Entry items have non-empty English_Term values
2. WHEN a user clicks "Generate Google Sheet", THE System SHALL validate that all Vocabulary_Entry items have non-empty Cantonese_Text values
3. IF any Vocabulary_Entry has empty required fields, THEN THE System SHALL display a validation error and prevent export
4. THE System SHALL highlight entries with validation errors in the Review_Table
5. THE System SHALL allow export when all Vocabulary_Entry items pass validation

### Requirement 8: Progress Feedback

**User Story:** As a user, I want to see progress during translation generation, so that I know the system is working and can estimate completion time.

#### Acceptance Criteria

1. WHEN translation generation starts, THE System SHALL display a progress indicator
2. WHILE translations are being generated, THE System SHALL update the progress indicator to show the percentage of completed translations
3. WHEN translation generation completes, THE System SHALL hide the progress indicator and display the Review_Table
4. THE System SHALL display the total number of terms being processed
5. THE System SHALL display the number of successfully processed terms and the number of failed terms

### Requirement 9: Error Handling

**User Story:** As a system administrator, I want comprehensive error handling, so that users receive helpful guidance when issues occur.

#### Acceptance Criteria

1. IF the Translation_API is unavailable, THEN THE System SHALL display an error message indicating the service is unreachable
2. IF the Google Sheets API authentication fails, THEN THE System SHALL display an error message with instructions to re-authenticate
3. IF network connectivity is lost during processing, THEN THE System SHALL display an error message and allow the user to retry
4. WHEN any error occurs, THE System SHALL log the error details for debugging purposes
5. THE System SHALL preserve user-entered data when recoverable errors occur

### Requirement 10: Integration with Existing Pipeline

**User Story:** As a developer, I want the spreadsheet preparation feature to integrate seamlessly with the existing codebase, so that maintenance is simplified and consistency is maintained.

#### Acceptance Criteria

1. THE System SHALL reuse the existing Google Sheets API authentication module from google_docs_auth
2. THE System SHALL generate Google_Sheet formats that are compatible with the existing google_sheets_parser module
3. THE System SHALL follow the existing error handling patterns defined in errors.py
4. THE System SHALL use the existing configuration management system from config.py
5. THE System SHALL integrate with the existing web UI framework and styling
