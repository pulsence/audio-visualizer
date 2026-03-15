# audio_visualizer

Root package for the Audio Visualizer application.

## Overview

- **Version:** 0.5.1
- **License:** MIT
- **Python:** >=3.13
- **Author:** Timothy Eck

## Entry Points

- `python -m audio_visualizer` — runs `__main__.py`, which calls `visualizer.main()`
- `audio-visualizer` — console script entry point defined in `pyproject.toml`, calls `audio_visualizer.visualizer:main`

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| av | 15.0.0 | Video/audio encoding via FFmpeg (PyAV) |
| librosa | 0.11.0 | Audio loading and analysis |
| numpy | 2.2.* | Numerical operations |
| Pillow | 11.3.0 | Image/frame generation |
| PySide6 | 6.9.1 | Qt 6 GUI framework |
| PySide6_Addons | 6.9.1 | Qt multimedia components |
| PySide6_Essentials | 6.9.1 | Qt core/widgets components |

### Optional Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 8.3.2 | Test framework |

## Package Structure

```
src/audio_visualizer/
    __init__.py          # Exports __version__ = "0.5.1"
    __main__.py          # Entry point shim: calls visualizer.main()
    visualizer.py        # QApplication bootstrap, icon resolution
    app_logging.py       # File-based logging setup
    app_paths.py         # Platform-specific config/data directories
    updater.py           # GitHub release update checker
    ui/                  # UI layer (see audio_visualizer.ui)
    visualizers/         # Rendering engines (see audio_visualizer.visualizers)
```

## `__init__.py`

Exports a single constant:

- `__version__: str` — current application version (`"0.5.1"`)

## `__main__.py`

Module execution entry point for `python -m audio_visualizer`. It first tries a relative import of `main()` from `visualizer.py`, then falls back to an absolute import if needed.
