# Phase 5: Advanced Screen — Correction Database and Prompt Management

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 5.

Implement the correction-tracking database and the first user-facing Advanced-tab tools.

### 5.1: SQLite Correction Database

Create the correction database used for correction tracking, prompt suggestions, and training export.

**Tasks:**
1. Create `core/correctionDb.py` with a `CorrectionDatabase` class.
2. Use SQLite WAL mode and a single-writer pattern.
3. Create tables for:
   - `corrections` with fields for source media path, time range, original text, corrected text, speaker label, model name, LoRA name, confidence, `bundle_entry_id`, and created time,
   - `prompt_terms`,
   - `replacement_rules`.
4. Store the database at `app_paths.data_dir() / "corrections.db"`.
5. Expose methods for recording corrections, querying corrections, managing prompt terms, managing replacement rules, and exporting training pairs.
6. Keep writes on committed action boundaries, not on every keystroke.

**Files:**
- `src/audio_visualizer/core/correctionDb.py`

**Success criteria:** The correction database is created automatically, supports the required query and write operations, preserves bundle linkage where available, and is safe for the app's expected read/write pattern.

**Close-out:** Add or update tests for schema creation and CRUD behavior, run the relevant tests and `pytest tests/ -v` when shared correction-tracking behavior changed, update `.agents/docs/architecture/` docs if persistence architecture changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 5.2: SRT Edit Correction Recording Integration

Automatically record corrections when users edit bundle-backed subtitle text.

**Tasks:**
1. In `SrtEditTab`, detect when the loaded document originated from a bundle with provenance fields.
2. On committed text edits, compare the edited text to `original_text`.
3. Record a correction row only when the text differs and the edit is a forward user action, not an undo/redo replay.
4. Do not record corrections for plain SRT imports that lack provenance.
5. Auto-populate prompt terms when a correction introduces a new candidate domain term or proper noun.
6. Ensure both table editing and sidebar editing flow through the same committed-action recording path.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEditTab.py`
- `src/audio_visualizer/core/correctionDb.py`

**Success criteria:** Bundle-backed edits create useful correction records without duplicate rows, plain subtitle imports do not pollute the correction DB, and all committed edit paths share one recording rule.

**Close-out:** Add or update tests for correction-recording triggers and undo/redo behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if correction-recording contracts changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 5.3: Prompt and Dictionary Management UI

Build the first real Advanced-tab UI sections.

**Tasks:**
1. Add a "Prompt Terms" management section to `AdvancedTab`.
2. Allow add, edit, remove, filter, and export-to-prompt actions for prompt terms.
3. Add a "Replacement Rules" management section with add, edit, remove, filter, and export-to-dictionary actions.
4. Add per-speaker filtering using distinct speaker labels from the database.

**Files:**
- `src/audio_visualizer/ui/tabs/advancedTab.py`
- `src/audio_visualizer/core/correctionDb.py`

**Success criteria:** Users can inspect, edit, filter, and export both prompt terms and replacement rules directly from the Advanced tab.

**Close-out:** Add or update tests for Advanced-tab prompt and replacement-rule management where practical, run the relevant tests and `pytest tests/ -v` when shared Advanced-tab behavior changed, update `.agents/docs/architecture/` docs if Advanced-tab structure changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 5.4: Phase 5 Review

**Tasks:**
1. Review the DB schema and SRT Edit integration together so provenance, write timing, and exported prompt data remain aligned.
2. Remove any duplicate or bypass recording logic introduced during implementation.
3. Verify the new database-backed UI is covered by tests at the correct abstraction level.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 5 implementation files
- Phase 5 tests

**Success criteria:** Phase 5 leaves one clean correction-data path from bundle-backed edits into the Advanced-tab management UI.

### 5.5: Phase 5 Changelog

**Tasks:**
1. Summarize the correction DB, SRT Edit recording, and prompt-management capabilities added in Phase 5.
2. Note any schema or provenance assumptions later LoRA work must preserve.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 5 implementation notes

**Success criteria:** The next Advanced-tab phase can treat correction tracking as established infrastructure.
