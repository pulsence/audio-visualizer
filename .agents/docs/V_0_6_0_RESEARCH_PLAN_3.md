# v0.6.0 Stage Three: Tab-Based GUI Layout — Research Plan

> **Prerequisite:** Stage Two (integrating `srt` and `caption` packages into `audio_visualizer`) is **complete**. Both `audio_visualizer.srt` and `audio_visualizer.caption` packages exist in `src/audio_visualizer/` with full APIs, shared event infrastructure (`audio_visualizer.events`), and broad repo coverage across the current `tests/` suite (23 top-level test modules with 325+ tests, plus fixtures and smoke coverage).

## Overview

Stage Three restructures the application's GUI from a single-screen Audio Visualizer layout to a **multi-tab interface** with five tabs:

1. **Audio Visualizer** (default) — the current main screen
2. **SRT Gen** — generate SRT files from audio using `audio_visualizer.srt`
3. **SRT Edit** — view audio waveform alongside SRT timestamps and adjust them
4. **Caption Animate** — generate caption overlay videos from SRT using `audio_visualizer.caption`
5. **Render Composition** — composite background, audio, and outputs from other tabs into a final video

This plan researches each tab's requirements, explores how the current `MainWindow` architecture must change to support tabs, and identifies design options and trade-offs.

As of Stage Two completion, several topic areas remain intentionally open rather than fully decided:

- The SRT Edit waveform stack still needs a repo-local compatibility spike before any dependency/version change is treated as final
- The Render Composition tab still needs an explicit cross-tab asset contract for alpha, duration, FPS, and audio-source behavior

The Phase 3 follow-on considerations have been folded into the relevant sections below rather than treated only as an appendix. In practice, they now shape the SRT Edit waveform decision, Caption Animate preset/resource handling, Render Composition asset contracts, threading/event bridging, testing/tooling, and `SessionContext` design.

---

## 1. Current MainWindow Architecture

### Current state

`MainWindow` (`src/audio_visualizer/ui/mainWindow.py`, 1544 lines) is a `QMainWindow` that uses a single `QGridLayout` as its central widget:

```
Row 0: Heading label
Row 1: Col 0 = GeneralSettingsView | Col 1 = GeneralVisualizerView
Row 2: Col 0 = Preview Panel       | Col 1 = Specific Visualizer View (dynamic)
Row 3: Col 0 = Render Controls     | Col 1 = (render status)
```

Key components tightly coupled to `MainWindow`:
- **View management:** `_VIEW_ATTRIBUTE_MAP`, `__getattr__()` lazy-loading, `_build_visualizer_view()`, `_get_visualizer_view()`, `_show_visualizer_view()`
- **Rendering:** `render_thread_pool` (QThreadPool max 1), `RenderWorker`, `_start_render()`, `_create_visualizer()`, progress/cancel signals
- **Live preview:** `_preview_update_timer` (QTimer 400ms), `_connect_live_preview_updates()`, `_trigger_live_preview_update()`
- **Settings persistence:** `_collect_settings()`, `_apply_settings()`, `save_project()`, `load_project()`, `closeEvent()` auto-save
- **Menu:** `_setup_menu()` — currently only Help > Check for Updates

### Problems and gaps

| Problem | Detail |
|---------|--------|
| Monolithic MainWindow | All logic (view management, rendering, preview, settings, menu) lives in one 1544-line class. Adding 4 new tabs into this class would make it unmanageable. |
| Single-layout assumption | The grid layout is built directly in `__init__()` with hardcoded row/column positions. There is no concept of tabs or switchable content areas. |
| Tightly coupled rendering | `_start_render()`, `_create_visualizer()`, and `RenderWorker` are specific to audio visualizer rendering. SRT generation and caption rendering are fundamentally different operations. |
| Settings format | `_collect_settings()` / `_apply_settings()` serialize only audio visualizer settings. The format must expand to include settings for all tabs. |
| Preview coupling | Live preview is wired to visualizer-specific widgets. Other tabs need different preview mechanisms (waveform display, video preview) or none at all. |

### Design options for tab container

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. QTabWidget** | Replace the grid layout central widget with a `QTabWidget`. Each tab is a `QWidget` with its own layout. | Simple, native Qt tab bar, keyboard navigation built-in, well-understood pattern | Less customizable tab appearance; tabs are strictly full-page |
| **B. QStackedWidget + custom tab bar** | Use a `QStackedWidget` for content with a custom sidebar or toolbar for navigation | Full visual control, can use icon-based navigation, sidebar layout possible | More code to maintain, reimplements standard tab behavior |
| **C. QToolBox** | Collapsible accordion-style sections | Interesting for related sections | Poor fit for independent workflows; confusing UX for 5 full screens |
| **D. QMdiArea** | Multiple document interface with sub-windows | Allows side-by-side comparison | Overwhelming for this use case; unusual for production tools |

#### Deep Dive: QTabWidget vs QStackedWidget + Custom Navigation

**Key architectural note:** `QTabWidget` is internally built from `QTabBar` + `QStackedWidget`. The question is whether to use the pre-packaged combination or decompose and build custom navigation.

| Criterion | QTabWidget | QStackedWidget + Custom Nav |
|-----------|-----------|---------------------------|
| **Setup effort** | Minimal — `addTab()` and go | Moderate — build nav widget, wire signals |
| **Navigation style** | Horizontal/vertical tab bar only | Anything: sidebar, toolbar, ribbon, icon strip, tree view |
| **Scalability (8+ screens)** | Tab bar becomes crowded; relies on scroll buttons or text eliding | Unlimited — sidebar with sections, collapsible groups, search filtering |
| **Icon + label support** | Built-in `setTabIcon()`, `setTabText()` | Full control — arbitrary widget layout per nav item (badges, status dots) |
| **Styling** | Styleable via QSS but constrained by QTabBar's internal paint structure; vertical tabs need subclassing | Full QSS/custom paint control; no fighting with QTabBar internals |
| **Keyboard / Accessibility** | Built-in Ctrl+Tab cycling, ampersand shortcuts, screen reader announces "tab 2 of 5" natively | Must implement shortcuts manually; must set accessible names/roles on custom widgets |
| **Adding a new screen** | One line: `addTab(widget, icon, "Label")` | Add to stack + nav widget + wire connection — more boilerplate but templatable |
| **Screen layout flexibility** | Each page is independent QWidget — identical | Identical |
| **Performance** | Negligible difference for <50 screens | Identical underlying mechanism |

**Production app patterns:**

| Application | Pattern |
|-------------|---------|
| DaVinci Resolve | Bottom toolbar with icon+label buttons — QStackedWidget pattern |
| OBS Studio | Custom toolbar/dock-based navigation |
| VS Code | Sidebar icon strip + activity bar — QStackedWidget pattern |
| VLC Preferences | QStackedWidget + tree navigation |
| KDE Systemsettings | Sidebar with categorized icon grid |

Production desktop apps with many screens almost universally use **QStackedWidget + custom navigation**. `QTabWidget` is typically reserved for sub-dialogs or property panels with 3-5 tabs.

**Long-term recommendation:** `QStackedWidget + custom navigation` scales better and avoids a future migration if the app grows beyond 8 screens. The upfront cost (custom sidebar widget + signal wiring) is modest, and using a `QListWidget` for the sidebar provides keyboard navigation and basic screen reader support out of the box.

**Short-term trade-off:** `QTabWidget` gets you running faster with less code. If the app will stay at 5-7 screens, it is perfectly adequate.

### Design options for MainWindow decomposition

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Tab widgets as separate classes** | Each tab is its own `QWidget` subclass (e.g., `AudioVisualizerTab`, `SrtGenTab`). `MainWindow` becomes a thin shell that holds the `QTabWidget`, menu bar, shared thread pools, and cross-tab coordination. | Clean separation, each tab is testable in isolation, manageable file sizes | Need to define inter-tab communication mechanism |
| **B. Single MainWindow with sections** | Keep everything in `MainWindow`, use methods to build each tab's content | No new files, simpler initial implementation | MainWindow grows to 3000+ lines, increasingly difficult to maintain |
| **C. Plugin/extension architecture** | Each tab registers itself via a plugin registry | Maximum extensibility | Over-engineered for 5 known tabs |

---

## 2. Audio Visualizer Tab (Default)

### Current state

This is the existing application UI. All current `MainWindow` functionality belongs to this tab.

### What must change

The current `MainWindow.__init__()` builds the grid layout directly. This content must be extracted into a dedicated tab widget class. The following elements move into the Audio Visualizer tab:

| Element | Current location | Tab responsibility |
|---------|-----------------|-------------------|
| General settings (audio/video paths, resolution, codec) | `_prepare_general_settings_elements()` at grid (1,0) | Audio file selection shared or duplicated; video output settings tab-specific |
| General visualizer settings (type, position, colors) | `_prepare_general_visualizer_elements()` at grid (1,1) | Fully tab-specific |
| Specific visualizer settings (dynamic views) | `_prepare_specific_visualizer_elements()` at grid (2,1) | Fully tab-specific — all `_VIEW_ATTRIBUTE_MAP` logic, `__getattr__`, lazy loading |
| Preview panel | `_prepare_preview_panel_elements()` at grid (2,0) | Tab-specific preview |
| Render controls | `_prepare_render_elements()` at grid (3,0) | Render button, progress, cancel — pattern reused but implementation is tab-specific |

### Design options for shared vs. tab-specific audio file selection

| Option | Pros | Cons |
|--------|------|------|
| **A. Each tab has its own audio file input** | Tabs are independent, no cross-tab state coupling | User re-enters the same audio path across tabs |
| **B. Shared audio file at MainWindow level** | Single source of truth, consistent across workflow | Not all tabs need audio (Caption Animate needs SRT, not audio directly); adds coupling |
| **C. Shared session context object** | Tabs read from a shared `SessionContext` that holds file paths, settings; tabs subscribe to changes | Clean separation, supports workflow chaining (output of one tab feeds another) | Requires designing a context/state management layer |

---

## 3. SRT Gen Tab

### Purpose

Allow the user to select audio files and generate SRT subtitle files using `audio_visualizer.srt` (the integrated Local SRT package).

### Required functionality (from TODO)

- Select audio file(s) for transcription
- Configure SRT generation settings
- Generate SRT file

### Key integration points with `audio_visualizer.srt`

The integrated `audio_visualizer.srt` package provides these APIs for the SRT Gen tab:

| API Element | Purpose | Tab UI element |
|------------|---------|---------------|
| `load_model(model_name, device, strict_cuda, emitter)` | Load faster-whisper model; returns `(model, device_used, compute_type_used)` | Model selection dropdown, device selector, load status |
| `ModelManager(emitter)` | Thread-safe model caching with `.load()`, `.is_loaded()`, `.unload()` | Model lifecycle management across tab switches |
| `transcribe_file(*, input_path, output_path, fmt, cfg, model, ...)` | Transcribe single file; returns `TranscriptionResult` | Transcribe button, progress display |
| `ResolvedConfig` (with `FormattingConfig`, `TranscriptionConfig`, `SilenceConfig`) | All transcription settings | Settings form fields |
| `PRESETS` dict (`shorts`, `yt`, `podcast`, `transcript`) | Built-in config presets | Preset dropdown |
| `PipelineMode` enum (`GENERAL`, `SHORTS`, `TRANSCRIPT`) | Output mode selection | Mode dropdown |
| `AppEventEmitter` + `EventType.PROGRESS` / `STAGE` / `JOB_START` / `JOB_COMPLETE` | Progress reporting via shared event protocol | Progress bar, status updates |

### Stage Two surface — confirmed API

The integrated package confirms single-file transcription only (no batch API). The full feature surface retained from Stage Two:

| Capability area | Status in `audio_visualizer.srt` | Impact on Stage Three GUI |
|-----------------|----------------------------------|---------------------------|
| Batch transcription | **Not included** — `transcribe_file()` handles one file | GUI is single-file; batch would require tab-level orchestration if desired |
| Output formats | Full set retained: `srt`, `vtt`, `ass`, `txt`, `json` | GUI should expose format dropdown |
| Word-level / Shorts outputs | Retained (`word_level` param, `PipelineMode.SHORTS`, `word_output_path`) | SRT Gen needs paired output path controls |
| Correction and script alignment | Retained (`correction_srt`, `script_path` params) | GUI needs file dialogs for these inputs |
| Prompt / script file loading | Retained (`initial_prompt` param; `scriptReader.py` handles `.docx`) | GUI needs multiline text + file browse |
| Side outputs / diagnostics | Retained (`transcript_path`, `segments_path`, `json_bundle_path`, `keep_wav`, `dry_run`) | Belong in advanced panel |
| Speaker diarization | Retained (`diarize`, `hf_token` params; `pyannote.audio` optional dep) | Advanced panel checkbox + token field |
| Config presets | 4 built-in presets: `shorts`, `yt`, `podcast`, `transcript` | Preset dropdown with `apply_overrides()` |
| Model management | `ModelManager` with thread-safe load/unload/cache | Can share model across transcription jobs |

### Config resources and preset discovery

The integrated SRT package now has two parallel config surfaces:

| Surface | Current behavior | GUI implication |
|--------|------------------|-----------------|
| In-memory presets | `PRESETS` provides 4 built-in preset dicts: `shorts`, `yt`, `podcast`, `transcript` | Best fit for the default preset dropdown |
| Config files | `load_config_file()` resolves an explicit path first, then falls back to `get_data_dir()/srt/configs/` | Advanced users can import JSON configs without relying on cwd |
| Seeded examples | `ensure_example_configs()` (defined in `srt/config.py` but **not exported** from `srt.__init__.py`) writes `podcast_config.json` and `yt_config.json` into the app data dir on demand. It is called internally by `get_srt_config_dir()`. | GUI can offer "Open config folder" / import-from-library affordances later without inventing a new storage scheme; if the GUI needs to trigger seeding directly, it should call `get_srt_config_dir()` or the function should be added to exports |

### `TranscriptionResult` fields

`transcribe_file()` returns a `TranscriptionResult` dataclass. Its fields are relevant for batch orchestration, progress display, and cross-tab data flow (e.g., passing subtitle data to SRT Edit or Caption Animate via `SessionContext`):

| Field | Type | Purpose |
|-------|------|---------|
| `success` | `bool` | Whether transcription succeeded |
| `input_path` | `Path` | Input media file |
| `output_path` | `Path` | Primary output subtitle file |
| `subtitles` | `List[SubtitleBlock]` | Parsed subtitle blocks — can feed SRT Edit directly |
| `segments` | `List[Any]` | Raw Whisper segments with timing |
| `device_used` | `str` | GPU/CPU device actually used |
| `compute_type_used` | `str` | Compute precision (fp16, int8, etc.) |
| `error` | `Optional[str]` | Error message if failed |
| `transcript_path` | `Optional[Path]` | Full text transcript output |
| `segments_path` | `Optional[Path]` | Segments JSON output |
| `json_bundle_path` | `Optional[Path]` | Combined JSON bundle output |
| `elapsed` | `Optional[float]` | Execution time in seconds |

### Settings that need UI controls

From `ResolvedConfig` and `transcribe_file()` parameters:

| Category | Settings | Type |
|----------|---------|------|
| **Model** | `model_name` (tiny/base/small/medium/large), `device` (`auto` / `cpu` / `cuda`), `strict_cuda` | Dropdowns, checkbox |
| **Formatting** | `max_chars`, `max_lines`, `target_cps`, `min_dur`, `max_dur`, `allow_commas`, `allow_medium`, `prefer_punct_splits`, `min_gap`, `pad` | Line edits, checkboxes |
| **Transcription** | `vad_filter`, `condition_on_previous_text`, `no_speech_threshold`, `log_prob_threshold`, `compression_ratio_threshold`, `initial_prompt` | Checkboxes, line edits |
| **Silence** | `silence_min_dur`, `silence_threshold_db` | Line edits |
| **Prompt / alignment inputs** | `initial_prompt`, prompt source (`.txt` / `.docx` mapped into `initial_prompt`), `correction_srt`, `script_path` | Multiline text, file dialogs |
| **Output** | `output_path`, `fmt` (`srt` / `vtt` / `ass` / `txt` / `json`), `word_level`, `mode` (`GENERAL` / `SHORTS` / `TRANSCRIPT`), `language` | File dialog, dropdowns, checkboxes |
| **Side outputs** | `word_output_path`, `transcript_path`, `segments_path`, `json_bundle_path` | File dialogs / optional path fields |
| **Advanced / diagnostics** | `diarize`, `hf_token`, `keep_wav`, `dry_run` | Checkbox, line edit, checkbox, checkbox |

### Design options for settings layout

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. All settings visible** | Single scrollable form with all settings | Everything visible at once, no hidden options | Overwhelming for new users; many settings are rarely changed |
| **B. Basic + Advanced collapsible** | Show common settings (model, output path, format) upfront; collapsible "Advanced" section for formatting/transcription/silence settings | Clean default view, power users can expand | Need to decide what's "basic" vs "advanced" |
| **C. Tabbed sub-sections** | Sub-tabs within the SRT Gen tab for Model, Formatting, Transcription, Output | Organized by category | Nested tabs can be confusing |
| **D. Preset-based with overrides** | Presets (e.g., "General", "Shorts", "Transcript") that set defaults; user can override individual values | Simplifies common workflows | Requires defining and maintaining presets |

### Design options for Stage Three feature surface

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Single-file core UI** | Match the current Stage Two direction: one input file, one primary output, common model/format/mode controls only | Smallest Stage Three surface, easiest to validate | Hides many retained Local SRT capabilities; may feel incomplete next to the integrated package |
| **B. Single-file UI + advanced panel** | Single-file workflow by default, with collapsible advanced controls for correction/script inputs, side outputs, diarization, and diagnostics | Matches the retained feature set without overwhelming default users | More UI complexity; needs careful grouping |
| **C. Reintroduce batch at the GUI layer** | Add multi-file selection and a batch orchestration layer even if Stage Two drops `transcribe_batch()` | Preserves the original TODO language and broader workflow | Adds new orchestration work not covered by the current Stage Two direction |

**Direction chosen:** Stage Three should reintroduce **GUI-level batch orchestration** and expose the **full advanced SRT feature surface**. In practice, SRT Gen should accept multiple input files, queue them through the shared worker model, reuse a loaded `ModelManager` instance across files when possible, and expose advanced controls for correction SRT, script/prompt loading, side outputs, diarization, and diagnostics.

### Threading considerations

Model loading and transcription are long-running operations. The existing `QThreadPool` pattern from `MainWindow` can be reused:

- **Model loading:** `ModelManager.load()` or `load_model()` on a background thread. Emits `EventType.MODEL_LOAD` on completion. `ModelManager` is thread-safe and caches models for reuse.
- **Transcription:** `transcribe_file()` on a background thread. Emits `EventType.STAGE` (4 stages: audio conversion, transcribing, chunking, writing) and `EventType.PROGRESS` with percent data during transcription.
- A Qt worker subscribes to the `AppEventEmitter` and forwards events as Qt signals for progress bar / status updates.
- Cancellation is **not** available at the API boundary — `transcribe_file()` runs synchronously. However, user direction for v0.6.0 is that cancellation is required, so batch orchestration must at minimum stop before the next queued file and the implementation plan must investigate mid-file cancellation via new cooperative hooks or a killable process boundary.

### Design options for model lifecycle

The integrated `ModelManager` class provides thread-safe model caching with `load()`, `is_loaded()`, `model_info()`, and `unload()`. It emits `EventType.MODEL_LOAD` on completion. The question is when to trigger loading:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Load on demand** | Load model when user clicks "Transcribe"; `ModelManager` caches for reuse | No upfront cost, simple | First transcription has noticeable delay |
| **B. Load on tab entry** | Load model when user switches to SRT Gen tab | Ready when user needs it | Wastes resources if user is just browsing tabs |
| **C. Explicit load button** | User clicks "Load Model" separately from "Transcribe" | User controls when the cost is paid; clear feedback via `MODEL_LOAD` event | Extra step in the workflow |

**Current codebase note:** `ModelManager` caches only one loaded model instance at a time. Switching model names unloads the previous model before loading the new one, so the GUI should not imply multi-model residency.

---

## 4. SRT Edit Tab

### Purpose

Display an audio waveform alongside SRT timestamps and allow the user to adjust the timestamps visually.

### Required functionality (from TODO)

- View audio waveform
- View SRT timestamps overlaid on the waveform
- Adjust SRT timestamps (start/end times)
- Undo / redo all editing operations

### Key technical challenges

| Challenge | Detail |
|-----------|--------|
| **Waveform rendering** | Need to render an audio waveform that can be zoomed and scrolled. Qt does not have a built-in waveform widget. |
| **SRT timestamp overlay** | SRT blocks must be displayed as regions on the waveform timeline. Each block needs draggable start/end handles. |
| **Audio playback sync** | User should be able to play audio from a specific timestamp to verify alignment. |
| **Large file handling** | Audio files can be long; waveform must support zooming and scrolling without loading the entire waveform at full resolution. |
| **Undo / redo** | All editing operations (timestamp drags, text edits, block add/remove) must be undoable. Requires a command history that works across both the waveform and table views. |

### Design options for waveform rendering

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Custom QWidget with QPainter** | Draw waveform using `QPainter` on a custom `QWidget`. Pre-compute waveform data at multiple zoom levels using librosa/numpy. | Full control, no extra dependencies, consistent with project's existing Qt approach | Significant implementation effort; scrolling/zooming, hit-testing for drag handles all manual |
| **B. pyqtgraph** | Use `pyqtgraph` for waveform plotting with built-in zoom/pan/scroll | Battle-tested plotting, efficient for large datasets, built-in mouse interaction | New dependency; **not currently in `pyproject.toml`**; styling may not match the rest of the app; requires a repo-local compatibility spike with the current PySide6 / NumPy stack |
| **C. matplotlib embedded in Qt** | Use `matplotlib` with `FigureCanvasQTAgg` for waveform | Well-known library, good plotting | Slow for interactive use (zooming/scrolling), not designed for real-time interaction |
| **D. QGraphicsView/QGraphicsScene** | Use Qt's graphics view framework for the waveform and overlay elements | Built-in support for items, hit-testing, zooming, scrolling | More complex API than QPainter; still need custom waveform item |

### Design options for SRT timestamp editing

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Visual drag on waveform** | SRT blocks rendered as colored rectangles on the waveform. Draggable edges to adjust start/end. | Intuitive, visual | Complex interaction code (hit-testing, snapping, overlaps) |
| **B. Table + waveform** | Split view: waveform display on top, editable table of SRT entries below. Select a row to highlight on waveform; edit times in table. | Easier to implement, precise numeric editing | Less visual, harder to see timing in context |
| **C. Combined** | Both visual drag on waveform AND an editable table synced together | Best of both worlds | Most implementation effort |

#### Deep Dive: pyqtgraph vs Custom QPainter for Waveform

**What pyqtgraph provides out-of-the-box:**

| Feature | pyqtgraph | Custom QPainter effort |
|---------|-----------|----------------------|
| Zoomable/pannable plot area | `PlotWidget` with mouse wheel zoom, right-click drag pan | ~200-300 lines: coordinate transforms, mouse events, scroll bars |
| Waveform rendering | `PlotDataItem` — call `setData(y=samples)` | Build `QPainterPath`, handle repaints, coordinate mapping |
| Draggable SRT regions | `LinearRegionItem` — colored rectangle with draggable edges, emits `sigRegionChanged`, prevents edge crossing | ~300-500 lines: hit-testing, drag tracking, visual feedback, constraints |
| Playback cursor | `InfiniteLine(movable=True)` — 5 lines of code | ~50-100 lines: draw line, click-to-seek, animate during playback |
| Auto downsampling | `PlotItem.setDownsampling(auto=True, mode='peak')` — draws min/max pairs per pixel, preserves waveform envelope | ~200 lines: pre-compute mipmap levels, slice visible range |
| Clip-to-view | `PlotItem.setClipToView(True)` — only renders visible data | Must track visible range and slice arrays manually |
| Axis labels/ticks | Built-in `AxisItem` with auto-scaling | Must implement tick generation, label positioning |

**Performance with large audio files:** A 1-hour file at 44.1kHz mono = ~159 million samples. With `setDownsampling(auto=True, mode='peak')` + `setClipToView(True)`, pyqtgraph only draws ~1000-2000 points regardless of total dataset size. A custom widget needs the same optimization but must implement it from scratch.

**Key risk — PySide6 compatibility:** pyqtgraph has documented compatibility issues with PySide6 6.9.x. The current host app pins `PySide6==6.9.1`, so any pyqtgraph adoption already implies a dependency review in the host repository. The repo-local spike is now complete; the remaining risk is broader application regression after moving the host pin to the validated 6.10.x lane.

**Summary comparison:**

| Dimension | pyqtgraph | Custom QPainter |
|-----------|-----------|----------------|
| Time to working prototype | 2-4 days | 1-2 weeks |
| PySide6 compatibility | **Risk — known issues** | No risk |
| Visual customization | Good but constrained | Complete control |
| Long-term maintenance | Track upstream compat | Maintain own code |
| Additional dependency | ~1.3 MB (numpy already present) | None |
| Code complexity | Less code, but debugging requires understanding pyqtgraph internals | More code, fully transparent |

**External verification note (2026-03-15):** Upstream pyqtgraph issue `#3328`, PR `#3359`, and the `0.14.0` release notes were checked while reviewing this plan. The important conclusion is not a finalized support matrix; it is that the late-2025 compatibility story is nuanced enough that this repo should not encode a permanent version decision from document research alone.

**Conservative compatibility summary:**

| Topic | Current evidence | Impact on Stage Three research |
|-------|------------------|--------------------------------|
| Host repo pin | Audio Visualizer currently pins `PySide6==6.9.1` | Any pyqtgraph adoption implies changing or revalidating the host dependency set |
| PySide6 6.9.1 | Upstream pyqtgraph documents a known breakage | The current repo pin is risky for pyqtgraph as-is |
| PySide6 6.9.2+ / 6.10.x | Upstream fixes landed before and around pyqtgraph `0.14.0`; `6.10.x` is now the preferred lane and the repo-local spike succeeded on `6.10.2` | Treat `6.10.x` as the target family rather than `6.9.1` |
| Python 3.13 | This repo requires Python `>=3.13` | The spike must use the real project interpreter, not only upstream CI assumptions |

**Practical implication after the spike:**
- The research no longer supports staying on `PySide6==6.9.1` for the preferred waveform path
- The next step is host-repo dependency migration plus broader app regression testing, not more waveform-library research

**Current research conclusion:** Upstream pyqtgraph now documents support for Qt 6.8+ / PySide6, and pyqtgraph `0.14.0` shipped after the October 2025 `0.13.7` + PySide6 `6.10.0` segfault report where the reporter noted `master` was already okay. **Inference from upstream sources:** the first concrete pair worth targeting in this repo is **`pyqtgraph==0.14.0` + `PySide6==6.10.2`**.

**Repo-local validation result (2026-03-15):** The target pair was installed into the project `.venv` and exercised with the real project interpreter (`Python 3.13.5`) under `QT_QPA_PLATFORM=offscreen`. Two smoke tests succeeded:
- `PlotWidget` rendering with `setDownsampling(auto=True, mode='peak')`, `setClipToView(True)`, `LinearRegionItem`, and `InfiniteLine` over a 500k-sample waveform
- Coexistence with `QMediaPlayer` / `QAudioOutput` in the same interpreter

No import crash, render failure, or widget-grab failure occurred in the local spike. That does **not** replace broader app regression testing, but it is enough to close the research question and move the plan from "candidate pair" to "accepted target pair."

**Direction chosen:** Move the host repo to **`pyqtgraph==0.14.0` + `PySide6==6.10.2`** for SRT Edit. `PySide6==6.9.1` should no longer be treated as the preferred baseline for the waveform path.

### SRT parsing/writing

The integrated `audio_visualizer.srt` package provides:

- **`SubtitleBlock`** dataclass: `start: float`, `end: float`, `lines: List[str]`, `speaker: Optional[str]`
- **Output writers**: `write_srt()`, `write_vtt()`, `write_ass()`, `write_txt()`, `write_json_bundle()` in `srt.io.outputWriters`
- **Correction parser**: `parse_srt_to_words()` in `srt.core.alignment` — parses SRT into `(normalized, original)` word pairs, designed for correction-alignment workflows

The SRT Edit tab needs to:
1. Parse an existing SRT file into `SubtitleBlock` objects
2. Display them with timing information
3. Allow editing of start/end times and text
4. Write the modified SRT back to file

**Confirmed gap:** The package does **not** expose a general-purpose "load SRT into editable `SubtitleBlock` objects" parser. `parse_srt_to_words()` returns word pairs, not `SubtitleBlock` objects. The `caption` package has `SubtitleFile.load()` (which wraps `pysubs2`), but that returns an `SSAFile`, not `SubtitleBlock` objects. SRT Edit still needs a dedicated parsing solution.

### Design options for editable subtitle parsing / round-tripping

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Add parsing API to `audio_visualizer.srt`** | Stage Two or early Stage Three adds a first-class parser/serializer pair around `SubtitleBlock` | Keeps subtitle logic in one package, reusable by SRT Gen and SRT Edit | Expands Stage Two / shared-package scope |
| **B. Add a Stage Three-local parser/editor model** | SRT Edit owns a small parser that converts `.srt` text into a tab-local editing model, then writes back via local logic or `output_writers.py` | Keeps Stage Two smaller, isolates editing concerns to the tab | Splits subtitle I/O logic across packages |
| **C. Add a third-party parsing dependency** | Use an existing SRT parsing library and map it into `SubtitleBlock` | Fastest path to robust parsing if the dependency is solid | Adds another dependency and another data model to reconcile |

**Direction chosen:** Use **Option B**. SRT Edit should own a tab-local parser/editor model rather than expanding `audio_visualizer.srt` again for editable round-tripping in v0.6.0.

### Design options for audio playback / sync

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Reuse `QMediaPlayer` / `QAudioOutput`** | Follow the current app's preview stack for playback and seeking | Consistent with current dependencies and code patterns | Need to verify seek precision and sync callbacks for editing workflows |
| **B. Custom audio playback via PyAV / numpy** | Decode and drive playback outside Qt Multimedia | Maximum timing control | Large new implementation surface; duplicates media capabilities already in the app |
| **C. Hybrid** | Use Qt Multimedia for playback, but keep waveform timebase and editing overlays fully custom | Lower playback implementation cost while keeping editing UI flexible | Requires careful sync bridging between playback position and custom visuals |

### Undo / Redo

SRT Edit must support undo/redo for all editing operations. This tab extends the generic undo/redo system described in Section 8.5. Without undo, destructive edits to a user's carefully aligned SRT file are too risky.

**SRT Edit undoable operations:**

| Operation | State to capture |
|-----------|-----------------|
| Drag region start/end on waveform | Block index, old start/end, new start/end |
| Edit timestamp in table | Block index, field (start/end), old value, new value |
| Edit subtitle text in table | Block index, old text, new text |
| Add subtitle block | Block index, block data |
| Remove subtitle block | Block index, block data (for restore) |
| Merge / split blocks | Affected block indices and data before/after |

**SRT Edit-specific considerations:**

- Waveform drag operations should push a single `QUndoCommand` on mouse release, not on every intermediate drag position
- Table cell edits should coalesce rapid keystrokes (e.g., via `QUndoCommand.mergeWith()` with a matching `id()`) to avoid one undo step per character
- The undo stack should be per-SRT-file — loading a new SRT file clears the stack

### Subtitle QA / Lint Panel

SRT Edit is the natural home for subtitle QA because it already owns the editable subtitle model, waveform context, and undo/redo system.

**External product precedent:** Subtitle Edit exposes CPS, line-length guidance, spell-check dictionaries, and "Fix common errors" workflows; Aegisub's timing tools likewise treat subtitle cleanup as part of editing rather than as a separate export-time step.

**Recommended rule groups:**

| Group | Checks |
|-------|--------|
| **Readability** | CPS, line length, line count, minimum duration, maximum duration |
| **Timing integrity** | overlaps, negative gaps, flashes, suspiciously short gaps, subtitle blocks with zero or near-zero duration |
| **Text quality** | double spaces, stray punctuation spacing, repeated punctuation, optional spell-check / dictionary warnings |
| **Speaker consistency** | missing or inconsistent speaker prefixes when diarization/speaker labeling is in use |
| **Render safety** | warnings when downstream caption style/layout choices imply likely off-screen or margin-unsafe output |

**Design options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Passive inline warnings** | Show warning icons/colors directly in the table | Lightweight, always visible | Harder to review many issues at once |
| **B. Dedicated QA panel** | Dock/panel listing issues with click-to-jump navigation | Best review workflow, scalable | More UI work |
| **C. Pre-render validation only** | Run checks only before Caption Animate / Composition render | Easy to wire into pipeline | Too late in the workflow; weaker editing UX |

**Recommended direction:** Combine **A + B**. Inline severity hints in the editor plus a dedicated QA panel for bulk review. Keep every automatic fix undoable.

**Baseline thresholds and rule-profile strategy:**

- `audio_visualizer.srt.models.FormattingConfig` already defines the current subtitle heuristics: `max_chars=42`, `max_lines=2`, `target_cps=17.0`, `min_dur=1.0`, `max_dur=6.0`, plus `min_gap=0.08` (minimum inter-subtitle gap), `pad=0.00` (timing padding), `allow_commas=True`, `allow_medium=True`, and `prefer_punct_splits=False`. The lint panel should use these as its default profile so SRT Gen and SRT Edit do not disagree about what "good" timing looks like. In particular, `min_gap` directly informs timing-integrity checks for "suspiciously short gaps" and `min_dur`/`max_dur` set the duration bounds. `ResolvedConfig` also contains `SilenceConfig` (`silence_min_dur=0.2`, `silence_threshold_db=-35.0`), which can inform checks for subtitles that overlap with detected silence regions.
- External accessibility guidance is not perfectly uniform. Section 508 recommends no more than two lines at a time and no more than 45 characters per line, while DCMP emphasizes two-line captions, safe-zone placement, and audience-dependent presentation-rate limits. The app therefore should not hard-code one universal standard.
- v0.6.0 should ship named lint profiles rather than a single fixed rule set. Recommended starting profiles:
  - `pipeline_default` — mirrors the current `ResolvedConfig.formatting` values
  - `accessible_general` — closer to broad accessibility guidance
  - `short_form_social` — more tolerant of fast pacing but stricter about screen safety and line compactness

**Local codebase leverage points:**

| Need | Current hook |
|------|--------------|
| Core readability thresholds | `ResolvedConfig.formatting` stores max chars, max lines, target CPS, min/max duration, min gap, and padding |
| Speaker consistency checks | `SubtitleBlock.speaker` and diarized segment labels already exist (**note:** speaker labels only populated in `PipelineMode.TRANSCRIPT` mode) |
| Timing-integrity checks | Tab-local editable subtitle model plus `FormattingConfig.min_gap` for gap thresholds and `SilenceConfig` for silence-overlap detection |
| Render-safety warnings | Caption preset alignment/margins and composition safe-area assumptions |
| Machine-fixable issues | Shared `QUndoStack` plan lets auto-fixes remain reversible |

### Auto-Resync Toolkit

Auto-resync should sit inside SRT Edit as a set of batch timing tools rather than a separate tab.

**External product precedent:** Subtitle Edit offers "Adjust all times", "Visual sync", "Point sync", and "Change frame rate"; Aegisub's Timing Post-Processor and keyframe snapping show the value of rule-driven timing cleanup after initial sync.

**Recommended operations:**

| Operation | Purpose |
|----------|---------|
| Global shift | Move all subtitles by fixed offset |
| Shift from cursor onward | Fix drift introduced partway through a file |
| Two-point stretch | Fit a subtitle span to two anchor points |
| FPS drift correction | Repair frame-rate-based misalignment |
| Silence snap | Pull subtitle boundaries toward detected silence regions |
| Segment/word reapply | Reconstruct or tighten timings from Whisper segments or word-level outputs when available |

**Design options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Numeric tools only** | Dialogs for offsets, anchor points, and thresholds | Simple, precise | Less discoverable and less confidence-inspiring |
| **B. Wizard + preview diff** | Show before/after timings for selected lines or whole file | Safer, easier to review | More implementation work |
| **C. Fully automatic one-click resync** | "Best effort" retime using silence/word data | Fastest workflow | Harder to trust without explanation |

**Recommended direction:** Start with **B**. Every resync operation should show a preview, be scope-limited (selection vs whole file), and push a single undoable command/macro.

**Implementation substrate from the current codebase:**

| Resync operation | Existing building block |
|-----------------|-------------------------|
| Global shift / two-point stretch / FPS correction | Pure subtitle-model math inside the tab-local editor model |
| Silence snap | `detect_silences()` in `srt.io.audioHelpers` and `apply_silence_alignment()` in `srt.core.subtitleGeneration` already exist — **but neither is exported from `srt.__init__.py`**. SRT Edit must either import them from internal modules directly or Stage Three must add them to the package's public API. |
| Segment/word reapply | `write_json_bundle()` persists segment timing always, and word-level timing **conditionally** (only when segments contain word data, i.e., when `word_level=True` was used during transcription). SRT Gen should surface this dependency clearly so users know resync quality depends on enabling word-level output. |
| Speaker-aware resync boundaries | Diarization labels flow through pipeline segments and into `SubtitleBlock.speaker`, **but only when `mode == PipelineMode.TRANSCRIPT`**. Speaker-aware resync is therefore limited to transcript-mode output; general/shorts-mode transcriptions will not have speaker data. |

**Important integration consequence:** SRT Gen should register its JSON bundle sidecars in `SessionContext` whenever they are generated. That gives SRT Edit a reliable source of richer timing metadata for later resync operations without forcing the editor to rerun transcription. **Note:** word-level timing is only present in JSON bundles when the transcription was run with `word_level=True` (segments must contain word data). The SRT Gen UI should default to enabling word-level output, or at minimum warn users that resync quality is reduced without it.

---

## 5. Caption Animate Tab

### Purpose

Select SRT files and generate caption overlay videos using `audio_visualizer.caption` (the integrated Caption Animator package).

### Required functionality (from TODO)

- Select SRT file(s)
- Configure caption generation settings
- Generate caption overlay video

### Key integration points with `audio_visualizer.caption`

The integrated `audio_visualizer.caption` package provides:

| API Element | Purpose | Tab UI element |
|------------|---------|---------------|
| `render_subtitle(input_path, output_path, config, on_progress, on_event, emitter)` | Main render function; returns `RenderResult` | Render button, progress display |
| `RenderConfig.preset` | Preset name (default: `"modern_box"`) | Preset dropdown |
| `RenderConfig.fps` | Output FPS (default: `"30"`) | FPS input |
| `RenderConfig.quality` | Quality tier: `small` (H.264, default) / `medium` (ProRes 422 HQ) / `large` (ProRes 4444 with alpha) | Quality dropdown |
| `RenderConfig.safety_scale` | Scale factor for sizing (default: `1.12`) | Scale input |
| `RenderConfig.apply_animation` | Whether to animate (default: `True`) | Checkbox |
| `RenderConfig.reskin` | For ASS files: apply preset style (default: `False`) | Checkbox |
| `list_presets()` | List built-in preset names only | Populate the simplest preset dropdown |
| `PresetLoader.list_available()` | Enumerate built-ins plus file-based presets from configured preset dirs | Advanced preset browser / library UI |
| `list_animations()` | List animation types and their defaults | Animation selection UI |
| `PresetConfig` | Full preset data (font, colors, padding, margins, alignment, animation) | Advanced style overrides |
| `PresetLoader(preset_dirs)` | Loads presets from built-ins, files, or custom dirs | Preset resolution |
| `AnimationRegistry.list_types()` | 5 built-in types: `fade`, `slide_up`, `scale_settle`, `blur_settle`, `word_reveal` | Animation type dropdown |
| `AppEventEmitter` + `EventType.STAGE` / `RENDER_START` / `RENDER_PROGRESS` / `RENDER_COMPLETE` | Progress reporting via shared event protocol | Progress bar, status updates |

### `RenderResult` fields

`render_subtitle()` returns a `RenderResult` dataclass. Its fields are relevant for SessionContext asset registration and Render Composition input:

| Field | Type | Purpose |
|-------|------|---------|
| `success` | `bool` | Whether render succeeded |
| `output_path` | `Optional[Path]` | Path to output video |
| `width` | `int` | Output width in pixels |
| `height` | `int` | Output height in pixels |
| `duration_ms` | `int` | Duration in milliseconds |
| `error` | `Optional[str]` | Error message if failed |

### `AnimationConfig` fields

`AnimationConfig` (defined in `caption/core/config.py`) controls animation behavior per preset:

| Field | Type | Purpose |
|-------|------|---------|
| `type` | `str` | Animation type name (e.g., `"fade"`, `"slide_up"`, `"scale_settle"`, `"blur_settle"`, `"word_reveal"`) |
| `params` | `Dict[str, Any]` | Animation-specific parameters (default: empty dict — each animation type has its own `get_default_params()`) |

Includes `from_dict()` and `to_dict()` serialization methods.

### Settings that need UI controls

| Setting | Type | Notes |
|---------|------|-------|
| Input SRT/ASS file path | File dialog | Single file selection |
| Output video path | File dialog | Defaults to `.mov` (transparent) |
| Preset | Dropdown | Load available presets from `PresetLoader` |
| FPS | Line edit / dropdown | Common values: 24, 30, 60 |
| Quality | Dropdown | small, medium, large |
| Safety scale | Line edit | Float, default 1.12 |
| Apply animation | Checkbox | Default True |
| Reskin | Checkbox | Only relevant for ASS input |

### Resolved and remaining gaps

| Topic | Stage Two resolution | Remaining gap |
|-------|---------------------|---------------|
| **Preset discovery** | `PresetLoader` now uses `get_data_dir()/caption/presets/` (not cwd-relative). `ensure_example_presets()` seeds bundled example files (`preset.json`, `word_highlight.json`). 2 built-in presets: `clean_outline`, `modern_box`. `list_presets()` currently reports built-ins only, while `PresetLoader.list_available()` includes file-backed presets. | GUI now needs a single coherent picker/workflow that exposes built-ins, explicit file browse, and the app-data preset library together. |
| **Style surface** | `PresetConfig` is fully exported with `from_dict()`, `to_dict()`, `merge_with()`, `from_json()`, `to_json()`. Contains: font, colors, outline, shadow, blur, line spacing, max width, padding, alignment, margins, wrap style, animation. | The full surface is now in scope; the remaining work is organizing it into a usable UI without overwhelming the tab. |
| **Font determinism** | `PresetConfig.font_file` and `PresetConfig.font_name` are both configurable. Built-in presets use `font_name="Arial"` with empty `font_file`. | No change — built-ins are system-font-dependent. |
| **Cancellation** | **Not resolved.** `render_subtitle()` runs synchronously. `AppEventEmitter.disable()` exists but does not stop in-flight FFmpeg. | Still needs worker-level cancellation design. |
| **Animation system** | `AnimationRegistry` with 5 built-in types (`fade`, `slide_up`, `scale_settle`, `blur_settle`, `word_reveal`). Each has `get_default_params()`. | Animation selection + params should be exposed as part of the now-approved full caption option surface. |
| **Render qualities** | Current code paths are concrete: `small` requests `libx264` + `yuva420p`, `medium` uses `prores_ks` profile 3 (`yuv422p10le`), `large` uses `prores_ks` profile 4 (`yuva444p10le`). | Render Composition still needs to decide which qualities count as reusable overlay intermediates. |

### Design options for preset preview

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. No preview** | User selects preset, renders, checks output | Simplest implementation | Trial-and-error workflow |
| **B. Static text preview** | Render a sample subtitle with the selected preset and display it in the tab | Quick feedback on style choices | Need sample text rendering infrastructure |
| **C. Short video preview** | Render a 2-3 second preview clip when preset changes | Shows animation as well as style | Slower, uses more resources |

### Design options for preset / style exposure

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Preset-only UI** | The tab exposes only built-in preset selection plus `RenderConfig` fields | Smallest UI surface, easiest to support | Hides many current Caption Animator capabilities |
| **B. Preset + common overrides** | Preset dropdown plus a small advanced group for font, colors, padding, and animation toggle | Covers likely real-world customization without a full preset editor | More UI work; must define which overrides are "common" |
| **C. Full preset editor** | Expose most or all `PresetConfig` fields in the GUI | Maximum power, closest to package capability | Largest UI and validation surface |

### Design options for preset source strategy

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Built-in presets only** | GUI lists only packaged built-ins for v0.6.0 | Deterministic, no cwd dependence | Drops file-based preset workflows |
| **B. Built-ins + explicit file browse** | GUI lists built-ins and lets users browse to JSON/YAML preset files | Retains flexibility while removing hidden cwd assumptions | More UI/state handling |
| **C. App-data preset library** | GUI manages editable presets stored under app config/data dirs | Best long-term desktop UX | Requires new preset-management features that do not exist today |

**Direction chosen:** Caption Animate should support **all three** preset-source paths in v0.6.0: built-ins, explicit file browse, and the app-data preset library. It should also expose the **full caption option surface** rather than stopping at preset-only or light-override UI.

### Audio-Reactive Captions

Audio-reactive captions are the most differentiated feature in this plan because they connect Caption Animate to the app's original visualizer identity instead of treating captions as a generic overlay generator.

**External product precedent:** After Effects' "Convert Audio To Keyframes" formalizes the pattern of turning amplitude into animation-driving data. For this project, the opportunity is stronger because audio analysis already exists in the visualizer stack.

**Required integration point:** Caption Animate cannot stay subtitle-only if this feature is included. It needs either:
- a source audio file selected directly in the tab, or
- an audio role provided by `SessionContext`

**Design options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Amplitude-only reactivity** | Drive scale/glow/emphasis from smoothed loudness | Easiest to implement, clear UX | Limited expressive range |
| **B. Amplitude + onset accents** | Add beat/attack-like triggers using simple onset detection | Feels more musical and intentional | More analysis/state complexity |
| **C. Full visualizer bridge** | Reuse richer audio-analysis features (volume + spectral/chroma features) to drive caption styling | Most unique result | Largest coupling and preview complexity |

**Recommended direction:** Start with **B**, designed so it can grow toward **C** later. v0.6.0 should ship a small set of reactive presets like pulse, emphasis, and beat-pop rather than a freeform motion-graph editor.

**Local codebase leverage points:**

- `audio_visualizer.visualizers.utilities.AudioData.analyze_audio()` already computes per-frame average volume (via `np.mean(np.abs(frame))`) and chroma data (via `librosa.feature.chroma_stft()`) per audio frame, storing results in `average_volumes` and `chromagrams` instance attributes.
- The waveform visualizer (`waveformVisualizer.py`) already derives normalized amplitude envelopes from `audio_frames` by computing `max(abs(frame))` per frame and dividing by the global maximum.
- Caption animations accept `params` via `BaseAnimation.__init__(params)` and `generate_ass_override()` accepts an optional `event_context: Optional[Dict[str, Any]]` parameter. **However, the current render pipeline does NOT pass `event_context` into animations.** `SubtitleFile.apply_animation()` calls `animation.apply_to_event(event, size=..., position=...)` — it never passes `event_context` or audio-analysis data. Stage Three must extend the render pipeline to thread audio-reactive analysis data through to `generate_ass_override()` and/or `apply_to_event()` for reactive animations to function.

**Recommended v0.6.0 boundary:**

1. Build a shared audio-analysis bundle for the selected audio source containing at least smoothed amplitude, peak emphasis markers, and optional chroma-energy summaries.
2. Expose a small preset family (`pulse`, `beat_pop`, `emphasis_glow`, etc.) that maps this bundle into bounded ASS-style transforms.
3. Keep text placement stable by default. Reactivity should primarily modulate scale, outline/glow, blur, or word emphasis instead of introducing large positional motion. This aligns better with Section 508 guidance against distracting caption animation.

### Threading considerations

Caption rendering via FFmpeg is a long-running operation. Same QThreadPool pattern applies:
- `render_subtitle()` accepts `emitter` (`AppEventEmitter`) for structured events, plus `on_progress` / `on_event` callbacks
- Events: `STAGE` for pipeline steps, `RENDER_START` / `RENDER_PROGRESS` (throttled ~2Hz with frame/time/speed data) / `RENDER_COMPLETE`
- A Qt worker can subscribe to the emitter and forward events as Qt signals
- Cancellation is **not** available at the API boundary — `render_subtitle()` runs synchronously and FFmpeg subprocess is not exposed. User direction for v0.6.0 is that cancellation is required, so Caption Animate needs a worker strategy that can terminate the render subprocess and stop any queued work cleanly.

---

## 6. Render Composition Tab

### Purpose

Allow the user to load a background video/image, audio, and results from other tabs (e.g., visualizer output, caption overlay), arrange them spatially, and render a final composed video.

### Required functionality (from TODO)

- Load background video/image
- Load audio
- Load results from other tabs (Audio Visualizer output, Caption Animate output)
- Layout the different elements
- Render into a single video file
- Undo / redo all layout and layer editing operations

### Key technical challenges

| Challenge | Detail |
|-----------|--------|
| **Layer compositing** | Must combine multiple video/image layers (background, visualizer overlay, caption overlay) with proper alpha blending and positioning |
| **Layout editor** | Users need to position and size each layer. This requires some form of spatial editor. |
| **Timeline management** | Different layers may have different durations. Need to define how they align temporally. |
| **Video decoding** | Must decode input videos frame-by-frame for compositing. PyAV (already a dependency) can handle this. |
| **Audio handling** | Audio may come from the original audio file or from a video layer. User needs to select the audio source. |
| **Undo / redo** | Layer positioning, add/remove, reordering, and property changes must all be undoable. Extends the generic undo/redo system (Section 8.5). |

**Current codebase context:** Caption Animate already uses an external FFmpeg/libass renderer (`FFmpegRenderer`). Render Composition is therefore no longer choosing in a vacuum; it must either lean further into FFmpeg-based rendering/compositing or intentionally introduce a second rendering stack (for example PyAV/Pillow or PyAV/numpy) alongside the caption renderer.

### Design options for compositing engine

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Frame-by-frame Pillow compositing** | Decode each layer's frames, composite using Pillow's `Image.paste()` / `Image.alpha_composite()`, encode result with PyAV | Consistent with existing tech stack (Pillow already used in visualizers), full control | Potentially slow for high-resolution multi-layer compositing |
| **B. FFmpeg filter_complex** | Use FFmpeg's overlay filter via command-line or PyAV's filter graph API | Hardware-accelerated, battle-tested compositing | Less control over per-frame logic; FFmpeg filter graph API in PyAV is less documented |
| **C. numpy array compositing** | Decode frames to numpy arrays, composite using array operations, encode with PyAV | Fast for numerical operations, already have numpy | Need to handle alpha blending math manually |

**User Feedback:** Option B.

### Design options for layout editor

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Numeric positioning** | Form fields for each layer's x, y, width, height, z-order | Simple to implement, precise values | Hard to visualize the layout |
| **B. Visual canvas** | QGraphicsView-based canvas where users drag/resize layer rectangles | Intuitive, WYSIWYG | Significant implementation effort |
| **C. Preset layouts** | Predefined layouts (e.g., "full-screen background + centered visualizer + bottom caption") | Fastest to implement, covers common cases | Limited flexibility |
| **D. Visual canvas + numeric overrides** | Canvas for rough positioning, form fields for precise values | Best UX | Most implementation effort |

**User Feedback:** Both Option A and C. User set positioning, and can save/load
presets. They should also be able to see a preview of these presets/positioning.

### Design options for layer management

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Fixed layer slots** | Predefined slots: Background, Visualizer, Caption, Audio | Simple, covers the primary workflow | Inflexible if user wants multiple visualizers or captions |
| **B. Dynamic layer list** | User adds/removes/reorders layers freely | Maximum flexibility | More complex UI (layer list, add/remove buttons, reordering) |
| **C. Fixed slots with optional extras** | Background + Audio mandatory; Visualizer and Caption optional with "add another" capability | Balanced approach | Still needs some dynamic UI |

**User Feedback:** Option C.

### Undo / Redo

Render Composition extends the generic undo/redo system described in Section 8.5. Layout editing is inherently trial-and-error; users must be able to undo positioning mistakes without re-adding layers from scratch.

**Render Composition undoable operations:**

| Operation | State to capture |
|-----------|-----------------|
| Move layer (x, y change) | Layer id, old position, new position |
| Resize layer (width, height change) | Layer id, old dimensions, new dimensions |
| Change z-order | Layer id, old z-index, new z-index |
| Add layer | Layer id, layer data |
| Remove layer | Layer id, layer data (for restore) |
| Change layer source file | Layer id, old path, new path |
| Apply/change preset layout | Full layer state snapshot before and after |
| Change audio source | Old source reference, new source reference |

**Render Composition-specific considerations:**

- Applying a preset layout is a compound operation affecting all layers — should use `beginMacro`/`endMacro` to group as a single undo step
- Numeric field edits (x, y, width, height) should coalesce rapid changes using `mergeWith()` so typing "1920" doesn't create four undo entries
- The undo stack should be cleared when a completely new composition is started (all layers removed), but not when individual layers are swapped

### Cross-tab data flow

The Render Composition tab needs to receive outputs from other tabs. This is the strongest argument for a shared session/context object:

| Source Tab | Output | Used by Render Composition |
|-----------|--------|---------------------------|
| Audio Visualizer | Rendered visualizer video (MP4, optionally with audio) | Visualizer layer |
| Caption Animate | Rendered caption overlay video (typically `.mov`; alpha depends on quality/output path choices) | Caption overlay layer |
| SRT Gen | Generated SRT file | Could feed into Caption Animate first |

### Current research gap - cross-tab asset contract

The composition tab is the place where assumptions from the other tabs finally collide. The current plan identifies the need for background/audio/overlay inputs, but it does not yet define the concrete asset contract those tabs must satisfy.

| Asset type | Current producer behavior | Open questions for composition |
|------------|---------------------------|--------------------------------|
| Audio Visualizer output | Current app renders an MP4 visualizer video and can optionally mux AAC audio into it (`Include Audio in Output`) | Should composition treat this as video-only by default, strip/ignore embedded audio unless selected, and what happens if it is shorter than the final composition? |
| Caption Animate output | Quality-dependent output: `small` currently requests H.264 + `yuva420p`, `medium` is ProRes 422 HQ (`yuv422p10le`), `large` is ProRes 4444 (`yuva444p10le`) | Which qualities are acceptable as overlay inputs? Should composition require clearly alpha-capable outputs only, or auto-normalize incoming caption assets first? |
| Background image | Static image loaded by the user | How is duration created: loop to audio length, fixed user length, or final render length? |
| Background video | Arbitrary duration / FPS / codec | Trim, loop, freeze-last-frame, or reject mismatched lengths? |
| Audio source | Standalone audio file or audio extracted from a video layer | Which source is authoritative? Is one source selected or are multiple sources mixed? |

### Design options for composition asset contract

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Restrict inputs to composition-friendly intermediates** | Require known-good inputs, e.g. alpha-capable caption overlays and standard visualizer outputs | Simplest composition logic, easiest to test | Pushes responsibility upstream to other tabs and user choices |
| **B. Auto-transcode incompatible assets** | Composition normalizes incoming assets (codec, alpha, FPS, duration prep) before building the final graph | More forgiving UX | Adds preprocessing time, temp-file management, and more FFmpeg complexity |
| **C. Render some layers directly in composition** | Composition may consume source SRT/audio and generate certain overlays itself instead of always reusing intermediate files | Maximum control over the final graph | Blurs tab boundaries and duplicates work already done in other tabs |

**Direction chosen:** Use a **hybrid of Options B and C**. Render Composition may auto-transcode incompatible intermediates, and it may also render certain overlays directly during composition when that produces a cleaner result. User feedback also expands the keying requirement from a simple luma keyer to **advanced matte control**, so the composition path should plan for keyed overlay workflows with richer control than a single threshold slider.

### Advanced matte control design

Research against FFmpeg's official filter surface suggests the v0.6.0 keyed-overlay UI should expose a concrete advanced matte toolset rather than a vague "keyer" checkbox.

**Recommended v0.6.0 control surface:**

| Group | Controls | FFmpeg-oriented implementation direction |
|------|----------|-------------------------------------------|
| **Key mode** | Mode dropdown: `colorkey`, `chromakey`, `lumakey` | RGB keying, YUV/chroma keying, and luma-only keying cover the common overlay cases |
| **Key target** | Eyedropper/manual key color for color/chroma modes; threshold target for luma mode | `colorkey` / `chromakey` need a key color; `lumakey` is threshold-driven |
| **Core matte** | Similarity / threshold, blend / softness | Maps directly to the official keyer controls exposed by `colorkey`, `chromakey`, and `lumakey` |
| **Matte cleanup** | Erode, dilate/grow, feather/blur | Use alpha-mask cleanup passes after key generation so rough edges can be tightened or softened |
| **Spill suppression** | Enable despill, type/preset, mix, expand, brightness, channel scaling | Backed by FFmpeg's `despill` filter for green/blue spill cleanup |
| **Mask utilities** | Invert matte toggle, alpha-preview mode | Important for debugging and for nonstandard keyed overlays |

**Boundary for v0.6.0:** This is "advanced matte control" for a desktop batch compositor, not a full node-based compositing suite. The scope above is enough to satisfy keyed-overlay workflows without turning Render Composition into a full Resolve/Fusion replacement.

### Design options for timeline authority

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Selected audio source defines final duration** | Final composition length follows the chosen audio track; visual/video layers are trimmed, looped, or frozen to match | Natural fit for the current workflows where audio is central | Requires explicit rules for every non-audio layer |
| **B. Background defines final duration** | Background image/video drives duration; audio/overlays adapt to it | Good for video-first workflows | Less natural for the current short/video workflows described in `TODO` |
| **C. Per-layer start/end controls** | User sets offsets plus trim/loop/freeze behavior per layer | Most flexible | Largest UI and validation surface |

**Direction chosen:** Use **per-layer start/end controls** with looping/trimming/freeze behavior, and define final composition duration as the **maximum layer end time** across enabled assets. Static assets may be stretched across the full composition duration.

---

## 7. Settings Persistence

### Current state

`_collect_settings()` returns a flat dict with keys: `general`, `visualizer`, `specific`, `ui`. `_apply_settings()` restores from this dict. Auto-saved to `last_settings.json` on close.

**Storage location:** `last_settings.json` is stored in the system-appropriate user config directory via `app_paths.get_config_dir()`:
- **Windows:** `%LOCALAPPDATA%/audio_visualizer/last_settings.json`
- **Linux:** `$XDG_CONFIG_HOME/audio_visualizer/last_settings.json` (defaults to `~/.config/audio_visualizer/`)

The expanded multi-tab settings file must continue to use this user config directory — it must **not** be written to the project root or working directory.

### Problems

The current format only supports Audio Visualizer settings. Adding tabs requires expanding the format to include settings for all tabs.

### Design options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Expand existing format** | Add new top-level keys: `srt_gen`, `srt_edit`, `caption_animate`, `render_composition` alongside existing keys. Each tab's widget class implements its own `collect_settings()` / `apply_settings()`. | Backward-compatible (old settings files still load for visualizer tab), simple | Keys accumulate; single large JSON file |
| **B. Per-tab settings files** | Each tab saves/loads its own settings file in the config directory | Independent, no format conflicts | Multiple files to manage; cross-tab settings (like audio file path) duplicated |
| **C. Versioned format with migration** | Add a `version` key to the settings JSON. Migrate old formats on load. | Clean evolution path | Migration code adds complexity |

### Backward compatibility

Existing `last_settings.json` files in the user config directory contain only Audio Visualizer settings. The expanded format should:
1. Read from and write to the user config directory (`get_config_dir()`) — never the project root or working directory
2. Load old files without error (missing tab keys get defaults)
3. Save in the new expanded format going forward
4. Project save/load files (`.json`) should include all tabs

### Workflow Recipes

Workflow Recipes should build on settings persistence, but they should not be treated as just another save of `last_settings.json`.

**External product precedent:** Descript's layout system is the clearest analogue. It allows creators to save reusable scene layouts, decide which layers stay fixed vs become placeholders, and then apply those layouts across projects. That is closer to this app's need than a plain settings snapshot because the reusable value is not only "what were my knobs set to?" but also "which roles need to be filled when I run this workflow again?"

**Design options:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Recipe = settings snapshot** | Save the per-tab settings dict with a name | Easy to implement on top of Section 7 work | Too brittle; encourages machine-local paths and does not express workflow intent |
| **B. Recipe = staged workflow template** | Save enabled stages, per-tab settings, asset-role bindings, export targets, and optional preset/layout references | Captures reusable workflow intent without becoming a full project file | Needs a new schema and "apply recipe" UX |
| **C. Recipe = full project template** | Save recipes plus locked assets and near-complete scene state | Maximum reuse | Overlaps heavily with project save/load and becomes harder to share cleanly |

**Recommended direction:** Use **Option B**. Recipes should be versioned workflow templates, separate from both auto-saved settings and project files.

**Recommended recipe contents:**

- Enabled stages: SRT Gen, SRT Edit QA pass, Caption Animate, Render Composition
- Per-tab settings subsets, excluding ephemeral UI state
- Asset-role expectations such as `primary_audio`, `subtitle_source`, `caption_source`, `background`, `brand_pack`
- Export profile choices and output naming rules
- References to caption presets, composition layouts, and lint profiles

**Storage and portability direction:**

- Store the user recipe library under the app data/config area, not in the repo root
- Support import/export as explicit versioned JSON recipe files (for example, `.avrecipe.json`)
- Prefer asset roles and preset references over absolute file paths
- Allow optional relative-path bindings only for clearly intentional local assets such as repo-managed brand packs or checked-in presets

---

## 8. Threading and Worker Architecture

### Current state

`MainWindow` uses:
- `render_thread_pool` (QThreadPool, max 1) for `RenderWorker` instances
- `_background_thread_pool` for `UpdateCheckWorker`
- `RenderWorker` extends `QRunnable` with Qt signals via a signals object

### New threading needs

| Tab | Long-running operation | Cancelable? | Progress? |
|-----|----------------------|-------------|-----------|
| SRT Gen | Model loading | **No** — `ModelManager.load()` is synchronous, no cancel token | Yes — `EventType.MODEL_LOAD` event |
| SRT Gen | Transcription | **No** — `transcribe_file()` is synchronous, no cancel token | Yes — `EventType.PROGRESS` with percent data, `STAGE` events (4 stages) |
| Caption Animate | Caption rendering | **No** — `render_subtitle()` is synchronous, FFmpeg subprocess not cancellable via API | Yes — `EventType.STAGE`, `RENDER_START`, `RENDER_PROGRESS` (throttled ~2Hz), `RENDER_COMPLETE` |
| Caption Animate | Audio analysis for reactive captions | **No** — `AudioData.analyze_audio()` is synchronous with per-frame librosa chroma computation | No — no event infrastructure exists for analysis progress |
| SRT Edit | Silence detection for resync | **No** — `detect_silences()` shells out to ffmpeg synchronously | No — internal function, no emitter wiring |
| Render Composition | Composition rendering | Depends on engine choice | Yes |

Because both integrated packages already emit `AppEvent` objects through `AppEventEmitter`, Stage Three should standardize a small Qt bridge/adapter layer instead of wiring emitter subscriptions ad hoc in each tab. That bridge becomes the concrete follow-on from Stage Two's shared-service extraction work.

### Tab switching during active work

The shared render pool (max 1 thread) means only one long-running job can run at a time across all tabs. Key UX questions:

| Scenario | Current behavior | Multi-tab question |
|----------|-----------------|-------------------|
| User switches tab while render is in progress | N/A (single screen) | Should progress/cancel controls remain visible? Should they follow the source tab, stay on a persistent status bar, or be accessible from any tab? |
| Render completes while user is on a different tab | `RenderDialog` opens immediately | Should the dialog still open immediately (potentially blocking the wrong tab), be deferred until the user returns to the source tab, or use a notification pattern? |
| User tries to start a second job from another tab | N/A | Should the UI prevent this (disable render buttons on all tabs when pool is busy), queue it, or show an error? |

**Design options for cross-tab progress visibility:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Per-tab progress only** | Each tab shows progress only for its own jobs; switching away hides progress | Simple, no cross-tab UI wiring | User loses visibility into running jobs when they switch tabs |
| **B. Persistent status bar** | MainWindow has a bottom status bar showing active job type, progress, and cancel button | Always visible regardless of active tab; familiar pattern | Additional UI layer outside tabs; needs to handle multiple job types |
| **C. Tab badge / indicator** | The source tab's navigation label shows a spinner or badge while its job runs | User knows which tab has active work; can switch to it for details | Less visible than a status bar; still needs per-tab progress when focused |

### Post-render playback dialog (`RenderDialog`)

`RenderDialog` (`ui/renderDialog.py`) is a modal `QDialog` with `QMediaPlayer`, `QVideoWidget`, `QAudioOutput`, and volume slider. It is currently opened by `MainWindow.render_finished()` after a full render completes. Volume persists across dialog instances via a class variable.

In the tab architecture, each tab that renders output (Audio Visualizer, Caption Animate, Render Composition) may want to show a playback dialog on completion. The dialog should be shared infrastructure — it already takes a generic `VideoData` or output path rather than visualizer-specific data. The implementation plan should decide whether to open it immediately (blocking) or as a notification the user can click through.

### Design options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Shared render thread pool** | All tabs share the existing max-1 `render_thread_pool` | Prevents resource contention, simple | Can only do one operation at a time across all tabs |
| **B. Per-tab thread pools** | Each tab manages its own QThreadPool | Tabs can run operations independently | Resource contention; user might accidentally run expensive operations in parallel |
| **C. Shared pool, per-tab workers** | Shared thread pool but each tab has its own worker class with appropriate signals | Controlled concurrency, tab-specific progress | Need to handle "pool busy" state across tabs |

### Researched cancellation boundary

Both `audio_visualizer.srt` and `audio_visualizer.caption` expose progress via `AppEventEmitter` but have **no cancellation tokens or stop handles**. `AppEventEmitter.disable()` suppresses event emission but does not stop in-flight work. Local code review gives a clearer split:

- **Caption Animate:** true cancellation is feasible **within the current library boundary**. `FFmpegRenderer._render_with_progress()` already uses `subprocess.Popen`; Stage Three can make the render worker cancellable by retaining the child handle and terminating it from the Qt side.
- **SRT Gen:** queue-level cancellation is feasible in-process, but **reliable mid-file hard-stop cancellation is not** with the current synchronous boundaries. Audio conversion uses blocking `subprocess.run()`, silence detection shells out synchronously, diarization is synchronous, and faster-whisper transcription is driven through a blocking iterator. Cooperative checks can improve responsiveness between stages and files, but a truly stoppable transcription job is best implemented behind a **killable subprocess boundary**.

**Prototype result (2026-03-15):** A local parent/child subprocess spike validated the orchestration shape for SRT Gen:
- A queue-based JSONL event relay from child stdout avoided the parent hanging on blocking `readline()`
- A responsive child could soft-cancel, emit a terminal `canceled` event, and self-clean temporary artifacts
- A wedged child required forced termination, and parent-owned work-dir cleanup successfully removed leftover artifacts afterward

This confirms that the right SRT boundary is not "just kill a thread." It is:
- parent-owned temporary workspace
- structured stdout/stderr event relay
- soft-cancel request first
- hard-kill timeout fallback
- parent cleanup after child exit or termination

**Direction chosen:** use a **mixed cancellation strategy**. Caption Animate cancels in-process by terminating FFmpeg; SRT Gen uses cooperative in-process checks for batch orchestration plus subprocess isolation for truly stoppable file-level transcription, with the parent owning temp-dir cleanup and event relay.

---

## 8.5. Generic Undo / Redo System

### Motivation

Multiple tabs require undo/redo support (SRT Edit for timestamp/text editing, Render Composition for layer layout changes). Rather than each tab implementing its own undo infrastructure, the app should provide a generic system that tabs opt into and extend with their own command types.

### Design options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Qt `QUndoStack` + `QUndoCommand` per tab** | Each tab that needs undo owns a `QUndoStack` instance. Tab-specific operations are `QUndoCommand` subclasses. `BaseTab` provides the shared wiring (keyboard shortcuts, menu actions, stack lifecycle). | Built-in Ctrl+Z/Ctrl+Y action creation, `beginMacro`/`endMacro` for compound ops, `setUndoLimit()` for memory control, `createUndoAction()`/`createRedoAction()` for menus, well-documented Qt pattern | Each operation needs its own `QUndoCommand` subclass; commands must fully capture before/after state |
| **B. Custom command stack in BaseTab** | `BaseTab` owns a generic command stack (list of command objects with `execute()`/`undo()` methods). Tabs register command types. | No Qt dependency for the stack; simpler to unit-test without `QApplication` | Reimplements `QUndoStack`; must manually wire shortcuts, action text, and menu integration |
| **C. Per-tab independent implementations** | Each tab builds its own undo system from scratch. | No shared abstractions to design | Duplication, inconsistent behavior, harder to maintain |

**Recommendation:** Option A. `QUndoStack` is purpose-built for this and already part of PySide6. The shared infrastructure lives in `BaseTab`; tabs only need to define their `QUndoCommand` subclasses.

### Architecture sketch

```
BaseTab (abstract)
├── _undo_stack: QUndoStack | None        # None for tabs that don't need undo
├── _init_undo_stack(limit: int) -> None  # Creates stack, wires Ctrl+Z / Ctrl+Y
├── _push_command(cmd: QUndoCommand)      # Pushes to stack; no-op if stack is None
├── _clear_undo_stack() -> None           # Clears history (e.g., on new file load)
├── undo_action() -> QAction | None       # For menu/toolbar integration
├── redo_action() -> QAction | None       # For menu/toolbar integration
│
├── SrtEditTab
│   ├── calls _init_undo_stack(limit=200) in __init__
│   ├── MoveRegionCommand(QUndoCommand)
│   ├── EditTimestampCommand(QUndoCommand)
│   ├── EditTextCommand(QUndoCommand)      # mergeWith() for keystroke coalescing
│   ├── AddBlockCommand(QUndoCommand)
│   ├── RemoveBlockCommand(QUndoCommand)
│   └── SplitMergeCommand(QUndoCommand)    # uses beginMacro/endMacro
│
├── RenderCompositionTab
│   ├── calls _init_undo_stack(limit=100) in __init__
│   ├── MoveLayerCommand(QUndoCommand)
│   ├── ResizeLayerCommand(QUndoCommand)
│   ├── ReorderLayerCommand(QUndoCommand)
│   ├── AddLayerCommand(QUndoCommand)
│   ├── RemoveLayerCommand(QUndoCommand)
│   ├── ChangeSourceCommand(QUndoCommand)
│   └── ApplyPresetCommand(QUndoCommand)   # uses beginMacro/endMacro
│
└── AudioVisualizerTab, SrtGenTab, CaptionAnimateTab
    └── do NOT call _init_undo_stack() — no undo needed
```

### MainWindow integration

When the active tab changes, `MainWindow` should update the Edit menu's Undo/Redo actions to point at the current tab's `QUndoStack`:

- If the active tab has an undo stack → bind Edit > Undo / Redo to that stack's actions
- If the active tab has no undo stack → disable/hide Edit > Undo / Redo

This is straightforward with `QUndoStack.createUndoAction()` / `createRedoAction()`, which automatically update their text (e.g., "Undo Move Region") and enabled state.

### Shared `QUndoCommand` patterns

Tabs will share common patterns that can be templated or base-classed:

| Pattern | Where used | Implementation |
|---------|-----------|---------------|
| **Keystroke coalescing** | SRT Edit text edits, Render Composition numeric fields | Override `id()` to return a stable int per field; override `mergeWith()` to update `new_value` while keeping `old_value` from the first command |
| **Compound operations** | SRT Edit split/merge, Render Composition apply-preset | Wrap in `stack.beginMacro("description")` / `stack.endMacro()` |
| **Drag completion** | SRT Edit region drag, Render Composition layer move | Push command on mouse release only, capturing start-of-drag vs end-of-drag state |

### Key design decisions

- **Per-tab stacks, not a single global stack.** Undo in SRT Edit should not undo a layer move in Render Composition. Each tab's history is independent.
- **Opt-in, not mandatory.** Tabs that don't need undo (Audio Visualizer, SRT Gen, Caption Animate) simply don't call `_init_undo_stack()`.
- **Stack cleared on context change.** SRT Edit clears its stack when a new SRT file is loaded. Render Composition clears its stack when a new composition is started.
- **Configurable history limit.** `setUndoLimit()` prevents unbounded memory growth. Reasonable defaults: 200 for SRT Edit (many small edits), 100 for Render Composition (fewer, larger operations).

---

## 9. Testing Considerations

### Existing test state

From `tests/`: 23 top-level test modules with 325+ tests, plus `conftest.py` fixtures. Coverage includes:
- **Core:** `test_app_paths.py`, `test_logging.py`, `test_media_utils.py`
- **Events:** `test_events.py`
- **SRT package:** `test_srt_models.py`, `test_srt_config.py`, `test_srt_text_processing.py`, `test_srt_subtitle_generation.py`, `test_srt_alignment.py`, `test_srt_output_writers.py`, `test_srt_events.py`, `test_srt_format_helpers.py`, `test_srt_audio.py`, `test_srt_system.py`, `test_srt_script_reader.py`, `test_srt_smoke.py`
- **Caption package:** `test_caption_measurement.py`, `test_caption_presets.py`, `test_caption_sizing.py`, `test_caption_smoke.py`, `test_caption_word_reveal.py`, `test_caption_wrapper.py`
- **Integration:** `test_integration_smoke.py`

No UI tests exist.

### New testing needs

| Area | Test type | Notes |
|------|----------|-------|
| Tab widget creation | Unit | Verify each tab class instantiates without errors |
| Settings serialization | Unit | Each tab's `collect_settings()` / `apply_settings()` round-trips correctly |
| Settings backward compat | Unit | Old format `last_settings.json` loads without error |
| Workflow recipe round-trip / apply | Unit + integration | Recipe schema versioning, role resolution, defaults, and "apply recipe" behavior must be stable |
| Cross-tab data flow | Integration | Output of one tab can be loaded by Render Composition |
| Worker classes | Unit | Each worker type emits correct signals |
| SRT parsing/editing | Unit | SRT Edit tab correctly modifies timestamps |
| Subtitle QA / lint rules | Unit | Rule severity, profile overrides, machine-fix actions, and jump-to-issue behavior need coverage |
| Auto-resync operations | Unit + integration | Preview diff generation, selection scoping, silence snap, and word-data reapply should all be tested |
| Audio-analysis bundle / cache | Unit | Shared analysis results must be deterministic for the same source + settings |
| Audio-reactive caption mapping | Unit + integration | Reactive presets should map analysis data into expected animation parameters and render without regressions |
| Undo/redo commands | Unit | Each `QUndoCommand` subclass correctly applies and reverts state; `mergeWith()` coalescing works; macro grouping produces single undo steps |
| Undo stack lifecycle | Unit | Stack clears on new file/composition; history limit is respected; undo/redo actions enable/disable correctly |

### Testing challenges

- UI tests with PySide6 require either `pytest-qt` or manual `QApplication` management
- Waveform rendering tests would need sample audio fixtures
- Caption rendering tests would need FFmpeg available in CI
- Audio-reactive caption tests need deterministic audio fixtures and stable analysis tolerances so small DSP differences do not cause flaky failures
- Current `pyproject.toml` dev extras include `pytest` and `pytest-mock`, but not `pytest-qt`, so Stage Three UI testing adds a tooling/dependency decision as well as test code

---

## 10. MainWindow Code Review and Refactoring Analysis

A detailed code review of `mainWindow.py` (1544 lines) identified the following refactoring needs for tab decomposition.

### Code smells identified

| Smell | Location | Impact |
|-------|----------|--------|
| Magic `__getattr__` for lazy view loading | Lines 165-170 | No IDE autocomplete, runtime errors, side-effect-laden attribute access |
| 14-branch `if` chain in `_build_visualizer_view()` | Lines 173-216 | 14 standalone `if` statements (not `elif`); must edit MainWindow to add any new visualizer; not extensible |
| 214-line `_create_visualizer()` factory | Lines 360-573 | 14 near-identical branches; violates Single Responsibility |
| 170-line `_collect_settings()` | Lines 828-998 | 14-way branching, identical serialization pattern repeated |
| 248-line `_apply_settings()` | Lines 1000-1248 | 14-way branching, identical deserialization pattern repeated |
| Direct widget access across class boundaries | Lines 1007-1028 | `self.generalSettingsView.audio_file_path.setText(...)` — breaks if view refactors internals |
| Global `findChildren()` for control disabling | Lines 709-716 | Slow, fragile, special-cases cancel button |
| Scattered preview state | Lines 116-123, 260-262, 799-823 | Related state spread across 5+ locations |

### Refactoring plan for tab decomposition

**What moves where:**

| Component | Current (MainWindow lines) | Target | Reason |
|-----------|---------------------------|--------|--------|
| `_create_visualizer()` | 360-573 (214 lines) | Each tab's `create_visualizer()` method | Visualizer-specific |
| `_build_visualizer_view()` | 172-215 | Factory registry or each tab | Remove branching |
| `_collect_settings()` | 828-998 (170 lines) | BaseTab + tab-specific `get_specific_settings_dict()` | Reduce duplication |
| `_apply_settings()` | 1000-1248 (248 lines) | BaseTab + View `apply_settings()` methods | Reduce duplication |
| `__getattr__` + `_VIEW_ATTRIBUTE_MAP` | 64-79, 165-170 | DELETE | Replace with explicit tab views |
| Render control methods | 575-707 | BaseTab | Shared pattern |
| Preview methods | 799-823 | PreviewManager or BaseTab | Group related state |
| Worker creation | 640-653 | BaseTab helper `_start_render_worker()` | Reusable pattern |
| Thread pools | 113-124 | MainWindow (shared, injected into tabs) | Shared resource |
| Menu setup | 312-319 | MainWindow (thin shell) | Top-level UI |

**Thin MainWindow shell after decomposition (~80 lines):**
- Holds `QTabWidget` or `QStackedWidget` + navigation
- Owns shared resources: `render_thread_pool`, `_background_thread_pool`, `SessionContext`
- Manages settings persistence at app level (`closeEvent` auto-save, startup auto-load)
- Manages Edit menu Undo/Redo actions, switching to the active tab's `QUndoStack` on tab change (see Section 8.5)
- Delegates all tab-specific logic to tab classes

**View class improvements needed:**
- Each View subclass should add `apply_settings(data: dict)` method (counterpart to existing `read_view_values()`)
- `GeneralSettingsView` and `GeneralVisualizerView` should expose setter methods instead of allowing direct widget access

**Standardized patterns for all tabs:**
- Worker creation: `BaseTab._start_render_worker(worker, callbacks)`
- Progress reporting: consistent signal interface across all worker types
- Validation: each tab implements `validate_settings() -> (bool, str)`
- Settings: each tab implements `collect_settings() -> dict` and `apply_settings(dict)`
- Undo/redo: opt-in via `BaseTab._init_undo_stack(limit)` — see Section 8.5
- Control disabling: each tab registers its editable controls explicitly

---

## 11. Global File Provider / Session Context

### Purpose

Per user decision, a global file provider should make all audio/video/graphics/SRT files commonly accessible to all screens. This combines shared state at the MainWindow level (Option B) with a structured session context (Option C).

### Design sketch

```
SessionAsset:
    - id: str
    - path: Path
    - category: str                  # audio, subtitle, video, image, config
    - source_tab: str | None
    - width: int | None
    - height: int | None
    - fps: float | None
    - duration_ms: int | None
    - has_alpha: bool | None
    - has_audio: bool | None
    - metadata: dict[str, object]

SessionContext:
    - assets: list[SessionAsset]
    - add_asset(asset: SessionAsset)
    - remove_asset(asset_id: str)
    - find_assets(category: str | None = None, source_tab: str | None = None)
    - signals:
        - asset_added(asset: SessionAsset)
        - asset_updated(asset: SessionAsset)
        - asset_removed(asset_id: str)
```

Tabs register outputs (e.g., Audio Visualizer adds its rendered MP4 plus metadata, SRT Gen adds its generated SRT, Caption Animate adds its rendered MOV and alpha/duration/fps metadata) and other tabs can browse/select from the pool. File pickers in each tab should show both the global pool and allow browsing the filesystem.

### Key considerations

- SessionContext should be owned by MainWindow and injected into each tab
- File entries should track their source (which tab produced them) for clarity
- Render Composition should consume asset metadata from SessionContext rather than probing every file lazily at selection time
- The asset metadata is the natural place to encode the cross-tab contract for alpha support, duration, FPS, and embedded-audio behavior
- The global pool supplements but does not replace per-tab file selection — users can always browse the filesystem directly
- SessionContext state should be included in project save/load
- Recipe application should resolve named asset roles through `SessionContext` first before falling back to filesystem prompts
- Generated sidecars such as SRT JSON bundles should be registered as first-class session assets so SRT Edit can reuse segment/word timing data for resync work
- SessionContext should grow a lightweight derived-analysis cache keyed by source asset + analysis settings so waveform data, silence intervals, and audio-reactive caption analysis are not recomputed independently in every tab

---

## 12. Implementation Sequencing

> Note: Section numbers below refer to research plan sections, not implementation order.

```
Stage Two (srt + caption packages)  ✅ COMPLETE
        │
        ▼
Section 1 (MainWindow container refactor)      ← Foundation for all tabs
        │
        ├──▶ Section 2 (Audio Visualizer Tab)  ← Extract existing UI into tab class
        │           │
        │           ▼
        ├──▶ Section 3 (SRT Gen Tab)           ← Depends on audio_visualizer.srt package
        │           │
        │           ▼
        ├──▶ Section 5 (Caption Animate Tab)   ← Depends on audio_visualizer.caption package
        │
        ├──▶ Section 4 (SRT Edit Tab)          ← Depends on subtitle round-trip decision and waveform stack spike
        │
        └──▶ Section 6 (Render Composition Tab) ← Depends on outputs from other tabs and an explicit asset contract
                                                   Should be implemented last

Section 7 (Settings persistence) — Evolves alongside each tab
Section 8 (Threading) — Foundation established with tab refactor, extended per tab
```

**Critical path:** MainWindow refactor → Audio Visualizer Tab extraction → remaining tabs

**Parallelizable:** SRT Gen, SRT Edit, and Caption Animate tabs can be developed in parallel after the MainWindow refactor and Audio Visualizer extraction are complete.

**Cross-cutting feature layering after the core tabs:**

- **Subtitle QA / Lint Panel** should land after the SRT Edit parser/editor model exists, because it depends on a stable editable subtitle source of truth.
- **Auto-Resync Toolkit** should follow the first playable waveform/editor milestone and the `SessionContext` asset registration work for JSON bundles.
- **Workflow Recipes** should land only after per-tab settings schemas and `SessionContext` asset roles are stable enough to avoid immediate migration churn.
- **Audio-Reactive Captions** should land after Caption Animate's full preset surface is exposed and the shared audio-analysis cache shape is defined.

---

## 13. Risk Areas

| Risk | Mitigation |
|------|-----------|
| MainWindow refactor breaks existing functionality | Extract Audio Visualizer tab first; verify all existing features work before adding new tabs |
| Waveform rendering performance for large audio files | Use downsampled waveform data at multiple zoom levels; render only visible portion |
| Editable SRT round-tripping is not yet implemented | Build and round-trip test the chosen tab-local parser/editor model before wiring the full SRT Edit UI |
| SRT Edit interaction complexity (drag handles, snapping) | Phase 1: table + waveform display; Phase 2: draggable handles |
| FFmpeg filter_complex API surface in PyAV | Spike test the overlay filter with representative inputs early |
| Cross-tab asset contract is still open | Define alpha/FPS/duration/audio rules before committing to a composition backend |
| Caption preset discovery | `PresetLoader` now uses `get_data_dir()/caption/presets/` — no cwd dependency. Only 2 built-in presets (`clean_outline`, `modern_box`); may need more for v0.6.0 UX. |
| Long-running job cancellation confirmed absent | Both `srt` and `caption` packages run synchronously with no cancel tokens, but cancellation is now a v0.6.0 requirement. Research is complete: use in-process FFmpeg termination for Caption Animate and subprocess isolation plus parent-owned cleanup/event relay for truly stoppable SRT Gen jobs. |
| SessionContext complexity | Start with a minimal asset registry plus only the metadata Composition actually needs (path, source tab, duration/FPS, alpha/audio flags) |
| Cross-tab progress/cancel UX during renders | Shared pool (max 1 thread) means only one job at a time. The plan must decide how progress, cancel, and post-render dialogs behave when the user switches away from the source tab. See Section 8 tab-switching analysis. |
| Settings format migration | Load old files with silent defaults; save in new format going forward |
| pyqtgraph + PySide6 compatibility | Repo-local offscreen spike succeeded on `pyqtgraph==0.14.0` + `PySide6==6.10.2` with Python 3.13.5; the remaining risk is broader app regression after the host dependency pin change, not basic compatibility |
| SRT Edit round-trip parser gap | `audio_visualizer.srt` has no general-purpose "load SRT → `SubtitleBlock` list" parser. `caption` package has `SubtitleFile.load()` wrapping `pysubs2`, but returns `SSAFile`, not `SubtitleBlock`. The chosen tab-local parser/editor model still needs to be implemented and round-trip tested. |
| Subtitle QA false positives / conflicting standards | Use named lint profiles seeded from `ResolvedConfig.formatting`, keep thresholds editable, and separate warnings from hard errors |
| Workflow recipes accidentally capture machine-local state | Keep recipe schema distinct from project/session saves and prefer asset-role placeholders over absolute paths |
| Audio-reactive captions hurt readability or accessibility | Keep motion bounded, preserve stable placement by default, and provide a non-reactive fallback preset path |
| Shared analysis cache invalidation | Key cache entries by asset fingerprint/path + relevant analysis parameters; invalidate on source change or recipe rebind |
| Bulk resync operations become destructive | Require preview + scope selection, and apply each batch change as a single undoable macro |
| Auto-resync helpers are internal-only | `detect_silences()` and `apply_silence_alignment()` are not exported from `srt.__init__.py`. Stage Three must either add them to the public API or accept direct internal-module imports in SRT Edit. |
| Audio-reactive caption pipeline wiring gap | `BaseAnimation.generate_ass_override(event_context)` exists but `SubtitleFile.apply_animation()` never passes `event_context`. The render pipeline must be extended to thread audio-analysis data through to animations. |
| Audio analysis for reactive captions has no progress reporting | `AudioData.analyze_audio()` is synchronous with per-frame librosa chroma computation and no emitter wiring. Long audio files could cause UI freezes if not run on a background thread with progress feedback. |
| Speaker-aware resync limited to TRANSCRIPT mode | Diarization only runs when `mode == PipelineMode.TRANSCRIPT`. Speaker labels are absent from general/shorts-mode transcriptions, limiting speaker-aware resync applicability. |
| Word-level resync data depends on transcription settings | JSON bundles only include word timing when `word_level=True` was used. Resync quality degrades without it, and users may not realize this dependency. |

---

## 14. Decisions Made

| Topic | Decision |
|-------|---------|
| Tab container | QStackedWidget + custom navigation (Option B from Section 1) |
| SRT Edit scope | Full implementation: table + waveform + draggable handles. Phased in implementation plan. |
| Render Composition scope | Preset-based composition with preview. Numeric positioning + save/load presets. |
| Layout editor | Numeric positioning + preset layouts (Options A + C from Section 6) with preview |
| Layer management | Fixed slots with optional extras (Option C from Section 6) |
| MainWindow decomposition | Separate class files per tab (Option A from Section 1). See code review in Section 10. |
| Shared file access | Global file provider / `SessionContext` accessible to all tabs (Options B + C from Section 2). See Section 11. |
| Threading model | Shared render thread pool, max 1 (Option A from Section 8) |
| Settings backward compat | Load old format with silent defaults, save in new expanded format |
| Cross-tab workflow | File pickers that can browse both `SessionContext` pool and filesystem |
| Research timing | Stage Two is complete. This research plan has been updated to reflect the actual `audio_visualizer.srt` and `audio_visualizer.caption` APIs. |
| Undo/redo system | Generic `QUndoStack`-based system in `BaseTab` (Option A from Section 8.5). Per-tab stacks, opt-in. Used by SRT Edit and Render Composition. |
| SRT Gen scope | Reintroduce GUI-level batch transcription orchestration over the single-file `transcribe_file()` API |
| SRT Gen feature exposure | Expose the full advanced SRT feature surface in v0.6.0 |
| SRT Edit parser model | Use a Stage Three-local parser/editor model (Option B from Section 4) |
| Waveform stack direction | Use `pyqtgraph==0.14.0` with `PySide6==6.10.2`; repo-local spike passed in the project `.venv` on Python 3.13.5 |
| Caption preset scope | Support built-ins, explicit preset files, the app-data preset library, and the full caption option surface |
| Cancellation requirement | Cancellation is required for SRT Gen and Caption Animate in v0.6.0; non-cancelable UX is rejected |
| Cancellation boundary | Caption Animate cancels in-process by terminating FFmpeg; SRT Gen uses cooperative checks plus subprocess isolation for truly stoppable per-file work, with parent-owned temp-dir cleanup and JSONL event relay |
| Composition asset strategy | Hybrid of auto-transcode plus direct-in-composition overlay rendering, with advanced matte/key control support |
| Composition timeline | Per-layer start/end controls with looping/trimming rules and final duration defined by the maximum enabled layer end time |
| Workflow recipe artifact | Add separate versioned workflow-recipe files with asset-role bindings; do not collapse them into project files or `last_settings.json` |
| Subtitle QA strategy | Use SRT Edit inline warnings + a QA panel, with named lint profiles seeded from `ResolvedConfig.formatting` |
| Auto-resync scope | Ship previewable batch timing tools in SRT Edit, reusing silence detection and JSON-bundle timing data when available |
| Audio-reactive caption scope | Ship a bounded preset-based system powered by shared audio analysis, not a freeform node/graph editor |

---

## 15. Clarifications Resolved

1. **SRT Edit complexity:** Full implementation (table + draggable handles), broken into two phases during implementation.
2. **Render Composition complexity:** Preset-based with numeric positioning overrides and preview capability.
3. **Compositing engine direction:** User preference currently favors FFmpeg `filter_complex`, but additional asset-contract research is still required before treating that as final.
4. **Layout editor:** Numeric positioning + saveable/loadable presets with preview.
5. **Layer management:** Fixed slots (Background, Audio) with optional extras (Visualizer, Caption with "add another").
6. **MainWindow decomposition:** Separate files. Code review completed — see Section 10.
7. **Shared audio file:** Global file provider / `SessionContext` for all file types across all tabs.
8. **Threading model:** Shared pool (Option A) to start.
9. **Settings backward compat:** Silent defaults, save in new format.
10. **Cross-tab workflow:** File pickers with `SessionContext` integration.
11. **Stage Two status:** Complete. Plan updated with actual API surface, confirmed gaps, and resolved assumptions.
12. **Tab container:** QStackedWidget + custom navigation.
13. **SRT Gen scope:** Reintroduce batch at the GUI layer even though the integrated core API remains single-file.
14. **SRT Gen feature exposure:** Full advanced SRT feature set should be exposed.
15. **SRT Edit parser model:** Use a tab-local parser/editor model.
16. **Waveform direction:** Use `pyqtgraph==0.14.0` with `PySide6==6.10.2`; the repo-local spike passed in the project `.venv`.
17. **Caption preset scope:** Support built-ins, external files, app-data preset library access, and the full caption option surface.
18. **Cancellation requirement:** Required for both SRT Gen and Caption Animate.
19. **Cancellation boundary:** Caption Animate should cancel in-process by terminating FFmpeg; SRT Gen should use cooperative checks plus subprocess isolation for truly stoppable per-file work, with parent-owned cleanup and JSONL event relay.
20. **Composition asset handling:** Hybrid of auto-transcode and direct-in-composition overlay generation, plus advanced matte/key controls.
21. **Composition timeline:** Final duration comes from the maximum layer end time; layers may start/stop independently and loop/trim as needed.
22. **Workflow recipe model:** Use separate versioned workflow recipes with asset roles instead of conflating them with project saves.
23. **Subtitle QA model:** Use named lint profiles seeded from the SRT pipeline defaults plus inline/panel review UX.
24. **Auto-resync model:** Keep resync inside SRT Edit with previewable, undoable batch operations.
25. **Audio-reactive caption model:** Keep reactivity preset-based and driven by shared audio analysis with bounded motion.

---

## 16. Technical Validation Results

All previously listed validation items have now been researched and reduced to concrete implementation guidance.

1. **Waveform acceptance spike:** Completed. `pyqtgraph==0.14.0` + `PySide6==6.10.2` worked in the project `.venv` (`Python 3.13.5`) with offscreen `PlotWidget` rendering, `LinearRegionItem`, `InfiniteLine`, downsampling, clip-to-view, and a QtMultimedia coexistence smoke test.
2. **SRT Gen subprocess orchestration:** Completed. The right wrapper shape is a child transcription process with JSONL event streaming, parent-owned temp workspace, cooperative cancel request, hard-kill timeout fallback, and parent cleanup after exit/termination.
3. **Advanced matte control design:** Completed. v0.6.0 should expose key mode (`colorkey` / `chromakey` / `lumakey`), key target, similarity/threshold, blend/softness, matte cleanup (erode/dilate/feather), despill controls, invert, and alpha-preview/debug views.

Stage Two is complete. This plan now reflects the current `audio_visualizer.srt` and `audio_visualizer.caption` APIs plus the completed validation research. Key findings: Stage Three now deliberately expands beyond the current single-file SRT API at the GUI layer, the preferred waveform lane is the repo-validated `pyqtgraph==0.14.0` + `PySide6==6.10.2` pair, cancellation is a hard requirement with a validated mixed implementation boundary, and Render Composition needs metadata-rich assets plus explicit timing and advanced matte/key rules.

---

## 17. Additional Major-Release Features

These features are no longer treated as a detached appendix. They are integrated into the main implementation sections above:

- **Workflow Recipes:** Sections 7, 11, 12, 13, and 14
- **Subtitle QA / Lint Panel:** Sections 4, 9, 12, 13, and 14
- **Auto-Resync Toolkit:** Sections 4, 9, 11, 12, 13, and 14
- **Audio-Reactive Captions:** Sections 5, 9, 11, 12, 13, and 14

**Research grounding used for this integration (reviewed 2026-03-15):**

- Subtitle Edit docs: visual sync, point sync, change frame rate, max CPS, and fix-common-error workflows
- Aegisub manual: timing post-processor, keyframe snapping, and timing tools
- Section 508 and DCMP caption guidance: screen-safety, line-count, line-length, and readability expectations
- Descript help: reusable layouts, placeholders, and cross-project caption/layout reuse
- Adobe After Effects help: converting audio amplitude into animation-driving keyframes
- DaVinci Resolve 20 new-features guide: AI animated subtitles and beat detector direction

### Workflow Recipes

**Purpose:** Let users save and reuse an end-to-end production workflow rather than only isolated tab settings.

**External precedent and why it matters:**

- Descript lets users save layouts, turn layers into placeholders, and reapply those layouts across projects. That reinforces the idea that reusable creative workflows need placeholders/roles, not just a dump of current settings.

**What it would include:**
- SRT Gen settings, model choice, formatting preset, and output rules
- Caption Animate preset/style configuration and render quality
- Render Composition layout, layer bindings, timing rules, and export target
- Optional asset-role bindings such as "main audio", "caption source", "background", and "brand package"

**Why it fits this release:**
- It extends the already-researched multi-tab settings persistence and `SessionContext` work
- It turns the app from a collection of tools into a repeatable production pipeline
- It is especially valuable for Shorts, Reels, and recurring channel formats

**Integration points:** Section 7 defines the schema/storage boundary, Section 11 covers asset-role resolution through `SessionContext`, and Section 12 places recipes after tab settings stabilize.

**Design direction:** Treat recipes as a higher-level artifact than project save files. A project captures current working state; a recipe captures reusable workflow defaults and asset-role expectations.

### Subtitle QA / Lint Panel

**Purpose:** Add automated subtitle quality checks so SRT output is not only generated and editable, but also production-safe.

**External precedent and why it matters:**

- Subtitle Edit surfaces max CPS and line-length feedback throughout editing and ties those thresholds into fix/common-error workflows.
- Section 508 and DCMP both reinforce the need for readable line counts, safe placement, synchronized timing, and non-distracting presentation.

**Recommended checks:**
- Characters per second (CPS)
- Max line length / line count
- Minimum and maximum subtitle duration
- Overlaps and negative gaps
- Suspiciously short gaps or flashes
- Off-screen-safe caption placement warnings for animated/rendered captions
- Missing speaker labels or inconsistent speaker formatting when diarization is in use

**Why it fits this release:**
- It leverages the `SubtitleBlock` model, SRT Edit, and Caption Animate settings already in scope
- It creates a natural "review before render" step between SRT Edit and Caption Animate / Composition
- It gives the app a stronger professional polish without requiring a new tab

**Integration points:** Section 4 now defines this as part of SRT Edit, Section 9 adds dedicated lint testing, and Sections 13-14 capture the rule-profile and false-positive strategy.

**Design direction:** Start with a dock/panel that lists warnings and jumps to the affected subtitle or composition setting when clicked.

### Auto-Resync Toolkit

**Purpose:** Provide bulk retiming operations for subtitle repair after audio edits or timing drift.

**External precedent and why it matters:**

- Subtitle Edit's "Adjust all times", "Visual sync", "Point sync", and "Change frame rate" workflows show that bulk retiming belongs in the editor, not in a separate utility.
- Aegisub's timing post-processor and keyframe snapping show that batch timing cleanup is most useful when it stays previewable and rule-driven.

**Recommended operations:**
- Shift all subtitles by offset
- Shift from current subtitle onward
- Two-point stretch / fit-to-range
- FPS / drift correction
- Snap boundaries toward silence regions
- Reapply timing from word-level or corrected alignment data when available

**Why it fits this release:**
- It directly complements the researched SRT Edit waveform, silence detection, correction alignment, and undo/redo system
- It addresses one of the most common real-world subtitle maintenance tasks
- It makes SRT Edit materially more powerful than a simple manual timestamp editor

**Integration points:** Section 4 ties resync to existing silence detection and JSON bundles, Section 11 adds the `SessionContext` sidecar requirement, and Section 12 places this after the first waveform/editor milestone.

**Design direction:** Put these tools in SRT Edit as batch operations with preview + undo, not as a separate screen.

### Audio-Reactive Captions

**Purpose:** Make captions respond to audio energy so the product feels uniquely native to an audio-visualizer workflow.

**External precedent and why it matters:**

- Adobe After Effects' "Convert Audio To Keyframes" formalizes the pattern of turning audio amplitude into animation-driving data.
- DaVinci Resolve 20's AI animated subtitles and beat detector features show that speech-aware and beat-aware subtitle motion is now an expected part of premium editing workflows.

**Possible behaviors:**
- Scale, glow, shake, bounce, or highlight intensity tied to volume peaks
- Word emphasis triggered by loudness or beat-like onset detection
- Speaker-specific reactive behavior when diarization is enabled
- Shared timing hooks between visualizer output and caption animation

**Why it fits this release:**
- It is the clearest differentiator from generic caption tools
- The app already has audio analysis and animation systems that can be bridged
- It creates a meaningful connection between the Audio Visualizer and Caption Animate tabs

**Integration points:** Section 5 ties this to the animation registry and shared audio-analysis bundle, Section 11 adds analysis caching, and Section 12 places it after Caption Animate's base preset/editor work.

**Design direction:** Start with a small number of musically useful reactive presets rather than exposing a full motion-graph system in v0.6.0.

**Verification pass 1 (2026-03-15):** All API claims, line counts, method signatures, dataclass fields, event types, test inventories, and dependency pins were cross-referenced against the actual codebase. Corrections applied: `ensure_example_configs()` export status clarified, `RenderConfig.quality` default documented as `"small"`, `TranscriptionResult`/`RenderResult`/`AnimationConfig` field tables added, `_build_visualizer_view()` branching style corrected, test count updated to 325+, tab-switch UX during renders and `RenderDialog` placement added as new research areas, and cross-tab progress visibility risk added.

**Verification pass 2 (2026-03-15):** Major-feature integration audit covering Workflow Recipes, Subtitle QA / Lint Panel, Auto-Resync Toolkit, and Audio-Reactive Captions. Corrections applied: (1) `detect_silences()` and `apply_silence_alignment()` flagged as internal-only, not exported from `srt.__init__.py`; (2) diarization limitation documented — speaker labels only populated in `PipelineMode.TRANSCRIPT` mode; (3) `event_context` pipeline wiring gap exposed — `SubtitleFile.apply_animation()` does not pass `event_context` to animations, so audio-reactive data has no path into the render pipeline without extension; (4) `FormattingConfig` lint coverage expanded to include `min_gap`, `pad`, and related fields, plus `SilenceConfig` relevance for timing-integrity checks; (5) audio analysis and silence detection added to Section 8 threading needs table; (6) `write_json_bundle()` word timing documented as conditional on `word_level=True`; (7) six new risks added to Section 13 for the newly identified gaps.
