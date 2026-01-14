"""
Pytest configuration and fixtures for validation tests.

Provides common fixtures and configuration for testing the validation system
with both unit tests and property-based tests using Hypothesis.
"""

import pytest
from hypothesis import settings, Verbosity
from datetime import datetime
from typing import List

from cantonese_anki_generator.models import VocabularyEntry, AudioSegment
from cantonese_anki_generator.validation.config import ValidationConfig, ValidationStrictness
from cantonese_anki_generator.validation.models import (
    ValidationResult, ValidationIssue, ValidationCheckpoint,
    IssueType, IssueSeverity
)
import numpy as np


# Configure Hypothesis for property-based testing
settings.register_profile("validation", 
    max_examples=100,  # Run 100 iterations as specified in design
    verbosity=Verbosity.normal,
    deadline=None  # No deadline for validation tests
)
settings.load_profile("validation")


@pytest.fixture
def validation_config():
    """Provide a standard validation configuration for testing."""
    return ValidationConfig(
        strictness=ValidationStrictness.NORMAL,
        enabled=True,
        halt_on_critical=True
    )


@pytest.fixture
def strict_validation_config():
    """Provide a strict validation configuration for testing."""
    return ValidationConfig(
        strictness=ValidationStrictness.STRICT,
        enabled=True,
        halt_on_critical=True
    )


@pytest.fixture
def lenient_validation_config():
    """Provide a lenient validation configuration for testing."""
    return ValidationConfig(
        strictness=ValidationStrictness.LENIENT,
        enabled=True,
        halt_on_critical=False
    )


@pytest.fixture
def sample_vocabulary_entries():
    """Provide sample vocabulary entries for testing."""
    return [
        VocabularyEntry(english="hello", cantonese="你好", row_index=0, confidence=1.0),
        VocabularyEntry(english="goodbye", cantonese="再見", row_index=1, confidence=0.9),
        VocabularyEntry(english="thank you", cantonese="多謝", row_index=2, confidence=0.95),
        VocabularyEntry(english="water", cantonese="水", row_index=3, confidence=1.0),
        VocabularyEntry(english="food", cantonese="食物", row_index=4, confidence=0.8)
    ]


@pytest.fixture
def sample_audio_segments():
    """Provide sample audio segments for testing."""
    # Create sample audio data (1 second at 22050 Hz sample rate)
    sample_rate = 22050
    duration = 1.0
    audio_length = int(sample_rate * duration)
    
    segments = []
    for i in range(5):
        # Generate simple sine wave audio data
        t = np.linspace(0, duration, audio_length)
        frequency = 440 + (i * 100)  # Different frequency for each segment
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
        
        segment = AudioSegment(
            start_time=i * duration,
            end_time=(i + 1) * duration,
            audio_data=audio_data,
            confidence=0.9,
            segment_id=f"segment_{i}",
            audio_file_path=f"test_audio_{i}.wav"
        )
        segments.append(segment)
    
    return segments


@pytest.fixture
def sample_validation_issues():
    """Provide sample validation issues for testing."""
    return [
        ValidationIssue(
            issue_type=IssueType.COUNT_MISMATCH,
            severity=IssueSeverity.ERROR,
            affected_items=["vocabulary_count", "audio_count"],
            description="Vocabulary count (5) does not match audio segment count (4)",
            suggested_fix="Check if audio contains all vocabulary words",
            confidence=0.95
        ),
        ValidationIssue(
            issue_type=IssueType.SILENT_AUDIO,
            severity=IssueSeverity.WARNING,
            affected_items=["segment_2"],
            description="Audio segment appears to be silent or very quiet",
            suggested_fix="Check audio recording quality and volume levels",
            confidence=0.8
        ),
        ValidationIssue(
            issue_type=IssueType.ALIGNMENT_CONFIDENCE,
            severity=IssueSeverity.WARNING,
            affected_items=["hello_segment_0"],
            description="Low alignment confidence (0.45) for term-audio pair",
            suggested_fix="Review alignment or consider re-recording",
            confidence=0.7
        )
    ]


@pytest.fixture
def sample_validation_result(sample_validation_issues):
    """Provide a sample validation result for testing."""
    return ValidationResult(
        checkpoint=ValidationCheckpoint.ALIGNMENT_PROCESS,
        success=False,
        confidence_score=0.75,
        issues=sample_validation_issues,
        recommendations=[
            "Review audio quality and recording conditions",
            "Check vocabulary document for completeness",
            "Consider adjusting alignment parameters"
        ],
        validation_methods_used=["confidence_scoring", "cross_verification"],
        timestamp=datetime.now()
    )


@pytest.fixture
def silent_audio_segment():
    """Provide a silent audio segment for testing."""
    # Create silent audio data
    sample_rate = 22050
    duration = 1.0
    audio_length = int(sample_rate * duration)
    silent_audio = np.zeros(audio_length)
    
    return AudioSegment(
        start_time=0.0,
        end_time=duration,
        audio_data=silent_audio,
        confidence=0.1,
        segment_id="silent_segment",
        audio_file_path="silent_test.wav"
    )


@pytest.fixture
def noisy_audio_segment():
    """Provide a noisy audio segment for testing."""
    # Create noisy audio data
    sample_rate = 22050
    duration = 1.0
    audio_length = int(sample_rate * duration)
    
    # Generate white noise
    noise = np.random.normal(0, 0.1, audio_length)
    
    return AudioSegment(
        start_time=0.0,
        end_time=duration,
        audio_data=noise,
        confidence=0.3,
        segment_id="noisy_segment",
        audio_file_path="noisy_test.wav"
    )


@pytest.fixture
def duplicate_vocabulary_entries():
    """Provide vocabulary entries with duplicates for testing."""
    return [
        VocabularyEntry(english="hello", cantonese="你好", row_index=0, confidence=1.0),
        VocabularyEntry(english="hello", cantonese="你好", row_index=1, confidence=1.0),  # Duplicate
        VocabularyEntry(english="goodbye", cantonese="再見", row_index=2, confidence=0.9),
        VocabularyEntry(english="", cantonese="", row_index=3, confidence=0.0),  # Empty
        VocabularyEntry(english="water", cantonese="水", row_index=4, confidence=1.0)
    ]


# Hypothesis strategies for property-based testing
from hypothesis import strategies as st

# Strategy for generating vocabulary entries
vocabulary_entry_strategy = st.builds(
    VocabularyEntry,
    english=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))),
    cantonese=st.text(min_size=1, max_size=50),
    row_index=st.integers(min_value=0, max_value=1000),
    confidence=st.floats(min_value=0.0, max_value=1.0)
)

# Strategy for generating audio segments
audio_segment_strategy = st.builds(
    AudioSegment,
    start_time=st.floats(min_value=0.0, max_value=100.0),
    end_time=st.floats(min_value=0.1, max_value=101.0),
    audio_data=st.just(np.random.random(1000)),  # Simple random audio data
    confidence=st.floats(min_value=0.0, max_value=1.0),
    segment_id=st.text(min_size=1, max_size=20),
    audio_file_path=st.text(min_size=1, max_size=50)
)

# Strategy for generating lists of vocabulary entries
vocabulary_list_strategy = st.lists(vocabulary_entry_strategy, min_size=1, max_size=20)

# Strategy for generating lists of audio segments  
audio_list_strategy = st.lists(audio_segment_strategy, min_size=1, max_size=20)