# Phase 1: Cross-Cutting Foundations

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 1.

Foundation work required before later feature phases can ship. This phase establishes the bundle contract, persistence/versioning rules for the coordinate break, dependency packaging expectations, and the Advanced tab shell slot.

### 1.1: Bundle Schema Contract

Establish the canonical word-level contract shared by SRT Gen, SRT Edit, Caption Animator, and later correction-tracking work.

**Tasks:**
1. Add `bundle_version: int` to bundle output in `write_json_bundle()` in `srt/io/outputWriters.py`. Treat the current writer output as v1 and the new contract as v2.
2. Define the v2 bundle schema so it is explicit and stable:
   - subtitle entries have stable `id` fields,
   - word entries use `text` instead of `word`,
   - each word carries a `subtitle_id` back-reference,
   - subtitle entries preserve `words`,
   - the bundle also exposes a flat top-level `words` convenience list for consumers like resync helpers,
   - provenance fields are stored where available: `original_text`, `source_media_path`, `model_name`, `device`, `compute_type`, `speaker_label`, `confidence`,
   - alignment fields are reserved for bundle-from-SRT output: `alignment_status`, `alignment_confidence`,
   - markdown source text is stored verbatim in text fields.
3. Update `write_json_bundle()` to emit v2 by default and to write the normalized field names even when the source objects still come from faster-whisper.
4. Create `read_json_bundle()` in `src/audio_visualizer/srt/io/bundleReader.py` that accepts both v1 and v2 bundles and normalizes them into one in-memory contract that downstream code can trust.
5. Update `src/audio_visualizer/srt/models.py` so `WordItem` supports optional `id` and `subtitle_id` fields.
6. Update `ui/tabs/srtEdit/resync.py` so `reapply_word_timing()` consumes the normalized loader output instead of assuming a raw dict with a top-level `words[]` payload.
7. Extend `SubtitleEntry` in `ui/tabs/srtEdit/document.py` with `words: list[WordItem]` plus provenance fields required for later correction tracking and bundle round-tripping.
8. Export `read_json_bundle` from `src/audio_visualizer/srt/io/__init__.py` so every consumer uses the shared loader.

**Files:**
- `src/audio_visualizer/srt/io/outputWriters.py`
- `src/audio_visualizer/srt/io/bundleReader.py`
- `src/audio_visualizer/srt/io/__init__.py`
- `src/audio_visualizer/srt/models.py`
- `src/audio_visualizer/ui/tabs/srtEdit/resync.py`
- `src/audio_visualizer/ui/tabs/srtEdit/document.py`

**Success criteria:** `write_json_bundle()` emits v2 bundles by default, `read_json_bundle()` normalizes both v1 and v2 into one consistent structure, word-level consumers stop depending on raw bundle shape, and later phases can build on stable subtitle and word identifiers.

**Close-out:** Add or update tests for bundle v1/v2 normalization and SRT Edit word hydration, run the relevant tests and `pytest tests/ -v` when shared SRT flows changed, update `.agents/docs/architecture/` docs if contracts changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 1.2: Settings Schema and Recipe Versioning

Prepare the persistence layer for the center-origin coordinate break and the new Advanced tab.

**Tasks:**
1. Bump the settings schema version in `ui/settingsSchema.py`.
2. Add explicit rejection logic for composition payloads created before the new coordinate system. Do not silently load old top-left-origin data.
3. Make the rejection path user-facing and clear in both auto-load and manual-load flows.
4. Add `"advanced"` to the tab key set so settings persistence now expects 7 tabs.
5. Add default settings slots for the Advanced tab.
6. Update `workflowRecipes.py` so recipes also understand the new tab key and reject old composition payloads the same way settings does.
7. Add `composition_schema_version` to `CompositionModel.to_dict()` and reject missing or old versions in `from_dict()`.

**Files:**
- `src/audio_visualizer/ui/settingsSchema.py`
- `src/audio_visualizer/ui/workflowRecipes.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`

**Success criteria:** Pre-v0.7.0 composition payloads are rejected with a clear message, settings and recipes both persist the new 7-tab layout, and composition data cannot silently load with incorrect center-origin math.

**Close-out:** Add or update tests for settings-schema bumps, recipe rejection, and composition-schema version gating, run the relevant tests and `pytest tests/ -v` when shared UI persistence changed, update `.agents/docs/architecture/` docs if persistence contracts changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 1.3: Dependency Additions, Capability Gating, and Release Build Notes

Add new dependencies and make sure missing runtime capabilities degrade cleanly instead of crashing.

**Tasks:**
1. Add `PyOpenGL` and `sounddevice` to the base dependencies in `pyproject.toml` because real-time playback depends on them.
2. Add `torch`, `transformers`, `peft`, and `ctranslate2` under an `[advanced]` extra for source installs.
3. Document the official desktop build path so the release artifact is built with the advanced stack enabled even if source installs use extras.
4. Create `core/capabilities.py` with cached, lazy capability checks such as `has_opengl()`, `has_sounddevice()`, and `has_training_stack()`.
5. Update runtime call sites to use those capability checks and surface a clear user-facing explanation when playback or training features are unavailable.
6. Audit the in-repo release/build path. If a build script or spec file exists, update it so the packaged app bundles the playback and training dependencies. If the release flow is managed outside this repo, add an explicit release note in the repo docs so v0.7.0 cannot be packaged without those dependencies.

**Files:**
- `pyproject.toml`
- `readme.md`
- `src/audio_visualizer/core/capabilities.py`

**Success criteria:** Base installs can run the app with playback dependencies, advanced installs can enable training dependencies, runtime failures are converted into diagnostics instead of crashes, and the repo documents how the official desktop build must include the advanced stack.

**Close-out:** Add or update tests for capability gating and missing-dependency fallbacks where practical, run the relevant tests and `pytest tests/ -v` when startup or shared UI flows changed, update `.agents/docs/architecture/` docs if runtime capability behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 1.4: Advanced Tab Shell Registration

Register the Advanced tab in the application shell so later phases can implement its content.

**Tasks:**
1. Create a placeholder `AdvancedTab` class in `ui/tabs/advancedTab.py` extending `BaseTab`.
2. Register `"advanced"` in `MainWindow._lazy_tab_defs`.
3. Add the Advanced tab to any tab-instantiation path that still assumes 6 tabs.
4. Add the Advanced tab as the last sidebar entry in `NavigationSidebar`.
5. Update tests that currently assert exactly 6 tabs so they expect 7.

**Files:**
- `src/audio_visualizer/ui/tabs/advancedTab.py`
- `src/audio_visualizer/ui/mainWindow.py`
- `tests/`

**Success criteria:** The app launches with 7 sidebar entries, the Advanced tab lazy-loads successfully, and the shell test suite no longer assumes a 6-tab application.

**Close-out:** Add or update tests for tab registration and lazy loading, run the relevant tests and `pytest tests/ -v` when shared UI shell behavior changed, update `.agents/docs/architecture/` docs if shell structure changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 1.5: Phase 1 Review

**Tasks:**
1. Review all Phase 1 foundation changes and verify there are no gaps in the bundle, settings, dependency, or shell contracts.
2. Remove dead code, duplicate compatibility logic, or one-off schema handling that Phase 1 made obsolete.
3. Verify tests are structured around the new shared contracts instead of around temporary implementation details.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 1 implementation files
- Phase 1 tests

**Success criteria:** Phase 1 leaves one clear source of truth for bundle reading, persistence gating, dependency detection, and Advanced-tab shell registration.

### 1.6: Phase 1 Changelog

**Tasks:**
1. Summarize the user-visible and developer-visible changes delivered in Phase 1.
2. Call out the breaking persistence change and the new bundle-version contract so later phases do not re-open those decisions.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 1 implementation notes
- Any release-prep notes or TODO updates touched in this sub-phase

**Success criteria:** The rest of the plan can treat bundle v2, 7-tab persistence, and dependency gating as settled foundations.
