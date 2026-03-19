# UI Architecture

This document describes the Phase 10 UI shell: lazy tab startup, shared session state, browse-path defaults, and the main cross-tab workflows.

## Shell Layout

`MainWindow` now hosts a two-part shell:

- Left: `NavigationSidebar`
- Right: `QStackedWidget` containing one eager tab and five lazy tabs
- Bottom: global `JobStatusWidget`

Tab order:

1. `Audio Visualizer`
2. `SRT Gen`
3. `SRT Edit`
4. `Caption Animate`
5. `Render Composition`
6. `Assets`

Only `AudioVisualizerTab` is instantiated during startup. The remaining tabs are placeholders until the user activates them or another shell path needs them.

## Lazy Startup

Startup work is split so theme and shell state are ready before heavy tabs import their large dependencies.

1. `MainWindow` loads the last saved settings file once.
2. The saved app theme is applied immediately (fresh installs default to `auto` — system theme preference — rather than light mode).
3. The shell widgets are created.
4. The eager Audio Visualizer tab is instantiated.
5. Heavy tabs remain placeholders until first use.
6. Full settings are replayed, with per-tab settings queued for still-lazy tabs.

This keeps startup responsive while preserving autosave/project correctness.

## Shared Workspace State

`WorkspaceContext` is injected into every tab and holds:

- Session assets and role bindings
- Cached analysis results
- The session `project_folder`
- Imported external assets used by the Assets screen

Tabs should treat `WorkspaceContext.project_folder` as the default browse/output root when no stronger local context exists.

## Default Path Resolution

Browse and auto-output behavior now share central helpers from `sessionFilePicker.py`.

### Browse precedence

1. Current entered path
2. Selected session asset path
3. Session project folder
4. User home directory

### Auto-output precedence

1. Explicit output directory/path chosen by the user
2. Session project folder
3. Source/input file parent
4. User home directory

This rule is used across SRT Gen, Caption Animate, SRT Edit, Render Composition, the Assets import screen, Settings, and Audio Visualizer file pickers.

## Settings and Persistence

The persisted UI schema is versioned and split into four top-level sections:

- `app`: machine-level UI state such as `theme_mode`
- `ui`: active tab and window geometry
- `tabs`: per-tab settings payloads
- `session`: serialized `WorkspaceContext` state, including project folder and assets

`SettingsDialog` edits the app theme and the current session project folder. Changes are applied only when the dialog is accepted.

## Global Job Status

Long-running work across tabs is surfaced in one shared `JobStatusWidget`.

- Active work shows progress plus a live `Cancel` action.
- Terminal states keep a `Finished` button and auto-clear after 5 seconds.
- Completed jobs with an output path expose `Preview`, `Open Output`, and `Open Folder`.
- Starting a new job while a terminal timer is pending rewires the row back to the active cancel handler.

## Audio Visualizer View System

`AudioVisualizerTab` still owns the legacy visualizer-specific view registry.

- `GeneralSettingsView` handles input/output file paths and now receives workspace context so project-folder defaults apply there too. The video output path field auto-appends `.mp4` on focus-out when no extension is present.
- `GeneralVisualizerView` and the chroma force views use clickable swatches for color selection.
- Per-band chroma force controls use tabbed 12-band editors instead of a single pipe-delimited text field.
- Live preview remains a debounced 5-second render driven from the shared render pool.

## Render Composition Workspace

`RenderCompositionTab` is now a layer editor backed by a persistent `CompositionModel`.

- A unified layer list shows both visual (`[V]` prefix) and audio (`[A]` prefix) layers. Selecting a layer switches a `QStackedWidget` to display context-sensitive settings for that layer type.
- The preview panel sits on the right side of the layout.
- Render and output sections are merged; the separate cancel button has been removed.
- Standard resolution presets (`HD`, `HD Vertical`, `2K`, `4K`) update width/height but manual edits still fall back to `Custom`.
- A timeline widget reflects the same timing model used by preview and final render, with snap-to-align behavior at a 200ms threshold.
- Key color can be picked directly from the preview image.
- Audio is layered, delayable, trimmable, and mixed during final FFmpeg export.

## Caption Animate

`CaptionAnimateTab` owns subtitle overlay rendering with two preview modes.

- **Style Preview** shows a styled `QLabel` reflecting current typography/color settings for quick visual feedback.
- **Render Preview** runs a short (~5 second) actual render to a temporary directory using the shared job pool, then plays the result back via an embedded `QMediaPlayer`/`QVideoWidget`. Preview renders are clamped to 5 seconds via `RenderConfig.max_duration_sec` and do not register session assets.
- Full renders use the shared `MainWindow.render_thread_pool` with guarded `_safe_main_window()` calls so the tab is safe to use without a host window.
- `_create_delivery_output()` writes to a temp file then renames to avoid FFmpeg in-place conflicts. A process lock guards `_captured_process`. Preview temp files are cleaned up on rerender, failure, cancel, and close.
- Mixed-type animation parameters (numeric, string, `None`) are handled by a control registry that creates `QDoubleSpinBox` or `QLineEdit` widgets depending on the parameter type.

## SRT Gen

`SrtGenTab` provides batch whisper transcription with explicit model lifecycle.

- The model can be preloaded via a `Load Model` button or auto-loaded at transcription time.
- `SrtGenWorker` owns the model thread: the same thread that calls `load()` also calls `transcribe()`, avoiding cross-thread GPU handle issues.
- Cancel is responsive during model loading via a polling loop around the blocking load call.
- Compute type fallback uses a valid value (`int8`) instead of `"default"`.
- The event log panel uses an expanding size policy (no fixed 150px max height cap).
- Worker completed payload includes `device_used` and `compute_type_used`; the tab displays the resolved device info after transcription.

## SRT Edit

`SrtEditTab` provides waveform-synced subtitle editing with tab-scoped undo.

- Ctrl+wheel pans horizontally via an event filter on the `PlotWidget` viewport; the horizontal scrollbar stays synchronized.
- Inline table edits (text, timestamps, speaker) emit a structured signal from `SubtitleTableModel` instead of mutating the document directly. `SrtEditTab` converts these into undoable commands (`EditTextCommand`, `EditTimestampCommand`, `EditSpeakerCommand`).
- Multiline text edits auto-resize their table rows via a `dataChanged` handler.
- Audio loading is performed on a background `_WaveformLoadWorker(QRunnable)` with a monotonic request ID so stale completions are ignored. `WaveformView` exposes `set_loading_message()`, `set_error_message()`, and `clear_message()` for an overlay status API.

## Tab-Scoped Undo/Redo

`SrtEditTab` and `RenderCompositionTab` each own a `QUndoStack`. Local `Ctrl+Z`/`Ctrl+Y` shortcuts are bound per-tab. `MainWindow._update_undo_actions()` rebinds the Edit menu Undo/Redo actions on every tab switch so keyboard shortcuts never leak across tabs.

## Assets Screen

`AssetsTab` is a support screen rather than a workflow stage.

- Shows a live table of current `SessionAsset` entries.
- Imports individual external files or folders through `WorkspaceContext` helper methods.
- Persists the visible imported-source list through tab settings so autosave/project restore can explain where external assets came from.
