"""
Bug condition exploration tests for the Anki card field alignment bugfix.

These tests are EXPECTED TO FAIL on unfixed code — failure confirms the bugs exist.
DO NOT fix the tests or the code when they fail.

When these tests PASS after the fix is applied, they confirm all bugs are resolved.

Bugs under test:
  Bug 1 — Field Slot Misassignment in _create_anki_card()
  Bug 2 — Wrong Model ID in _create_anki_card()
  Bug 3 — Numeric Archive Key in Media Manifest (build_bidirectional_package)
  Bug 4 — Bad Model Selection for MODEL_ID_NO_JYUTPING (build_bidirectional_package)

**Validates: Requirements 1.1, 1.2, 1.4, 1.6, 2.1, 2.2, 2.3, 2.5, 2.6**
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cantonese_anki_generator.anki.package_generator import AnkiPackageGenerator
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate
from cantonese_anki_generator.models import AlignedPair, AudioSegment, VocabularyEntry
from backfill_bidirectional_cards import build_bidirectional_package


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aligned_pair(english: str, cantonese: str, jyutping: str) -> AlignedPair:
    """Create a minimal AlignedPair for testing _create_anki_card()."""
    vocab = VocabularyEntry(
        english=english,
        cantonese=cantonese,
        jyutping=jyutping,
        row_index=0,
    )
    # AudioSegment requires audio_data; use a tiny silent array
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


def _make_raw_note(english: str, cantonese: str, jyutping: str, audio: str) -> dict:
    """Create a raw note dict as returned by read_notes_from_db() for 5-field notes."""
    return {
        "id": 1,
        "guid": "testguid",
        "mid": 1607392321,
        "flds": [english, cantonese, jyutping, audio, ""],
        "tags": "",
        "sfld": english,
    }


# ---------------------------------------------------------------------------
# Bug 1 — Field Slot Misassignment
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
)
@settings(max_examples=50)
def test_bug1_field_slot_order(english: str, cantonese: str, jyutping: str):
    """
    Bug 1: _create_anki_card() places Cantonese in slot 1 and Jyutping in slot 2,
    but the canonical order requires Jyutping in slot 1 and Cantonese in slot 2.

    EXPECTED TO FAIL on unfixed code.

    Counterexample documented:
      note.fields[1] = "藍"   (Chinese characters — should be Jyutping)
      note.fields[2] = "laam2" (Jyutping — should be Cantonese)
      Slots 1 and 2 are swapped relative to the canonical order.

    **Validates: Requirements 2.1**
    """
    generator = AnkiPackageGenerator()
    pair = _make_aligned_pair(english, cantonese, jyutping)

    note = generator._create_anki_card(pair, index=1)
    assert note is not None, "Note creation returned None"

    # Slot 0: English
    assert note.fields[0] == english.strip(), (
        f"Slot 0 should be English '{english.strip()}', got '{note.fields[0]}'"
    )

    # Slot 1: Jyutping  ← EXPECTED TO FAIL on unfixed code (gets Cantonese instead)
    assert note.fields[1] == jyutping.strip(), (
        f"Slot 1 should be Jyutping '{jyutping.strip()}', got '{note.fields[1]}'"
    )

    # Slot 2: Cantonese  ← EXPECTED TO FAIL on unfixed code (gets Jyutping instead)
    assert note.fields[2] == cantonese.strip(), (
        f"Slot 2 should be Cantonese '{cantonese.strip()}', got '{note.fields[2]}'"
    )

    # Slot 3: Audio reference
    assert note.fields[3].startswith("[sound:"), (
        f"Slot 3 should be an audio reference, got '{note.fields[3]}'"
    )


@pytest.mark.unit
def test_bug1_concrete_example():
    """
    Concrete counterexample for Bug 1 using the canonical blue/藍/laam2 values.

    EXPECTED TO FAIL on unfixed code.

    Counterexample:
      note.fields[1] = "藍"   (should be "laam2")
      note.fields[2] = "laam2" (should be "藍")

    **Validates: Requirements 2.1**
    """
    generator = AnkiPackageGenerator()
    pair = _make_aligned_pair("blue", "藍", "laam2")

    note = generator._create_anki_card(pair, index=1)
    assert note is not None

    assert note.fields[0] == "blue", f"Slot 0: expected 'blue', got '{note.fields[0]}'"

    # EXPECTED TO FAIL on unfixed code — unfixed puts "藍" here
    assert note.fields[1] == "laam2", (
        f"Slot 1: expected 'laam2' (Jyutping), got '{note.fields[1]}'"
    )

    # EXPECTED TO FAIL on unfixed code — unfixed puts "laam2" here
    assert note.fields[2] == "藍", (
        f"Slot 2: expected '藍' (Cantonese), got '{note.fields[2]}'"
    )

    assert note.fields[3].startswith("[sound:"), (
        f"Slot 3: expected audio reference, got '{note.fields[3]}'"
    )


# ---------------------------------------------------------------------------
# Bug 2 — Wrong Model ID
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bug2_model_id():
    """
    Bug 2: _create_anki_card() must produce a note whose model.mid equals
    CantoneseCardTemplate.MODEL_ID (1607392321).

    EXPECTED OUTCOME: PASSES if the current source already uses the constant
    (confirms no regression needed). FAILS if a wrong ID is present.

    Result documented: model.mid == 1607392321 on current unfixed code
    (Bug 2 is a regression-prevention guard, not an active misassignment).

    **Validates: Requirements 2.2**
    """
    generator = AnkiPackageGenerator()
    pair = _make_aligned_pair("blue", "藍", "laam2")

    note = generator._create_anki_card(pair, index=1)
    assert note is not None

    assert note.model.model_id == CantoneseCardTemplate.MODEL_ID, (
        f"Model ID should be {CantoneseCardTemplate.MODEL_ID} (MODEL_ID), "
        f"got {note.model.model_id}"
    )


# ---------------------------------------------------------------------------
# Bug 3 — Numeric Archive Key in Media Manifest
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bug3_media_manifest_filename():
    """
    Bug 3: build_bidirectional_package() appends the numeric archive key path
    (e.g. "tmp/0") to media_files instead of the named .wav path.

    EXPECTED TO FAIL on unfixed code.

    Counterexample documented:
      Path(media_files[0]).name == "0"  (numeric archive key)
      Expected: Path(media_files[0]).name == "hello_001.wav"

    **Validates: Requirements 2.3, 2.4**
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)

        # Write a dummy file using the numeric archive key "0"
        archive_file = media_dir / "0"
        archive_file.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")  # dummy WAV bytes

        # One note whose audio field references hello_001.wav
        notes = [
            {
                "id": 1,
                "guid": "testguid",
                "mid": 1607392321,
                "flds": ["hello", "你好", "nei5 hou2", "[sound:hello_001.wav]", ""],
                "tags": "",
                "sfld": "hello",
            }
        ]

        # media_map: filename → archive key (as returned by read_media_map)
        media_map = {"hello_001.wav": "0"}

        package = build_bidirectional_package(
            notes=notes,
            media_dir=media_dir,
            media_map=media_map,
            deck_name="Test Deck",
            original_mid=1607392321,
        )

        assert len(package.media_files) == 1, (
            f"Expected 1 media file, got {len(package.media_files)}"
        )

        # EXPECTED TO FAIL on unfixed code — unfixed appends "tmp/0" so name == "0"
        actual_name = Path(package.media_files[0]).name
        assert actual_name == "hello_001.wav", (
            f"Media file basename should be 'hello_001.wav', got '{actual_name}'"
        )


# ---------------------------------------------------------------------------
# Bug 4 — Bad Model Selection for MODEL_ID_NO_JYUTPING
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_bug4_model_id_no_jyutping_preserved():
    """
    Bug 4: build_bidirectional_package() with original_mid=1607392322
    (MODEL_ID_NO_JYUTPING) falls into the else branch and assigns model
    mid=1607392321 instead of preserving 1607392322.

    EXPECTED TO FAIL on unfixed code for the mid=1607392322 case.

    Counterexample documented:
      original_mid=1607392322 → output model mid=1607392321
      Expected: output model mid=1607392322

    **Validates: Requirements 2.5, 2.6**
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)

        # Minimal 4-field note (MODEL_ID_NO_JYUTPING layout: English, Cantonese, Audio, Tags)
        notes_4field = [
            {
                "id": 1,
                "guid": "testguid4field",
                "mid": 1607392322,
                "flds": ["hello", "你好", "", ""],
                "tags": "",
                "sfld": "hello",
            }
        ]

        # EXPECTED TO FAIL on unfixed code — else branch assigns 1607392321
        package = build_bidirectional_package(
            notes=notes_4field,
            media_dir=media_dir,
            media_map={},
            deck_name="Test Deck",
            original_mid=1607392322,
        )

        output_mid = package.decks[0].notes[0].model.model_id
        assert output_mid == 1607392322, (
            f"original_mid=1607392322: output model mid should be 1607392322, "
            f"got {output_mid}"
        )


@pytest.mark.unit
def test_bug4_jyutping_model_id_maps_to_canonical():
    """
    Bug 4 (complementary case): build_bidirectional_package() with
    original_mid=1607392320 (JYUTPING_MODEL_ID) should map to model mid=1607392321.

    EXPECTED TO PASS on unfixed code (confirms this path is already correct).

    **Validates: Requirements 2.5, 2.6**
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)

        notes_5field = [
            {
                "id": 1,
                "guid": "testguid5field",
                "mid": 1607392320,
                "flds": ["hello", "你好", "nei5 hou2", "", ""],
                "tags": "",
                "sfld": "hello",
            }
        ]

        package = build_bidirectional_package(
            notes=notes_5field,
            media_dir=media_dir,
            media_map={},
            deck_name="Test Deck",
            original_mid=1607392320,
        )

        output_mid = package.decks[0].notes[0].model.model_id
        assert output_mid == 1607392321, (
            f"original_mid=1607392320: output model mid should be 1607392321, "
            f"got {output_mid}"
        )
