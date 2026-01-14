"""
Session management for manual audio alignment.
"""

import os
import json
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

from .session_models import (
    AlignmentSession,
    TermAlignment,
    BoundaryUpdate,
    generate_session_id
)


class SessionManager:
    """
    Manages alignment sessions including creation, retrieval, updates, and cleanup.
    """

    def __init__(self, storage_dir: str = "temp/sessions"):
        """
        Initialize the SessionManager.
        
        Args:
            storage_dir: Directory path for storing session data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for active sessions
        self._sessions: Dict[str, AlignmentSession] = {}

    def create_session(
        self,
        doc_url: str,
        audio_file_path: str,
        terms: List[TermAlignment],
        audio_duration: float
    ) -> str:
        """
        Create a new alignment session.
        
        Args:
            doc_url: URL to the Google Docs/Sheets document
            audio_file_path: Path to the uploaded audio file
            terms: List of term alignments from automatic alignment
            audio_duration: Total duration of the audio file in seconds
            
        Returns:
            The session ID of the newly created session
        """
        session_id = generate_session_id()
        
        session = AlignmentSession(
            session_id=session_id,
            doc_url=doc_url,
            audio_file_path=audio_file_path,
            created_at=datetime.now(),
            terms=terms,
            audio_duration=audio_duration,
            status="ready",
            last_modified=datetime.now(),
            updates=[]
        )
        
        # Store in memory cache
        self._sessions[session_id] = session
        
        # Persist to disk
        self._save_session(session)
        
        return session_id

    def get_session(self, session_id: str) -> Optional[AlignmentSession]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: The session identifier
            
        Returns:
            The AlignmentSession if found, None otherwise
        """
        # Check memory cache first
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Try to load from disk
        session = self._load_session(session_id)
        if session:
            self._sessions[session_id] = session
        
        return session

    def update_boundaries(
        self,
        session_id: str,
        term_id: str,
        new_start_time: float,
        new_end_time: float
    ) -> bool:
        """
        Update the boundaries for a specific term.
        
        Args:
            session_id: The session identifier
            term_id: The term identifier
            new_start_time: New start time in seconds
            new_end_time: New end time in seconds
            
        Returns:
            True if update was successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Find the term and update its boundaries
        term_found = False
        for term in session.terms:
            if term.term_id == term_id:
                term.start_time = new_start_time
                term.end_time = new_end_time
                term.is_manually_adjusted = True
                term_found = True
                break
        
        if not term_found:
            return False
        
        # Record the update
        update = BoundaryUpdate(
            term_id=term_id,
            new_start_time=new_start_time,
            new_end_time=new_end_time,
            timestamp=datetime.now()
        )
        session.updates.append(update)
        session.last_modified = datetime.now()
        
        # Persist changes
        self._save_session(session)
        
        return True

    def mark_manual_adjustment(self, session_id: str, term_id: str) -> bool:
        """
        Mark a term as manually adjusted.
        
        Args:
            session_id: The session identifier
            term_id: The term identifier
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        for term in session.terms:
            if term.term_id == term_id:
                term.is_manually_adjusted = True
                session.last_modified = datetime.now()
                self._save_session(session)
                return True
        
        return False

    def reset_term_boundaries(self, session_id: str, term_id: str) -> bool:
        """
        Reset a term's boundaries to the original automatic alignment.
        
        Args:
            session_id: The session identifier
            term_id: The term identifier
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        for term in session.terms:
            if term.term_id == term_id:
                term.start_time = term.original_start
                term.end_time = term.original_end
                term.is_manually_adjusted = False
                session.last_modified = datetime.now()
                self._save_session(session)
                return True
        
        return False

    def get_all_alignments(self, session_id: str) -> Optional[List[TermAlignment]]:
        """
        Get all term alignments for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            List of TermAlignment objects if session exists, None otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        return session.terms

    def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update the status of a session.
        
        Args:
            session_id: The session identifier
            status: New status ("processing", "ready", "generating", "complete")
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = status
        session.last_modified = datetime.now()
        self._save_session(session)
        
        return True

    def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up a session and its associated files.
        
        Args:
            session_id: The session identifier
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Remove from memory cache
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        # Remove session file from disk
        session_file = self._get_session_file_path(session_id)
        try:
            if session_file.exists():
                session_file.unlink()
            return True
        except Exception as e:
            print(f"Error cleaning up session {session_id}: {e}")
            return False

    def list_sessions(self) -> List[str]:
        """
        List all available session IDs.
        
        Returns:
            List of session IDs
        """
        session_files = self.storage_dir.glob("session_*.json")
        return [f.stem.replace("session_", "") for f in session_files]

    def _get_session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.storage_dir / f"session_{session_id}.json"

    def _save_session(self, session: AlignmentSession) -> None:
        """
        Save a session to disk.
        
        Args:
            session: The AlignmentSession to save
        """
        session_file = self._get_session_file_path(session.session_id)
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                f.write(session.to_json())
        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")
            raise

    def _load_session(self, session_id: str) -> Optional[AlignmentSession]:
        """
        Load a session from disk.
        
        Args:
            session_id: The session identifier
            
        Returns:
            The AlignmentSession if found, None otherwise
        """
        session_file = self._get_session_file_path(session_id)
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                json_str = f.read()
                return AlignmentSession.from_json(json_str)
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None
