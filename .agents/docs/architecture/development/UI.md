# UI Architecture

This document describes the Phase 9 UI shell: lazy tab startup, shared session state, browse-path defaults, and the main cross-tab workflows.

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
2. The saved app theme is applied immediately.
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

- `GeneralSettingsView` handles input/output file paths and now receives workspace context so project-folder defaults apply there too.
- `GeneralVisualizerView` and the chroma force views use clickable swatches for color selection.
- Per-band chroma force controls use tabbed 12-band editors instead of a single pipe-delimited text field.
- Live preview remains a debounced 5-second render driven from the shared render pool.

## Render Composition Workspace

`RenderCompositionTab` is now a layer editor backed by a persistent `CompositionModel`.

- Visual layers and audio layers both live in the model.
- Standard resolution presets (`HD`, `HD Vertical`, `2K`, `4K`) update width/height but manual edits still fall back to `Custom`.
- A timeline widget reflects the same timing model used by preview and final render.
- Audio is layered, delayable, trimmable, and mixed during final FFmpeg export.

## Assets Screen

`AssetsTab` is a support screen rather than a workflow stage.

- Shows a live table of current `SessionAsset` entries.
- Imports individual external files or folders through `WorkspaceContext` helper methods.
- Persists the visible imported-source list through tab settings so autosave/project restore can explain where external assets came from.
