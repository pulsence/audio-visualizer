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
    events.py                # Shared event protocol (AppEvent, AppEventEmitter, LoggingBridge)
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
    srt/
        __init__.py              # Lazy-loaded public API (transcribe_file, load_model, models, config)
        srtApi.py                # Public API: transcribe_file(), load_model(), TranscriptionResult
        models.py                # Data models: ResolvedConfig, SubtitleBlock, WordItem, PipelineMode
        config.py                # Configuration: PRESETS, load_config_file(), apply_overrides()
        modelManager.py          # ModelManager — thread-safe Whisper model lifecycle
        modelManagement.py       # Model listing, download, delete, diagnostics
        formatHelpers.py         # Duration formatting
        core/
            pipeline.py          # Core transcription pipeline (4-stage)
            whisperWrapper.py    # faster-whisper model initialization
            subtitleGeneration.py # Segment/word to subtitle block conversion
            textProcessing.py    # Text normalization, wrapping, splitting, timing
            alignment.py         # Corrected SRT and script alignment
            diarization.py       # Optional speaker diarization (pyannote.audio)
        io/
            audioHelpers.py      # Audio conversion, silence detection (ffmpeg)
            outputWriters.py     # SRT/VTT/ASS/TXT/JSON output writers
            scriptReader.py      # .docx script reading (python-docx)
            systemHelpers.py     # File system, ffmpeg/ffprobe checks, command execution
    caption/
        __init__.py              # Lazy-loaded public API (render_subtitle, configs, classes)
        captionApi.py            # Public API: render_subtitle(), list_presets(), list_animations()
        core/
            config.py            # PresetConfig, AnimationConfig dataclasses
            style.py             # StyleBuilder — ASS style from PresetConfig
            sizing.py            # SizeCalculator, OverlaySize — overlay dimension computation
            subtitle.py          # SubtitleFile — high-level pysubs2 wrapper
        animations/
            __init__.py          # Lazy loading + AnimationRegistry patching
            baseAnimation.py     # BaseAnimation abstract base class
            registry.py          # AnimationRegistry — plugin registry with decorator registration
            fadeAnimation.py     # FadeAnimation (fade in/out)
            slideAnimation.py    # SlideUpAnimation (slide up with move)
            scaleAnimation.py    # ScaleSettleAnimation (scale effect)
            blurAnimation.py     # BlurSettleAnimation (blur to sharp)
            wordRevealAnimation.py # WordRevealAnimation (per-word alpha reveal)
        rendering/
            ffmpegRenderer.py    # FFmpegRenderer — ProRes 4444 / H.264 transparent video
            progressTracker.py   # ProgressTracker — event-based progress reporting
        presets/
            defaults.py          # Built-in presets (clean_outline, modern_box)
            loader.py            # PresetLoader — multi-source preset resolution
        text/
            measurement.py       # Text measurement via Pillow
            utils.py             # ASS tag stripping, newline conversion, whitespace normalization
            wrapper.py           # Pixel-width text wrapping
        utils/
            files.py             # ensure_parent_dir()
```

## Package Details

See individual package documentation in the [architecture/packages](./architecture/packages/) folder:

- [audio_visualizer](./architecture/packages/audio_visualizer.md) — Root package, version, entry points, dependency list.
- [audio_visualizer.core](./architecture/packages/audio_visualizer.core.md) — Application bootstrap, logging, platform paths, update checker.
- [audio_visualizer.ui](./architecture/packages/audio_visualizer.ui.md) — MainWindow, RenderDialog, render threading, settings persistence.
- [audio_visualizer.ui.views](./architecture/packages/audio_visualizer.ui.views.md) — View base class and all visualizer-specific settings views.
- [audio_visualizer.visualizers](./architecture/packages/audio_visualizer.visualizers.md) — Visualizer base class, data models, and all visualizer implementations.
- [audio_visualizer.srt](./architecture/packages/audio_visualizer.srt.md) — Subtitle generation from media using faster-whisper.
- [audio_visualizer.caption](./architecture/packages/audio_visualizer.caption.md) — Subtitle overlay rendering with animated effects.

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
| `AppEvent` | `events.py` | Unified event dataclass for cross-package communication |
| `AppEventEmitter` | `events.py` | Pub/sub event bus with enable/disable toggle |
| `LoggingBridge` | `events.py` | Forwards AppEvents to Python logging |
| `TranscriptionResult` | `srt/srtApi.py` | Result of a transcription job |
| `ResolvedConfig` | `srt/models.py` | Nested SRT configuration container |
| `SubtitleBlock` | `srt/models.py` | A timed subtitle cue with text lines |
| `ModelManager` | `srt/modelManager.py` | Thread-safe Whisper model lifecycle manager |
| `RenderConfig` | `caption/captionApi.py` | Configuration for caption rendering |
| `RenderResult` | `caption/captionApi.py` | Result of a caption render job |
| `PresetConfig` | `caption/core/config.py` | Complete caption preset configuration |
| `SubtitleFile` | `caption/core/subtitle.py` | High-level pysubs2 wrapper |
| `BaseAnimation` | `caption/animations/baseAnimation.py` | Abstract base for animation plugins |
| `AnimationRegistry` | `caption/animations/registry.py` | Central animation plugin registry |
| `FFmpegRenderer` | `caption/rendering/ffmpegRenderer.py` | FFmpeg-based transparent video renderer |

## Data Flow

### Visualization Pipeline

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

### SRT Subtitle Generation Pipeline

```
Media file → ffmpeg (to_wav_16k_mono) → 16kHz mono WAV
    → faster-whisper model.transcribe() → segments + word timestamps
    → detect_silences() → silence intervals
    → chunk_words_to_subtitles() or chunk_segments_to_subtitles()
    → apply_silence_alignment() → timing-adjusted blocks
    → hygiene_and_polish() → final SubtitleBlock list
    → write_srt/vtt/ass/txt/json() → output file(s)

All stages emit AppEvent (LOG, PROGRESS, STAGE) via optional emitter.
```

### Caption Overlay Rendering Pipeline

```
Subtitle file (.srt/.ass) → pysubs2.load() → SubtitleFile
    → PresetLoader.load() → PresetConfig
    → StyleBuilder.build() → pysubs2.SSAStyle → apply to events
    → AnimationRegistry.create() → BaseAnimation → apply to events
    → SizeCalculator.compute_size() → OverlaySize (tight dimensions)
    → apply_center_positioning() → \an5\pos() tags
    → SubtitleFile.save() → working .ass file
    → FFmpegRenderer.render() → transparent video overlay (.mov)

All stages emit AppEvent (STAGE, RENDER_START/PROGRESS/COMPLETE) via emitter.
```

## View-to-Visualizer Mapping

`MainWindow._VIEW_ATTRIBUTE_MAP` maps attribute names (e.g., `_volume_rectangle_view`) to `VisualizerOptions` enum values. When a visualizer type is selected in the dropdown, `MainWindow.__getattr__()` lazy-loads the corresponding View subclass, and `_create_visualizer()` instantiates the matching Visualizer subclass with the collected settings.

## Phase 11 Changes

Phase 11 simplified the composition model by removing `layer_type` in favour of extension-based `source_kind`, added `source_duration_ms` with looping support, unified Loaded Assets management, and aligned Render Composition timeline, preview, and final-render timing through shared FFmpeg helpers. It also consolidated Caption Animate audio input into one persisted field, added timeline scroll/zoom plus a playhead, and cleaned up theming (explicit `build_light_palette()`, `refresh_theme()`, "Light"/"Dark"/"Auto" labels). See the [UI](./architecture/development/UI.md), [Rendering](./architecture/development/RENDERING.md), and [Testing](./architecture/development/TESTING.md) development overviews for full details.
