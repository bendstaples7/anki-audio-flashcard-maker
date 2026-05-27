"""
Integration tests for end-to-end Anki package generation.

Task 4.5 — End-to-end package generation with correct field slots
  - Generate a .apkg from a small vocabulary list (3–5 entries)
  - Unpack the .apkg (it is a zip); open collection.anki2 with SQLite
  - Query the notes table; split flds on \\x1f
  - Assert slot 1 is Jyutping and slot 2 is Cantonese for every note
  - Assert the mid column equals 1607392321 for every note

Task 4.6 — End-to-end backfill with correct media manifest
  - Build a synthetic .apkg with one note containing [sound:hello_001.wav]
    and a media manifest {"0": "hello_001.wav"}
  - Run convert_apkg() on it; unpack the output .apkg
  - Read the media JSON file; assert it contains "hello_001.wav" as a value

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 3.3**
"""

import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backfill_bidirectional_cards import convert_apkg
from cantonese_anki_generator.anki.package_generator import AnkiPackageGenerator
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate
from cantonese_anki_generator.models import AlignedPair, AudioSegment, VocabularyEntry


# ---------------------------------------------------------------------------
# Vocabulary data: 5 entries with English, Cantonese, Jyutping, and audio
# ---------------------------------------------------------------------------

VOCAB_DATA = [
    ("blue",   "藍色", "laam4 sik1"),
    ("water",  "水",   "seoi2"),
    ("cat",    "貓",   "maau1"),
    ("happy",  "開心", "hoi1 sam1"),
    ("school", "學校", "hok6 haau6"),
]


# ---------------------------------------------------------------------------
# Helper: build AlignedPair objects with real (silent) audio files
# ---------------------------------------------------------------------------

def _make_aligned_pairs(tmp_dir: Path) -> list:
    """
    Create one AlignedPair per VOCAB_DATA entry.  Each pair gets a real
    (silent) WAV file written to tmp_dir so that AnkiPackageGenerator can
    copy it into the package.
    """
    pairs = []
    for i, (english, cantonese, jyutping) in enumerate(VOCAB_DATA, start=1):
        # Write a minimal valid WAV file (44-byte header, no audio data)
        wav_path = tmp_dir / f"audio_{i:03d}.wav"
        _write_silent_wav(wav_path)

        vocab = VocabularyEntry(
            english=english,
            cantonese=cantonese,
            jyutping=jyutping,
            row_index=i,
        )
        segment = AudioSegment(
            start_time=0.0,
            end_time=0.5,
            audio_data=np.zeros(100, dtype=np.float32),
            confidence=1.0,
            segment_id=f"seg_{i:03d}",
            audio_file_path=str(wav_path),
        )
        pair = AlignedPair(
            vocabulary_entry=vocab,
            audio_segment=segment,
            alignment_confidence=1.0,
            audio_file_path=str(wav_path),
        )
        pairs.append(pair)
    return pairs


def _write_silent_wav(path: Path) -> None:
    """Write a minimal 44-byte PCM WAV header with no audio samples."""
    import struct

    num_channels = 1
    sample_rate = 16000
    bits_per_sample = 16
    num_samples = 0
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,   # ChunkSize
        b"WAVE",
        b"fmt ",
        16,               # Subchunk1Size (PCM)
        1,                # AudioFormat (PCM = 1)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    path.write_bytes(header)


# ---------------------------------------------------------------------------
# Helper: unpack .apkg and return path to collection.anki2
# ---------------------------------------------------------------------------

def _unpack_apkg(apkg_path: Path, dest_dir: Path) -> Path:
    """Unzip the .apkg and return the path to collection.anki2."""
    with zipfile.ZipFile(str(apkg_path), "r") as zf:
        zf.extractall(str(dest_dir))
    db_path = dest_dir / "collection.anki2"
    assert db_path.exists(), f"collection.anki2 not found after unpacking {apkg_path}"
    return db_path


# ---------------------------------------------------------------------------
# Integration test 4.5 — field slots and model ID
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_end_to_end_field_slots_and_model_id():
    """
    End-to-end test: generate a .apkg from 5 vocabulary entries, unpack it,
    and verify that every note in collection.anki2 has:
      - flds split on \\x1f: slot 1 == Jyutping, slot 2 == Cantonese
      - mid == 1607392321 (CantoneseCardTemplate.MODEL_ID)

    **Validates: Requirements 2.1, 2.2, 3.3**
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        audio_dir = tmp_dir / "audio"
        audio_dir.mkdir()
        unpack_dir = tmp_dir / "unpacked"
        unpack_dir.mkdir()
        apkg_path = tmp_dir / "test_deck.apkg"

        # Build aligned pairs with real audio files
        pairs = _make_aligned_pairs(audio_dir)

        # Generate the .apkg
        generator = AnkiPackageGenerator()
        success = generator.generate_package(
            aligned_pairs=pairs,
            output_path=str(apkg_path),
            deck_name="Integration Test Deck",
        )
        assert success, "generate_package() returned False — package was not created"
        assert apkg_path.exists(), f".apkg file not found at {apkg_path}"

        # Unpack and open the SQLite database
        db_path = _unpack_apkg(apkg_path, unpack_dir)
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT mid, flds FROM notes").fetchall()
        conn.close()

        assert len(rows) == len(VOCAB_DATA), (
            f"Expected {len(VOCAB_DATA)} notes in collection.anki2, got {len(rows)}"
        )

        # Build a lookup from (english, cantonese, jyutping) for assertion
        vocab_lookup = {english: (cantonese, jyutping) for english, cantonese, jyutping in VOCAB_DATA}

        for mid, flds_raw in rows:
            fields = flds_raw.split("\x1f")

            # Must have at least 5 slots
            assert len(fields) >= 5, (
                f"Expected at least 5 fields, got {len(fields)}: {fields!r}"
            )

            english_slot = fields[0]
            jyutping_slot = fields[1]
            cantonese_slot = fields[2]

            # Assert mid == MODEL_ID
            assert mid == CantoneseCardTemplate.MODEL_ID, (
                f"Note mid={mid}, expected {CantoneseCardTemplate.MODEL_ID} "
                f"(CantoneseCardTemplate.MODEL_ID=1607392321)"
            )
            assert mid == 1607392321, (
                f"Note mid={mid}, expected 1607392321"
            )

            # Assert slot 1 is Jyutping and slot 2 is Cantonese
            assert english_slot in vocab_lookup, (
                f"Unexpected English value in slot 0: {english_slot!r}"
            )
            expected_cantonese, expected_jyutping = vocab_lookup[english_slot]

            assert jyutping_slot == expected_jyutping, (
                f"Slot 1 (Jyutping): expected {expected_jyutping!r}, "
                f"got {jyutping_slot!r} for entry '{english_slot}'"
            )
            assert cantonese_slot == expected_cantonese, (
                f"Slot 2 (Cantonese): expected {expected_cantonese!r}, "
                f"got {cantonese_slot!r} for entry '{english_slot}'"
            )


# ---------------------------------------------------------------------------
# Helper: build a synthetic .apkg with a media manifest
# ---------------------------------------------------------------------------

def _make_synthetic_apkg_with_media(
    dest_path: Path,
    note_flds: list[str],
    note_mid: int,
    media_manifest: dict,
    audio_bytes: bytes = b"RIFF\x00\x00\x00\x00WAVEfmt ",
) -> None:
    """
    Write a minimal synthetic .apkg to dest_path.

    The archive contains:
      - collection.anki2  (SQLite with one note)
      - media             (JSON manifest, e.g. {"0": "hello_001.wav"})
      - one audio file stored under its numeric archive key (e.g. "0")

    Parameters
    ----------
    dest_path:       Where to write the .apkg file.
    note_flds:       Field values for the single note (list of str).
    note_mid:        Model ID to store in the notes table.
    media_manifest:  Dict mapping archive key → filename, e.g. {"0": "hello_001.wav"}.
    audio_bytes:     Raw bytes to write for each audio file in the manifest.
    """
    import struct

    with tempfile.TemporaryDirectory() as build_tmp:
        build_dir = Path(build_tmp)

        # --- SQLite database ---
        db_path = build_dir / "collection.anki2"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE notes "
            "(id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER, "
            "flds TEXT, tags TEXT, sfld TEXT)"
        )
        conn.execute(
            "INSERT INTO notes (id, guid, mid, flds, tags, sfld) VALUES (?,?,?,?,?,?)",
            (1, "synth_guid_001", note_mid, "\x1f".join(note_flds), "", note_flds[0]),
        )
        conn.commit()
        conn.close()

        # --- media manifest ---
        media_json_path = build_dir / "media"
        media_json_path.write_text(
            json.dumps(media_manifest), encoding="utf-8"
        )

        # --- audio files stored under their numeric archive keys ---
        for archive_key in media_manifest:
            (build_dir / archive_key).write_bytes(audio_bytes)

        # --- zip everything into the .apkg ---
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(dest_path), "w") as zf:
            zf.write(str(db_path), "collection.anki2")
            zf.write(str(media_json_path), "media")
            for archive_key in media_manifest:
                zf.write(str(build_dir / archive_key), archive_key)


# ---------------------------------------------------------------------------
# Integration test 4.6 — backfill produces correct media manifest
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_backfill_media_manifest_contains_named_wav():
    """
    End-to-end test: build a synthetic .apkg with one note whose audio field
    is [sound:hello_001.wav] and a media manifest {"0": "hello_001.wav"}.
    Run convert_apkg() on it, unpack the output .apkg, read the 'media' JSON
    file, and assert that "hello_001.wav" appears as a value (not "0").

    The Anki media manifest maps numeric string keys to filenames:
      {"0": "hello_001.wav"}
    After the fix, the value must be the named .wav filename, not the numeric
    archive key.

    **Validates: Requirements 2.3, 2.4**
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src_apkg = tmp_dir / "source.apkg"
        dest_apkg = tmp_dir / "output.apkg"
        unpack_dir = tmp_dir / "unpacked"
        unpack_dir.mkdir()

        # Build the synthetic source .apkg:
        #   - one 5-field note: [English, Cantonese, Jyutping, Audio, Tags]
        #   - audio field: [sound:hello_001.wav]
        #   - media manifest: {"0": "hello_001.wav"}  (archive key "0" → filename)
        _make_synthetic_apkg_with_media(
            dest_path=src_apkg,
            note_flds=["hello", "你好", "nei5 hou2", "[sound:hello_001.wav]", ""],
            note_mid=1607392321,
            media_manifest={"0": "hello_001.wav"},
        )
        assert src_apkg.exists(), "Synthetic source .apkg was not created"

        # Run the backfill conversion
        result = convert_apkg(src_apkg, dest_apkg, dry_run=False)
        assert result is True, f"convert_apkg() returned {result!r}, expected True"
        assert dest_apkg.exists(), f"Output .apkg not found at {dest_apkg}"

        # Unpack the output .apkg
        with zipfile.ZipFile(str(dest_apkg), "r") as zf:
            zf.extractall(str(unpack_dir))

        # Read the media manifest from the unpacked output
        media_json_path = unpack_dir / "media"
        assert media_json_path.exists(), (
            f"'media' file not found in unpacked output at {unpack_dir}"
        )
        with open(str(media_json_path), "r", encoding="utf-8") as f:
            media_manifest_out: dict = json.load(f)

        # The manifest maps numeric string keys → filenames.
        # Assert that "hello_001.wav" appears as a VALUE (not as a key or as "0").
        manifest_values = list(media_manifest_out.values())
        assert "hello_001.wav" in manifest_values, (
            f"Expected 'hello_001.wav' to appear as a value in the output media "
            f"manifest, but got: {media_manifest_out!r}. "
            f"The manifest should contain the named .wav filename, not the numeric "
            f"archive key '0'."
        )

        # Also assert the numeric key "0" is NOT a value (it should be a key)
        assert "0" not in manifest_values, (
            f"The numeric archive key '0' must not appear as a value in the media "
            f"manifest. Got manifest: {media_manifest_out!r}"
        )


# ---------------------------------------------------------------------------
# Integration test 4.7 — backfill preserves mid=1607392322 notes
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_backfill_preserves_mid_1607392322():
    """
    End-to-end test: build a synthetic .apkg whose notes have mid=1607392322
    (4-field bidirectional layout: English, Cantonese, Audio, Tags), run
    convert_apkg() on it, unpack the output, and assert that every note in
    collection.anki2 still has mid=1607392322 (not mid=1607392321).

    This verifies that already-correct 4-field bidirectional notes are NOT
    reassigned to the 5-field model ID during backfill.

    **Validates: Requirements 3.2**
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src_apkg = tmp_dir / "source_4field.apkg"
        dest_apkg = tmp_dir / "output_4field.apkg"
        unpack_dir = tmp_dir / "unpacked"
        unpack_dir.mkdir()

        # Build a synthetic source .apkg with mid=1607392322 (4-field layout).
        # Fields: English, Cantonese, Audio, Tags  (no Jyutping slot)
        _make_synthetic_apkg_with_media(
            dest_path=src_apkg,
            note_flds=["hello", "你好", "[sound:hello_001.wav]", ""],
            note_mid=1607392322,
            media_manifest={"0": "hello_001.wav"},
        )
        assert src_apkg.exists(), "Synthetic source .apkg was not created"

        # Run the backfill conversion
        result = convert_apkg(src_apkg, dest_apkg, dry_run=False)
        assert result is True, f"convert_apkg() returned {result!r}, expected True"
        assert dest_apkg.exists(), f"Output .apkg not found at {dest_apkg}"

        # Unpack the output .apkg
        with zipfile.ZipFile(str(dest_apkg), "r") as zf:
            zf.extractall(str(unpack_dir))

        # Open collection.anki2 and check every note's mid
        db_path = unpack_dir / "collection.anki2"
        assert db_path.exists(), (
            f"collection.anki2 not found in unpacked output at {unpack_dir}"
        )
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT mid FROM notes").fetchall()
        conn.close()

        assert len(rows) > 0, "No notes found in the output collection.anki2"

        for (mid,) in rows:
            assert mid == 1607392322, (
                f"Expected every note to have mid=1607392322 (MODEL_ID_NO_JYUTPING), "
                f"but got mid={mid}. The backfill incorrectly reassigned the model ID."
            )
