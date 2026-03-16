# audio_visualizer.ui

PySide6 application shell and shared UI infrastructure.

## MainWindow

`MainWindow` is now a thin six-tab shell rather than the old single-screen visualizer window.

- Owns the shared `SessionContext`, the render `QThreadPool`, a background pool for update checks, the navigation sidebar, and the global `JobStatusWidget`.
- Instantiates `AudioVisualizerTab` eagerly, then registers lazy placeholders for `SRT Gen`, `SRT Edit`, `Caption Animate`, `Render Composition`, and `Assets`.
- Loads the saved settings file once during startup so app theme can be applied before lazy tab creation.
- Persists a versioned settings schema with top-level `app`, `ui`, `tabs`, and `session` sections.

### Shell responsibilities

- `_register_all_tabs()` adds the eager tab plus five lazy placeholders.
- `_ensure_tab_instantiated()` swaps a placeholder for the real tab on first activation and replays pending tab settings.
- `try_start_job()` / `finish_job()` enforce the single shared render/transcription slot.
- `show_job_*()` forwards lifecycle state into `JobStatusWidget`.
- `_open_settings()` shows `SettingsDialog`, applies theme changes, updates `SessionContext.project_folder`, and immediately saves the app state.

### Theme and settings

- Theme mode lives in `settings["app"]["theme_mode"]` with allowed values `off`, `on`, and `auto`.
- `auto` resolves against Qt color-scheme hints when available, but the stored mode remains `auto`.
- Session state is serialized through `SessionContext.to_dict()`, so project folder and imported assets travel with autosave/project files.

## JobStatusWidget

Persistent bottom-row status widget shared across tabs.

- Active jobs show owner, label, progress, status text, and a wired `Cancel` button.
- Terminal states (`completed`, `failed`, `canceled`) switch the button text to `Finished`.
- Completion actions (`Preview`, `Open Output`, `Open Folder`) stay available during the 5-second completed state when an output path exists.
- A widget-owned `QTimer` handles the timed auto-reset and is cancelled/restarted safely when the user clears the row or a new job begins.

## SessionContext

Cross-tab session registry for assets, roles, analysis cache, and project-level defaults.

- Stores `project_folder: Path | None` plus a `project_folder_changed` signal.
- Tracks generated and imported `SessionAsset` records.
- Provides `import_asset_file()` and `import_asset_folder()` helpers used by the Assets screen to deduplicate by resolved path and opportunistically probe media metadata through `mediaProbe.py`.
- Excludes analysis cache from persisted project files, but persists assets, role bindings, and project folder.

## SessionFilePicker

Shared browse-path resolver and session-aware chooser dialog.

- `resolve_browse_directory()` centralizes default-directory precedence:
  1. Current path (directory or parent of file path)
  2. Selected session asset parent
  3. `SessionContext.project_folder`
  4. User home directory
- `resolve_output_directory()` centralizes auto-derived output parents:
  1. Explicit output directory
  2. `SessionContext.project_folder`
  3. Source file parent
  4. User home directory
- `SessionFilePickerDialog` lets tabs choose from session assets first, then fall back to the filesystem.

## SettingsDialog

Modal settings dialog for app-level and session-level defaults.

- Theme section exposes `Off`, `On`, and `Auto`.
- Project section exposes the session `Project Folder`.
- Uses explicit accept semantics: widget edits do not persist until the user confirms the dialog.

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
