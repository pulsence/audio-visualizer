# Agent Documentation Index

This document is the entry point for Claude/Codex agents working on Audio Visualizer. For detailed architecture and file documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Project Overview

Multi-tab desktop application for audio visualization, subtitle generation, subtitle editing, caption animation, and video composition. The app hosts six workflow screens: Audio Visualizer, SRT Gen, SRT Edit, Caption Animate, Render Composition, and Assets.

- **Language:** Python >=3.13
- **Entry:** `python -m audio_visualizer` or `audio-visualizer` script
- **Version:** 0.6.0
- **License:** MIT
- **Author:** Timothy Eck

## Tech Stack

- **GUI:** PySide6 (Qt 6)
- **Audio analysis:** librosa
- **Numerical:** numpy
- **Video encoding:** av (PyAV / FFmpeg)
- **Image generation:** Pillow
- **Update checking:** GitHub REST API
- **Speech recognition:** faster-whisper (Whisper model)
- **Subtitle parsing:** pysubs2
- **Document reading:** python-docx
- **Preset files:** PyYAML (optional)
- **Speaker diarization:** pyannote.audio (optional)

## Architecture Overview

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the detailed package structure.

### Package Docs

- [audio_visualizer](./architecture/packages/audio_visualizer.md) — Root package, version, entry points.
- [audio_visualizer.core](./architecture/packages/audio_visualizer.core.md) — Bootstrap, logging, paths, updater.
- [audio_visualizer.ui](./architecture/packages/audio_visualizer.ui.md) — MainWindow shell, tabs, workers, shared infrastructure.
- [audio_visualizer.ui.views](./architecture/packages/audio_visualizer.ui.views.md) — View base class, settings views for all visualizer types.
- [audio_visualizer.visualizers](./architecture/packages/audio_visualizer.visualizers.md) — Visualizer base class, AudioData, VideoData, all visualizer implementations.
- [audio_visualizer.srt](./architecture/packages/audio_visualizer.srt.md) — Subtitle generation from media using faster-whisper.
- [audio_visualizer.caption](./architecture/packages/audio_visualizer.caption.md) — Subtitle overlay rendering with animated effects.

### Development Overviews

- [Overview](./architecture/development/OVERVIEW.md) — System map and data flow.
- [Visualizers](./architecture/development/VISUALIZERS.md) — Visualizer lifecycle and how to add new types.
- [UI](./architecture/development/UI.md) — MainWindow layout, tab architecture, settings persistence.
- [Rendering](./architecture/development/RENDERING.md) — Threading model, video pipeline, composition engine.
- [Testing](./architecture/development/TESTING.md) — Test setup, existing tests, coverage gaps.

## Developer Guides

- When asked to create a plan read how to do so here: [CREATE_IMPLEMENTATION_PLAN.md](./CREATE_IMPLEMENTATION_PLAN.md).
- Always use the commit message format in [COMMIT_MESSAGE.md](./COMMIT_MESSAGE.md).
- [CODING_PATTERNS.md](./CODING_PATTERNS.md) — Coding conventions.
- When asked to create a research plan read how to do so here: [RESEARCH_PLAN.md](./RESEARCH_PLAN.md).
- You can find past plans and research in `.agents/docs/past_plans/`.
- When asked to create a release summary or release statement read
  [RELEASE_STATEMENT.md](./RELEASE_STATEMENT.md) for a guide on how to do so.

## Commands

Run the application and the test suite from the project `.venv`. If the virtualenv is not activated, call its Python directly.

```bash
# Run the application
.venv/bin/python -m audio_visualizer

# Run all tests
.venv/bin/python -m pytest tests/ -v
```

## Environment Variables

- `AUDIO_VISUALIZER_REPO` — Override the GitHub owner/repo used by the update checker (default: `pulsence/audio-visualizer`).

## Key Implementation Notes

- **Frozen builds:** PyInstaller is supported. `visualizer.py` resolves the application icon via `_resolve_icon_path()`, checking `sys._MEIPASS` for frozen environments.
- **Platform paths:** `app_paths.py` uses `LOCALAPPDATA` on Windows and XDG directories on Unix for config and data storage.
- **Logging:** `app_logging.setup_logging()` writes to `{config_dir}/audio_visualizer.log` at INFO level.
- **Update checking:** `updater.py` queries the GitHub Releases API. The repo can be overridden via the `AUDIO_VISUALIZER_REPO` environment variable.
- **Multi-tab shell:** `MainWindow` is a thin shell hosting six tabs via `QStackedWidget` with a `NavigationSidebar`. Only `AudioVisualizerTab` is instantiated at startup; the remaining five are lazy-loaded on first activation.
- **Shared job pool:** `MainWindow.render_thread_pool` (`QThreadPool`, max 1) is shared across all tabs for heavy work. A separate background pool handles update checks and waveform loading.
- **Cross-tab assets:** `WorkspaceContext` maintains a `SessionAsset` registry. Tab outputs are registered as assets; downstream tabs can pick them via `SessionFilePickerDialog`.
- **Live preview:** A `QTimer` with 400ms debounce triggers 5-second preview renders when settings change.
- **Settings persistence:** Settings are serialized as versioned JSON with `app`, `ui`, `tabs`, and `session` sections. Auto-saved on close, auto-loaded on startup. Users can also save/load named project files.
- **Workflow recipes:** Reusable workflow templates stored as `.avrecipe.json` files. Recipes capture tab settings and asset role bindings without machine-local state.
- **View-to-Visualizer mapping:** `AudioVisualizerTab._VIEW_CLASS_REGISTRY` maps `VisualizerOptions` enum values to module/class pairs for lazy-loading visualizer-specific UI panels.
- **Shared event protocol:** `events.py` defines `AppEvent`, `AppEventEmitter`, and `LoggingBridge`. Both the `srt` and `caption` packages emit structured events (LOG, PROGRESS, STAGE, JOB_START/COMPLETE, RENDER_START/PROGRESS/COMPLETE, MODEL_LOAD) via optional emitter parameters, decoupling progress reporting from any specific UI.
- **Lazy loading:** Both `srt` and `caption` packages use `__getattr__`-based lazy loading in their `__init__.py` files. Heavy dependencies (faster-whisper, pysubs2, Pillow) are only imported when first accessed.
- **SRT transcription:** The `srt` package provides a 4-stage pipeline (audio conversion, transcription, chunking/formatting, output writing). Supports multiple output formats (SRT, VTT, ASS, TXT, JSON), word-level timestamps, silence-aware splitting, script alignment, correction SRT alignment, and optional speaker diarization via pyannote.audio.
- **Caption rendering:** The `caption` package renders subtitle files to transparent video overlays via FFmpeg with libass. Supports preset-based styling, a plugin animation system (fade, slide, scale, blur, word reveal), tight overlay sizing with Pillow-based text measurement, and multiple quality tiers (H.264, ProRes 422 HQ, ProRes 4444).
- **Render Composition:** Visual/audio sources must have resolved duration metadata before they are accepted into the model. Preview and final render share the same FFmpeg timing helpers, so timeline length, looping, and preview behavior stay aligned.
- **Model management:** `ModelManager` provides thread-safe Whisper model caching and reuse across multiple transcription jobs. `modelManagement.py` provides standalone model listing, download, delete, and system diagnostics.
- **Test suite:** 938 tests across all packages, including dedicated coverage for main-window shell behavior, assets/session workflows, Render Composition FFmpeg command generation, caption/audio-input handling, waveform loading, and integration smoke tests.
