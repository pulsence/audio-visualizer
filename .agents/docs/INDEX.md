# Agent Documentation Index

This document is the entry point for Claude/Codex agents working on Audio Visualizer. For detailed architecture and file documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Project Overview

Desktop application for generating synchronized audio visualization videos. Users select an audio file, configure a visualizer type and rendering options, and produce an MP4 video with animated graphics driven by the audio's volume and chromatic content.

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
- [audio_visualizer.ui](./architecture/packages/audio_visualizer.ui.md) — MainWindow, RenderDialog, threading.
- [audio_visualizer.ui.views](./architecture/packages/audio_visualizer.ui.views.md) — View base class, settings views for all visualizer types.
- [audio_visualizer.visualizers](./architecture/packages/audio_visualizer.visualizers.md) — Visualizer base class, AudioData, VideoData, all visualizer implementations.
- [audio_visualizer.srt](./architecture/packages/audio_visualizer.srt.md) — Subtitle generation from media using faster-whisper.
- [audio_visualizer.caption](./architecture/packages/audio_visualizer.caption.md) — Subtitle overlay rendering with animated effects.

### Development Overviews

- [Overview](./architecture/development/OVERVIEW.md) — System map and data flow.
- [Visualizers](./architecture/development/VISUALIZERS.md) — Visualizer lifecycle and how to add new types.
- [UI](./architecture/development/UI.md) — MainWindow layout, view mapping, settings persistence.
- [Rendering](./architecture/development/RENDERING.md) — Threading model and video pipeline.
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
- **Rendering:** `MainWindow` uses a `QThreadPool` (max 1 thread) for render workers. A separate background thread pool handles update checks.
- **Live preview:** A `QTimer` with 400ms debounce triggers 5-second preview renders when settings change.
- **Settings persistence:** Settings are serialized as JSON. Auto-saved on close, auto-loaded on startup. Users can also save/load named project files.
- **View-to-Visualizer mapping:** `MainWindow._VIEW_ATTRIBUTE_MAP` maps view attribute names to `VisualizerOptions` enum values for lazy-loading visualizer-specific UI panels.
- **Shared event protocol:** `events.py` defines `AppEvent`, `AppEventEmitter`, and `LoggingBridge`. Both the `srt` and `caption` packages emit structured events (LOG, PROGRESS, STAGE, JOB_START/COMPLETE, RENDER_START/PROGRESS/COMPLETE, MODEL_LOAD) via optional emitter parameters, decoupling progress reporting from any specific UI.
- **Lazy loading:** Both `srt` and `caption` packages use `__getattr__`-based lazy loading in their `__init__.py` files. Heavy dependencies (faster-whisper, pysubs2, Pillow) are only imported when first accessed.
- **SRT transcription:** The `srt` package provides a 4-stage pipeline (audio conversion, transcription, chunking/formatting, output writing). Supports multiple output formats (SRT, VTT, ASS, TXT, JSON), word-level timestamps, silence-aware splitting, script alignment, correction SRT alignment, and optional speaker diarization via pyannote.audio.
- **Caption rendering:** The `caption` package renders subtitle files to transparent video overlays via FFmpeg with libass. Supports preset-based styling, a plugin animation system (fade, slide, scale, blur, word reveal), tight overlay sizing with Pillow-based text measurement, and multiple quality tiers (H.264, ProRes 422 HQ, ProRes 4444).
- **Model management:** `ModelManager` provides thread-safe Whisper model caching and reuse across multiple transcription jobs. `modelManagement.py` provides standalone model listing, download, delete, and system diagnostics.
- **Test suite:** 312+ tests across all packages, including dedicated test files for srt models, config, text processing, subtitle generation, alignment, output writers, events, format helpers, audio helpers, system helpers, script reader, smoke tests, caption sizing, measurement, wrapper, word reveal, and integration smoke tests.
