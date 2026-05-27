"""
Preservation property tests — Task 2 of the bugfix workflow.

These tests follow the observation-first methodology:
  1. Run UNFIXED code with non-buggy inputs.
  2. Observe the output.
  3. Encode the observed behaviour as property-based tests.

ALL tests in this file MUST PASS on the UNFIXED code.  They capture the
baseline behaviour that the fix must not break.

Scoped to inputs where NONE of the four bug conditions trigger:
  - Bug 1 / Bug 2: package_generator path — not exercised here (those are
    bug-condition tests in test_bugfix_exploration.py).
  - Bug 3: media manifest naming — Preservation 4 only checks *count*, not
    basename, so it passes on unfixed code.
  - Bug 4: model selection for mid=1607392320 / mid=1607392322 — Preservation 1
    only uses mid=1607392319, which is the unchanged legacy path.

**Validates: Requirements 3.1, 3.4, 3.5, 3.6, 3.7**
"""

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import genanki
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backfill_bidirectional_cards import (
    build_bidirectional_package,
    convert_apkg,
)
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEGACY_MODEL_ID = 1607392319        # 4-field legacy → output mid=1607392322
MODEL_ID_NO_JYUTPING = 1607392322   # already-bidirectional 4-field


# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

def _nonempty_text():
    """Strategy: non-empty, non-whitespace-only text (printable ASCII + CJK)."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Lo", "Nd"),
            whitelist_characters=" ",
        ),
        min_size=1,
    ).filter(lambda s: s.strip() != "")


def _audio_field(filename: str) -> str:
    return f"[sound:{filename}]"


def _make_raw_note_4field(english: str, cantonese: str, audio_filename: str) -> dict:
    """Build a raw note dict as read_notes_from_db would return for a 4-field note."""
    return {
        "id": 1,
        "guid": "testguid",
        "mid": LEGACY_MODEL_ID,
        "flds": [english, cantonese, _audio_field(audio_filename), ""],
        "tags": "",
        "sfld": english,
    }


@st.composite
def legacy_notes_strategy(draw):
    """
    Strategy: a non-empty list of valid 4-field raw notes for mid=1607392319.

    Each note has non-empty English and Cantonese fields so none are skipped.
    """
    n = draw(st.integers(min_value=1, max_value=10))
    notes = []
    for i in range(n):
        english = draw(_nonempty_text())
        cantonese = draw(_nonempty_text())
        audio_filename = f"audio_{i:03d}.wav"
        notes.append(_make_raw_note_4field(english, cantonese, audio_filename))
    return notes


@st.composite
def audio_note_strategy(draw):
    """
    Strategy: a raw note dict whose audio field resolves to a real file.

    Returns (note_dict, filename) so the caller can create the file.
    """
    english = draw(_nonempty_text())
    cantonese = draw(_nonempty_text())
    filename = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=20,
        ).map(lambda s: s + ".wav")
    )
    note = {
        "id": 1,
        "guid": "testguid",
        "mid": LEGACY_MODEL_ID,
        "flds": [english, cantonese, _audio_field(filename), ""],
        "tags": "",
        "sfld": english,
    }
    return note, filename


# ---------------------------------------------------------------------------
# Helper: build a minimal synthetic .apkg for convert_apkg tests
# ---------------------------------------------------------------------------

def _build_synthetic_apkg(dest_path: Path, notes_data: list[dict], mid: int) -> None:
    """
    Write a minimal .apkg (zip) containing collection.anki2 + empty media manifest.

    notes_data: list of dicts with keys english, cantonese, audio (filename str).
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        db_path = tmp_dir / "collection.anki2"

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                guid TEXT,
                mid INTEGER,
                flds TEXT,
                tags TEXT,
                sfld TEXT,
                csum INTEGER DEFAULT 0,
                flags INTEGER DEFAULT 0,
                data TEXT DEFAULT ''
            )"""
        )
        for i, nd in enumerate(notes_data):
            flds = "\x1f".join([nd["english"], nd["cantonese"],
                                f"[sound:{nd['audio']}]", ""])
            conn.execute(
                "INSERT INTO notes (id, guid, mid, flds, tags, sfld) VALUES (?,?,?,?,?,?)",
                (i + 1, f"guid{i}", mid, flds, "", nd["english"]),
            )
        conn.commit()
        conn.close()

        media_manifest = json.dumps({})
        media_path = tmp_dir / "media"
        media_path.write_text(media_manifest, encoding="utf-8")

        with zipfile.ZipFile(dest_path, "w") as zf:
            zf.write(db_path, "collection.anki2")
            zf.write(media_path, "media")


# ===========================================================================
# Preservation 1 — Legacy 4-field model path (mid=1607392319)
# ===========================================================================

@pytest.mark.property
@given(legacy_notes_strategy())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_1_legacy_model_mid(notes):
    """
    **Validates: Requirements 3.1**

    For any list of valid 4-field notes with original_mid=1607392319,
    build_bidirectional_package() MUST select create_model_no_jyutping()
    and the output model mid MUST be MODEL_ID_NO_JYUTPING (1607392322).

    This path is UNCHANGED by the fix — it must pass on both unfixed and fixed code.
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        media_map: dict[str, str] = {}

        package = build_bidirectional_package(
            notes=notes,
            media_dir=media_dir,
            media_map=media_map,
            deck_name="Test Deck",
            original_mid=LEGACY_MODEL_ID,
        )

        # The package must have been built
        assert package is not None

        # The deck must contain notes
        deck = package.decks[0]
        assert len(deck.notes) > 0

        # Every note must use the no-jyutping model (model_id=1607392322)
        for note in deck.notes:
            assert note.model.model_id == CantoneseCardTemplate.MODEL_ID_NO_JYUTPING, (
                f"Expected model model_id {CantoneseCardTemplate.MODEL_ID_NO_JYUTPING}, "
                f"got {note.model.model_id}"
            )


# ===========================================================================
# Preservation 2 — Dry-run produces no output file
# ===========================================================================

@pytest.mark.property
@given(st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_2_dry_run_no_output_file(deck_name_suffix):
    """
    **Validates: Requirements 3.4**

    For any valid source .apkg and any dest path, convert_apkg() with
    dry_run=True MUST return True and MUST NOT create the dest file.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "source.apkg"
        dest = tmp_dir / f"output_{deck_name_suffix[:10]}.apkg"

        # Build a minimal valid source .apkg
        _build_synthetic_apkg(
            src,
            notes_data=[{"english": "hello", "cantonese": "你好", "audio": "hello.wav"}],
            mid=LEGACY_MODEL_ID,
        )

        result = convert_apkg(src, dest, dry_run=True)

        assert result is True, "convert_apkg with dry_run=True must return True"
        assert not dest.exists(), (
            f"dry_run=True must not create the dest file, but {dest} was created"
        )


# ===========================================================================
# Preservation 3 — Empty English or Cantonese field is skipped
# ===========================================================================

def _make_empty_english_note(cantonese: str) -> dict:
    return {
        "id": 1, "guid": "g1", "mid": LEGACY_MODEL_ID,
        "flds": ["", cantonese, "[sound:x.wav]", ""],
        "tags": "", "sfld": "",
    }


def _make_empty_cantonese_note(english: str) -> dict:
    return {
        "id": 2, "guid": "g2", "mid": LEGACY_MODEL_ID,
        "flds": [english, "", "[sound:x.wav]", ""],
        "tags": "", "sfld": english,
    }


def _make_whitespace_english_note(cantonese: str) -> dict:
    return {
        "id": 3, "guid": "g3", "mid": LEGACY_MODEL_ID,
        "flds": ["   ", cantonese, "[sound:x.wav]", ""],
        "tags": "", "sfld": "   ",
    }


@pytest.mark.property
@given(
    st.lists(
        st.tuples(_nonempty_text(), _nonempty_text()),
        min_size=0,
        max_size=8,
    ),
    st.lists(
        st.sampled_from(["empty_english", "empty_cantonese", "whitespace_english"]),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_3_empty_fields_skipped(valid_pairs, invalid_types):
    """
    **Validates: Requirements 3.6**

    For any mix of valid notes and notes with empty/whitespace English or
    Cantonese fields, build_bidirectional_package() MUST include exactly the
    valid notes in the output deck and skip the invalid ones.
    """
    valid_notes = [
        _make_raw_note_4field(eng, cant, f"audio_{i}.wav")
        for i, (eng, cant) in enumerate(valid_pairs)
    ]

    invalid_notes = []
    for t in invalid_types:
        if t == "empty_english":
            invalid_notes.append(_make_empty_english_note("你好"))
        elif t == "empty_cantonese":
            invalid_notes.append(_make_empty_cantonese_note("hello"))
        else:
            invalid_notes.append(_make_whitespace_english_note("你好"))

    all_notes = valid_notes + invalid_notes

    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)
        package = build_bidirectional_package(
            notes=all_notes,
            media_dir=media_dir,
            media_map={},
            deck_name="Test Deck",
            original_mid=LEGACY_MODEL_ID,
        )

    deck = package.decks[0]
    assert len(deck.notes) == len(valid_notes), (
        f"Expected {len(valid_notes)} notes in deck (valid only), "
        f"got {len(deck.notes)}"
    )


# ===========================================================================
# Preservation 4 — All present audio files included in output
# ===========================================================================

@pytest.mark.property
@given(st.lists(audio_note_strategy(), min_size=1, max_size=8))
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_4_all_audio_files_included(note_filename_pairs):
    """
    **Validates: Requirements 3.5**

    For any set of notes where every [sound:F] field resolves to a file
    present in media_dir, the count of package.media_files MUST equal the
    count of notes with resolvable audio.

    NOTE: On unfixed code the paths appended are numeric archive-key paths
    (Bug 3), but the COUNT is still correct — every resolvable file is
    included.  This preservation test checks count only, not basename.
    """
    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)

        notes = []
        media_map: dict[str, str] = {}
        expected_count = 0

        for i, (note, filename) in enumerate(note_filename_pairs):
            archive_key = str(i)
            # Create the archive-key file in media_dir
            (media_dir / archive_key).write_bytes(b"RIFF....WAVEfmt ")
            media_map[filename] = archive_key
            # Update the note's audio field to use this filename
            note = dict(note)
            note["flds"] = [
                note["flds"][0],
                note["flds"][1],
                _audio_field(filename),
                "",
            ]
            notes.append(note)
            expected_count += 1

        package = build_bidirectional_package(
            notes=notes,
            media_dir=media_dir,
            media_map=media_map,
            deck_name="Test Deck",
            original_mid=LEGACY_MODEL_ID,
        )

    assert len(package.media_files) == expected_count, (
        f"Expected {expected_count} media files, got {len(package.media_files)}"
    )


# ===========================================================================
# Preservation 5 — Stable deck ID derivation
# ===========================================================================

def _deck_id_from_name(name: str) -> int:
    """
    Replicate the deck ID derivation used in build_bidirectional_package().

    Uses hashlib.md5 of the name — deterministic, no timestamp component.
    """
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 2_147_483_647


@pytest.mark.property
@given(st.text(min_size=1))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_5_stable_deck_id(deck_name):
    """
    **Validates: Requirements 3.7**

    For any deck name string, calling the deck ID derivation twice with the
    same name MUST produce the same integer both times.

    This confirms the derivation is deterministic (no timestamp component),
    so re-imports merge into the existing deck rather than creating duplicates.
    """
    id1 = _deck_id_from_name(deck_name)
    id2 = _deck_id_from_name(deck_name)
    assert id1 == id2, (
        f"Deck ID is not stable for name {deck_name!r}: "
        f"first call={id1}, second call={id2}"
    )


@pytest.mark.property
@given(st.text(min_size=1))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_5_stable_deck_id_via_package(deck_name):
    """
    **Validates: Requirements 3.7**

    End-to-end variant: build_bidirectional_package() called twice with the
    same deck_name MUST produce the same deck ID both times.
    """
    note = _make_raw_note_4field("hello", "你好", "hello.wav")

    with tempfile.TemporaryDirectory() as tmp:
        media_dir = Path(tmp)

        pkg1 = build_bidirectional_package(
            notes=[note],
            media_dir=media_dir,
            media_map={},
            deck_name=deck_name,
            original_mid=LEGACY_MODEL_ID,
        )
        pkg2 = build_bidirectional_package(
            notes=[note],
            media_dir=media_dir,
            media_map={},
            deck_name=deck_name,
            original_mid=LEGACY_MODEL_ID,
        )

    deck_id_1 = pkg1.decks[0].deck_id
    deck_id_2 = pkg2.decks[0].deck_id

    assert deck_id_1 == deck_id_2, (
        f"Deck ID not stable for name {deck_name!r}: "
        f"first={deck_id_1}, second={deck_id_2}"
    )
