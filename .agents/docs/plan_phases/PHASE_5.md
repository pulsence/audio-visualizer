# Phase 5: Build the Caption Animate Tab

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 5.1: Create the Caption Animate UI and full preset workflow

The caption tab should expose the full capability of the integrated `audio_visualizer.caption` package while supporting all three approved preset-source paths: built-ins, explicit files, and the app-data preset library.

**Tasks:**
- Create `CaptionAnimateTab` with subtitle input, output path, FPS, quality, safety scale, animation toggle, and reskin controls
- Build a unified preset-selection workflow that combines built-ins, explicit file browse, and the app-data preset library. Leverage `ensure_example_presets()` (called internally by the caption package's data-dir helpers) to seed bundled example preset files (`preset.json`, `word_highlight.json`) into `get_data_dir()/caption/presets/` on first access so the library is not empty on initial launch.
- Expose the full `PresetConfig` style surface in structured groups (font, colors, outline, shadow, blur, line spacing, max width, padding, alignment, margins, wrap style, animation type and params) rather than limiting the tab to preset-only controls
- Expose the built-in animation registry types (`fade`, `slide_up`, `scale_settle`, `blur_settle`, `word_reveal`) plus their default parameter surfaces so users can edit animation behavior without leaving the GUI
- Add preset import/export and "open preset folder" actions backed by the app-data directory
- Add a lightweight in-tab preset preview for style validation before full render. v0.6.0 uses a static sample-text preview inside the tab; full motion preview remains the responsibility of an actual render.
- Ensure file pickers can browse both the filesystem and compatible subtitle assets from `SessionContext`
- Create/update tests for preset-source resolution, settings round-trip, and full-surface preset serialization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_caption_tab.py`

**Success criteria:** The Caption Animate tab supports the full caption-style surface and all approved preset-source paths without depending on cwd-relative discovery.

### 5.2: Implement cancellable caption rendering

Caption rendering is synchronous today, but the underlying FFmpeg boundary makes true in-process cancel support achievable for Stage Three.

**Tasks:**
- Create a caption-render Qt worker that owns progress/event bridging, process handle retention, cancel-state updates, and output registration
- Modify the caption render stack so the worker can terminate the active FFmpeg subprocess cleanly on user cancel
- Preserve stage/progress events and completion/error payloads from the caption package through the worker bridge
- Ensure cancellation cleans up partial outputs and resets tab/job-shell state correctly
- Register finished caption renders as `SessionAsset` entries with alpha, resolution, duration, and quality metadata
- Create/update tests for render-worker lifecycle, progress forwarding, cancel behavior, and output registration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- Modify `src/audio_visualizer/caption/captionApi.py`
- Modify `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Create `tests/test_caption_render_worker.py`

**Success criteria:** Caption Animate renders can be started, monitored, canceled, and reused downstream as metadata-rich overlay assets.

### 5.3: Add audio-reactive caption support

Audio-reactive captions are the most distinctive Caption Animate feature in Stage Three and need both a shared analysis bundle and render-pipeline support for passing reactive context into animations.

**Tasks:**
- Add audio-source selection to the caption tab, using either a directly chosen file or a `SessionContext` asset role
- Build a shared audio-analysis bundle with smoothed amplitude, emphasis/peak markers, and optional chroma summaries using the existing audio-analysis stack. **Important:** `AudioData.analyze_audio()` is synchronous with per-frame librosa chroma computation and has no progress reporting infrastructure. Audio analysis must run on a background thread through the worker bridge to avoid UI freezes on long audio files, and should forward progress updates so the tab can show analysis status before the render begins.
- Reuse the `SessionContext` analysis cache so caption re-renders do not recompute audio analysis unnecessarily
- Extend the caption render pipeline so `event_context` or equivalent per-event reactive data reaches the animation layer. Note that `SubtitleFile.apply_animation()` currently does **not** pass `event_context` to animations — the render pipeline must be extended so audio-reactive analysis data flows through `apply_to_event()` and into `generate_ass_override(event_context)` for reactive animations to function.
- Ship a bounded preset family such as `pulse`, `beat_pop`, and `emphasis_glow` instead of a freeform animation graph
- Keep reactive motion bounded and readability-safe by default
- Create/update tests for audio-analysis reuse, reactive-preset mapping, and render-pipeline event-context flow
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/caption/core/subtitle.py`
- Modify `src/audio_visualizer/caption/animations/baseAnimation.py`
- Create `src/audio_visualizer/caption/core/audioReactive.py`
- Create `tests/test_caption_audio_reactive.py`

**Success criteria:** Caption Animate can render bounded audio-reactive caption presets using shared audio analysis, and the render pipeline now has a real path for per-event reactive context.

### 5.4: Phase 5 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify preset management, cancel behavior, and audio-reactive rendering all work from the same tab state and asset model

**Phase 5 Changelog:**
- Added a full-surface Caption Animate tab with built-in, file-based, and app-data preset workflows
- Implemented cancellable caption rendering around the FFmpeg process boundary
- Added shared-analysis-driven audio-reactive caption presets
