"""
Unit tests for AnkiPackageGenerator._create_anki_card().

Covers:
  - Field ordering: [English, Jyutping, Cantonese, Audio, Tags] (slots 0–4)
  - Empty Jyutping: slot 1 is "" and slot 2 is the Cantonese value
  - Model ID: note.model.model_id == CantoneseCardTemplate.MODEL_ID (1607392321)

These tests are written against the FIXED code and are expected to PASS.

**Validates: Requirements 2.1, 2.2**
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cantonese_anki_generator.anki.package_generator import AnkiPackageGenerator
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate
from cantonese_anki_generator.models import AlignedPair, AudioSegment, VocabularyEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aligned_pair(english: str, cantonese: str, jyutping: str = "") -> AlignedPair:
    """Build a minimal AlignedPair for unit-testing _create_anki_card()."""
    vocab = VocabularyEntry(
        english=english,
        cantonese=cantonese,
        jyutping=jyutping,
        row_index=0,
    )
    segment = AudioSegment(
        start_time=0.0,
        end_time=0.1,
        audio_data=np.zeros(100, dtype=np.float32),
        confidence=1.0,
        segment_id="test_seg",
        audio_file_path="",
    )
    return AlignedPair(
        vocabulary_entry=vocab,
        audio_segment=segment,
        alignment_confidence=1.0,
        audio_file_path="",
    )


# ---------------------------------------------------------------------------
# Test 1 — All five fields populated: verify canonical slot order
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_anki_card_all_fields_slot_order():
    """
    When all five fields are provided, _create_anki_card() must place them in
    the canonical order:
      slot 0 → English
      slot 1 → Jyutping
      slot 2 → Cantonese
      slot 3 → Audio  (starts with "[sound:")
      slot 4 → Tags

    **Validates: Requirements 2.1**
    """
    generator = AnkiPackageGenerator()
    english = "blue"
    cantonese = "藍"
    jyutping = "laam4"

    pair = _make_aligned_pair(english, cantonese, jyutping)
    note = generator._create_anki_card(pair, index=1)

    assert note is not None, "_create_anki_card() returned None unexpectedly"
    assert len(note.fields) == 5, f"Expected 5 fields, got {len(note.fields)}"

    # Slot 0: English
    assert note.fields[0] == english, (
        f"Slot 0 (English): expected '{english}', got '{note.fields[0]}'"
    )

    # Slot 1: Jyutping
    assert note.fields[1] == jyutping, (
        f"Slot 1 (Jyutping): expected '{jyutping}', got '{note.fields[1]}'"
    )

    # Slot 2: Cantonese
    assert note.fields[2] == cantonese, (
        f"Slot 2 (Cantonese): expected '{cantonese}', got '{note.fields[2]}'"
    )

    # Slot 3: Audio reference
    assert note.fields[3].startswith("[sound:"), (
        f"Slot 3 (Audio): expected '[sound:…]', got '{note.fields[3]}'"
    )

    # Slot 4: Tags (string, may be empty or space-separated)
    assert isinstance(note.fields[4], str), (
        f"Slot 4 (Tags): expected a string, got {type(note.fields[4])}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Empty Jyutping: slot 1 is "" and slot 2 is Cantonese
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_anki_card_empty_jyutping():
    """
    When Jyutping is empty, _create_anki_card() must:
      - Place "" in slot 1 (Jyutping)
      - Place the Cantonese value in slot 2

    **Validates: Requirements 2.1**
    """
    generator = AnkiPackageGenerator()
    english = "water"
    cantonese = "水"
    jyutping = ""  # intentionally empty

    pair = _make_aligned_pair(english, cantonese, jyutping)
    note = generator._create_anki_card(pair, index=2)

    assert note is not None, "_create_anki_card() returned None unexpectedly"

    # Slot 1: empty Jyutping
    assert note.fields[1] == "", (
        f"Slot 1 (Jyutping): expected '' for empty jyutping, got '{note.fields[1]}'"
    )

    # Slot 2: Cantonese still present
    assert note.fields[2] == cantonese, (
        f"Slot 2 (Cantonese): expected '{cantonese}', got '{note.fields[2]}'"
    )

    # Slot 0 and 3 sanity checks
    assert note.fields[0] == english
    assert note.fields[3].startswith("[sound:")


# ---------------------------------------------------------------------------
# Test 3 — Model ID matches CantoneseCardTemplate.MODEL_ID (1607392321)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_anki_card_model_id():
    """
    The note produced by _create_anki_card() must use the model whose
    model_id equals CantoneseCardTemplate.MODEL_ID (1607392321).

    **Validates: Requirements 2.2**
    """
    generator = AnkiPackageGenerator()
    pair = _make_aligned_pair("hello", "你好", "nei5 hou2")

    note = generator._create_anki_card(pair, index=1)

    assert note is not None, "_create_anki_card() returned None unexpectedly"
    assert note.model.model_id == CantoneseCardTemplate.MODEL_ID, (
        f"Model ID: expected {CantoneseCardTemplate.MODEL_ID} "
        f"(CantoneseCardTemplate.MODEL_ID), got {note.model.model_id}"
    )
    # Explicit numeric check so the test is self-documenting
    assert note.model.model_id == 1607392321, (
        f"Model ID: expected 1607392321, got {note.model.model_id}"
    )
