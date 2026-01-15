# Requirements Document

## Introduction

The Manual Audio Alignment feature enhances the Cantonese Anki Generator by providing an interactive review and adjustment interface for audio-term alignments. Users can visually inspect audio waveforms, play back individual term recordings, and manually adjust alignment boundaries when the automatic alignment produces errors. This addresses the common issue of misalignments where multiple terms' audio gets included in one clip or audio segments are incorrectly matched to terms.

## Glossary

- **Alignment_Table**: A visual table displaying vocabulary terms alongside their corresponding audio segments
- **Waveform_Display**: A graphical representation of the audio signal showing amplitude over time
- **Alignment_Boundary**: The start and end time markers that define which portion of audio corresponds to a term
- **Playback_Control**: Interactive controls allowing users to play audio segments for verification
- **Boundary_Adjuster**: Interactive UI element (slider or draggable marker) for modifying alignment boundaries
- **Term_Row**: A single row in the alignment table representing one vocabulary term and its audio
- **Audio_Segment**: A specific portion of the full audio file defined by start and end timestamps
- **Alignment_Review_UI**: The complete interface for reviewing and adjusting audio-term alignments
- **Confirmation_Action**: User action to accept all alignments and proceed with Anki package generation
- **Auto_Alignment**: The initial automatic alignment produced by the system's segmentation algorithms

## Requirements

### Requirement 1

**User Story:** As a language teacher, I want to upload my vocabulary sheet and audio file through the UI, so that I can begin the alignment review process without using command-line tools.

#### Acceptance Criteria

1. WHEN a user opens the application, THE Alignment_Review_UI SHALL display file selection controls for vocabulary documents and audio files
2. WHEN a user selects a Google Docs or Sheets URL, THE Alignment_Review_UI SHALL validate the URL format and accessibility
3. WHEN a user selects an audio file, THE Alignment_Review_UI SHALL validate the file format (MP3, WAV, M4A) and load it successfully
4. WHEN both inputs are provided and valid, THE Alignment_Review_UI SHALL enable a "Process" button to begin automatic alignment
5. THE Alignment_Review_UI SHALL display clear error messages if file validation fails

### Requirement 2

**User Story:** As a user, I want to see the automatic alignment results in a table with visual audio representations, so that I can quickly identify potential misalignments.

#### Acceptance Criteria

1. WHEN automatic alignment completes, THE Alignment_Review_UI SHALL display an Alignment_Table with all vocabulary terms
2. WHEN displaying each term, THE Alignment_Table SHALL show the English term, Cantonese text, and corresponding audio segment
3. WHEN displaying audio segments, THE Alignment_Review_UI SHALL render a Waveform_Display for each term's audio
4. THE Waveform_Display SHALL visually indicate the start and end boundaries of each Audio_Segment
5. WHEN the table is displayed, THE Alignment_Review_UI SHALL provide scrolling for tables with many terms

### Requirement 3

**User Story:** As a user, I want to play the audio for each term, so that I can verify whether the alignment is correct.

#### Acceptance Criteria

1. WHEN viewing a Term_Row, THE Alignment_Review_UI SHALL display a play button for that term's audio
2. WHEN the play button is clicked, THE Playback_Control SHALL play only the audio segment for that specific term
3. WHEN audio is playing, THE Playback_Control SHALL provide visual feedback indicating playback is active
4. WHEN audio playback completes, THE Playback_Control SHALL return to the ready state
5. WHEN a user clicks play on a different term while audio is playing, THE Playback_Control SHALL stop the current audio and play the new selection

### Requirement 4

**User Story:** As a user, I want to manually adjust the start and end points of audio segments, so that I can fix misalignments where the automatic system made errors.

#### Acceptance Criteria

1. WHEN viewing a Term_Row, THE Alignment_Review_UI SHALL display interactive Boundary_Adjuster controls for start and end times
2. WHEN a user drags a boundary marker, THE Waveform_Display SHALL update in real-time to show the new segment boundaries
3. WHEN a boundary is adjusted, THE Alignment_Review_UI SHALL prevent overlapping segments with adjacent terms
4. WHEN a boundary is adjusted, THE Playback_Control SHALL use the updated boundaries for audio playback
5. WHEN boundaries are modified, THE Alignment_Review_UI SHALL visually indicate which terms have been manually adjusted

### Requirement 5

**User Story:** As a user, I want to see the full audio waveform with all term boundaries marked, so that I can understand the overall alignment and identify problematic sections.

#### Acceptance Criteria

1. THE Alignment_Review_UI SHALL display a full-length Waveform_Display showing the entire audio file
2. WHEN displaying the full waveform, THE Alignment_Review_UI SHALL overlay all Alignment_Boundary markers for all terms
3. WHEN a user clicks on a boundary marker in the full waveform, THE Alignment_Review_UI SHALL scroll to and highlight the corresponding Term_Row
4. THE Waveform_Display SHALL use distinct colors or labels to identify different term boundaries
5. WHEN boundaries are adjusted in the table, THE Alignment_Review_UI SHALL update the full waveform display accordingly

### Requirement 6

**User Story:** As a user, I want to zoom in on specific sections of the audio waveform, so that I can precisely adjust boundaries for closely-spaced terms.

#### Acceptance Criteria

1. WHEN viewing the full waveform, THE Alignment_Review_UI SHALL provide zoom controls for magnifying specific time ranges
2. WHEN zoomed in, THE Waveform_Display SHALL show higher resolution audio detail for precise boundary adjustment
3. WHEN zoomed, THE Alignment_Review_UI SHALL provide pan controls to navigate along the audio timeline
4. WHEN adjusting boundaries while zoomed, THE Boundary_Adjuster SHALL provide fine-grained time precision
5. THE Alignment_Review_UI SHALL display the current zoom level and visible time range

### Requirement 7

**User Story:** As a user, I want to confirm my alignment adjustments and generate the Anki package, so that I can complete the deck creation process with corrected alignments.

#### Acceptance Criteria

1. WHEN all alignments are reviewed, THE Alignment_Review_UI SHALL display a "Generate Anki Deck" button
2. WHEN the generate button is clicked, THE Alignment_Review_UI SHALL use the current alignment boundaries (including manual adjustments) for audio clip generation
3. WHEN generation begins, THE Alignment_Review_UI SHALL display progress feedback during package creation
4. WHEN generation completes, THE Alignment_Review_UI SHALL provide a download link or save dialog for the .apkg file
5. THE Alignment_Review_UI SHALL display a summary showing the number of terms and which alignments were manually adjusted

### Requirement 8

**User Story:** As a user, I want to save my alignment adjustments, so that I can resume my work later without losing my manual corrections.

#### Acceptance Criteria

1. WHEN alignments are modified, THE Alignment_Review_UI SHALL provide a "Save Progress" option
2. WHEN progress is saved, THE Alignment_Review_UI SHALL store all current alignment boundaries and manual adjustment flags
3. WHEN a user reopens a saved session, THE Alignment_Review_UI SHALL restore all alignment boundaries and adjustment states
4. THE Alignment_Review_UI SHALL associate saved alignments with the specific vocabulary document and audio file combination
5. WHEN loading a saved session, THE Alignment_Review_UI SHALL validate that the original files are still accessible

### Requirement 9

**User Story:** As a user, I want to reset individual term alignments back to the automatic alignment, so that I can undo manual adjustments that made things worse.

#### Acceptance Criteria

1. WHEN viewing a manually adjusted Term_Row, THE Alignment_Review_UI SHALL display a "Reset" button for that term
2. WHEN the reset button is clicked, THE Alignment_Review_UI SHALL restore the original Auto_Alignment boundaries for that term
3. WHEN a term is reset, THE Alignment_Review_UI SHALL remove the manual adjustment indicator for that term
4. THE Alignment_Review_UI SHALL provide a "Reset All" option to restore all terms to automatic alignment
5. WHEN resetting alignments, THE Alignment_Review_UI SHALL request confirmation before applying the reset

### Requirement 10

**User Story:** As a user, I want visual indicators showing alignment quality, so that I can prioritize which terms need manual review.

#### Acceptance Criteria

1. WHEN displaying the Alignment_Table, THE Alignment_Review_UI SHALL show confidence scores or quality indicators for each alignment
2. WHEN an alignment has low confidence, THE Alignment_Review_UI SHALL visually highlight that Term_Row for attention
3. THE Alignment_Review_UI SHALL provide sorting or filtering options to show low-confidence alignments first
4. WHEN displaying quality indicators, THE Alignment_Review_UI SHALL use clear visual cues (colors, icons) to indicate alignment quality
5. THE Alignment_Review_UI SHALL explain what the quality indicators mean through tooltips or help text
