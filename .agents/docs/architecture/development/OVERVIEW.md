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
┌─────────────────────────────────────────┐
│              Core Modules               │
│  visualizer.py  app_logging  app_paths  │
│                 updater                 │
└────────────────────┬────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────▼────────┐   ┌─────────▼─────────┐
│    UI Layer     │   │  Visualizer Engine │
│  MainWindow     │   │  Visualizer (base) │
│  RenderDialog   │   │  AudioData         │
│  Views (16)     │   │  VideoData         │
│                 │   │  14 implementations│
└─────────────────┘   └───────────────────┘
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
