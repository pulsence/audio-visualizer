# Overview
Audio Visualizer is a seven-screen desktop workflow app for audio visualization, subtitle generation, subtitle editing, caption animation, render composition, asset management, and advanced transcription/training tools. It is built around shared session assets so files produced in one tab can be picked directly in the next.

The current workflow screens are:
- `Audio Visualizer`
- `SRT Gen`
- `SRT Edit`
- `Caption Animate`
- `Render Composition`
- `Assets`
- `Advanced`

This project is provided as-is under the MIT License and is maintained primarily for personal use.

## Features
- Multi-tab workflow with project save/load, autosave, shared session assets, and workflow recipes.
- Audio visualization rendering with 14 visualizer types, live preview, and shared H.264 encoder selection with fallback.
- Bundle-first subtitle workflow: SRT Gen can create bundle v2 output, SRT Edit can edit it, and Caption Animate can consume it directly.
- SRT Edit word-level editing with waveform sync, undo/redo, markdown-aware editing, QA linting, and resync tools.
- Caption Animate bundle input, markdown-to-ASS styling, word-aware animations, MP4-first delivery, and optional advanced overlay export.
- Render Composition with center-origin positioning, linked video/audio ingest, layered audio mixing, real-time preview when runtime capabilities are available, and graceful fallback when they are not.
- Advanced tab tools for correction management, prompt terms, replacement rules, training-data export, LoRA training, and trained-model selection.
- Shared render/transcription queue with global status, cancellation, preview, and output actions.

## Visualizers
Volume:
- Rectangle (left-to-right or center-out flow)
- Circle (left-to-right or center-out flow)
- Smooth Line (flowed line)
- Force Line (mass-spring rope with impulse injection)

Chroma:
- Rectangle (12 bands)
- Circle (12 bands)
- Smooth Line (single curve across 12 bands)
- Lines (12 independent smooth lines)
- Force Rectangle (gravity + chroma force)
- Force Circle (gravity + chroma force)
- Force Line (single rope with 12 anchor forces)
- Force Lines (12 independent force ropes)

Combined:
- Rectangle (volume + chroma in one view)

## Dependencies
Base install:
- `av`
- `librosa`
- `numpy`
- `Pillow`
- `PySide6`
- `pyqtgraph`
- `faster-whisper`
- `python-docx`
- `pysubs2`
- `PyYAML`
- `PyOpenGL`
- `sounddevice`

Optional/runtime-specific:
- `pyannote.audio` for speaker diarization
- `torch`, `transformers`, `peft`, and `ctranslate2` for Advanced-tab LoRA training and conversion

## Setup
Install Python 3.13 or newer.

- Base install: `pip install .`
- Training stack for source installs: `pip install .[advanced]`
- Launch: `python -m audio_visualizer`

The official desktop build for the v0.7.0 workflow must ship both playback dependencies (`PyOpenGL`, `sounddevice`) and the advanced training stack. Source installs can keep the training stack optional.

## Run Scripts
- Windows: `run.bat`
- Bash (Linux/macOS): `run.sh`
