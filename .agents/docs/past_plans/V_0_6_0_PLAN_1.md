# Stage One Implementation Plan: Realign `.agents/` Documentation

**Reference:** [V_0_6_0_RESEARCH_PLAN_1.md](V_0_6_0_RESEARCH_PLAN_1.md) for background context. This document is the authoritative implementation plan.

---

## Phase 1: Remove Irrelevant Files

### 1.1: Delete LSM Architecture Documentation
Delete all LSM-specific architecture files that have no Audio Visualizer analog.

**Tasks:**
- Delete all 24 files in `.agents/docs/architecture/packages/` (`lsm.*.md`)
- Delete all 10 files in `.agents/docs/architecture/development/`
- Delete all 5 files in `.agents/docs/architecture/api-reference/`
- Remove the now-empty `packages/`, `development/`, and `api-reference/` subdirectories

**Files to delete:**
- `.agents/docs/architecture/packages/lsm.md`
- `.agents/docs/architecture/packages/lsm.agents.md`
- `.agents/docs/architecture/packages/lsm.agents.memory.md`
- `.agents/docs/architecture/packages/lsm.agents.tools.md`
- `.agents/docs/architecture/packages/lsm.config.md`
- `.agents/docs/architecture/packages/lsm.config.models.md`
- `.agents/docs/architecture/packages/lsm.db.md`
- `.agents/docs/architecture/packages/lsm.ingest.md`
- `.agents/docs/architecture/packages/lsm.migration.md`
- `.agents/docs/architecture/packages/lsm.providers.md`
- `.agents/docs/architecture/packages/lsm.query.md`
- `.agents/docs/architecture/packages/lsm.remote.md`
- `.agents/docs/architecture/packages/lsm.ui.md`
- `.agents/docs/architecture/packages/lsm.ui.desktop.md`
- `.agents/docs/architecture/packages/lsm.ui.helpers.md`
- `.agents/docs/architecture/packages/lsm.ui.shell.md`
- `.agents/docs/architecture/packages/lsm.ui.tui.md`
- `.agents/docs/architecture/packages/lsm.ui.tui.presenters.md`
- `.agents/docs/architecture/packages/lsm.ui.tui.screens.md`
- `.agents/docs/architecture/packages/lsm.ui.tui.state.md`
- `.agents/docs/architecture/packages/lsm.ui.tui.widgets.md`
- `.agents/docs/architecture/packages/lsm.ui.web.md`
- `.agents/docs/architecture/packages/lsm.utils.md`
- `.agents/docs/architecture/packages/lsm.vectordb.md`
- `.agents/docs/architecture/development/OVERVIEW.md`
- `.agents/docs/architecture/development/AGENTS.md`
- `.agents/docs/architecture/development/INGEST.md`
- `.agents/docs/architecture/development/MIGRATIONS.md`
- `.agents/docs/architecture/development/MODES.md`
- `.agents/docs/architecture/development/PROVIDERS.md`
- `.agents/docs/architecture/development/QUERY.md`
- `.agents/docs/architecture/development/SECURITY.md`
- `.agents/docs/architecture/development/TESTING.md`
- `.agents/docs/architecture/development/TUI_ARCHITECTURE.md`
- `.agents/docs/architecture/api-reference/ADDING_PROVIDERS.md`
- `.agents/docs/architecture/api-reference/CONFIG.md`
- `.agents/docs/architecture/api-reference/PROVIDERS.md`
- `.agents/docs/architecture/api-reference/REMOTE.md`
- `.agents/docs/architecture/api-reference/REPL.md`

**Success criteria:** `.agents/docs/architecture/` is an empty directory. The `packages/`, `development/`, and `api-reference/` subdirectories no longer exist.

### 1.2: Delete LSM Plans and Phases
Delete all LSM-specific plans and phase documents. Keep the directories for future use.

**Tasks:**
- Delete all 23 files in `.agents/docs/plan_phases/` (PHASE_1.md through PHASE_23.md)
- Delete all 8 files in `.agents/docs/past_plans/`
- Delete both files in `.agents/future_plans/`
- Delete `.agents/docs/PLAN.md`
- Delete `.agents/docs/v_0_9_0_RESEARCH_PLAN.md`
- Verify `plan_phases/`, `past_plans/`, and `future_plans/` directories still exist (empty)

**Files to delete:**
- `.agents/docs/plan_phases/PHASE_1.md` through `PHASE_23.md` (23 files)
- `.agents/docs/past_plans/INGEST_FUTURE.md`
- `.agents/docs/past_plans/v_0_7_0_PLAN.md`
- `.agents/docs/past_plans/v_0_7_1_PLAN.md`
- `.agents/docs/past_plans/v_0_7_1_RESEARCH_PLAN.md`
- `.agents/docs/past_plans/v_0_8_0_PLAN.md`
- `.agents/docs/past_plans/v_0_8_0_RESEARCH_PLAN.md`
- `.agents/docs/past_plans/v_0_8_1_PLAN.md`
- `.agents/docs/past_plans/v_0_8_1_RESEARCH_PLAN.md`
- `.agents/future_plans/FINANCE_PROVIDERS.md`
- `.agents/future_plans/v_0_10_0_RESEARCH_PLAN.md`
- `.agents/docs/PLAN.md`
- `.agents/docs/v_0_9_0_RESEARCH_PLAN.md`

**Success criteria:** All LSM plan files are deleted. `plan_phases/`, `past_plans/`, and `future_plans/` directories exist but are empty.

### 1.3: Phase 1 Review
Verify the deletion phase is complete and only the correct files remain.

**Tasks:**
- List all remaining files in `.agents/`
- Confirm exactly 7 files remain in `.agents/docs/`: `INDEX.md`, `ARCHITECTURE.md`, `CODING_PATTERNS.md`, `COMMIT_MESSAGE.md`, `CREATE_IMPLEMENTATION_PLAN.md`, `RESEARCH_PLAN.md`, `RELEASE_STATEMENT.md`
- Confirm 3 empty directories remain: `plan_phases/`, `past_plans/`, `future_plans/`
- Confirm `.agents/docs/architecture/` exists but is empty
- Run `git diff --stat` to verify only expected files were deleted

**Success criteria:** `.agents/docs/` contains exactly 7 top-level doc files, `.agents/docs/architecture/` exists and is empty, and the preserved directories (`.agents/docs/plan_phases/`, `.agents/docs/past_plans/`, `.agents/future_plans/`) remain in place and empty.

---

## Phase 2: Rewrite Core Documentation

### 2.1: Rewrite `INDEX.md`
Rewrite the project entry point to describe Audio Visualizer.

**Tasks:**
- Read all core source files to confirm current state: `__init__.py`, `__main__.py`, `visualizer.py`, `app_logging.py`, `app_paths.py`, `updater.py`
- Read `pyproject.toml` for project metadata
- Rewrite `INDEX.md` with:
  - Project name and purpose: desktop tool for generating synchronized audio visualization videos
  - Tech stack: Python >=3.13, PySide6, librosa, numpy, av (PyAV), Pillow
  - Entry points: `python -m audio_visualizer` and `audio-visualizer` script
  - High-level architecture overview (core, ui, visualizers)
  - Build notes: PyInstaller support, icon resolution for frozen builds
  - Environment variables: `AUDIO_VISUALIZER_REPO` for update checking
  - Links to `ARCHITECTURE.md`, `CODING_PATTERNS.md`, and other docs

**Files:** `.agents/docs/INDEX.md`

**Success criteria:** `INDEX.md` accurately describes the Audio Visualizer project. A developer reading it can understand the project purpose, how to run it, and where to find further documentation. Zero LSM references.

### 2.2: Rewrite `ARCHITECTURE.md`
Rewrite the architecture overview to map the actual Audio Visualizer codebase.

**Tasks:**
- Read key structural files: `ui/mainWindow.py`, `ui/views/__init__.py`, `visualizers/__init__.py`, `visualizers/utilities.py`, `visualizers/genericVisualizer.py`
- Read representative view and visualizer files to confirm patterns
- Rewrite `ARCHITECTURE.md` with:
  - Package map of `src/audio_visualizer/`
  - Core modules section: `visualizer.py`, `app_logging.py`, `app_paths.py`, `updater.py`
  - UI layer section: `ui/mainWindow.py`, `ui/renderDialog.py`, `ui/views/` (general, volume, chroma)
  - Visualizer engine section: `visualizers/` (genericVisualizer, utilities, volume, chroma, combined, waveform)
  - Key abstractions: `Visualizer` base class, `View` base class, `AudioData`, `VideoData`, `VisualizerOptions` enum
  - Data flow: audio file → librosa → AudioData → frame generation → av video
  - View-to-Visualizer mapping: `_VIEW_ATTRIBUTE_MAP` pattern
  - Links to detailed package docs once Phase 3 creates them

**Files:** `.agents/docs/ARCHITECTURE.md`

**Success criteria:** `ARCHITECTURE.md` provides a complete package-level map of the codebase. Every package and key abstraction is documented. Zero LSM references.

### 2.3: Rewrite `CODING_PATTERNS.md`
Rewrite coding conventions to reflect the actual project patterns.

**Tasks:**
- Sample multiple source files to confirm naming and style patterns
- Rewrite `CODING_PATTERNS.md` with:
  - Module naming: mixed conventions already present in the codebase; snake_case for utility modules (`app_logging.py`, `app_paths.py`, `updater.py`) and camelCase for many UI / view / visualizer modules (`mainWindow.py`, `generalView.py`, `genericVisualizer.py`)
  - Class naming: PascalCase (`MainWindow`, `AudioData`, `GeneralVisualizerView`)
  - Method/function naming: snake_case (`get_config_dir()`, `load_audio_data()`, `setup_logging()`)
  - Enum value naming: UPPER_SNAKE_CASE (`VOLUME_RECTANGLE`, `LEFT_TO_RIGHT`)
  - Architecture pattern: Visualizer/View separation (engine class + UI settings class per visualizer type)
  - Base-class usage: `Visualizer` for renderers and `View` for settings panels (implemented via shared base classes that raise `NotImplementedError`, not `abc.ABC`)
  - Enum-driven configuration: `VisualizerOptions` → `_VIEW_ATTRIBUTE_MAP`
  - Qt patterns: PySide6 signals/slots, QThreadPool (max 1) for rendering, QTimer debounce for live preview
  - Logging: `app_logging.setup_logging()` file-based at INFO level
  - Testing: pytest in `tests/` directory

**Files:** `.agents/docs/CODING_PATTERNS.md`

**Success criteria:** `CODING_PATTERNS.md` documents conventions that match the actual code. A developer can follow these patterns when adding new code. Zero LSM references.

### 2.4: Update `COMMIT_MESSAGE.md`
Strip LSM references while preserving the existing template style.

**Tasks:**
- Replace "Local Second Mind" with "Audio Visualizer" in the description
- Replace the LSM-specific example ("research agent multi-source query") with an Audio Visualizer example
- Keep the template format, guidelines, and structure unchanged

**Files:** `.agents/docs/COMMIT_MESSAGE.md`

**Success criteria:** Template style is unchanged. Example is relevant to Audio Visualizer. Zero LSM references.

### 2.5: Rewrite `CREATE_IMPLEMENTATION_PLAN.md`
Adapt the implementation plan template for Audio Visualizer.

**Tasks:**
- Read the current file to identify all LSM-specific references
- Keep the plan structure: numbered phases, task blocks (N.N), task block contents, post-task completion, success criteria, code review phases, changelog
- Remove LSM-specific items from post-task completion:
  - Remove: API keys / `.env` file references
  - Remove: `example_config.json` and `.env.example` references
  - Remove: DB migration script references (`lsm/migration/scripts/`)
  - Keep: test running (`pytest tests/ -v`)
  - Keep: architecture doc updates
  - Keep: git commit with `COMMIT_MESSAGE.md` format
- Remove LSM-specific items from final review:
  - Remove: DB migration verification
  - Remove: FTS5, cross-encoder, agent tools security checks
  - Remove: SLO targets (TUI startup, retrieval p95, query p95, ingest throughput)
  - Remove: LSM-specific file paths (`lsm/ui/tui/screens/help.py`, etc.)
  - Keep: general code review, test review, architecture doc update, release prep structure
- Replace LSM paths with Audio Visualizer equivalents where applicable

**Files:** `.agents/docs/CREATE_IMPLEMENTATION_PLAN.md`

**Success criteria:** Template is fully functional for planning Audio Visualizer tasks. All LSM-specific paths, commands, and concepts are removed. Structure and methodology are preserved.

### 2.6: Rewrite `RESEARCH_PLAN.md`
Adapt the research plan template for Audio Visualizer.

**Tasks:**
- Read the current file to identify all LSM-specific references
- Keep the methodology: describe realities, ground in codebase, present options with trade-offs, leave scope decisions as clarification questions
- Remove LSM-specific examples (pagination strategy, logging system examples)
- Replace with Audio Visualizer examples where helpful (e.g., visualizer rendering approaches, UI layout options)

**Files:** `.agents/docs/RESEARCH_PLAN.md`

**Success criteria:** Template is fully functional for Audio Visualizer research. Methodology is preserved. Zero LSM references.

### 2.7: Update `RELEASE_STATEMENT.md`
Strip LSM references while preserving the existing template style.

**Tasks:**
- Replace "Local Second Mind" with "Audio Visualizer" in the header template and description
- Replace LSM-specific config examples in Upgrade Notes (`llms.tiers`, `global.mcp_servers`, "agent subpackage restructuring", "remote provider schemas") with Audio Visualizer equivalents
- Replace the hardcoded changelog reference (`docs/CHANGELOG.md`) with a repo-accurate path or remove that footer from the template if the project continues without a checked-in changelog
- Keep the template format, section structure, and authoring guidelines unchanged

**Files:** `.agents/docs/RELEASE_STATEMENT.md`

**Success criteria:** Template style is unchanged. All examples are relevant to Audio Visualizer. Zero LSM references.

### 2.8: Phase 2 Review
Review all 7 rewritten/updated files for quality and consistency.

**Tasks:**
- Read all 7 files and verify no LSM references remain
- Cross-check `INDEX.md` links against actual file paths
- Verify `ARCHITECTURE.md` classes/modules match actual source files in `src/`
- Verify `CODING_PATTERNS.md` conventions match actual code style
- Verify `COMMIT_MESSAGE.md` and `RELEASE_STATEMENT.md` retain their original template style
- Verify `CREATE_IMPLEMENTATION_PLAN.md` and `RESEARCH_PLAN.md` are self-consistent

**Success criteria:** All 7 files are accurate, internally consistent, and contain zero LSM references.

---

## Phase 3: Rebuild Architecture Documentation

### 3.1: Create Package Documentation
Create detailed package docs for each major module under `.agents/docs/architecture/packages/`.

**Tasks:**
- Create `audio_visualizer.md`:
  - Root package overview, version (0.5.1), license (MIT)
  - Entry points and dependencies from `pyproject.toml`
  - `__main__.py` as the `python -m audio_visualizer` shim
  - Package structure tree
- Create `audio_visualizer.core.md`:
  - `visualizer.py`: `main()` function, QApplication setup, icon resolution, MainWindow launch
  - `app_logging.py`: `setup_logging()`, log file location, formatter, log level
  - `app_paths.py`: `get_config_dir()`, `get_data_dir()`, platform detection
  - `updater.py`: `get_current_version()`, `fetch_latest_release()`, `is_update_available()`, GitHub API integration
- Create `audio_visualizer.ui.md`:
  - `mainWindow.py`: `MainWindow`, layout structure, `_VIEW_ATTRIBUTE_MAP`, render threading (QThreadPool max 1), background update-check workers, live preview (QTimer 400ms debounce), settings persistence, and render / preview orchestration
  - `renderDialog.py`: post-render playback dialog with looping video preview and volume controls
  - Overview of view mapping from `VisualizerOptions` enum to view classes
- Create `audio_visualizer.ui.views.md`:
  - `View` base class: `get_view_in_layout()`, `get_view_in_widget()`, `validate_view()`, `read_view_values()`
  - `Fonts` class: h1_font (24pt bold), h2_font (16pt underlined)
  - `general/` subpackage: `GeneralSettingsView`, `GeneralVisualizerView`, `CombinedVisualizerView`, `WaveformVisualizerView`
  - `volume/` subpackage: Rectangle, Circle, Line, ForceLine view classes
  - `chroma/` subpackage: Rectangle, Circle, Line, LineBands, ForceRectangle, ForceCircle, ForceLine, ForceLines view classes
- Create `audio_visualizer.visualizers.md`:
  - `Visualizer` base class: constructor signature, `prepare_shapes()`, `generate_frame()`, super-sampling
  - `AudioData`: fields, `load_audio_data()`, librosa integration
  - `VideoData`: fields, container management
  - `VisualizerOptions` enum: all 14 types
  - `VisualizerFlow` and `VisualizerAlignment` enums
  - `volume/` subpackage: 4 visualizer implementations
  - `chroma/` subpackage: 8 visualizer implementations
  - `combined/` subpackage: 1 implementation
  - `waveform/` subpackage: 1 implementation

**Files:**
- `.agents/docs/architecture/packages/audio_visualizer.md`
- `.agents/docs/architecture/packages/audio_visualizer.core.md`
- `.agents/docs/architecture/packages/audio_visualizer.ui.md`
- `.agents/docs/architecture/packages/audio_visualizer.ui.views.md`
- `.agents/docs/architecture/packages/audio_visualizer.visualizers.md`

**Success criteria:** Each package doc accurately reflects the source code. All public classes, key methods, and relationships are documented.

### 3.2: Create Development Overviews
Create high-level development guides under `.agents/docs/architecture/development/`.

**Tasks:**
- Create `OVERVIEW.md`:
  - System context: desktop application for audio-to-video conversion
  - Component diagram: Core → UI → Visualizers
  - Data flow: audio file → librosa analysis → AudioData → Visualizer.generate_frame() → av video container
  - Key design decisions: Visualizer/View separation, enum-driven config, threaded rendering
- Create `VISUALIZERS.md`:
  - Visualizer base-class lifecycle: construction → `prepare_shapes()` → `generate_frame(frame_index)` loop
  - Audio analysis pipeline: file → librosa.load() → sample chunking → volume/chromagram computation
  - Adding a new visualizer: create a Visualizer subclass + View subclass, add it to `VisualizerOptions`, and wire all registration points in `mainWindow.py` (`_VIEW_ATTRIBUTE_MAP`, `_build_visualizer_view()`, validation / error messaging, settings extraction, and save/load serialization)
  - Super-sampling: how resolution scaling works
- Create `UI.md`:
  - MainWindow layout: grid structure (general settings, visualizer view, specific settings, preview, render controls)
  - View mapping: `VisualizerOptions` → `_VIEW_ATTRIBUTE_MAP` → view class instantiation
  - Live preview: QTimer debounce (400ms), preview rendering pipeline
  - Settings persistence: `_load_last_settings_if_present()`, `_save_settings_to_path()`, and the explicit save/load project flows
  - Adding a new view: create a View subclass and update the related `MainWindow` registration / serialization branches so the view can be selected, validated, persisted, and restored
- Create `RENDERING.md`:
  - Threading model: dedicated render QThreadPool (max 1 thread) plus QRunnable workers for rendering and update checks
  - Video pipeline: AudioData → frame loop → Visualizer.generate_frame() → av container write
  - Codec options, container format, and optional audio muxing
  - Progress / cancellation UI in `MainWindow`, plus finished-output playback in `RenderDialog`
- Create `TESTING.md`:
  - Current test setup: pytest, `tests/conftest.py` adds `src/` to path
  - Existing tests: `test_app_paths.py`, `test_logging.py`, `test_media_utils.py`
  - Coverage gaps: no visualizer tests, no UI tests, no integration tests
  - Running tests: `pytest tests/ -v`

**Files:**
- `.agents/docs/architecture/development/OVERVIEW.md`
- `.agents/docs/architecture/development/VISUALIZERS.md`
- `.agents/docs/architecture/development/UI.md`
- `.agents/docs/architecture/development/RENDERING.md`
- `.agents/docs/architecture/development/TESTING.md`

**Success criteria:** Development overviews accurately describe how the system works. A developer can use `VISUALIZERS.md` and `UI.md` to add a new visualizer type. All descriptions match actual source code.

### 3.3: Phase 3 Review
Review all new architecture documentation for accuracy.

**Tasks:**
- Cross-reference every class, method, and module name in package docs against `src/`
- Cross-reference development overviews against actual code flow
- Verify all internal links between docs are correct
- Verify `ARCHITECTURE.md` links to the new package and development docs
- Verify zero LSM references in any new files

**Success criteria:** All architecture docs are accurate, cross-linked, and consistent with source code.

---

## Phase 4: Final Review

### 4.1: Full Validation Sweep
Comprehensive review of all `.agents/` documentation.

**Tasks:**
- Search all `.agents/` files for any remaining LSM references: "LSM", "Local Second Mind", "RAG", "ingest" (in LSM context), "query pipeline", "vectordb", "providers" (in LSM context), "lsm."
- Verify both `AGENTS.md` and `CLAUDE.md` (project root) correctly point to `.agents/docs/INDEX.md`
- Read `INDEX.md` and follow all links to verify they resolve correctly
- Spot-check 3-5 class/method references in architecture docs against source code
- Cross-check version, Python requirement, dependencies, and script entry point references against `pyproject.toml`
- Review `COMMIT_MESSAGE.md` and `RELEASE_STATEMENT.md` to confirm template styles are preserved

**Success criteria:** Zero LSM references in any `.agents/` file. All links resolve. All documentation accurately reflects the Audio Visualizer codebase. Template styles for `COMMIT_MESSAGE.md` and `RELEASE_STATEMENT.md` are unchanged.

### 4.2: Final File Inventory
Confirm the expected file structure is in place.

**Tasks:**
- List all files in `.agents/` and verify against expected inventory:
  - `.agents/docs/INDEX.md`
  - `.agents/docs/ARCHITECTURE.md`
  - `.agents/docs/CODING_PATTERNS.md`
  - `.agents/docs/COMMIT_MESSAGE.md`
  - `.agents/docs/CREATE_IMPLEMENTATION_PLAN.md`
  - `.agents/docs/RESEARCH_PLAN.md`
  - `.agents/docs/RELEASE_STATEMENT.md`
  - `.agents/docs/architecture/packages/audio_visualizer.md`
  - `.agents/docs/architecture/packages/audio_visualizer.core.md`
  - `.agents/docs/architecture/packages/audio_visualizer.ui.md`
  - `.agents/docs/architecture/packages/audio_visualizer.ui.views.md`
  - `.agents/docs/architecture/packages/audio_visualizer.visualizers.md`
  - `.agents/docs/architecture/development/OVERVIEW.md`
  - `.agents/docs/architecture/development/VISUALIZERS.md`
  - `.agents/docs/architecture/development/UI.md`
  - `.agents/docs/architecture/development/RENDERING.md`
  - `.agents/docs/architecture/development/TESTING.md`
  - `.agents/docs/plan_phases/` (empty, preserved)
  - `.agents/docs/past_plans/` (empty, preserved)
  - `.agents/future_plans/` (empty, preserved)
- Verify total: 17 documentation files + 3 empty directories

**Success criteria:** File inventory matches expected list exactly. No unexpected files remain. No files are missing.
