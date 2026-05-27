# Bugfix Requirements Document

## Introduction

Four related bugs in the Cantonese Anki flashcard generator cause field misalignment, model ID conflicts, and broken audio manifests when creating or backfilling bidirectional card packages. Together they result in cards that display Jyutping where Chinese characters should appear, duplicate note types in Anki on re-import, and audio files that exist in the archive but cannot be found by Anki at review time.

The desired canonical field order for every note is:
1. English meaning
2. Jyutping (romanization)
3. Chinese characters (may be empty)
4. Audio

All cards must be bidirectional (English→Cantonese and Cantonese→English).

---

## Bug Analysis

### Current Behavior (Defect)

**Bug 1 — Cantonese field stores Jyutping instead of Chinese characters**

1.1 WHEN a note is written to an .apkg by `package_generator.py` THEN the system places Jyutping romanization (e.g. `laam2`) in field slot 1 (Cantonese) and leaves field slot 2 (Jyutping) empty, swapping the two values intermittently across decks

**Bug 2 — Multiple conflicting model IDs for the same note type**

1.2 WHEN `package_generator.py` creates a new 5-field note THEN the system assigns model ID `1607392320`, which is distinct from the intended bidirectional model ID `1607392321` defined in `templates.py`

1.3 WHEN the backfill script processes a note whose `mid` is `1607392320` THEN the system reassigns it to model ID `1607392321`, creating a second note type in Anki's collection and causing field slot mismatches on re-import

**Bug 3 — Backfill script corrupts the media manifest**

1.4 WHEN `build_bidirectional_package()` collects audio files THEN the system appends the numeric archive key path (e.g. `tmp/0`) to `media_files` instead of the named `.wav` file path, causing genanki to write `{"0": "0", "1": "1", …}` in the media manifest instead of `{"0": "filename.wav", "1": "filename2.wav", …}`

1.5 WHEN Anki imports a backfilled package with a corrupted media manifest THEN the system cannot locate audio files by name, so no audio plays during card review even though the files are present in the archive

**Bug 4 — Backfill unnecessarily changes model ID on 5-field notes**

1.6 WHEN the backfill script processes a note with `mid=1607392320` THEN the system re-emits it under `mid=1607392321`, so if Anki already has `1607392320` in its collection the re-imported notes create a duplicate note type with identical field names but a different ID, causing cards to render with wrong field mappings

---

### Expected Behavior (Correct)

**Bug 1 — Field slot assignment**

2.1 WHEN `package_generator.py` creates a 5-field note THEN the system SHALL place the English meaning in slot 0, Jyutping romanization in slot 1, Chinese characters in slot 2, the audio reference in slot 3, and tags in slot 4 — consistently across all generated decks

**Bug 2 — Consistent model ID from package generator**

2.2 WHEN `package_generator.py` creates a new 5-field note THEN the system SHALL assign model ID `1607392321` (matching `CantoneseCardTemplate.MODEL_ID`) so that notes produced by the generator and notes produced by the backfill script share a single note type

**Bug 3 — Correct media manifest**

2.3 WHEN `build_bidirectional_package()` collects audio files for a note THEN the system SHALL resolve the archive key to the actual named `.wav` file path (e.g. `tmp_dir / filename`) and append that path to `media_files`, so genanki writes `{"0": "filename.wav", …}` in the manifest

2.4 WHEN Anki imports a backfilled package THEN the system SHALL play the correct audio clip for each card because the manifest maps archive indices to the original named filenames

**Bug 4 — Backfill preserves model ID for already-correct notes**

2.5 WHEN the backfill script processes a note whose `mid` is already `1607392321` THEN the system SHALL emit the note under the same model ID without reassignment, preventing duplicate note types in Anki

2.6 WHEN the backfill script processes a note whose `mid` is `1607392320` THEN the system SHALL treat it as a 5-field note and emit it under `1607392321` only if `1607392320` is confirmed to be a transitional ID that was never imported into any live Anki collection; otherwise the system SHALL preserve the original ID

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a note has `mid=1607392319` (legacy 4-field: English, Cantonese, Audio, Tags) THEN the system SHALL CONTINUE TO convert it using `create_model_no_jyutping()` (model ID `1607392322`) with the 4-field layout

3.2 WHEN a note has `mid=1607392322` (already a bidirectional 4-field note) THEN the system SHALL CONTINUE TO leave its model ID and field layout unchanged

3.3 WHEN `package_generator.py` generates a deck from a vocabulary list where all entries have both Chinese characters and Jyutping THEN the system SHALL CONTINUE TO produce a valid `.apkg` with the correct number of notes and embedded audio files

3.4 WHEN the backfill script runs with `--dry-run` THEN the system SHALL CONTINUE TO log what would be done without writing any output files

3.5 WHEN the backfill script processes a package whose audio files are all present in the archive THEN the system SHALL CONTINUE TO include every audio file in the output package with no files silently dropped

3.6 WHEN a note's English or Cantonese field is empty THEN the system SHALL CONTINUE TO skip that note and log a warning, as it does today

3.7 WHEN the backfill script derives a deck ID from the deck name THEN the system SHALL CONTINUE TO produce a stable, deterministic ID so that re-imports merge into the existing deck rather than creating duplicates
