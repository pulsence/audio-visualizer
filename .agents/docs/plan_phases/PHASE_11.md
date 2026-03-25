# Phase 11: Refinement - 1

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 11.

This phase follows the same structure as the past User Debug phases: collect reported issues, record clarified decisions and findings, then map the work into concrete implementation subphases before final release review.

## Reported Changes to Make

Every item in this section is in scope for Phase 11 and must map to one of the implementation subphases below. Each item should end with automated regression coverage or an explicit manual verification note when the behavior is difficult to exercise in tests.

- General
  - THERE IS TO BE NO MIGRATION CODE. All the migration and versioning code added in Phase 1 for the json bundles must be removed
    and bundles are not to be versioned.
- Audio Visualizer Screen
  - Add reported Audio Visualizer refinement items here.
- SRT Gen Screen
  - Add reported SRT Gen refinement items here.
- SRT Edit Screen
  - Error message:
```
Error calling Python override of QGraphicsView::mouseMoveEvent(): Traceback (most recent call last):
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\widgets\GraphicsView.py", line 360, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\GraphicsScene\GraphicsScene.py", line 178, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\srtEdit\waveformView.py", line 69, in hoverEnterEvent
    pen = line.pen()
TypeError: Error calling Python override of QGraphicsScene::mouseMoveEvent(): Error calling Python override of QGraphicsObject::hoverEnterEvent(): 'PySide6.QtGui.QPen' object is not callable   
Error calling Python override of QGraphicsView::mouseMoveEvent(): Traceback (most recent call last):
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\widgets\GraphicsView.py", line 360, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\GraphicsScene\GraphicsScene.py", line 178, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\srtEdit\waveformView.py", line 76, in hoverLeaveEvent
    pen = line.pen()
TypeError: Error calling Python override of QGraphicsScene::mouseMoveEvent(): Error calling Python override of QGraphicsObject::hoverLeaveEvent(): 'PySide6.QtGui.QPen' object is not callable  
```
  - Another error message:
```
Error calling Python override of QGraphicsView::mouseMoveEvent(): Traceback (most recent call last):
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\widgets\GraphicsView.py", line 360, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\pyqtgraph\GraphicsScene\GraphicsScene.py", line 178, in mouseMoveEvent
    super().mouseMoveEvent(ev)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\srtEdit\waveformView.py", line 76, in hoverLeaveEvent
    pen = line.pen()
TypeError: Error calling Python override of QGraphicsScene::mouseMoveEvent(): Error calling Python override of QGraphicsObject::hoverLeaveEvent(): 'PySide6.QtGui.QPen' object is not callable 
```
- Caption Animate Screen
  - Add reported Caption Animate refinement items here.
- Render Composition
  - Error message:
```
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\mainWindow.py", line 287, in _on_tab_selected
    self._ensure_tab_instantiated(index)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\mainWindow.py", line 272, in _ensure_tab_instantiated
    tab.apply_settings(pending)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\renderCompositionTab.py", line 2537, in apply_settings
    self._model = CompositionModel.from_dict(model_data)
                  ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\renderComposition\model.py", line 383, in from_dict
    raise ValueError(
    ...<3 lines>...
    )
ValueError: This composition was created with an older coordinate system (top-left origin) that is incompatible with v0.7.0's center-origin coordinates. Please recreate the composition.  
```
  When this happens this needs to be handled more gracefully
- Advanced / Assets / Shared Infrastructure
  - Add reported Advanced tab, Assets tab, session, queue, persistence, or worker refinement items here.

## Phase 11 Planning Notes

- Record clarified product decisions, scope cuts, and verification requirements here as reported issues are triaged.
- Preserve the contracts from Phases 1-10 unless this phase explicitly replaces them.
- Phase 11 explicitly replaces the earlier bundle-versioning direction from Phase 1: bundle files are now an unversioned canonical JSON contract, so bundle migration/version-normalization code should be removed rather than extended.
- The Render Composition coordinate-system break remains a hard rejection for pre-v0.7.0 payloads; this phase only changes how that failure is surfaced to the user during settings restore and lazy tab activation.
- The SRT Edit waveform hover fix must preserve the wider hover-target affordance for both segment and word regions after the crash is removed.
- For pointer-heavy, playback-heavy, or FFmpeg-heavy fixes that are difficult to assert fully in tests, add a brief manual verification checklist in addition to targeted automated coverage.

## Phase 11 Resolved Findings

- Bundle migration/versioning is currently spread across `src/audio_visualizer/srt/io/bundleReader.py`, `src/audio_visualizer/srt/io/outputWriters.py`, `src/audio_visualizer/ui/tabs/srtEdit/document.py`, and multiple bundle-focused tests/docs. Phase 11 should collapse this to one unversioned bundle contract, remove `bundle_version` persistence, and delete the normalization path that reshapes legacy bundle variants.
- The SRT Edit hover traceback is caused by `_HoverableRegionItem.hoverEnterEvent()` and `hoverLeaveEvent()` treating `line.pen` as a callable even though PySide6 exposes it as a `QPen` attribute in this path. The fix should keep the width-change affordance while removing the repeated mouse-move exception.
- Render Composition currently lets `CompositionModel.from_dict()` raise through `RenderCompositionTab.apply_settings()` during lazy tab instantiation in `MainWindow._ensure_tab_instantiated()`. Phase 11 should keep rejecting invalid old payloads, but convert that failure into a controlled user-facing warning plus a safe fallback state instead of an uncaught tab-load error.

### 11.1: Bundle Contract Cleanup

Remove the bundle migration/versioning work that Phase 11 explicitly de-scopes and align all bundle persistence/read paths with one unversioned canonical contract.

**Tasks:**
1. Remove bundle version metadata from the JSON bundle write paths so SRT Gen, bundle-from-SRT export, and SRT Edit bundle saves stop emitting `bundle_version`.
2. Delete bundle migration/version-normalization branches that distinguish between legacy and current bundle shapes, keeping one direct reader/validator for the current bundle contract.
3. Update bundle-consuming code paths only as needed to keep SRT Gen, SRT Edit, and Caption Animate aligned on the same unversioned schema without reintroducing compatibility shims.
4. Remove or rewrite tests that assert versioned bundle behavior, replacing them with coverage for the current unversioned contract and round-trip behavior.
5. Update plan/architecture docs that still describe the bundle as `v2` or version-gated.

**Files:**
- `src/audio_visualizer/srt/io/bundleReader.py`
- `src/audio_visualizer/srt/io/outputWriters.py`
- `src/audio_visualizer/ui/tabs/srtEdit/document.py`
- `tests/test_bundle_reader.py`
- `tests/test_srt_output_writers.py`
- `tests/test_caption_bundle_loading.py`
- `tests/test_srt_edit_model.py`
- `tests/test_ui_srt_edit_tab.py`
- Relevant `.agents/docs/` plan and architecture files

**Success criteria:** Bundles are saved and loaded through one unversioned JSON contract, `bundle_version` is no longer persisted or documented, and no bundle migration/version-normalization code remains in the active code or test paths.

**Close-out:** Add or update automated coverage for bundle round-trips and shared consumer loading, run the relevant tests and `pytest tests/ -v` if shared bundle behavior changes broadly, update `.agents/docs/architecture/` docs if the bundle contract description changes, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 11.2: SRT Edit Waveform Hover Crash Fix

Remove the reported waveform hover traceback while preserving the existing hover affordance for draggable subtitle boundaries.

**Tasks:**
1. Fix `_HoverableRegionItem.hoverEnterEvent()` and `hoverLeaveEvent()` so they read and update the line pen correctly under PySide6/pyqtgraph instead of calling a non-callable `QPen`.
2. Verify the hover-width change still applies to both segment and word regions and still restores the normal border width when the cursor leaves.
3. Add targeted regression coverage for the hover-pen behavior where practical, and include a short manual verification note for live pointer-hover interaction if the event path is awkward to assert fully in tests.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Relevant SRT Edit UI tests

**Success criteria:** Hovering subtitle boundaries in SRT Edit no longer throws repeated mouse-move exceptions, and the hover affordance still makes the draggable boundaries easier to target.

**Close-out:** Add or update targeted SRT Edit waveform tests, run the relevant tests and `pytest tests/ -v` if shared waveform behavior changes, update `.agents/docs/architecture/` docs if the waveform interaction contract changes, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 11.3: Render Composition Legacy-Load Error Handling

Keep the center-origin schema break intact, but handle invalid old composition payloads gracefully during restore and lazy tab loading.

**Tasks:**
1. Preserve the existing rejection of pre-center-origin composition payloads in `CompositionModel.from_dict()`; do not add migration code for old coordinates.
2. Catch/translate the restore failure during `RenderCompositionTab.apply_settings()` and lazy tab instantiation so selecting the tab or restoring a project does not surface an uncaught traceback.
3. Show a clear user-facing warning that the stored composition is from the old coordinate system and must be recreated, then fall back to a safe empty/default composition state so the tab remains usable.
4. Ensure the invalid payload does not keep re-triggering the same failure on every tab activation or block the rest of the app from loading its other tabs/settings.
5. Add regression coverage for direct tab settings restore and `MainWindow` lazy-tab restore paths using an old composition payload.

**Files:**
- `src/audio_visualizer/ui/mainWindow.py`
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `tests/test_ui_main_window.py`
- `tests/test_ui_render_composition_tab.py`

**Success criteria:** Old Render Composition payloads are still rejected, but the app now handles that rejection with a controlled warning and safe fallback state instead of an uncaught lazy-load failure.

**Close-out:** Add or update automated coverage for restore/error-handling paths, run the relevant tests and `pytest tests/ -v` if shared settings restore behavior changes, update `.agents/docs/architecture/` docs if restore/error behavior changes, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 11.4: Phase 11 Code Review

**Tasks:**
1. Review the Phase 11 changes together and ensure every reported item in this file maps cleanly to a completed implementation task.
2. Review code for dead code, especially bundle migration/versioning helpers or one-off restore/error-handling scaffolding that should not remain after the fixes land.
3. Review tests to ensure they are well-structured and that the new coverage exercises the bundle contract, SRT Edit hover behavior, and lazy Render Composition restore handling.
4. Verify the refinement fixes did not weaken existing v0.7.0 guarantees, especially cross-tab bundle handoff, session behavior, lazy tab loading, and shared-worker/render behavior.
5. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 11 implementation files
- Phase 11 tests

**Success criteria:** Phase 11 closes the currently reported refinement issues without leaving behind bundle migration dead code or regressing the v0.7.0 workflow/runtime contracts established in earlier phases.

### 11.5: Phase 11 Changelog

**Tasks:**
1. Summarize the Phase 11 bundle-contract cleanup, SRT Edit waveform hover crash fix, and Render Composition graceful restore handling work.
2. Call out that Phase 11 explicitly removes bundle migration/versioning code while preserving the Render Composition coordinate-system rejection as a user-facing hard break.
3. Commit and push any documentation-only cleanup from this sub-phase.

**Files:**
- Phase 11 implementation notes

**Success criteria:** The release notes for this refinement pass clearly describe the bundle-contract reset, the SRT Edit hover-stability fix, and the improved handling for incompatible old Render Composition payloads.

---

## Phase 11 Release Notes

### Bundle Contract Reset (11.1)
- JSON bundles are now an **unversioned canonical contract**. The `bundle_version` field is no longer emitted by any write path (SRT Gen, SRT Edit save, bundle-from-SRT).
- The v1→v2 migration code (`_normalize_v1`, version-routing in `normalize_bundle`) has been removed from `bundleReader.py`. The reader now uses a single normalization path.
- All bundle tests have been rewritten to exercise the unversioned contract and round-trip behavior.
- Architecture docs (`INDEX.md`, `audio_visualizer.srt.md`, `UI.md`, `audio_visualizer.ui.md`) updated to remove v2/versioning language.

### SRT Edit Waveform Hover Stability (11.2)
- Fixed a `TypeError` crash when hovering subtitle boundaries in the SRT Edit waveform. The `_HoverableRegionItem` hover events were calling `line.pen()` as a method, but PySide6 exposes it as a `QPen` property attribute. Changed to `QPen(line.pen)` copy constructor.
- The hover affordance (border width expansion on enter, restore on leave) is preserved for both segment and word regions.
- Added regression tests exercising the hover enter/leave pen-width behavior.

### Render Composition Graceful Restore (11.3)
- Old composition payloads (pre-center-origin coordinate system) are **still rejected** — no migration code was added.
- The rejection is now handled gracefully: `apply_settings` catches the `ValueError`, logs a warning, shows a user-facing `QMessageBox`, and falls back to the default composition state so the tab remains usable.
- The invalid payload does not re-trigger on subsequent tab activations because the pending settings are consumed on first instantiation.
- Added regression tests for both the warning path (old payload) and the success path (valid payload).

### Code Review (11.4)
- Cleaned up 3 remaining docstring references to bundle versioning in `srt.io.__init__` and `srtGenWorker`.
- Full test suite: **1373 passed**, no regressions from Phase 11 changes.
