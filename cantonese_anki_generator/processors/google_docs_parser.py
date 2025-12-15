"""
Google Docs document parsing and table extraction module.

Handles document retrieval, table detection, and vocabulary extraction.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from googleapiclient.errors import HttpError

from .google_docs_auth import GoogleDocsAuthenticator, GoogleDocsAuthError
from ..models import VocabularyEntry


class GoogleDocsParser:
    """Handles parsing Google Docs documents and extracting vocabulary tables."""
    
    def __init__(self, authenticator: Optional[GoogleDocsAuthenticator] = None):
        """
        Initialize the parser.
        
        Args:
            authenticator: Optional pre-configured authenticator
        """
        self.authenticator = authenticator or GoogleDocsAuthenticator()
        self._service = None
    
    def _get_service(self):
        """Get authenticated Google Docs service."""
        if not self._service:
            if not self.authenticator.authenticate():
                raise GoogleDocsAuthError("Failed to authenticate with Google Docs API")
            self._service = self.authenticator.get_docs_service()
        return self._service
    
    def extract_document_id(self, doc_url: str) -> str:
        """
        Extract document ID from Google Docs URL.
        
        Args:
            doc_url: Google Docs URL
            
        Returns:
            Document ID string
            
        Raises:
            ValueError: If URL format is invalid
        """
        # Handle different Google Docs URL formats
        patterns = [
            r'/document/d/([a-zA-Z0-9-_]+)',  # Standard format
            r'id=([a-zA-Z0-9-_]+)',          # Alternative format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, doc_url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Invalid Google Docs URL format: {doc_url}")
    
    def retrieve_document(self, doc_url: str) -> Dict[str, Any]:
        """
        Retrieve document content from Google Docs API.
        
        Args:
            doc_url: Google Docs URL
            
        Returns:
            Document content as dictionary
            
        Raises:
            GoogleDocsAuthError: If authentication fails
            HttpError: If document access fails
        """
        try:
            doc_id = self.extract_document_id(doc_url)
            service = self._get_service()
            
            # Retrieve the document
            document = service.documents().get(documentId=doc_id).execute()
            return document
            
        except HttpError as e:
            if e.resp.status == 403:
                raise GoogleDocsAuthError(
                    "Access denied. Please ensure the document is shared with your Google account."
                )
            elif e.resp.status == 404:
                raise GoogleDocsAuthError("Document not found. Please check the URL.")
            else:
                raise GoogleDocsAuthError(f"Failed to retrieve document: {e}")
    
    def find_tables(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all tables in the document.
        
        Args:
            document: Document content from Google Docs API
            
        Returns:
            List of table elements
        """
        tables = []
        
        def extract_tables_from_content(content):
            """Recursively extract tables from document content."""
            for element in content:
                if 'table' in element:
                    tables.append(element['table'])
                elif 'paragraph' in element:
                    # Tables can be nested in other structures
                    paragraph = element['paragraph']
                    if 'elements' in paragraph:
                        for para_element in paragraph['elements']:
                            if 'table' in para_element:
                                tables.append(para_element['table'])
        
        # Extract tables from document body
        if 'body' in document and 'content' in document['body']:
            extract_tables_from_content(document['body']['content'])
        
        return tables
    
    def extract_text_from_element(self, element: Dict[str, Any]) -> str:
        """
        Extract plain text from a document element.
        
        Args:
            element: Document element
            
        Returns:
            Extracted text string
        """
        text = ""
        
        if 'textRun' in element:
            text += element['textRun'].get('content', '')
        elif 'paragraph' in element:
            paragraph = element['paragraph']
            if 'elements' in paragraph:
                for para_element in paragraph['elements']:
                    text += self.extract_text_from_element(para_element)
        
        return text.strip()
    
    def parse_table_structure(self, table: Dict[str, Any]) -> List[List[str]]:
        """
        Parse table structure and extract cell contents.
        
        Args:
            table: Table element from document
            
        Returns:
            2D list representing table rows and columns
        """
        rows = []
        
        if 'tableRows' not in table:
            return rows
        
        for table_row in table['tableRows']:
            row_cells = []
            
            if 'tableCells' in table_row:
                for cell in table_row['tableCells']:
                    cell_text = ""
                    
                    if 'content' in cell:
                        for content_element in cell['content']:
                            if 'paragraph' in content_element:
                                paragraph = content_element['paragraph']
                                if 'elements' in paragraph:
                                    for element in paragraph['elements']:
                                        cell_text += self.extract_text_from_element(element)
                    
                    row_cells.append(cell_text.strip())
            
            rows.append(row_cells)
        
        return rows
    
    def identify_vocabulary_table(self, tables: List[Dict[str, Any]]) -> Optional[List[List[str]]]:
        """
        Identify which table contains vocabulary data.
        
        Args:
            tables: List of table elements
            
        Returns:
            Parsed vocabulary table or None if not found
        """
        best_table = None
        best_score = 0
        
        for table in tables:
            parsed_table = self.parse_table_structure(table)
            
            # Skip empty tables
            if not parsed_table or len(parsed_table) < 1:
                continue
            
            # Normalize table structure - handle varying column counts
            normalized_table = self._normalize_table_structure(parsed_table)
            
            # Score this table based on vocabulary likelihood
            score = self._score_vocabulary_table(normalized_table)
            
            if score > best_score:
                best_score = score
                best_table = normalized_table
        
        # Return best table if it meets minimum threshold
        return best_table if best_score > 0.3 else None
    
    def _normalize_table_structure(self, table_data: List[List[str]]) -> List[List[str]]:
        """
        Normalize table structure to handle varying formats.
        
        Args:
            table_data: Raw table data
            
        Returns:
            Normalized table with consistent column structure
        """
        if not table_data:
            return []
        
        # Find the maximum number of columns
        max_cols = max(len(row) for row in table_data)
        
        # Ensure all rows have the same number of columns
        normalized_table = []
        for row in table_data:
            normalized_row = row + [''] * (max_cols - len(row))
            normalized_table.append(normalized_row)
        
        # Handle merged cells and empty columns by consolidating content
        return self._consolidate_table_content(normalized_table)
    
    def _consolidate_table_content(self, table_data: List[List[str]]) -> List[List[str]]:
        """
        Consolidate table content to handle merged cells and formatting variations.
        
        Args:
            table_data: Normalized table data
            
        Returns:
            Consolidated table with merged content
        """
        if not table_data:
            return []
        
        consolidated = []
        
        for row in table_data:
            # Merge adjacent cells that might be split due to formatting
            consolidated_row = []
            current_cell = ""
            
            for cell in row:
                cell_content = cell.strip()
                if cell_content:
                    if current_cell:
                        # Check if this looks like a continuation (no punctuation at end of previous)
                        if not current_cell.endswith(('.', '!', '?', ':', ';')):
                            current_cell += " " + cell_content
                        else:
                            consolidated_row.append(current_cell)
                            current_cell = cell_content
                    else:
                        current_cell = cell_content
                elif current_cell:
                    # Empty cell - finalize current content
                    consolidated_row.append(current_cell)
                    current_cell = ""
            
            # Add final cell if any content remains
            if current_cell:
                consolidated_row.append(current_cell)
            
            # Ensure we have at least 2 columns for vocabulary pairs
            while len(consolidated_row) < 2:
                consolidated_row.append("")
            
            consolidated.append(consolidated_row)
        
        return consolidated
    
    def _score_vocabulary_table(self, table_data: List[List[str]]) -> float:
        """
        Score a table based on likelihood of containing vocabulary data.
        
        Args:
            table_data: Normalized table data
            
        Returns:
            Score between 0 and 1 (higher = more likely vocabulary table)
        """
        if not table_data or len(table_data) < 2:
            return 0.0
        
        score = 0.0
        total_rows = len(table_data) - 1  # Exclude header
        
        # Check for header indicators
        header_row = table_data[0]
        if len(header_row) >= 2:
            header_text = " ".join(header_row[:2]).lower()
            if any(word in header_text for word in ['english', 'cantonese', 'chinese', 'vocabulary', 'word']):
                score += 0.3
        
        # Check content rows
        valid_pairs = 0
        for row in table_data[1:]:
            if len(row) >= 2:
                english_col = row[0].strip()
                cantonese_col = row[1].strip()
                
                if english_col and cantonese_col:
                    # Check if columns look like English and Cantonese
                    if self._looks_like_english(english_col) and self._looks_like_cantonese(cantonese_col):
                        valid_pairs += 1
                    elif english_col and cantonese_col:  # Any non-empty pair
                        valid_pairs += 0.5
        
        # Calculate content score
        if total_rows > 0:
            content_score = valid_pairs / total_rows
            score += content_score * 0.7
        
        return min(score, 1.0)
    
    def _looks_like_english(self, text: str) -> bool:
        """Check if text looks like English."""
        if not text:
            return False
        
        # Simple heuristic: mostly ASCII characters
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        return ascii_chars / len(text) > 0.8
    
    def _looks_like_cantonese(self, text: str) -> bool:
        """Check if text looks like Cantonese/Chinese."""
        if not text:
            return False
        
        # Simple heuristic: contains CJK characters
        cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return cjk_chars > 0
    
    def extract_vocabulary_pairs(self, table_data: List[List[str]]) -> List[VocabularyEntry]:
        """
        Extract vocabulary entries from table data with robust error recovery.
        
        Args:
            table_data: 2D list of table contents
            
        Returns:
            List of VocabularyEntry objects
        """
        vocabulary_entries = []
        
        # Determine column mapping (handle different layouts)
        english_col, cantonese_col = self._determine_column_mapping(table_data)
        
        # Skip header row (index 0) and process content rows
        for row_index, row in enumerate(table_data[1:], start=1):
            try:
                entry = self._extract_vocabulary_entry(row, row_index, english_col, cantonese_col)
                if entry:
                    vocabulary_entries.append(entry)
            except Exception as e:
                # Log error but continue processing other rows
                print(f"Warning: Failed to process row {row_index}: {e}")
                continue
        
        return vocabulary_entries
    
    def _determine_column_mapping(self, table_data: List[List[str]]) -> Tuple[int, int]:
        """
        Determine which columns contain English and Cantonese content.
        
        Args:
            table_data: Table data
            
        Returns:
            Tuple of (english_column_index, cantonese_column_index)
        """
        if not table_data or len(table_data[0]) < 2:
            return (0, 1)  # Default mapping
        
        # Check header row for clues
        header_row = table_data[0]
        english_col = 0
        cantonese_col = 1
        
        for i, header in enumerate(header_row[:4]):  # Check first 4 columns
            header_lower = header.lower().strip()
            if 'english' in header_lower:
                english_col = i
            elif any(word in header_lower for word in ['cantonese', 'chinese', '中文', '粵語']):
                cantonese_col = i
        
        # Validate mapping by checking content
        if len(table_data) > 1:
            sample_rows = table_data[1:min(6, len(table_data))]  # Check first 5 content rows
            
            # Count how many rows have English-like content in each column
            english_scores = [0] * min(4, len(table_data[0]))
            cantonese_scores = [0] * min(4, len(table_data[0]))
            
            for row in sample_rows:
                for i in range(min(len(row), 4)):
                    if self._looks_like_english(row[i]):
                        english_scores[i] += 1
                    if self._looks_like_cantonese(row[i]):
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
        
        return (english_col, cantonese_col)
    
    def _extract_vocabulary_entry(self, row: List[str], row_index: int, 
                                english_col: int, cantonese_col: int) -> Optional[VocabularyEntry]:
        """
        Extract a single vocabulary entry from a table row.
        
        Args:
            row: Table row data
            row_index: Row index for tracking
            english_col: Column index for English content
            cantonese_col: Column index for Cantonese content
            
        Returns:
            VocabularyEntry or None if row is invalid
        """
        # Ensure row has enough columns
        if len(row) <= max(english_col, cantonese_col):
            return None
        
        # Extract and clean content
        english = self._clean_text(row[english_col])
        cantonese = self._clean_text(row[cantonese_col])
        
        # Skip empty or invalid entries
        if not english or not cantonese:
            return None
        
        # Calculate confidence based on content quality
        confidence = self._calculate_entry_confidence(english, cantonese)
        
        return VocabularyEntry(
            english=english,
            cantonese=cantonese,
            row_index=row_index,
            confidence=confidence
        )
    
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
        
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common formatting artifacts
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\-\'\"]+', '', cleaned)
        
        return cleaned
    
    def _calculate_entry_confidence(self, english: str, cantonese: str) -> float:
        """
        Calculate confidence score for a vocabulary entry.
        
        Args:
            english: English text
            cantonese: Cantonese text
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 1.0
        
        # Reduce confidence for very short entries
        if len(english) < 2 or len(cantonese) < 1:
            confidence *= 0.5
        
        # Reduce confidence if content doesn't match expected language patterns
        if not self._looks_like_english(english):
            confidence *= 0.7
        
        if not self._looks_like_cantonese(cantonese):
            confidence *= 0.7
        
        # Reduce confidence for entries with unusual characters
        if re.search(r'[^\w\s\u4e00-\u9fff.,!?;:()\-\'\"]+', english + cantonese):
            confidence *= 0.8
        
        return max(confidence, 0.1)  # Minimum confidence threshold
    
    def extract_vocabulary_table(self, doc_url: str) -> List[VocabularyEntry]:
        """
        Main method to extract vocabulary table from Google Docs URL with robust error recovery.
        
        Args:
            doc_url: Google Docs URL
            
        Returns:
            List of VocabularyEntry objects
            
        Raises:
            GoogleDocsAuthError: If authentication or document access fails
            ValueError: If no vocabulary table is found
        """
        try:
            # Retrieve document
            document = self.retrieve_document(doc_url)
            
            # Find tables with fallback strategies
            tables = self.find_tables(document)
            if not tables:
                # Try alternative content extraction methods
                tables = self._find_tables_alternative(document)
            
            if not tables:
                raise ValueError(
                    "No tables found in the document. Please ensure the document contains "
                    "a table with vocabulary data."
                )
            
            # Identify vocabulary table with scoring
            vocabulary_table = self.identify_vocabulary_table(tables)
            if vocabulary_table is None:
                # Provide detailed feedback about what was found
                table_info = self._analyze_available_tables(tables)
                raise ValueError(
                    f"No vocabulary table found. Found {len(tables)} table(s) but none "
                    f"contained recognizable English-Cantonese vocabulary pairs. "
                    f"Table analysis: {table_info}"
                )
            
            # Extract vocabulary pairs with error recovery
            vocabulary_entries = self.extract_vocabulary_pairs(vocabulary_table)
            if not vocabulary_entries:
                raise ValueError(
                    "No valid vocabulary entries found in the table. Please check that "
                    "the table contains English and Cantonese text in separate columns."
                )
            
            # Filter out low-confidence entries but warn about them
            high_confidence_entries = [e for e in vocabulary_entries if e.confidence >= 0.5]
            low_confidence_count = len(vocabulary_entries) - len(high_confidence_entries)
            
            if low_confidence_count > 0:
                print(f"Warning: {low_confidence_count} entries had low confidence and were excluded")
            
            if not high_confidence_entries:
                raise ValueError(
                    "All extracted entries had low confidence. Please check the table format "
                    "and ensure it contains clear English-Cantonese vocabulary pairs."
                )
            
            return high_confidence_entries
            
        except GoogleDocsAuthError:
            # Re-raise authentication errors as-is
            raise
        except Exception as e:
            # Wrap other errors with more context
            raise GoogleDocsParsingError(f"Failed to extract vocabulary table: {str(e)}") from e
    
    def _find_tables_alternative(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Alternative method to find tables in case primary method fails.
        
        Args:
            document: Document content
            
        Returns:
            List of table elements found through alternative methods
        """
        tables = []
        
        # Try searching in different document structures
        def search_recursive(content, depth=0):
            if depth > 10:  # Prevent infinite recursion
                return
            
            if isinstance(content, dict):
                if 'table' in content:
                    tables.append(content['table'])
                for value in content.values():
                    if isinstance(value, (dict, list)):
                        search_recursive(value, depth + 1)
            elif isinstance(content, list):
                for item in content:
                    search_recursive(item, depth + 1)
        
        search_recursive(document)
        return tables
    
    def _analyze_available_tables(self, tables: List[Dict[str, Any]]) -> str:
        """
        Analyze available tables to provide helpful feedback.
        
        Args:
            tables: List of table elements
            
        Returns:
            Analysis summary string
        """
        if not tables:
            return "No tables found"
        
        analysis = []
        for i, table in enumerate(tables):
            parsed = self.parse_table_structure(table)
            if parsed:
                rows = len(parsed)
                cols = max(len(row) for row in parsed) if parsed else 0
                analysis.append(f"Table {i+1}: {rows} rows, {cols} columns")
            else:
                analysis.append(f"Table {i+1}: Could not parse structure")
        
        return "; ".join(analysis)


class GoogleDocsParsingError(Exception):
    """Custom exception for Google Docs parsing errors."""
    pass