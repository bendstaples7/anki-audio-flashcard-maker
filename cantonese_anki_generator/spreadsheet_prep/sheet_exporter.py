"""
Sheet exporter service for creating Google Sheets with vocabulary data.
"""

from typing import List, Optional
from cantonese_anki_generator.models import VocabularyEntry, SheetCreationResult
from cantonese_anki_generator.processors.google_docs_auth import (
    GoogleDocsAuthenticator,
    GoogleDocsAuthError
)


class SheetExporter:
    """Handles Google Sheets creation and formatting for vocabulary data."""
    
    def __init__(self, authenticator: Optional[GoogleDocsAuthenticator] = None):
        """
        Initialize the sheet exporter.
        
        Args:
            authenticator: Optional pre-configured authenticator
        """
        self.authenticator = authenticator or GoogleDocsAuthenticator()
        self._service = None
    
    def _get_service(self):
        """Get authenticated Google Sheets service."""
        if not self._service:
            if not self.authenticator.authenticate():
                raise GoogleDocsAuthError("Failed to authenticate with Google Sheets API")
            
            # Import here to avoid circular imports
            from googleapiclient.discovery import build
            self._service = build('sheets', 'v4', credentials=self.authenticator._credentials)
        return self._service
    
    def create_vocabulary_sheet(
        self, 
        entries: List[VocabularyEntry],
        title: str = "Cantonese Vocabulary"
    ) -> SheetCreationResult:
        """
        Create a new Google Sheet with vocabulary data.
        
        Args:
            entries: List of vocabulary entries
            title: Title for the new spreadsheet
            
        Returns:
            SheetCreationResult with URL and ID
        """
        try:
            service = self._get_service()
            
            # Create a new spreadsheet
            spreadsheet_body = {
                'properties': {
                    'title': title
                }
            }
            
            spreadsheet = service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            
            sheet_id = spreadsheet['spreadsheetId']
            sheet_url = spreadsheet['spreadsheetUrl']
            
            # Prepare data with header row
            values = [
                ['English', 'Cantonese', 'Jyutping']
            ]
            
            # Add vocabulary entries in correct column order
            for entry in entries:
                values.append([
                    entry.english,
                    entry.cantonese,
                    entry.jyutping
                ])
            
            # Write data to the sheet
            body = {
                'values': values
            }
            
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return SheetCreationResult(
                success=True,
                sheet_url=sheet_url,
                sheet_id=sheet_id
            )
            
        except GoogleDocsAuthError as e:
            return SheetCreationResult(
                success=False,
                error=f"Authentication error: {str(e)}"
            )
        except Exception as e:
            return SheetCreationResult(
                success=False,
                error=f"Failed to create sheet: {str(e)}"
            )
    
    def format_for_parser_compatibility(self, sheet_id: str) -> bool:
        """
        Ensure sheet format is compatible with google_sheets_parser.
        
        The parser expects:
        - Header row with "English", "Cantonese", "Jyutping" labels
        - Column order: English (A), Cantonese (B), Jyutping (C)
        - All text values (no formulas or special formatting)
        - No empty rows between header and data
        
        Args:
            sheet_id: Google Sheets document ID
            
        Returns:
            True if formatting successful, False otherwise
        """
        try:
            service = self._get_service()
            
            # Get all sheet data to validate format
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range='A1:C'
            ).execute()
            
            values = result.get('values', [])
            
            # Validate header row exists
            if not values or len(values[0]) < 3:
                return False
            
            header = values[0]
            expected_headers = ['English', 'Cantonese', 'Jyutping']
            
            # Check if headers match expected format
            if header[:3] != expected_headers:
                return False
            
            # Validate no empty rows between header and data
            # (sheets created by create_vocabulary_sheet won't have this issue,
            # but this validates the format for compatibility)
            if len(values) > 1:
                for i, row in enumerate(values[1:], start=1):
                    # Check if row has at least 2 columns with data (English and Cantonese required)
                    if len(row) >= 2:
                        # If we find a row with data, ensure no empty rows before it
                        if i > 1:
                            # Check all rows between header and this row
                            for j in range(1, i):
                                if not values[j] or len(values[j]) < 2:
                                    return False
                        break
            
            # Format is compatible
            return True
            
        except Exception:
            return False
