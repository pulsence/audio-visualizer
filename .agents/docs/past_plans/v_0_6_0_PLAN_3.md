# v0.6.0 Stage Three - Multi-Tab Workflow UI Implementation Plan

This plan implements Stage Three of the v0.6.0 work: refactoring the current single-screen application into a multi-tab workflow desktop app with shared session assets, cancellable background jobs, SRT editing, caption animation, render composition, and workflow recipes.

**Scope:** Stage Three only. Stage Two package integration (`audio_visualizer.srt`, `audio_visualizer.caption`, and shared events) is assumed complete.

**Source research:** `V_0_6_0_RESEARCH_PLAN_3.md`

**Authoritative note:** This document is the implementation source of truth. `V_0_6_0_RESEARCH_PLAN_3.md` is background context only and should not be required to carry out the work below.

---

## Stage Three Target State

Stage Three ends with the application restructured as a five-screen workflow desktop app hosted inside a thin `MainWindow` shell. The finished app must have these top-level screens in this order:

1. `Audio Visualizer` — default landing screen; preserves the current product workflow
2. `SRT Gen` — transcription screen using `audio_visualizer.srt`
3. `SRT Edit` — waveform-backed subtitle editor with undo/redo, QA, and resync
4. `Caption Animate` — subtitle-to-overlay renderer using `audio_visualizer.caption`
5. `Render Composition` — final compositor for background/audio/overlay assembly

### MainWindow target layout

After Stage Three, `MainWindow` should be a thin shell with this shape:

```text
MainWindow
├── menu bar
│   ├── File
│   ├── Edit (Undo/Redo rebound to active tab when available)
│   └── Help
├── central widget
│   ├── NavigationSidebar (QListWidget-backed custom nav)
│   └── QStackedWidget
│       ├── AudioVisualizerTab
│       ├── SrtGenTab
│       ├── SrtEditTab
│       ├── CaptionAnimateTab
│       └── RenderCompositionTab
└── JobStatusWidget
    ├── active job label
    ├── progress indicator
    ├── status text
    └── cancel button
```

### Required application behavior

- Navigation uses `QStackedWidget` plus a custom sidebar, not `QTabWidget`.
- The app keeps one shared long-running user-job pool (`QThreadPool`, max 1) for render/transcribe/analyze/export work.
- Update checks keep using a separate background pool.
- The shell always shows active-job state, even when the user switches away from the source tab.
- Source tabs also show their own detailed progress views when focused.
- The sidebar shows a busy badge/spinner on tabs that own active work.
- Starting a second user job while the shared pool is busy is blocked with a clear status message; v0.6.0 does not support multiple simultaneous heavy jobs across tabs.
- Render completion should not auto-open a blocking modal dialog. Instead, show a completion notification with actions such as `Preview`, `Open Output`, and `Open Folder`. `RenderDialog` opens only when the user explicitly chooses preview.
- File-picking UIs across all tabs must support both current-session assets from `SessionContext` and raw filesystem browsing.

### Tab responsibilities

| Tab | Responsibilities | Primary outputs |
|-----|------------------|-----------------|
| `AudioVisualizerTab` | Current visualizer UI, live preview, visualizer rendering | Rendered visualizer video |
| `SrtGenTab` | Batch input queue, transcription settings, model lifecycle, cancellable queue execution | Subtitle file plus JSON/transcript/segment sidecars |
| `SrtEditTab` | Editable subtitle document model, waveform timeline, playback, undo/redo, QA, resync | Edited subtitle file |
| `CaptionAnimateTab` | Preset/style editing, cancellable caption rendering, audio-reactive animation | Caption overlay video |
| `RenderCompositionTab` | Layer layout, preset layouts, timeline rules, matte/key settings, final composition render | Final composed video |

### Chosen architectural decisions

These decisions are fixed for this implementation plan and should not be reopened during implementation unless a hard blocker is found:

| Topic | Decision |
|-------|---------|
| Tab host | `QStackedWidget` with custom navigation sidebar |
| MainWindow scope | Thin shell only; all workflow logic belongs in tab classes |
| Shared state | `SessionContext` owned by `MainWindow` and injected into tabs |
| Shared job model | Shared user-job pool (max 1) plus per-tab worker classes |
| Undo/redo | `QUndoStack` via `BaseTab`; used by SRT Edit and Render Composition only |
| SRT Gen scope | GUI-level batch orchestration over the existing single-file `transcribe_file()` API |
| SRT Edit parser strategy | Tab-local subtitle parser/editor model, not a Stage Two `audio_visualizer.srt` API expansion |
| Waveform stack | `pyqtgraph==0.14.0` on `PySide6==6.10.2` |
| Caption presets | Support built-ins, explicit preset files, and app-data preset library |
| Caption cancellation | In-process cancel by terminating FFmpeg |
| SRT cancellation | Cooperative queue checks plus killable subprocess boundary for per-file work |
| Composition engine | FFmpeg `filter_complex` renderer with hybrid auto-transcode/direct-render behavior |
| Composition timeline | Per-layer start/end with loop/trim/freeze behavior; final duration is max enabled layer end |
| Workflow reuse | Separate versioned recipe files, not merged into project saves or autosave state |

### Shared tab contract

Every tab class created in Stage Three must follow the same minimum contract through `BaseTab`:

- `tab_id: str` — stable storage and routing key such as `audio_visualizer`, `srt_gen`, `srt_edit`, `caption_animate`, `render_composition`
- `tab_title: str` — display label used in navigation/status UI
- `validate_settings() -> tuple[bool, str]` — tab-local validation before starting work
- `collect_settings() -> dict` — serializable settings payload with no live widget instances
- `apply_settings(data: dict) -> None` — restore settings from saved/project/recipe state
- `set_session_context(context: SessionContext) -> None`
- `set_global_busy(is_busy: bool, owner_tab_id: str | None) -> None` — disable or enable start controls based on shared-pool state
- `register_output_assets(...)` helpers or equivalent tab-local asset publication path
- optional undo helpers:
  - `_init_undo_stack(limit: int)`
  - `_push_command(command: QUndoCommand)`
  - `_clear_undo_stack()`
  - `undo_action()`
  - `redo_action()`

Tabs that render or run background work must also use the shared worker bridge/signal contract rather than emitting custom incompatible Qt signal shapes.

### Shared worker contract

All Stage Three workers should expose a consistent Qt-facing signal vocabulary so `MainWindow`, `JobStatusWidget`, and tabs can react uniformly:

- `started(job_type: str, owner_tab_id: str, label: str)`
- `stage(name: str, index: int | None, total: int | None, data: dict | None)`
- `progress(percent: float | None, message: str, data: dict | None)`
- `log(level: str, message: str, data: dict | None)`
- `completed(result: dict)` — includes output paths, asset metadata, and any follow-up actions
- `failed(error_message: str, data: dict | None)`
- `canceled(message: str | None)`

The bridge between `AppEventEmitter` and Qt signals should preserve stage/progress payloads rather than flattening them into plain strings. This is especially important for SRT Gen and Caption Animate, where downstream UI needs actual progress values, stage names, device/compute metadata, frame counts, and timing information.

### SessionContext contract

`SessionContext` is the cross-tab file provider and metadata registry for the whole app. It must carry enough information that downstream tabs can use outputs without lazily reprobe-opening every file.

#### Required `SessionAsset` fields

At minimum, each registered asset must carry:

- `id: str`
- `display_name: str`
- `path: Path`
- `category: str`
  - allowed starting categories for v0.6.0: `audio`, `subtitle`, `video`, `image`, `json_bundle`, `segments`, `transcript`, `config`, `preset`
- `source_tab: str | None`
- `role: str | None`
  - common roles: `primary_audio`, `subtitle_source`, `caption_overlay`, `visualizer_output`, `background`, `final_render`
- `width: int | None`
- `height: int | None`
- `fps: float | None`
- `duration_ms: int | None`
- `has_alpha: bool | None`
- `has_audio: bool | None`
- `is_overlay_ready: bool | None`
- `preferred_for_overlay: bool | None`
- `metadata: dict[str, object]`

#### Required `metadata` payloads by asset type

- Audio Visualizer outputs:
  - `include_audio_in_output`
  - `resolution`
  - `codec`
  - `visualizer_type`
- SRT Gen primary subtitles:
  - `format`
  - `mode`
  - `language`
  - `word_level_enabled`
  - `diarization_enabled`
- SRT Gen JSON bundles:
  - `contains_segments`
  - `contains_word_timing`
  - `contains_speaker_labels`
- Caption Animate outputs:
  - `quality`
  - `preset_name`
  - `render_quality`
  - `alpha_expected`
- Composition outputs:
  - `audio_source_asset_id`
  - `layer_count`
  - `export_profile`

#### Analysis cache contract

`SessionContext` must also own a lightweight reusable analysis cache keyed by:

`(asset_identity, analysis_type, settings_signature)`

Where:
- `asset_identity` is a stable value derived from asset id plus normalized path or fingerprint
- `analysis_type` starts with `waveform`, `silence`, and `audio_reactive`
- `settings_signature` captures the parameters that would change the analysis output

This cache exists so:
- SRT Edit can reuse waveform and silence data
- Caption Animate can reuse audio-reactive analysis
- Multiple tabs do not independently recompute the same long-running audio analysis

### Cross-tab asset rules

These are concrete v0.6.0 rules and should be implemented as-is:

- Audio Visualizer outputs are treated as video assets first. If they contain audio, that embedded audio is ignored by Composition unless the user explicitly selects it as the authoritative audio source.
- SRT Gen should register the primary subtitle file plus all generated sidecars. JSON bundles are especially important because SRT Edit resync features depend on them.
- Caption Animate outputs are classified like this:
  - `large` quality (ProRes 4444, `yuva444p10le` — has alpha channel) is the preferred reusable alpha-capable overlay intermediate
  - `small` quality (H.264, `yuva420p`) may be accepted for reuse only after Composition auto-normalizes it into a composition-friendly intermediate
  - `medium` quality (ProRes 422 HQ, `yuv422p10le` — no alpha channel) should be treated as opaque unless Composition explicitly normalizes or re-renders it
- Static images default to stretching across the full composition duration unless the user trims them earlier.
- Background video, visualizer video, and caption overlay layers support per-layer start/end time plus `loop`, `trim`, or `freeze_last_frame` behavior.
- Composition uses exactly one authoritative audio source in v0.6.0. The app does not need multi-track audio mixing in this release.
- SRT/ASS subtitle files may be rendered directly inside Composition only when the user intentionally chooses a direct-render caption layer path; otherwise Composition consumes the already-rendered overlay asset from Caption Animate.

### Settings, project, and recipe schemas

Stage Three needs three related but distinct storage artifacts:

1. App autosave state
2. Project save/load files
3. Workflow recipe files

#### App autosave / project schema

Use a versioned JSON shape with stable top-level sections. The exact implementation may use dataclasses or helper objects, but the stored structure should be equivalent to:

```json
{
  "version": 1,
  "ui": {
    "last_active_tab": "audio_visualizer",
    "window": {
      "width": 1600,
      "height": 1000,
      "maximized": false
    }
  },
  "tabs": {
    "audio_visualizer": {},
    "srt_gen": {},
    "srt_edit": {},
    "caption_animate": {},
    "render_composition": {}
  },
  "session": {
    "assets": [],
    "roles": {}
  }
}
```

Implementation rules:

- Autosave state lives under `get_config_dir()` and continues replacing the old `last_settings.json`.
- Project files may reuse the same schema shape but should omit purely machine-local window state when appropriate.
- The old pre-Stage-Three settings shape (`general`, `visualizer`, `specific`, `ui`) must migrate into `tabs.audio_visualizer`.
- Missing new-tab keys must silently default on load.
- Do not persist ephemeral state such as current playback position, waveform zoom, transient progress status, or selection highlights.

#### Workflow recipe schema

Recipes are not project saves. They are reusable workflow templates. The stored shape should be equivalent to:

```json
{
  "version": 1,
  "name": "Shorts Caption Workflow",
  "enabled_stages": {
    "srt_gen": true,
    "srt_edit": true,
    "caption_animate": true,
    "render_composition": true
  },
  "asset_roles": {
    "primary_audio": null,
    "subtitle_source": null,
    "caption_source": null,
    "background": null
  },
  "tabs": {
    "srt_gen": {},
    "srt_edit": {},
    "caption_animate": {},
    "render_composition": {}
  },
  "references": {
    "caption_preset": null,
    "layout_preset": null,
    "lint_profile": "pipeline_default"
  },
  "export": {
    "naming_rule": "{audio_stem}_final",
    "target_dir": null
  }
}
```

Recipe rules:

- Store recipes under the app data/config area, not in the repo root.
- Support explicit import/export as `.avrecipe.json`.
- Prefer semantic asset roles over absolute paths.
- Allow absolute or relative asset bindings only when the user intentionally saves them.
- Keep recipes versioned independently from project files so they can evolve without breaking session saves.

### Composition control surface

Render Composition must implement these concrete v0.6.0 controls:

- layer position: `x`, `y`
- layer size: `width`, `height`
- z-order
- layer timing:
  - `start_ms`
  - `end_ms`
  - `behavior_after_end`: `freeze_last_frame`, `hide`, `loop`
- audio source selector:
  - one standalone audio asset or one embedded stream from a selected video asset
- matte/key controls:
  - `mode`: `colorkey`, `chromakey`, `lumakey`
  - `key_target`
  - `threshold`/`similarity`
  - `blend`/`softness`
  - cleanup values for erode/dilate/feather
  - despill controls
  - invert toggle
  - alpha/matte debug preview toggle

### Subtitle QA and resync baseline

SRT Edit must ship with:

- inline warnings in the subtitle table
- a dedicated QA issue panel
- three named lint profiles:
  - `pipeline_default` — mirrors current SRT formatting defaults
  - `accessible_general`
  - `short_form_social`
- undoable machine-fix actions
- preview-based resync operations:
  - global shift
  - shift from cursor onward
  - two-point stretch
  - FPS drift correction
  - silence snap
  - segment/word timing reapply

Important implementation rules:

- word-level resync quality depends on JSON bundles generated with `word_level=True`
- speaker-aware resync is only available when speaker labels exist, which currently means transcript-mode transcriptions
- silence snap may directly import internal SRT helpers if they are not exported through `audio_visualizer.srt.__init__`

---

## Phase Plans

The detailed phase plans for Stage Three are embedded below in execution order.

## Phase 1: Foundation, Dependency Lane, and MainWindow Decomposition

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

---

## Phase 2: Extract the Audio Visualizer Tab

### 2.1: Move the current visualizer UI into `AudioVisualizerTab`

Extract the existing application workflow into a dedicated default tab so the original product remains fully functional inside the new shell before additional tabs are added.

**Tasks:**
- Create `AudioVisualizerTab` and move the current general settings, general visualizer settings, specific visualizer settings, preview panel, and render controls into it
- Preserve the existing visual hierarchy inside the tab: heading, settings panels, preview panel, specific visualizer controls, and render controls. The user should experience the old screen as "moved into a tab", not redesigned during extraction.
- Move the live-preview timer and render-start/cancel UI behavior out of `MainWindow` and into the tab
- Keep the current Audio Visualizer experience as the default landing tab
- Ensure the tab exposes standardized `collect_settings()`, `apply_settings()`, `validate_settings()`, and asset-registration hooks through `BaseTab`
- Preserve preview debouncing and the current preview image behavior
- Create/update tests for tab construction, settings round-trip, preview wiring, and render-control state transitions
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/audioVisualizerTab.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/views/general/generalSettingViews.py`
- Modify `src/audio_visualizer/ui/views/general/generalVisualizerView.py`
- Create `tests/test_ui_audio_visualizer_tab.py`

**Success criteria:** The existing Audio Visualizer workflow works from inside `AudioVisualizerTab` with no feature regression relative to the pre-tab application.

### 2.2: Replace `MainWindow`-era branching with explicit view and visualizer registries

The old `__getattr__`, `_VIEW_ATTRIBUTE_MAP`, `_build_visualizer_view()`, `_create_visualizer()`, `_collect_settings()`, and `_apply_settings()` patterns do not scale inside the tab architecture and should be replaced while the original visualizer logic is being moved.

**Tasks:**
- Replace magic `__getattr__` view loading with explicit registries or factory mappings owned by `AudioVisualizerTab`
- Refactor the visualizer factory logic into a structured registry instead of a 14-branch monolith
- Add `apply_settings(data: dict)` methods to View classes so tabs no longer reach through direct widget internals from the outside
- Add explicit setter/getter helpers to general settings and general visualizer views where needed
- Remove or isolate the old `MainWindow`-only serialization and factory branches once the tab owns those responsibilities
- Create/update tests for view creation, specific-view switching, settings application, and visualizer instantiation by registry
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/audioVisualizerTab.py`
- Modify `src/audio_visualizer/ui/views/__init__.py`
- Modify `src/audio_visualizer/ui/views/general/generalSettingViews.py`
- Modify `src/audio_visualizer/ui/views/general/generalView.py`
- Modify `src/audio_visualizer/ui/views/general/generalVisualizerView.py`
- Modify relevant files under `src/audio_visualizer/ui/views/chroma/`, `src/audio_visualizer/ui/views/volume/`, and `src/audio_visualizer/ui/views/general/`
- Modify `src/audio_visualizer/visualizers/__init__.py`
- Create or modify `tests/test_ui_audio_visualizer_tab.py`

**Success criteria:** Audio Visualizer view creation, visualizer creation, and settings application are explicit and tab-local. The old `MainWindow` branching and cross-class widget access are no longer required.

### 2.3: Register Audio Visualizer outputs in `SessionContext`

Once the original tab is extracted, its renders need to participate in the new cross-tab workflow by publishing reusable assets and metadata.

**Tasks:**
- Register completed visualizer renders as `SessionAsset` entries with width, height, FPS, duration, audio-presence, and source-tab metadata
- Define how "Include Audio in Output" is represented in the asset metadata so Composition can treat embedded audio intentionally rather than accidentally
- Ensure project save/load restores Audio Visualizer output references and tab settings cleanly
- Reuse the shared completion-notification flow and `RenderDialog` launch path from the new shell
- Create/update tests for asset registration, settings restoration, and output-metadata persistence
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/audioVisualizerTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Create or modify `tests/test_ui_audio_visualizer_tab.py`

**Success criteria:** Audio Visualizer renders appear in `SessionContext` as reusable assets with enough metadata for later tabs to consume them without re-probing raw files at every selection.

### 2.4: Phase 2 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify the Audio Visualizer tab remains feature-equivalent to the original single-screen workflow

**Phase 2 Changelog:**
- Extracted the original product UI into `AudioVisualizerTab`
- Replaced `MainWindow`-era dynamic branching with explicit tab-local registries and view APIs
- Registered Audio Visualizer outputs as reusable session assets

---

## Phase 3: Build the SRT Gen Tab

### 3.1: Create the SRT Gen UI and settings model

Implement the transcription tab as a preset-driven, batch-capable UI with a clean default surface and a full advanced feature set behind structured grouping.

**Tasks:**
- Create `SrtGenTab` with batch input-file selection, queue display, primary output controls, and advanced panels for correction/script inputs, side outputs, diarization, and diagnostics
- Use a preset-driven form with collapsible Advanced sections so common workflows stay simple while the full `audio_visualizer.srt` surface remains available
- Add explicit model controls with a "Load Model" action plus load-on-demand fallback when starting a transcription
- Expose the full `ResolvedConfig` settings surface organized into structured groups: **Model** (model_name, device, strict_cuda), **Formatting** (max_chars, max_lines, target_cps, min_dur, max_dur, allow_commas, allow_medium, prefer_punct_splits, min_gap, pad), **Transcription** (vad_filter, condition_on_previous_text, no_speech_threshold, log_prob_threshold, compression_ratio_threshold, initial_prompt), **Silence** (silence_min_dur, silence_threshold_db), **Prompt/alignment** (initial_prompt text/file, correction_srt, script_path), **Output** (output_path, fmt, word_level, mode, language, word_output_path), **Side outputs** (transcript_path, segments_path, json_bundle_path), and **Advanced/diagnostics** (diarize, hf_token, keep_wav, dry_run). Common settings (model, format, mode, output path) belong in the default view; the rest go into collapsible advanced groups.
- Default word-level output on, or clearly warn when it is disabled, because later resync quality depends on it
- Add config-file import/browse and "open config folder" actions backed by `get_srt_config_dir()`, which also triggers `ensure_example_configs()` seeding on first access. Support loading saved JSON config files from the app-data config library alongside the in-memory `PRESETS` dropdown.
- Add file-picker integration that can browse both filesystem inputs and relevant assets from `SessionContext`
- Create/update tests for settings collection/application, preset application, queue serialization, and advanced-option validation
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_srt_gen_tab.py`

**Success criteria:** The SRT Gen tab supports queued inputs, a usable default form, and the full advanced transcription feature surface without overwhelming the common path.

### 3.2: Implement cancellable batch transcription orchestration

Batch transcription must be cancelable even though the current `audio_visualizer.srt` API is synchronous, so the tab needs both queue-level orchestration and a killable per-file execution boundary.

**Tasks:**
- Create a Qt worker for SRT Gen that owns queue sequencing, progress forwarding, and cancel-state transitions
- Implement a child-process transcription runner that streams structured JSONL events to the parent and allows soft-cancel plus hard-kill fallback
- Add parent-owned temporary-workspace management and cleanup after normal completion, cancellation, or forced termination
- Add cooperative cancellation checks between files and between major pipeline stages where the in-process code can reasonably surface them
- Preserve event payloads from `audio_visualizer.srt` through the worker bridge so the tab can show stage/progress/model status accurately
- Reuse the loaded `ModelManager` instance across batch queue items to avoid reloading the model between files. Note that `ModelManager` caches only one model at a time — switching model names unloads the previous model before loading the new one, so the batch worker should hold a consistent model reference for the duration of a queue run and the GUI should not imply multi-model residency.
- Ensure batch cancel stops before the next file, and file-level cancel terminates the child process when needed
- Create/update tests for queue orchestration, event relay, soft cancel, hard-kill fallback, and cleanup behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/srtGenWorker.py`
- Create `src/audio_visualizer/ui/workers/srtTranscribeChild.py`
- Modify `src/audio_visualizer/srt/srtApi.py`
- Modify `src/audio_visualizer/srt/core/pipeline.py`
- Modify `src/audio_visualizer/srt/core/whisperWrapper.py`
- Create `tests/test_srt_gen_worker.py`

**Success criteria:** SRT Gen jobs can be started, monitored, and canceled from the UI. Batch jobs stop cleanly, per-file work can be forcibly terminated when necessary, and temporary artifacts are cleaned up predictably.

### 3.3: Register transcription outputs and sidecars for downstream tabs

SRT Gen is the first cross-tab producer in the new workflow, so it must publish its outputs in a way that SRT Edit, Caption Animate, and Composition can reuse without manual re-entry.

**Tasks:**
- Register generated subtitle files, JSON bundles, transcript outputs, segment sidecars, and optional word-output files as `SessionAsset` entries with source metadata
- Capture enough metadata to distinguish primary subtitle outputs from diagnostic sidecars
- Add tab actions to send generated outputs directly into SRT Edit and Caption Animate selection flows
- Ensure project save/load restores queued inputs, tab settings, and generated output references correctly
- Create/update tests for asset registration, downstream handoff metadata, and project-state restoration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Create or modify `tests/test_ui_srt_gen_tab.py`

**Success criteria:** SRT Gen outputs become reusable session assets, including the JSON bundles needed for later resync work, and downstream tabs can consume them without the user re-browsing the filesystem.

### 3.4: Phase 3 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify batch orchestration, cancel behavior, and session-asset publication all work together

**Phase 3 Changelog:**
- Added a batch-capable SRT Gen tab with a full advanced settings surface
- Implemented cancellable transcription orchestration around the synchronous SRT pipeline
- Registered transcription outputs and sidecars in `SessionContext` for downstream reuse

---

## Phase 4: Build the SRT Edit Tab

### 4.1: Create the editable subtitle document model and round-trip I/O

SRT Edit needs its own stable editing model and round-trip layer before the waveform/editor UI is added, because the integrated `audio_visualizer.srt` package does not currently expose a general editable parser model for this use case.

**Tasks:**
- Create a tab-local subtitle document model that tracks ordered blocks, text, timing, speaker labels, dirty state, and source metadata
- Implement `.srt` load/save round-tripping into that model, using `pysubs2` mapping or equivalent tab-local parsing logic as the underlying parser layer
- Preserve enough information for safe re-save without collapsing the editing model into the shared `audio_visualizer.srt` public API
- Add model-level operations for add/remove/split/merge and timestamp normalization
- Create/update tests for parser round-trip fidelity, timestamp normalization, split/merge behavior, and save output correctness
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/__init__.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/document.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/parser.py`
- Create `tests/test_srt_edit_model.py`

**Success criteria:** The app can load an existing SRT into a stable editable model, modify it, and write it back without relying on ad hoc widget state as the source of truth.

### 4.2: Build the waveform, playback, and table-editing foundation

With the document model in place, the next milestone is an editor that can display waveform context, synchronize playback, and expose precise table-based editing before the drag UI is layered on top.

**Tasks:**
- Build the waveform view on `pyqtgraph` using downsampling, clip-to-view, region overlays, and a playback cursor
- Use `PlotWidget`/`PlotItem` with `setDownsampling(auto=True, mode='peak')` and `setClipToView(True)` so large audio files remain responsive
- Represent subtitle timing regions with pyqtgraph items that support draggable boundaries and selection highlighting; include a distinct playback cursor line that can also support click-to-seek
- Add a split layout with waveform on top and an editable subtitle table below
- Integrate `QMediaPlayer` and `QAudioOutput` for playback, seeking, cursor updates, and selection-follow behavior
- Support selecting a subtitle row from the table and highlighting the corresponding waveform region
- Load waveform/analysis data through the shared `SessionContext` analysis cache when possible; waveform generation for long files should happen in a background worker rather than blocking the UI thread
- Create/update tests for widget construction, selection sync, playback-position updates, and large-file waveform data handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`
- Create `tests/test_ui_srt_edit_tab.py`

**Success criteria:** Users can load an SRT and its audio source, see subtitle timing against a waveform, play/seek audio, and edit timestamps/text numerically in a synchronized editor.

### 4.3: Add full editing interactions and undo/redo support

After the waveform and table are stable, add the direct-manipulation editing layer and make every destructive change safely undoable.

**Tasks:**
- Add draggable waveform-region handles for adjusting subtitle start/end times visually
- Implement `QUndoCommand` subclasses for move-region, edit-timestamp, edit-text, add/remove, and split/merge operations
- Initialize the SRT Edit undo stack with a limit of 200 (high limit because subtitle editing produces many small changes)
- Push drag commands on mouse release only, and coalesce text/numeric edits with `mergeWith()` to avoid noisy undo history
- Clear the SRT Edit undo stack when a new subtitle document is loaded
- Wire tab-local undo/redo actions into the shared Edit menu through `BaseTab`
- Create/update tests for command apply/revert behavior, merge/coalesce logic, and stack-reset behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- Create `tests/test_ui_undo.py`
- Create or modify `tests/test_ui_srt_edit_tab.py`

**Success criteria:** SRT Edit supports both numeric and drag-based timing changes, and every editor action can be undone/redone through a tab-local `QUndoStack`.

### 4.4: Add the subtitle QA panel and named lint profiles

Subtitle QA belongs in the editor because that is where the editable source of truth, undo stack, and waveform context already live.

**Tasks:**
- Implement lint checks for readability, timing integrity, text quality, speaker consistency, and render safety
- Seed the default lint profile from `ResolvedConfig.formatting` so SRT Gen and SRT Edit agree on baseline thresholds
- Add named lint profiles such as `pipeline_default`, `accessible_general`, and `short_form_social`
- Ensure `pipeline_default` explicitly incorporates `max_chars`, `max_lines`, `target_cps`, `min_dur`, `max_dur`, `min_gap`, and `pad` from the current formatting defaults instead of hard-coding a second independent rule set
- Show inline severity hints in the table and a dedicated QA panel with click-to-jump navigation
- Make every machine-fix action undoable through the shared SRT Edit undo stack
- Create/update tests for lint rules, profile overrides, issue navigation, and machine-fix undo behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/lint.py`
- Create `tests/test_srt_edit_lint.py`

**Success criteria:** SRT Edit can highlight subtitle quality problems inline and through a QA panel, using profile-driven thresholds that remain consistent with the transcription pipeline defaults.

### 4.5: Add the auto-resync toolkit

Resync operations are a major differentiator for the editor and should be implemented after the waveform, document model, and undo system are all stable.

**Tasks:**
- Implement batch timing tools for global shift, shift from cursor onward, two-point stretch, and FPS-drift correction
- Add preview-diff flows so users can review timing changes before applying them
- Integrate silence-based snapping using `detect_silences()` from `srt.io.audioHelpers` and `apply_silence_alignment()` from `srt.core.subtitleGeneration`. These helpers are **not exported** from `srt.__init__.py`, so SRT Edit must import them directly from the internal modules (e.g., `from audio_visualizer.srt.io.audioHelpers import detect_silences`). If a cleaner public API boundary is preferred, add the needed symbols to `srt.__init__.py`'s `_EXPORTS` and `src/audio_visualizer/srt/__init__.py` to the files list for this task.
- Reapply word-level or segment timing from generated JSON bundles when compatible sidecars exist in `SessionContext`. Note that JSON bundles only include word-level timing when the transcription was run with `word_level=True`; when word data is absent, the resync UI should clearly indicate reduced resync quality and fall back to segment-level timing only.
- Handle speaker-aware resync boundaries when diarization labels are present. Note that `SubtitleBlock.speaker` is only populated in `PipelineMode.TRANSCRIPT` mode — general and shorts-mode transcriptions will not have speaker data. The UI should degrade gracefully when speaker labels are absent rather than offering speaker-aware operations that cannot function.
- Scope resync operations to either the current selection or the full document
- Apply each resync operation as a single undoable command or macro
- Create/update tests for resync math, preview generation, selection scoping, silence snapping, JSON-bundle timing reuse, missing word-level data fallback, and absent speaker-label handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Create `src/audio_visualizer/ui/tabs/srtEdit/resync.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_srt_edit_resync.py`

**Success criteria:** SRT Edit includes previewable, undoable batch retiming tools that can reuse silence data and word/segment sidecars from earlier transcription work when available.

### 4.6: Phase 4 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify round-trip editing, waveform interaction, QA checks, and resync tools all operate against the same document model

**Phase 4 Changelog:**
- Added a tab-local subtitle document model and round-trip I/O for SRT editing
- Built a waveform-plus-table editor with playback sync
- Added drag editing and full undo/redo support
- Added subtitle QA/lint tooling and batch auto-resync operations

---

## Phase 5: Build the Caption Animate Tab

### 5.1: Create the Caption Animate UI and full preset workflow

The caption tab should expose the full capability of the integrated `audio_visualizer.caption` package while supporting all three approved preset-source paths: built-ins, explicit files, and the app-data preset library.

**Tasks:**
- Create `CaptionAnimateTab` with subtitle input, output path, FPS, quality, safety scale, animation toggle, and reskin controls
- Build a unified preset-selection workflow that combines built-ins, explicit file browse, and the app-data preset library. Leverage `ensure_example_presets()` (called internally by the caption package's data-dir helpers) to seed bundled example preset files (`preset.json`, `word_highlight.json`) into `get_data_dir()/caption/presets/` on first access so the library is not empty on initial launch.
- Expose the full `PresetConfig` style surface in structured groups (font, colors, outline, shadow, blur, line spacing, max width, padding, alignment, margins, wrap style, animation type and params) rather than limiting the tab to preset-only controls
- Expose the built-in animation registry types (`fade`, `slide_up`, `scale_settle`, `blur_settle`, `word_reveal`) plus their default parameter surfaces so users can edit animation behavior without leaving the GUI
- Add preset import/export and "open preset folder" actions backed by the app-data directory
- Add a lightweight in-tab preset preview for style validation before full render. v0.6.0 uses a static sample-text preview inside the tab; full motion preview remains the responsibility of an actual render.
- Ensure file pickers can browse both the filesystem and compatible subtitle assets from `SessionContext`
- Create/update tests for preset-source resolution, settings round-trip, and full-surface preset serialization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_caption_tab.py`

**Success criteria:** The Caption Animate tab supports the full caption-style surface and all approved preset-source paths without depending on cwd-relative discovery.

### 5.2: Implement cancellable caption rendering

Caption rendering is synchronous today, but the underlying FFmpeg boundary makes true in-process cancel support achievable for Stage Three.

**Tasks:**
- Create a caption-render Qt worker that owns progress/event bridging, process handle retention, cancel-state updates, and output registration
- Modify the caption render stack so the worker can terminate the active FFmpeg subprocess cleanly on user cancel
- Preserve stage/progress events and completion/error payloads from the caption package through the worker bridge
- Ensure cancellation cleans up partial outputs and resets tab/job-shell state correctly
- Register finished caption renders as `SessionAsset` entries with alpha, resolution, duration, and quality metadata
- Create/update tests for render-worker lifecycle, progress forwarding, cancel behavior, and output registration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- Modify `src/audio_visualizer/caption/captionApi.py`
- Modify `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Create `tests/test_caption_render_worker.py`

**Success criteria:** Caption Animate renders can be started, monitored, canceled, and reused downstream as metadata-rich overlay assets.

### 5.3: Add audio-reactive caption support

Audio-reactive captions are the most distinctive Caption Animate feature in Stage Three and need both a shared analysis bundle and render-pipeline support for passing reactive context into animations.

**Tasks:**
- Add audio-source selection to the caption tab, using either a directly chosen file or a `SessionContext` asset role
- Build a shared audio-analysis bundle with smoothed amplitude, emphasis/peak markers, and optional chroma summaries using the existing audio-analysis stack. **Important:** `AudioData.analyze_audio()` is synchronous with per-frame librosa chroma computation and has no progress reporting infrastructure. Audio analysis must run on a background thread through the worker bridge to avoid UI freezes on long audio files, and should forward progress updates so the tab can show analysis status before the render begins.
- Reuse the `SessionContext` analysis cache so caption re-renders do not recompute audio analysis unnecessarily
- Extend the caption render pipeline so `event_context` or equivalent per-event reactive data reaches the animation layer. Note that `SubtitleFile.apply_animation()` currently does **not** pass `event_context` to animations — the render pipeline must be extended so audio-reactive analysis data flows through `apply_to_event()` and into `generate_ass_override(event_context)` for reactive animations to function.
- Ship a bounded preset family such as `pulse`, `beat_pop`, and `emphasis_glow` instead of a freeform animation graph
- Keep reactive motion bounded and readability-safe by default
- Create/update tests for audio-analysis reuse, reactive-preset mapping, and render-pipeline event-context flow
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/caption/core/subtitle.py`
- Modify `src/audio_visualizer/caption/animations/baseAnimation.py`
- Create `src/audio_visualizer/caption/core/audioReactive.py`
- Create `tests/test_caption_audio_reactive.py`

**Success criteria:** Caption Animate can render bounded audio-reactive caption presets using shared audio analysis, and the render pipeline now has a real path for per-event reactive context.

### 5.4: Phase 5 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify preset management, cancel behavior, and audio-reactive rendering all work from the same tab state and asset model

**Phase 5 Changelog:**
- Added a full-surface Caption Animate tab with built-in, file-based, and app-data preset workflows
- Implemented cancellable caption rendering around the FFmpeg process boundary
- Added shared-analysis-driven audio-reactive caption presets

---

## Phase 6: Build the Render Composition Tab

### 6.1: Finalize the composition asset contract and probing layer

Composition is where all cross-tab assumptions meet, so Stage Three must formalize the metadata contract for reusable assets before the composition UI and renderer are built on top of it.

**Tasks:**
- Define the `SessionAsset` metadata contract Composition requires: width, height, FPS, duration, alpha support, audio presence, source role, and compatibility flags, using the concrete rules from the "Cross-tab asset rules" section above
- Add media probing helpers for video, audio, image, and overlay assets so metadata is captured once and reused
- Decide and encode which intermediate caption/visualizer outputs are composition-ready versus requiring auto-transcode
- Explicitly classify caption-render outputs so `large` is the preferred alpha-ready overlay, `small` requires normalization before trusted reuse, and `medium` is treated as opaque unless normalized or re-rendered
- Add compatibility checks for pixel format, alpha capability, duration mismatches, and embedded-audio behavior
- Encode the rule that Audio Visualizer embedded audio is ignored by default in Composition unless the user explicitly selects it as the authoritative audio source
- Store enough metadata for Composition to make choices without re-probing every source on every selection
- Create/update tests for media probing, compatibility checks, and asset-contract serialization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/mediaProbe.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Create `tests/test_media_probe.py`

**Success criteria:** `SessionContext` assets carry a clear composition contract, and Composition can tell which inputs are ready, which need transcoding, and how each asset should be treated.

### 6.2: Create the composition tab UI, model, and undoable layout editing

The Composition tab should follow the user-approved direction: numeric positioning plus preset layouts with preview, fixed slots with optional extras, and full undo/redo for layout changes.

**Tasks:**
- Create `RenderCompositionTab` with fixed slots for `background` and `audio_source` plus optional overlay layers for visualizer and caption assets
- Add numeric controls for position, size, z-order, start/end time, loop/trim/freeze behavior, and matte/key options
- The tab model should support exactly one authoritative audio source, one background source, and zero-to-many overlay layers. This keeps the UI aligned with the chosen v0.6.0 composition scope without introducing general-purpose multi-track audio mixing.
- Add a composition preview panel that shows the current layout/preset state without requiring a full export
- Implement save/load layout presets and connect them to the shared settings/persistence model
- Ship initial built-in layout presets such as full-screen background with centered visualizer, full-screen background with bottom captions, and picture-in-picture overlay arrangements so preset support is useful immediately
- Add `QUndoCommand` subclasses for move, resize, reorder, source change, add/remove, audio-source change, and apply-preset actions
- Initialize the Render Composition undo stack with a limit of 100 (lower limit than SRT Edit because composition operations are fewer but larger)
- Ensure the tab clears or preserves undo history appropriately when compositions are reset versus edited
- Create/update tests for layout model round-trip, preset application, undo/redo commands, and preview-state synchronization
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/__init__.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/presets.py`
- Create `tests/test_ui_render_composition_tab.py`
- Create or modify `tests/test_ui_undo.py`

**Success criteria:** Users can assemble a composition with numeric layout controls, preview it, save/load layout presets, and undo/redo every important layout change.

### 6.3: Implement the FFmpeg-based composition renderer and advanced matte controls

Render Composition should follow the chosen Stage Three direction defined in this plan: an FFmpeg `filter_complex`-based renderer with hybrid direct-render/auto-transcode handling, explicit timeline rules, and richer matte/key control than a simple threshold slider.

**Tasks:**
- Build a composition worker around FFmpeg `filter_complex` generation and subprocess lifecycle management
- Implement layer timeline rules with per-layer start/end times, looping, trimming, freeze-on-last-frame behavior, and final duration defined by the maximum enabled layer end time
- Add explicit audio-source selection and strip rules so embedded audio is only used intentionally. v0.6.0 should choose one audio source, not mix multiple sources together.
- Implement advanced matte controls including key mode, key target, similarity/threshold, softness/blend, cleanup, despill, invert, and debug/alpha-preview modes
- Add auto-transcode paths for incompatible intermediates and reuse direct-in-composition overlays when that produces cleaner output
- Support both composition paths for captions:
  - consume a previously rendered overlay asset from Caption Animate
  - directly render an SRT/ASS source during composition when the user intentionally chooses that path because it produces a cleaner graph
- Register final composition renders as `SessionAsset` entries and route completion through the shared notification/preview flow
- Create/update tests for filter-graph building, timeline math, matte-control serialization, cancel behavior, and final asset registration
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workers/compositionWorker.py`
- Create `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_composition_filter_graph.py`
- Create or modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** Composition can export a final render through FFmpeg with explicit audio/timeline behavior, advanced matte controls, cancel support, and metadata-rich output registration.

### 6.4: Phase 6 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify asset probing, layout editing, and final composition rendering all follow the same contract and timeline rules

**Phase 6 Changelog:**
- Finalized the cross-tab asset contract and media probing layer
- Added a preset-driven Composition tab with numeric layout editing and undo/redo
- Implemented FFmpeg-based composition rendering with advanced matte controls and explicit timeline/audio rules

---

## Phase 7: Workflow Recipes and Cross-Tab Integration Polish

### 7.1: Add workflow recipes as a separate versioned artifact

Recipes are reusable workflow templates, not project saves, so they need their own schema, storage, and import/export flow.

**Tasks:**
- Create a versioned recipe schema that stores enabled stages, per-tab settings subsets, asset-role expectations, output naming rules, and references to presets/layouts/lint profiles, using the concrete structure from the "Workflow recipe schema" section above
- Store the recipe library under the app config/data area rather than in the repo root
- Support recipe import/export as explicit `.avrecipe.json` files
- Add "save recipe" and "apply recipe" flows at the shell level and in relevant tabs
- Resolve asset roles through `SessionContext` first, then fall back to filesystem prompts when bindings are missing
- Keep recipes distinct from project save/load artifacts and auto-saved last-session settings
- Exclude transient UI state from recipes just as with normal settings saves: recipes should capture workflow intent, not the user's last zoom level, current playback position, or in-progress output temp paths
- Create/update tests for recipe round-trip, versioning, import/export, asset-role resolution, and missing-binding handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workflowRecipes.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify relevant tab files under `src/audio_visualizer/ui/tabs/`
- Create `tests/test_workflow_recipes.py`

**Success criteria:** Recipes can be saved, imported, exported, and applied as reusable workflow templates without being confused with project files or machine-local autosaves.

### 7.2: Finish cross-tab workflow and status UX

Once all five tabs exist, the shell and tabs need a final integration pass so the application feels like one coherent workflow rather than five separate tools sharing a window.

**Tasks:**
- Finish session-aware file pickers across all tabs so users can choose between current-session assets and raw filesystem paths consistently
- Add explicit handoff actions between tabs for common flows such as SRT Gen -> SRT Edit, SRT Edit -> Caption Animate, and Caption Animate/Audio Visualizer -> Composition
- Polish the shared status area, tab badges, busy-state messaging, and completion notifications now that all long-running job types exist
- Ensure the shared analysis cache invalidates correctly when source assets or relevant analysis settings change
- Review render-preview behavior across all render-producing tabs and keep `RenderDialog` invocation consistent
- Create/update integration tests for cross-tab handoff flows, busy-state behavior, and shared-status updates
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/jobStatusWidget.py`
- Modify relevant files under `src/audio_visualizer/ui/tabs/`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_integration.py`

**Success criteria:** Cross-tab asset handoff feels intentional, users retain visibility into background work from anywhere in the app, and the Stage Three workflow operates like a unified production pipeline.

### 7.3: Add end-to-end migration and integration coverage

Before final review, Stage Three needs test coverage for the new whole-app behaviors that do not fit inside any one tab's unit tests.

**Tasks:**
- Add integration tests for loading old Audio Visualizer-only settings into the new multi-tab schema
- Add end-to-end session-flow tests covering SRT Gen output registration, SRT Edit reuse, Caption Animate render registration, and Composition consumption
- Add workflow-recipe application tests that bind asset roles into a populated `SessionContext`
- Add regression coverage for shared undo-action rebinding, shared busy-state blocking, and completion notifications
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create or modify `tests/test_ui_integration.py`
- Create or modify `tests/test_ui_settings_schema.py`
- Create or modify `tests/test_workflow_recipes.py`

**Success criteria:** The repo has automated coverage for the Stage Three migration path and the most important cross-tab workflows, not just isolated tab widgets.

### 7.4: Phase 7 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify recipes remain separate from project saves and that cross-tab workflows use `SessionContext` consistently

**Phase 7 Changelog:**
- Added versioned workflow recipes with import/export and asset-role resolution
- Polished cross-tab workflow, status, and handoff UX
- Added end-to-end migration and integration coverage for the multi-tab app

---

## Phase 8: User Debug - 1

### Reported Changes to Make

Every item in this section is in scope for Phase 8 and must map to one of the implementation subphases below. Each item should end with either automated regression coverage or an explicit manual verification note when the behaviour is difficult to exercise in tests.

- General
  - The backwards compatibility shim for old last settings can be removed and only support for loading
    current settings retained.
  - The global rendering progress bar once finished remains on the bottom instead of disappearing.
  - Global render progress bar should calculate percentage including audio muxing.
- Audio Visualizer Screen
  - The "Welcome to the Audio Visualizer!" header on the audio visualizer screen should be removed,
    and then the panel align to the top of the screen with remaining space on bottom blank
  - The OutputVideo File Path should automatically add ".mp4" to file path if no extension is given
  - Render video/Live Preview Render have duplicate render information in a side panel now that we have a master
    render progress bar on the bottom. The Audio Visualizer render progress panel should be removed and the live
    preview controls moved to its place.
- SRT Gen Screen
  - Input Files should be just as large as needed, and not default to a large space.
  - Start Transcription should be Generate SRTs
  - Transcription should show a scrolling panel with event statuses
  - Once model is loaded either from load button or Transcription it should stay loaded and the Model
    panel should indicate such. When the model is loaded, the Model "Load Model" button should
    change to "Unload Model"
  - The model list should not show "large-v3" but "large", it should also include "turbo"
  - Transcribe hangs without any error or ability to cancel. It does not appear to load the model.
- SRT Edit
  - Speaker column should be much smaller and text column much larger.
  - User should be able to click on the waveform graph to focus, and then press space to start/pause.
  - Double clicking on a row turn the row bright yellow in darkmode making the text unreadable and
    also this happens for no apparent reason.
  - Text in row should not be abridged with `...`
  - When user hovers over graph start/step boundary they should be able to drag and move that particular
    boundary line
  - When zoomed in on graph so the whole wave form cannot be seen a scroll bar should appear beneath the graph
  - When moused over the graph ctrl+scroll wheel should scroll left and right on the graph
  - When text is double clicked there is an unneeded text shadow produced
  - There is no way to break lines when editing text to spread text over two lines
- Caption Animate Screen
  - Render does not use the global render progress
  - Render does not use the proper font styles and settings even though the Style Preview panel is correct
  - Caption Animate package needs to be updated to produce mp4 instead of mov
  - Add option to mux audio with caption like in Audio Visualizer
- Render Composition
  - Can't load background
  - No live preview
  - Bring the overall implementation back in line with the Phase 6 contract, especially fixed background/audio controls, preview support, and correct asset registration

### Phase 8 Planning Notes

- Preserve Stage Three contracts unless this phase explicitly replaces them. In particular, completed renders still need follow-up actions such as `Preview`, `Open Output`, and `Open Folder`; if the current bottom status area should no longer remain expanded after completion, replace it with a compact dismissible completion state rather than silently removing those actions.
- Removing legacy settings migration means unversioned pre-Stage-Three settings should no longer be reshaped into the current schema. The replacement behaviour for this phase is fixed: log a warning, ignore the legacy payload, and fall back to a clean current schema rather than partially loading stale data.
- The caption-export request is resolved for this phase as a two-artifact contract when transparency is needed: the user-facing export becomes a delivery `.mp4`, while Composition keeps consuming a separately registered alpha-capable intermediate overlay artifact if the workflow needs transparency.
- Render Composition background loading and live preview must work for both raw filesystem picks and `SessionContext` assets.
- SRT Edit graph navigation is fixed for this phase: normal wheel behaviour remains zoom-focused, `Ctrl+wheel` performs horizontal panning, the horizontal scrollbar mirrors the current visible waveform range, and viewport-preservation rules should avoid jumpy repositioning during zoom/pan updates.
- For complex pointer/Qt behaviours that are difficult to assert fully in unit tests, add a short manual verification checklist to the phase work in addition to targeted automated coverage.

### Phase 8 Resolved Findings

- Legacy settings compatibility is currently implemented inside `settingsSchema.migrate_settings()`. Phase 8 should delete the unversioned legacy migration path rather than keep reshaping old `general`/`visualizer`/`specific`/`ui` payloads.
- The completed global job UI currently stays visible because `JobStatusWidget.show_completed()` leaves the progress area expanded at 100%. The required implementation is a compact dismissible completion state that keeps completion actions without leaving the active progress row pinned open.
- Global render percentage currently stops measuring after frame encoding and treats audio muxing as an unmeasured tail step. Phase 8 should convert this to stage-aware progress accounting so encode and mux both contribute to the final percentage.
- SRT Gen currently mixes an ad hoc `_ModelLoader` path with synchronous model loading inside `SrtGenWorker.run()`, and the tab does not surface bridge events in a scrolling log. Phase 8 should unify explicit load and auto-load around shared model state and worker-bridge event reporting.
- SRT Edit currently hardcodes a bright yellow dirty-row highlight, lacks waveform focus/key handling, lacks boundary dragging, and has no horizontal scrollbar. Phase 8 should replace those defaults with palette-safe table styling plus a coherent waveform interaction model.
- Caption Animate preview styling already builds a `PresetConfig`, but the render worker/API path ignores `preset_override`. Phase 8 should pass the resolved preset through the entire render stack so preview and final output use the same styling data.
- Render Composition background loading breaks down when a direct file path is stored on the layer because the source combo falls back to `(none)` instead of surfacing the chosen file. Phase 8 should make direct file-backed layers visible in the UI and use that same source data for preview and final render paths.

### 8.1: General and Audio Visualizer Screen Fixes

Address global UX regressions and Audio Visualizer tab issues reported after Stage Three integration.

**Tasks:**
- Remove the backwards-compatibility shim for old pre-Stage-Three settings format (`general`, `visualizer`, `specific`, `ui`) and retain only current v1 schema loading
- When legacy settings files are encountered after the shim removal, log a clear warning, reject the payload, and fall back to a clean current schema instead of silently migrating legacy keys
- Rework the completed-job state in `JobStatusWidget` so active render progress no longer remains pinned at the bottom after completion while preserving explicit completion actions (`Preview`, `Open Output`, `Open Folder`) through a compact dismissible success state
- Update the global progress percentage calculation to include the audio muxing stage so the bar reaches 100% only after muxing finishes; this should use stage-aware progress accounting rather than treating muxing as an unmeasured tail step
- Remove the "Welcome to the Audio Visualizer!" header from `AudioVisualizerTab` and align the settings panel to the top of the screen with remaining space left blank below
- Add automatic `.mp4` extension to the output video file path when the user provides a path with no extension, including the explicit save/browse flow and the direct typed-path validation path
- Remove the duplicate Audio Visualizer render progress side panel (now redundant with the global `JobStatusWidget`) and move the live preview controls into its place without regressing existing live-preview refresh behaviour
- Create/update tests for legacy settings rejection, progress bar lifecycle, mux-inclusive progress calculation, output path extension handling, and layout changes
- Add a brief manual verification pass for the completed-job UI and Audio Visualizer layout changes
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/jobStatusWidget.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/tabs/audioVisualizerTab.py`
- Modify `src/audio_visualizer/ui/workers/workerBridge.py`
- Modify relevant worker files under `src/audio_visualizer/ui/workers/`
- Modify relevant test files

**Success criteria:** Old settings shim is removed without breaking current schema loads, legacy settings are clearly rejected instead of silently migrated, the active global progress UI no longer lingers after completion while completion actions remain available, muxing contributes to progress accounting, the Audio Visualizer tab has no welcome header or duplicate progress panel, and output paths automatically gain `.mp4` when no extension is provided.

### 8.2: SRT Gen Screen Fixes

Fix SRT Gen tab UI sizing, labelling, model lifecycle, and the transcription hang.

**Tasks:**
- Resize the Input Files panel so it only takes as much vertical space as needed instead of defaulting to a large fixed area
- Rename the "Start Transcription" button to "Generate SRTs"
- Replace the current transcription output display with a scrolling panel that shows streaming event statuses as they arrive from the worker; keep a concise summary status label in addition to the scrollable event history
- Track model-loaded state across the tab lifecycle: once a model is loaded (via the Load button or implicitly during transcription), the Model panel should indicate the model is loaded, the "Load Model" button should change to "Unload Model", and the loaded-model label should reflect the actual loaded name/device
- Update the model list display names so `large-v3` appears as `large`, and add `turbo` to the available model list while preserving the correct underlying model identifier mapping used by the transcription API
- Replace the ad hoc `_ModelLoader` path with a shared `ModelManager`-backed load/unload flow that is used by both the explicit Model-panel button and Generate-SRT auto-load
- Surface model-load attempts, fallback/errors, and stage transitions through the worker bridge and keep the scrolling event log subscribed to those events so a stalled start-up path is visible to the user
- Make cancellation effective during startup by checking cancel state before long transcription work begins, returning the UI to a consistent unloaded/idle state on load failure or cancel, and preventing the tab from claiming a model is loaded when acquisition did not succeed
- Use one shared loaded-model state source for explicit load, unload, and transcription auto-load so the UI cannot claim one model is loaded while the worker uses another
- Create/update tests for model lifecycle state, button label toggling, model list display names, event log scrolling, and worker cancellation/error propagation
- Add a brief manual verification pass covering model load, unload, auto-load via Generate SRTs, and cancel during a stalled transcription attempt
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/workers/srtGenWorker.py`
- Modify `src/audio_visualizer/ui/workers/workerBridge.py`
- Modify `src/audio_visualizer/srt/modelManager.py`
- Modify `src/audio_visualizer/srt/modelManagement.py`
- Modify relevant test files

**Success criteria:** Input Files panel is compact, the button reads "Generate SRTs", event statuses scroll in real time, model load state persists and the button label reflects it, the model list shows `large` and includes `turbo`, and transcription no longer hangs silently or without a working cancel/error path.

### 8.3: SRT Edit Screen Fixes

Fix SRT Edit table layout, waveform interaction, editing behaviour, and graph navigation.

**Tasks:**
- Adjust table column proportions so the Speaker column is much narrower and the Text column takes the majority of available width
- Allow the user to click the waveform graph to give it keyboard focus, then press Space to toggle playback start/pause
- Replace the hardcoded bright-yellow dirty/edit highlight with palette-safe selection and dirty-state styling so double-clicking a row does not make text unreadable in dark mode
- Prevent text in rows from being abridged with `...` by enabling wrapping/non-elided display for the text column and allowing row heights to grow with content
- Add drag-to-move behaviour on subtitle boundary lines in the waveform graph: when the user hovers over a start or end boundary, the cursor should change and they should be able to drag the boundary to adjust timing
- Add a horizontal scrollbar beneath the waveform graph when zoomed in so the full waveform cannot be seen
- Keep normal wheel-driven zoom behaviour, add `Ctrl+scroll wheel` horizontal panning, and tie the scrollbar position to the same visible-range state so zoom, pan, and scrollbar movement stay synchronized without viewport jumps
- Replace the current inline text editor with a multiline editor configuration that removes the unwanted text-shadow artifact and supports line breaks during editing (for example `Shift+Enter` newline with normal commit still preserved)
- Create/update tests for column sizing, keyboard playback toggle, boundary drag behaviour, scroll/zoom interaction, selection/edit styling, and multiline text editing
- Add a brief manual verification pass for waveform hover/drag interactions and multiline text editing
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/document.py`
- Modify relevant test files

**Success criteria:** The subtitle table has a narrow Speaker column and wide Text column with no ellipsis truncation, Space toggles playback after clicking the waveform, row selection uses readable dark-mode colours, boundary lines are draggable, the graph has a horizontal scrollbar and Ctrl+scroll panning when zoomed, text editing has no shadow artifact, and multiline editing supports line breaks without breaking normal commit behaviour.

### 8.4: Caption Animate and Render Composition Fixes

Fix Caption Animate render integration and output format, and address Render Composition blocking issues.

**Tasks:**
- Wire Caption Animate rendering into the global `JobStatusWidget` progress bar so it reports progress like other tabs
- Pass the resolved style-preview configuration through `CaptionRenderJobSpec.preset_override`, `captionApi.render_subtitle()`, and the FFmpeg render path so Caption Animate output uses the same font/style settings shown in the Style Preview panel
- Implement the caption export contract as a user-facing `.mp4` delivery render, plus a separately registered alpha-capable intermediate overlay artifact when Composition needs transparency; update `SessionContext` asset registration and downstream tab consumption accordingly
- Add an explicit caption-audio mux option that mirrors the Audio Visualizer mux flow and clearly binds the chosen audio source to the delivery `.mp4`
- Fix Render Composition background loading by surfacing direct file-backed `asset_path` selections in the UI instead of resetting the source control to `(none)`, and ensure both direct-file sources and session assets resolve through validation, filter-graph generation, and render execution
- Add a still-frame live preview panel to Render Composition with a timestamp/refresh workflow that reuses composition graph generation without requiring a full export, and make it work for both direct-file and session-backed layers
- Bring Render Composition back in line with the Phase 6 contract by making background and audio-source controls explicit, preserving layer timing/matte behaviour, and ensuring output registration remains consistent with the rest of Stage Three
- Create/update tests for caption render progress integration, shared style resolution, mp4 output contract, audio mux option, background loading, and composition preview
- Add a brief manual verification pass for caption style parity and composition background/preview flows
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- Modify `src/audio_visualizer/ui/workers/workerBridge.py`
- Modify `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- Modify `src/audio_visualizer/caption/captionApi.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- Modify `src/audio_visualizer/ui/workers/compositionWorker.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify relevant test files

**Success criteria:** Caption Animate renders report progress through the global status bar, rendered output matches the style preview, the `.mp4` delivery/output contract is explicit and Composition still consumes the correct asset type, audio muxing is available, Render Composition can load backgrounds from both supported source types, live preview works under the agreed preview model, and the overall composition implementation is verified against plan contracts.

### 8.5: Phase 8 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify the user-debug fixes did not weaken existing Stage Three guarantees, especially cross-tab integration and shared-worker behavior

**Phase 8 Changelog:**
- Added a dedicated user-debug phase for triage, targeted fixes, and regression verification
- Captured post-implementation debugging work as a first-class phase between integration polish and final review
- Reserved a clear plan slot for real-user issue follow-up before release review work
- Organized reported changes into four implementation subphases: General/Audio Visualizer (8.1), SRT Gen (8.2), SRT Edit (8.3), Caption Animate/Render Composition (8.4)
- Added explicit decision notes and validation requirements for the ambiguous user-reported items, especially legacy settings removal, completed-job UI, and caption mp4 output behaviour
- Converted remaining discovery-style implementation bullets into repo-backed concrete tasks so Phase 8 can be executed without another diagnose/review pass

---

## Phase 9: User Debug - 2

### Reported Changes to Make

Every item in this section is in scope for Phase 9 and must map to one of the implementation subphases below. Each item should end with automated regression coverage or an explicit manual verification note when the behavior is difficult to exercise in tests.

- General
  - Startup is slowing down, so review the startup path and lazy-load intelligently.
  - The app should have a settings popup. The current settings to add are dark mode on/off/auto.
  - Global render status bar on finished render:
    - The "Cancel" button should turn into a field that says "Finished".
    - It should fade away after 5 seconds.
  - The user should be able to set a project folder and files should default to input/output relative to there unless otherwise specified.
- Audio Visualizer Screen
  - Clicking on color swatches should open the color dialog.
  - Chroma gradients should follow tabs like the chroma lines view.
- Assets Screen
  - Create an Assets screen which shows the session assets, other assets, and any asset folders the user has loaded.
- SRT Gen Screen
  - Error trying to generate SRTs when the model was preloaded:
  ```
  [Stage 0/5] Loading model
  [Stage 1/5] Transcribing Short 1.mp3 (1/4)
  [INFO] Input: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\Short 1.mp3
  [INFO] Output: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\New folder\Short 1.srt
  [Stage 1/4] Converting audio
  [Stage 2/4] Transcribing
  [ERROR] Library cublas64_12.dll is not found or cannot be loaded
  FAILED: Library cublas64_12.dll is not found or cannot be loaded
  FAILED: Library cublas64_12.dll is not found or cannot be loaded
  [ERROR] Library cublas64_12.dll is not found or cannot be loaded
  FAILED: Library cublas64_12.dll is not found or cannot be loaded
  Completed 1/4
  ```
  and the SRT Gen path crashes afterwards.
  - When the model is not preloaded the model appears to load looking at GPU memory usage, but then hangs with this log:
  ```
  Starting transcription with model 'large' (large-v3)
  Processing 4 file(s)...
  ```
  pressing cancel does not help.
- SRT Edit Screen
  - Ctrl-scroll does not scroll side to side but still zooms in.
  - Clicking on text in a row and adding an Enter does not resize the text box to show both lines.
  - Editing text and then clicking undo does not undo the text change.
- Caption Animate
  - Should have a preview panel and preview render like Audio Visualizer.
  - Error from this tab while loading:
  ```
  qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version 7.1.2 LGPL version 2.1 or later
  Input #0, mp3, from 'C:/Users/TimEckII/OneDrive - Personal Use/Documents/Podcast/Homilies/2026/3-15-26 Lt 4/Short 1.mp3':
    Duration: 00:00:34.43, start: 0.025057, bitrate: 128 kb/s
    Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 128 kb/s
        Metadata:
          encoder         : LAME3.99r
  Traceback (most recent call last):
    File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\captionAnimateTab.py", line 873, in _on_animation_type_changed
      spin.setValue(float(default_val))
                    ~~~~~^^^^^^^^^^^^^
  ValueError: could not convert string to float: 'even'
  ```
  - Error rendering video:
  ```
  Traceback (most recent call last):
  File "C:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\src\audio_visualizer\ui\tabs\captionAnimateTab.py", line 1018, in _start_render
    if not self._main_window.try_start_job(self.tab_id):
           ^^^^^^^^^^^^^^^^^
  AttributeError: 'CaptionAnimateTab' object has no attribute '_main_window'
  ```
- Render Composition
  - Output Settings should have a standard resolutions dropdown: HD, HD Vertical, 2K, 4K. This should set width/height, and the user can manually set width/height if needed.
  - Audio source should be treated like layers, meaning the user can load multiple audio sources and have them start at particular times, and play for a certain amount of time, or play for their whole length.
  - Explore how hard it would be to create a basic timeline for positioning visual and audio assets for composition.
    - | Loaded Assets           | Live    |
      |-------------------------|         |
      | Selected Layer Settings | Preview |
      |-----------------------------------|
      | Timeline with drag drop           |
      |-----------------------------------|
      | Render Settings with Render button|
    - There will be similarity in this code with the Edit SRT screen.

### Phase 9 Planning Notes

- Preserve Phase 8 behavior unless this phase explicitly replaces it. In particular, the global `JobStatusWidget` must keep non-blocking follow-up actions (`Preview`, `Open Output`, `Open Folder`) while adding the new terminal-state fade behavior.
- Phase 9 intentionally extends the Stage Three shell from five tabs to six by appending a non-workflow `Assets` screen after `Render Composition`. This means autosave/project schema support must grow to tolerate `tabs.assets`, but the workflow recipe stage model does not need to treat `assets` as a recipe stage.
- Theme choice is app-level state and should live under a new top-level `app` section in the versioned settings schema. The project-folder setting is session-level state and should travel with project/autosave data via `SessionContext`, not as a global machine-only preference.
- Default browse/output directory handling is currently fragmented across `sessionFilePicker.py` and many direct `QFileDialog` call sites. Phase 9 must centralize that logic so the project-folder rule is actually enforced everywhere instead of only in one helper.
- The current Caption Animate "Style Preview" is not the requested render preview. Phase 9 must keep style preview and add a real media preview workflow for the rendered overlay.
- The SRT Gen GPU issue is not just a missing DLL error surface; the current model lifecycle crosses threads in a way the original Local SRT integration did not. The fix must eliminate the bad load/use threading pattern and keep cancel/error propagation intact.
- Startup performance work must address both eager heavy imports and eager tab construction in `MainWindow`; lazy imports alone are not enough if all heavy tabs are still instantiated during startup.
- The Render Composition timeline item is implementation scope for Phase 9, not just discovery. The final subphase must deliver a usable drag/drop timeline tied to the actual composition model.

### Phase 9 Resolved Findings

- `CaptionAnimateTab._build_preview_section()` currently builds only a styled `QLabel` called "Style Preview". There is no rendered overlay preview panel yet.
- `CaptionAnimateTab` owns its own private `QThreadPool` and still makes several bare `_main_window` calls, so the current render path can bypass the shared job-pool contract and crash when the parent is not wired as expected.
- `SessionContext` currently manages assets and analysis cache only. It has no concept of `project_folder`, no signal for that setting, and no helper for importing arbitrary external file/folder assets.
- `SessionFilePickerDialog` and multiple tab browse handlers currently pass `""` as the default directory to `QFileDialog`, so they cannot honor any project-root preference without a shared helper.
- `MainWindow._register_all_tabs()` imports and instantiates every tab during startup. Combined with top-level imports in `srtGenTab.py` and `captionAnimateTab.py`, this defeats most lazy-loading benefits.
- `settingsSchema.create_default_schema()` currently has no top-level `app` section and `_TAB_KEYS` still only includes the original five tabs.
- `workflowRecipes.py` hardcodes the workflow-stage keys and should stay that way; the new Assets tab should be treated as a support screen, not a new workflow recipe stage.
- `ForceCircleChromaVisualizerView` and `ForceRectangleChromaVisualizerView` still use a single pipe-delimited `QLineEdit` for per-band colors, while `ForceLinesChromaVisualizerView` already has the tabbed per-band UI the user wants.
- Visualizer swatches across `generalVisualizerView.py` and the chroma force views are still passive `QLabel` color boxes, so clicking them does nothing.
- `SubtitleTableModel.setData()` directly mutates the document for text/timestamp/speaker edits, which bypasses the undo stack for inline edits.
- `RenderCompositionTab` still models one audio source via `_audio_combo` plus `CompositionModel.audio_source_asset_id/audio_source_path`, so it cannot satisfy the requested layered-audio workflow without a model/schema rewrite.
- `JobStatusWidget` still uses a "Dismiss" button in terminal states and has no owned timer for timed auto-reset.

---

### 9.1: Caption Animate Crash Fixes and Shared-Job Compliance

Fix the two reported Caption Animate runtime crashes and bring the tab back into compliance with the shared job/status contract before adding new preview functionality.

**Tasks:**
- Replace the current `_anim_param_spins: dict[str, QDoubleSpinBox]` approach with a mixed-type parameter-control registry that can hold numeric, string, and nullable defaults. Numeric defaults should use `QDoubleSpinBox`; string defaults should use `QLineEdit`; `None` defaults should render as an empty `QLineEdit` and round-trip back to `None`.
- Update `_on_animation_type_changed()`, `_collect_preset_config()`, preset-apply logic, and `apply_settings()` so animation defaults and persisted values round-trip correctly for mixed parameter types such as `word_reveal.mode = "even"` and `unrevealed_color = None`.
- Remove the tab-local `self._thread_pool` and use `self._main_window.render_thread_pool` for full renders so Caption Animate behaves like the other heavy-job tabs.
- Guard all `MainWindow` integration points with the same defensive pattern already used in `SrtGenTab`, including `try_start_job`, `show_job_status`, `update_job_progress`, `update_job_status`, `show_job_completed`, `show_job_failed`, and `show_job_canceled`.
- Ensure early validation failures, worker-construction failures, and render-cancel paths all restore button state cleanly and do not leave the shared job slot stuck busy.
- Create/update automated coverage for mixed animation parameter widgets, settings round-trip for mixed types, guarded render lifecycle behavior, and shared-pool usage.
- Add a short manual verification pass covering: selecting `word_reveal`, switching between multiple animation types, starting a render, and canceling a render.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/workers/captionRenderWorker.py` only if worker metadata/signals need minor alignment for the guarded lifecycle
- Modify `tests/test_ui_caption_tab.py`
- Modify `tests/test_caption_render_worker.py` if worker-level coverage is needed

**Success criteria:** Caption Animate no longer crashes when an animation exposes string or nullable defaults, full renders use the shared user-job pool, all global job-status calls are safe when the main window is absent or partially initialized, and cancel/failure paths restore the tab to a usable state.

### 9.2: SRT Edit Bug Fixes and Undo Scoping

Fix the three reported SRT Edit regressions and harden undo/redo routing so inline edits always stay tab-scoped.

**Tasks:**
- Fix Ctrl+wheel horizontal panning by installing an event filter on the pyqtgraph view that actually receives the wheel event (`PlotWidget` viewport). When Ctrl is held, convert wheel delta into horizontal pan, accept the event, and skip pyqtgraph's zoom handling; otherwise preserve current zoom behavior.
- Keep the waveform horizontal scrollbar and visible-range state synchronized with the new Ctrl+wheel handling so wheel-panning, scrollbar movement, and zoom all operate on the same viewport model.
- Fix row growth after newline edits by listening for `SubtitleTableModel.dataChanged` in `SrtEditTab` and calling `resizeRowToContents(row)` for affected rows when the text column changes.
- Stop `SubtitleTableModel.setData()` from mutating the document directly for inline editable fields. Instead, have the model validate/parse the requested change and emit a structured edit-request signal back to `SrtEditTab`.
- In `SrtEditTab`, convert inline edit requests into undoable commands. Timestamp edits should use `EditTimestampCommand`; text edits should use `EditTextCommand`; speaker edits should either gain a new `EditSpeakerCommand` or move to a shared field-edit command so all inline document mutations remain undoable.
- Add local Ctrl+Z / Ctrl+Y shortcuts to `RenderCompositionTab` using `QShortcut` so keyboard undo/redo remains available when that tab has focus, matching the existing `SrtEditTab` behavior.
- Audit all tab-switch paths (`sidebar` selection, `handoff_to_tab`, settings restore, and any lazy-tab creation path introduced in Phase 9.7) to ensure `MainWindow._update_undo_actions()` always rebinds correctly and tabs without undo support leave Edit > Undo/Redo disabled.
- Create/update automated coverage for wheel interception, row auto-resize after multiline edits, inline-edit undo routing, and undo isolation across tab switches.
- Add a short manual verification pass covering Ctrl+wheel panning, multiline text entry, undo/redo after inline table edits, and switching between SRT Edit and Render Composition while using Ctrl+Z / Ctrl+Y.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `tests/test_ui_srt_edit_tab.py`
- Modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** Ctrl+wheel pans horizontally instead of zooming, multiline text edits immediately resize their rows to show all lines, inline text/timestamp/speaker edits are undoable through the tab-local undo stack, and Ctrl+Z / Ctrl+Y never leak across tabs.

### 9.3: SRT Gen GPU Regression and Hang Fix

Fix the `cublas64_12.dll` regression, the follow-on crash after a failed file, and the non-preloaded model hang/cancel failure by replacing the current broken model lifecycle with a thread-safe, single-owner pattern.

**Tasks:**
- Compare the integrated SRT Gen model lifecycle against the original working code in `Projects to integrate/Local SRT/` and capture the exact load/use assumptions that must be preserved in the GUI path.
- Replace the current split `_ModelLoadWorker` plus `SrtGenWorker` ownership model with a single thread-owning lifecycle for the actual Whisper model instance. The concrete rule for Phase 9 is: the thread that loads the model must also be the thread that uses it for transcription. Do not reuse a GPU-backed model object across unrelated thread-pool workers.
- Keep explicit "Load Model" / "Unload Model" UX, but treat the tab's loaded-model state as metadata backed by that dedicated owner thread instead of a model object shared across arbitrary workers.
- Ensure one shared `AppEventEmitter` instance is used consistently for model load, batch transcription, and error reporting so the scrolling event log and the global job-status UI describe the same lifecycle.
- Fix `compute_type_used` fallback handling in `srtGenWorker.py`; do not emit `"default"` to downstream transcription paths. Use the actual resolved compute type when known, otherwise fall back to a valid value such as `"int8"`.
- Make cancel responsive during model loading by moving blocking load work behind a cancel-aware polling loop. The implementation can use a daemon helper thread or another equivalent structure, but the UI-facing worker must check cancel state while the model load is in progress and emit a real canceled result instead of hanging until load completes.
- Harden post-failure behavior so a failed first file or failed load leaves the tab, model state, event log, and shared job status in a clean idle state instead of crashing the rest of the batch path.
- Keep the Load/Unload button text, loaded-model label, and batch auto-load path all driven from the same source of truth so the UI cannot claim a model is loaded when acquisition actually failed.
- Create/update automated coverage for compute-type propagation, emitter consistency, cancel-during-load behavior, failed-load cleanup, and the thread-owned model lifecycle contract.
- Add a manual verification pass covering three cases: preloaded GPU transcription, auto-load transcription without preload, and cancel during model load. Record the exact verification conditions in the phase implementation notes.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Reference files (original working code):**
- `Projects to integrate/Local SRT/src/local_srt/api.py`
- `Projects to integrate/Local SRT/src/local_srt/cli.py`
- `Projects to integrate/Local SRT/src/local_srt/whisper_wrapper.py`

**Files:**
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/workers/srtGenWorker.py`
- Modify `src/audio_visualizer/srt/modelManager.py`
- Modify `src/audio_visualizer/srt/core/whisperWrapper.py` if the thread-owned lifecycle requires a lower-level change
- Modify `tests/test_ui_srt_gen_tab.py`
- Modify `tests/test_srt_gen_worker.py`
- Modify `tests/test_srt_model_manager.py`

**Success criteria:** GPU transcription works again without the preload/use-thread regression, auto-load transcription progresses beyond "Processing N file(s)...", cancel works during model loading, and failures leave SRT Gen in a stable idle state instead of crashing the tab.

### 9.4: JobStatusWidget Terminal-State Polish

Polish the global job-status widget so finished work reads as finished, stays actionable briefly, and then clears itself automatically.

**Tasks:**
- Change the terminal-state button text from `"Dismiss"` to `"Finished"` for completed jobs.
- Add a widget-owned auto-reset timer (`QTimer`, not a fire-and-forget `singleShot`) so terminal states can be canceled/restarted safely when the user clicks manually or a new job begins.
- Start the 5-second auto-fade timer in all terminal states: completed, failed, and canceled.
- Preserve completion actions (`Preview`, `Open Output`, `Open Folder`) during the 5-second completed state when an output path exists.
- Ensure clicking `"Finished"` before the timer fires immediately resets the widget and stops the timer.
- Ensure starting a new job while a terminal-state timer is pending clears the old timer and restores the widget to the active-job state without stale button wiring.
- Create/update automated coverage for terminal-state button text, timer-driven reset, manual click canceling the timer, and timer reset when a new job starts.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/jobStatusWidget.py`
- Modify `tests/test_ui_job_status_widget.py`

**Success criteria:** Terminal states show `"Finished"` instead of `"Dismiss"`, completion actions remain usable during the brief finished state, and completed/failed/canceled job rows all clear automatically after 5 seconds unless the user clears them sooner.

### 9.5: Settings Dialog and Theme Mode

Add the missing Settings dialog and implement the dark-mode On/Off/Auto preference as app-level state.

**Tasks:**
- Extend the versioned settings schema with a new top-level `app` section that at minimum stores `theme_mode` with allowed values `off`, `on`, and `auto`.
- Create `SettingsDialog` as a `QDialog` with a theme section containing a three-option combo box for `Off`, `On`, and `Auto`.
- Add a `File > Settings...` action after the recipe actions in `MainWindow`.
- Implement theme application in a single helper so `MainWindow` can apply it during startup and after Settings changes. The helper should resolve `auto` using Qt color-scheme APIs when available and fall back to explicit dark/light `QPalette` setup when needed.
- Load the saved theme setting early enough that the initial window honors it before the user starts interacting with the app. With the lazy-tab work from Phase 9.7, theme application should happen before deferred tab creation so all later tabs inherit the same palette.
- Decide and document one interaction model for the dialog. For Phase 9 the dialog should use explicit accept/apply semantics: changing the combo alone should not silently persist settings until the user confirms.
- Create/update automated coverage for schema defaults, Settings dialog load/save behavior, theme helper resolution for On/Off/Auto, and MainWindow startup application of the saved theme.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/settingsDialog.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `tests/test_ui_settings_schema.py`
- Create or modify `tests/test_ui_settings_dialog.py`
- Modify `tests/test_ui_main_window.py`

**Success criteria:** The File menu contains a working Settings dialog, the dialog exposes dark-mode Off/On/Auto, the choice persists in the app settings schema, and the selected theme is applied on the next launch without waiting for a later tab interaction.

### 9.6: Project Folder and Default Path Resolution

Add project-folder support and make browse/output defaults actually honor it across the application.

**Tasks:**
- Add a `Project Folder` field plus browse button to `SettingsDialog`.
- Extend `SessionContext` with `project_folder: Path | None` and a `project_folder_changed` signal so tabs can use one shared session-level default directory.
- Persist `project_folder` through `SessionContext.to_dict()` / `from_dict()` so autosave and project save/load retain it with the rest of the current session.
- Create a shared directory-resolution helper used by both `SessionFilePickerDialog` and direct `QFileDialog` call sites. The precedence should be: an already-entered path's parent if valid, otherwise the relevant selected asset's parent if applicable, otherwise `SessionContext.project_folder`, otherwise a sane local fallback such as the user's home directory.
- Update the direct browse handlers in `srtGenTab.py`, `captionAnimateTab.py`, `srtEditTab.py`, `renderCompositionTab.py`, and any remaining UI browse/save helpers that currently pass `""` as the default directory so they all use the shared resolver.
- Update output-path derivation rules so tabs that auto-pick an output directory (`SRT Gen`, `Caption Animate`, `Render Composition`, and any equivalent save helpers) prefer the session project folder when no explicit output path was set by the user.
- Keep project-folder behavior additive rather than destructive: an explicitly chosen file path or output directory always wins over the project-folder default.
- Create/update automated coverage for `SessionContext` project-folder persistence, dialog start-directory resolution, and output-directory fallback logic across the affected tabs.
- Add a short manual verification pass covering browse defaults and output-default behavior before and after changing the project folder.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/settingsDialog.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/sessionFilePicker.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/views/general/generalSettingViews.py` (has its own `QFileDialog` instances for audio/video file selection)
- Modify `tests/test_ui_session_context.py`
- Modify `tests/test_ui_srt_gen_tab.py`
- Modify `tests/test_ui_caption_tab.py`
- Modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** The user can set a project folder in Settings, project/autosave persistence retains it, browse dialogs open there by default when no stronger context exists, and automatically derived output paths use that folder unless the user explicitly chose something else.

### 9.7: Startup Performance and Lazy Tab Initialization

Reduce startup cost by deferring heavy tab imports and heavy tab construction instead of front-loading the entire Stage Three UI stack.

**Tasks:**
- Add startup timing instrumentation around `MainWindow` construction, shell build, settings load, and first tab show so the phase produces before/after evidence in logs instead of relying on subjective feel alone.
- Replace the current eager `_register_all_tabs()` pattern with a lazy tab registry/factory model. The sidebar entries should exist immediately, but only the default `Audio Visualizer` tab must be instantiated during startup; the other heavy tabs should be created on first activation or the first time another code path genuinely needs them.
- Ensure lazy tab creation still supports `SessionContext` injection, sidebar busy states, tab handoff helpers, and menu-bound undo/redo behavior.
- Preserve autosave/project-load correctness with lazy tabs by keeping unapplied per-tab settings available until the tab is instantiated, then applying those settings once the tab exists.
- Audit and defer heavy imports in `captionAnimateTab.py`, `srtGenTab.py`, and any newly added Assets/Timeline modules so importing the main window no longer drags in `faster-whisper`, caption preset machinery, or other expensive modules before the user opens those screens.
- Keep `caption.__getattr__` and `srt.__getattr__` lazy-loading effective; do not reintroduce eager imports that bypass those package boundaries.
- Ensure Settings/theme application still happens before lazy heavy tabs are instantiated so their widgets inherit the correct palette.
- Create/update automated coverage for lazy tab instantiation, delayed settings application, and proof that heavy modules are not imported during startup until the user activates the relevant tab.
- Add a short manual verification pass covering cold startup to the Audio Visualizer tab and first-open behavior for SRT Gen / Caption Animate.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py` if pending-tab application needs schema-awareness changes
- Modify `tests/test_ui_main_window.py`
- Modify any other relevant UI tests that assume eager tab construction

**Success criteria:** Cold startup only constructs the shell plus the default Audio Visualizer screen, later tabs are created lazily without breaking settings restore or tab handoff behavior, and heavy caption/SRT imports stay unloaded until those screens are first used.

### 9.8: Audio Visualizer Clickable Color Swatches

Make visualizer swatches behave like controls instead of passive indicators.

**Tasks:**
- Create a reusable clickable swatch widget or helper that exposes a click signal and can be bound to an existing `QColorDialog` / `QLineEdit` pair.
- Replace passive swatch `QLabel`s in all visualizer views that use them: `generalVisualizerView.py`, `forceCircleChromaVisualizerView.py`, `forceRectangleChromaVisualizerView.py`, `forceLinesChromaVisualizerView.py`, `circleChromaVisualizerView.py`, `rectangleChromaVisualizerView.py`, `lineChromaVisualizerView.py`, and `lineChromaBandsVisualizerView.py`.
- Wire swatch clicks to the same color dialog already used by the adjacent `Select Color` button so clicking the swatch and clicking the button always produce the same result.
- Preserve current text-field-driven swatch refresh logic so manual RGB edits still update the swatch and invalid color text still clears it safely.
- Create/update automated coverage for swatch-click activation and swatch/text synchronization.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/widgets/clickableColorSwatch.py` or another shared helper module if that better fits the repo
- Modify `src/audio_visualizer/ui/views/general/generalVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/forceCircleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/forceRectangleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/forceLinesChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/circleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/rectangleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/lineChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/lineChromaBandsVisualizerView.py`
- Modify `tests/test_ui_audio_visualizer_tab.py` or add a focused visualizer-view test module

**Success criteria:** Clicking any visible color swatch opens the associated color picker and updates the underlying field exactly as if the user had pressed the adjacent `Select Color` button.

### 9.9: Audio Visualizer Tabbed Per-Band Chroma Controls

Bring the force circle and force rectangle chroma views into line with the tabbed per-band color workflow already used by force chroma lines.

**Tasks:**
- Replace the single pipe-delimited `band_colors` `QLineEdit` in `ForceCircleChromaVisualizerView` with a `QTabWidget` containing two tabs (`Bands 1-6` and `Bands 7-12`), each with six per-band rows matching the `ForceLinesChromaVisualizerView` interaction pattern.
- Apply the same refactor to `ForceRectangleChromaVisualizerView`.
- Apply the same refactor to the non-force variants that also use the flat pipe-delimited field: `CircleChromaVisualizerView`, `RectangleChromaVisualizerView`, and `LineChromaVisualizerView`.
- Reuse the new clickable swatch helper from Phase 9.8 so per-band rows have consistent button/swatch behavior across all chroma force views.
- Keep `color_mode` behavior explicit: gradient mode continues using the start/end controls, while per-band mode uses the tabbed per-band UI. Remove the legacy pipe-delimited field instead of keeping both UIs alive in parallel.
- Update validation and settings-read logic so both views still return `band_colors` as a list of 12 RGB tuples and reject incomplete/invalid per-band configurations cleanly.
- Update any save/load or view-restore logic that still assumes the old single-string per-band control.
- Create/update automated coverage for validation, settings round-trip, and per-band UI structure in both views.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/views/chroma/forceCircleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/forceRectangleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/circleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/rectangleChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/lineChromaVisualizerView.py`
- Modify `src/audio_visualizer/ui/views/chroma/forceLinesChromaVisualizerView.py` only if shared helpers should be extracted
- Modify `src/audio_visualizer/ui/widgets/clickableColorSwatch.py` if the helper needs shared band-row support
- Modify `tests/test_ui_audio_visualizer_tab.py` or add a focused visualizer-view test module

**Success criteria:** All chroma visualizer views that expose per-band colors present them in the same tabbed six-at-a-time layout as the force chroma lines view, with clean validation and settings round-trip behavior.

### 9.10: Caption Animate Render Preview Panel

Add the missing rendered preview workflow to Caption Animate while preserving the existing style-preview panel.

**Tasks:**
- Keep the current "Style Preview" section for typography/colors, but add a separate rendered preview panel for the actual caption overlay output.
- Add a `Preview` action that renders a short preview clip using the current settings. For Phase 9, the preview contract is a short temporary render (about 5 seconds) starting from the beginning of the subtitle file unless a later preview-position control is explicitly added during implementation.
- Extend the caption render job spec/API path as needed so preview renders can write to a temporary output without being treated as full delivery renders. Preview runs must not register session assets or overwrite the final output field.
- Display the preview in-tab using an actual media surface (`QVideoWidget` / `QMediaPlayer`) or another repo-consistent embedded preview approach that lets the user view the rendered clip inside the tab.
- Route preview jobs through the same shared render pool and global job-status surface used by full renders so preview and full-render jobs obey the same single-heavy-job rule.
- Ensure cancel works for preview renders and that starting a full render while a preview is active is blocked by the shared busy-state rules rather than creating overlapping caption jobs.
- Create/update automated coverage for preview job setup, temporary-output behavior, no-asset-registration behavior, and preview UI state transitions.
- Add a short manual verification pass covering: preview render, preview playback, cancel during preview, and subsequent full render after preview completes.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- Modify `src/audio_visualizer/caption/captionApi.py`
- Modify `src/audio_visualizer/caption/rendering/ffmpegRenderer.py` if preview-duration/start controls belong there
- Modify `tests/test_ui_caption_tab.py`
- Modify `tests/test_caption_render_worker.py`

**Success criteria:** Caption Animate shows both style preview and rendered preview, preview renders stay temporary and in-tab, preview uses the shared heavy-job pipeline, and the user can see a real caption overlay result before launching the full render.

### 9.11: Assets Screen and External Asset Intake

Add the new Assets screen and make it a first-class place to inspect session outputs plus bring in reusable external assets.

**Tasks:**
- Create `AssetsTab` as a `BaseTab` subclass with `tab_id = "assets"` and `tab_title = "Assets"`.
- Register the new tab after `Render Composition` in `MainWindow`, and update settings-schema tab defaults so project/autosave data tolerates `tabs.assets`.
- Keep workflow recipes unchanged as workflow-stage artifacts; do not add `assets` to `workflowRecipes.VALID_STAGES`. If any recipe tests assume the tab list and break because autosave/project state now has `tabs.assets`, update those tests without changing recipe-stage semantics.
- Build the Assets screen around two concerns:
  - A live table/tree of current `SessionAsset` entries with metadata columns such as display name, category, role, source tab, path, duration, dimensions, alpha/audio flags, and key metadata summaries.
  - A visible list of imported external asset roots/files that explains where non-generated assets came from.
- Extend `SessionContext` with helper methods for importing single files and folders. Folder import should scan supported file types, probe metadata where appropriate via `mediaProbe.py`, deduplicate by resolved path, and register imported assets under `source_tab = "assets"` unless a better source is known.
- Persist imported external asset roots/files at the session level if the screen needs to restore that context across project/autosave loads; do not rely on the assets table alone if the UI needs to show which folders were loaded.
- Keep the Assets tab live by subscribing to `asset_added`, `asset_updated`, and `asset_removed`.
- Create/update automated coverage for the new tab registration/order, asset-table refresh behavior, file/folder import behavior, and settings-schema compatibility with the new tab key.
- Add a short manual verification pass covering asset imports, generated outputs appearing automatically, and the Assets tab staying in sync while other tabs run.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/tabs/assetsTab.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/mediaProbe.py` only if import/probe helpers need to be shared
- Modify `tests/test_ui_main_window.py`
- Modify `tests/test_ui_session_context.py`
- Create or modify `tests/test_ui_assets_tab.py`
- Modify `tests/test_workflow_recipes.py` only if schema-compatibility assumptions need adjustment

**Success criteria:** A new Assets tab appears last in navigation, it shows live session assets with useful metadata, the user can import external files/folders from there, and the new support tab integrates cleanly with autosave/project state without changing workflow-recipe stage semantics.

### 9.12: Render Composition Output Resolution Presets

Add the requested standard-resolution presets while preserving manual width/height control.

**Tasks:**
- Add a `Resolution Preset` combo box to the Render Composition output section with `HD (1920x1080)`, `HD Vertical (1080x1920)`, `2K (2560x1440)`, `4K (3840x2160)`, and `Custom`.
- Store the selected preset in the composition state rather than only in transient UI controls so project save/load restores both the preset choice and the derived width/height values consistently.
- Selecting a standard preset should update width/height without triggering recursive UI loops.
- Manual width or height edits should immediately switch the preset selector to `Custom`.
- Ensure preview generation and final render validation use the model's resolved width/height regardless of whether they came from a preset or from `Custom`.
- Create/update automated coverage for preset selection, manual edit fallback to `Custom`, and settings round-trip.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** Render Composition exposes the requested preset list, presets immediately drive width/height, manual edits cleanly switch to `Custom`, and the chosen preset survives save/load.

### 9.13: Render Composition Layered Audio Model

Replace the single audio-source model with a real audio-layer system that matches the requested composition workflow.

**Tasks:**
- Replace `CompositionModel.audio_source_asset_id` / `audio_source_path` with a dedicated layered-audio model, such as a new `CompositionAudioLayer` dataclass list that carries `id`, `display_name`, `asset_id` or `asset_path`, `start_ms`, `duration_ms` or `use_full_length`, and `enabled`.
- Update composition serialization so audio layers persist through autosave/project save/load, and update any session-output metadata that still assumes a single authoritative audio source.
- Replace the current single audio combo UI with an audio-layer list plus editor controls for source selection, start time, duration/full-length behavior, enable/disable, and add/remove/reorder actions.
- Bring layered audio under undo/redo just like visual layers. This likely requires replacing `ChangeAudioSourceCommand` with add/remove/edit/reorder audio-layer commands.
- Update the FFmpeg graph generation and composition worker so multiple enabled audio layers can be delayed, trimmed, and mixed. The Phase 9 contract is: use actual time-offset and trim logic (`adelay`, `atrim`, and `amix` or equivalent) rather than serially picking one source.
- Update composition duration calculation so the final timeline length accounts for enabled audio layers as well as enabled visual layers.
- Keep backwards compatibility for existing saved projects by treating legacy single-audio-source data as one migrated audio layer when loading older Phase 8 state.
- Create/update automated coverage for model serialization, undoable audio-layer edits, duration calculation, and FFmpeg graph generation with multiple audio sources.
- Add a short manual verification pass covering multiple delayed audio layers and full-length vs trimmed behavior.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/workers/compositionWorker.py`
- Modify `src/audio_visualizer/ui/sessionContext.py` if composition output metadata needs to record the new audio-layer summary
- Modify `tests/test_composition_filter_graph.py`
- Modify `tests/test_ui_render_composition_tab.py`

**Success criteria:** Render Composition can manage multiple audio layers with start times and duration/full-length rules, those edits are undoable and persistent, and final renders actually mix the enabled audio layers instead of choosing only one source.

### 9.14: Render Composition Timeline and Layout Rewrite

Deliver the requested drag/drop timeline and reshape the tab layout around loaded assets, selected-layer controls, preview, timeline, and render settings.

**Tasks:**
- Replace the current long-form scroll layout with a composition workspace that matches the target structure as closely as practical:
  - Loaded Assets panel
  - Selected Layer Settings panel
  - Live Preview panel
  - Timeline panel
  - Render Settings / Render controls area
- Add a dedicated `TimelineWidget` (or equivalent timeline scene/view split) that draws both visual and audio layers on separate tracks with a shared time axis.
- The timeline interaction contract for Phase 9 is:
  - Dragging the body of a bar moves its start/end window together.
  - Dragging the leading/trailing handle trims the layer start or end.
  - Selecting an item in the timeline syncs selection with the layer/audio editor controls.
  - Timeline edits update the actual composition model immediately and therefore affect preview/render output.
- Reuse good interaction ideas from SRT Edit where helpful (time-axis math, horizontal scrolling, zoom concepts), but keep the composition timeline as its own widget/model implementation rather than a copy-paste of waveform code.
- Integrate the Loaded Assets panel with `SessionContext` so users can create composition layers from session outputs and imported external assets without manually retyping file paths. If drag/drop from the asset list into the timeline is practical during implementation, that should be the preferred layer-creation path.
- Ensure live preview and final render both read from the same timeline-backed model so the preview is a truthful representation of the composition state.
- Remove or refactor any now-redundant legacy timing controls that would let the UI and the timeline drift out of sync.
- Create/update automated coverage for timeline model synchronization, timeline selection syncing, and any non-trivial helper logic that can be tested outside full pointer-driven GUI interaction.
- Add a focused manual verification checklist for drag/drop, trim handles, timeline zoom/scroll, asset-to-layer creation, and preview/render parity.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Create `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `tests/test_ui_render_composition_tab.py`
- Create or modify timeline-focused UI/helper tests as needed

**Success criteria:** Render Composition presents the requested workspace shape, shows visual and audio layers on a real timeline, supports drag/trim interactions that update the composition model, and keeps preview/render output aligned with the same timeline state.

### 9.15: SessionContext to WorkspaceContext Rename

Rename the shared runtime-state type from `SessionContext` to `WorkspaceContext` so the code matches the broader responsibility added during Stage Three.

**Tasks:**
- Rename the primary class from `SessionContext` to `WorkspaceContext` everywhere in the UI/runtime code that now treats it as the shared working-state model for the current app workspace.
- Rename `src/audio_visualizer/ui/sessionContext.py` to `src/audio_visualizer/ui/workspaceContext.py` and update imports throughout the repo.
- Decide and document the compatibility strategy. For Phase 9, prefer a thin compatibility shim only if needed to avoid a flag day during the refactor; otherwise remove the old name completely once all internal references are updated.
- Keep the persisted settings schema semantics stable. The top-level settings section may remain `session` if changing the serialized key would create unnecessary migration churn; this subphase is about the runtime type name, not forcing a project-file schema rename.
- Update any helper names, type-checking imports, test fixtures, and architecture docs that still refer to `SessionContext`.
- Review related UI labels/comments/docstrings so they use `workspace` terminology only where the meaning is actually broader than a transient session.
- Create/update automated coverage for the renamed imports/aliases and for any compatibility shim retained during the transition.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Rename `src/audio_visualizer/ui/sessionContext.py` to `src/audio_visualizer/ui/workspaceContext.py`
- Modify all imports/usages under `src/audio_visualizer/ui/`
- Modify any non-UI imports/usages that still reference `SessionContext`
- Modify affected tests under `tests/`
- Modify relevant documentation under `.agents/docs/`

**Success criteria:** The shared runtime-state type is consistently named `WorkspaceContext` across code, tests, and docs; any retained compatibility shim is intentional and documented; and persisted project/autosave data continues to load without unnecessary schema churn.

### 9.16: Phase 9 Code Review

Review the completed Phase 9 work as an integrated whole and clean up any temporary scaffolding left behind while implementing the user-debug fixes.

**Tasks:**
- Review every reported change in this phase and confirm it maps to a shipped implementation with either automated tests or an explicit manual verification note.
- Review for regressions introduced by the new settings/app schema work, lazy tab creation, added Assets tab, and layered composition audio/timeline changes.
- Review for dead code, deprecated compatibility shims, or temporary debug-only scaffolding created during GPU/transcription troubleshooting and remove it.
- Review all new/changed tests for structure, determinism, and alignment with the actual UI/module boundaries.
- Run the full test suite: `pytest tests/ -v`
- Update `.agents/docs/architecture/` and any other relevant `.agents/docs/` files so the final docs reflect the new settings dialog, Assets tab, lazy startup path, project-folder behavior, and Render Composition model changes.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- All files touched by Phase 9
- Relevant documentation under `.agents/docs/`

**Success criteria:** Phase 9 is fully implemented without leftover scaffolding, the reported issues are all accounted for, tests pass, and the architecture/docs accurately describe the post-Phase-9 application.

**Phase 9 Changelog:**
- Expanded Phase 9 so every reported debug item maps to a concrete implementation subphase with explicit files, validation, and completion criteria.
- Added missing scope for the new Assets tab, startup lazy-tab initialization, project-folder directory resolution, and the Render Composition audio/timeline model rewrite.
- Tightened Caption Animate, SRT Edit, and SRT Gen work from bug-summary bullets into repo-specific implementation steps grounded in the current code structure.
- Clarified schema boundaries: `app` for theme mode, `session` / `SessionContext` for project-folder and imported-asset context, and no recipe-stage expansion for the new support-only Assets tab.
- Turned the Render Composition "explore" item into a deliverable implementation contract with a real drag/drop timeline and layered audio model.

---

## Phase 10: User Debug - 3

### Reported Changes to Make
- General:
  - In settings, Light/Dark mode should default to system
  - In Light Mode the menu elements are styled for Dark Mode
  - The tab labels should have a horizontal rule separating them.
  - When a tab is selected it does not the border temporarily drawn.
- Audio Visualizer
  - Output Video File path does not automatically append `.mp4` when missing in file name
- SRT Gen
  - When there is extra space in the screen, all elements should remain fixed sized but the log
    panel should expand to fill space.
  - CUDA error still persists:
  '''
  Starting transcription with model 'large' (large-v3)
  Processing 4 file(s)...
  [Stage 0/5] Loading model
  [INFO] Loading model 'large-v3'...
  [INFO] Using device=cuda compute_type=float16
  [INFO] Model 'large-v3' loaded on cuda
  [Stage 1/5] Transcribing Short 1.mp3 (1/4)
  [INFO] Input: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\Short 1.mp3
  [INFO] Output: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\New folder\Short 1.srt
  [Stage 1/4] Converting audio
  [Stage 2/4] Transcribing
  [ERROR] Library cublas64_12.dll is not found or cannot be loaded
  FAILED: Library cublas64_12.dll is not found or cannot be loaded
  [ERROR] Library cublas64_12.dll is not found or cannot be loaded
  Completed 1/4
  [Stage 2/5] Transcribing Short 2.mp3 (2/4)
  [INFO] Input: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\Short 2.mp3
  [INFO] Output: C:\Users\TimEckII\OneDrive - Personal Use\Documents\Podcast\Homilies\2026\3-15-26 Lt 4\New folder\Short 2.srt
  [Stage 1/4] Converting audio
  [Stage 2/4] Transcribing
  '''
  double check the .venv and make sure the proper cuda packages are set up, and then make sure that the
  transcribing code is proper. The model cannot be loaded either by clicking "Load Model" or by clicking "Generate SRTs"
- SRT Edit
  - Slow first loading, need to investigate why. Suspect it it because the wave graph is being
    recreated. Need to investigate how to load screen while wave is calculated and populated
    when finished.
- Caption Animate
  - "Render Preview" button hangs without rendering, and then cannot be canceled:
    '''
    c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\librosa\core\spectrum.py:266: UserWarning: n_fft=2048 is too large for input signal of length=1838
    warnings.warn(
    c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\librosa\core\pitch.py:103: UserWarning: Trying to estimate tuning from empty frequency set.
    return pitch_tuning(
    c:\Users\TimEckII\OneDrive - Personal Use\Documents\Development\Audio Visualizer\.venv\Lib\site-packages\librosa\core\spectrum.py:266: UserWarning: n_fft=2048 is too large for input signal of length=1837
    warnings.warn(
    Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'C:/Users/TimEckII/AppData/Local/audio_visualizer/preview_output.mp4':
    Metadata:
        major_brand     : isom
        minor_version   : 512
        compatible_brands: isomiso2avc1mp41
        encoder         : Lavf61.7.100
    Duration: 00:00:05.01, start: 0.000000, bitrate: 498 kb/s
    Stream #0:0[0x1](und): Video: h264 (Main) (avc1 / 0x31637661), yuv420p(progressive), 1080x100 [SAR 1:1 DAR 54:5], 366 kb/s, 12 fps, 12 tbr, 12288 tbn (default)
        Metadata:
            handler_name    : VideoHandler
            vendor_id       : [0][0][0][0]
    Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 127 kb/s (default)
        Metadata:
            handler_name    : SoundHandler
            vendor_id       : [0][0][0][0]
    Input #0, mp3, from 'C:/Users/TimEckII/OneDrive - Personal Use/Documents/Podcast/Homilies/2026/3-15-26 Lt 4/Short 1.mp3':
    Duration: 00:00:34.43, start: 0.025057, bitrate: 128 kb/s
    Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 128 kb/s
        Metadata:
            encoder         : LAME3.99r
    '''
- Render Composition Screen
  - Timeline elements should snap to other elements to align by time.
  - UI is not properly designed like:
      | Loaded Assets           | Live    |
      |-------------------------|         |
      | Selected Layer Settings | Preview |
      |-----------------------------------|
      | Timeline with drag drop           |
      |-----------------------------------|
      | Render Settings with Render button|
      - All assets (graphic and audio) should be in one place
      - When a layer is selected then the specific settings for that kind of asset
        should be should in a pannel beneath the Loaded Assets panel.
      - The Live Preview needs to be move to the upper right in a column of the height
        of the Loade Assets Panel + Layer Settings Panel in the left column
      - The render panel should be merge with the Output Settings panel.
      - There should not be two render buttons: Start and Cancel. Just Start since the
        global render field will have a cancel button.
      - The Matte/Key Pick button should let the user select a region from the live preview
        to set the value.
- Caption Animate
  - Render preview failed because "FFmpeg cannot edit existing files in-place". We need to make sure that all the
    file outputs are properly checking/handling when an output file already exists.
  - Caption Animate is creating a preview temp file in a fixed fashion and so bumping into the same file, this
    needs to be reviewed.

---

### Phase 10 Planning Notes

- This phase is corrective. Preserve Phase 9 behavior unless a task block here explicitly replaces it.
- For SRT Gen CUDA handling, keep the runtime pre-check in `src/audio_visualizer/srt/core/whisperWrapper.py` so both the explicit `Load Model` flow and the `Generate SRTs` batch flow use the same detection and fallback rules.
- For SRT Edit waveform loading, background workers may only compute/cache waveform data. All widget mutation must remain on the UI thread, and stale worker completions must be ignored when the user selects a newer audio file before the old load finishes.
- For Render Composition, unify audio and visual entries at the UI layer only. Keep `CompositionModel.layers` and `CompositionModel.audio_layers` as the persisted backing model for Phase 10 unless a later phase deliberately migrates the schema.
- Caption preview temp cleanup must cover rerender, failure/cancel, and tab/application teardown. Successful previews should remain playable until they are replaced or the tab closes.

---

### 10.1: General UI Polish — Theme Default, Light Mode Styling, and Sidebar Separators

Fix four general UI shell issues: theme default, light mode stylesheet bleed, navigation separators, and tab selection indicator.

**Root cause notes:**
- Theme defaults to `"off"` (Light) instead of `"auto"` (System) in the settings schema.
- `_apply_theme()` resets the palette for light mode but never clears application-level stylesheets set during dark mode, causing dark styling to bleed into menus and popups.
- Navigation sidebar CSS has no item separators or pressed-state indicator.

**Tasks:**
- In `src/audio_visualizer/ui/settingsSchema.py` line 48, change `"theme_mode": "off"` to `"theme_mode": "auto"` so fresh installs follow system preference.
- In `src/audio_visualizer/ui/mainWindow.py` `_apply_theme()` lines 738-742, add `app.setStyleSheet("")` in the light-mode branch (after `app.setPalette(app.style().standardPalette())`) to clear any dark-mode-specific stylesheet rules. This ensures menus, combo box popups, scroll areas, and context menus fully inherit the system light palette.
- In `src/audio_visualizer/ui/navigationSidebar.py` `_apply_styles()` lines 186-188, add `border-bottom: 1px solid palette(mid);` to `#navigationList::item` for horizontal rule separators between tab labels.
- In the same method, add a `#navigationList::item:pressed` rule with `border-left: 3px solid palette(highlight);` for immediate click feedback, and add `border-left: 3px solid palette(highlight);` to `::item:selected` for a persistent left-edge selection indicator.
- Update `tests/test_ui_settings_schema.py` to verify `create_default_schema()["app"]["theme_mode"] == "auto"`.
- Update `tests/test_ui_main_window.py` to verify toggling dark mode back to light mode clears any application-level stylesheet state while preserving `_current_theme_mode`.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/navigationSidebar.py`
- Modify `tests/test_ui_settings_schema.py`
- Modify `tests/test_ui_main_window.py`

**Success criteria:** New installs default to system theme. Switching to light mode fully resets all widget styling with no dark-mode remnants in menus or popups. Sidebar items are visually separated by horizontal rules. Clicking a tab shows an immediate border indicator; the selected tab has a persistent left-edge indicator.

**Manual verification:** Launch the app fresh (delete `last_settings.json`). Confirm the theme follows system preference. Toggle to light mode and verify menus, combo boxes, and scroll areas render correctly with light backgrounds. Toggle to dark mode and back. Confirm sidebar separators and click indicator are visible.

---

### 10.2: Audio Visualizer MP4 Extension and SRT Gen Log Panel

Fix the output video path `.mp4` auto-append and the SRT Gen log panel expansion.

**Root cause notes:**
- The `.mp4` extension is only appended at render time (`audioVisualizerTab.py:1056-1059`), not when the user edits the path field — so the UI doesn't reflect the actual output name until render starts.
- The event log in SRT Gen has `setMaximumHeight(150)` (line 630) which prevents it from expanding when the window grows.

**Tasks:**
- In `src/audio_visualizer/ui/views/general/generalSettingViews.py`, connect an `editingFinished` handler on the video file path `QLineEdit`. In the handler, if the text is non-empty and has no file extension (`os.path.splitext(text)[1]` is empty), append `.mp4`. This respects user-typed extensions like `.mov`. Keep the existing render-time check in `audioVisualizerTab.py` as a safety net.
- In `src/audio_visualizer/ui/tabs/srtGenTab.py` line 630, remove `self._event_log.setMaximumHeight(150)`. Set the event log size policy to `QSizePolicy(Expanding, Expanding)`. Change line 632 from `layout.addWidget(self._event_log)` to `layout.addWidget(self._event_log, 1)` to set a stretch factor so the log gets all extra vertical space while sibling widgets (buttons, progress bar, status label) remain fixed-size. Ensure the parent `QGroupBox` container policy allows vertical growth.
- Create or update `tests/test_ui_general_settings_view.py` to verify the `.mp4` append happens on focus-out without overriding an explicitly typed extension.
- Update `tests/test_ui_srt_gen_tab.py` to verify `_event_log` no longer has the 150px maximum-height cap and receives the extra vertical stretch.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/views/general/generalSettingViews.py`
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Create or modify `tests/test_ui_general_settings_view.py`
- Modify `tests/test_ui_srt_gen_tab.py`

**Success criteria:** Typing a path without `.mp4` in the Output Video File field and tabbing away auto-appends `.mp4`. The SRT Gen event log expands to fill all available vertical space while buttons and progress bar remain fixed height.

**Manual verification:** In Audio Visualizer tab, type `C:\test\output` in the output path field, click elsewhere, confirm the field now reads `C:\test\output.mp4`. In SRT Gen tab, resize the window vertically and confirm the event log grows while buttons/progress bar stay fixed.

---

### 10.3: SRT Gen CUDA Fix and SRT Edit Waveform Background Loading

Fix the CUDA `cublas64_12.dll` error via a missing dependency and add a pre-check diagnostic. Move the SRT Edit waveform computation to a background thread.

**Root cause analysis — CUDA:**

The CUDA error is a **missing transitive dependency**, not a code bug. The original Local SRT project had its own `.venv` (now deleted) that worked with CUDA. When the Audio Visualizer `.venv` was created fresh for Python 3.13, `pip install` pulled `ctranslate2==4.7.1` which:
- IS compiled with CUDA 12 support (reports CUDA compute types: float16, int8_float16, etc.)
- Bundles `cudnn64_9.dll` but does NOT bundle `cublas64_12.dll` or `cublasLt64_12.dll`
- Expects those DLLs from either the system CUDA Toolkit PATH or the `nvidia-cublas-cu12` pip package

Neither source is available:
- System has CUDA Toolkit v13.1 — its DLLs are named for CUDA 13, not 12
- `nvidia-cublas-cu12` pip package was never installed

Verified via dry-run: `nvidia_cublas_cu12-12.9.1.4-py3-none-win_amd64.whl` installs cleanly.

**Root cause analysis — SRT Edit slow load:**

`_load_audio()` in `srtEditTab.py` (line 347) calls `librosa.load()` synchronously on the UI thread, blocking the interface for seconds on large files.

**Tasks:**
- In `pyproject.toml`, add a new optional dependency group `cuda = ["nvidia-cublas-cu12>=12.4"]`. After updating, run `pip install -e ".[cuda]"` in the dev venv to install the missing DLL.
- In `src/audio_visualizer/srt/core/whisperWrapper.py`, add a `_check_cuda_runtime() -> tuple[bool, str]` function that tries `ctypes.cdll.LoadLibrary("cublas64_12.dll")` and returns availability status with a diagnostic message including install instructions (`pip install nvidia-cublas-cu12`). Call this in `init_whisper_model_internal()` before the CUDA branch so both `ModelManager.load()` and `srtApi.load_model()` inherit the same pre-check. If unavailable: with `strict_cuda=False` or `auto` device, emit a LOG event and fall back to CPU; with `strict_cuda=True`, raise `RuntimeError` with diagnostic.
- In `src/audio_visualizer/srt/modelManager.py` `load()` method, ensure the fallback-to-CPU diagnostic propagates via the emitter as a LOG event.
- In `src/audio_visualizer/ui/workers/srtGenWorker.py`, include `device_used` and `compute_type_used` in the completed payload so `SrtGenTab` can report the resolved runtime used by `Generate SRTs` without depending on `ModelManager` state. Batch auto-load should remain transient; do not silently convert it into an explicit preloaded-model state.
- In `src/audio_visualizer/ui/tabs/srtGenTab.py`, update the model/status UI to show the resolved runtime after both explicit `Load Model` and `Generate SRTs`. On fallback, show `"Loaded on CPU (CUDA unavailable)"` for the explicit preload path and `"Last run used CPU (CUDA unavailable)"` for the transient batch path.
- In `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`, add a minimal loading/error-state surface (for example `set_loading_message()` / `set_error_message()` or an equivalent placeholder API) so the tab can display background-load status without reaching into pyqtgraph internals.
- In `src/audio_visualizer/ui/tabs/srtEditTab.py`, refactor `_load_audio()` (lines 337-355):
  - Show a "Loading waveform..." indicator on `_waveform_view`.
  - Create a private `_WaveformLoadWorker(QRunnable)` class with `Signals(QObject)` emitting `finished(object, int)` and `failed(str)`.
  - Track a monotonically increasing request id or pending path token and ignore stale `finished` / `failed` signals that arrive after the user has already selected a newer audio file.
  - Launch the worker on `QThreadPool.globalInstance()` instead of calling `_load_waveform_data()` synchronously.
  - On completion, call `self._waveform_view.load_waveform(samples, sr)` and clear the loading indicator.
  - On failure, log the error, clear the loading indicator, and show error state.
  - Keep `self._media_player.setSource()` synchronous (lightweight).
  - `_load_waveform_data()` (lines 884-898) already handles the session analysis cache and is safe to call from a worker thread.
- Update `tests/test_srt_model_manager.py` to test CUDA pre-check fallback with mocked `ctypes.cdll.LoadLibrary` raising `OSError`.
- Update `tests/test_srt_gen_worker.py` and `tests/test_ui_srt_gen_tab.py` to verify resolved device / compute-type metadata propagate through the batch-completion path and drive the status text shown after a run.
- Update `tests/test_ui_srt_edit_tab.py` to verify `_load_audio()` launches a worker, ignores stale completions, and keeps waveform-view mutation on the UI thread with mocked loaders.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `pyproject.toml`
- Modify `src/audio_visualizer/srt/core/whisperWrapper.py`
- Modify `src/audio_visualizer/srt/modelManager.py`
- Modify `src/audio_visualizer/ui/workers/srtGenWorker.py`
- Modify `src/audio_visualizer/ui/tabs/srtGenTab.py`
- Modify `src/audio_visualizer/ui/tabs/srtEditTab.py`
- Modify `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- Modify `tests/test_srt_model_manager.py`
- Modify `tests/test_srt_gen_worker.py`
- Modify `tests/test_ui_srt_gen_tab.py`
- Modify `tests/test_ui_srt_edit_tab.py`

**Success criteria:** When CUDA DLLs are missing, the pre-check catches it before model load in both the explicit preload and batch generation paths, emits a diagnostic with install instructions, and falls back to CPU when allowed. After `pip install -e ".[cuda]"`, CUDA transcription works. SRT Edit tab loads audio without blocking the UI, shows a loading indicator while the waveform is computed, and ignores stale worker completions when the user switches files quickly.

**Manual verification:**
- In SRT Gen, select `cuda` device, click `Load Model` without `nvidia-cublas-cu12` installed. Verify diagnostic in the event log and CPU fallback. Then click `Generate SRTs` and verify the same fallback behavior is reported for the batch path. Install `pip install -e ".[cuda]"`, retry both flows, and verify CUDA loads successfully.
- In SRT Edit, load a 30+ second audio file. Verify the UI stays responsive and the waveform appears after a loading indicator. Quickly switch to a second audio file before the first waveform completes and confirm only the newest waveform is shown.

---

### 10.4: Caption Animate Preview Fixes — Hang, In-Place File, and Temp Path Cleanup

Fix the render preview hang, the FFmpeg in-place file conflict, and orphaned temp directory accumulation.

**Root cause analysis:**

**In-place file conflict (primary cause of hang):** In `captionAnimateTab.py` line 1168 & 1172, `output_path=preview_output` and `delivery_output_path=preview_output` are the same path. After `render_subtitle()` writes the overlay to `preview_output`, the worker calls `_create_delivery_output(overlay_path=preview_output, delivery_path=preview_output, audio_path=...)`. FFmpeg reads from and writes to the same file — it either hangs or fails with "cannot edit in-place".

**Missing temp dir cleanup:** `_on_preview_completed()` (line 1203), `_on_render_failed()` (line 1454), and `_on_render_canceled()` (line 1470) all have no cleanup of `self._preview_temp_dir`. `tempfile.mkdtemp()` creates unique dirs per render so concurrent conflicts don't happen, but orphaned directories accumulate.

**Subprocess capture race (secondary):** The monkey-patching of `subprocess.Popen` (lines 108-128 in `captionRenderWorker.py`) to capture the process handle has a race condition — `cancel()` may fire before `_captured_process` is set.

**Tasks:**
- In `src/audio_visualizer/ui/workers/captionRenderWorker.py` `_create_delivery_output()` (lines 188-269), fix the in-place conflict: always write delivery output to a `tempfile.mkstemp()` temp file in the same directory as `delivery_path`, then rename to `delivery_path` after FFmpeg succeeds. On failure or cancel, delete the temp file. This handles both the preview case (`overlay_path == delivery_path`) and the general case safely.
- In the same file, add a `threading.Lock` (`self._process_lock`) around all `_captured_process` access — in `_CapturingPopen.__init__`, in `_create_delivery_output()` line 254, and in `cancel()`. After setting `_cancel_flag` in `cancel()`, if the process handle is None, the flag alone causes the render to abort at the next check point.
- In `src/audio_visualizer/ui/tabs/captionAnimateTab.py`, add a `_cleanup_preview_temp()` helper that calls `shutil.rmtree(self._preview_temp_dir)` and resets the field. Call it at the start of `_start_preview_render()` (to clean up the previous preview before creating a new temp dir), and in `_on_render_failed()` and `_on_render_canceled()` when `self._is_preview_render` was True. Do NOT call it in `_on_preview_completed()` because the media player still needs the file until the next preview.
- Also wire preview-temp cleanup into tab/application teardown (for example `closeEvent()`, a `destroyed` callback, or equivalent shutdown hook) after stopping preview playback so the final successful preview temp directory is not orphaned when the app closes.
- Update `tests/test_caption_render_worker.py` to test: delivery output when `overlay_path == delivery_path` succeeds via temp+rename; cancel during render terminates the process; cancel before subprocess starts aborts via flag.
- Update `tests/test_ui_caption_tab.py` to verify preview temp cleanup on rerender, failure/cancel, and tab teardown when a preview temp directory exists.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- Modify `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- Modify `tests/test_caption_render_worker.py`
- Modify `tests/test_ui_caption_tab.py`

**Success criteria:** Caption Animate preview renders complete without hanging. Cancel terminates FFmpeg reliably. Delivery output never reads and writes the same file. Preview temp directories are cleaned up on rerender, failure, cancellation, and tab/application shutdown.

**Manual verification:** In Caption Animate, load subtitle + audio, click `Render Preview` and confirm completion. Click again immediately and confirm there is no file conflict. Start a preview and quickly click `Cancel` and confirm clean cancellation. Close the tab/app after a successful preview and confirm there are no orphaned `caption_preview_*` directories left behind.

---

### 10.5: Render Composition — UI Reorganization, Timeline Snap, and Key Color Pick

Restructure the Render Composition tab layout, add timeline snap-to-align, and add key color sampling from the live preview.

**Tasks:**

**Task 1 — Restructure `_build_ui()` layout:**

Rewrite `src/audio_visualizer/ui/tabs/renderCompositionTab.py` `_build_ui()` (lines 128-226). Replace the current vertical scroll layout with:

```
root_layout (QVBoxLayout, no scroll area)
+--------------------------------------------------+
| upper_splitter (QSplitter, Horizontal)            |
| +----------------------------+------------------+ |
| | left_column (Vertical)     | "Live Preview"   | |
| | +------------------------+ | QGroupBox        | |
| | | "Loaded Assets"        | |   timestamp spin | |
| | |  unified _layer_list   | |   refresh btn    | |
| | |  (all visual + audio)  | |   _preview_label | |
| | |  button row            | |   (expanding,    | |
| | |  preset selector       | |    min 400x300)  | |
| | +------------------------+ |                  | |
| | | "Layer Settings"       | |                  | |
| | |  QStackedWidget:       | |                  | |
| | |   page 0: visual       | |                  | |
| | |    (source, position,  | |                  | |
| | |     timing, matte)     | |                  | |
| | |   page 1: audio        | |                  | |
| | |    (source, start,     | |                  | |
| | |     duration, full len)| |                  | |
| | +------------------------+ +------------------+ |
+--------------------------------------------------+
| "Timeline" QGroupBox (full-width)                 |
|   TimelineWidget with drag/drop and snap          |
+--------------------------------------------------+
| "Render" QGroupBox (full-width, merged)           |
|   row 1: Resolution, W, H, FPS, Output, Browse   |
|   row 2: Start Render btn + progress + status     |
|   (NO separate Cancel — global JobStatusWidget)   |
+--------------------------------------------------+
```

Specific changes:
- Keep `CompositionModel.layers` and `CompositionModel.audio_layers` as the Phase 10 persisted backing model. Implement the unified `_layer_list` as a UI projection over those collections rather than a schema rewrite. Add helper(s) that map each visible row to `("visual", layer_id)` or `("audio", layer_id)` so selection, remove, timeline sync, and undo routing stay deterministic.
- Merge current `_layer_list` (visual, line 149) and `_audio_layer_list` (audio, line 415) into one unified `_layer_list`. Prefix display names with `[V]` or `[A]` to indicate type.
- Use a `QStackedWidget` with page 0 (visual: source, position/size, timing, matte/key sections) and page 1 (audio: source, start ms, duration, full length). Switch pages in `_on_layer_selected()` based on the selected backing row type.
- Move `_build_preview_section()` content into the right column of `upper_splitter`. Set `_preview_label.setMinimumSize(400, 300)` and `setSizePolicy(Expanding, Expanding)`.
- Merge `_build_output_section()` and `_build_render_section()` into a single group. Remove `_cancel_btn` entirely — cancellation handled by global `JobStatusWidget` via `cancel_job()` (line 1423). Remove all `_cancel_btn` references from render lifecycle methods.
- Remove hidden legacy `_audio_combo` (lines 408-413) and all direct UI references to it. Keep read-compat for legacy serialized `audio_source_*` fields only in the model/settings layer if older saved settings still need to load.

**Task 2 — Add timeline snap-to-align:**

In `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`:
- Add `_SNAP_THRESHOLD_MS = 200` constant.
- Add `_snap_value(self, ms: int, exclude_id: str) -> int` helper that finds the nearest start/end edge of any other item within the threshold.
- In `mouseMoveEvent()` (lines 267-279): for "move" mode, snap `new_start` and `new_end` preferring the closer snap and maintaining duration; for "trim_start" and "trim_end", snap the trimmed edge.
- Track `_snap_line_x: float | None` state. Set it when a snap occurs, draw a thin vertical dashed guide line in `paintEvent()`, clear in `mouseReleaseEvent()`.

**Task 3 — Add key color pick from live preview:**

In `src/audio_visualizer/ui/tabs/renderCompositionTab.py`:
- Add `self._picking_key_color: bool = False` state.
- In `_build_matte_section()`, add a "Pick from Preview" button alongside the existing "Pick" button.
- On click: check that `_preview_label` has a valid pixmap; set crosshair cursor; install event filter.
- In `eventFilter()`: on `MouseButtonPress`, map click coordinates to pixmap coordinates (accounting for aspect ratio scaling and `AlignCenter` padding), sample pixel color via `pixmap.toImage().pixelColor()`, set `_key_color_edit`, call `_on_matte_changed()`, reset cursor and remove filter.
- If no preview exists, show an info message.
- Support `Escape` or right-click cancel while key-pick mode is active, and always restore cursor / remove the event filter if preview generation replaces the pixmap or the mode is canceled unexpectedly.

**Testing:**
- Update `tests/test_ui_render_composition_tab.py`:
  - Verify new layout structure (unified list, stacked widget with 2 pages, no cancel button).
  - Verify row-to-backing-model mapping so selecting a unified-list audio item shows the audio settings page and selecting a visual item shows the visual page.
  - Verify legacy saved settings with audio layers still round-trip even though the hidden `_audio_combo` widget is gone.
  - Test key color pick: mock pixmap, simulate click, verify key color updated.
- Create or update `tests/test_ui_render_composition_timeline_widget.py` to test timeline snap behavior and snap-guide rendering at the widget level if the existing tab test becomes too indirect.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- Modify `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- Modify `tests/test_ui_render_composition_tab.py`
- Create or modify `tests/test_ui_render_composition_timeline_widget.py`

**Success criteria:** Layout matches the target wireframe. All assets appear in one panel with context-sensitive settings driven by a deterministic unified-list projection over the existing visual/audio backing collections. Timeline items snap to edges of other items with a visual guide. Key color can be picked by clicking the preview and can be canceled safely. Single render button with global cancel. All existing functionality (add/remove layers, presets, timeline drag/trim, render lifecycle, undo/redo, settings round-trip) works correctly.

**Manual verification:** Open Render Composition tab — verify layout matches wireframe. Add visual and audio layers — confirm unified list with context-sensitive settings. Drag timeline items near each other — confirm snap with guide line. Generate preview frame, click "Pick from Preview", click colored region — confirm key color updates. Start render — confirm only global cancel available.

---

### 10.6: Phase 10 Code Review

Review the completed Phase 10 work as an integrated whole and clean up any temporary scaffolding created while implementing this round of user-debug fixes.

**Tasks:**
- Review every reported change in this phase and confirm it maps to a shipped implementation with either automated tests or an explicit manual verification note.
- Review for regressions introduced by the theme-default change, light-mode reset behavior, CUDA runtime fallback, async waveform loading, preview-temp cleanup, and the Render Composition layout/timeline rewrite.
- Review for dead code, deprecated compatibility shims, or temporary debug-only scaffolding created during CUDA troubleshooting or Render Composition UI migration and remove it.
- Review all new or changed tests for structure, determinism, and alignment with the actual UI/module boundaries.
- Run the full test suite: `pytest tests/ -v`
- Update `.agents/docs/architecture/` and any other relevant `.agents/docs/` files so the final docs reflect the Phase 10 fixes.
- Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- All files touched by Phase 10
- Relevant documentation under `.agents/docs/`

**Success criteria:** Phase 10 is fully implemented without leftover scaffolding, the reported issues are all accounted for, tests pass, and the architecture/docs accurately describe the post-Phase-10 application.

**Phase 10 Changelog:**
- Added a dedicated third user-debug phase after Phase 9 so another round of post-integration fixes has an explicit place in the plan
- Shifted `Final Review` to Phase 12 to preserve chronological phase ordering
- Reserved a scoped handoff point for future user-reported fixes before release-review work begins
- Expanded with 5 implementation subphases (10.1–10.5) plus a dedicated Phase 10 code-review subphase covering 14 user-reported issues
- Clarified that SRT Gen CUDA runtime checks must live at the shared Whisper wrapper so explicit model loads and batch generation stay in sync
- Clarified that Render Composition unifies audio and visual layers at the UI layer while preserving the existing persisted backing model for Phase 10
- Identified CUDA root cause as missing `nvidia-cublas-cu12` transitive dependency (not a code bug)
- Identified Caption Animate preview hang root cause as FFmpeg in-place file conflict (`output_path == delivery_output_path`)
- Identified SRT Edit slow load root cause as synchronous `librosa.load()` on UI thread
- Added stale waveform-load and preview-temp-teardown constraints so the fixes remain correct under rapid user interaction and app shutdown

---

## Phase 11: User Debug - 4

### Reported Changes to Make
- General
  - The light mode does not work, the fixes in Phase 10 did not properly address the problem. Light mode text in the navigation bar is still
    white and the menus are still black background with black text. The theme drop down should be Light|Dark|Auto
  - The scroll wheel needs to be changed for the timeline in the SRT Edit screen and Timeline screen. In both scroll should pan left/right
    while ctrl+scroll should zoom in/out.
  - When a navigation tab is selected there should BE NO BORDER!
- Assets Screen
  - User should be able to delete session assets from the disk or just delete them from the session.
  - There should be a load from project folder/reload from project folder button to load assets from
    project folder.
- Render Composition Screen
  - When an audio source is selected, and then the length is changed, then when "full length" is checked again it should revert
    to the full length once more.
  - When an audio source is selected and increase beyond it full length, a vertical grey dashed line should on the audio source
    timeline object that marks where the full length original ends, and then the audio should loop for every "second" after and
    the grey line vertical line should appear every time the audio is fully extend another length. The idea being the user should
    be able to set background music and then drag the length to keep the music repeating and see where the loop point is.
  - The loaded asset panel should just have an "Add Asset" button to load visual/audio assets, the "Remove" button, and the preset
    drop down followed by the preset apply. After the preset apply there should be a "Save Preset" button.
  - The user should be able to click on the timeline and set a play head to determine the track preview location.
  - The Loaded assets name should be the file name. And the user should be able to set the name of the layer
  - The user should be able to drag layers on the timeline up or down to change heirarchy
  - Visual layer settings type drop down is unneeded, either it is a video or an image, what it is used for is unimportant.
  - Video layers should follow the the same as audio layers with it comes expanding/shortening video times.
  - Live preview should have two tabs: Timeline|Layer. The timeline time previews the timeline with all layers at that timestamp
    while Layer should the selected layer at that timestamp.
  - Render panenl should only be as large as needed for elements, the Timeline panel should expand to take up extra room in the screen.
- Caption Animate
  - In the Input/Output panel there should be an field for the input audio that is paired with the input srt. This input audio should
    be used for "Mux audio into ouput" option. It should also be used in the "Audio-Reactive" panel
- SRT Edit
  - When the waveforms are loaded, the subtitle overlays are not added after the changes in Phase 10. Selecting a subtitle row also
    no longer zooms in on the sectino of the waveform for this row.
- SRT Gen
  - Input Files pannel should not be so large. It should just be large enouge for its elements.
- Audio Visualizer
  - Output Video File path STILL does not automatically append `.mp4` when missing in file name. This has been specified in Phase 9, and 10
    and yet still is not fixed. The appendix appears latter, and so it appears there is some later thread fixing it, but this is entirely wrong,
    this should be validated the moment the file picker is closed.

---

### Phase 11 Planning Notes

- This phase is corrective. Preserve Phase 10 behavior unless a task block here explicitly replaces it.
- For repeat regressions from Phases 9 and 10 (`.mp4` append, light palette, SRT Edit overlays), fix them through one shared code path/helper per behavior. Do not add separate ad-hoc fixes in different callbacks that can drift apart again.
- Phase 11 does **not** preserve backward compatibility for superseded Render Composition schema or command paths. Remove obsolete fields, migration code, and tests instead of adding compatibility shims.
- For light mode, the root cause is that `app.style().standardPalette()` on Windows 11 dark system theme returns ambiguous palette values. An explicit light palette must be built, mirroring the existing `build_dark_palette()` approach.
- For scroll wheel changes, both `WaveformView` and `TimelineWidget` must follow the same convention: normal scroll = pan, Ctrl+scroll = zoom.
- For SRT Edit subtitle overlays, the root cause is Phase 10.3's background waveform loading: `load_waveform()` calls `_plot_widget.clear()` and `_regions.clear()`, destroying subtitle regions that were set earlier by `_load_subtitle()`. Regions must be re-applied after the waveform finishes loading, and the tab should not reach into private widget fields to decide whether that state exists.
- For Audio Visualizer `.mp4` append, the file-picker path must be handled with standard Qt save-dialog behavior (`AcceptSave` + `setDefaultSuffix("mp4")`) plus one shared normalization helper reused by the dialog callback, `editingFinished`, and validation.
- For Render Composition changes, keep `CompositionModel.layers` and `CompositionModel.audio_layers` as separate persisted backing lists. UI changes unify them visually but the schema stays the same.
- For Render Composition timing changes, any "Full Length", loop-marker, or preview behavior must be backed by model data and FFmpeg command generation. Timeline-only drawing is not a valid fix if render/preview output still behaves differently.
- For Render Composition source metadata, audio/video assets must always have a resolved `duration_ms` before they are accepted into the model. If duration cannot be determined from an existing session asset, probe the file immediately; if probing still fails, abort the add/assign action with a warning instead of storing a partially-known source.

---

### 11.1: General UI Fixes — Light Mode, Scroll Behavior, Nav Border, Theme Labels

Fix four cross-cutting UI shell issues: broken light mode theming, scroll wheel behavior on both timeline widgets, the selected navigation tab border, and simplified theme dropdown labels.

**Root cause notes:**
- Light mode: `_apply_theme()` in `mainWindow.py:743-744` calls `app.style().standardPalette()` for light mode, which on Windows 11 dark system theme returns ambiguous values producing dark bg with dark text. The NavigationSidebar QSS is only applied once at construction and never refreshed on theme change.
- Scroll wheel: `WaveformView` uses Ctrl+wheel=pan, wheel=zoom (inverted from user expectation). `TimelineWidget` imports `QWheelEvent` but has no handler — `_pixels_per_ms` and `_scroll_offset` variables exist but are unused.
- Nav border: `navigationSidebar.py:191,196` applies `border-left: 3px solid palette(highlight)` on selected/pressed items.
- Theme labels: Current labels are `"Off (Light)"`, `"On (Dark)"`, `"Auto (System)"`.

**Tasks:**
- In `mainWindow.py` `_apply_theme()`, build an explicit `build_light_palette()` (parallel to `build_dark_palette()`) with these exact values:
  - `Window`: `QColor(240, 240, 240)`
  - `WindowText`: `QColor(0, 0, 0)`
  - `Base`: `QColor(255, 255, 255)`
  - `AlternateBase`: `QColor(245, 245, 245)`
  - `ToolTipBase`: `QColor(255, 255, 220)`
  - `ToolTipText`: `QColor(0, 0, 0)`
  - `Text`: `QColor(0, 0, 0)`
  - `Button`: `QColor(240, 240, 240)`
  - `ButtonText`: `QColor(0, 0, 0)`
  - `BrightText`: `QColor(255, 0, 0)`
  - `Link`: `QColor(0, 102, 204)`
  - `Highlight`: `QColor(0, 120, 215)`
  - `HighlightedText`: `QColor(255, 255, 255)`
  - Disabled `Text` and `ButtonText`: `QColor(120, 120, 120)`
  Use it instead of `app.style().standardPalette()`. Keep `app.setStyleSheet("")` in the light branch so any stale dark-mode stylesheet state is cleared before the light palette is applied.
- After setting either palette, call `self._sidebar.refresh_theme()` if the sidebar exists, to force QSS re-application against the new palette.
- In `navigationSidebar.py`, add a public `refresh_theme()` method that re-calls `_apply_styles()`. Remove `border-left: 3px solid palette(highlight);` from both `::item:pressed` and `::item:selected` QSS rules.
- In `settingsDialog.py`, change `_THEME_OPTIONS` labels to `"Light"`, `"Dark"`, `"Auto"`.
- In `waveformView.py`, swap scroll wheel behavior using one shared horizontal-pan helper: normal wheel (no modifiers) = horizontal pan, Ctrl+wheel = let pyqtgraph handle zoom. Update both the viewport `eventFilter` and `wheelEvent`, and keep the existing waveform horizontal scrollbar synchronized with the panned range.
- In `timelineWidget.py`, implement standard scroll/zoom state around `_pixels_per_ms` and `_scroll_offset`. Refactor `_ms_to_x` and `_x_to_ms` to use those values. Expose this exact public contract for the owning tab:
  - `set_scroll_offset(ms: int) -> None`
  - `scroll_offset() -> int`
  - `set_pixels_per_ms(value: float) -> None`
  - `pixels_per_ms() -> float`
  - `scroll_state_changed(minimum: int, maximum: int, page_step: int, value: int)` signal
  `renderCompositionTab.py` must create `_timeline_scrollbar = QScrollBar(Qt.Horizontal)` in `_build_timeline_section()` and wire it to that contract; the custom widget itself remains paint-only. Normal wheel pans via scroll offset/scrollbar; Ctrl+wheel zooms around the mouse time anchor. Clamp zoom to `0.02 <= _pixels_per_ms <= 2.0`, clamp scroll offset after every wheel event and resize, and keep the visible time under the mouse pointer anchored during zoom.
- Create/update tests for the explicit light palette, sidebar style refresh, theme labels, waveform wheel behavior, and timeline wheel/scrollbar behavior.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/architecture/development/UI.md` and `.agents/docs/architecture/development/TESTING.md` to reflect the new theme and timeline-input behavior
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- `src/audio_visualizer/ui/mainWindow.py`
- `src/audio_visualizer/ui/navigationSidebar.py`
- `src/audio_visualizer/ui/settingsDialog.py`
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `tests/test_ui_main_window.py`
- `tests/test_ui_settings_dialog.py`
- `tests/test_ui_srt_edit_tab.py`
- `tests/test_ui_render_composition_timeline_widget.py`

**Success criteria:** Light mode renders with correct contrast on all widgets (menus, nav sidebar, popups) on Windows 11. Theme dropdown shows "Light", "Dark", "Auto". Normal scroll pans, Ctrl+scroll zooms on both SRT Edit waveform and Render Composition timeline. No border appears on selected navigation sidebar items.

---

### 11.2: Assets Screen — Delete and Load from Project Folder

Add the ability to remove assets from the session or delete them from disk, and add a button to load/reload assets from the configured project folder.

**Root cause notes:**
- No delete UI exists. The backend `WorkspaceContext.remove_asset()` method is fully implemented but no UI exposes it.
- No "Load from Project Folder" button exists. `WorkspaceContext.import_asset_folder()` and `project_folder` property exist but lack a direct UI trigger in the Assets tab.

**Tasks:**
- In `assetsTab.py`, add three buttons to the button row:
  - "Remove from Session" — calls `workspace_context.remove_asset(asset_id)` for each selected row with `QMessageBox.question` confirmation
  - "Delete from Disk" — prompts `QMessageBox.warning` confirmation, then `Path.unlink(missing_ok=True)` plus `remove_asset()`
  - "Load from Project Folder" — reads `workspace_context.project_folder`; calls `import_asset_folder()` if set, shows info warning if not
- Store `asset.id` as `Qt.ItemDataRole.UserRole` data on the first column table item in `_refresh_table()` so selected rows can be traced back to specific assets. Add one small helper that resolves the currently selected asset ids from the table instead of duplicating row-walk logic in each button handler.
- Make "Load from Project Folder" safe to run repeatedly. Rely on `WorkspaceContext.import_asset_file()` deduplication rather than trying to track a special reload state in the UI.
- When deleting from disk, continue removing the session asset even if the file is already gone; the end state should still be "not in session, not on disk if it existed".
- Create/update tests for remove, delete, and load-from-project-folder handlers
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/architecture/development/UI.md` and `.agents/docs/architecture/development/TESTING.md` to reflect the new Assets tab actions
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- `src/audio_visualizer/ui/tabs/assetsTab.py`
- `tests/test_ui_assets_tab.py`

**Success criteria:** Users can select one or more rows in the asset table and remove them from the session without deleting files, or delete the files from disk along with session removal. A "Load from Project Folder" button imports all supported files from the configured project folder.

---

### 11.3: Render Composition Fixes Part 1 — Audio Revert, Loop Markers, Asset Panel, Layer Names, Type Dropdown, Drag Order

Fix six Render Composition issues: Full Length checkbox revert, audio loop markers, simplified Loaded Assets panel, file-name-based editable layer names, remove layer type dropdown, and connect drag-drop to z-order sync.

**Root cause notes:**
- Full Length revert: `EditAudioLayerCommand` sets `use_full_length=True` but `duration_ms` retains the manually edited value instead of resetting to `0` (the model convention for "full length").
- Loop markers: No implementation exists. `TimelineItem` has no `source_duration_ms` field. `_draw_item()` has no logic for dashed vertical lines, and the FFmpeg audio render path does not loop audio when the requested timeline span exceeds the source duration.
- Asset panel: Currently has 5 buttons (Add Layer, Add Audio, Remove, Up, Down). User wants: "Add Asset" (unified), "Remove", preset dropdown + "Apply" + "Save Preset".
- Layer names: Default names are "Layer 1", "Audio 1". No mechanism sets the name to the file basename on source assignment, and no editable name field exists.
- Type dropdown: `_layer_type_combo` (background, visualizer, caption_overlay, subtitle_direct, custom) is unnecessary per user feedback. The current `layer_type` field exists only to support that dropdown and old preset code.
- Drag order: `_layer_list` has `InternalMove` drag-drop enabled but no signal handler syncs the new order back to the model z-order. Audio rows also have no meaningful z-order.
- Legacy composition state still exists: `CompositionModel.audio_source_asset_id`, `CompositionModel.audio_source_path`, `ChangeAudioSourceCommand`, and the legacy `from_dict()` migration block preserve pre-layered-audio behavior even though Phase 10/11 now use `audio_layers`.

**Tasks:**
- Remove `layer_type` and `VALID_LAYER_TYPES` completely from Render Composition:
  - Delete `layer_type` from `CompositionLayer`
  - Delete `VALID_LAYER_TYPES`
  - Delete `_layer_type_combo` and `_on_layer_type_changed`
  - Delete all preset/test/model references to layer types
  Visual source kind is no longer a user-editable field. Determine whether a visual source is an image or video from session-asset category or file suffix.
- Remove legacy single-audio-source support completely:
  - Delete `CompositionModel.audio_source_asset_id`
  - Delete `CompositionModel.audio_source_path`
  - Delete `ChangeAudioSourceCommand`
  - Delete `_resolve_audio_path()` and every render/output path that reads the deleted fields
  - Delete the `from_dict()` block that migrates legacy audio-source fields into `audio_layers`
  - Delete the tests that assert legacy migration behavior
  After Phase 11, Render Composition audio exists only in `audio_layers`.
- Add `source_duration_ms: int = 0` to both `CompositionAudioLayer` and `CompositionLayer`, and serialize/deserialize it in `model.py`. For `CompositionLayer`, also add `source_kind: str = ""`, where allowed values are `""`, `"image"`, and `"video"`. Populate both fields whenever a source is assigned:
  - Session asset with complete metadata: copy `duration_ms` and map category `image -> "image"`, `video -> "video"`
  - Session asset missing duration metadata: probe `asset.path`, update the session asset, then copy the result
  - Direct file path: call `probe_media(path)` once and set `source_duration_ms` / `source_kind` from the result or file suffix
  - If a video/audio duration still cannot be resolved after probing, abort the add/assign action with `QMessageBox.warning` and leave the model unchanged
- Add exact duration helpers in `model.py` and use them everywhere timing is computed:
  - `CompositionAudioLayer.effective_duration_ms()`: `source_duration_ms` when `use_full_length` is true, otherwise `duration_ms`
  - `CompositionAudioLayer.effective_end_ms()`: `start_ms + effective_duration_ms()`
  - `CompositionLayer.effective_duration_ms()`: `max(0, end_ms - start_ms)`
  `CompositionModel.get_duration_ms()`, `_refresh_timeline()`, preview generation, and render generation must all call these helpers instead of duplicating timing math.
- Extend the relevant undo commands so source metadata round-trips correctly:
  - `ChangeSourceCommand` must carry `asset_id`, `asset_path`, `display_name`, `source_kind`, and `source_duration_ms`
  - `EditAudioLayerCommand` must carry `asset_id`, `asset_path`, `display_name`, and `source_duration_ms` when an audio source changes
  Undo/redo must restore both timing metadata and names, not just the path/id.
- Fix `_on_audio_layer_edited()`: when `_audio_full_length_cb.isChecked()` is True, push `duration_ms=0` and `use_full_length=True` through `EditAudioLayerCommand`. Disable the duration spin box while full length is checked and show the source duration there for display; when unchecked, re-enable manual duration editing and push `use_full_length=False`.
- Add `source_duration_ms` to `TimelineItem`. Populate it from the model in `_refresh_timeline()`. Timeline item start/end must use the model helper methods exactly; remove the current hard-coded 5000 ms fallback for audio items.
- In `_draw_item()`, when `source_duration_ms > 0` and the item span exceeds that duration, draw grey dashed vertical lines at each internal loop boundary `item.start_ms + (n * source_duration_ms)` for every positive integer `n` where the boundary is strictly less than `item.end_ms`.
- Update `filterGraph.build_ffmpeg_command()` so audio layers actually loop in rendered output when their requested timeline duration exceeds `source_duration_ms`:
  - Requested span for audio is always `effective_duration_ms()`
  - If `effective_duration_ms() <= source_duration_ms`, add the input normally and trim only when needed
  - If `effective_duration_ms() > source_duration_ms`, add the input with `-stream_loop -1`, then `atrim=duration=<effective_duration_s>` and `adelay=<start_ms>|<start_ms>`
  - Mix multiple enabled audio layers with `amix=duration=longest`
  Rendered output must match the visible loop markers.
- Replace "Add Layer" and "Add Audio" buttons with a single "Add Asset" button that opens a unified file picker for `*.mp4 *.mkv *.webm *.avi *.mov *.mxf *.png *.jpg *.jpeg *.bmp *.tiff *.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma`. The exact add behavior is:
  - Audio file: create `CompositionAudioLayer(display_name=Path(path).name, asset_path=path, start_ms=0, duration_ms=0, use_full_length=True, source_duration_ms=<resolved duration>, enabled=True)`
  - Video file: create `CompositionLayer(display_name=Path(path).name, asset_path=path, start_ms=0, end_ms=<resolved duration>, source_kind="video", source_duration_ms=<resolved duration>, x=0, y=0, width=output_width, height=output_height, z_order=len(layers), enabled=True)`
  - Image file: create `CompositionLayer(display_name=Path(path).name, asset_path=path, start_ms=0, end_ms=5000, source_kind="image", source_duration_ms=0, x=0, y=0, width=output_width, height=output_height, z_order=len(layers), enabled=True)`
  Remove "Up" and "Down" buttons.
- Define preset persistence exactly in `presets.py`:
  - Store user presets in `get_data_dir() / "render_composition" / "presets"`
  - File name is a slugified preset name plus `.yaml`
  - YAML schema contains only visual-layer layout fields: `display_name`, `x`, `y`, `width`, `height`, `z_order`, `start_ms`, `end_ms`, `behavior_after_end`, `enabled`, `matte_settings`
  - It does **not** store `asset_id`, `asset_path`, `source_kind`, `source_duration_ms`, or any audio layer
  - Add `list_presets()` and `load_preset(name)` helpers so the preset combo shows both built-ins and user-saved presets
  - Applying a preset replaces only `self._model.layers`; `self._model.audio_layers` are left unchanged
  - Saving with an existing name prompts for overwrite confirmation
- When a source file is assigned via browse or combo, set `display_name` to the file name (`asset.display_name` or `Path(path).name`). Add editable `QLineEdit` controls for the layer name in both visual and audio settings pages. `editingFinished` updates `display_name` and refreshes both the list and the timeline.
- Keep the Loaded Assets list as the standard Qt hierarchy editor with one explicit rule: only visual rows are draggable. Audio rows stay below the visual block and are not draggable because they do not participate in visual z-order. Implement that rule by clearing the drag/drop item flags on audio `QListWidgetItem`s when rebuilding the list. Connect `_layer_list.model().rowsMoved` to a new `_on_layer_list_reordered()` handler that recalculates `z_order` from the visual-row order and then refreshes the timeline.
- Create/update tests for the audio full-length reset, model duration calculation, audio loop markers, actual audio-loop FFmpeg command generation, Add Asset defaults, preset save behavior, editable names, and visual z-order drag/drop.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/architecture/development/UI.md`, `.agents/docs/architecture/development/RENDERING.md`, and `.agents/docs/architecture/development/TESTING.md` to reflect the schema cleanup and new Render Composition behavior
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `src/audio_visualizer/ui/tabs/renderComposition/presets.py`
- `src/audio_visualizer/ui/tabs/renderComposition/commands.py`
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `tests/test_ui_render_composition_tab.py`
- `tests/test_ui_render_composition_timeline_widget.py`

**Success criteria:** Checking "Full Length" after manually editing duration resets an audio layer to the source's natural length and stores `duration_ms=0`. Grey dashed vertical lines appear on the timeline at audio loop boundaries, and rendered audio actually loops to match those markers. The asset panel has "Add Asset", "Remove", preset dropdown, "Apply", and "Save Preset", and saved presets are reloadable from the same dropdown. Layer names default to the source file name and are editable. `layer_type`, `audio_source_asset_id`, `audio_source_path`, `ChangeAudioSourceCommand`, and legacy migration code are removed. Dragging visual rows in the Loaded Assets list updates visual z-order in the model and the timeline mirrors that order; audio rows remain fixed below the visual block.

---

### 11.4: Render Composition Fixes Part 2 — Playhead, Video Timing, Preview Tabs, Layout

Add the timeline playhead, align video layer timing behavior with audio layers, add Live Preview tabs (Timeline/Layer), and make the Render panel compact while the Timeline expands.

**Root cause notes:**
- Playhead: No playhead/cursor concept exists in `TimelineWidget`. There is no `_playhead_ms` state, no click handler that updates preview time, and no red vertical line in `paintEvent`.
- Video timing: Audio layers have `use_full_length`/`duration_ms` with loop semantics. Visual layers use `start_ms`/`end_ms`/`behavior_after_end`. User wants consistent expand/shorten behavior with loop markers, but the current model and FFmpeg path do not carry source duration metadata or loop video inputs for render/preview.
- Preview tabs: Current preview is a single panel with no distinction between composition-level and layer-level rendering.
- Layout: Root layout uses `QVBoxLayout` with no stretch factors; the render group takes as much space as the timeline.

**Tasks:**
- In `timelineWidget.py`, add `_playhead_ms: int = 0` state, `playhead_changed = Signal(int)`, and a public `set_playhead_ms(ms: int) -> None` method so the tab can synchronize the playhead from the timestamp spin box. In `mousePressEvent`, set the playhead on any left click in the timeline content area before handling selection/drag so clicking an item still updates preview position. In `paintEvent`, draw a red vertical line at `_ms_to_x(_playhead_ms)` after all items.
- In `renderCompositionTab.py`, connect `_timeline.playhead_changed` to a handler that updates `_preview_time_spin.setValue(ms)`, and connect `_preview_time_spin.valueChanged` back to the timeline setter so timeline and spin box stay synchronized in both directions.
- Add a visual-layer "Full Length" checkbox tied to `source_kind == "video"` and `source_duration_ms > 0`. Show it only for video layers, hide it for image/unassigned layers, and disable it when no valid video duration is available. When checked, set `end_ms = start_ms + source_duration_ms` and disable manual end editing. When unchecked, re-enable end editing; if the current end is not greater than start, set `end_ms = start_ms + source_duration_ms` before re-enabling so the layer remains valid. Still images always use explicit start/end timing and never show the checkbox.
- Update the FFmpeg input/preview builders so video layers use the same source-duration logic as the timeline:
  - Requested span for a visual layer is `end_ms - start_ms`
  - `source_kind == "image"`: do not loop; treat the input as a still image shown for the requested span
  - `source_kind == "video"` and requested span `<= source_duration_ms`: add the input normally and trim to the requested span
  - `source_kind == "video"` and requested span `> source_duration_ms`: add the input with `-stream_loop -1`, then trim to the requested span
  Factor this into shared helpers so `build_ffmpeg_command()`, `build_preview_command()`, and the new `build_single_layer_preview_command()` all follow the same rules.
- Replace the single `_preview_label` with a `QTabWidget` inside the "Live Preview" group containing exactly:
  - "Timeline" tab: `_timeline_preview_label`
  - "Layer" tab: `_layer_preview_label`
  Move the timestamp spin and refresh button above the tab widget so they are always visible. The Layer tab behavior is:
  - Selected visual layer: render only that layer at the current timestamp
  - Selected audio layer: show text `"Audio layers do not have a layer preview."`
  - No selection: show text `"Select a visual layer to preview."`
- Implement `build_single_layer_preview_command()` in `filterGraph.py` by creating a temporary one-layer `CompositionModel` that reuses the same input-building and timing helpers as the full-composition preview path. Do not duplicate separate layer-only FFmpeg timing logic.
- Make the layout compact using standard Qt size policy and stretch rules: add the upper splitter with stretch `0`, the timeline section with stretch `1`, and the render section with stretch `0`; set the render group vertical size policy to `Maximum` so it only takes the height it needs while the timeline group expands.
- Create/update tests for playhead sync, visual full-length behavior, video-loop FFmpeg command generation, preview tabs, audio-layer placeholder behavior in the Layer tab, and layout stretch/size-policy behavior.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/architecture/development/UI.md`, `.agents/docs/architecture/development/RENDERING.md`, and `.agents/docs/architecture/development/TESTING.md` to reflect the playhead, video timing, and preview-tab behavior
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `src/audio_visualizer/ui/tabs/renderComposition/model.py`
- `tests/test_ui_render_composition_tab.py`
- `tests/test_ui_render_composition_timeline_widget.py`

**Success criteria:** Clicking anywhere on the timeline updates a red playhead line and syncs the preview timestamp spin, and changing the spin box updates the playhead. Video layers with known duration have a "Full Length" control and actually loop in preview/render when extended beyond source duration; still images remain manually timed. Preview area has Timeline and Layer tabs, with a clean placeholder for audio-only selection. The render panel is compact and the timeline section expands to fill available vertical space.

---

### 11.5: Caption Animate, SRT Edit, SRT Gen, and Audio Visualizer Fixes

Fix five issues across four tabs: Caption Animate input audio field, SRT Edit subtitle overlay restoration after waveform load, SRT Gen compact input panel, and Audio Visualizer `.mp4` auto-append.

**Root cause notes:**
- Caption Animate: The audio file field is inside the "Audio-Reactive (optional)" section (`captionAnimateTab.py:534-563`). The user wants it in the "Input / Output" panel so it is used for both "Mux audio into output" and "Audio-Reactive".
- SRT Edit overlays: In `_on_waveform_loaded()` (`srtEditTab.py:385-389`), `load_waveform()` calls `_plot_widget.clear()` and `_regions.clear()`, destroying subtitle regions set earlier by `_load_subtitle() -> set_regions()`. Regions must be re-applied after the waveform finishes loading.
- SRT Edit zoom: Same root cause — empty `_regions` list causes `highlight_region(row)` to return early.
- SRT Gen: `QGroupBox("Input Files")` has no vertical size policy constraint, allowing it to expand beyond its needed size.
- Audio Visualizer `.mp4`: The `fileSelected` signal from `QFileDialog` is connected directly to `setText` (`generalSettingViews.py:99`). The `.mp4` validation at line 160-163 only fires on `editingFinished`, which doesn't trigger when the dialog sets the text programmatically.

**Tasks:**
- **Caption Animate**: Add an "Input audio:" row with `QLineEdit`, "Browse..." button, and session audio combo to `_build_input_section()`. Remove the duplicate audio file widgets from `_build_audio_reactive_section()`. Make the session-audio combo populate the same line edit so there is one source of truth for audio path. Reference `_input_audio_edit.text()` wherever audio path is needed (mux audio validation, audio-reactive analysis, preview/render job spec). Update `collect_settings()` and `apply_settings()` to serialize/restore the new field and combo selection.
- **Caption Animate**: Persist `input_audio_path` as the only saved audio-input setting. On `apply_settings()`, set the line edit first, then select the matching session-audio combo item by comparing asset paths; do not persist a separate session-audio identifier.
- **SRT Edit**: In `_load_audio()`, before starting the worker, clear any pending highlight, call a public `clear_regions()` helper on `WaveformView`, and then call `set_loading_message("Loading waveform...")`. In `_on_waveform_loaded()`, after `self._waveform_view.load_waveform(samples, sr)`, re-apply regions when document entries exist. Add a `_pending_highlight_row: int | None = None` field on the tab. Add public `has_regions()` and `clear_regions()` helpers on `WaveformView` and use them instead of reading `_waveform_view._regions` directly. In `_on_table_selection_changed()`, if waveform regions are not available yet, store the row in `_pending_highlight_row`. In `_on_waveform_loaded()`, after restoring regions, replay the pending highlight if present, otherwise highlight the current table selection if one exists. In `_load_subtitle()`, after `set_regions()`, immediately replay the current table selection if the waveform is already loaded. Clear `_pending_highlight_row` on new audio load, new subtitle load, and load failure so stale selections do not replay later.
- **SRT Gen**: After `group.setLayout(layout)` in `_build_input_section()`, call `group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)`.
- **Audio Visualizer**: Configure the video output dialog as a save dialog with `setAcceptMode(QFileDialog.AcceptSave)` and `setDefaultSuffix("mp4")`. Factor path normalization into one helper named `_normalize_video_output_path(text: str) -> str` with this exact behavior:
  - Trim leading/trailing whitespace for evaluation and for the returned value
  - If the trimmed value is empty, return `""`
  - If it has no suffix, append `.mp4`
  - If it already ends with `.mp4` (case-insensitive), keep it unchanged except for trimming
  - If it has any other suffix, keep it unchanged; `validate_view()` continues to reject non-`.mp4` outputs
  Call the helper from the file-dialog callback, the `editingFinished` handler, and `validate_view()` so the same rule is applied everywhere. The file-picker callback should update the line edit immediately when the dialog closes; validation remains a safety net, not the primary fix.
- Create/update tests for the shared Caption Animate audio field, waveform-region restoration and deferred highlight replay, SRT Gen input-group size policy, and shared `.mp4` normalization for both dialog-selected and manually typed paths.
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/architecture/development/UI.md` and `.agents/docs/architecture/development/TESTING.md` to reflect the new Caption Animate, SRT Edit, SRT Gen, and Audio Visualizer behavior
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- `src/audio_visualizer/ui/tabs/srtEditTab.py`
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- `src/audio_visualizer/ui/tabs/srtGenTab.py`
- `src/audio_visualizer/ui/views/general/generalSettingViews.py`
- `tests/test_ui_caption_tab.py`
- `tests/test_ui_srt_edit_tab.py`
- `tests/test_ui_srt_gen_tab.py`
- `tests/test_ui_general_settings_view.py`

**Success criteria:** Caption Animate has one input audio field in the Input/Output panel that is used for both mux audio and audio-reactive features. SRT Edit subtitle overlays appear on the waveform after background loading completes, and selecting a subtitle row before or after the waveform finishes still zooms to the correct section. SRT Gen Input Files panel only takes as much vertical space as its elements need. Audio Visualizer output path gets `.mp4` appended immediately when the file picker closes, and the same normalization rule is used for manual text entry.

---

### 11.6: Phase 11 Code Review

Review the completed Phase 11 work as an integrated whole once the fourth user-debug pass has been defined and implemented.

**Tasks:**
- Review every reported change added to Phase 11 and confirm it maps to a shipped implementation with either automated regression coverage or an explicit manual verification note
- Re-test the repeat regressions from Phases 9 and 10 as first-class checks: light mode menus/sidebar contrast, immediate `.mp4` append on save-dialog close, SRT Edit overlay/highlight after async waveform loading, and Render Composition full-length reset plus actual loop behavior in preview/render
- Review for regressions introduced while addressing the Phase 11 fixes
- Review the final code for duplicated fix logic on the repeated-regression items. The desired end state is one shared helper/code path per behavior, not multiple partially overlapping fixes.
- Review specifically for deleted compatibility paths that must stay deleted after the phase:
  - Render Composition `layer_type`
  - Render Composition `audio_source_asset_id`
  - Render Composition `audio_source_path`
  - `ChangeAudioSourceCommand`
  - Legacy Render Composition migration tests/data paths
- Review for dead code, deprecated compatibility shims, or temporary debug scaffolding created during the Phase 11 work and remove it
- Review all new or changed tests for structure, determinism, and alignment with the actual UI/module boundaries
- Run the full test suite: `pytest tests/ -v`
- Update these documentation files so they reflect the post-Phase-11 application exactly:
  - `.agents/docs/ARCHITECTURE.md`
  - `.agents/docs/INDEX.md`
  - `.agents/docs/architecture/development/UI.md`
  - `.agents/docs/architecture/development/RENDERING.md`
  - `.agents/docs/architecture/development/TESTING.md`
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- All files touched by Phase 11
- Relevant documentation under `.agents/docs/`

**Success criteria:** The fourth user-debug pass is fully implemented, reviewed, and documented without leftover scaffolding or untracked regressions.

**Phase 11 Changelog:**
- Added a dedicated fourth user-debug phase after Phase 10 so another post-integration fix pass has an explicit place in the plan
- Shifted `Final Review` to Phase 12 to preserve chronological phase ordering
- Expanded with 5 implementation task blocks (11.1 through 11.5) plus the code-review block 11.6 covering 20 user-reported issues
- Tightened the repeated-regression fixes so light mode, `.mp4` append, and SRT Edit overlay restoration each go through a single shared implementation path instead of scattered callbacks
- Identified light mode root cause as `standardPalette()` returning ambiguous values on Windows 11 dark system theme — requires building an explicit light palette
- Identified SRT Edit subtitle overlay loss as a race between background waveform loading and region setup — `load_waveform()` calls `clear()` which destroys regions
- Identified Audio Visualizer `.mp4` append issue as a save-dialog configuration plus shared-normalization problem — fix must use standard Qt save-dialog behavior and one reusable path-normalization helper
- Identified Render Composition "Full Length" revert issue as `EditAudioLayerCommand` not resetting `duration_ms` to 0
- Expanded Render Composition work so source duration metadata, timeline loop markers, and actual FFmpeg loop behavior stay aligned for audio/video layers
- Added timeline playhead, loop markers, video timing alignment, preview tabs, and layout compaction to Render Composition
- Unified Caption Animate audio input into the Input/Output panel for both mux and audio-reactive usage

---

## Phase 12: Final Review

### 12.1: Code Review

Perform a final code-quality and regression review across the full Stage Three implementation before final documentation and release work.

**Tasks:**
- Review all phases in this plan and ensure there are no gaps or bugs remaining in the implementation
- Review all changes for unintended regressions
- Review for deprecated code, dead code, or legacy compatibility shims and remove them
- Review all new modules for proper error handling, cancellation safety, and logging
- Review the full test suite:
  - No auto-pass tests
  - Test structure matches the new module structure
  - All new features have tests
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Potentially modify any files changed in Phases 1-11, especially under `src/audio_visualizer/`, `tests/`, and `.agents/docs/`

**Success criteria:** No known Stage Three implementation gaps remain, and the multi-tab app is ready for the final test/documentation/release pass.

### 12.2: Integration Testing

Run the full regression and integration pass against the completed Stage Three application.

**Tasks:**
- Run all existing tests: `pytest tests/ -v`
- Verify no pre-existing tests regressed on the new Qt dependency lane
- Verify the full Stage Three integration coverage passes in the same suite run
- Verify the multi-tab application launches and all tabs instantiate successfully in the project environment
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- No new files planned; if regressions are found, modify the affected files under `src/audio_visualizer/` and `tests/`

**Success criteria:** The full test suite passes and the multi-tab application starts successfully with all Stage Three tabs and worker flows intact.

### 12.3: Architecture Documentation Update

**Tasks:**
- Update `ARCHITECTURE.md` to reflect the tab-based app structure, `WorkspaceContext`, worker architecture, and new persistence model
- Update `INDEX.md` to reference the new Stage Three UI architecture and any new package docs
- Update `.agents/docs/architecture/development/OVERVIEW.md` with the new end-to-end tab workflow
- Update `.agents/docs/architecture/development/UI.md` for the new `MainWindow`, tab classes, shared status shell, and undo/menu behavior
- Update `.agents/docs/architecture/development/RENDERING.md` for the new worker model, cancel boundaries, caption rendering, and composition rendering
- Update `.agents/docs/architecture/development/TESTING.md` for the new Qt/widget/integration coverage
- Add or update package docs for any new `ui` subpackages introduced by Stage Three
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `.agents/docs/ARCHITECTURE.md`
- Modify `.agents/docs/INDEX.md`
- Modify `.agents/docs/architecture/development/OVERVIEW.md`
- Modify `.agents/docs/architecture/development/UI.md`
- Modify `.agents/docs/architecture/development/RENDERING.md`
- Modify `.agents/docs/architecture/development/TESTING.md`
- Potentially create additional package docs under `.agents/docs/architecture/packages/`

**Success criteria:** The architecture docs accurately describe the Stage Three codebase and workflow model.

### 12.4: Release Preparation

**Tasks:**
- Update `readme.md` to reflect the new multi-tab workflow, SRT editing, caption animation, render composition, and workflow-recipe features
- Align version strings across `pyproject.toml`, `src/audio_visualizer/__init__.py`, and `readme.md` for the Stage Three release number
- Run final full test suite: `pytest tests/ -v`
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `pyproject.toml`
- Modify `src/audio_visualizer/__init__.py`
- Modify `readme.md`

**Success criteria:** Release-facing documentation and version strings match the completed Stage Three feature set, and the final full test suite passes.
