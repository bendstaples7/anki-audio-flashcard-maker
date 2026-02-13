# Design Document: Spreadsheet Preparation Tool

## Overview

The Spreadsheet Preparation Tool is a web-based feature that enables users to create properly formatted Google Sheets for the Cantonese Anki Generator without requiring pre-existing spreadsheets. The tool provides an interactive workflow where users input English terms, the system automatically generates Cantonese translations and Jyutping romanization, and users can review and edit the results before exporting to Google Sheets.

This feature integrates seamlessly with the existing web UI and leverages the current Google Sheets API authentication infrastructure. It serves as an alternative entry point to the main audio alignment pipeline, reducing friction for users who need to create vocabulary lists from scratch.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Mode         │  │ Input        │  │ Review       │      │
│  │ Selection    │→ │ Interface    │→ │ Table        │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (Flask)                       │
│  ┌────────────────────────────────┐  ┌──────────────┐      │
│  │ /api/spreadsheet-prep/         │  │ /api/        │      │
│  │ translate                       │  │ spreadsheet- │      │
│  │ (includes romanization)         │  │ prep/export  │      │
│  └────────────────────────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Translation  │  │ Romanization │  │ Sheet        │      │
│  │ Service      │  │ Service      │  │ Exporter     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Translation  │  │ pycantonese  │  │ Google       │      │
│  │ API          │  │ Library      │  │ Sheets API   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **Mode Selection**: User chooses "Prepare Spreadsheet" mode
2. **Input Collection**: User enters English terms (one per line)
3. **Translation**: System calls translation service for each term
4. **Romanization**: System generates Jyutping for each Cantonese translation
5. **Review**: User reviews and edits results in interactive table
6. **Validation**: System validates all entries before export
7. **Export**: System creates Google Sheet with formatted data
8. **Handoff**: User receives sheet URL to use with main pipeline

## Components and Interfaces

### 1. Frontend Components

#### ModeSelector Component
```javascript
class ModeSelector {
  // Displays mode selection buttons
  // Handles navigation to appropriate interface
  
  render() {
    // Returns HTML for mode selection UI
  }
  
  onModeSelect(mode: 'prepare' | 'upload') {
    // Navigate to selected mode interface
  }
}
```

#### InputInterface Component
```javascript
class InputInterface {
  // Text area for English term input
  // Generate button to trigger translation
  
  state: {
    inputText: string
    isProcessing: boolean
  }
  
  parseInput(): string[] {
    // Split by newlines, filter empty, trim whitespace
  }
  
  onGenerate() {
    // Call API to translate terms
  }
}
```

#### ReviewTable Component
```javascript
class ReviewTable {
  // Editable table with English, Cantonese, Jyutping columns
  // Error indicators for failed translations
  // Export button
  
  state: {
    entries: VocabularyEntry[]
    validationErrors: Map<number, string>
  }
  
  onCellEdit(rowIndex: number, field: string, value: string) {
    // Update entry and revalidate
  }
  
  onExport() {
    // Validate and call export API
  }
}
```

#### ProgressIndicator Component
```javascript
class ProgressIndicator {
  // Progress bar and status text
  // Shows completion percentage
  
  state: {
    total: number
    completed: number
    failed: number
  }
  
  updateProgress(completed: number, failed: number) {
    // Update UI with current progress
  }
}
```

### 2. Backend API Endpoints

#### POST /api/spreadsheet-prep/translate
```python
@bp.route('/spreadsheet-prep/translate', methods=['POST'])
def translate_terms():
    """
    Translate English terms to Cantonese and generate Jyutping.
    
    Request Body:
        {
            "terms": ["hello", "goodbye", ...]
        }
    
    Response:
        {
            "success": true,
            "results": [
                {
                    "english": "hello",
                    "cantonese": "你好",
                    "jyutping": "nei5 hou2",
                    "success": true
                },
                {
                    "english": "goodbye",
                    "cantonese": "",
                    "jyutping": "",
                    "success": false,
                    "error": "Translation service unavailable"
                }
            ],
            "summary": {
                "total": 2,
                "successful": 1,
                "failed": 1
            }
        }
    """
    pass
```

#### POST /api/spreadsheet-prep/export
```python
@bp.route('/spreadsheet-prep/export', methods=['POST'])
def export_to_sheets():
    """
    Export vocabulary entries to Google Sheets.
    
    Request Body:
        {
            "entries": [
                {
                    "english": "hello",
                    "cantonese": "你好",
                    "jyutping": "nei5 hou2"
                }
            ]
        }
    
    Response:
        {
            "success": true,
            "sheet_url": "https://docs.google.com/spreadsheets/d/...",
            "sheet_id": "abc123..."
        }
    """
    pass
```

### 3. Service Layer

#### TranslationService
```python
class TranslationService:
    """Handles English to Cantonese translation."""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def translate(self, english_term: str) -> TranslationResult:
        """
        Translate English term to Cantonese.
        
        Args:
            english_term: English word or phrase
            
        Returns:
            TranslationResult with cantonese text or error
        """
        pass
    
    def translate_batch(self, terms: List[str]) -> List[TranslationResult]:
        """
        Translate multiple terms efficiently.
        
        Args:
            terms: List of English terms
            
        Returns:
            List of TranslationResult objects
        """
        pass
```

#### RomanizationService
```python
class RomanizationService:
    """Handles Cantonese to Jyutping romanization."""
    
    def __init__(self):
        # Initialize pycantonese library
        pass
    
    def romanize(self, cantonese_text: str) -> RomanizationResult:
        """
        Convert Cantonese text to Jyutping romanization.
        
        Args:
            cantonese_text: Chinese characters (Cantonese)
            
        Returns:
            RomanizationResult with jyutping or error
        """
        pass
    
    def romanize_batch(self, texts: List[str]) -> List[RomanizationResult]:
        """
        Romanize multiple texts efficiently.
        
        Args:
            texts: List of Cantonese texts
            
        Returns:
            List of RomanizationResult objects
        """
        pass
```

#### SheetExporter
```python
class SheetExporter:
    """Handles Google Sheets creation and formatting."""
    
    def __init__(self, authenticator: GoogleDocsAuthenticator):
        self.authenticator = authenticator
    
    def create_vocabulary_sheet(
        self, 
        entries: List[VocabularyEntry]
    ) -> SheetCreationResult:
        """
        Create a new Google Sheet with vocabulary data.
        
        Args:
            entries: List of vocabulary entries
            
        Returns:
            SheetCreationResult with URL and ID
        """
        pass
    
    def format_for_parser_compatibility(
        self, 
        sheet_id: str
    ) -> bool:
        """
        Ensure sheet format is compatible with google_sheets_parser.
        
        Args:
            sheet_id: Google Sheets document ID
            
        Returns:
            True if formatting successful
        """
        pass
```

## Data Models

### VocabularyEntry (Extended)
```python
@dataclass
class VocabularyEntry:
    """Vocabulary entry for spreadsheet preparation."""
    english: str
    cantonese: str
    jyutping: str = ""
    row_index: int = 0
    confidence: float = 1.0
    translation_error: Optional[str] = None
    romanization_error: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if entry has all required fields."""
        return bool(self.english and self.cantonese)
    
    def has_errors(self) -> bool:
        """Check if entry has any errors."""
        return bool(self.translation_error or self.romanization_error)
```

### TranslationResult
```python
@dataclass
class TranslationResult:
    """Result of translation operation."""
    english: str
    cantonese: str
    success: bool
    error: Optional[str] = None
    confidence: float = 1.0
```

### RomanizationResult
```python
@dataclass
class RomanizationResult:
    """Result of romanization operation."""
    cantonese: str
    jyutping: str
    success: bool
    error: Optional[str] = None
```

### SheetCreationResult
```python
@dataclass
class SheetCreationResult:
    """Result of Google Sheet creation."""
    success: bool
    sheet_url: Optional[str] = None
    sheet_id: Optional[str] = None
    error: Optional[str] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Input Parsing Preserves Non-Empty Lines
*For any* multi-line input text, parsing should produce a list where each element corresponds to a non-empty line from the input, with leading and trailing whitespace removed.

**Validates: Requirements 2.2, 2.3, 2.4, 2.5**

### Property 2: Translation Service Handles All Terms
*For any* list of English terms, the translation service should return a result for each term, either with a successful translation or an error indicator, and continue processing all terms even if some fail.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

### Property 3: Romanization Preserves Tone Numbers
*For any* Cantonese text that successfully romanizes to Jyutping, the output should contain tone numbers (digits 1-6) for each syllable.

**Validates: Requirements 4.5**

### Property 4: Romanization Service Handles All Texts
*For any* list of Cantonese texts, the romanization service should return a result for each text, either with successful Jyutping or an error indicator.

**Validates: Requirements 4.1, 4.3, 4.4**

### Property 5: Cell Edits Update Underlying Data
*For any* vocabulary entry in the review table, editing a field (Cantonese or Jyutping) should immediately update the corresponding entry in the application state.

**Validates: Requirements 5.2, 5.3, 5.4, 5.6**

### Property 6: Validation Rejects Empty Required Fields
*For any* set of vocabulary entries, validation should fail if any entry has an empty English term or empty Cantonese text, and should prevent export.

**Validates: Requirements 7.1, 7.2, 7.3, 7.5**

### Property 7: Progress Tracking Reflects Completion State
*For any* batch translation operation, the progress indicator should accurately reflect the number of completed and failed translations at each update.

**Validates: Requirements 8.2**

### Property 8: Sheet Export Round-Trip Compatibility
*For any* set of valid vocabulary entries, exporting to Google Sheets then parsing with google_sheets_parser should produce equivalent vocabulary entries with the same English, Cantonese, and Jyutping values.

**Validates: Requirements 6.2, 6.3, 10.2**

### Property 9: Error Logging Captures All Failures
*For any* error that occurs during translation, romanization, or export, the system should log the error details including error type, message, and context.

**Validates: Requirements 9.4**

### Property 10: Data Persistence After Recoverable Errors
*For any* recoverable error (translation API timeout, network interruption), user-entered data in the review table should remain unchanged after the error is handled.

**Validates: Requirements 9.5**

## Error Handling

### Error Categories

Following the existing error handling patterns in `errors.py`:

1. **INPUT_VALIDATION**: Invalid English term format, empty input
2. **TRANSLATION_SERVICE**: API unavailable, rate limiting, invalid response
3. **ROMANIZATION_SERVICE**: pycantonese library failure, unsupported characters
4. **AUTHENTICATION**: Google Sheets API auth failure
5. **SHEET_EXPORT**: Sheet creation failure, formatting failure
6. **NETWORK**: Connection timeout, service unreachable

### Error Handling Strategy

```python
class SpreadsheetPrepError(CantoneseAnkiError):
    """Base exception for spreadsheet preparation errors."""
    pass

class TranslationServiceError(SpreadsheetPrepError):
    """Raised when translation service fails."""
    pass

class RomanizationServiceError(SpreadsheetPrepError):
    """Raised when romanization service fails."""
    pass

class SheetExportError(SpreadsheetPrepError):
    """Raised when sheet export fails."""
    pass
```

### Graceful Degradation

- **Translation Failures**: Mark individual entries with errors, allow manual entry
- **Romanization Failures**: Leave Jyutping empty, allow manual entry
- **Partial Success**: Display summary of successful/failed translations
- **Network Issues**: Preserve user data, allow retry
- **Auth Failures**: Redirect to authentication flow

### User-Facing Error Messages

```python
ERROR_MESSAGES = {
    'translation_api_unavailable': {
        'message': 'Translation service is currently unavailable',
        'actions': [
            'Check your internet connection',
            'Try again in a few moments',
            'Manually enter translations for failed terms'
        ]
    },
    'auth_required': {
        'message': 'Google Sheets authentication required',
        'actions': [
            'Click the authentication link',
            'Sign in with your Google account',
            'Grant the requested permissions'
        ]
    },
    'validation_failed': {
        'message': 'Some entries have missing required fields',
        'actions': [
            'Review highlighted entries',
            'Fill in missing English or Cantonese text',
            'Try exporting again'
        ]
    }
}
```

## Testing Strategy

### Unit Testing

Unit tests focus on specific components and edge cases:

- **Input Parsing**: Empty input, whitespace handling, special characters
- **Translation Service**: API response parsing, error handling, timeout handling
- **Romanization Service**: Tone preservation, unsupported characters, empty input
- **Validation Logic**: Empty fields, partial data, all valid
- **Sheet Formatting**: Header row, column order, data types

### Property-Based Testing

Property tests verify universal behaviors across many generated inputs:

- **Minimum 100 iterations per property test**
- Each test references its design document property
- Tag format: `Feature: spreadsheet-preparation, Property {number}: {property_text}`

**Property Test Examples**:

```python
@given(st.text(min_size=1))
def test_input_parsing_preserves_non_empty_lines(input_text):
    """
    Feature: spreadsheet-preparation, Property 1: Input Parsing Preserves Non-Empty Lines
    """
    lines = input_text.split('\n')
    parsed = parse_input(input_text)
    
    # All non-empty lines should be preserved
    expected = [line.strip() for line in lines if line.strip()]
    assert parsed == expected

@given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=20))
def test_translation_service_handles_all_terms(terms):
    """
    Feature: spreadsheet-preparation, Property 2: Translation Service Handles All Terms
    """
    service = TranslationService(mock_api_client)
    results = service.translate_batch(terms)
    
    # Should have result for each term
    assert len(results) == len(terms)
    
    # Each result should have english field matching input
    for term, result in zip(terms, results):
        assert result.english == term
        # Should have either success or error
        assert result.success or result.error is not None
```

### Integration Testing

Integration tests verify component interactions:

- **End-to-End Flow**: Input → Translation → Romanization → Review → Export
- **API Integration**: Flask endpoints with mock services
- **Google Sheets Integration**: Sheet creation and parsing round-trip
- **Authentication Flow**: OAuth integration with existing auth module
- **Error Recovery**: Partial failures, retry logic, data preservation

### Manual Testing Checklist

- [ ] Mode selection navigation works correctly
- [ ] Input interface accepts and parses terms
- [ ] Translation generates Cantonese text
- [ ] Romanization generates Jyutping with tones
- [ ] Review table displays all entries
- [ ] Cell editing updates data immediately
- [ ] Error indicators show for failed translations
- [ ] Validation prevents export with empty fields
- [ ] Progress indicator updates during processing
- [ ] Google Sheet is created with correct format
- [ ] Exported sheet is compatible with parser
- [ ] Error messages are clear and actionable

## Implementation Notes

### Translation API Selection

The implementation uses **Google Cloud Translation API** (google-cloud-translate library):

1. **Credentials**: Requires `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to service account key file
2. **Target Language**: Configurable choice between Cantonese and Traditional Chinese
   - **Current Implementation**: Uses `'yue'` (Cantonese) for direct Cantonese translation
   - **Alternative Option**: Can use `'zh-TW'` (Traditional Chinese - Taiwan) for Mandarin in Traditional characters
   - **API Support**: As of November 2024, Google Cloud Translation API supports both Cantonese ('yue') and Traditional Chinese ('zh-TW') as part of its 189-language expansion
   - **Code Decision**: The choice between 'yue' and 'zh-TW' is a design decision, not an API limitation
3. **Client**: Uses `translate_v2.Client()` for translation operations
   - **For Cantonese Output**: Use language code `'yue'` when Cantonese is desired
   - **Model Verification**: Verify NMT (Neural Machine Translation) model availability for 'yue' in your region
   - **Fallback Strategy**: If 'yue' model is unavailable or produces unexpected results, consider:
     - Using 'zh-TW' with manual review/editing for Cantonese-specific vocabulary
     - Falling back to mock translations for development/testing
     - Implementing manual translation workflow with review interface
4. **Error Handling**: Gracefully handles API failures with clear error messages
5. **Review Interface**: Users can review and edit translations for accuracy via the interactive table, regardless of which language code is used

**Setup Instructions**:
```bash
# Install the library
pip install google-cloud-translate

# Set credentials environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

**Translation Workflow (Current Implementation with 'yue')**:
1. System translates English to Cantonese using 'yue' language code
2. User reviews translations in interactive table
3. User can manually edit translations if needed for accuracy or regional variations
4. System generates Jyutping romanization from Cantonese text

**Alternative Workflow (Using 'zh-TW')**:
1. System translates English to Traditional Chinese (Mandarin) using 'zh-TW' language code
2. User reviews and edits translations to convert Mandarin to Cantonese vocabulary
3. User manually corrects for Cantonese-specific terms and expressions
4. System generates Jyutping romanization from edited Cantonese text

### Romanization Implementation

Use the `pycantonese` library for accurate Cantonese Jyutping with tone numbers:

```python
import pycantonese

# Convert Cantonese text to Jyutping
jyutping_data = pycantonese.characters_to_jyutping(cantonese_text)

# Extract jyutping romanizations
jyutping_list = [jyutping for char, jyutping in jyutping_data if jyutping]
jyutping = ' '.join(jyutping_list)
```

**Why pycantonese instead of phonemizer:**
- `phonemizer` with eSpeak backend outputs IPA (International Phonetic Alphabet), not Jyutping
- `pycantonese` is specifically designed for Cantonese and outputs authentic Jyutping with tone numbers (1-6)
- Example: 你好 → "nei5 hou2" (Jyutping) vs "nei˨˩hou˨˩" (IPA from eSpeak)

### Google Sheets Format

The exported sheet must match the format expected by `google_sheets_parser.py`:

- **Header Row**: "English", "Cantonese", "Jyutping"
- **Column Order**: English (A), Cantonese (B), Jyutping (C)
- **Data Types**: All text/string values
- **No Empty Rows**: Between header and data

### State Management

Use React state or similar for frontend:

```javascript
const [entries, setEntries] = useState([]);
const [isProcessing, setIsProcessing] = useState(false);
const [progress, setProgress] = useState({ total: 0, completed: 0, failed: 0 });
```

### Performance Considerations

- **Batch Processing**: Translate multiple terms in single API call
- **Debouncing**: Debounce cell edits to avoid excessive re-renders
- **Lazy Loading**: Load large tables progressively
- **Caching**: Cache translation results to avoid duplicate API calls

### Security Considerations

- **Input Sanitization**: Sanitize English terms before API calls
- **Rate Limiting**: Implement rate limiting for translation API
- **Authentication**: Reuse existing Google OAuth flow
- **Data Privacy**: Don't log sensitive vocabulary data
