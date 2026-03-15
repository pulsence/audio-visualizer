# Coding Patterns

This document defines the coding patterns and conventions for Audio Visualizer.

## Naming Conventions

The codebase uses mixed file naming conventions:

- **Utility modules:** snake_case (`app_logging.py`, `app_paths.py`, `updater.py`, `utilities.py`)
- **UI and visualizer modules:** camelCase (`mainWindow.py`, `generalView.py`, `genericVisualizer.py`, `circleVolumeVisualizer.py`)
- **Classes:** PascalCase (`MainWindow`, `AudioData`, `GeneralVisualizerView`, `CircleVisualizer`)
- **Methods and functions:** snake_case (`get_config_dir()`, `load_audio_data()`, `setup_logging()`, `generate_frame()`)
- **Enum values:** UPPER_SNAKE_CASE (`VOLUME_RECTANGLE`, `LEFT_TO_RIGHT`, `BOTTOM`)
- **Constants:** UPPER_SNAKE_CASE (`APP_DIRNAME`, `DEFAULT_REPO_OWNER`, `GITHUB_API_BASE`)

## Architecture Patterns

### Visualizer / View Separation

Each visualizer type has two paired classes:

1. A **Visualizer** subclass (in `visualizers/`) — the rendering engine that generates frames
2. A **View** subclass (in `ui/views/`) — the settings panel that collects user input

Each View also has a corresponding **Settings** class that packages the validated user input.

### Base Class Usage

- `Visualizer` (`visualizers/genericVisualizer.py`) — base class for all renderers. Subclasses implement `prepare_shapes()` and `generate_frame()`. These raise `NotImplementedError` in the base class (not `abc.ABC`).
- `View` (`ui/views/general/generalView.py`) — base class for all settings panels. Subclasses implement `validate_view()` and `read_view_values()`.

### Enum-Driven Configuration

- `VisualizerOptions` enum lists all 14 visualizer types
- `MainWindow._VIEW_ATTRIBUTE_MAP` maps view attributes to `VisualizerOptions` values
- `_build_visualizer_view()` is the factory that creates View instances
- `_create_visualizer()` is the factory that creates Visualizer instances

### Qt Patterns

- **Signals/Slots:** PySide6 signal connections for UI events
- **Threading:** `QThreadPool` (max 1 thread) for rendering via `QRunnable` workers (`RenderWorker`, `UpdateCheckWorker`)
- **Debounce:** `QTimer` (400ms) for live preview updates — setting changes schedule a preview, and rapid changes reset the timer
- **Media playback:** `QMediaPlayer` + `QVideoWidget` for preview and `RenderDialog`

## Logging

```python
import logging
logger = logging.getLogger(__name__)
```

Logging is configured once via `app_logging.setup_logging()`, which creates a `FileHandler` writing to `{config_dir}/audio_visualizer.log` at INFO level.

## Testing

- Tests use **pytest**
- `tests/conftest.py` adds `src/` to `sys.path`
- Run tests: `pytest tests/ -v`

## Type Hints

Type hints are used on function signatures where present in the codebase. The project does not use `from __future__ import annotations`.

## File Organization

- Core bootstrap and utilities: `src/audio_visualizer/` (top-level modules)
- UI code: `src/audio_visualizer/ui/`
- Settings views: `src/audio_visualizer/ui/views/` (organized by visualizer category)
- Rendering engines: `src/audio_visualizer/visualizers/` (organized by visualizer category)
- Tests: `tests/`
