"""
Tests for core data models.
"""

import pytest
import numpy as np
from cantonese_anki_generator.models import (
    VocabularyEntry,
    AudioSegment,
    AlignedPair,
    AnkiCard
)


class TestVocabularyEntry:
    """Test cases for VocabularyEntry data model."""
    
    def test_vocabulary_entry_creation(self):
        """Test basic VocabularyEntry creation."""
        entry = VocabularyEntry(
            english="hello",
            cantonese="你好",
            row_index=1
        )
        assert entry.english == "hello"
        assert entry.cantonese == "你好"
        assert entry.row_index == 1
        assert entry.confidence == 1.0
    
    def test_vocabulary_entry_with_confidence(self):
        """Test VocabularyEntry with custom confidence."""
        entry = VocabularyEntry(
            english="goodbye",
            cantonese="再見",
            row_index=2,
            confidence=0.8
        )
        assert entry.confidence == 0.8


class TestAudioSegment:
    """Test cases for AudioSegment data model."""
    
    def test_audio_segment_creation(self):
        """Test basic AudioSegment creation."""
        audio_data = np.array([0.1, 0.2, 0.3])
        segment = AudioSegment(
            start_time=0.0,
            end_time=1.0,
            audio_data=audio_data,
            confidence=0.9,
            segment_id="seg_001"
        )
        assert segment.start_time == 0.0
        assert segment.end_time == 1.0
        assert np.array_equal(segment.audio_data, audio_data)
        assert segment.confidence == 0.9
        assert segment.segment_id == "seg_001"


class TestAlignedPair:
    """Test cases for AlignedPair data model."""
    
    def test_aligned_pair_creation(self):
        """Test basic AlignedPair creation."""
        vocab_entry = VocabularyEntry("hello", "你好", 1)
        audio_data = np.array([0.1, 0.2, 0.3])
        audio_segment = AudioSegment(0.0, 1.0, audio_data, 0.9, "seg_001")
        
        aligned_pair = AlignedPair(
            vocabulary_entry=vocab_entry,
            audio_segment=audio_segment,
            alignment_confidence=0.85,
            audio_file_path="/path/to/audio.wav"
        )
        
        assert aligned_pair.vocabulary_entry == vocab_entry
        assert aligned_pair.audio_segment == audio_segment
        assert aligned_pair.alignment_confidence == 0.85
        assert aligned_pair.audio_file_path == "/path/to/audio.wav"


class TestAnkiCard:
    """Test cases for AnkiCard data model."""
    
    def test_anki_card_creation(self):
        """Test basic AnkiCard creation."""
        card = AnkiCard(
            front_text="hello",
            back_text="你好",
            audio_file="hello.mp3",
            tags=["cantonese", "greetings"],
            card_id="card_001"
        )
        
        assert card.front_text == "hello"
        assert card.back_text == "你好"
        assert card.audio_file == "hello.mp3"
        assert card.tags == ["cantonese", "greetings"]
        assert card.card_id == "card_001"