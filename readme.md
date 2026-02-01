# Overview
This app turns any audio file into a video visualization. It was built for creating audiograms from spoken content, but works for music and general audio as well. The output video can be layered over images or footage in any editor.

This project is provided as-is under the MIT License. It is maintained for personal use, but shared in case it helps others.

## Features
- Render videos from audio with configurable FPS, size, codec, and colors.
- Live preview panel in the main UI (toggleable).
- Per-visualizer settings with saved project presets.
- Volume and chroma (pitch class) visualizers, including "force" variants.
- Built-in update check via Help menu.

## Feature Table
| Area | Highlights |
| --- | --- |
| Rendering | MP4 output, configurable FPS/size/codec, optional audio mux |
| Preview | Embedded live preview panel, toggleable, auto-updates on changes |
| Volume Visualizers | Rectangle, Circle, Smooth Line, Force Line |
| Chroma Visualizers | Rectangle, Circle, Smooth Line, Lines, Force Rectangle/Circle/Line/Lines |
| Combined | Volume + Chroma rectangle mode |
| Projects | Save/load presets to JSON |

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
- Pyside 6

# Set Up
Install Python 3 (3.13 was version this was developed in).
Run `pip install .` to install required packages.
Run `python -m audio_visualizer` from the project root.

## Run Scripts
- Windows: `run.bat`
- Bash (Linux/macOS): `run.sh`
