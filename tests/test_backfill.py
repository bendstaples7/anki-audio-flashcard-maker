"""
Unit tests for backfill_bidirectional_cards.py.

Task 4.2: Unit tests for build_bidirectional_package() model selection.

Covers the canonical four-way model ID mapping:
  1607392319 (LEGACY_MODEL_ID)          → create_model_no_jyutping() → output model_id=1607392322
  1607392320 (JYUTPING_MODEL_ID)        → create_model()             → output model_id=1607392321
  1607392321 (MODEL_ID)                 → create_model()             → output model_id=1607392321
  1607392322 (MODEL_ID_NO_JYUTPING)     → create_model_no_jyutping() → output model_id=1607392322

Also covers unknown model IDs falling through to the 5-field default (model_id=1607392321).

**Validates: Requirements 2.5, 2.6, 3.1, 3.2**
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backfill_bidirectional_cards import build_bidirectional_package
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_note_4field(guid: str = "testguid") -> dict:
    """Minimal 4-field note (English, Cantonese, Audio, Tags)."""
    return {
        "id": 1,
        "guid": guid,
        "mid": 0,  # will be overridden by original_mid parameter
        "flds": ["hello", "你好", "", ""],
        "tags": "",
        "sfld": "hello",
    }


def _make_note_5field(guid: str = "testguid") -> dict:
    """Minimal 5-field note (English, Cantonese, Jyutping, Audio, Tags)."""
    return {
        "id": 1,
        "guid": guid,
        "mid": 0,  # will be overridden by original_mid parameter
        "flds": ["hello", "你好", "nei5 hou2", "", ""],
        "tags": "",
        "sfld": "hello",
    }


def _get_output_model_id(original_mid: int, notes: list[dict]) -> int:
    """
    Call build_bidirectional_package() with the given original_mid and notes,
    then return the model_id of the first note in the output deck.
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        package = build_bidirectional_package(
            notes=notes,
            media_dir=media_dir,
            media_map={},
            deck_name="Test Deck",
            original_mid=original_mid,
        )
    return package.decks[0].notes[0].model.model_id


# ---------------------------------------------------------------------------
# Tests — canonical four-way mapping
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_model_selection_legacy_mid_1607392319():
    """
    original_mid=1607392319 (LEGACY_MODEL_ID) must select create_model_no_jyutping()
    → output model_id=1607392322 (MODEL_ID_NO_JYUTPING).

    **Validates: Requirements 3.1**
    """
    output_model_id = _get_output_model_id(1607392319, [_make_note_4field()])
    assert output_model_id == 1607392322, (
        f"original_mid=1607392319: expected output model_id=1607392322, "
        f"got {output_model_id}"
    )


@pytest.mark.unit
def test_model_selection_jyutping_mid_1607392320():
    """
    original_mid=1607392320 (JYUTPING_MODEL_ID) must select create_model()
    → output model_id=1607392321 (MODEL_ID).

    **Validates: Requirements 2.5, 3.2**
    """
    output_model_id = _get_output_model_id(1607392320, [_make_note_5field()])
    assert output_model_id == 1607392321, (
        f"original_mid=1607392320: expected output model_id=1607392321, "
        f"got {output_model_id}"
    )


@pytest.mark.unit
def test_model_selection_model_id_1607392321():
    """
    original_mid=1607392321 (MODEL_ID) must select create_model()
    → output model_id=1607392321 (unchanged).

    **Validates: Requirements 2.6, 3.2**
    """
    output_model_id = _get_output_model_id(1607392321, [_make_note_5field()])
    assert output_model_id == 1607392321, (
        f"original_mid=1607392321: expected output model_id=1607392321, "
        f"got {output_model_id}"
    )


@pytest.mark.unit
def test_model_selection_model_id_no_jyutping_1607392322():
    """
    original_mid=1607392322 (MODEL_ID_NO_JYUTPING) must select create_model_no_jyutping()
    → output model_id=1607392322 (unchanged).

    **Validates: Requirements 2.5, 3.1**
    """
    output_model_id = _get_output_model_id(1607392322, [_make_note_4field()])
    assert output_model_id == 1607392322, (
        f"original_mid=1607392322: expected output model_id=1607392322, "
        f"got {output_model_id}"
    )


# ---------------------------------------------------------------------------
# Test — unknown model ID falls through to 5-field default
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_model_selection_unknown_mid_falls_through_to_default():
    """
    An unknown original_mid (e.g. 9999999) must fall through to the 5-field
    default model (model_id=1607392321) without raising an exception.

    **Validates: Requirements 2.6**
    """
    unknown_mid = 9999999
    # Should not raise
    output_model_id = _get_output_model_id(unknown_mid, [_make_note_5field()])
    assert output_model_id == 1607392321, (
        f"Unknown original_mid={unknown_mid}: expected fallback model_id=1607392321, "
        f"got {output_model_id}"
    )


# ---------------------------------------------------------------------------
# Tests — media file naming (task 4.3)
# ---------------------------------------------------------------------------

def _make_note_5field_with_audio(guid: str = "audioguid") -> dict:
    """5-field note with a [sound:hello_001.wav] audio reference in slot 3."""
    return {
        "id": 1,
        "guid": guid,
        "mid": 0,
        "flds": ["hello", "你好", "nei5 hou2", "[sound:hello_001.wav]", ""],
        "tags": "",
        "sfld": "hello",
    }


@pytest.mark.unit
def test_media_file_name_in_package_media_files():
    """
    After calling build_bidirectional_package() with media_map={"hello_001.wav": "0"},
    the entry in package.media_files must have basename "hello_001.wav", not "0".

    **Validates: Requirements 2.3, 2.4**
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        # Create the archive file named "0" (as Anki stores it)
        (media_dir / "0").write_bytes(b"RIFF....WAVEfmt ")

        package = build_bidirectional_package(
            notes=[_make_note_5field_with_audio()],
            media_dir=media_dir,
            media_map={"hello_001.wav": "0"},
            deck_name="Test Deck",
            original_mid=1607392321,
        )

    assert len(package.media_files) == 1, (
        f"Expected 1 media file, got {len(package.media_files)}"
    )
    assert Path(package.media_files[0]).name == "hello_001.wav", (
        f"Expected media file basename 'hello_001.wav', "
        f"got '{Path(package.media_files[0]).name}'"
    )


@pytest.mark.unit
def test_media_named_file_exists_in_temp_dir():
    """
    After calling build_bidirectional_package() with media_map={"hello_001.wav": "0"},
    the file hello_001.wav must exist in the temp directory (copied from "0").

    **Validates: Requirements 2.3, 2.4**
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        # Create the archive file named "0"
        (media_dir / "0").write_bytes(b"RIFF....WAVEfmt ")

        build_bidirectional_package(
            notes=[_make_note_5field_with_audio()],
            media_dir=media_dir,
            media_map={"hello_001.wav": "0"},
            deck_name="Test Deck",
            original_mid=1607392321,
        )

        assert (media_dir / "hello_001.wav").exists(), (
            "Expected hello_001.wav to exist in the temp directory after "
            "build_bidirectional_package(), but it was not found."
        )


# ---------------------------------------------------------------------------
# Tests — edge cases (task 4.4)
# ---------------------------------------------------------------------------

import io
import json
import sqlite3
import zipfile


def _make_minimal_apkg(tmp_path: Path, notes: list[dict], model_id: int = 1607392321) -> Path:
    """
    Build a minimal synthetic .apkg file at tmp_path/source.apkg.

    Each note dict must have keys: id, guid, mid, flds (list of str), tags, sfld.
    The .apkg is a zip containing:
      - collection.anki2  (SQLite with a notes table)
      - media             (JSON: {})
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "collection.anki2"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE notes "
        "(id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER, "
        "flds TEXT, tags TEXT, sfld TEXT)"
    )
    for n in notes:
        conn.execute(
            "INSERT INTO notes (id, guid, mid, flds, tags, sfld) VALUES (?,?,?,?,?,?)",
            (n["id"], n["guid"], n["mid"], "\x1f".join(n["flds"]), n["tags"], n["sfld"]),
        )
    conn.commit()
    conn.close()

    media_path = tmp_path / "media"
    media_path.write_text("{}", encoding="utf-8")

    apkg_path = tmp_path / "source.apkg"
    with zipfile.ZipFile(str(apkg_path), "w") as zf:
        zf.write(str(db_path), "collection.anki2")
        zf.write(str(media_path), "media")

    return apkg_path


# --- 1. Empty English field: note is skipped, warning is logged ---------------

@pytest.mark.unit
def test_empty_english_field_note_is_skipped(caplog):
    """
    A note with an empty English field (flds[0] == "") must be skipped and a
    warning must be logged.  The output deck must contain 0 notes.

    **Validates: Requirements 3.6**
    """
    note_empty_english = {
        "id": 1,
        "guid": "emptyeng",
        "mid": 0,
        "flds": ["", "你好", "nei5 hou2", "", ""],
        "tags": "",
        "sfld": "",
    }
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        import logging
        with caplog.at_level(logging.WARNING, logger="backfill_bidirectional_cards"):
            package = build_bidirectional_package(
                notes=[note_empty_english],
                media_dir=media_dir,
                media_map={},
                deck_name="Test Deck",
                original_mid=1607392321,
            )

    assert len(package.decks[0].notes) == 0, (
        f"Expected 0 notes in deck (empty English note should be skipped), "
        f"got {len(package.decks[0].notes)}"
    )
    assert any("Skipping" in r.message for r in caplog.records), (
        "Expected a warning log message containing 'Skipping' for the empty-English note"
    )


@pytest.mark.unit
def test_empty_cantonese_field_note_is_skipped(caplog):
    """
    A note with an empty Cantonese field (flds[1] == "") must be skipped and a
    warning must be logged.  The output deck must contain 0 notes.

    **Validates: Requirements 3.6**
    """
    note_empty_cantonese = {
        "id": 2,
        "guid": "emptycant",
        "mid": 0,
        "flds": ["hello", "", "nei5 hou2", "", ""],
        "tags": "",
        "sfld": "hello",
    }
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        import logging
        with caplog.at_level(logging.WARNING, logger="backfill_bidirectional_cards"):
            package = build_bidirectional_package(
                notes=[note_empty_cantonese],
                media_dir=media_dir,
                media_map={},
                deck_name="Test Deck",
                original_mid=1607392321,
            )

    assert len(package.decks[0].notes) == 0, (
        f"Expected 0 notes in deck (empty Cantonese note should be skipped), "
        f"got {len(package.decks[0].notes)}"
    )
    assert any("Skipping" in r.message for r in caplog.records), (
        "Expected a warning log message containing 'Skipping' for the empty-Cantonese note"
    )


# --- 2. dry_run=True: convert_apkg returns True and no output file is created --

@pytest.mark.unit
def test_dry_run_returns_true_and_no_output_file_created():
    """
    convert_apkg() with dry_run=True must return True and must NOT create the
    destination file.

    **Validates: Requirements 3.4**
    """
    from backfill_bidirectional_cards import convert_apkg

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Build a minimal synthetic .apkg as the source
        note = {
            "id": 1,
            "guid": "dryrun1",
            "mid": 1607392321,
            "flds": ["hello", "你好", "nei5 hou2", "", ""],
            "tags": "",
            "sfld": "hello",
        }
        src = _make_minimal_apkg(tmp_dir / "src", [note])
        dest = tmp_dir / "output.apkg"

        result = convert_apkg(src, dest, dry_run=True)

        # Assertions must be inside the context so dest still refers to a
        # path within the live temporary directory.
        assert result is True, (
            f"convert_apkg() with dry_run=True should return True, got {result!r}"
        )
        assert not dest.exists(), (
            f"convert_apkg() with dry_run=True must NOT create the dest file, "
            f"but {dest} exists"
        )


# --- 3. Missing audio archive file: warning logged, note still added ----------

@pytest.mark.unit
def test_missing_audio_archive_file_note_still_added(caplog):
    """
    When a note references [sound:missing.wav] and the archive key "99" is in
    media_map but the file "99" does NOT exist in media_dir, a warning must be
    logged and the note must still be added to the deck.  package.media_files
    must be empty (no media file was added).

    **Validates: Requirements 3.5**
    """
    note_with_missing_audio = {
        "id": 3,
        "guid": "missingaudio",
        "mid": 0,
        "flds": ["hello", "你好", "nei5 hou2", "[sound:missing.wav]", ""],
        "tags": "",
        "sfld": "hello",
    }
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        # Intentionally do NOT create the file "99" in media_dir
        import logging
        with caplog.at_level(logging.WARNING, logger="backfill_bidirectional_cards"):
            package = build_bidirectional_package(
                notes=[note_with_missing_audio],
                media_dir=media_dir,
                media_map={"missing.wav": "99"},
                deck_name="Test Deck",
                original_mid=1607392321,
            )

    assert len(package.decks[0].notes) == 1, (
        f"Expected 1 note in deck (note should not be skipped for missing audio), "
        f"got {len(package.decks[0].notes)}"
    )
    assert package.media_files == [], (
        f"Expected package.media_files to be empty when archive file is missing, "
        f"got {package.media_files!r}"
    )
    assert any("not found" in r.message.lower() or "missing" in r.message.lower()
               for r in caplog.records), (
        "Expected a warning log message about the missing media file"
    )
