# System Overview

Audio Visualizer is a desktop application that converts audio files into visualization videos. Users configure a visualizer type and rendering options through a PySide6 GUI, and the application generates an MP4 video with synchronized animated graphics.

## System Context

```
User → MainWindow (PySide6 GUI)
    → selects audio file, visualizer type, and rendering options
    → triggers render

MainWindow → RenderWorker (QRunnable, background thread)
    → AudioData: loads and analyzes audio via librosa
    → VideoData: creates PyAV output container
    → Visualizer: generates frames via Pillow
    → Optional: muxes audio track into video
    → Output: MP4 file
```

## Component Diagram

```
┌──────────────────────────────────────────────────────┐
│                    Core Modules                       │
│  visualizer.py  app_logging  app_paths  updater      │
│                    events.py                         │
│         (AppEvent, AppEventEmitter, LoggingBridge)   │
└───────────────────────┬──────────────────────────────┘
                        │
         ┌──────────────┼──────────────┬───────────────┐
         │              │              │               │
┌────────▼────────┐  ┌──▼──────────┐  ┌▼────────────┐ ┌▼────────────────┐
│    UI Layer     │  │ Visualizer  │  │  SRT Package │ │ Caption Package │
│  MainWindow     │  │   Engine    │  │  srtApi      │ │ captionApi      │
│  RenderDialog   │  │ Visualizer  │  │  pipeline    │ │ SubtitleFile    │
│  Views (16)     │  │ AudioData   │  │  whisper     │ │ StyleBuilder    │
│                 │  │ VideoData   │  │  subtitleGen │ │ SizeCalculator  │
│                 │  │ 14 impls    │  │  textProc    │ │ AnimationReg.   │
│                 │  │             │  │  outputWrite │ │ FFmpegRenderer  │
│                 │  │             │  │  ModelManager│ │ PresetLoader    │
└─────────────────┘  └─────────────┘  └─────────────┘ └─────────────────┘
```

## Data Flow

1. **User input** — User selects an audio file, chooses a visualizer type, and configures settings via View panels in MainWindow.

2. **Validation** — `MainWindow.validate_render_settings()` validates all View panels. Each View's `validate_view()` checks its inputs and populates error messages.

3. **Render initiation** — `MainWindow._start_render()`:
   - Creates `AudioData` from the selected audio file
   - Creates `VideoData` with resolution, FPS, codec, and output path
   - Calls `_create_visualizer()` to instantiate the correct Visualizer subclass
   - Submits a `RenderWorker` to the render `QThreadPool`

4. **Audio processing** (in RenderWorker):
   - `AudioData.load_audio_data()` — loads audio via librosa
   - `AudioData.chunk_audio(fps)` — splits samples into per-frame chunks
   - `AudioData.analyze_audio()` — computes volume and chromagram per frame

5. **Video generation** (in RenderWorker):
   - `VideoData.prepare_container()` — creates PyAV output container
   - `Visualizer.prepare_shapes()` — initializes shape data
   - Loop: `Visualizer.generate_frame(i)` → numpy array → encoded to video stream
   - Optional: `_mux_audio()` — encodes and muxes audio track
   - `VideoData.finalize()` — closes the container

6. **Completion** — `RenderWorker` emits `finished` signal. MainWindow shows the video in `RenderDialog` or the preview panel.

### SRT Subtitle Generation Data Flow

7. **Model loading** — `load_model()` or `ModelManager.load()` initializes a faster-whisper model with automatic device selection (CUDA/CPU). The model is cached for reuse across multiple transcriptions.

8. **SRT render initiation** — `transcribe_file()` in `srtApi.py` accepts a pre-loaded model, input/output paths, format, and `ResolvedConfig`. Delegates to `transcribe_file_internal()`.

9. **Audio conversion** — `to_wav_16k_mono()` converts input media to 16kHz mono WAV via ffmpeg.

10. **Transcription** — The faster-whisper model transcribes the WAV file, yielding segments with word-level timestamps. Progress events with percent and ETA are emitted per segment.

11. **Silence detection** — `detect_silences()` uses ffmpeg's silencedetect filter to find silent regions for timing alignment.

12. **Subtitle chunking** — Depending on `PipelineMode`, segments/words are chunked into `SubtitleBlock` lists using silence-aware splitting, punctuation-based text splitting, and timing distribution. Optional script alignment and correction SRT alignment are applied.

13. **Timing polish** — `apply_silence_alignment()` and `hygiene_and_polish()` clean up timing: remove empties, merge duplicates, enforce min gaps, apply padding, ensure monotonic timing.

14. **Output writing** — Subtitles are written in the requested format (SRT, VTT, ASS, TXT, JSON) with atomic file writes. Optional transcript, segments dump, and JSON bundle outputs.

### Caption Overlay Rendering Data Flow

15. **Caption render initiation** — `render_subtitle()` in `captionApi.py` accepts input subtitle path, output video path, and `RenderConfig`.

16. **Subtitle loading** — `SubtitleFile.load()` parses the input .srt or .ass file via pysubs2.

17. **Preset and style application** — `PresetLoader.load()` resolves the preset (built-in, file, or directory search). `StyleBuilder.build()` converts the preset to a pysubs2 `SSAStyle`. Text is optionally wrapped to `max_width_px` using Pillow font measurement.

18. **Animation application** — If the preset includes animation config, `AnimationRegistry.create()` instantiates the animation and applies ASS override tags to each subtitle event.

19. **Overlay sizing** — `SizeCalculator.compute_size()` measures all subtitle events with Pillow, adds padding/outline/shadow allowances, applies safety scaling, and ensures even dimensions.

20. **Positioning and rendering** — `apply_center_positioning()` injects `\an5\pos()` tags. The working ASS file is saved and rendered to transparent video via `FFmpegRenderer.render()` using ffmpeg with libass.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Visualizer/View separation | Decouples rendering logic from UI settings collection |
| Enum-driven configuration | `VisualizerOptions` provides a single source of truth for all visualizer types |
| Threaded rendering | QThreadPool (max 1) keeps the UI responsive during long renders |
| Lazy view loading | `__getattr__()` defers view creation until a visualizer type is actually selected |
| JSON settings persistence | Simple format for saving/loading project configurations |
| librosa for audio analysis | Robust audio loading plus chromagram and per-frame average-amplitude analysis |
| PyAV for video encoding | Direct FFmpeg bindings with hardware acceleration support |
| Pillow for frame generation | Simple 2D drawing API for shapes, lines, and curves |
| Shared AppEvent protocol | Decouples progress reporting from UI; srt and caption packages emit structured events without depending on Qt or any specific UI framework |
| `__getattr__` lazy loading for srt/caption | Heavy dependencies (faster-whisper, pysubs2) are only imported on first use, keeping startup fast and import side-effects minimal |
| Thread-safe ModelManager | Enables model reuse across multiple transcription jobs without reloading; the lock allows safe access from Qt worker threads |
| Plugin-based animation registry | New animations can be added by subclassing `BaseAnimation` and decorating with `@AnimationRegistry.register`; no changes to core code needed |
| Preset-driven caption styling | Presets decouple visual style from rendering logic; supports built-in, JSON, and YAML sources with multi-preset file support |
| Pillow for text measurement | Approximates libass rendering for tight overlay sizing before FFmpeg render, avoiding oversized canvases |
| Atomic file writes in SRT output | Write to `.tmp` then `os.replace()` prevents partial output files on failure |
| Optional pyannote.audio diarization | Speaker labeling is opt-in and guarded by `is_diarization_available()` to avoid hard dependency |
