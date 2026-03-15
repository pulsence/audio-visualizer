# Stage One: Realign `.agents/` Documentation with Audio Visualizer Codebase

## Problem Statement
The `.agents/` directory currently documents a different project ("Local Second Mind" / LSM — a local-first RAG system).
The actual codebase in `src/` is **Audio Visualizer** — a PySide6 desktop app that generates synchronized audio visualization videos.
Every file in `.agents/` needs to be rewritten or removed to accurately reflect the Audio Visualizer project.

**Total files to address:** 80 files across `.agents/docs/` and `.agents/future_plans/`.

## Scope
- All files within `.agents/` and its subdirectories.
- Reference material: `src/audio_visualizer/` only.
- **Ignore** everything in `Projects to integrate/`.

---

## Phase 1: Audit and Triage

**Goal:** Categorize every file in `.agents/` as **rewrite**, **remove**, or **keep (strip LSM refs only)**.

The full audit has been completed. Results below.

### Files to **rewrite** (replace content with Audio Visualizer equivalents):
| File | Action |
|------|--------|
| `.agents/docs/INDEX.md` | Rewrite — entry point must describe Audio Visualizer |
| `.agents/docs/ARCHITECTURE.md` | Rewrite — must map Audio Visualizer packages |
| `.agents/docs/CODING_PATTERNS.md` | Rewrite — must reflect actual project conventions |
| `.agents/docs/CREATE_IMPLEMENTATION_PLAN.md` | Rewrite — remove LSM-specific paths/commands, adapt references |
| `.agents/docs/RESEARCH_PLAN.md` | Rewrite — remove LSM-specific examples, adapt references |

### Files to **keep with edits** (preserve template style, strip LSM references only):
| File | Action |
|------|--------|
| `.agents/docs/COMMIT_MESSAGE.md` | Keep style — replace "Local Second Mind" and LSM-specific example with Audio Visualizer equivalents |
| `.agents/docs/RELEASE_STATEMENT.md` | Keep style — replace "Local Second Mind" references, LSM-specific config examples, and header with Audio Visualizer equivalents |

### Files to **remove** (entirely LSM-specific, no Audio Visualizer analog):
| File/Directory | Count | Reason |
|----------------|-------|--------|
| `.agents/docs/PLAN.md` | 1 | LSM v0.9.0 UI rework plan |
| `.agents/docs/v_0_9_0_RESEARCH_PLAN.md` | 1 | LSM v0.9.0 research plan |
| `.agents/docs/architecture/packages/lsm.*.md` | 24 | All `lsm.*` package docs |
| `.agents/docs/architecture/development/*.md` | 10 | LSM development overviews (AGENTS, INGEST, MIGRATIONS, MODES, OVERVIEW, PROVIDERS, QUERY, SECURITY, TESTING, TUI_ARCHITECTURE) |
| `.agents/docs/architecture/api-reference/*.md` | 5 | LSM API reference (ADDING_PROVIDERS, CONFIG, PROVIDERS, REMOTE, REPL) |
| `.agents/docs/plan_phases/PHASE_*.md` | 23 | All 23 LSM phase docs — delete files, **keep directory** |
| `.agents/docs/past_plans/*.md` | 8 | LSM historical plans — delete files, **keep directory** |
| `.agents/future_plans/FINANCE_PROVIDERS.md` | 1 | LSM finance providers plan — delete file, **keep directory** |
| `.agents/future_plans/v_0_10_0_RESEARCH_PLAN.md` | 1 | LSM v0.10.0 research — delete file, **keep directory** |
| **Total removals** | **74 files** | Directories `plan_phases/`, `past_plans/`, `future_plans/` are preserved empty for future use |

---

## Phase 2: Remove Irrelevant Files

**Goal:** Clean out all LSM-specific content.

### Tasks
1. Delete all 74 files identified for removal.
2. Remove now-empty subdirectories:
   - `.agents/docs/architecture/packages/`
   - `.agents/docs/architecture/development/`
   - `.agents/docs/architecture/api-reference/`
3. **Keep** these directories (empty, for future use):
   - `.agents/docs/plan_phases/`
   - `.agents/docs/past_plans/`
   - `.agents/future_plans/`
4. Verify `.agents/docs/` contains only the 7 files marked for rewrite/edit, plus the three empty planning directories.

---

## Phase 3: Rewrite Core Documentation

**Goal:** Rewrite the top-level `.agents/docs/` files to accurately document the Audio Visualizer project.

### 3.1 — `INDEX.md`
- Project name: Audio Visualizer
- Purpose: Desktop tool for generating synchronized audio visualization videos
- Tech stack: Python >=3.13, PySide6, librosa, numpy, av (PyAV), Pillow
- Entry point: `python -m audio_visualizer` or `audio-visualizer` (pyproject.toml script)
- High-level architecture overview
- Build notes (PyInstaller support for frozen builds)
- Environment: `AUDIO_VISUALIZER_REPO` env var for update checking

### 3.2 — `ARCHITECTURE.md`
- Package map of `src/audio_visualizer/`:
  - Core modules: `visualizer.py` (app entry), `app_logging.py`, `app_paths.py`, `updater.py`
  - `ui/` — PySide6 UI layer (`mainWindow.py`, `renderDialog.py`, `views/`)
  - `ui/views/` — View hierarchy: `general/`, `volume/`, `chroma/`
  - `visualizers/` — Visualization engine: `volume/`, `chroma/`, `combined/`, `waveform/`
- Key abstractions:
  - `Visualizer` ABC (`genericVisualizer.py`) — abstract base with `prepare_shapes()`, `generate_frame()`
  - `View` base class (`generalView.py`) — abstract base with `validate_view()`, `read_view_values()`
  - `AudioData` — loads audio via librosa, computes frames/volumes/chromagrams
  - `VideoData` — video metadata and container management
  - `VisualizerOptions` enum — 14 visualizer types driving view selection
- Data flow: audio file → librosa analysis → frame generation → av video render
- View-to-Visualizer mapping pattern (`_VIEW_ATTRIBUTE_MAP` in `mainWindow.py`)

### 3.3 — `CODING_PATTERNS.md`
Derive from actual codebase conventions:
- **Module names:** camelCase (`mainWindow.py`, `generalView.py`, `genericVisualizer.py`)
- **Classes:** PascalCase (`MainWindow`, `AudioData`, `GeneralVisualizerView`)
- **Methods/functions:** snake_case (`get_config_dir()`, `load_audio_data()`, `setup_logging()`)
- **Enum values:** UPPER_SNAKE_CASE (`VOLUME_RECTANGLE`, `LEFT_TO_RIGHT`)
- **Architecture pattern:** Visualizer/View separation — each visualizer type has a paired View (UI) and Visualizer (engine) class
- **ABC usage:** `Visualizer` base for all renderers, `View` base for all settings panels
- **Enum-driven config:** `VisualizerOptions` enum maps to views in `_VIEW_ATTRIBUTE_MAP`
- **Qt patterns:** PySide6 signals/slots, QThreadPool for rendering (max 1), QTimer for live preview debounce (400ms)
- **Logging:** `app_logging.setup_logging()` — file-based, INFO level
- **Testing:** pytest, tests in `tests/` directory

### 3.4 — `COMMIT_MESSAGE.md`
- **Keep existing template style** — only replace "Local Second Mind" with "Audio Visualizer" and swap the LSM-specific example for an Audio Visualizer example.

### 3.5 — `CREATE_IMPLEMENTATION_PLAN.md`
- Keep the plan template structure (numbered phases, task blocks, success criteria, code review, testing, release prep)
- Remove all LSM-specific references: `lsm/migration/scripts/`, LSM test commands, LSM paths
- Replace with Audio Visualizer equivalents: `src/audio_visualizer/`, pytest commands, relevant package paths

### 3.6 — `RESEARCH_PLAN.md`
- Keep the research plan methodology (describe realities, ground in codebase, present options)
- Remove LSM-specific examples (pagination, logging systems)
- Replace with Audio Visualizer examples where helpful

### 3.7 — `RELEASE_STATEMENT.md`
- **Keep existing template style** — only replace "Local Second Mind" with "Audio Visualizer" and swap LSM-specific config examples (`llms.tiers`, `global.mcp_servers`, "agent subpackage", "remote provider schemas") with Audio Visualizer equivalents.

---

## Phase 4: Rebuild Architecture Documentation

**Goal:** Create new architecture docs specific to Audio Visualizer under `.agents/docs/architecture/`.

### Tasks
1. Create package documentation under `.agents/docs/architecture/packages/`:
   - `audio_visualizer.md` — Root package overview (version, entry points, dependencies)
   - `audio_visualizer.ui.md` — UI layer (MainWindow, renderDialog, view mapping, threading model)
   - `audio_visualizer.ui.views.md` — View hierarchy (View base, general/, volume/, chroma/ subpackages)
   - `audio_visualizer.visualizers.md` — Visualizer engine (Visualizer ABC, AudioData, VideoData, volume/, chroma/, combined/, waveform/)
   - `audio_visualizer.core.md` — Core utilities (app_logging, app_paths, updater)
2. Create development overviews under `.agents/docs/architecture/development/`:
   - `OVERVIEW.md` — High-level architecture, data flow, component relationships
   - `VISUALIZERS.md` — How visualizers work: ABC pattern, frame generation lifecycle, audio analysis pipeline (librosa → AudioData → frames)
   - `UI.md` — How the UI is structured: view mapping, settings flow, live preview, render dialog
   - `RENDERING.md` — Video rendering pipeline: threading model, av container, super-sampling, codec options
   - `TESTING.md` — Current test coverage (4 test files: app_paths, logging, media_utils), pytest setup, gaps

---

## Phase 5: Validation

**Goal:** Ensure all `.agents/` documentation is accurate and internally consistent.

### Tasks
1. Cross-reference every class/module/function mentioned in docs against `src/`.
2. Verify zero LSM references remain anywhere in `.agents/`.
3. Ensure `INDEX.md` links to all architecture docs correctly.
4. Verify `CLAUDE.md` (root) still correctly points to `.agents/docs/INDEX.md`.
5. Review for completeness — are there important aspects of the codebase not covered?

---

## Success Criteria
- [ ] Zero references to "LSM", "Local Second Mind", "RAG", "ingest", "query pipeline", "vectordb", "providers", "agents" (in LSM context), or other LSM concepts in `.agents/`.
- [ ] Every file in `.agents/` accurately describes the Audio Visualizer codebase as it exists in `src/`.
- [ ] `COMMIT_MESSAGE.md` retains its existing template style.
- [ ] `RELEASE_STATEMENT.md` retains its existing template style.
- [ ] Documentation covers: project overview, architecture, coding patterns, commit style, implementation planning templates, and research plan templates.
- [ ] Architecture docs cover all major packages: core, UI (views), visualizers (volume, chroma, combined, waveform).
- [ ] A developer reading `.agents/docs/INDEX.md` can orient themselves in the Audio Visualizer codebase.
