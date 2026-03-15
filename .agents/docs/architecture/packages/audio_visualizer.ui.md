# audio_visualizer.ui

UI layer built on PySide6 (Qt 6). Contains the main application window, render dialog, and view system.

## mainWindow.py

### Class: MainWindow(QMainWindow)

The primary application window. Manages the full UI layout, visualizer selection, rendering, live preview, and settings persistence.

#### Class Variables

- `_VIEW_ATTRIBUTE_MAP: dict` — Maps view attribute names to `VisualizerOptions` enum values. Used for lazy-loading visualizer-specific settings panels via `__getattr__()`.

#### Layout Structure

The window uses a `QGridLayout` with these regions:

| Position | Content |
|----------|---------|
| (0, 0) | Heading label |
| (1, 0) | General settings panel (`GeneralSettingsView`) |
| (1, 1) | General visualizer settings (`GeneralVisualizerView`) |
| (2, 0) | Live preview video widget |
| (2, 1) | Specific visualizer settings (dynamic, swapped on selection change) |
| (3, 0) | Render controls (button, progress bar, checkboxes) |

#### Key Methods — UI Setup

- `_prepare_general_settings_elements()` — Creates the general settings panel
- `_prepare_general_visualizer_elements()` — Creates the visualizer settings panel
- `_prepare_specific_visualizer_elements()` — Creates the dynamic container for visualizer-specific views
- `_prepare_preview_panel_elements()` — Creates video preview widget with volume slider
- `_prepare_render_elements()` — Creates render button, progress bar, cancel button, checkboxes
- `_setup_menu()` — Creates Help menu with "Check for Updates" action
- `__getattr__()` — Lazy-loads visualizer view instances by attribute name

#### Key Methods — Visualizer Management

- `_build_visualizer_view(visualizer: VisualizerOptions) -> View` — Factory that creates the correct View subclass for a given visualizer type
- `_get_visualizer_view(visualizer: VisualizerOptions) -> View` — Returns cached view, creating it if needed
- `_show_visualizer_view(visualizer: VisualizerOptions)` — Shows the selected view and hides others
- `visualizer_selection_changed(visualizer)` — Signal handler for the visualizer dropdown

#### Key Methods — Rendering

- `validate_render_settings() -> tuple[bool, str]` — Validates all settings panels and returns `(is_valid, error_message)`
- `_create_visualizer() -> Visualizer` — Factory that instantiates the correct Visualizer subclass from current settings
- `render_video()` — Starts a full render (with optional 30-second preview)
- `render_preview()` — Starts a 5-second preview render
- `_start_render(...)` — Core render initiation: creates AudioData, VideoData, Visualizer, and submits RenderWorker
- `render_finished(video_data)` — Handles successful render completion
- `render_failed(error_msg)` — Shows error dialog
- `render_canceled()` — Handles render cancellation
- `cancel_render()` — Requests cancellation on the active RenderWorker
- `_reset_render_controls()` — Resets progress bar and buttons after render

#### Key Methods — Live Preview

- `_connect_live_preview_updates()` — Connects UI change signals to preview scheduling
- `_schedule_live_preview_update()` — Resets the 400ms debounce timer
- `_trigger_live_preview_update()` — Fires when the timer expires; starts a preview render
- `_show_preview_in_panel(video_data)` — Loads rendered preview into the QVideoWidget
- `_toggle_preview_panel()` — Shows/hides the preview panel

#### Key Methods — Settings Persistence

- `_collect_settings() -> dict` — Serializes all current settings to a dictionary
- `_apply_settings(data: dict)` — Deserializes and applies settings from a dictionary
- `_default_settings_path() -> Path` — Returns path to `last_settings.json` in the config dir
- `_save_settings_to_path(path)` — Writes settings as JSON
- `_load_settings_from_path(path)` — Loads settings from JSON
- `_load_last_settings_if_present()` — Auto-loads previous settings on startup
- `save_project()` / `load_project()` — File dialog flows for named project files
- `closeEvent(event)` — Auto-saves settings on window close

#### Key Methods — Updates

- `check_for_updates()` — Spawns an `UpdateCheckWorker` on the background thread pool
- `_handle_update_check_result(current, latest, url)` — Shows dialog if update available
- `_handle_update_check_error(msg)` — Shows error dialog

### Class: UpdateCheckWorker(QRunnable)

Background worker for checking GitHub releases.

- **Signals:** `finished(str, str, str)` (current, latest, url), `error(str)`
- **`run()`** — Calls `fetch_latest_release()` and `get_current_version()`, emits results

### Class: RenderWorker(QRunnable)

Background worker for video rendering.

- **Constructor:** `(audio_data, video_data, visualizer, preview_seconds, include_audio)`
- **Signals:** `finished(VideoData)`, `error(str)`, `status(str)`, `progress(int, int, float)`, `canceled()`
- **`run()`** — Full render pipeline: load audio → chunk → analyze → prepare container → prepare shapes → generate frames → optional audio mux → finalize
- **`cancel()`** — Sets cancellation flag, checked between frames
- **`_prepare_audio_mux()`** — Sets up audio resampler and output stream
- **`_mux_audio()`** — Encodes and muxes the audio track into the video container

## renderDialog.py

### Class: RenderDialog(QDialog)

Modal dialog for previewing a rendered video with volume controls and looping playback.

#### Class Variables

- `_last_volume = 100` — Persists volume setting across dialog instances

#### Constructor

- `(video_data: VideoData)` — Creates a `QMediaPlayer` + `QVideoWidget` + `QAudioOutput` + volume slider

#### Key Methods

- `_media_status()` — Starts playback when media is loaded
- `_cleanup_player()` — Safely stops and releases the media player
- `_volume_changed()` — Updates volume and persists to class variable
- `reject()` / `closeEvent()` — Clean up player on close
