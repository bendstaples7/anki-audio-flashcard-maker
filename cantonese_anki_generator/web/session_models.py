"""
Data models for manual audio alignment sessions.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any
import json
import uuid
import numpy as np


def convert_numpy_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj


@dataclass
class TermAlignment:
    """Represents the alignment data for a single vocabulary term."""
    term_id: str
    english: str
    cantonese: str
    start_time: float  # seconds
    end_time: float  # seconds
    original_start: float  # for reset functionality
    original_end: float
    is_manually_adjusted: bool
    confidence_score: float  # 0.0 to 1.0
    audio_segment_url: str  # URL to audio file for this term

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return convert_numpy_types(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TermAlignment':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class BoundaryUpdate:
    """Represents a boundary adjustment made by the user."""
    term_id: str
    new_start_time: float
    new_end_time: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BoundaryUpdate':
        """Create instance from dictionary."""
        data = data.copy()
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class AlignmentSession:
    """Represents a complete alignment session with all terms and metadata."""
    session_id: str
    doc_url: str
    audio_file_path: str
    created_at: datetime
    terms: List[TermAlignment]
    audio_duration: float
    status: str  # "processing", "ready", "generating", "complete"
    last_modified: datetime = field(default_factory=datetime.now)
    updates: List[BoundaryUpdate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'session_id': self.session_id,
            'doc_url': self.doc_url,
            'audio_file_path': self.audio_file_path,
            'created_at': self.created_at.isoformat(),
            'terms': [term.to_dict() for term in self.terms],
            'audio_duration': self.audio_duration,
            'status': self.status,
            'last_modified': self.last_modified.isoformat(),
            'updates': [update.to_dict() for update in self.updates]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlignmentSession':
        """Create instance from dictionary."""
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        data['terms'] = [TermAlignment.from_dict(term) for term in data['terms']]
        data['updates'] = [BoundaryUpdate.from_dict(update) for update in data['updates']]
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'AlignmentSession':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


def generate_session_id() -> str:
    """
    Generate a unique session ID.
    
    Returns:
        A unique session identifier string
    """
    return str(uuid.uuid4())


def generate_term_id(index: int, english: str) -> str:
    """
    Generate a unique term ID based on index and English text.
    
    Args:
        index: The position of the term in the vocabulary list
        english: The English text of the term
        
    Returns:
        A unique term identifier string
    """
    # Create a simple but unique ID combining index and sanitized english text
    sanitized = ''.join(c if c.isalnum() else '_' for c in english.lower())[:20]
    return f"term_{index}_{sanitized}"
