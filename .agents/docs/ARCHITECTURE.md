# Architecture Overview

This document provides a package-level map of Audio Visualizer. See [INDEX.md](./INDEX.md) for the quick start guide.

## Package Map

```
src/audio_visualizer/
    __init__.py              # Package root, exports __version__
    __main__.py              # python -m audio_visualizer entry point
    visualizer.py            # QApplication bootstrap, icon resolution, main()
    app_logging.py           # File-based logging setup
    app_paths.py             # Platform-specific config/data directories
    updater.py               # GitHub release update checker
    ui/
        mainWindow.py        # MainWindow — primary application window
        renderDialog.py      # RenderDialog — post-render playback dialog
        views/
            __init__.py      # Re-exports View, Fonts
            general/
                generalView.py             # View base class
                utilities.py               # Fonts (h1_font, h2_font)
                generalSettingViews.py     # GeneralSettingsView — file paths, codec, resolution
                generalVisualizerView.py   # GeneralVisualizerView — position, colors, spacing
                combinedVisualizerView.py  # CombinedVisualizerView
                waveformVisualizerView.py  # WaveformVisualizerView
            volume/
                rectangleVolumeVisualizerView.py
                circleVolumeVisualizerView.py
                lineVolumeVisualizerView.py
                forceLineVolumeVisualizerView.py
            chroma/
                rectangleChromaVisualizerView.py
                circleChromaVisualizerView.py
                lineChromaVisualizerView.py
                lineChromaBandsVisualizerView.py
                forceRectangleChromaVisualizerView.py
                forceCircleChromaVisualizerView.py
                forceLineChromaVisualizerView.py
                forceLinesChromaVisualizerView.py
    visualizers/
        __init__.py              # Re-exports Visualizer
        genericVisualizer.py     # Visualizer abstract base class
        utilities.py             # AudioData, VideoData, VisualizerOptions, VisualizerFlow, VisualizerAlignment
        volume/
            rectangleVolumeVisualizer.py
            circleVolumeVisualizer.py
            lineVolumeVisualizer.py
            forceLineVisualizer.py
        chroma/
            rectangleChromaVisualizer.py
            circleChromaVisualizer.py
            lineChromaVisualizer.py
            lineBandsChromaVisualizer.py
            forceRectangleVisualizer.py
            forceCircleVisualizer.py
            forceLineVisualizer.py
            forceLinesVisualizer.py
        combined/
            rectangleCombinedVisualizer.py
        waveform/
            waveformVisualizer.py
```

## Package Details

See individual package documentation in the [architecture/packages](./architecture/packages/) folder:

- [audio_visualizer](./architecture/packages/audio_visualizer.md) — Root package, version, entry points, dependency list.
- [audio_visualizer.core](./architecture/packages/audio_visualizer.core.md) — Application bootstrap, logging, platform paths, update checker.
- [audio_visualizer.ui](./architecture/packages/audio_visualizer.ui.md) — MainWindow, RenderDialog, render threading, settings persistence.
- [audio_visualizer.ui.views](./architecture/packages/audio_visualizer.ui.views.md) — View base class and all visualizer-specific settings views.
- [audio_visualizer.visualizers](./architecture/packages/audio_visualizer.visualizers.md) — Visualizer base class, data models, and all visualizer implementations.

## Development Overviews

Developer-focused architecture notes:

- [Overview](./architecture/development/OVERVIEW.md) — System context, component diagram, data flow.
- [Visualizers](./architecture/development/VISUALIZERS.md) — Visualizer lifecycle and adding new types.
- [UI](./architecture/development/UI.md) — MainWindow layout, view mapping, settings persistence.
- [Rendering](./architecture/development/RENDERING.md) — Threading model and video encoding pipeline.
- [Testing](./architecture/development/TESTING.md) — Test setup, existing tests, coverage gaps.

## Key Abstractions

| Abstraction | Location | Purpose |
|---|---|---|
| `Visualizer` | `visualizers/genericVisualizer.py` | Abstract base for all frame generators |
| `View` | `ui/views/general/generalView.py` | Abstract base for all settings panels |
| `AudioData` | `visualizers/utilities.py` | Audio loading, chunking, and analysis |
| `VideoData` | `visualizers/utilities.py` | Video container management and codec config |
| `VisualizerOptions` | `visualizers/utilities.py` | Enum of all 14 visualizer types |
| `VisualizerFlow` | `visualizers/utilities.py` | LEFT_TO_RIGHT or OUT_FROM_CENTER |
| `VisualizerAlignment` | `visualizers/utilities.py` | BOTTOM or CENTER |

## Data Flow

```
Audio file → librosa.load() → AudioData
    → chunk_audio(fps) → audio_frames[]
    → analyze_audio() → average_volumes[], chromagrams[]

AudioData + VideoData + settings → Visualizer subclass
    → prepare_shapes()
    → generate_frame(0..N) → numpy arrays → av video stream
    → optional audio muxing
    → VideoData.finalize() → output MP4
```

## View-to-Visualizer Mapping

`MainWindow._VIEW_ATTRIBUTE_MAP` maps attribute names (e.g., `_volume_rectangle_view`) to `VisualizerOptions` enum values. When a visualizer type is selected in the dropdown, `MainWindow.__getattr__()` lazy-loads the corresponding View subclass, and `_create_visualizer()` instantiates the matching Visualizer subclass with the collected settings.
