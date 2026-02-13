"""
Google Sheets parser for vocabulary extraction.

Handles Google Sheets API access and vocabulary table extraction.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from googleapiclient.errors import HttpError

from .google_docs_auth import GoogleDocsAuthenticator, GoogleDocsAuthError
from ..models import VocabularyEntry


class GoogleSheetsParser:
    """Handles parsing Google Sheets and extracting vocabulary tables."""
    
    def __init__(self, authenticator: Optional[GoogleDocsAuthenticator] = None):
        """
        Initialize the parser.
        
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
            
            self._service = self.authenticator.get_sheets_service()
        return self._service
    
    def extract_spreadsheet_id(self, sheets_url: str) -> str:
        """
        Extract spreadsheet ID from Google Sheets URL.
        
        Args:
            sheets_url: Google Sheets URL
            
        Returns:
            Spreadsheet ID string
            
        Raises:
            ValueError: If URL format is invalid
        """
        # Handle different Google Sheets URL formats
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',  # Standard format
            r'id=([a-zA-Z0-9-_]+)',               # Alternative format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sheets_url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Invalid Google Sheets URL format: {sheets_url}")
    
    def get_sheet_names(self, sheets_url: str) -> List[str]:
        """
        Get all sheet names in the spreadsheet.
        
        Args:
            sheets_url: Google Sheets URL
            
        Returns:
            List of sheet names
        """
        try:
            spreadsheet_id = self.extract_spreadsheet_id(sheets_url)
            service = self._get_service()
            
            # Get spreadsheet metadata
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            sheet_names = []
            for sheet in spreadsheet['sheets']:
                sheet_names.append(sheet['properties']['title'])
            
            return sheet_names
            
        except HttpError as e:
            if e.resp.status == 403:
                raise GoogleDocsAuthError(
                    "Access denied. Please ensure the spreadsheet is shared with your Google account."
                )
            elif e.resp.status == 404:
                raise GoogleDocsAuthError("Spreadsheet not found. Please check the URL.")
            else:
                raise GoogleDocsAuthError(f"Failed to retrieve spreadsheet: {e}")
    
    def get_sheet_data(self, sheets_url: str, sheet_name: Optional[str] = None, 
                      range_name: Optional[str] = None) -> List[List[str]]:
        """
        Get data from a specific sheet.
        
        Args:
            sheets_url: Google Sheets URL
            sheet_name: Name of the sheet (uses first sheet if None)
            range_name: Specific range like "A1:B10" (uses all data if None)
            
        Returns:
            2D list of cell values
        """
        try:
            spreadsheet_id = self.extract_spreadsheet_id(sheets_url)
            service = self._get_service()
            
            # Determine the range to read
            if range_name:
                # Use specific range
                if sheet_name:
                    full_range = f"'{sheet_name}'!{range_name}"
                else:
                    full_range = range_name
            else:
                # Use entire sheet or first sheet
                if sheet_name:
                    full_range = f"'{sheet_name}'"
                else:
                    # Get first sheet name
                    sheet_names = self.get_sheet_names(sheets_url)
                    if not sheet_names:
                        raise ValueError("No sheets found in spreadsheet")
                    full_range = f"'{sheet_names[0]}'"
            
            # Get the data
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=full_range,
                valueRenderOption='UNFORMATTED_VALUE',
                dateTimeRenderOption='FORMATTED_STRING'
            ).execute()
            
            values = result.get('values', [])
            
            # Normalize rows to have same length
            if values:
                max_cols = max(len(row) for row in values)
                normalized_values = []
                for row in values:
                    # Pad short rows with empty strings
                    normalized_row = row + [''] * (max_cols - len(row))
                    # Convert all values to strings
                    normalized_row = [str(cell) if cell is not None else '' for cell in normalized_row]
                    normalized_values.append(normalized_row)
                return normalized_values
            
            return []
            
        except HttpError as e:
            if e.resp.status == 403:
                raise GoogleDocsAuthError(
                    "Access denied. Please ensure the spreadsheet is shared with your Google account."
                )
            elif e.resp.status == 404:
                raise GoogleDocsAuthError("Spreadsheet not found. Please check the URL.")
            else:
                raise GoogleDocsAuthError(f"Failed to retrieve sheet data: {e}")
    
    def identify_vocabulary_columns(self, sheet_data: List[List[str]]) -> Tuple[int, int]:
        """
        Identify which columns contain English and Cantonese content.
        
        Args:
            sheet_data: 2D list of sheet data
            
        Returns:
            Tuple of (english_column_index, cantonese_column_index)
        """
        if not sheet_data or len(sheet_data[0]) < 2:
            return (0, 1)  # Default mapping
        
        # Check header row for clues
        header_row = sheet_data[0]
        english_col = 0
        cantonese_col = 1
        
        for i, header in enumerate(header_row[:4]):  # Check first 4 columns
            header_lower = str(header).lower().strip()
            if 'english' in header_lower:
                english_col = i
            elif any(word in header_lower for word in ['cantonese', 'chinese', '中文', '粵語']):
                cantonese_col = i
        
        # Validate mapping by checking content
        if len(sheet_data) > 1:
            sample_rows = sheet_data[1:min(6, len(sheet_data))]  # Check first 5 content rows
            
            # Count how many rows have English-like content in each column
            english_scores = [0] * min(4, len(sheet_data[0]))
            cantonese_scores = [0] * min(4, len(sheet_data[0]))
            
            for row in sample_rows:
                for i in range(min(len(row), 4)):
                    if self._looks_like_english(str(row[i])):
                        english_scores[i] += 1
                    if self._looks_like_cantonese(str(row[i])):
                        cantonese_scores[i] += 1
            
            # Find best columns based on content analysis
            if english_scores:
                best_english = english_scores.index(max(english_scores))
                if english_scores[best_english] > 0:
                    english_col = best_english
            
            if cantonese_scores:
                best_cantonese = cantonese_scores.index(max(cantonese_scores))
                if cantonese_scores[best_cantonese] > 0:
                    cantonese_col = best_cantonese
            
            # Ensure columns are different
            if english_col == cantonese_col:
                # If both detected as same column, use heuristics
                if len(sheet_data[0]) >= 2:
                    # Check first few entries to determine which is which
                    sample_text_0 = ' '.join(str(row[0]) for row in sample_rows if len(row) > 0)
                    sample_text_1 = ' '.join(str(row[1]) for row in sample_rows if len(row) > 1)
                    
                    # Look for romanized Cantonese patterns (letters followed by numbers)
                    has_romanized_0 = bool(re.search(r'[a-zA-Z]+\d+', sample_text_0))
                    has_romanized_1 = bool(re.search(r'[a-zA-Z]+\d+', sample_text_1))
                    
                    if has_romanized_0 and not has_romanized_1:
                        cantonese_col = 0
                        english_col = 1
                    elif has_romanized_1 and not has_romanized_0:
                        cantonese_col = 1
                        english_col = 0
                    else:
                        # Default: assume first column is Cantonese, second is English
                        cantonese_col = 0
                        english_col = 1
        
        return (english_col, cantonese_col)
    
    def _looks_like_english(self, text: str) -> bool:
        """Check if text looks like English."""
        if not text:
            return False
        
        # Check for romanized Cantonese patterns (numbers after letters)
        if re.search(r'[a-zA-Z]+\d+', text):
            return False  # Likely romanized Cantonese
        
        # Check for common English words
        english_words = {'the', 'a', 'an', 'to', 'of', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for', 'with', 'from'}
        words = text.lower().split()
        if any(word in english_words for word in words):
            return True
        
        # Simple heuristic: mostly ASCII characters and looks like English
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        if ascii_chars / len(text) > 0.8:
            # Additional check: avoid romanized Cantonese patterns
            if not re.search(r'\d', text) and len(text.split()) > 0:
                return True
        
        return False
    
    def _looks_like_cantonese(self, text: str) -> bool:
        """Check if text looks like Cantonese/Chinese."""
        if not text:
            return False
        
        # Simple heuristic: contains CJK characters
        cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return cjk_chars > 0
    
    def _detect_header_row(self, sheet_data: List[List[str]], english_col: int, cantonese_col: int) -> bool:
        """
        Detect if the first row is a header row or contains vocabulary data.
        
        Args:
            sheet_data: 2D list of sheet data
            english_col: Index of English column
            cantonese_col: Index of Cantonese column
            
        Returns:
            True if first row appears to be a header, False if it contains vocabulary
        """
        if len(sheet_data) < 1:
            return False  # No data
        
        first_row = sheet_data[0]
        
        # Check if first row has enough columns
        if len(first_row) <= max(english_col, cantonese_col):
            return False
        
        # Get the content from the first row
        first_english = str(first_row[english_col]).strip().lower()
        first_cantonese = str(first_row[cantonese_col]).strip().lower()
        
        # Common header indicators - be very specific
        header_keywords = [
            'english', 'cantonese', 'chinese', 'word', 'phrase', 'translation',
            'term', 'vocabulary', 'meaning', '中文', '粵語', '英文', 'column'
        ]
        
        # Check if first row contains obvious header-like text
        is_obvious_header = (
            any(keyword in first_english for keyword in header_keywords) or
            any(keyword in first_cantonese for keyword in header_keywords) or
            first_english in ['a', 'b', 'column a', 'column b', '1', '2'] or
            first_cantonese in ['a', 'b', 'column a', 'column b', '1', '2']
        )
        
        if is_obvious_header:
            return True
        
        # Check if first row looks like vocabulary data
        first_has_vocab = (
            self._looks_like_english(first_row[english_col]) and 
            self._looks_like_cantonese(first_row[cantonese_col])
        )
        
        # If first row clearly looks like vocabulary, it's not a header
        if first_has_vocab:
            return False
        
        # If we have multiple rows, compare patterns
        if len(sheet_data) > 1:
            second_row = sheet_data[1]
            if len(second_row) > max(english_col, cantonese_col):
                second_has_vocab = (
                    self._looks_like_english(second_row[english_col]) and 
                    self._looks_like_cantonese(second_row[cantonese_col])
                )
                
                # If second row looks like vocabulary but first doesn't, first might be header
                if second_has_vocab and not first_has_vocab:
                    return True
                
                # If both look like vocabulary, first is probably not a header
                if first_has_vocab and second_has_vocab:
                    return False
        
        # Conservative default: if we can't tell, assume it's vocabulary data
        return False
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Convert to string and remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', str(text).strip())
        
        # Remove common formatting artifacts
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\-\'\"]+', '', cleaned)
        
        return cleaned
    
    def extract_vocabulary_pairs(self, sheet_data: List[List[str]], 
                               skip_header: bool = None) -> List[VocabularyEntry]:
        """
        Extract vocabulary entries from sheet data.
        
        Args:
            sheet_data: 2D list of sheet data
            skip_header: Whether to skip the first row as header (auto-detect if None)
            
        Returns:
            List of VocabularyEntry objects
        """
        if not sheet_data:
            return []
        
        vocabulary_entries = []
        
        # Determine column mapping
        english_col, cantonese_col = self.identify_vocabulary_columns(sheet_data)
        
        # Auto-detect if first row is header if not specified
        if skip_header is None:
            skip_header = self._detect_header_row(sheet_data, english_col, cantonese_col)
        
        # Process rows (skip header if requested)
        start_row = 1 if skip_header else 0
        
        for row_index, row in enumerate(sheet_data[start_row:], start=start_row):
            try:
                # Ensure row has enough columns
                if len(row) <= max(english_col, cantonese_col):
                    continue
                
                # Extract and clean content
                english = self._clean_text(row[english_col])
                cantonese = self._clean_text(row[cantonese_col])
                
                # Skip empty entries
                if not english or not cantonese:
                    continue
                
                # Calculate confidence
                confidence = 1.0
                if not self._looks_like_english(english):
                    confidence *= 0.7
                if not self._looks_like_cantonese(cantonese):
                    confidence *= 0.7
                
                # Create vocabulary entry
                entry = VocabularyEntry(
                    english=english,
                    cantonese=cantonese,
                    row_index=row_index + 1,  # 1-based for user display
                    confidence=confidence
                )
                vocabulary_entries.append(entry)
                
            except Exception as e:
                # Log error but continue processing
                print(f"Warning: Failed to process row {row_index + 1}: {e}")
                continue
        
        return vocabulary_entries
    
    def extract_vocabulary_from_sheet(self, sheets_url: str, sheet_name: Optional[str] = None,
                                    range_name: Optional[str] = None) -> List[VocabularyEntry]:
        """
        Main method to extract vocabulary from Google Sheets.
        
        Args:
            sheets_url: Google Sheets URL
            sheet_name: Optional sheet name (uses first sheet if None)
            range_name: Optional range like "A1:B10" (uses all data if None)
            
        Returns:
            List of VocabularyEntry objects
        """
        # Get sheet data
        sheet_data = self.get_sheet_data(sheets_url, sheet_name, range_name)
        
        if not sheet_data:
            raise ValueError("No data found in the sheet")
        
        # Extract vocabulary pairs
        vocabulary_entries = self.extract_vocabulary_pairs(sheet_data)
        
        if not vocabulary_entries:
            raise ValueError("No vocabulary entries found in the sheet")
        
        return vocabulary_entries


class GoogleSheetsParsingError(Exception):
    """Custom exception for Google Sheets parsing errors."""
    pass