# System Overview

Audio Visualizer is a multi-tab desktop application for audio visualization, subtitle generation, subtitle editing, caption animation, video composition, asset management, and advanced transcription/training workflows. The PySide6 GUI hosts seven workflow screens inside a thin `MainWindow` shell.

## System Context

```
User → MainWindow (PySide6 thin shell)
    ├── NavigationSidebar — tab switcher
    ├── QStackedWidget — one eager + six lazy tabs
    │   ├── AudioVisualizerTab — audio visualization rendering
    │   ├── SrtGenTab — batch Whisper transcription
    │   ├── SrtEditTab — waveform-synced subtitle editor
    │   ├── CaptionAnimateTab — subtitle overlay rendering
    │   ├── RenderCompositionTab — layer-based video compositor
    │   ├── AssetsTab — session asset browser
    │   └── AdvancedTab — correction/training tooling
    ├── JobStatusWidget — global job progress/cancel
    └── WorkspaceContext — shared asset registry
```

## Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Core Modules                           │
│  visualizer.py  app_logging  app_paths  updater          │
│                    events.py                             │
│         (AppEvent, AppEventEmitter, LoggingBridge)       │
└───────────────────────┬──────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┬───────────────┐
    │                   │                   │               │
┌───▼───────────────┐ ┌▼─────────────┐  ┌──▼────────────┐ ┌▼─────────────────┐
│    UI Layer       │ │ Visualizer   │  │  SRT Package  │ │ Caption Package  │
│  MainWindow shell │ │   Engine     │  │  srtApi       │ │ captionApi       │
│  7 tabs (BaseTab) │ │ Visualizer   │  │  pipeline     │ │ SubtitleFile     │
│  Workers          │ │ AudioData    │  │  whisper      │ │ StyleBuilder     │
│  WorkspaceContext │ │ VideoData    │  │  subtitleGen  │ │ SizeCalculator   │
│  SessionFilePicker│ │ 14 impls     │  │  textProc     │ │ AnimationReg.    │
│  WorkflowRecipes  │ │              │  │  outputWrite  │ │ FFmpegRenderer   │
│  Views (16)       │ │              │  │  ModelManager │ │ PresetLoader     │
└───────────────────┘ └──────────────┘  └──────────────┘ └──────────────────┘
```

## Data Flow

1. **User input** — User navigates between tabs via the sidebar. Each tab collects settings through its own UI surface.

2. **Validation** — Each tab's `validate_settings()` checks inputs before starting work.

3. **Job execution** — Long-running work (render, transcription, composition) is submitted to the shared `render_thread_pool` (max 1 concurrent job). The shell blocks new jobs while one is active.

4. **Audio Visualizer render** — `AudioVisualizerTab` creates `AudioData` + `VideoData` + `Visualizer`, submits a `RenderWorker` to the pool. Frames are generated via Pillow, encoded via PyAV, with optional audio muxing.

5. **SRT transcription** — `SrtGenTab` submits a `SrtGenWorker` that loads a faster-whisper model and processes a batch queue. Each file goes through audio conversion, transcription, chunking, timing polish, and output writing.

6. **SRT editing** — `SrtEditTab` loads subtitles into a `SubtitleDocument`, displays a pyqtgraph waveform with subtitle regions, and provides undoable editing with QA lint and resync tools.

7. **Caption rendering** — `CaptionAnimateTab` submits a `CaptionRenderWorker` that calls the `caption` package API. Bundles and markdown source are normalized before ASS generation. The render path produces a user-facing MP4 delivery artifact by default and keeps transparent overlay export optional.

8. **Composition** — `RenderCompositionTab` builds a `CompositionModel` of visual and audio layers, generates an FFmpeg `filter_complex` command via `filterGraph.py`, exposes real-time preview through `playbackEngine.py` when host capabilities allow it, and submits a `CompositionWorker` for final export.

9. **Advanced tooling** — `AdvancedTab` exposes the correction database, prompt/replacement rule management, training-data export, LoRA training, and trained-model selection used by the speaker-adaptation path.

10. **Cross-tab assets** — Tab outputs are registered as `SessionAsset` entries in `WorkspaceContext`. Downstream tabs can pick session assets via `SessionFilePickerDialog` instead of browsing the filesystem.

11. **Completion** — `JobStatusWidget` shows result with `Preview`, `Open Output`, and `Open Folder` actions. No blocking modal dialog on completion.

### SRT Subtitle Generation Data Flow

11. **Model loading** — `load_model()` or `ModelManager.load()` initializes a faster-whisper model with automatic device selection (CUDA/CPU). The model is cached for reuse across multiple transcriptions.

12. **SRT render initiation** — `transcribe_file()` in `srtApi.py` accepts a pre-loaded model, input/output paths, format, and `ResolvedConfig`. Delegates to `transcribe_file_internal()`.

13. **Audio conversion** — `to_wav_16k_mono()` converts input media to 16kHz mono WAV via ffmpeg.

14. **Transcription** — The faster-whisper model transcribes the WAV file, yielding segments with word-level timestamps. Progress events with percent and ETA are emitted per segment.

15. **Silence detection** — `detect_silences()` uses ffmpeg's silencedetect filter to find silent regions for timing alignment.

16. **Subtitle chunking** — Depending on `PipelineMode`, segments/words are chunked into `SubtitleBlock` lists using silence-aware splitting, punctuation-based text splitting, and timing distribution. Optional script alignment and correction SRT alignment are applied.

17. **Timing polish** — `apply_silence_alignment()` and `hygiene_and_polish()` clean up timing: remove empties, merge duplicates, enforce min gaps, apply padding, ensure monotonic timing.

18. **Output writing** — Subtitles are written in the requested format (SRT, VTT, ASS, TXT, JSON) with atomic file writes. Optional transcript, segments dump, and JSON bundle outputs.

### Caption Overlay Rendering Data Flow

19. **Caption render initiation** — `render_subtitle()` in `captionApi.py` accepts input subtitle path, output video path, and `RenderConfig`.

20. **Subtitle loading** — `SubtitleFile.load()` parses `.srt`, `.ass`, or normalized bundle JSON input.

21. **Preset and style application** — `PresetLoader.load()` resolves the preset (built-in, file, or directory search). `StyleBuilder.build()` converts the preset to a pysubs2 `SSAStyle`. Text is optionally wrapped to `max_width_px` using Pillow font measurement.

22. **Animation application** — If the preset includes animation config, `AnimationRegistry.create()` instantiates the animation and applies ASS override tags to each subtitle event. Markdown-to-ASS conversion happens at render time so source markdown survives SRT Edit round-trips untouched.

23. **Overlay sizing** — `SizeCalculator.compute_size()` measures all subtitle events with Pillow, adds padding/outline/shadow allowances, applies safety scaling, and ensures even dimensions.

24. **Positioning and rendering** — `apply_center_positioning()` injects `\an5\pos()` tags. The working ASS file is saved and rendered to transparent video via `FFmpegRenderer.render()` using ffmpeg with libass, then the worker produces the user-facing MP4 delivery artifact.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Multi-tab shell with `QStackedWidget` | Decouples workflow stages; each tab owns its own lifecycle |
| Lazy tab instantiation | Heavy tabs defer dependency imports until activation, keeping startup fast |
| Shared `WorkspaceContext` | Cross-tab asset registry eliminates manual file passing between workflow steps |
| Single shared job pool (max 1) | Prevents resource contention; shell blocks concurrent heavy jobs |
| `BaseTab` contract | Standardizes settings, validation, and undo across all tabs |
| Visualizer/View separation | Decouples rendering logic from UI settings collection |
| Enum-driven configuration | `VisualizerOptions` provides a single source of truth for all visualizer types |
| Threaded rendering | QThreadPool (max 1) keeps the UI responsive during long renders |
| JSON settings persistence | Simple format for saving/loading project configurations |
| librosa for audio analysis | Robust audio loading plus chromagram and per-frame average-amplitude analysis |
| PyAV for video encoding | Direct FFmpeg bindings with hardware acceleration support |
| Pillow for frame generation | Simple 2D drawing API for shapes, lines, and curves |
| Shared AppEvent protocol | Decouples progress reporting from UI; srt and caption packages emit structured events without depending on Qt |
| `__getattr__` lazy loading for srt/caption | Heavy dependencies (faster-whisper, pysubs2) are only imported on first use |
| Thread-safe ModelManager | Enables model reuse across transcription jobs without reloading |
| Plugin-based animation registry | New animations can be added by subclassing `BaseAnimation` and decorating with `@AnimationRegistry.register` |
| Preset-driven caption styling | Presets decouple visual style from rendering logic |
| FFmpeg filter_complex for composition | Enables multi-layer video/audio composition with looping, keying, and timing control |
| Tab-scoped QUndoStack | SRT Edit and Render Composition each own independent undo history |
| Atomic file writes in SRT output | Write to `.tmp` then `os.replace()` prevents partial output files on failure |
