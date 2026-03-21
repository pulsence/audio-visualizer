# Overview
This app turns any audio file into a video visualization. It was built for creating audiograms from spoken content, but works for music and general audio as well. The output video can be layered over images or footage in any editor.

Starting with v0.6.0, Audio Visualizer is a multi-tab workflow desktop app with six screens: Audio Visualizer, SRT Gen, SRT Edit, Caption Animate, Render Composition, and Assets. The app includes integrated subtitle generation (`audio_visualizer.srt`), subtitle editing with waveform sync, caption animation rendering (`audio_visualizer.caption`), and layer-based video composition.

This project is provided as-is under the MIT License. It is maintained for personal use, but shared in case it helps others.

## Features
- Multi-tab workflow with shared session assets across all screens.
- Audio visualization rendering with 14 visualizer types, live preview, and configurable output.
- Batch subtitle generation from audio/video using faster-whisper with word-level timing.
- Waveform-synced subtitle editor with undo/redo, QA lint profiles, and resync tools.
- Animated subtitle overlay rendering with preset-based styling and multiple quality tiers.
- Layer-based video composition with timeline, drag-to-reorder, looping, keying, and audio mixing.
- Workflow recipe system for reusable pipeline templates.
- Session asset management with cross-tab file sharing.
- Cancellable background jobs with global progress tracking.
- Project save/load and auto-save on close.

## Feature Table
| Area | Highlights |
| --- | --- |
| Rendering | MP4 output, configurable FPS/size/codec, optional audio mux |
| Preview | Embedded live preview panel, toggleable, auto-updates on changes |
| Volume Visualizers | Rectangle, Circle, Smooth Line, Force Line |
| Chroma Visualizers | Rectangle, Circle, Smooth Line, Lines, Force Rectangle/Circle/Line/Lines |
| Combined | Volume + Chroma rectangle mode |
| Projects | Save/load project files, auto-save, workflow recipes |
| SRT Generation | Whisper-based transcription, word-level timing, batch queue, multiple output formats |
| SRT Editing | Waveform-synced editor, undo/redo, QA lint, resync (shift, stretch, FPS drift, silence snap) |
| Caption Rendering | Animated subtitle overlays, preset system, transparent video output (H.264, ProRes 422 HQ, ProRes 4444) |
| Render Composition | Layer-based compositor, timeline with scroll/zoom, audio mixing, looping, chroma/luma keying |
| Assets | Session asset browser, cross-tab file sharing, project folder import |

## Visualizers
Volume:
- Rectangle (left-to-right or center-out flow).
- Circle (left-to-right or center-out flow).
- Smooth Line (flowed line).
- Force Line (mass-spring rope with impulse injection).

Chroma:
- Rectangle (12 bands).
- Circle (12 bands).
- Smooth Line (single curve across 12 bands).
- Lines (12 independent smooth lines).
- Force Rectangle (gravity + chroma force).
- Force Circle (gravity + chroma force).
- Force Line (single rope with 12 anchor forces).
- Force Lines (12 independent force ropes).

Combined:
- Rectangle (volume + chroma in one view).

# Dependencies:
- av
- numpy
- librosa
- PIL (Pillow)
- PySide6
- pyqtgraph
- faster-whisper
- python-docx
- pysubs2
- PyYAML
- pyannote.audio (optional, for speaker diarization)

# Set Up
Install Python 3 (3.13 was version this was developed in).
Run `pip install .` to install required packages.
Run `python -m audio_visualizer` from the project root.

## Run Scripts
- Windows: `run.bat`
- Bash (Linux/macOS): `run.sh`
