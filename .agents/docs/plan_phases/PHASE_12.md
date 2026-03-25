# Phase 12: Refinement - 2

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 12.

This phase exists to capture any second-wave refinement issues discovered after Phase 11 verification and before the third refinement pass and final release review.

## Reported Changes to Make

Every item in this section is in scope for Phase 12 and must map to one of the implementation subphases below. Each item should end with automated regression coverage or an explicit manual verification note when the behavior is difficult to exercise in tests.

- General
  - The auto save for input values is broken as the changes in this Plan
- Render Composition
  - The Refresh preview should not exist, as the compositor/timeline/layer view should update whenever the playhead moves.
  - Why is there a compositor tab? There should only be timeline, to should the timeline at the playhead, and layer to should
    the selected layer at the play head
  - Clicking play on the Render Preview crashes the program with no error.

## Phase 12 Planning Notes

- Preserve the contracts from Phases 1-11 unless this phase explicitly replaces them.
- Use this phase only for issues that are discovered after Phase 11 verification or that were intentionally deferred out of Phase 11 scope.
- If a Phase 12 item overrides a decision made in Phase 11, record that override explicitly in the resolved findings before implementation starts.
- Treat the autosave report as a persistence regression against the current settings/project contract, not as permission to add one-off storage paths. The fix should stay inside the normal `collect_settings()` / `apply_settings()` and `MainWindow` save/load flow.
- Phase 12 explicitly replaces the current Render Composition manual-preview UX. The normal preview workflow should stay on the Phase 4 OpenGL-backed compositor/playback path, with capability fallback preserved only as a safety net rather than as a parallel user-facing preview mode.
- The separate `Refresh Preview` button and user-facing `Compositor` tab are in scope to remove in favor of playhead-synchronized Timeline and Layer views.
- For pointer-heavy, playback-heavy, or FFmpeg-heavy fixes that are difficult to assert fully in tests, add a brief manual verification checklist in addition to targeted automated coverage.

## Phase 12 Resolved Findings

- Settings persistence currently flows through `MainWindow._collect_settings()` / `_apply_settings()` plus each tab's `collect_settings()` / `apply_settings()` pair. Phase 12 should treat the autosave report as a regression audit for controls touched by this refinement pass and add round-trip coverage for last-settings and project save/load behavior.
- Render Composition still exposes a manual `Refresh Preview` button, a three-tab preview stack (`Compositor`, `Timeline`, `Layer`), and single-frame preview workers that drive the Timeline/Layer labels separately from the OpenGL playback path. Phase 12 should collapse this back to a playhead-driven preview model anchored on the OpenGL compositor contract from Phase 4.
- Preview playback is split between `RenderCompositionTab` transport controls and `PlaybackEngine`. Existing tests cover empty/fallback paths, but Phase 12 still needs explicit crash-regression coverage for pressing Play with real composition data and for surfacing engine-start failures in the UI instead of terminating the tab/app.

### 12.1: Autosave and Input Persistence Regression Fixes

Restore autosave/project persistence for the input values affected by the recent refinement work.

**Tasks:**
1. Audit the controls changed by this refinement pass and ensure their values round-trip through the normal `collect_settings()` / `apply_settings()` paths instead of relying on transient widget state.
2. Fix any regressions in last-session autosave and explicit project save/load so edited values survive restart and reload.
3. Verify lazy-tab storage still captures pending settings correctly for tabs that are not instantiated at save time.
4. Add regression coverage for autosave/project round-trip behavior in the affected tabs and `MainWindow` settings persistence flow.
5. Update `.agents/docs/` architecture documentation if the persistence contract or saved state changes.
6. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- `src/audio_visualizer/ui/mainWindow.py`
- Relevant tab modules touched by the persistence fixes
- `tests/test_ui_main_window.py`
- Relevant tab/settings persistence tests

**Success criteria:** Input values changed in this refinement pass persist reliably through last-session autosave and explicit project save/load without adding one-off persistence paths.

### 12.2: Render Composition Preview Workspace Alignment

Remove the manual preview UX and align the Render Composition preview surface with the Phase 4 OpenGL-backed playback model.

**Tasks:**
1. Remove the user-facing `Refresh Preview` button and the current manual-refresh-only messaging from the preview area.
2. Remove the separate user-facing `Compositor` tab and reorganize the preview workspace around only two views: the timeline composition at the current playhead and the selected layer at the current playhead.
3. Replace the primary Timeline/Layer preview update path so it follows playhead movement, transport movement, and layer selection changes through the OpenGL-backed preview/compositor infrastructure established in Phase 4 rather than through a separate software/manual frame-generation flow.
4. Keep preview-dependent interactions such as key-color picking or layer inspection working under the new preview model.
5. Remove obsolete preview glue or worker paths if they are no longer needed after the OpenGL-aligned preview update.
6. Add regression coverage for the preview UI structure and for automatic playhead-driven preview updates, plus a brief manual verification note for the live preview flow on capable hardware.
7. Run tests: `pytest tests/ -v`.
8. Update `.agents/docs/` architecture documentation as needed.
9. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `tests/test_ui_render_composition_tab.py`
- Relevant Render Composition preview tests

**Success criteria:** Render Composition no longer exposes `Refresh Preview` or a user-facing `Compositor` tab, and the Timeline/Layer preview views stay synchronized with the playhead through the OpenGL-backed preview path rather than a separate manual software-preview workflow.

### 12.3: Render Composition Preview Playback Stability

Fix the reported preview-play crash and keep the preview runtime within the Phase 4 playback/fallback guarantees.

**Tasks:**
1. Reproduce and fix the crash triggered by pressing Play in the Render Composition preview area.
2. Harden the `RenderCompositionTab` transport/load path and the `PlaybackEngine` start/seek lifecycle so preview start-up failures are caught and surfaced as user-facing status/errors instead of crashing the program.
3. Preserve the OpenGL-backed preview path as the normal runtime on capable machines while keeping the existing capability-gated fallback behavior safe and non-fatal when runtime requirements are missing.
4. Add regression coverage for play/pause start-up on representative composition data and for failure/fallback paths that previously terminated without a useful error.
5. Add a brief manual verification note covering play, pause, seek, and stop in the updated preview workspace.
6. Run tests: `pytest tests/ -v`.
7. Update `.agents/docs/` architecture documentation as needed.
8. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`
- `src/audio_visualizer/core/capabilities.py`
- `tests/test_ui_render_composition_tab.py`
- Relevant playback-engine tests

**Success criteria:** Clicking Play in Render Composition no longer crashes the program, preview playback either runs on the OpenGL-backed path or fails gracefully with a user-visible reason, and transport/seek interactions remain stable.

### 12.4: Phase 12 Code Review

**Tasks:**
1. Review the Phase 12 changes together and ensure every reported item in this file maps cleanly to a completed implementation task.
2. Review code for dead code, especially preview worker/UI paths or temporary persistence workarounds that should not remain after the fixes land.
3. Review tests to ensure they are well-structured and that the new coverage exercises autosave/project persistence, OpenGL-backed preview synchronization, and preview playback failure handling.
4. Verify the refinement fixes did not weaken existing v0.7.0 guarantees, especially settings persistence, session behavior, Render Composition playback, and shared-worker/render behavior.
5. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 12 implementation files
- Phase 12 tests

**Success criteria:** The second refinement pass closes all newly reported issues without regressing the v0.7.0 guarantees already stabilized in Phase 11.

### 12.5: Phase 12 Changelog

**Tasks:**
1. Summarize the autosave/persistence regression fixes and the Render Composition preview/playback changes delivered in Phase 12.
2. Call out that Phase 12 removes the manual `Refresh Preview` / user-facing `Compositor` workflow in favor of a playhead-synchronized OpenGL-backed preview model.
3. Commit and push any documentation-only cleanup from this sub-phase.

**Files:**
- Phase 12 implementation notes

**Success criteria:** The release notes for this refinement pass clearly describe the persistence repair work and the shift back to the OpenGL-backed Render Composition preview contract.

---

## Phase 12 Release Notes

### Autosave Persistence Fixes (12.1)
- Added `lock_ratio` checkbox to `RenderCompositionTab.collect_settings()` / `apply_settings()` so the lock-aspect-ratio state survives restart and project reload.
- All other tab controls audited — no further persistence gaps found. The `resolution_preset` and per-audio-layer `volume`/`muted` state are correctly persisted inside `CompositionModel.to_dict()`.
- Added settings round-trip regression tests.

### Render Composition Preview Workspace Alignment (12.2)
- **Removed** the manual `Refresh Preview` button and the user-facing `Compositor` tab from the preview area.
- The preview workspace is now organized around two views:
  - **Timeline** — the OpenGL-backed `CompositorWidget` shows all layers composited at the current playhead position.
  - **Layer** — shows the selected visual layer's frame at the current playhead position, sourced from the playback engine's decode buffers.
- Preview updates are driven by playhead movement (transport controls, timeline scrubbing, timestamp spin changes) through the Phase 4 OpenGL compositor infrastructure — no separate FFmpeg subprocess previews.
- **Removed** `_PreviewWorker`, `_LayerPreviewWorker`, and `_PreviewSignals` classes.
- Pick-from-preview for key-color selection now uses `compositor.grab()` instead of a QLabel pixmap.
- Added `PlaybackEngine.layer_image_at()` for single-layer frame access.

### Render Composition Preview Playback Stability (12.3)
- Wrapped transport play/pause handler in `try/except` so playback startup failures are caught and displayed as a status message instead of crashing the application.
- Hardened `PlaybackEngine.play()` to clean up decode workers and audio player on startup failure.
- Hardened the display tick (`_on_display_tick`) to catch and stop playback on render errors.
- Added regression tests for exception handling in play/pause and engine failure paths.

### Code Review (12.4)
- Full test suite: **1380 passed**, no regressions from Phase 12 changes.
- No dead preview-worker code or references remain after cleanup.

### Manual Verification Checklist
- [ ] Play/Pause/Stop/Seek work in the Timeline tab with a multi-layer composition on OpenGL-capable hardware.
- [ ] Layer tab updates automatically when switching layer selection and scrubbing the playhead.
- [ ] Pressing Play with no layers shows a status message instead of crashing.
- [ ] Lock Ratio persists through save/reload.
- [ ] Pick-from-preview for key color works from the Timeline compositor view.
