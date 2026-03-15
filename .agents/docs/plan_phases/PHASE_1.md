# Phase 1: Foundation, Dependency Lane, and MainWindow Decomposition

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 1.1: Update the GUI and test dependency lane

Move the host app onto the validated waveform-compatible Qt stack and add the UI-test tooling needed for the new tab architecture.

**Tasks:**
- Update `pyproject.toml` to move the host GUI stack from `PySide6==6.9.1` to `PySide6==6.10.2`, `PySide6_Addons==6.10.2`, and `PySide6_Essentials==6.10.2`
- Add `pyqtgraph==0.14.0` as the approved waveform dependency for SRT Edit
- Add `pytest-qt` to the `[dev]` extra for widget-level tests
- Verify editable install and dependency resolution in the project `.venv`
- Run a repo-level smoke pass for `pyqtgraph`, QtMultimedia, and the existing application entry point on the upgraded Qt stack
- Create/update tests for new features
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `pyproject.toml`
- Potentially modify `readme.md` if dependency notes or setup instructions need adjustment
- Create or modify dependency/tooling coverage tests under `tests/`

**Success criteria:** The project installs cleanly on the validated `PySide6==6.10.2` + `pyqtgraph==0.14.0` lane, existing non-UI tests still pass, and the repo has the tooling needed for Qt widget tests.

### 1.2: Create shared tab, job, and session infrastructure

Build the shared infrastructure that every tab will rely on so Stage Three does not re-implement job control, settings, undo wiring, or cross-tab file access in five different places.

**Tasks:**
- Create a `ui/tabs/` package for tab classes and shared tab helpers
- Add a `BaseTab` abstraction with the fixed Stage Three contract from the "Shared tab contract" section above: `tab_id`, `tab_title`, `validate_settings()`, `collect_settings()`, `apply_settings()`, `set_session_context()`, `set_global_busy()`, and optional `QUndoStack` helpers
- Create `SessionAsset` and `SessionContext` models for cross-tab asset registration, browsing, metadata updates, and removal using the required fields and categories defined in the "SessionContext contract" section above
- Add `SessionContext` signals for `asset_added`, `asset_updated`, `asset_removed`, and analysis-cache invalidation events so tabs do not poll
- Add a lightweight derived-analysis cache to `SessionContext` keyed by source asset plus analysis settings so waveform data, silence intervals, and reactive-caption analysis can be reused
- Create a shared Qt bridge that subscribes to `AppEventEmitter` and forwards progress, stage, log, and completion data into the shared worker signal vocabulary described in the "Shared worker contract" section above
- Add shared worker/job-state helpers so tabs expose a consistent signal surface to `MainWindow`, `JobStatusWidget`, and tab-local progress UIs
- Add a reusable session-asset picker/helper widget or helper API so all tabs can surface the same "session assets first, filesystem second" selection flow
- Create/update tests for base-tab lifecycle, session-asset registration, asset updates/removal, and analysis-cache invalidation
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/__init__.py`
- Create `src/audio_visualizer/ui/tabs/baseTab.py`
- Create `src/audio_visualizer/ui/sessionContext.py`
- Create `src/audio_visualizer/ui/workerBridge.py`
- Create `src/audio_visualizer/ui/workers/__init__.py`
- Modify `src/audio_visualizer/ui/__init__.py`
- Create `tests/test_ui_base_tab.py`
- Create `tests/test_ui_session_context.py`
- Create `tests/test_ui_workers.py`

**Success criteria:** Tabs can share a single `SessionContext`, register outputs as first-class assets, opt into undo support, and forward `AppEventEmitter` activity into Qt widgets without per-tab ad hoc glue code.

### 1.3: Replace `MainWindow` with a thin multi-tab shell

Convert the monolithic `MainWindow` into a navigation shell built around `QStackedWidget` and custom navigation, while preserving the existing render/thread ownership and top-level menu behavior.

**Tasks:**
- Refactor `MainWindow` to own a `QStackedWidget` plus a custom navigation widget built on `QListWidget` or an equivalent Qt-native sidebar control
- Move shared resources into the shell: `render_thread_pool`, `_background_thread_pool`, `SessionContext`, global busy state, and menu wiring
- Add a persistent job-status area that remains visible across tab switches and shows job type, source tab, progress, status text, and cancel action
- Add tab-level busy indicators/badges so users can see which tab owns active work even when they switch away
- Block second-job startup across tabs while the shared render pool is busy, and surface the reason clearly in the UI
- Update Edit-menu Undo/Redo actions to bind to the active tab's `QUndoStack` when one exists and disable otherwise
- Change render-complete behavior from immediate modal interruption to a completion notification with explicit Preview/Open actions that can launch `RenderDialog`
- Preserve Help/update-check functionality in the thinner shell
- Create/update widget tests for shell navigation, active-tab switching, undo-action rebinding, and shared busy-state handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/renderDialog.py`
- Create `src/audio_visualizer/ui/navigationSidebar.py`
- Create `src/audio_visualizer/ui/jobStatusWidget.py`
- Create `tests/test_ui_main_window.py`

**Success criteria:** `MainWindow` becomes a thin shell that hosts tab widgets, shared pools, `SessionContext`, and top-level menu/status behavior. The app supports tab switching without losing visibility into active jobs or undo/redo state.

### 1.4: Add versioned settings and project-schema foundations

Stage Three expands persistence from one audio-visualizer screen into a multi-tab application, so the settings format must become versioned, migratable, and capable of serializing tab state plus session assets.

**Tasks:**
- Create a versioned app/project settings schema that stores per-tab settings, shared UI state, and serialized `SessionContext` asset metadata
- Use the fixed Stage Three schema shape from the "App autosave / project schema" section above with `version`, `ui`, `tabs`, and `session` top-level sections
- Implement migration logic from the old Audio Visualizer-only `last_settings.json` shape into the new multi-tab schema with silent defaults
- Map the old `general`, `visualizer`, `specific`, and `ui` sections into `tabs.audio_visualizer` during migration instead of preserving the old top-level structure
- Update project save/load so saved project files include all tab settings plus session assets, not just the original visualizer settings
- Ensure auto-save on close and auto-load on startup use the new schema through `get_config_dir()`
- Keep machine-local ephemeral UI state out of the persisted data unless intentionally required. Do not store transient progress text, waveform zoom, current playback position, active selection rows, or temporary output paths created only for cancellation/worker internals.
- Create/update tests for schema versioning, backward compatibility, save/load round-trips, and missing-key defaults
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/app_paths.py` if helper paths are needed for new persistence artifacts
- Create `tests/test_ui_settings_schema.py`

**Success criteria:** Old settings files still load, new app/project saves round-trip all Stage Three state cleanly, and the schema has an explicit version/migration path for future releases.

### 1.5: Phase 1 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify the new dependency lane is consistent across `pyproject.toml` and the project environment
- Verify the new shell no longer depends on the old single-layout assumptions in `MainWindow`

**Phase 1 Changelog:**
- Upgraded the host GUI stack to the validated Qt/waveform dependency lane
- Added shared `BaseTab`, `SessionContext`, analysis-cache, and worker-bridge infrastructure
- Replaced the monolithic `MainWindow` layout with a thin multi-tab shell
- Added versioned settings/project-schema foundations for the Stage Three app model
