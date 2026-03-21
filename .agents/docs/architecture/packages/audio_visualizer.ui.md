# audio_visualizer.ui

PySide6 application shell and shared UI infrastructure.

## MainWindow

`MainWindow` is now a thin six-tab shell rather than the old single-screen visualizer window.

- Owns the shared `WorkspaceContext`, the render `QThreadPool`, a background pool for update checks, the navigation sidebar, and the global `JobStatusWidget`.
- Instantiates `AudioVisualizerTab` eagerly, then registers lazy placeholders for `SRT Gen`, `SRT Edit`, `Caption Animate`, `Render Composition`, and `Assets`.
- Loads the saved settings file once during startup so app theme can be applied before lazy tab creation.
- Persists a versioned settings schema with top-level `app`, `ui`, `tabs`, and `session` sections.

### Shell responsibilities

- `_register_all_tabs()` adds the eager tab plus five lazy placeholders.
- `_ensure_tab_instantiated()` swaps a placeholder for the real tab on first activation and replays pending tab settings.
- `try_start_job()` / `finish_job()` enforce the single shared render/transcription slot.
- `show_job_*()` forwards lifecycle state into `JobStatusWidget`.
- `_open_settings()` shows `SettingsDialog`, applies theme changes, updates `WorkspaceContext.project_folder`, and immediately saves the app state.

### Theme and settings

- Theme mode lives in `settings["app"]["theme_mode"]` with allowed values `off`, `on`, and `auto`.
- Fresh installs default to `auto` (system theme preference) instead of `off` (light mode).
- `auto` resolves against Qt color-scheme hints when available, but the stored mode remains `auto`.
- `_apply_theme()` clears the application stylesheet when switching to light mode (`off`), ensuring no dark-mode rules linger.
- Session state is serialized through `WorkspaceContext.to_dict()`, so project folder and imported assets travel with autosave/project files.

## JobStatusWidget

Persistent bottom-row status widget shared across tabs.

- Active jobs show owner, label, progress, status text, and a wired `Cancel` button.
- Terminal states (`completed`, `failed`, `canceled`) switch the button text to `Finished`.
- Completion actions (`Preview`, `Open Output`, `Open Folder`) stay available during the 5-second completed state when an output path exists.
- A widget-owned `QTimer` handles the timed auto-reset and is cancelled/restarted safely when the user clears the row or a new job begins.

## WorkspaceContext

Cross-tab workspace registry for assets, roles, analysis cache, and project-level defaults.

- Stores `project_folder: Path | None` plus a `project_folder_changed` signal.
- Tracks generated and imported `SessionAsset` records.
- Provides `import_asset_file()` and `import_asset_folder()` helpers used by the Assets screen to deduplicate by resolved path and opportunistically probe media metadata through `mediaProbe.py`.
- Excludes analysis cache from persisted project files, but persists assets, role bindings, and project folder.

## SessionFilePicker

Shared browse-path resolver and session-aware chooser dialog.

- `resolve_browse_directory()` centralizes default-directory precedence:
  1. Current path (directory or parent of file path)
  2. Selected session asset parent
  3. `WorkspaceContext.project_folder`
  4. User home directory
- `resolve_output_directory()` centralizes auto-derived output parents:
  1. Explicit output directory
  2. `WorkspaceContext.project_folder`
  3. Source file parent
  4. User home directory
- `SessionFilePickerDialog` lets tabs choose from session assets first, then fall back to the filesystem.

## SettingsDialog

Modal settings dialog for app-level and session-level defaults.

- Theme section exposes `Off`, `On`, and `Auto`.
- Project section exposes the session `Project Folder`.
- Uses explicit accept semantics: widget edits do not persist until the user confirms the dialog.

## NavigationSidebar

Left-side tab switcher that drives `QStackedWidget` tab display.

- Shows all six tabs with labels and optional busy-state indicators.
- Items use a highlight background for the selected tab with no border indicator.
- Sidebar clicks trigger `_ensure_tab_instantiated()` for lazy tabs before switching.

## CaptionAnimateTab

Subtitle overlay rendering with dual preview modes.

- Style Preview: live `QLabel` reflecting current typography/color settings.
- Render Preview: ~5 second render to a temporary directory via `RenderConfig.max_duration_sec`, played back in an embedded `QMediaPlayer`/`QVideoWidget`. Does not register session assets.
- Mixed-type animation parameters use a control registry: `QDoubleSpinBox` for numeric, `QLineEdit` for string/`None`.
- `_create_delivery_output()` writes to a temp file then renames to avoid FFmpeg in-place conflicts. A process lock guards `_captured_process`. Preview temp files are cleaned up on rerender, failure, cancel, and close.
- All `MainWindow` integration points use `_safe_main_window()` guards.

## SrtGenTab

Batch Whisper transcription with explicit model lifecycle.

- `SrtGenWorker` owns the model thread: load and transcribe happen on the same thread.
- Cancel-responsive during model loading via a polling loop.
- Compute type fallback resolves to a valid value instead of `"default"`.
- Event log panel uses an expanding size policy (no fixed 150px max height cap).
- Worker completed payload includes `device_used` and `compute_type_used`; the tab displays the resolved device info after transcription.

## SrtEditTab

Waveform-synced subtitle editing with tab-scoped undo.

- Ctrl+wheel pans horizontally; scrollbar stays synchronized.
- Inline table edits emit structured signals from `SubtitleTableModel` and are converted to undoable commands in the tab.
- Multiline text edits auto-resize rows.
- Audio loading runs on a background `_WaveformLoadWorker(QRunnable)` with a monotonic request ID to discard stale completions. `WaveformView` provides `set_loading_message()`, `set_error_message()`, and `clear_message()` overlay helpers.

## RenderCompositionTab

Layer-based video composition with timeline.

- Unified layer list with `[V]`/`[A]` prefixes; selecting a layer switches a `QStackedWidget` to context-sensitive settings. Preview panel on the right.
- Render and output sections are merged; the separate cancel button has been removed.
- `TimelineWidget` shows all layers on separate tracks with drag-to-move, handle-based trimming, and snap-to-align (200ms threshold) for both visual and audio layers.
- Key color can be picked from the preview image.
- Standard resolution presets (`HD`, `HD Vertical`, `2K`, `4K`, `Custom`) drive width/height; manual edits fall back to `Custom`.
- Audio layers use `adelay`, `atrim`, and `amix` FFmpeg filters for multi-source mixing.
- Tab-local `QUndoStack` with `Ctrl+Z`/`Ctrl+Y` shortcuts.

## AssetsTab

Support screen (not a workflow stage) for browsing and importing assets.

- Shows a live table of `SessionAsset` entries with metadata columns.
- Imports individual files or folders through `WorkspaceContext` helpers.
- Not included in `workflowRecipes.VALID_STAGES`.

## RenderDialog

Standalone media preview dialog used by global completion actions.

- Wraps `QMediaPlayer`, `QVideoWidget`, and `QAudioOutput`.
- Reuses a class-level remembered volume between dialog instances.

## UpdateCheckWorker

Background `QRunnable` that queries the updater module and reports current/latest version info back to `MainWindow`.

## RenderWorker

Legacy audio-visualizer render worker used by `AudioVisualizerTab`.

- Loads audio, performs chunking and analysis, prepares the output container, renders frames, and optionally muxes audio.
- Exposes progress, status, error, and cancellation signals consumed by the tab and the global shell.
