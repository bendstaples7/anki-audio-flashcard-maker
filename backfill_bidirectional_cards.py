#!/usr/bin/env python3
"""
Backfill script: convert all existing one-sided .apkg files to bidirectional.

For every .apkg in the output/ directory this script:
  1. Unpacks the archive (it's a zip containing collection.anki2 + media files)
  2. Reads every note from the SQLite database
  3. Re-creates the note using the new bidirectional model (MODEL_ID 1607392321)
  4. Writes a new .apkg alongside the original with a "_bidirectional" suffix

The original files are NOT modified or deleted.

Usage:
    python backfill_bidirectional_cards.py
    python backfill_bidirectional_cards.py --output-dir output/backfilled
    python backfill_bidirectional_cards.py --dry-run
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

import genanki

# ---------------------------------------------------------------------------
# Make sure the package is importable when run from the project root
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from cantonese_anki_generator.anki.templates import CantoneseCardTemplate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Original model IDs used by the tool before bidirectional support
LEGACY_MODEL_ID = 1607392319   # 4 fields: English, Cantonese, Audio, Tags
JYUTPING_MODEL_ID = 1607392320  # 5 fields: English, Cantonese, Jyutping, Audio, Tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def unpack_apkg(apkg_path: Path, dest_dir: Path) -> None:
    """Extract an .apkg (zip) into dest_dir."""
    with zipfile.ZipFile(apkg_path, "r") as zf:
        zf.extractall(dest_dir)


def read_notes_from_db(db_path: Path) -> tuple[list[dict], int]:
    """
    Read all notes from an Anki SQLite collection.

    Returns a tuple of:
      - list of dicts with keys: id, guid, mid, flds (list), tags, sfld
      - the original model ID (mid) used by the notes
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT id, guid, mid, flds, tags, sfld FROM notes"
        )
        notes = []
        model_ids = set()
        for row in cursor:
            note_id, guid, mid, flds_raw, tags, sfld = row
            model_ids.add(mid)
            notes.append(
                {
                    "id": note_id,
                    "guid": guid,
                    "mid": mid,
                    "flds": flds_raw.split("\x1f"),  # Anki field separator
                    "tags": tags.strip(),
                    "sfld": sfld,
                }
            )
        original_mid = model_ids.pop() if model_ids else 0
        return notes, original_mid
    finally:
        conn.close()


def read_media_map(media_path: Path) -> dict[str, str]:
    """
    Read the media manifest from an unpacked .apkg.

    The 'media' file is a JSON object mapping numeric string keys to filenames,
    e.g. {"0": "hello_001.wav", "1": "world_002.wav"}.
    Returns a dict mapping filename → archive key (for locating the actual file).
    """
    if not media_path.exists():
        return {}
    with open(media_path, "r", encoding="utf-8") as f:
        raw: dict = json.load(f)
    # Invert: filename → key so we can find the file by name
    return {v: k for k, v in raw.items()}


def build_bidirectional_package(
    notes: list[dict],
    media_dir: Path,
    media_map: dict[str, str],
    deck_name: str,
    original_mid: int,
) -> genanki.Package:
    """
    Build a new genanki Package with the bidirectional model.

    Selects the correct model based on the original model ID:
    - LEGACY_MODEL_ID (1607392319): 4-field notes → use create_model_no_jyutping()
    - JYUTPING_MODEL_ID (1607392320): 5-field notes → use create_model()
    """
    if original_mid == LEGACY_MODEL_ID:
        model = CantoneseCardTemplate.create_model_no_jyutping()
        num_fields = 4
        logger.info(f"  Using legacy 4-field bidirectional model (original mid={original_mid})")
    else:
        model = CantoneseCardTemplate.create_model()
        num_fields = 5
        logger.info(f"  Using 5-field bidirectional model (original mid={original_mid})")

    # Use a stable deck ID derived from the deck name so re-imports merge
    # into the same deck rather than creating duplicates.
    import hashlib
    deck_id = int(hashlib.md5(deck_name.encode()).hexdigest()[:8], 16) % 2_147_483_647
    deck = genanki.Deck(deck_id, deck_name)

    media_files: list[str] = []
    skipped = 0

    for raw_note in notes:
        flds = raw_note["flds"]

        # Pad with empty strings if somehow fewer fields exist.
        while len(flds) < num_fields:
            flds.append("")

        flds = flds[:num_fields]

        english = flds[0]
        cantonese = flds[1]

        if not english.strip() or not cantonese.strip():
            logger.warning(f"Skipping note with empty English or Cantonese: {flds}")
            skipped += 1
            continue

        note = genanki.Note(
            model=model,
            fields=flds,
            # Preserve the original GUID so Anki recognises these as the same
            # notes and updates them in-place rather than creating duplicates.
            guid=raw_note["guid"],
        )
        deck.add_note(note)

        # Collect the actual audio file — it's in the last field before Tags
        # For 4-field: flds[2] is Audio. For 5-field: flds[3] is Audio.
        audio_field = flds[2] if num_fields == 4 else flds[3]
        if audio_field.startswith("[sound:") and audio_field.endswith("]"):
            filename = audio_field[7:-1]
            archive_key = media_map.get(filename)
            if archive_key is not None:
                file_path = media_dir / archive_key
                if file_path.exists():
                    media_files.append(str(file_path))
                else:
                    logger.warning(f"Media file not found in archive: {file_path}")
            else:
                logger.warning(f"No archive key for media file: {filename}")

    if skipped:
        logger.warning(f"Skipped {skipped} notes with missing fields.")

    package = genanki.Package(deck)
    package.media_files = media_files
    return package


def convert_apkg(
    src: Path,
    dest: Path,
    dry_run: bool = False,
) -> bool:
    """
    Convert a single .apkg to bidirectional and write to dest.

    Returns True on success.
    """
    logger.info(f"Processing: {src.name}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        try:
            unpack_apkg(src, tmp_dir)
        except Exception as e:
            logger.error(f"  Failed to unpack {src.name}: {e}")
            return False

        db_path = tmp_dir / "collection.anki2"
        if not db_path.exists():
            logger.error(f"  No collection.anki2 found in {src.name}")
            return False

        try:
            notes, original_mid = read_notes_from_db(db_path)
        except Exception as e:
            logger.error(f"  Failed to read notes from {src.name}: {e}")
            return False

        media_map = read_media_map(tmp_dir / "media")

        # Derive a clean deck name from the filename
        deck_name = src.stem.replace("_", " ").replace("-", " ").title()

        logger.info(f"  Found {len(notes)} notes (model {original_mid}) → building bidirectional package")

        if dry_run:
            logger.info(f"  [dry-run] Would write: {dest}")
            return True

        try:
            package = build_bidirectional_package(notes, tmp_dir, media_map, deck_name, original_mid)
            dest.parent.mkdir(parents=True, exist_ok=True)
            package.write_to_file(str(dest))
            size_kb = dest.stat().st_size // 1024
            logger.info(f"  ✓ Written: {dest.name} ({size_kb} KB)")
            return True
        except Exception as e:
            logger.error(f"  Failed to write {dest}: {e}")
            return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill existing .apkg files with bidirectional card templates."
    )
    parser.add_argument(
        "--input-dir",
        default="output",
        help="Directory containing the original .apkg files (default: output/)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory to write converted files. "
            "Defaults to the same directory as the input files, "
            "with '_bidirectional' appended to each filename."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing any files.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    apkg_files = sorted(input_dir.glob("*.apkg"))
    if not apkg_files:
        logger.warning(f"No .apkg files found in {input_dir}")
        sys.exit(0)

    logger.info(f"Found {len(apkg_files)} .apkg file(s) to convert")

    success_count = 0
    fail_count = 0

    for src in apkg_files:
        # Skip files that are already bidirectional backfills
        if src.stem.endswith("_bidirectional"):
            logger.info(f"Skipping already-converted file: {src.name}")
            continue

        if args.output_dir:
            dest = Path(args.output_dir) / f"{src.stem}_bidirectional.apkg"
        else:
            dest = src.parent / f"{src.stem}_bidirectional.apkg"

        ok = convert_apkg(src, dest, dry_run=args.dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    logger.info(
        f"\nDone. {success_count} converted, {fail_count} failed."
        + (" (dry-run)" if args.dry_run else "")
    )

    if fail_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
