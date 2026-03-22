# Phase 3: Render Composition — Coordinates, Layout, and Audio

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 3.

Implement the coordinate-system break plus the layout, audio, and layer-management changes that do not require the new real-time playback engine.

### 3.1: Center-Origin Coordinate System

Switch Render Composition from top-left origin to center origin.

**Tasks:**
1. Add `center_x` and `center_y` user-facing position properties to `CompositionLayer`.
2. Convert center-origin coordinates to FFmpeg top-left coordinates using:
   - `ffmpeg_x = (output_width / 2) + center_x - (layer_width / 2)`
   - `ffmpeg_y = (output_height / 2) + center_y - (layer_height / 2)`
3. Update `to_dict()` and `from_dict()` to serialize the new coordinate model together with `composition_schema_version`.
4. Update `filterGraph.py` overlay placement to use the center-origin conversion.
5. Update layout presets in `presets.py` so `(0, 0)` means perfectly centered.
6. Update Render Composition UI controls so the X/Y fields display center-origin values.
7. Audit any preview-hit-testing or drag logic that still assumes top-left-origin values and update it to use the new user-facing coordinates.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `src/audio_visualizer/ui/tabs/renderComposition/presets.py`
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`

**Success criteria:** A layer at `(0, 0)` is centered, presets place layers correctly under the new coordinate model, and old composition payloads are rejected instead of being silently mispositioned.

**Close-out:** Add or update tests for center-origin serialization, preset placement, and FFmpeg coordinate math, run the relevant tests and `pytest tests/ -v` when shared composition behavior changed, update `.agents/docs/architecture/` docs if composition contracts changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.2: Settings Panel Layout Fix

Fix label and control alignment in the visual and audio settings panels.

**Tasks:**
1. Rebuild the visual position-and-size controls with a compact `QGridLayout`.
2. Use the row layout:
   - Row 0: X and Y,
   - Row 1: W, H, Lock Ratio,
   - Row 2: Z, Original Size, Fit to Output.
3. Rebuild the audio settings area with a `QFormLayout`.
4. Keep the audio controls grouped as Name, Source, Start, Duration plus Full Length, Volume, and Mute.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`

**Success criteria:** Visual and audio controls are aligned, compact, and readable without the current large label/input gaps.

**Close-out:** Add or update UI tests for the new control layout where practical, run the relevant tests and `pytest tests/ -v` when shared composition UI changed, update `.agents/docs/architecture/` docs if UI structure changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.3: Audio Volume and Mute Controls

Add volume and mute controls to composition audio layers.

**Tasks:**
1. Add `volume: float` and `muted: bool` to `CompositionAudioLayer`.
2. Persist the new audio-layer fields in `to_dict()` and `from_dict()`.
3. Add a volume slider and mute toggle in the audio-layer settings panel.
4. Add a mute toggle on timeline audio items and visually dim muted tracks.
5. Update `filterGraph.py` so audio layers apply a `volume=` filter when active and are omitted from the audio mix when muted.
6. Add undo commands for volume changes and mute toggles.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `src/audio_visualizer/ui/tabs/renderComposition/commands.py`

**Success criteria:** Volume changes affect rendered output, mute can be toggled from both settings and timeline UI, muted tracks are visually distinct, and undo/redo covers both operations.

**Close-out:** Add or update tests for audio-layer persistence, mute handling, volume filters, and undo behavior, run the relevant tests and `pytest tests/ -v` when shared composition behavior changed, update `.agents/docs/architecture/` docs if audio-layer behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.4: Visual Asset Resize Controls

Add ratio lock and quick-resize helpers for visual layers.

**Tasks:**
1. Add a default-on "Lock Ratio" checkbox for visual resizing.
2. Add an "Original Size" action that restores source-media dimensions.
3. Add a "Fit to Output" action that scales to the output size while respecting ratio lock when enabled.
4. Reuse existing undoable size-change commands where possible instead of introducing parallel state paths.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`

**Success criteria:** Users can resize visual layers proportionally, restore source size, and fit a layer to the output area with correct undo support.

**Close-out:** Add or update tests for ratio locking and resize helpers where practical, run the relevant tests and `pytest tests/ -v` when shared composition UI changed, update `.agents/docs/architecture/` docs if resize behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.5: Track Ordering on the Timeline

Sort track rows so the timeline reflects the intended stacking order.

**Tasks:**
1. Sort visual tracks by Z order descending so the highest Z appears at the top.
2. Display audio tracks below visual tracks in audio-layer list order.
3. Update drag-reorder behavior so the rendered ordering invariant is preserved after user interaction.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`

**Success criteria:** The timeline consistently shows highest-Z visual layers first and audio layers below them without letting drag interactions break that rule.

**Close-out:** Add or update tests for track ordering and drag behavior, run the relevant tests and `pytest tests/ -v` when shared composition timeline behavior changed, update `.agents/docs/architecture/` docs if timeline ordering changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.6: Video-with-Audio Dual Track Insertion

Automatically create linked visual and audio layers when a source video contains audio.

**Tasks:**
1. Extend `_probe_media_dimensions()` so it also reports whether a source file has one or more audio streams.
2. When a video with audio is added, create both a `CompositionLayer` and a `CompositionAudioLayer`.
3. Add `linked_layer_id` to both model types and persist it.
4. On delete of either linked layer, show a three-way confirmation dialog: Delete both, Delete only this, Cancel.
5. Add undo support for linked layer creation and linked delete actions.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `src/audio_visualizer/ui/tabs/renderComposition/commands.py`

**Success criteria:** Adding a video with audio creates linked visual and audio tracks automatically, deletion prompts behave correctly, and linked state survives persistence and undo/redo.

**Close-out:** Add or update tests for linked-layer creation, persistence, and delete behavior, run the relevant tests and `pytest tests/ -v` when shared composition ingest behavior changed, update `.agents/docs/architecture/` docs if media-ingest behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 3.7: Phase 3 Review

**Tasks:**
1. Review coordinate, audio-layer, layout, and linked-layer changes together to verify there are no conflicting assumptions.
2. Remove any leftover top-left-origin logic or dead UI paths replaced by the new controls.
3. Verify tests cover persistence, filter-graph output, and user interaction paths touched in this phase.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 3 implementation files
- Phase 3 tests

**Success criteria:** Phase 3 leaves Render Composition internally consistent before the real-time playback engine is introduced.

### 3.8: Phase 3 Changelog

**Tasks:**
1. Summarize the coordinate-system break, audio controls, layout fixes, and linked-layer behavior added in Phase 3.
2. Note any UX or serialization assumptions that Phase 4 must preserve.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 3 implementation notes

**Success criteria:** The next Render Composition phase can build on stable coordinate, layout, and media-layer behavior.
