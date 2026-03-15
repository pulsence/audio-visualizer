# Phase 4: Build the SRT Edit Tab

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 4.1: Create the editable subtitle document model and round-trip I/O

SRT Edit needs its own stable editing model and round-trip layer before the waveform/editor UI is added, because the integrated `audio_visualizer.srt` package does not currently expose a general editable parser model for this use case.

**Tasks:**
- Create a tab-local subtitle document model that tracks ordered blocks, text, timing, speaker labels, dirty state, and source metadata
- Implement `.srt` load/save round-tripping into that model, using `pysubs2` mapping or equivalent tab-local parsing logic as the underlying parser layer
- Preserve enough information for safe re-save without collapsing the editing model into the shared `audio_visualizer.srt` public API
- Add model-level operations for add/remove/split/merge and timestamp normalization
- Create/update tests for parser round-trip fidelity, timestamp normalization, split/merge behavior, and save output correctness
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/__init__.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/document.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/parser.py`
- Create `tests/test_srt_edit_model.py`

**Success criteria:** The app can load an existing SRT into a stable editable model, modify it, and write it back without relying on ad hoc widget state as the source of truth.

### 4.2: Build the waveform, playback, and table-editing foundation

With the document model in place, the next milestone is an editor that can display waveform context, synchronize playback, and expose precise table-based editing before the drag UI is layered on top.

**Tasks:**
- Build the waveform view on `pyqtgraph` using downsampling, clip-to-view, region overlays, and a playback cursor
- Use `PlotWidget`/`PlotItem` with `setDownsampling(auto=True, mode='peak')` and `setClipToView(True)` so large audio files remain responsive
- Represent subtitle timing regions with pyqtgraph items that support draggable boundaries and selection highlighting; include a distinct playback cursor line that can also support click-to-seek
- Add a split layout with waveform on top and an editable subtitle table below
- Integrate `QMediaPlayer` and `QAudioOutput` for playback, seeking, cursor updates, and selection-follow behavior
- Support selecting a subtitle row from the table and highlighting the corresponding waveform region
- Load waveform/analysis data through the shared `SessionContext` analysis cache when possible; waveform generation for long files should happen in a background worker rather than blocking the UI thread
- Create/update tests for widget construction, selection sync, playback-position updates, and large-file waveform data handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`
- Create `tests/test_ui_srt_edit_tab.py`

**Success criteria:** Users can load an SRT and its audio source, see subtitle timing against a waveform, play/seek audio, and edit timestamps/text numerically in a synchronized editor.

### 4.3: Add full editing interactions and undo/redo support

After the waveform and table are stable, add the direct-manipulation editing layer and make every destructive change safely undoable.

**Tasks:**
- Add draggable waveform-region handles for adjusting subtitle start/end times visually
- Implement `QUndoCommand` subclasses for move-region, edit-timestamp, edit-text, add/remove, and split/merge operations
- Initialize the SRT Edit undo stack with a limit of 200 (high limit because subtitle editing produces many small changes)
- Push drag commands on mouse release only, and coalesce text/numeric edits with `mergeWith()` to avoid noisy undo history
- Clear the SRT Edit undo stack when a new subtitle document is loaded
- Wire tab-local undo/redo actions into the shared Edit menu through `BaseTab`
- Create/update tests for command apply/revert behavior, merge/coalesce logic, and stack-reset behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- Create `tests/test_ui_undo.py`
- Create or modify `tests/test_ui_srt_edit_tab.py`

**Success criteria:** SRT Edit supports both numeric and drag-based timing changes, and every editor action can be undone/redone through a tab-local `QUndoStack`.

### 4.4: Add the subtitle QA panel and named lint profiles

Subtitle QA belongs in the editor because that is where the editable source of truth, undo stack, and waveform context already live.

**Tasks:**
- Implement lint checks for readability, timing integrity, text quality, speaker consistency, and render safety
- Seed the default lint profile from `ResolvedConfig.formatting` so SRT Gen and SRT Edit agree on baseline thresholds
- Add named lint profiles such as `pipeline_default`, `accessible_general`, and `short_form_social`
- Ensure `pipeline_default` explicitly incorporates `max_chars`, `max_lines`, `target_cps`, `min_dur`, `max_dur`, `min_gap`, and `pad` from the current formatting defaults instead of hard-coding a second independent rule set
- Show inline severity hints in the table and a dedicated QA panel with click-to-jump navigation
- Make every machine-fix action undoable through the shared SRT Edit undo stack
- Create/update tests for lint rules, profile overrides, issue navigation, and machine-fix undo behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/lint.py`
- Create `tests/test_srt_edit_lint.py`

**Success criteria:** SRT Edit can highlight subtitle quality problems inline and through a QA panel, using profile-driven thresholds that remain consistent with the transcription pipeline defaults.

### 4.5: Add the auto-resync toolkit

Resync operations are a major differentiator for the editor and should be implemented after the waveform, document model, and undo system are all stable.

**Tasks:**
- Implement batch timing tools for global shift, shift from cursor onward, two-point stretch, and FPS-drift correction
- Add preview-diff flows so users can review timing changes before applying them
- Integrate silence-based snapping using `detect_silences()` from `srt.io.audioHelpers` and `apply_silence_alignment()` from `srt.core.subtitleGeneration`. These helpers are **not exported** from `srt.__init__.py`, so SRT Edit must import them directly from the internal modules (e.g., `from audio_visualizer.srt.io.audioHelpers import detect_silences`). If a cleaner public API boundary is preferred, add the needed symbols to `srt.__init__.py`'s `_EXPORTS` and `src/audio_visualizer/srt/__init__.py` to the files list for this task.
- Reapply word-level or segment timing from generated JSON bundles when compatible sidecars exist in `SessionContext`. Note that JSON bundles only include word-level timing when the transcription was run with `word_level=True`; when word data is absent, the resync UI should clearly indicate reduced resync quality and fall back to segment-level timing only.
- Handle speaker-aware resync boundaries when diarization labels are present. Note that `SubtitleBlock.speaker` is only populated in `PipelineMode.TRANSCRIPT` mode — general and shorts-mode transcriptions will not have speaker data. The UI should degrade gracefully when speaker labels are absent rather than offering speaker-aware operations that cannot function.
- Scope resync operations to either the current selection or the full document
- Apply each resync operation as a single undoable command or macro
- Create/update tests for resync math, preview generation, selection scoping, silence snapping, JSON-bundle timing reuse, missing word-level data fallback, and absent speaker-label handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/resync.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_srt_edit_resync.py`

**Success criteria:** SRT Edit includes previewable, undoable batch retiming tools that can reuse silence data and word/segment sidecars from earlier transcription work when available.

### 4.6: Phase 4 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify round-trip editing, waveform interaction, QA checks, and resync tools all operate against the same document model

**Phase 4 Changelog:**
- Added a tab-local subtitle document model and round-trip I/O for SRT editing
- Built a waveform-plus-table editor with playback sync
- Added drag editing and full undo/redo support
- Added subtitle QA/lint tooling and batch auto-resync operations
