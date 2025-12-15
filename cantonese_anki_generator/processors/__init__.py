"""
Processors module for handling Google Docs and document parsing.
"""

from .google_docs_auth import GoogleDocsAuthenticator, GoogleDocsAuthError, create_authenticated_service
from .google_docs_parser import GoogleDocsParser, GoogleDocsParsingError
from .google_sheets_parser import GoogleSheetsParser, GoogleSheetsParsingError

__all__ = [
    'GoogleDocsAuthenticator',
    'GoogleDocsAuthError', 
    'create_authenticated_service',
    'GoogleDocsParser',
    'GoogleDocsParsingError',
    'GoogleSheetsParser',
    'GoogleSheetsParsingError'
]