# Phase 6: Build the Render Composition Tab

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 6.1: Finalize the composition asset contract and probing layer

Composition is where all cross-tab assumptions meet, so Stage Three must formalize the metadata contract for reusable assets before the composition UI and renderer are built on top of it.

**Tasks:**
- Define the `SessionAsset` metadata contract Composition requires: width, height, FPS, duration, alpha support, audio presence, source role, and compatibility flags, using the concrete rules from the "Cross-tab asset rules" section above
- Add media probing helpers for video, audio, image, and overlay assets so metadata is captured once and reused
- Decide and encode which intermediate caption/visualizer outputs are composition-ready versus requiring auto-transcode
- Explicitly classify caption-render outputs so `large` is the preferred alpha-ready overlay, `small` requires normalization before trusted reuse, and `medium` is treated as opaque unless normalized or re-rendered
- Add compatibility checks for pixel format, alpha capability, duration mismatches, and embedded-audio behavior
- Encode the rule that Audio Visualizer embedded audio is ignored by default in Composition unless the user explicitly selects it as the authoritative audio source
- Store enough metadata for Composition to make choices without re-probing every source on every selection
- Create/update tests for media probing, compatibility checks, and asset-contract serialization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/mediaProbe.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Create `tests/test_media_probe.py`

**Success criteria:** `SessionContext` assets carry a clear composition contract, and Composition can tell which inputs are ready, which need transcoding, and how each asset should be treated.

### 6.2: Create the composition tab UI, model, and undoable layout editing

The Composition tab should follow the user-approved direction: numeric positioning plus preset layouts with preview, fixed slots with optional extras, and full undo/redo for layout changes.

**Tasks:**
- Create `RenderCompositionTab` with fixed slots for `background` and `audio_source` plus optional overlay layers for visualizer and caption assets
- Add numeric controls for position, size, z-order, start/end time, loop/trim/freeze behavior, and matte/key options
- The tab model should support exactly one authoritative audio source, one background source, and zero-to-many overlay layers. This keeps the UI aligned with the chosen v0.6.0 composition scope without introducing general-purpose multi-track audio mixing.
- Add a composition preview panel that shows the current layout/preset state without requiring a full export
- Implement save/load layout presets and connect them to the shared settings/persistence model
- Ship initial built-in layout presets such as full-screen background with centered visualizer, full-screen background with bottom captions, and picture-in-picture overlay arrangements so preset support is useful immediately
- Add `QUndoCommand` subclasses for move, resize, reorder, source change, add/remove, audio-source change, and apply-preset actions
- Initialize the Render Composition undo stack with a limit of 100 (lower limit than SRT Edit because composition operations are fewer but larger)
- Ensure the tab clears or preserves undo history appropriately when compositions are reset versus edited
- Create/update tests for layout model round-trip, preset application, undo/redo commands, and preview-state synchronization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/__init__.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/presets.py`
- Create `tests/test_ui_render_composition_tab.py`
- Create or modify `tests/test_ui_undo.py`

**Success criteria:** Users can assemble a composition with numeric layout controls, preview it, save/load layout presets, and undo/redo every important layout change.

### 6.3: Implement the FFmpeg-based composition renderer and advanced matte controls

Render Composition should follow the chosen Stage Three direction defined in this plan: an FFmpeg `filter_complex`-based renderer with hybrid direct-render/auto-transcode handling, explicit timeline rules, and richer matte/key control than a simple threshold slider.

**Tasks:**
- Build a composition worker around FFmpeg `filter_complex` generation and subprocess lifecycle management
- Implement layer timeline rules with per-layer start/end times, looping, trimming, freeze-on-last-frame behavior, and final duration defined by the maximum enabled layer end time
- Add explicit audio-source selection and strip rules so embedded audio is only used intentionally. v0.6.0 should choose one audio source, not mix multiple sources together.
- Implement advanced matte controls including key mode, key target, similarity/threshold, softness/blend, cleanup, despill, invert, and debug/alpha-preview modes
- Add auto-transcode paths for incompatible intermediates and reuse direct-in-composition overlays when that produces cleaner output
- Support both composition paths for captions:
  - consume a previously rendered overlay asset from Caption Animate
  - directly render an SRT/ASS source during composition when the user intentionally chooses that path because it produces a cleaner graph
- Register final composition renders as `SessionAsset` entries and route completion through the shared notification/preview flow
- Create/update tests for filter-graph building, timeline math, matte-control serialization, cancel behavior, and final asset registration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/compositionWorker.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_composition_filter_graph.py`
- Create or modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** Composition can export a final render through FFmpeg with explicit audio/timeline behavior, advanced matte controls, cancel support, and metadata-rich output registration.

### 6.4: Phase 6 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify asset probing, layout editing, and final composition rendering all follow the same contract and timeline rules

**Phase 6 Changelog:**
- Finalized the cross-tab asset contract and media probing layer
- Added a preset-driven Composition tab with numeric layout editing and undo/redo
- Implemented FFmpeg-based composition rendering with advanced matte controls and explicit timeline/audio rules
