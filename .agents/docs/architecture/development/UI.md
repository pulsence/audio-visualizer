# UI Architecture

This document describes the MainWindow layout, view mapping system, live preview, and settings persistence.

## MainWindow Layout

`MainWindow` uses a `QGridLayout` with this structure:

```
┌─────────────────────────┬──────────────────────────┐
│ (0,0) Heading           │                          │
├─────────────────────────┼──────────────────────────┤
│ (1,0) General Settings  │ (1,1) General Visualizer │
│   - Audio file path     │   - Visualizer type      │
│   - Video output path   │   - Position (x, y)      │
│   - Resolution / FPS    │   - Alignment            │
│   - Codec / Bitrate     │   - Colors / Spacing     │
│   - Include audio       │   - Super-sampling       │
├─────────────────────────┼──────────────────────────┤
│ (2,0) Live Preview      │ (2,1) Specific Settings  │
│   - QVideoWidget        │   - Type-specific view   │
│   - Volume slider       │   (dynamically swapped)  │
├─────────────────────────┼──────────────────────────┤
│ (3,0) Render Controls   │                          │
│   - Render / Cancel     │                          │
│   - Progress bar / ETA  │                          │
│   - Preview checkbox    │                          │
└─────────────────────────┴──────────────────────────┘
```

## View Mapping

The `_VIEW_ATTRIBUTE_MAP` dictionary maps attribute names to `VisualizerOptions` enum values. When the user selects a visualizer type from the dropdown:

1. `visualizer_selection_changed()` is called
2. `_show_visualizer_view()` hides the current specific view and shows the new one
3. If the view hasn't been created yet, `__getattr__()` triggers lazy loading via `_build_visualizer_view()`
4. The view instance is cached in `_visualizer_views` for future use

### Factory Methods

- **`_build_visualizer_view(visualizer)`** — Creates the correct View subclass for the given `VisualizerOptions` value
- **`_get_visualizer_view(visualizer)`** — Returns cached view or creates one
- **`_create_visualizer()`** — Creates the correct Visualizer subclass from current settings (called at render time)

## Live Preview

The live preview system provides real-time feedback as users change settings:

1. **Connection** — `_connect_live_preview_updates()` connects change signals from `QLineEdit`, `QComboBox`, and `QCheckBox` widgets to `_schedule_live_preview_update()`

2. **Debounce** — `_schedule_live_preview_update()` starts/restarts a `QTimer` with a 400ms delay. Rapid setting changes reset the timer, preventing excessive renders.

3. **Trigger** — When the timer fires, `_trigger_live_preview_update()` calls `render_preview()`, which starts a 5-second preview render on the render thread pool.

4. **Display** — On completion, `_show_preview_in_panel()` loads the rendered video into the `QVideoWidget` for looping playback.

The preview video is written to `{data_dir}/preview_output.mp4`.

## Settings Persistence

### Auto-Save / Auto-Load

- **On close:** `closeEvent()` calls `_save_settings_to_path(_default_settings_path())` to save current settings as `last_settings.json` in the config directory.
- **On startup:** `_load_last_settings_if_present()` loads `last_settings.json` if it exists, restoring the previous session's settings.

### Project Save / Load

Users can explicitly save/load named project files via `save_project()` and `load_project()`, which use file dialogs for JSON files.

### Serialization Format

`_collect_settings()` returns a dict with keys for each settings category:
- General settings (file paths, resolution, codec, etc.)
- General visualizer settings (position, colors, etc.)
- Visualizer type identifier
- Type-specific settings (varies by visualizer)

`_apply_settings(data)` restores all settings from the dict, including:
- Setting widget values in general and visualizer views
- Switching to the correct visualizer type
- Populating type-specific view fields

## Adding a New View

To add a new visualizer settings view:

1. Create a View subclass in the appropriate `ui/views/` subdirectory
2. Create a corresponding Settings class to hold validated values
3. Implement `validate_view()` for input validation
4. Implement `read_view_values()` to return the Settings object
5. Update `MainWindow`:
   - Add entry to `_VIEW_ATTRIBUTE_MAP`
   - Add case to `_build_visualizer_view()`
   - Add validation in `validate_render_settings()`
   - Add serialization in `_collect_settings()`
   - Add deserialization in `_apply_settings()`
