# Anki Card Field Alignment Bugfix Design

## Overview

Four related bugs in the Cantonese Anki flashcard generator cause field misalignment, model ID
conflicts, and broken audio manifests. This design formalises the bug conditions, defines the
expected correct behaviour, hypothesises root causes, and outlines the targeted fixes and testing
strategy.

The bugs affect two files:

- `cantonese_anki_generator/anki/package_generator.py` — field ordering and model ID (Bugs 1 & 2)
- `backfill_bidirectional_cards.py` — media manifest construction and model ID selection (Bugs 3 & 4)

The fix strategy is minimal: change only the lines that are wrong, leave everything else untouched.

---

## Glossary

- **Bug_Condition (C)**: The condition that identifies an input that triggers one of the four bugs.
- **Property (P)**: The desired correct behaviour when the bug condition holds.
- **Preservation**: Existing behaviours that must remain unchanged after the fix.
- **`_create_anki_card()`**: The method in `package_generator.py` that builds a `genanki.Note` from an `AlignedPair`.
- **`build_bidirectional_package()`**: The function in `backfill_bidirectional_cards.py` that converts unpacked notes into a new `genanki.Package`.
- **`original_mid`**: The model ID read from the source `.apkg` SQLite database; used to select the output model.
- **`archive_key`**: The numeric string key (e.g. `"0"`, `"1"`) used inside the `.apkg` zip to store a media file.
- **`filename`**: The human-readable `.wav` name stored in the media manifest (e.g. `hello_001.wav`).
- **`LEGACY_MODEL_ID`**: `1607392319` — original 4-field model (English, Cantonese, Audio, Tags).
- **`JYUTPING_MODEL_ID`**: `1607392320` — transitional 5-field model, never widely distributed.
- **`MODEL_ID`**: `1607392321` — current canonical 5-field bidirectional model.
- **`MODEL_ID_NO_JYUTPING`**: `1607392322` — current canonical 4-field bidirectional model.

---

## Bug Details

### Bug 1 — Field Slot Misassignment in `_create_anki_card()`

The `genanki.Note` is constructed with the field list:

```python
fields=[
    fields['English'],
    fields['Cantonese'],
    fields['Jyutping'],
    fields['Audio'],
    fields['Tags']
]
```

The model definition in `create_model()` declares slots in the order:
`English (0), Cantonese (1), Jyutping (2), Audio (3), Tags (4)`.

The `CardFormatter.format_card_fields()` method populates a dict keyed by name, so the field
values are correct in isolation. However, the bugfix.md requirements document specifies the
canonical slot order as:

```
Slot 0: English
Slot 1: Cantonese (Chinese characters)
Slot 2: Jyutping
Slot 3: Audio
Slot 4: Tags
```

The current code matches this order, but the requirements document (section 2.1) states the
intended order is `English, Jyutping, Chinese characters, Audio` — meaning Jyutping should be
slot 1 and Cantonese slot 2. The model template and the field list must be brought into
agreement with the canonical order declared in the requirements.

**Formal Specification:**

```
FUNCTION isBugCondition_1(note)
  INPUT: note of type genanki.Note
  OUTPUT: boolean

  RETURN note.fields[1] contains romanisation (Jyutping)
         AND note.fields[2] contains Chinese characters (Cantonese)
         -- i.e. slots 1 and 2 are swapped relative to the canonical order
END FUNCTION
```

**Examples:**

- Vocabulary entry `{english: "blue", cantonese: "藍", jyutping: "laam2"}` → current code
  produces `fields[1]="藍"`, `fields[2]="laam2"`. Expected: `fields[1]="laam2"`, `fields[2]="藍"`.
- Vocabulary entry `{english: "eat", cantonese: "食", jyutping: "sik6"}` → current code
  produces `fields[1]="食"`, `fields[2]="sik6"`. Expected: `fields[1]="sik6"`, `fields[2]="食"`.
- Vocabulary entry with empty Jyutping `{english: "yes", cantonese: "係", jyutping: ""}` →
  current code produces `fields[2]=""`. Expected: `fields[1]=""`, `fields[2]="係"`.

---

### Bug 2 — Wrong Model ID in `package_generator.py`

`AnkiPackageGenerator.__init__` calls `CantoneseCardTemplate.create_model()`, which correctly
uses `MODEL_ID = 1607392321`. The `genanki.Note` is then created with `model=self.model`, so
the note inherits `mid=1607392321`. This appears correct in the current source.

However, the requirements document (section 1.2) states the system was assigning `1607392320`.
The design must verify that `self.model.mid` is always `CantoneseCardTemplate.MODEL_ID`
(`1607392321`) and add an explicit assertion / constant reference to prevent regression.

**Formal Specification:**

```
FUNCTION isBugCondition_2(note)
  INPUT: note of type genanki.Note
  OUTPUT: boolean

  RETURN note.model.mid != CantoneseCardTemplate.MODEL_ID  -- i.e. != 1607392321
END FUNCTION
```

**Examples:**

- A note created by `_create_anki_card()` must have `note.model.mid == 1607392321`.
- If `create_model()` were accidentally replaced with a hardcoded `model_id=1607392320`, the
  bug would reappear; the fix pins the reference to `CantoneseCardTemplate.MODEL_ID`.

---

### Bug 3 — Numeric Archive Key Path in Media Manifest

In `build_bidirectional_package()`, after resolving `archive_key = media_map.get(filename)`,
the code appends:

```python
media_files.append(str(file_path))   # file_path = media_dir / archive_key  e.g. "tmp/0"
```

`genanki` uses the basename of each path in `media_files` as the manifest value. So the
manifest becomes `{"0": "0", "1": "1", …}` instead of `{"0": "hello_001.wav", …}`. Anki
cannot locate audio files by name at review time.

**Formal Specification:**

```
FUNCTION isBugCondition_3(media_files_entry, expected_filename)
  INPUT: media_files_entry of type str (a path appended to package.media_files)
         expected_filename of type str (the .wav name from the [sound:…] field)
  OUTPUT: boolean

  RETURN Path(media_files_entry).name != expected_filename
         -- i.e. the basename is a numeric key, not the .wav filename
END FUNCTION
```

**Examples:**

- Archive contains key `"0"` → file `tmp/0`. Filename from note field: `hello_001.wav`.
  Current code appends `"tmp/0"` → manifest entry `{"0": "0"}`. Anki cannot find `hello_001.wav`.
  Expected: copy `tmp/0` → `tmp/hello_001.wav`, append `"tmp/hello_001.wav"` → manifest
  entry `{"0": "hello_001.wav"}`.
- Archive key `"3"`, filename `world_004.wav` → same pattern; copy and rename before appending.

---

### Bug 4 — Unnecessary Model ID Reassignment for `JYUTPING_MODEL_ID` Notes

`build_bidirectional_package()` selects the model with:

```python
if original_mid == LEGACY_MODEL_ID:   # 1607392319
    model = CantoneseCardTemplate.create_model_no_jyutping()
else:
    model = CantoneseCardTemplate.create_model()   # mid=1607392321
```

Notes with `mid=1607392320` (`JYUTPING_MODEL_ID`) fall into the `else` branch and are
re-emitted under `mid=1607392321`. If any live Anki collection already contains notes with
`mid=1607392320`, the re-import creates a second note type with the same field names but a
different ID, causing field mapping errors.

**Formal Specification:**

```
FUNCTION isBugCondition_4(original_mid, output_model_mid)
  INPUT: original_mid of type int (mid read from source .apkg)
         output_model_mid of type int (mid of the model assigned to the output note)
  OUTPUT: boolean

  RETURN original_mid == JYUTPING_MODEL_ID   -- 1607392320
         AND output_model_mid == MODEL_ID     -- 1607392321
         -- i.e. a transitional-ID note is unnecessarily reassigned
END FUNCTION
```

**Examples:**

- `original_mid=1607392320` → current code assigns `mid=1607392321`. Bug: creates duplicate
  note type if `1607392320` exists in the collection.
- `original_mid=1607392321` → current code assigns `mid=1607392321`. Correct (no change).
- `original_mid=1607392319` → current code assigns `mid=1607392322`. Correct (legacy path).
- `original_mid=1607392322` → current code assigns `mid=1607392321`. Bug: should leave as
  `1607392322` (already a bidirectional 4-field note).

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- Notes with `mid=1607392319` (legacy 4-field) MUST continue to be converted using
  `create_model_no_jyutping()` (output `mid=1607392322`).
- Notes with `mid=1607392322` (already bidirectional 4-field) MUST be left with their model
  ID unchanged.
- `package_generator.py` MUST continue to produce a valid `.apkg` with the correct number of
  notes and embedded audio files for any vocabulary list.
- The `--dry-run` flag MUST continue to log actions without writing any output files.
- All audio files present in the source archive MUST continue to appear in the output package
  with no files silently dropped.
- Notes with an empty English or Cantonese field MUST continue to be skipped with a warning.
- The deck ID derivation from deck name MUST remain stable and deterministic so re-imports
  merge into the existing deck.

**Scope:**

All inputs that do NOT trigger one of the four bug conditions are completely unaffected by
these fixes. This includes:

- Mouse/UI interactions with Anki (unrelated to generation).
- Notes with `mid=1607392319` or `mid=1607392322` (handled by unchanged code paths).
- Vocabulary entries where both Chinese characters and Jyutping are present and correctly
  ordered (the fix only reorders the field list construction).
- The `--dry-run` path (no file I/O is changed).

---

## Hypothesized Root Cause

### Bug 1 — Field Slot Misassignment

The requirements document specifies a canonical field order that differs from the order in
which `CardFormatter.format_card_fields()` returns values and the order in which
`_create_anki_card()` assembles the list. The model template in `create_model()` and the
field list in `_create_anki_card()` must both be updated to match the canonical order:
`[English, Jyutping, Cantonese, Audio, Tags]`.

### Bug 2 — Wrong Model ID

The most likely historical cause is that `create_model()` was at some point called with a
hardcoded `model_id=1607392320` rather than referencing `CantoneseCardTemplate.MODEL_ID`. The
current source already uses the class constant, but the fix should add an explicit guard
(assertion or constant reference in `_create_anki_card`) to prevent silent regression.

### Bug 3 — Numeric Archive Key in Media Manifest

`genanki` derives the manifest filename from `Path(path).name`. When the path is
`tmp_dir / archive_key` (e.g. `tmp/0`), the name is `"0"` — a numeric string — not the
original `.wav` filename. The fix is to copy the file from `media_dir / archive_key` to
`media_dir / filename` before appending, so `Path(path).name == filename`.

### Bug 4 — Unnecessary Reassignment of `JYUTPING_MODEL_ID`

The `else` branch in `build_bidirectional_package()` was written to handle only the
`JYUTPING_MODEL_ID → MODEL_ID` transition, but it also inadvertently catches
`mid=1607392322` (already-correct 4-field bidirectional notes). The fix is to enumerate all
known model IDs explicitly rather than using a catch-all `else`.

---

## Correctness Properties

Property 1: Bug Condition — Canonical Field Slot Order

_For any_ `AlignedPair` where the vocabulary entry has non-empty English, Cantonese, and
Jyutping values, the fixed `_create_anki_card()` SHALL produce a `genanki.Note` where
`fields[0]` is the English meaning, `fields[1]` is the Jyutping romanisation, `fields[2]` is
the Cantonese Chinese characters, `fields[3]` is the audio reference (`[sound:…]`), and
`fields[4]` is the tags string.

**Validates: Requirements 2.1**

Property 2: Bug Condition — Consistent Model ID from Package Generator

_For any_ `AlignedPair` processed by `_create_anki_card()`, the fixed method SHALL produce a
`genanki.Note` whose `model.mid` equals `CantoneseCardTemplate.MODEL_ID` (`1607392321`),
regardless of how the model object was constructed.

**Validates: Requirements 2.2**

Property 3: Bug Condition — Named Media File Paths in Manifest

_For any_ note in `build_bidirectional_package()` whose audio field contains `[sound:F]` and
whose archive key `K` maps to a file that exists at `media_dir / K`, the fixed function SHALL
append a path whose `Path(...).name == F` to `media_files`, so that genanki writes
`{...: "F"}` in the manifest.

**Validates: Requirements 2.3, 2.4**

Property 4: Bug Condition — Correct Model Selection for All Known Model IDs

_For any_ `original_mid` value in `{1607392319, 1607392320, 1607392321, 1607392322}`, the
fixed `build_bidirectional_package()` SHALL select the model according to the canonical
mapping:

- `1607392319` → `create_model_no_jyutping()` (output `mid=1607392322`)
- `1607392320` → `create_model()` (output `mid=1607392321`)
- `1607392321` → `create_model()` (output `mid=1607392321`, unchanged)
- `1607392322` → `create_model_no_jyutping()` (output `mid=1607392322`, unchanged)

**Validates: Requirements 2.5, 2.6**

Property 5: Preservation — Legacy and Already-Correct Notes Unaffected

_For any_ input where `original_mid` is NOT one of the four bug-triggering values (i.e. any
mid outside `{1607392319, 1607392320, 1607392321, 1607392322}`), the fixed
`build_bidirectional_package()` SHALL behave identically to the original function, and for
`mid=1607392319` and `mid=1607392322` the output SHALL be identical to the original function
(these paths are unchanged).

**Validates: Requirements 3.1, 3.2**

Property 6: Preservation — All Audio Files Included

_For any_ set of notes where every audio field resolves to a file present in `media_dir`, the
fixed `build_bidirectional_package()` SHALL include every such file in `package.media_files`
with no files silently dropped.

**Validates: Requirements 3.5**

Property 7: Preservation — Stable Deck ID

_For any_ deck name string, calling the deck ID derivation function twice SHALL produce the
same integer both times (deterministic, no timestamp component).

**Validates: Requirements 3.7**

---

## Fix Implementation

### Changes Required

#### File: `cantonese_anki_generator/anki/package_generator.py`

**Function: `_create_anki_card()`**

**Change 1 — Reorder the field list to match the canonical slot order:**

The `genanki.Note` fields list must be reordered from
`[English, Cantonese, Jyutping, Audio, Tags]` to `[English, Jyutping, Cantonese, Audio, Tags]`
to match the canonical order declared in the requirements (slot 1 = Jyutping, slot 2 = Cantonese).

```python
# Before
note = genanki.Note(
    model=self.model,
    fields=[
        fields['English'],
        fields['Cantonese'],
        fields['Jyutping'],
        fields['Audio'],
        fields['Tags']
    ]
)

# After
note = genanki.Note(
    model=self.model,
    fields=[
        fields['English'],
        fields['Jyutping'],    # slot 1: romanisation
        fields['Cantonese'],   # slot 2: Chinese characters
        fields['Audio'],
        fields['Tags']
    ]
)
```

**Change 2 — Update `create_model()` field declaration to match the new slot order:**

The `genanki.Model` fields list in `CantoneseCardTemplate.create_model()` must be reordered
to `[English, Jyutping, Cantonese, Audio, Tags]` so that the model definition and the note
field list are consistent.

**Change 3 — Pin model ID reference in `_create_anki_card()`:**

Add an assertion after note creation to guard against regression:

```python
assert note.model.mid == CantoneseCardTemplate.MODEL_ID, (
    f"Model ID mismatch: expected {CantoneseCardTemplate.MODEL_ID}, "
    f"got {note.model.mid}"
)
```

---

#### File: `backfill_bidirectional_cards.py`

**Function: `build_bidirectional_package()`**

**Change 4 — Copy media file to named path before appending:**

Replace the current append:

```python
# Before
file_path = media_dir / archive_key
if file_path.exists():
    media_files.append(str(file_path))

# After
file_path = media_dir / archive_key
if file_path.exists():
    named_path = media_dir / filename
    if not named_path.exists():
        shutil.copy2(file_path, named_path)
    media_files.append(str(named_path))
```

This ensures `Path(entry).name == filename` for every entry in `media_files`, so genanki
writes the correct manifest.

**Change 5 — Enumerate all known model IDs explicitly:**

Replace the two-branch `if/else` with an explicit four-way mapping:

```python
# Before
if original_mid == LEGACY_MODEL_ID:
    model = CantoneseCardTemplate.create_model_no_jyutping()
    num_fields = 4
else:
    model = CantoneseCardTemplate.create_model()
    num_fields = 5

# After
FOUR_FIELD_MIDS = {LEGACY_MODEL_ID, CantoneseCardTemplate.MODEL_ID_NO_JYUTPING}
FIVE_FIELD_MIDS = {JYUTPING_MODEL_ID, CantoneseCardTemplate.MODEL_ID}

if original_mid in FOUR_FIELD_MIDS:
    model = CantoneseCardTemplate.create_model_no_jyutping()
    num_fields = 4
    logger.info(f"  Using legacy 4-field bidirectional model (original mid={original_mid})")
elif original_mid in FIVE_FIELD_MIDS:
    model = CantoneseCardTemplate.create_model()
    num_fields = 5
    logger.info(f"  Using 5-field bidirectional model (original mid={original_mid})")
else:
    logger.warning(f"  Unknown model ID {original_mid}; defaulting to 5-field model")
    model = CantoneseCardTemplate.create_model()
    num_fields = 5
```

Also add `import shutil` at the top of `backfill_bidirectional_cards.py` if not already present.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate each bug on the unfixed code, then verify the fix works correctly and preserves
existing behaviour.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix.
Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that construct notes or call `build_bidirectional_package()` with
controlled inputs and assert the expected invariants. Run these tests on the UNFIXED code to
observe failures and understand the root cause.

**Test Cases**:

1. **Field Order Test** (Bug 1): Create an `AlignedPair` with distinct English, Cantonese, and
   Jyutping values; call `_create_anki_card()`; assert `note.fields[1]` is Jyutping and
   `note.fields[2]` is Cantonese. Will fail on unfixed code if slots are swapped.

2. **Model ID Test** (Bug 2): Call `_create_anki_card()` and assert
   `note.model.mid == 1607392321`. Will fail on unfixed code if the wrong ID is used.

3. **Media Manifest Test** (Bug 3): Create a temp directory with a file named `"0"` (the
   archive key); call `build_bidirectional_package()` with a note whose audio field is
   `[sound:hello_001.wav]` and `media_map={"hello_001.wav": "0"}`; assert
   `Path(package.media_files[0]).name == "hello_001.wav"`. Will fail on unfixed code.

4. **Model Selection Test — JYUTPING_MODEL_ID** (Bug 4): Call
   `build_bidirectional_package()` with `original_mid=1607392320`; assert the package's
   model mid is `1607392321`. Will pass on unfixed code (this is the intended behaviour for
   this ID), confirming the fix does not break it.

5. **Model Selection Test — MODEL_ID_NO_JYUTPING** (Bug 4): Call
   `build_bidirectional_package()` with `original_mid=1607392322`; assert the package's
   model mid is `1607392322`. Will fail on unfixed code (currently falls into the `else`
   branch and gets `1607392321`).

**Expected Counterexamples**:

- Bug 1: `note.fields[1]` contains Chinese characters instead of Jyutping.
- Bug 3: `Path(media_files[0]).name` is `"0"` instead of `"hello_001.wav"`.
- Bug 4 (mid=1607392322): model mid is `1607392321` instead of `1607392322`.

---

### Fix Checking

**Goal**: Verify that for all inputs where each bug condition holds, the fixed function
produces the expected behaviour.

**Pseudocode:**

```
FOR ALL aligned_pair WHERE isBugCondition_1(note_from(aligned_pair)) DO
  note := _create_anki_card_fixed(aligned_pair)
  ASSERT note.fields[0] == aligned_pair.vocabulary_entry.english
  ASSERT note.fields[1] == aligned_pair.vocabulary_entry.jyutping
  ASSERT note.fields[2] == aligned_pair.vocabulary_entry.cantonese
  ASSERT note.fields[3].startswith("[sound:")
  ASSERT note.model.mid == CantoneseCardTemplate.MODEL_ID
END FOR

FOR ALL (notes, media_dir, media_map) WHERE isBugCondition_3(media_files_entry, filename) DO
  package := build_bidirectional_package_fixed(notes, media_dir, media_map, ...)
  FOR EACH entry IN package.media_files DO
    ASSERT Path(entry).name == expected_filename_for(entry)
  END FOR
END FOR

FOR ALL original_mid IN {1607392319, 1607392320, 1607392321, 1607392322} DO
  package := build_bidirectional_package_fixed(..., original_mid=original_mid)
  ASSERT package.deck.notes[0].model.mid == EXPECTED_MID[original_mid]
END FOR
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed functions
produce the same result as the original functions.

**Pseudocode:**

```
FOR ALL aligned_pair WHERE NOT isBugCondition_1(note_from(aligned_pair)) DO
  ASSERT _create_anki_card_original(aligned_pair) fields == _create_anki_card_fixed(aligned_pair) fields
END FOR

FOR ALL original_mid WHERE original_mid IN {1607392319, 1607392322} DO
  -- These paths are unchanged; assert model selection is identical
  ASSERT model_for_fixed(original_mid) == model_for_original(original_mid)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:

- It generates many test cases automatically across the input domain.
- It catches edge cases (empty Jyutping, very long field values, Unicode edge cases) that
  manual unit tests might miss.
- It provides strong guarantees that behaviour is unchanged for all non-buggy inputs.

**Test Plan**: Observe behaviour on UNFIXED code first for the unchanged paths (legacy
`mid=1607392319`, already-bidirectional `mid=1607392322`, dry-run, empty-field skipping),
then write property-based tests capturing that behaviour.

**Test Cases**:

1. **Legacy Model Preservation**: For `original_mid=1607392319`, verify the output model mid
   is `1607392322` both before and after the fix.
2. **Already-Bidirectional 4-Field Preservation**: For `original_mid=1607392322`, verify the
   output model mid is `1607392322` after the fix (was broken before).
3. **Dry-Run Preservation**: Verify no output file is written when `dry_run=True`.
4. **Empty Field Skipping Preservation**: Verify notes with empty English or Cantonese are
   skipped and a warning is logged.
5. **All Audio Files Included**: For any set of notes with valid audio fields and present
   archive files, verify all files appear in `media_files`.

---

### Unit Tests

- Test `_create_anki_card()` field order for entries with all five fields populated.
- Test `_create_anki_card()` field order for entries with empty Jyutping.
- Test `_create_anki_card()` model ID equals `CantoneseCardTemplate.MODEL_ID`.
- Test `build_bidirectional_package()` model selection for each of the four known model IDs.
- Test `build_bidirectional_package()` media file path naming (named `.wav`, not numeric key).
- Test `build_bidirectional_package()` skips notes with empty English or Cantonese fields.
- Test `convert_apkg()` with `dry_run=True` produces no output file.

### Property-Based Tests

- Generate arbitrary `AlignedPair` instances (random English, Cantonese, Jyutping strings)
  and verify the field slot invariant holds for every generated note (Property 1).
- Generate arbitrary model ID values and verify the model selection mapping is correct for
  all four known IDs and gracefully handles unknown IDs (Property 4).
- Generate arbitrary sets of notes with random audio filenames and verify all present audio
  files appear in `media_files` with correct basenames (Properties 3 & 6).
- Generate arbitrary deck name strings and verify the deck ID derivation is deterministic
  (Property 7).

### Integration Tests

- End-to-end: generate a `.apkg` from a small vocabulary list, unpack it, and verify the
  SQLite notes table has the correct field values in the correct slots.
- End-to-end: run `convert_apkg()` on a synthetic `.apkg` with known notes and media, then
  unpack the output and verify the media manifest maps to named `.wav` files.
- End-to-end: run `convert_apkg()` on a package with `mid=1607392322` notes and verify the
  output notes retain `mid=1607392322`.
