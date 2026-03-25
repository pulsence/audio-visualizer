# Phase 14: Refinement - 4

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 14.

This phase is a targeted Render Composition refactor pass focused on stability, clearer ownership boundaries, and preview/export timing parity. It exists because the issues discovered in the earlier refinement phases point to structural coupling in the editor, preview, playback, and export pipeline rather than to one isolated bug.

## Render Composition Refactor Callout

Phase 14 is a deliberate Render Composition refactor phase, not a generic cleanup bucket. It is being added because the recent refinement work has repeatedly found stability issues at the same architectural seams, which is a sign that localized fixes are no longer enough.

### Exact Pain Points

- `RenderCompositionTab` currently combines model mutation, timeline/list synchronization, property-panel loading, preview scheduling, playback transport, engine loading, and render-job orchestration in one large UI class. That coupling makes small timeline interactions fan out into multiple state changes and refresh paths.
- Live preview and final export still derive timing behavior through separate code paths. Preview/playback timing lives in `playbackEngine.py`, while export timing and FFmpeg behavior live in `filterGraph.py`, which leaves loop, trim, source-time mapping, and after-end behavior vulnerable to parity drift.
- The same composition state is translated repeatedly into multiple mutable forms: `CompositionModel`, `TimelineItem` rows, layer-list rows, property widgets, playback-engine layer dicts, and FFmpeg command inputs. Nearly every edit has to manually re-synchronize those views.
- `PlaybackEngine` currently owns decode-worker lifecycle, stopped-state synchronous frame decode, audio predecode/playback, compositor updates, and state transitions together. That concentration of responsibilities makes load/seek/play/pause/stop behavior hard to reason about and hard to harden.
- Recent crash fixes have already required more guard logic and event-loop deferral around drag/preview interactions. That is useful as a short-term safety measure, but it is also evidence that the current interaction boundary between UI events and preview execution is too re-entrant and fragile.

### Why This Refactor Needs to Happen Before Release

- Continuing to patch these issues locally will keep adding special cases without reducing the underlying risk.
- Render Composition is one of the most complex and user-visible workflows in v0.7.0; unstable preview/playback behavior undermines editing confidence and can also hide preview/export mismatches.
- Final review and release-preparation work should happen only after the preview, playback, and export responsibilities are consolidated behind clearer contracts and more testable boundaries.

## Reported Changes to Make

- Render Composition
  - Refactor the Render Composition editor so timeline edits, preview scheduling, playback transport, engine loading, and render orchestration are no longer tightly interleaved in one tab class.
  - Introduce one canonical timeline/layer-evaluation contract that both live preview and final FFmpeg export use for activity windows, source-time mapping, loop behavior, and after-end behavior.
  - Remove re-entrant update chains where a model mutation immediately fans out into UI rebuilds, preview reloads, engine seeks, and layer-preview refreshes inside the same interaction path.
  - Reduce duplicate state translation between `CompositionModel`, `TimelineItem`, playback-engine layer dicts, list rows, and property widgets.
  - Harden playback and preview lifecycle management around load, seek, play, pause, stop, worker cleanup, and failure surfacing.
  - Add automated regression coverage and an explicit manual verification checklist for the interaction paths most likely to crash or drift.
- Architecture / Shared Rendering Docs
  - Update the architecture documentation so the extracted responsibilities and shared timing contract are documented clearly.

## Phase 14 Planning Notes

- This is a refactor/stability phase, not a net-new workflow feature phase.
- Preserve the Phase 3 center-origin composition contract and the Phase 4 OpenGL-backed preview path as the normal capable-runtime workflow.
- Prefer extracting pure, testable helpers/services over adding more guards or branching directly inside `RenderCompositionTab`.
- The refactor should reduce responsibility overlap between UI event handlers and native/media lifecycle code.
- Final export behavior should stay compatible with the current composition model; this phase is about making the implementation more robust and maintainable, not about changing the saved-project contract again.

## Phase 14 Resolved Findings

- `RenderCompositionTab` currently mixes editing UI, state synchronization, preview scheduling, playback coordination, and render-job wiring, which makes small changes in one interaction path cascade into unrelated behavior.
- Timing semantics are duplicated between live preview/playback and export command generation, so trim, loop, start offset, and after-end behavior can drift between what the user sees and what FFmpeg renders.
- The editor repeatedly converts the same composition state into multiple mutable forms, which creates manual resynchronization work after move, trim, reorder, mute, selection, and property-edit operations.
- `PlaybackEngine` currently owns worker lifecycle, synchronous stopped-state seeking, audio decode/playback, compositor output, and state transitions together, making native-resource timing failures difficult to isolate.
- The recent refinement fixes around drag and preview behavior have increasingly relied on targeted guards and deferred execution, which is a strong sign that the current UI-to-preview execution boundary needs a structural cleanup.

### 14.1: Canonical Timeline Evaluation Contract

**Contract shape:** Create a new module `src/audio_visualizer/ui/tabs/renderComposition/evaluation.py` containing pure functions that accept only `CompositionLayer`, `CompositionAudioLayer`, and `CompositionModel` instances and return computed timing results. The core functions should include:

- `evaluate_visual_layer(layer, composition_ms) -> VisualLayerEval` — Returns a dataclass/namedtuple with fields: `is_active: bool`, `source_time_ms: int | None`, `is_looping: bool`, `loop_iteration: int`. This replaces the inline logic currently in `PlaybackEngine._layer_source_position_ms()` and the parallel `_build_enable_expr()` / `_build_visual_stream_filter()` logic in `filterGraph.py`.
- `evaluate_audio_layer(audio_layer, composition_ms) -> AudioLayerEval` — Returns: `is_active: bool`, `source_time_ms: int | None`, `effective_duration_ms: int`. This replaces the inline offset/duration checks in `_AudioPlayer._audio_callback()` and the parallel `atrim`/`adelay` construction in `build_ffmpeg_command()`.
- `compute_composition_duration_ms(model) -> int` — Canonical duration from all enabled layers, replacing `model.get_duration_ms()` as the single source of truth.
- `visual_needs_input_loop(layer) -> bool` — Whether the layer's effective duration exceeds source duration and requires looping at the input level. This replaces the duplicate `requested > source_duration_ms` checks in both `_add_visual_input()` and `_VideoDecodeWorker`.
- `audio_needs_input_loop(audio_layer) -> bool` — Same for audio layers.

**Behavior-after-end semantics to unify:**
- `"hide"` — Layer is inactive after source exhaustion within its timeline window. Preview returns `None`; export uses the existing `enable=` time gate.
- `"freeze_last_frame"` — Layer holds its last decoded frame for the remainder of its timeline window. Preview returns `source_duration_ms - 1`; export should use `tpad=stop_mode=clone` after the trim filter to extend the last frame.
- `"loop"` — Layer restarts from source frame 0 when source is exhausted. Preview returns `source_ms % source_duration_ms`; export uses `-stream_loop -1` at the input level (already implemented) plus a trim to the effective window duration.

Note: `_build_behavior_filter()` in `filterGraph.py` currently returns `""`, meaning freeze-last-frame has no FFmpeg-side implementation. This sub-phase must close that gap by generating the appropriate `tpad` filter when `behavior_after_end == "freeze_last_frame"`, or document that freeze is only supported in preview until a later phase.

**Tasks:**
1. Create `src/audio_visualizer/ui/tabs/renderComposition/evaluation.py` with the pure functions and result types described above.
2. Refactor `PlaybackEngine._layer_source_position_ms()` to call `evaluate_visual_layer()` instead of carrying its own activity/loop/freeze logic.
3. Refactor `_AudioPlayer._audio_callback()` to call `evaluate_audio_layer()` for per-layer activity checks instead of inline offset/duration math.
4. Refactor `filterGraph.py` to call `visual_needs_input_loop()`, `audio_needs_input_loop()`, and derive enable expressions and trim values from the shared evaluation functions rather than re-implementing the same checks.
5. Implement the `tpad`-based freeze-last-frame filter in `filterGraph.py` or document the gap explicitly if deferred.
6. Add focused unit tests for `evaluation.py` covering: move, trim, start offset, loop iteration, freeze-last-frame, hide-after-end, audio activity windows, and composition-duration calculations.
7. Run tests: `pytest tests/ -v`.
8. Update `.agents/docs/` architecture documentation as needed.
9. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/tabs/renderComposition/evaluation.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `tests/test_composition_filter_graph.py` (export timing parity tests)
- Create `tests/test_composition_evaluation.py` (shared contract unit tests)

**Success criteria:** Preview and export timing semantics are derived from one shared, testable contract, reducing parity drift and hidden duplication. Both `playbackEngine.py` and `filterGraph.py` import from `evaluation.py` instead of carrying parallel timing logic.

### 14.2: Preview and Playback Lifecycle Separation

**New module:** Create `src/audio_visualizer/ui/tabs/renderComposition/previewController.py`. This controller absorbs the preview scheduling responsibilities currently spread across `RenderCompositionTab`:
- Owns `_preview_model_dirty`, `_pending_preview_seek_ms`, and the `_preview_seek_timer` (currently a 0ms `QTimer` in the tab).
- Provides a `schedule_seek(ms)` method that the tab's timeline, property, and playhead handlers call instead of directly invoking `_schedule_preview_seek()` → `_flush_preview_seek()` → `_seek_preview()` → `_load_engine_data()` chains.
- Coalesces rapid seek requests (e.g., during playhead scrubbing or spin-box changes) into a single engine operation per event-loop turn.
- Manages the dirty-state flag so that model mutations mark the controller dirty, and the next scheduled seek triggers an engine reload automatically.
- Delegates actual engine calls (`load()`, `seek()`, `seek_from_timeline()`) to `PlaybackEngine` but owns the decision of when to call them.

**Failure surfacing:** The tab already has `self._preview_status_label` near the transport controls. The preview controller should update this label with a brief message (e.g., "Preview failed — decode error") when `_seek_preview()` or engine load raises, instead of silently catching and debug-logging the exception as the current `_seek_preview()` does.

**Tasks:**
1. Create `previewController.py` with the responsibilities described above, extracting `_mark_preview_dirty()`, `_schedule_preview_seek()`, `_flush_preview_seek()`, `_seek_preview()`, `_load_engine_data()`, and `_update_layer_preview_from_engine()` from `RenderCompositionTab`.
2. Update `RenderCompositionTab` to instantiate `PreviewController` and route all preview-related calls through it. Timeline, property, and playhead handlers should call `self._preview_controller.schedule_seek(ms)` instead of directly invoking engine methods.
3. Define explicit load/play/pause/seek/stop lifecycle and cleanup boundaries for decode workers, audio playback, and compositor resources in `PlaybackEngine`.
4. Update `_preview_status_label` on preview-start and preview-seek failures with a user-readable message instead of relying only on `logger.debug`.
5. Add automated regression coverage for stopped, paused, and actively playing preview transitions, and for coalesced seek behavior.
6. Run tests: `pytest tests/ -v`.
7. Update `.agents/docs/` architecture documentation as needed.
8. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/tabs/renderComposition/previewController.py`
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`
- `tests/test_ui_render_composition_tab.py` (preview lifecycle and transport tests)

**Success criteria:** Preview updates remain live, but the UI no longer relies on re-entrant direct engine work during edit interactions, and playback state transitions are explicit and testable.

### 14.3: Editor State and View Synchronization Cleanup

**Synchronization approach:** Currently every edit handler (`_on_timeline_item_moved`, `_on_timeline_item_trimmed`, property-change handlers, etc.) independently calls `_refresh_layer_list()` → `_refresh_timeline()`, `_load_layer_properties()` / `_load_audio_layer_properties()`, `settings_changed.emit()`, and `_schedule_preview_seek()`. This creates a pattern where forgetting any one of those calls in a new handler silently breaks sync.

The cleanup should introduce a single `_sync_views_after_edit(affected_layer_id: str | None = None)` method that:
1. Rebuilds the layer list (`_refresh_layer_list()`, which already chains into `_refresh_timeline()`).
2. Reloads the property panel for the currently selected layer (or `affected_layer_id` if provided).
3. Emits `settings_changed`.
4. Routes through the preview controller's `schedule_seek()` (from 14.2).

All edit handlers should call `_sync_views_after_edit()` instead of manually chaining the four separate calls. The method should accept an optional layer ID so that property-panel reload targets the correct layer after reorder operations that change list indices.

Selection retention should be handled inside `_refresh_layer_list()` by matching on layer ID (as it already attempts), but the current implementation can lose selection when the `_updating_ui` guard interacts with signals. The cleanup should ensure that `currentRowChanged` signals emitted during `_refresh_layer_list()` are suppressed via the existing `_updating_ui` flag and that selection is always restored by ID, not by row index.

**Tasks:**
1. Add `_sync_views_after_edit(affected_layer_id=None)` to `RenderCompositionTab` that encapsulates the layer-list rebuild, property-panel reload, settings-changed emission, and preview scheduling.
2. Refactor all edit handlers (`_on_timeline_item_moved`, `_on_timeline_item_trimmed`, `_on_position_changed`, `_on_size_changed`, `_on_timing_changed`, `_on_behavior_changed`, `_on_matte_changed`, `_on_audio_layer_edited`, `_on_layer_list_reordered`, etc.) to call `_sync_views_after_edit()` instead of manually chaining refresh and preview calls.
3. Fix selection retention in `_refresh_layer_list()` to match on layer ID consistently and suppress spurious `currentRowChanged` signals during rebuild.
4. Add regression coverage for selection retention after move/trim/reorder, timeline/list parity after property edits, and property panel synchronization after timeline drags.
5. Run tests: `pytest tests/ -v`.
6. Update `.agents/docs/` architecture documentation as needed.
7. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `tests/test_ui_render_composition_tab.py` (sync and selection retention tests)
- `tests/test_ui_render_composition_timeline_widget.py` (timeline/list parity tests)

**Success criteria:** Render Composition editing paths no longer depend on repeated manual full-refresh logic to keep the UI consistent, and synchronization regressions are substantially harder to reintroduce.

### 14.4: Export Path Alignment and Stability Hardening

**Scope clarification:** The primary timing-parity work in this sub-phase targets `filterGraph.py`, which is where FFmpeg command generation builds its own parallel timing logic. `compositionWorker.py` is a subprocess runner (~311 lines) that already deep-copies the model at init and delegates command construction to `build_ffmpeg_command()`. Changes to `compositionWorker.py` should be limited to consuming the shared evaluation contract's outputs (e.g., `compute_composition_duration_ms()`) instead of re-deriving values, and to any error-reporting improvements — not structural refactoring of the worker itself.

**Known parity gaps to close:**
- `_build_behavior_filter()` returns `""`, so freeze-last-frame has no export implementation. If 14.1 deferred the `tpad` filter, this sub-phase must implement it.
- Audio loop detection in `_add_audio_input()` duplicates `_add_visual_input()` logic. Both should call the shared `visual_needs_input_loop()` / `audio_needs_input_loop()` from `evaluation.py`.
- Audio trim/delay in `build_ffmpeg_command()` computes `effective_duration_ms()` and `start_ms` inline. These should derive from `evaluate_audio_layer()` to stay consistent with preview.

**Tasks:**
1. Refactor `filterGraph.py` to import and use the shared evaluation functions from `evaluation.py` (created in 14.1) for enable expressions, trim values, loop decisions, and behavior-after-end filters.
2. If 14.1 deferred the `tpad`-based freeze-last-frame FFmpeg filter, implement it in this sub-phase.
3. Update `compositionWorker.py` to use `compute_composition_duration_ms()` from the shared contract instead of calling `model.get_duration_ms()` directly, and ensure it passes shared evaluation outputs to `build_ffmpeg_command()` where applicable.
4. Review and close the audio layer parity gaps: ensure `atrim`, `adelay`, and loop behavior in export match the `_audio_callback()` semantics now routed through `evaluate_audio_layer()`.
5. Tighten render error reporting and fallback boundaries so FFmpeg/export failures are easier to diagnose without weakening cancellation or encoder fallback behavior.
6. Add regression tests around command generation and timing parity for the refactored evaluation pipeline.
7. Run tests: `pytest tests/ -v`.
8. Update `.agents/docs/` architecture documentation as needed.
9. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `src/audio_visualizer/ui/tabs/renderComposition/evaluation.py` (consume, not modify)
- `src/audio_visualizer/ui/workers/compositionWorker.py`
- `tests/test_composition_filter_graph.py` (export timing parity and behavior tests)

**Success criteria:** Export follows the same timing semantics as preview, and render failures remain diagnosable without depending on hidden special cases.

### 14.5: Stability Verification and Manual Checklist

**Manual verification scenarios** (to be written as a checklist in the phase documentation):
1. **Multi-layer video+audio preview:** Add 2+ video layers and 1+ audio layers. Play, pause, seek via playhead scrub, resume. Verify audio stays synchronized with video and layers composite correctly at all timestamps.
2. **Drag during stopped preview:** Drag a video layer to a new timeline position while playback is stopped. Verify the preview frame updates to reflect the new position without crash or stale frame.
3. **Trim handles:** Trim a video layer's start and end via timeline handles. Verify the preview updates, the property panel reflects the new values, and the layer list stays in sync.
4. **Seek while paused:** Pause playback, then scrub the playhead. Verify the compositor shows the correct frame at each scrubbed position and no decode worker errors appear in the log.
5. **Playhead scrub during playback:** While playing, grab the playhead and scrub. Verify playback resumes from the scrubbed position on release.
6. **Reorder layers via list drag:** Reorder visual layers in the layer list. Verify z-order updates in both timeline and preview.
7. **Mute/unmute audio during playback:** Toggle audio layer mute while playing. Verify audio output changes immediately.
8. **Preview/export parity:** Set up a composition with loop, freeze-last-frame, and hide behaviors. Export, then compare the exported video against the preview at several timestamps to verify timing matches.
9. **Engine load failure:** Remove or rename a source file while the composition references it. Verify a user-visible message appears in the preview status label rather than a silent failure.
10. **Rapid property edits:** Quickly change position, size, and timing values in the property panel. Verify seeks coalesce and the preview shows the final state without intermediate flicker or crash.

**Tasks:**
1. Add targeted automated coverage for stopped/paused preview seeks, timeline drag/trim/reorder interactions, play/pause/seek/stop transitions, and layer-preview synchronization.
2. Write the manual verification checklist above into the phase documentation.
3. Run the relevant targeted tests and the full suite with `pytest tests/ -v`.
4. Update `.agents/docs/` architecture documentation as needed.
5. Commit and push any cleanup changes from this sub-phase.

**Files:**
- `tests/test_ui_render_composition_tab.py` (lifecycle and transport regression tests)
- `tests/test_ui_render_composition_timeline_widget.py` (drag/trim/reorder interaction tests)
- `tests/test_composition_evaluation.py` (timing parity edge cases)
- Phase 14 documentation

**Success criteria:** The refactor is backed by regression coverage for the failure-prone interaction paths and by a concrete manual checklist for native/runtime-sensitive preview behavior.

### 14.6: Phase 14 Code Review

**Tasks:**
1. Review the changes and ensure the phase is entirely implemented.
2. Review code for deprecated code, dead code, or now-obsolete preview/playback glue left behind by the refactor.
3. Review tests to ensure they are well-structured and that timing-parity and stability coverage are centered on the new shared contracts.
4. Verify the refactor reduced coupling rather than just relocating the same fragility into new modules.
5. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 14 implementation files
- Phase 14 tests

**Success criteria:** The Render Composition refactor leaves the codebase structurally clearer, less coupled, and meaningfully more stable than the pre-refactor implementation.

### 14.7: Phase 14 Changelog

**Tasks:**
1. Summarize the architectural pain points this phase resolved and the new contracts extracted for preview, playback, and export behavior.
2. Record any deliberate decisions about scope, including what the refactor intentionally preserved from Phases 3 and 4.
3. Commit and push any documentation-only cleanup from this sub-phase.

**Files:**
- Phase 14 implementation notes

**Success criteria:** The project has a documented fourth refinement pass that explains both why the refactor was necessary and what stability boundaries it established before final review.

---

## Phase 14 Completion Notes

### Pain Points Resolved

1. **Duplicated timing logic** — `PlaybackEngine._layer_source_position_ms()` and `filterGraph._build_enable_expr()` / `_add_visual_input()` carried parallel implementations of activity windows, loop behavior, freeze-last-frame, and source-time mapping. These are now unified in `evaluation.py`.

2. **Re-entrant preview scheduling** — Preview seek/load/render was interleaved directly in the tab's edit handlers, with manual `_mark_preview_dirty` → `_schedule_preview_seek` → `_flush_preview_seek` → `_seek_preview` → `_load_engine_data` chains. This is now encapsulated in `PreviewController`.

3. **Manual sync chaining** — Every edit handler independently called `_refresh_layer_list()`, `_load_layer_properties()`, `settings_changed.emit()`, and `_schedule_preview_seek()`. Missing any one silently broke sync. Now all handlers call `_sync_views_after_edit()`.

4. **Missing freeze-last-frame export** — `_build_behavior_filter()` returned `""`, so freeze-last-frame had no FFmpeg-side implementation. Now generates `tpad=stop_mode=clone` filters.

5. **Duplicate duration calculations** — `model.get_duration_ms()`, `_duration_seconds()`, and `_load_engine_data()` all computed duration independently. Now all use `compute_composition_duration_ms()`.

### New Contracts Extracted

- **`evaluation.py`** — Pure functions (`evaluate_visual_layer`, `evaluate_audio_layer`, `compute_composition_duration_ms`, `visual_needs_input_loop`, `audio_needs_input_loop`) that both `playbackEngine.py` and `filterGraph.py` import. Result types `VisualLayerEval` and `AudioLayerEval` are frozen dataclasses.

- **`previewController.py`** — `PreviewController` owns dirty-state, coalesced seek timer, engine load/seek coordination, and failure surfacing to the status label.

- **`_sync_views_after_edit()`** — Single method in `RenderCompositionTab` that encapsulates layer-list rebuild, property-panel reload, settings emission, and preview scheduling.

### Deliberate Preservation Decisions

- The Phase 3 center-origin composition coordinate system is preserved. No position math was changed.
- The Phase 4 QPainter compositor path (with OpenGL deliberately disabled for stability) is preserved. No compositor changes were made.
- `CompositionModel.get_duration_ms()` is kept as a model method for backward compatibility with serialization/tests, but production code now calls `compute_composition_duration_ms()`.
- The undo/redo command architecture was not modified; `_sync_views_after_edit` works alongside it.

### Test Coverage

- The Phase 14 refactor added dedicated automated coverage for shared evaluation logic, preview lifecycle behavior, editor/view synchronization, and preview/export timing parity.
- Current review verification: full suite passing with 1428 tests (up from the 1369-test pre-phase baseline recorded in the plan index).

### Manual Verification Checklist

1. Multi-layer video+audio preview: play, pause, seek via playhead scrub, resume
2. Drag during stopped preview: drag a video layer, verify preview frame updates
3. Trim handles: trim start/end, verify preview, property panel, and layer list sync
4. Seek while paused: pause, scrub playhead, verify compositor shows correct frame
5. Playhead scrub during playback: grab playhead while playing, verify resume
6. Reorder layers via list drag: reorder visual layers, verify z-order updates
7. Mute/unmute audio during playback: toggle mute, verify audio output changes
8. Preview/export parity: set up loop/freeze/hide behaviors, export, compare timestamps
9. Engine load failure: remove source file, verify status label message
10. Rapid property edits: quickly change position/size/timing, verify no flicker/crash
