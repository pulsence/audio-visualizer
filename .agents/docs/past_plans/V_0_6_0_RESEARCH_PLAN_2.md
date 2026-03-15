# v0.6.0 Stage Two Package Integration - Research Plan

## Overview

This research plan covers Stage Two of the v0.6.0 work described in `TODO`: merging the two standalone projects in `Projects to integrate/` into the existing `audio_visualizer` codebase as internal packages:

- `Projects to integrate/Local SRT/` -> `audio_visualizer.srt`
- `Projects to integrate/Caption Animator/` -> `audio_visualizer.caption`

The current repository state on 2026-03-15 contains three distinct codebases:

| Codebase | Current version | Current package root | Primary role |
|----------|-----------------|----------------------|--------------|
| Audio Visualizer | `0.5.1` | `src/audio_visualizer/` | PySide6 desktop app for audio-driven video rendering |
| Local SRT | `0.3.0` | `Projects to integrate/Local SRT/src/local_srt/` | Subtitle generation from media using faster-whisper + ffmpeg |
| Caption Animator | `0.2.1` | `Projects to integrate/Caption Animator/src/caption_animator/` | Subtitle overlay rendering from SRT/ASS using pysubs2 + ffmpeg |

This plan is limited to Stage Two package integration. Stage Three GUI tab work is not designed here, but several sections note boundaries that will affect the later GUI work.

> **Stage Two constraints already decided in `TODO`:**
> - Local SRT becomes an internal `audio_visualizer.srt` package.
> - Caption Animator becomes an internal `audio_visualizer.caption` package.
> - The standalone CLI entry points for both projects no longer remain as user-facing commands.

## 1. Host Application Baseline and Integration Constraints

**Current state - Audio Visualizer today**

| Component | File | Current role |
|-----------|------|--------------|
| App entry | `src/audio_visualizer/visualizer.py` | Starts `QApplication`, creates `MainWindow`, sets icon |
| Main UI | `src/audio_visualizer/ui/mainWindow.py` | Owns layout, current workflow, settings persistence, preview, update checks, and render workers |
| Render pipeline data | `src/audio_visualizer/visualizers/utilities.py` | Defines `AudioData`, `VideoData`, `VisualizerOptions`, and render container setup |
| Visualizer base | `src/audio_visualizer/visualizers/genericVisualizer.py` | Defines the base `Visualizer` interface |
| Settings persistence | `src/audio_visualizer/ui/mainWindow.py` | Serializes only visualizer-related state to JSON |
| Existing tests | `tests/` | Four Python test modules around app paths, logging, and basic media utilities |

**Relevant code paths**

- `MainWindow._start_render(...)` reads UI state, builds `AudioData`, `VideoData`, and a concrete visualizer, then submits `RenderWorker` to a `QThreadPool`.
- `RenderWorker.run()` performs the full render lifecycle: load audio, chunk/analyze it, prepare the output container, encode frames with PyAV, and optionally mux audio.
- `MainWindow._collect_settings()` and `_apply_settings()` currently only know about the existing visualizer workflow. There is no schema for SRT generation, SRT editing, caption rendering, or composition state yet.

**Integration constraints that already exist in the host app**

| Constraint | Evidence in code | Integration effect |
|-----------|------------------|--------------------|
| The app is GUI-first, not library-first | `src/audio_visualizer/visualizer.py`, `src/audio_visualizer/ui/mainWindow.py` | New packages need clear internal APIs because the host app does not currently expose service boundaries |
| Long-running work is driven through Qt workers | `RenderWorker` in `src/audio_visualizer/ui/mainWindow.py` | `audio_visualizer.srt` and `audio_visualizer.caption` need either direct reuse inside new workers or thin adapters |
| Current render backend is PyAV-based | `VideoData.prepare_container()` and `RenderWorker.run()` | Caption integration introduces a second video backend because Caption Animator uses external `ffmpeg` commands |
| Current settings model is visualizer-specific | `MainWindow._collect_settings()` / `_apply_settings()` | Stage Three UI can only proceed cleanly if Stage Two leaves stable package APIs to serialize later |
| Current package surface is small | `src/audio_visualizer/__init__.py` exports only `__version__` | Adding two new internal packages expands the project from one workflow to three |

**Problems or gaps**

- There is no existing `audio_visualizer.srt` or `audio_visualizer.caption` namespace.
- The app has no shared abstraction for non-visualizer jobs such as transcription, subtitle rendering, diagnostics, or model lifecycle management.
- The current app does not check for external `ffmpeg` or `ffprobe` binaries on startup or per-feature use.
- The current test surface does not cover PySide6 view integration, long-running background work beyond the visualizer renderer, or external dependency availability.

**Design options**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| Minimal package merge | Relocate the two codebases largely intact into `audio_visualizer/srt` and `audio_visualizer/caption`, update imports, and defer app-facing adapters to Stage Three | Lowest churn, easiest comparison to upstream code, easiest test porting | Leaves multiple architectural styles inside one repo |
| Shared-service extraction during merge | Introduce common service layers for jobs, ffmpeg helpers, and event forwarding while moving the packages | Cleaner long-term app structure, fewer duplicated integration seams later | Larger Stage Two scope, more refactoring risk, harder to preserve existing behavior |
| Hybrid | Relocate packages mostly intact, but add only a small app-facing wrapper layer for each package (`audio_visualizer.srt.service`, `audio_visualizer.caption.service`) | Preserves source code shape while giving Stage Three stable hooks | Adds one more layer to maintain |

**Current direction after feedback**

- Phase 2 starts with a minimal package merge rather than immediate shared-service extraction.
- Shared-service extraction remains a Phase 3 follow-on research topic once `audio_visualizer.srt` and `audio_visualizer.caption` exist inside the host app.

## 2. Local SRT as `audio_visualizer.srt`

**Current state - Local SRT package layout**

| Area | Files | Current role |
|------|-------|--------------|
| Public API | `Projects to integrate/Local SRT/src/local_srt/api.py` | Exposes `load_model()`, `transcribe_file()`, `transcribe_batch()` and public result dataclasses |
| Package init | `Projects to integrate/Local SRT/src/local_srt/__init__.py` | Lazy-loading `__getattr__` facade that defers imports of `api`, `models`, `events`, and `config` until first access (see Section 4.1) |
| Core pipeline | `Projects to integrate/Local SRT/src/local_srt/core.py` | Converts media to WAV, runs Whisper, applies silence analysis and subtitle generation, writes outputs |
| Whisper wrapper | `Projects to integrate/Local SRT/src/local_srt/whisper_wrapper.py` | Initializes `faster_whisper.WhisperModel` with device/compute-type selection and CUDA fallback logic |
| Model config | `Projects to integrate/Local SRT/src/local_srt/models.py` | Defines `ResolvedConfig`, `PipelineMode`, `SubtitleBlock`, `WordItem` |
| Config presets | `Projects to integrate/Local SRT/src/local_srt/config.py` and `Projects to integrate/Local SRT/configs/*.json` | Built-in presets plus JSON file loading |
| Audio/system helpers | `audio.py`, `system.py`, `model_management.py` | ffmpeg conversion, ffprobe duration probing, diagnostic and model management helpers |
| Text/pipeline heuristics | `text_processing.py`, `subtitle_generation.py`, `alignment.py` | Splitting, timing, corrected-SRT alignment, script alignment |
| Event system | `events.py` | Defines `BaseEvent` hierarchy (`LogEvent`, `WarnEvent`, `ErrorEvent`, `ProgressEvent`, `StageEvent`, `FileStartEvent`, `FileCompleteEvent`, `ModelLoadEvent`), `EventLevel` enum, and `EventEmitter` with subscribe/emit (see Section 4.2 and 4.5) |
| Formatting helpers | `logging_utils.py` | Duration formatting utility (`format_duration()`) |
| Optional diarization | `diarization.py` | Speaker diarization via `pyannote.audio` |
| CLI | `cli.py` | Argument parsing, config merging, model management commands, path expansion, event printing |
| Tests | `Projects to integrate/Local SRT/tests/` | Broad unit coverage plus fixture-driven integration coverage |

**Current library surface already suitable for internal use**

The package already has a library-oriented public API, not just a CLI:

```python
load_model(model_name, device, strict_cuda, event_handler)
transcribe_file(... cfg: ResolvedConfig, model, ..., mode: PipelineMode, ...)
transcribe_batch(... cfg: ResolvedConfig, model, ..., continue_on_error=False, ...)
```

`transcribe_file()` returns a `TranscriptionResult` that already includes:

- `subtitles`
- `segments`
- `device_used`
- `compute_type_used`
- optional side-output paths
- elapsed time

That makes Local SRT a strong candidate for relocation without a full rewrite.

**Pipeline behavior today**

`transcribe_file_internal()` in `core.py` performs the following steps:

1. Check `ffmpeg` availability.
2. Convert the input media to temporary `16kHz` mono WAV.
3. Run `faster_whisper.WhisperModel.transcribe(...)`.
4. Optionally run speaker diarization in transcript mode.
5. Optionally apply corrected-SRT alignment or script-based sentence replacement.
6. Detect silence intervals with ffmpeg.
7. Build subtitle blocks using either segment-level or word-level timing.
8. Write outputs (`.srt`, `.vtt`, `.ass`, `.txt`, or JSON bundle`) plus optional side outputs.

**Problems or gaps for integration**

| Gap | Evidence in code | Why it matters |
|-----|------------------|----------------|
| Import path relocation is required everywhere | all imports are rooted at `local_srt.*` | Direct move to `audio_visualizer.srt` requires systematic import rewriting |
| CLI-only orchestration still owns part of the workflow | `cli.py` handles path expansion, config merging, prompt-file loading, model management commands, and env var handling | Removing the CLI requires deciding which of these concerns move into library helpers and which remain app-only |
| The package assumes external `ffmpeg` and `ffprobe` binaries | `system.py`, `audio.py`, `core.py` | Host app currently does not centralize binary discovery or user messaging for missing binaries |
| Config example files are not package resources today | `pyproject.toml` installs `configs/*.json` as top-level data-files | Internal-package relocation needs a new resource strategy |
| Heavy runtime dependency is introduced | `faster-whisper`, optional `pyannote.audio` | v0.6.0 packaging and installer size may change significantly |
| Model lifecycle is caller-controlled | `api.load_model()` returns a reusable model, but no host-level cache exists | Future GUI workflows may reload models unnecessarily unless the app adds a cache or session manager |

**Design options - module relocation strategy**

| Option | Pros | Cons |
|--------|------|------|
| Preserve the current module layout under `audio_visualizer/srt/*.py` | Lowest risk, easiest test migration, easiest to compare with upstream Local SRT changes | Keeps snake_case module conventions that differ from current host app module naming |
| Restructure during merge into subpackages like `audio_visualizer/srt/core/`, `audio_visualizer/srt/io/`, `audio_visualizer/srt/events/` | Cleaner long-term organization inside the host app | Higher migration cost, more path churn, more broken-import risk |
| Keep source layout but add a thin `audio_visualizer.srt.__init__` facade | Stable app-facing API with low internal churn | Internal structure remains mixed relative to the host app's existing style |

**Current direction after feedback**

Phase 2 should restructure the Local SRT code into internal subpackages during the merge. That increases relocation churn, but it keeps the cleanup scoped inside `audio_visualizer.srt` rather than turning Phase 2 into a full app-wide shared-service rewrite.

**Design options - model lifecycle**

| Option | Pros | Cons |
|--------|------|------|
| Caller-managed reuse via existing `load_model()` | Already supported, minimal code changes, easy to embed into a future Qt worker | GUI layer must decide caching and teardown behavior |
| Add an app-scoped model manager inside `audio_visualizer.srt` | Central place for reuse, diagnostics, and future settings-driven model switching | Adds new stateful behavior that does not exist today |
| Load the model per transcription job | Simplest to reason about, no shared mutable state | Slow repeated runs, more memory churn, weak fit for GUI iteration |

**Design options - feature retention after CLI removal**

| Feature area | Current code | Can exist without the standalone CLI? | Notes |
|--------------|--------------|---------------------------------------|------|
| Single-file transcription | `api.transcribe_file()` | Yes | Already library-ready |
| Batch transcription | `api.transcribe_batch()`, `batch.py` | Yes | Existing API covers the core batch loop |
| Output format selection | `output_writers.py` | Yes | `.srt`, `.vtt`, `.ass`, `.txt`, and JSON bundle already live in library code |
| Prompt/script `.docx` support | `script_reader.py`, `cli.py`, `core.py` | Yes | `python-docx` remains required if retained |
| Corrected SRT alignment | `alignment.py`, `core.py` | Yes | Already library code |
| Diarization | `diarization.py`, `core.py` | Yes | Depends on optional extra and HF token handling |
| Diagnostics and model cache management | `model_management.py`, `cli.py` | Yes, but surface changes | Need a new app-facing location if the feature remains user-visible |

**Current direction after feedback**

The retained Local SRT surface is no longer an all-or-nothing question. The current direction is feature-specific:

| Feature | Direction | Notes |
|---------|-----------|-------|
| Batch transcription API | Drop from the merged package | The current plan does not carry multi-file transcription into Phase 2 |
| Non-SRT output formats (`.vtt`, `.ass`, `.txt`, JSON bundle) | Keep in Phase 2 | Broader output support remains part of the merged package |
| Word-level outputs and Shorts mode | Keep in Phase 2 | Later GUI integration should connect this to the Caption Animate workflow |
| Corrected-SRT alignment | Keep in Phase 2 | Later GUI integration should expose it through the SRT Edit workflow |
| Script alignment | Keep in Phase 2 | Later GUI integration should expose it through the SRT Edit workflow |
| Prompt-file loading (`.txt` / `.docx`) | Keep in Phase 2 | Later GUI integration should expose it through the SRT Gen workflow |
| Speaker diarization | Keep in Phase 2 | UI exposure can begin as a stub and expand later in transcript-editing workflows |
| Model diagnostics and cache-management helpers | Keep in Phase 2 | Likely exposed later via menu-bar actions or a settings popout rather than a primary tab |
| Debug-oriented file controls (`keep_wav`, side outputs, debug artifacts) | Keep in Phase 2 | Better fit for a settings popout than the main tab surface |

**Stage Three relevance**

Local SRT already returns both subtitle blocks and raw segment data. That is directly relevant to later GUI tabs:

- `SRT Gen` can build on `ResolvedConfig`, `PipelineMode`, and `TranscriptionResult`.
- `SRT Edit` can build on returned segments, subtitles, and word-level outputs, instead of re-parsing a generated file as its only input.

## 3. Caption Animator as `audio_visualizer.caption`

**Current state - Caption Animator package layout**

| Area | Files | Current role |
|------|-------|--------------|
| Public API | `Projects to integrate/Caption Animator/src/caption_animator/api.py` | Exposes `render_subtitle()`, `RenderConfig`, `RenderResult`, preset and animation listing |
| Package entry | `__init__.py`, `__main__.py` | Version export and `python -m caption_animator` CLI entry |
| Subtitle manipulation | `core/subtitle.py`, `core/style.py`, `core/sizing.py` | Loads SRT/ASS with `pysubs2`, applies styles/animations, computes overlay size |
| Text utilities | `text/measurement.py`, `text/wrapper.py`, `text/utils.py` | Font-based text measurement, line wrapping, and text helper functions used by sizing |
| Presets | `core/config.py`, `presets/defaults.py`, `presets/loader.py` | Built-in presets plus JSON/YAML loading |
| Rendering backend | `rendering/ffmpeg.py` | Renders transparent overlays with external `ffmpeg` and libass |
| Event system | `core/events.py`, `rendering/progress.py` | `RenderEvent` dataclass, `EventType` enum, `EventEmitter` with subscribe/unsubscribe/emit, `ProgressTracker` for step events (see Section 4.2 and 4.5) |
| Animation plugins | `animations/base.py`, `animations/registry.py`, `animations/fade.py`, `animations/slide.py`, `animations/scale.py`, `animations/blur.py`, `animations/word_reveal.py` | Base animation class, plugin registry, and five animation types (fade, slide, scale, blur, word-reveal) |
| File utilities | `utils/files.py` | File path and I/O helper functions |
| CLI | `cli/args.py`, `cli/commands.py`, `cli/main.py`, `cli/interactive.py` | Argument parsing, command definitions, batch mode, interactive tweaking, stderr progress, keep-temp/keep-ass flows |
| Tests | `Projects to integrate/Caption Animator/tests/` | Unit-focused coverage for sizing, measurement, wrapping, and word-reveal behavior |

**Current library surface already suitable for internal use**

```python
render_subtitle(
    input_path,
    output_path,
    config: Optional[RenderConfig] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    on_event: Optional[Callable[[RenderEvent], None]] = None,
) -> RenderResult
```

`render_subtitle()` already handles:

- input validation for `.srt` and `.ass`
- preset loading
- style application
- optional animation injection
- overlay size calculation
- ASS generation
- final ffmpeg render

The function returns `success`, `output_path`, `width`, `height`, `duration_ms`, and `error`.

**Rendering behavior today**

`caption_animator.api.render_subtitle()` builds a working ASS file in a temporary directory, then `rendering/ffmpeg.py` runs an external `ffmpeg` command using:

- a transparent `lavfi` color input
- the `subtitles=...:alpha=1` filter
- codec presets chosen by the `quality` argument

The renderer currently writes a video-only overlay (`-an`), not a composed output with audio.

**Problems or gaps for integration**

| Gap | Evidence in code | Why it matters |
|-----|------------------|----------------|
| Import path relocation is required everywhere | imports are rooted at `caption_animator.*` | Direct move to `audio_visualizer.caption` requires systematic import rewriting |
| Rendering backend is external ffmpeg, not PyAV | `rendering/ffmpeg.py` | Host app gains a second media backend with its own error handling and binary requirements |
| Preset search path is cwd-relative | `PresetLoader(... preset_dirs or [Path("presets")])` | Embedded app usage should not depend on the process working directory |
| Font measurement can be environment-dependent | `SizeCalculator._load_font()` tries a `font_file` first, then common fallback fonts | Overlay sizing can vary across systems unless fonts are packaged or user-selected |
| CLI duplicates core orchestration | `cli/main.py` and `cli/interactive.py` repeat large parts of the API pipeline when `keep_ass`, `keep_temp`, or interactive tweaking is used | CLI removal can reduce code, but it also means deciding whether those debug flows survive elsewhere |
| Some config fields appear unused by the current render path | `PresetConfig` includes `video_codec`, `video_quality`, `h264_crf`, `prores_profile`, but `FFmpegRenderer` keys off the separate `quality` argument | Integration is a chance to decide whether those preset fields remain, move, or disappear |
| Some CLI flags are parser-only today | `cli/args.py` defines `--strip-overrides` and `--no-preset-for-ass`, but those flags do not appear in the rendering code paths inspected here | Stage Two does not need to preserve parser surface that is not connected to library behavior |

**Design options - library boundary**

| Option | Pros | Cons |
|--------|------|------|
| Preserve the current high-level API and low-level classes, remove only `cli/` | Lowest-risk merge, Stage Three can call `render_subtitle()` immediately | Keeps Caption Animator's event model and ffmpeg subprocess backend separate from the host app's render conventions |
| Add a new `audio_visualizer.caption.service` layer over the current internals | Gives the future GUI a narrower, app-shaped API | Extra abstraction work before the GUI layer exists |
| Expose only low-level building blocks (`SubtitleFile`, `StyleBuilder`, `SizeCalculator`, `FFmpegRenderer`) and let the app orchestrate them | Maximum host control | Recreates orchestration that already exists and is currently tested |

**Current direction after feedback**

- Phase 2 preserves the current high-level Caption Animator API as the app-facing entry point.
- Phase 3 should revisit whether a deeper `audio_visualizer.caption` service layer is worth introducing once the package is in use inside the broader system.

**Design options - rendering backend**

| Option | Pros | Cons |
|--------|------|------|
| Keep the current external ffmpeg/libass renderer | Already implemented, supports transparent overlay video generation, matches current Caption Animator behavior | Requires external binaries and separate progress/error handling |
| Rewrite toward a shared PyAV-based backend | Potential long-term media-stack consistency inside `audio_visualizer` | Large scope increase; current code relies on ASS rendering via libass and would need major replacement work |
| Hybrid: keep ffmpeg renderer now, define app-facing metadata objects for later composition | Small merge diff with a better seam for Stage Three | Two backends still coexist inside the repository |

**Current direction after feedback**

- Phase 2 keeps the existing external ffmpeg/libass renderer.
- Phase 3 should explicitly research whether a PyAV-based caption backend is worth the rewrite cost.

**Design options - preset and resource handling**

| Option | Pros | Cons |
|--------|------|------|
| Built-in presets only | Deterministic and package-local | Drops file-based preset workflows |
| Package resource presets under `audio_visualizer/caption/...` | Keeps flexible preset loading while avoiding cwd dependence | Requires resource-loading changes and packaging decisions |
| Store editable presets in the app's config/data directory | Fits a future GUI preset editor | Requires a new preset management story that does not exist today |

**Stage Three relevance**

Caption Animator's current output model already fits a later composition workflow:

- It renders a transparent overlay video.
- It reports final dimensions and duration.
- It already separates subtitle styling/rendering from final composition.

That means Stage Three can treat caption renders as an asset source, even if Stage Two does not yet design the composition screen itself.

## 4. Shared Integration Seams Across Both Packages

### 4.1 Dependency and runtime alignment

| Dependency area | Audio Visualizer today | Local SRT adds | Caption Animator adds |
|-----------------|------------------------|----------------|-----------------------|
| Python package deps | `av`, `librosa`, `numpy`, `Pillow`, `PySide6` | `faster-whisper`, `python-docx` | `pysubs2`, `PyYAML`, `Pillow` already present |
| Optional Python deps | none in runtime | `pyannote.audio` via `[diarize]` | none |
| External binaries | none checked explicitly in the current app | `ffmpeg`, `ffprobe` | `ffmpeg` |

**Problems or gaps**

- Stage Two can no longer assume that the current host dependency set is enough.
- Both integrated packages rely on the external ffmpeg CLI, while the current host render path uses PyAV bindings.
- Frozen-build behavior is not researched here for the new binaries and model assets.

**Existing lazy-loading precedent**

Local SRT already implements `__getattr__`-based lazy loading in its `__init__.py`. The module-level `_EXPORTS` dictionary maps public names (such as `transcribe_file`, `ResolvedConfig`, `EventEmitter`) to `(relative_module, attribute)` pairs. Imports of `faster_whisper` and other heavy dependencies are deferred until the caller first accesses an exported name. This means that `import local_srt` alone does not pull in `faster-whisper`, `torch`, or any other heavy transitive dependency.

Caption Animator does not currently use lazy loading — its `__init__.py` eagerly imports from subpackages.

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Make all new Python deps part of the default install | Simplest user installation story if Stage Three exposes the features by default | Larger environment, heavier installs, more runtime surface |
| Keep heavy subsystems behind extras (`caption`, `srt`, `diarize`) even inside one repo | Smaller base install, cleaner opt-in for heavy features | GUI installers and packaging need to understand extras |
| Lazy-import runtime-heavy modules while still shipping them by default | Keeps app startup lighter; Local SRT already proves the pattern works | Does not reduce install size |

**Current direction after feedback**

The new dependencies become part of the default installation. `audio_visualizer.srt` should preserve and extend Local SRT's existing `__getattr__` lazy-loading pattern so that importing the subpackage does not force immediate loading of `faster-whisper` or its transitive GPU dependencies. `audio_visualizer.caption` should adopt the same lazy-loading pattern so that `pysubs2` and rendering internals are deferred until first use. This keeps the host app's startup time unaffected by the new packages.

### 4.2 Event and progress model mismatch

| Codebase | Current progress mechanism |
|----------|----------------------------|
| Audio Visualizer | Qt `Signal` objects emitted from `QRunnable` workers |
| Local SRT | dataclass events plus a simple callback/emitter model |
| Caption Animator | `RenderEvent` callbacks and an `EventEmitter` |

**Problems or gaps**

- The app already has one progress idiom for visualizer rendering and two more will arrive with the merged packages.
- Without an adapter layer, each future GUI tab would need to translate package-specific events on its own.

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Keep each package's native event model and adapt only at the Qt worker boundary | Lowest source churn, easiest merge | Event adaptation logic gets repeated if many tabs are added |
| Add a shared app adapter layer from package events to Qt signals | Centralizes GUI integration logic | One more internal abstraction to design and test |
| Normalize both packages onto one new internal event protocol during merge | Cleanest eventual shape | Highest Stage Two refactor cost |

**Current direction after feedback**

The app should converge on one common event protocol during the Stage Two merge itself, rather than deferring the deeper rewrite to a later phase.

### 4.3 Resource and path management

| Current behavior | Code | Integration concern |
|------------------|------|--------------------|
| Host app stores config/data in app-specific directories | `audio_visualizer.app_paths` | Good destination if presets, model metadata, or cached artifacts need a stable home |
| Local SRT has built-in presets in code and JSON config files outside the package tree | `local_srt/config.py`, `Projects to integrate/Local SRT/configs/` | Resource loading strategy changes once the project is no longer its own distribution |
| Caption Animator searches `Path("presets")` by default | `caption_animator/presets/loader.py` | Current working directory should not be a hidden requirement once embedded |

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Keep resources as package-local data | Self-contained package behavior | Requires explicit packaging changes |
| Move editable resources into the app's config/data dirs | Good future GUI story | Requires migration and editing workflows |
| Treat external preset/config files as examples/docs only and rely on in-code defaults | Simplest runtime behavior | Less flexible for power users |

### 4.4 Naming and style mismatch

The host app currently uses camelCase module filenames such as `mainWindow.py`, `renderDialog.py`, and `generalSettingViews.py`. The two integration projects use snake_case module names throughout.

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Preserve the imported projects' snake_case internals under `audio_visualizer/srt` and `audio_visualizer/caption` | Smallest code diff, most faithful merge | Mixed module naming conventions inside one package tree |
| Rename modules to align with the host app | Stylistic consistency | Very high churn with low direct functional benefit |

**Current direction after feedback**

The merged modules should be renamed to align with the host app's naming conventions.

### 4.5 Logging and diagnostic output consolidation

The three codebases use three different mechanisms for logging and diagnostic output. None of them overlap, but they will all coexist inside one process after the merge.

**Current state**

| Codebase | Mechanism | Key code | How it works |
|----------|-----------|----------|--------------|
| Audio Visualizer | Python `logging` module | `app_logging.py` configures a root `FileHandler` writing to `{config_dir}/audio_visualizer.log`; `mainWindow.py` and `RenderWorker` use `logging.getLogger(__name__)` | Standard hierarchical Python logging. The root logger is set to `INFO` level with a formatter that includes timestamp, level, and logger name. |
| Local SRT | Custom dataclass event system | `events.py` defines `BaseEvent` subclasses (`LogEvent`, `WarnEvent`, `ErrorEvent`, `ProgressEvent`, `StageEvent`, etc.) and an `EventEmitter` with subscribe/emit | Does **not** use Python `logging` at all. All diagnostic output flows through `EventEmitter.emit()` callbacks. The CLI handler in `cli.py` prints these events to stderr. |
| Caption Animator | Custom dataclass event system | `core/events.py` defines `RenderEvent` dataclass with `EventType` enum (`STEP`, `DEBUG`, `WARNING`, `ERROR`, `RENDER_START`, `RENDER_PROGRESS`, `RENDER_COMPLETE`) and its own `EventEmitter` | Does **not** use Python `logging` at all. Diagnostic output flows through `EventEmitter.emit()` callbacks. The CLI handler prints to stderr. |

**Problems or gaps**

- After the merge, the host app's `logging.getLogger()` calls will not capture any diagnostic output from `audio_visualizer.srt` or `audio_visualizer.caption` because neither package emits through Python `logging`.
- The host app's log file (`audio_visualizer.log`) will have blind spots for transcription and caption rendering activity.
- Local SRT's `LogEvent` has a `level` field using its own `EventLevel` enum (`DEBUG`, `INFO`, `WARNING`, `ERROR`) that mirrors Python's log levels but is not connected to them.
- Local SRT's `logging_utils.py` is a misnomer — it contains only `format_duration()` (a time-formatting helper), not logging infrastructure.
- Section 4.2 already decides to converge on one app-wide event protocol for progress/status. This section addresses the separate question of how persistent diagnostic logging should work.

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Bridge package events to Python `logging` during the merge | Unified log file captures all package activity; familiar `logging` configuration for handler/filter/level control; no loss of existing event data | Adds a translation layer; log messages need meaningful formatting from event fields |
| Replace the host app's Python `logging` with the new unified event protocol | One mechanism for everything | Loses Python `logging` ecosystem benefits (handlers, filters, third-party integrations); large refactor of existing host code |
| Keep them separate — events for UI/progress, Python `logging` for persistent diagnostics | Clear separation of concerns; both can coexist without translation | Diagnostic output from the merged packages never reaches the log file unless each package also adds `logging` calls |

**Current direction after feedback**

The merged packages should bridge their event systems to Python `logging` so that all diagnostic output reaches the host app's log file. The approach:

1. The shared event protocol designed in Section 4.2 should include a log-level field (mapping to Python's `DEBUG`, `INFO`, `WARNING`, `ERROR` levels).
2. A thin bridge subscriber should be registered on each package's event emitter that forwards events with log-level semantics to a Python `logging.Logger` scoped to the package namespace (e.g., `logging.getLogger("audio_visualizer.srt")`, `logging.getLogger("audio_visualizer.caption")`).
3. The host app's existing `app_logging.setup_logging()` root `FileHandler` will automatically capture these forwarded messages with no additional configuration, because Python `logging` propagates to the root logger by default.
4. Local SRT's `logging_utils.py` should be renamed during the merge to reflect its actual content (`format_duration()`) rather than implying logging infrastructure.

This keeps the event system as the primary mechanism for UI-facing progress and status (as decided in Section 4.2), while ensuring that all diagnostic output is also persistently captured in the app's log file.

## 5. Testing Considerations

**Current test footprint**

| Codebase | Current test footprint | Observed focus |
|----------|------------------------|----------------|
| Audio Visualizer | 4 Python test modules under `tests/` | app paths, logging, basic media utility smoke tests |
| Caption Animator | 18 test and fixture files under `Projects to integrate/Caption Animator/tests/` | sizing, text measurement, text wrapping, word-reveal animation behavior |
| Local SRT | 70 test and fixture files under `Projects to integrate/Local SRT/tests/` | config, audio helpers, output writers, API, alignment, diarization, batch logic, subtitle generation, fixture-driven integration |

**Problems or gaps**

- The root `pyproject.toml` currently points pytest at `tests/`, so imported package tests will not run automatically unless they are relocated or discovery is expanded.
- Local SRT's own pytest configuration excludes integration tests by default and adds coverage/html reporting options that are not part of the host repo's pytest configuration.
- Some Local SRT tests rely on fixture media and `.docx` files; those need a destination if the test suite is preserved.
- The current host tests do not cover the new external dependency requirements (`ffmpeg`, `ffprobe`, Whisper model initialization, font availability).

**Design options**

| Option | Pros | Cons |
|--------|------|------|
| Port both projects' tests mostly intact with import-path rewrites | Highest confidence that the merge preserves behavior | Larger test suite, longer CI/runtime, more fixture movement |
| Port only unit-level tests and add a few host-level smoke tests | Faster integration with less repo churn | More behavioral drift risk in edge cases |
| Keep package-local test trees and widen root pytest discovery | Least rewriting of test structure | Root test configuration becomes more complex |

**Current direction after feedback**

Phase 2 test migration should favor unit-level coverage from the imported packages plus a small number of host-level smoke tests, rather than relocating the full upstream test suites.

**New test areas introduced by the merge regardless of option**

- Import smoke tests for `audio_visualizer.srt` and `audio_visualizer.caption`
- Resource path tests for config/preset loading after relocation
- Missing-binary behavior tests for `ffmpeg` / `ffprobe`
- Event-adapter tests if Qt workers translate Local SRT or Caption Animator progress into GUI signals
- End-to-end smoke tests for one transcription run and one caption render using bundled fixtures

## 6. Implementation Sequencing

The feedback now splits work into a Phase 2 merge track and a Phase 3 follow-on track.

### Phase 2 sequencing

1. Finalize Stage Two merge decisions that directly change package shape
   - default-install dependency strategy
   - resource relocation into app config/data directories
   - Local SRT subpackage structure
   - module renaming to match the host app
   - reusable Local SRT model manager
   - preserved Caption Animator high-level API and external renderer
   - lazy-loading strategy for both merged packages
   - logging consolidation approach (event-to-logging bridge)
2. Relocate and restructure Local SRT into `audio_visualizer.srt`
3. Relocate and rename Caption Animator into `audio_visualizer.caption`
4. Introduce the shared app-wide event protocol, bridge to Python `logging`, and update the merged packages to emit through both systems during Phase 2
5. Port unit-level tests and add host-level smoke tests

### Phase 3 sequencing

1. Research shared-service extraction after the packages exist inside the app
2. Revisit deeper `audio_visualizer.caption` service integration beyond the preserved high-level API
3. Evaluate the trade-offs of moving caption rendering toward PyAV

**Parallelizable work**

- Local SRT relocation/restructure and Caption Animator relocation/rename can proceed in parallel once the shared package-shape decisions are fixed.
- Unit-test migration can partially proceed in parallel as soon as the final namespace and module names are known.

**Hard dependencies**

- Resource-location decisions affect preset/config loading and should land before final package moves are considered complete.
- Event-protocol rollout affects how future Qt workers are designed even if full normalization is deferred past Phase 2.
- Packaging decisions for external dependencies affect installers and frozen builds for any release candidate.

## 7. Phase 3 Follow-On Considerations

This section captures work that the feedback explicitly pushes out of Phase 2, so it remains visible when the later research and implementation planning starts.

| Topic | Why it is a Phase 3 concern | Main code areas |
|-------|------------------------------|-----------------|
| Shared-service extraction | Phase 2 starts with a minimal package merge rather than immediate app-wide service consolidation | future `audio_visualizer` service layer, job orchestration, worker ownership |
| Deeper caption-system integration | Phase 2 preserves the current high-level caption API | `audio_visualizer.caption` facade/service layer, later tab integration |
| PyAV-based caption rendering evaluation | Phase 2 retains the external ffmpeg/libass renderer | `audio_visualizer.caption.rendering`, shared media stack, composition workflows |
| Broader test-suite expansion | Phase 2 keeps the test migration scoped to unit tests plus host smoke tests | root pytest config, fixture migration, end-to-end coverage strategy |
| Rich resource management UI | Phase 2 can move presets/configs into app config/data dirs without yet building a GUI for editing or managing them | `audio_visualizer.app_paths`, preset/config managers, later tabs |

## 8. Risk Areas

| Risk | Mitigation options |
|------|--------------------|
| `ffmpeg`/`ffprobe` become hard runtime requirements for two new features | Feature-scoped diagnostics, lazy checks, installer/bundling decisions |
| `faster-whisper` and optional diarization significantly expand the dependency footprint | Extras, lazy imports, clear diagnostics, explicit release packaging decisions |
| Caption overlay sizing changes across systems due to font fallback differences | Package fonts, require user-selected font files, or document deterministic font requirements |
| Package resource paths break after relocation | Use package resources or app data dirs instead of cwd-relative lookups |
| Full common-event rewrite increases Phase 2 migration scope | Keep the protocol small, document mappings from old package events during the transition, and port tests alongside event changes |
| Module renaming and subpackage restructuring increase migration churn | Port imports and tests together, keep rename scope explicit, preserve mapping notes during the move |
| Removal of CLIs also removes useful debug flows (`keep_ass`, diagnostics, model management commands) | Decide which debugging features become internal APIs or future GUI tools |
| Current host tests are too narrow to catch merged-package regressions | Port upstream tests or add targeted smoke and integration coverage |

## 9. Decisions Made

| Topic | Decision | Phase |
|-------|----------|-------|
| Local SRT namespace | The merged code lives under `audio_visualizer.srt` | Phase 2 |
| Caption Animator namespace | The merged code lives under `audio_visualizer.caption` | Phase 2 |
| Standalone CLIs | The `srtgen` and `caption-animator` entry points do not remain as standalone user-facing commands after the merge | Phase 2 |
| Integration approach | Start with a minimal package merge; do not begin with full shared-service extraction | Phase 2 |
| Shared-service extraction | Keep it visible as a follow-on research/planning topic after the packages are merged | Phase 3 |
| Local SRT package structure | Restructure the imported code into subpackages during the merge | Phase 2 |
| Local SRT retained feature set | Drop batch transcription, but retain non-SRT outputs, Shorts/word-level outputs, corrected alignment, script alignment, prompt-file loading, diarization, diagnostics, and debug controls | Phase 2 |
| Caption API shape | Preserve the current high-level API as the app-facing caption entry point | Phase 2 |
| Caption rendering backend | Keep the current external ffmpeg/libass renderer | Phase 2 |
| Event-protocol direction | Introduce one app-wide event protocol during the Stage Two merge | Phase 2 |
| Module naming | Rename the moved modules to align with the host app's naming conventions | Phase 2 |
| Dependency packaging | The new dependencies become part of the default installation | Phase 2 |
| Resource storage | Presets/config examples should live in app config/data directories | Phase 2 |
| Local SRT model lifecycle | Add a first-class reusable model manager | Phase 2 |
| Caption output model | Continue generating standalone overlay videos | Phase 2 |
| Test migration scope | Port unit-level tests plus a few host-level smoke tests | Phase 2 |
| Lazy loading | Both merged packages use `__getattr__`-based lazy loading to defer heavy imports; Local SRT's existing pattern is preserved and Caption Animator adopts it | Phase 2 |
| Logging consolidation | Bridge package event systems to Python `logging` so diagnostic output reaches the host app's log file; the shared event protocol includes a log-level field | Phase 2 |
| Stage ordering | Package integration remains Stage Two; GUI tab integration remains Stage Three | Stage order |

## 10. Clarifications Resolved

1. Phase 2 starts with a minimal package merge instead of immediate shared-service extraction.
2. Shared-service extraction remains visible as a Phase 3 follow-on concern.
3. The merged Local SRT code should be reorganized into subpackages during the move.
4. The merged caption package should preserve its current high-level API in Phase 2.
5. The caption package should keep its current external ffmpeg/libass renderer in Phase 2.
6. The new package dependencies should ship as part of the default installation.
7. Presets and config examples should move into app config/data directories.
8. `audio_visualizer.srt` should gain a first-class reusable model manager.
9. `audio_visualizer.caption` should continue to generate standalone overlay videos.
10. Phase 2 test migration should favor unit tests plus host-level smoke tests.
11. A clear Phase 3 considerations section should remain in this document for work intentionally left out of Phase 2.
12. Local SRT feature retention is now feature-specific rather than all-or-nothing, with batch transcription dropped and the remaining selected capabilities retained.
13. The shared app-wide event protocol should be implemented during Phase 2 rather than deferred.
14. Both merged packages should use `__getattr__`-based lazy loading to keep app startup unaffected by heavy transitive dependencies. Local SRT's existing pattern is the reference implementation.
15. Package event systems should be bridged to Python `logging` via a thin subscriber so that all diagnostic output reaches the host app's log file. The shared event protocol includes a log-level field mapping to Python's standard levels.

## 11. Clarifications Required

1. None currently. The previously open Local SRT feature-retention matrix and common event-protocol rollout question have both been resolved by the latest feedback.
