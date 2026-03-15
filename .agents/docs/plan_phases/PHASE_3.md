# Phase 3: Build the SRT Gen Tab

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 3.1: Create the SRT Gen UI and settings model

Implement the transcription tab as a preset-driven, batch-capable UI with a clean default surface and a full advanced feature set behind structured grouping.

**Tasks:**
- Create `SrtGenTab` with batch input-file selection, queue display, primary output controls, and advanced panels for correction/script inputs, side outputs, diarization, and diagnostics
- Use a preset-driven form with collapsible Advanced sections so common workflows stay simple while the full `audio_visualizer.srt` surface remains available
- Add explicit model controls with a "Load Model" action plus load-on-demand fallback when starting a transcription
- Expose the full `ResolvedConfig` settings surface organized into structured groups: **Model** (model_name, device, strict_cuda), **Formatting** (max_chars, max_lines, target_cps, min_dur, max_dur, allow_commas, allow_medium, prefer_punct_splits, min_gap, pad), **Transcription** (vad_filter, condition_on_previous_text, no_speech_threshold, log_prob_threshold, compression_ratio_threshold, initial_prompt), **Silence** (silence_min_dur, silence_threshold_db), **Prompt/alignment** (initial_prompt text/file, correction_srt, script_path), **Output** (output_path, fmt, word_level, mode, language, word_output_path), **Side outputs** (transcript_path, segments_path, json_bundle_path), and **Advanced/diagnostics** (diarize, hf_token, keep_wav, dry_run). Common settings (model, format, mode, output path) belong in the default view; the rest go into collapsible advanced groups.
- Default word-level output on, or clearly warn when it is disabled, because later resync quality depends on it
- Add config-file import/browse and "open config folder" actions backed by `get_srt_config_dir()`, which also triggers `ensure_example_configs()` seeding on first access. Support loading saved JSON config files from the app-data config library alongside the in-memory `PRESETS` dropdown.
- Add file-picker integration that can browse both filesystem inputs and relevant assets from `SessionContext`
- Create/update tests for settings collection/application, preset application, queue serialization, and advanced-option validation
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_srt_gen_tab.py`

**Success criteria:** The SRT Gen tab supports queued inputs, a usable default form, and the full advanced transcription feature surface without overwhelming the common path.

### 3.2: Implement cancellable batch transcription orchestration

Batch transcription must be cancelable even though the current `audio_visualizer.srt` API is synchronous, so the tab needs both queue-level orchestration and a killable per-file execution boundary.

**Tasks:**
- Create a Qt worker for SRT Gen that owns queue sequencing, progress forwarding, and cancel-state transitions
- Implement a child-process transcription runner that streams structured JSONL events to the parent and allows soft-cancel plus hard-kill fallback
- Add parent-owned temporary-workspace management and cleanup after normal completion, cancellation, or forced termination
- Add cooperative cancellation checks between files and between major pipeline stages where the in-process code can reasonably surface them
- Preserve event payloads from `audio_visualizer.srt` through the worker bridge so the tab can show stage/progress/model status accurately
- Reuse the loaded `ModelManager` instance across batch queue items to avoid reloading the model between files. Note that `ModelManager` caches only one model at a time — switching model names unloads the previous model before loading the new one, so the batch worker should hold a consistent model reference for the duration of a queue run and the GUI should not imply multi-model residency.
- Ensure batch cancel stops before the next file, and file-level cancel terminates the child process when needed
- Create/update tests for queue orchestration, event relay, soft cancel, hard-kill fallback, and cleanup behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/srtGenWorker.py`
- Create `src/audio_visualizer/ui/workers/srtTranscribeChild.py`
- Modify `src/audio_visualizer/srt/srtApi.py`
- Modify `src/audio_visualizer/srt/core/pipeline.py`
- Modify `src/audio_visualizer/srt/core/whisperWrapper.py`
- Create `tests/test_srt_gen_worker.py`

**Success criteria:** SRT Gen jobs can be started, monitored, and canceled from the UI. Batch jobs stop cleanly, per-file work can be forcibly terminated when necessary, and temporary artifacts are cleaned up predictably.

### 3.3: Register transcription outputs and sidecars for downstream tabs

SRT Gen is the first cross-tab producer in the new workflow, so it must publish its outputs in a way that SRT Edit, Caption Animate, and Composition can reuse without manual re-entry.

**Tasks:**
- Register generated subtitle files, JSON bundles, transcript outputs, segment sidecars, and optional word-output files as `SessionAsset` entries with source metadata
- Capture enough metadata to distinguish primary subtitle outputs from diagnostic sidecars
- Add tab actions to send generated outputs directly into SRT Edit and Caption Animate selection flows
- Ensure project save/load restores queued inputs, tab settings, and generated output references correctly
- Create/update tests for asset registration, downstream handoff metadata, and project-state restoration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Create or modify `tests/test_ui_srt_gen_tab.py`

**Success criteria:** SRT Gen outputs become reusable session assets, including the JSON bundles needed for later resync work, and downstream tabs can consume them without the user re-browsing the filesystem.

### 3.4: Phase 3 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify batch orchestration, cancel behavior, and session-asset publication all work together

**Phase 3 Changelog:**
- Added a batch-capable SRT Gen tab with a full advanced settings surface
- Implemented cancellable transcription orchestration around the synchronous SRT pipeline
- Registered transcription outputs and sidecars in `SessionContext` for downstream reuse
