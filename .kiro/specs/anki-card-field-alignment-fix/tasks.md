# Implementation Plan

## Overview

Fix four related bugs in the Cantonese Anki flashcard generator affecting field slot ordering, model ID consistency, media manifest construction, and model selection logic. The workflow follows the exploratory bugfix methodology: write tests that expose each bug on unfixed code, capture counterexamples, implement the targeted fixes, then verify all tests pass.

## Tasks

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Field Slot Misassignment, Wrong Model ID, Corrupt Media Manifest, and Bad Model Selection
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behaviour — they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate each bug exists
  - **Scoped PBT Approach**: Scope each property to the concrete failing case(s) to ensure reproducibility

  **Bug 1 — Field Slot Misassignment (`_create_anki_card`)**
  - Create an `AlignedPair` with distinct English (`"blue"`), Cantonese (`"藍"`), and Jyutping (`"laam2"`) values
  - Call `_create_anki_card()` on the unfixed code
  - Assert `note.fields[0] == "blue"` (English in slot 0)
  - Assert `note.fields[1] == "laam2"` (Jyutping in slot 1) — **EXPECTED TO FAIL**: unfixed code puts `"藍"` here
  - Assert `note.fields[2] == "藍"` (Cantonese in slot 2) — **EXPECTED TO FAIL**: unfixed code puts `"laam2"` here
  - Assert `note.fields[3].startswith("[sound:")` (Audio in slot 3)
  - Document counterexample: `note.fields[1]="藍"`, `note.fields[2]="laam2"` (slots 1 and 2 are swapped)
  - Use `@given(st.text(min_size=1), st.text(min_size=1), st.text(min_size=1))` to generate arbitrary (english, cantonese, jyutping) triples
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves Bug 1 exists)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 2.1_

  **Bug 2 — Wrong Model ID (`_create_anki_card`)**
  - Call `_create_anki_card()` on any `AlignedPair`
  - Assert `note.model.mid == CantoneseCardTemplate.MODEL_ID` (i.e. `== 1607392321`)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test PASSES if current source already uses the constant (confirms no regression needed) or FAILS if a wrong ID is present — document the result either way
  - Mark task complete when test is written, run, and result is documented
  - _Requirements: 1.2, 1.3, 2.2_

  **Bug 3 — Numeric Archive Key in Media Manifest (`build_bidirectional_package`)**
  - Create a temp directory; write a file named `"0"` (the archive key) containing dummy WAV bytes
  - Call `build_bidirectional_package()` with one note whose audio field is `[sound:hello_001.wav]` and `media_map={"hello_001.wav": "0"}`, `original_mid=1607392321`
  - Assert `Path(package.media_files[0]).name == "hello_001.wav"` — **EXPECTED TO FAIL**: unfixed code appends `"tmp/0"` so `.name == "0"`
  - Document counterexample: `Path(media_files[0]).name == "0"` instead of `"hello_001.wav"`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves Bug 3 exists)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.4, 1.5, 2.3, 2.4_

  **Bug 4 — Bad Model Selection for `MODEL_ID_NO_JYUTPING` (`build_bidirectional_package`)**
  - Call `build_bidirectional_package()` with `original_mid=1607392322` and one minimal note
  - Assert the model mid used for the output notes equals `1607392322` — **EXPECTED TO FAIL**: unfixed `else` branch assigns `1607392321`
  - Also call with `original_mid=1607392320` and assert output model mid equals `1607392321` — **EXPECTED TO PASS** on unfixed code (confirms this path is already correct)
  - Document counterexample for `mid=1607392322`: output model mid is `1607392321` instead of `1607392322`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: `mid=1607392322` case FAILS; `mid=1607392320` case PASSES
  - Mark task complete when tests are written, run, and results are documented
  - _Requirements: 1.6, 2.5, 2.6_

  **Test file location**: `tests/test_bugfix_exploration.py`

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Legacy and Already-Correct Model Paths, Dry-Run, Empty-Field Skipping, Audio Completeness, Stable Deck ID
  - **IMPORTANT**: Follow observation-first methodology — run UNFIXED code with non-buggy inputs first, observe outputs, then encode as property-based tests
  - **Scoped to non-bug-condition inputs** (i.e. inputs where `isBugCondition` returns false for all four bugs)

  **Preservation 1 — Legacy 4-field model path (`mid=1607392319`)**
  - Observe: `build_bidirectional_package()` with `original_mid=1607392319` selects `create_model_no_jyutping()` → output `mid=1607392322`
  - Write property: `@given(notes_strategy())` — for any list of valid 4-field notes with `original_mid=1607392319`, the output model mid is always `1607392322`
  - Verify test PASSES on UNFIXED code
  - _Requirements: 3.1_

  **Preservation 2 — Dry-run produces no output file**
  - Observe: `convert_apkg()` with `dry_run=True` returns `True` and writes no file to `dest`
  - Write property: for any valid source `.apkg` and any dest path, `dry_run=True` never creates the dest file
  - Verify test PASSES on UNFIXED code
  - _Requirements: 3.4_

  **Preservation 3 — Empty English or Cantonese field is skipped**
  - Observe: notes with `flds[0].strip() == ""` or `flds[1].strip() == ""` are skipped and a warning is logged
  - Write property: `@given(st.lists(...))` — for any mix of valid and empty-field notes, the output deck contains exactly the non-empty notes
  - Verify test PASSES on UNFIXED code
  - _Requirements: 3.6_

  **Preservation 4 — All present audio files included in output**
  - Observe: for any set of notes where every `[sound:F]` field resolves to a file present in `media_dir`, all files appear in `package.media_files`
  - Write property: `@given(st.lists(audio_note_strategy(), min_size=1))` — count of `media_files` equals count of notes with resolvable audio
  - Verify test PASSES on UNFIXED code
  - _Requirements: 3.5_

  **Preservation 5 — Stable deck ID derivation**
  - Observe: calling the deck ID derivation twice with the same deck name produces the same integer
  - Write property: `@given(st.text(min_size=1))` — `deck_id(name) == deck_id(name)` for all name strings
  - Verify test PASSES on UNFIXED code
  - _Requirements: 3.7_

  **Test file location**: `tests/test_bugfix_preservation.py`
  - Run all preservation tests on UNFIXED code
  - **EXPECTED OUTCOME**: All preservation tests PASS (confirms baseline behaviour to preserve)
  - Mark task complete when tests are written, run, and all pass on unfixed code

- [x] 3. Fix all four bugs

  - [x] 3.1 Fix Bug 1 — Reorder field list in `_create_anki_card()` to canonical slot order
    - In `cantonese_anki_generator/anki/package_generator.py`, change the `genanki.Note` fields list from `[English, Cantonese, Jyutping, Audio, Tags]` to `[English, Jyutping, Cantonese, Audio, Tags]`
    - Slot 0: `fields['English']`
    - Slot 1: `fields['Jyutping']`  ← was slot 2
    - Slot 2: `fields['Cantonese']` ← was slot 1
    - Slot 3: `fields['Audio']`
    - Slot 4: `fields['Tags']`
    - Also update `CantoneseCardTemplate.create_model()` in `templates.py` to declare fields in the same order: `[English, Jyutping, Cantonese, Audio, Tags]`
    - _Bug_Condition: `isBugCondition_1(note)` — `note.fields[1]` contains Chinese characters and `note.fields[2]` contains Jyutping (slots 1 and 2 swapped)_
    - _Expected_Behavior: `note.fields[1] == jyutping` AND `note.fields[2] == cantonese` for all generated notes_
    - _Preservation: vocabulary entries with all five fields populated continue to produce valid notes; empty Jyutping entries continue to produce `fields[1] == ""`_
    - _Requirements: 2.1_

  - [x] 3.2 Fix Bug 2 — Add model ID assertion guard in `_create_anki_card()`
    - In `cantonese_anki_generator/anki/package_generator.py`, after creating the `genanki.Note`, add:
      ```python
      assert note.model.mid == CantoneseCardTemplate.MODEL_ID, (
          f"Model ID mismatch: expected {CantoneseCardTemplate.MODEL_ID}, "
          f"got {note.model.mid}"
      )
      ```
    - This pins the reference to `CantoneseCardTemplate.MODEL_ID` and prevents silent regression if `create_model()` is ever changed to use a hardcoded ID
    - _Bug_Condition: `isBugCondition_2(note)` — `note.model.mid != CantoneseCardTemplate.MODEL_ID` (i.e. `!= 1607392321`)_
    - _Expected_Behavior: `note.model.mid == 1607392321` for every note produced by `_create_anki_card()`_
    - _Preservation: no change to note content or deck structure; assertion only fires if the model is misconfigured_
    - _Requirements: 2.2_

  - [x] 3.3 Fix Bug 3 — Copy media file to named `.wav` path before appending to `media_files`
    - In `backfill_bidirectional_cards.py`, inside `build_bidirectional_package()`, replace:
      ```python
      file_path = media_dir / archive_key
      if file_path.exists():
          media_files.append(str(file_path))
      ```
      with:
      ```python
      file_path = media_dir / archive_key
      if file_path.exists():
          named_path = media_dir / filename
          if not named_path.exists():
              shutil.copy2(file_path, named_path)
          media_files.append(str(named_path))
      ```
    - Verify `import shutil` is present at the top of `backfill_bidirectional_cards.py` (it already is; confirm and leave unchanged)
    - _Bug_Condition: `isBugCondition_3(entry, filename)` — `Path(entry).name != filename` (basename is a numeric archive key, not the `.wav` name)_
    - _Expected_Behavior: `Path(entry).name == filename` for every entry in `package.media_files`; genanki writes `{"0": "hello_001.wav", …}` in the manifest_
    - _Preservation: all audio files that were previously included continue to be included; no files are silently dropped; the copy is skipped if the named file already exists_
    - _Requirements: 2.3, 2.4, 3.5_

  - [x] 3.4 Fix Bug 4 — Replace if/else with explicit four-way model ID mapping in `build_bidirectional_package()`
    - In `backfill_bidirectional_cards.py`, replace the two-branch `if/else` model selection with:
      ```python
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
    - Canonical mapping:
      - `1607392319` (LEGACY_MODEL_ID) → `create_model_no_jyutping()` → output `mid=1607392322`
      - `1607392320` (JYUTPING_MODEL_ID) → `create_model()` → output `mid=1607392321`
      - `1607392321` (MODEL_ID) → `create_model()` → output `mid=1607392321` (unchanged)
      - `1607392322` (MODEL_ID_NO_JYUTPING) → `create_model_no_jyutping()` → output `mid=1607392322` (unchanged)
    - _Bug_Condition: `isBugCondition_4(original_mid, output_mid)` — `original_mid == 1607392320 AND output_mid == 1607392321` (transitional ID unnecessarily reassigned), OR `original_mid == 1607392322 AND output_mid == 1607392321` (already-correct 4-field note reassigned)_
    - _Expected_Behavior: each of the four known model IDs maps to exactly one output model ID per the canonical mapping above_
    - _Preservation: `mid=1607392319` path continues to use `create_model_no_jyutping()`; unknown model IDs fall through to the 5-field default with a warning_
    - _Requirements: 2.5, 2.6, 3.1, 3.2_

  - [x] 3.5 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - All Four Bug Conditions Resolved
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behaviour; when they pass, the bugs are fixed
    - Run `pytest tests/test_bugfix_exploration.py -v` on the FIXED code
    - **EXPECTED OUTCOME**: All four exploration tests PASS (confirms all bugs are fixed)
    - If any test still fails, revisit the corresponding fix sub-task (3.1–3.4) before proceeding
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Legacy Paths, Dry-Run, Empty-Field Skipping, Audio Completeness, Stable Deck ID
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `pytest tests/test_bugfix_preservation.py -v` on the FIXED code
    - **EXPECTED OUTCOME**: All preservation tests PASS (confirms no regressions introduced)
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6, 3.7_

- [x] 4. Write and run unit and integration tests

  - [x] 4.1 Unit tests for `_create_anki_card()` field ordering and model ID
    - Test with all five fields populated: assert `fields[0..4]` match `[english, jyutping, cantonese, "[sound:…]", tags]`
    - Test with empty Jyutping: assert `fields[1] == ""` and `fields[2] == cantonese`
    - Test model ID: assert `note.model.mid == CantoneseCardTemplate.MODEL_ID` (`1607392321`)
    - Test file: `tests/test_package_generator.py`
    - _Requirements: 2.1, 2.2_

  - [x] 4.2 Unit tests for `build_bidirectional_package()` model selection
    - Test each of the four known model IDs (`1607392319`, `1607392320`, `1607392321`, `1607392322`) and assert the output model mid matches the canonical mapping
    - Test an unknown model ID (e.g. `9999999`) and assert it falls through to the 5-field default without raising an exception
    - Test file: `tests/test_backfill.py`
    - _Requirements: 2.5, 2.6, 3.1, 3.2_

  - [x] 4.3 Unit tests for `build_bidirectional_package()` media file naming
    - Create a temp directory with a file named `"0"`; call `build_bidirectional_package()` with `media_map={"hello_001.wav": "0"}`
    - Assert `Path(package.media_files[0]).name == "hello_001.wav"`
    - Assert the named file `hello_001.wav` exists in the temp directory after the call
    - Test file: `tests/test_backfill.py`
    - _Requirements: 2.3, 2.4_

  - [x] 4.4 Unit tests for edge cases
    - Empty English or Cantonese field: assert note is skipped and warning is logged
    - `dry_run=True`: assert `convert_apkg()` returns `True` and no output file is created
    - Missing audio archive file: assert warning is logged and note is still added to deck
    - Test file: `tests/test_backfill.py`
    - _Requirements: 3.4, 3.6_

  - [x] 4.5 Integration test — end-to-end package generation with correct field slots
    - Generate a `.apkg` from a small vocabulary list (3–5 entries with English, Cantonese, Jyutping, and audio)
    - Unpack the `.apkg` (it is a zip); open `collection.anki2` with SQLite
    - Query the `notes` table; split `flds` on `\x1f`; assert slot 1 is Jyutping and slot 2 is Cantonese for every note
    - Assert the `mid` column equals `1607392321` for every note
    - Test file: `tests/test_integration.py`
    - _Requirements: 2.1, 2.2, 3.3_

  - [x] 4.6 Integration test — end-to-end backfill with correct media manifest
    - Build a synthetic `.apkg` containing one note with `[sound:hello_001.wav]` and a media manifest `{"0": "hello_001.wav"}`
    - Run `convert_apkg()` on it; unpack the output `.apkg`
    - Read the `media` JSON file; assert it contains `"hello_001.wav"` as a value (not `"0"`)
    - Test file: `tests/test_integration.py`
    - _Requirements: 2.3, 2.4_

  - [x] 4.7 Integration test — backfill preserves `mid=1607392322` notes
    - Build a synthetic `.apkg` with `mid=1607392322` notes (4-field layout)
    - Run `convert_apkg()` on it; unpack the output; open `collection.anki2`
    - Assert every note's `mid` is `1607392322` (not `1607392321`)
    - Test file: `tests/test_integration.py`
    - _Requirements: 3.2_

- [x] 5. Checkpoint — Ensure all tests pass
  - Run the full test suite: `pytest -v`
  - Confirm all exploration tests pass (bugs fixed)
  - Confirm all preservation tests pass (no regressions)
  - Confirm all unit tests pass
  - Confirm all integration tests pass
  - If any test fails, diagnose and fix before marking this task complete
  - Ask the user if any questions arise about ambiguous behaviour

## Task Dependency Graph

```json
{
  "waves": [
    {"wave": 1, "tasks": ["1", "2"]},
    {"wave": 2, "tasks": ["3"]},
    {"wave": 3, "tasks": ["4"]},
    {"wave": 4, "tasks": ["5"]}
  ]
}
```

- Task 1 must be completed before task 3 (tests must be written and run on unfixed code first)
- Task 2 must be completed before task 3 (baseline preservation behaviour must be observed and encoded first)
- Tasks 3.1–3.4 can be applied in any order but should all be complete before running 3.5 and 3.6
- Task 4 can be written in parallel with tasks 1–3 but must pass before task 5
- Task 5 is the final gate; all prior tasks must be complete and green

## Notes

- `import shutil` is already present in `backfill_bidirectional_cards.py` — confirm and leave unchanged (task 3.3)
- The `create_model()` field declaration in `templates.py` must be updated alongside the `_create_anki_card()` field list (task 3.1) — both must agree on the canonical order `[English, Jyutping, Cantonese, Audio, Tags]`
- Property-based tests use `hypothesis` (`@given`, `st.text`, `st.lists`) — already a project dependency
- Test files follow the project convention: `tests/test_*.py`
- Run tests with `pytest -v` or by category: `pytest -m unit`, `pytest -m property`, `pytest -m integration`
- The `.hypothesis/` directory in the workspace root contains saved examples from prior runs — Hypothesis will replay these automatically
