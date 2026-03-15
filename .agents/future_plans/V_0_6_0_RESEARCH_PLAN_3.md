# v0.6.0 Stage Three: Tab-Based GUI Layout — Research Plan

> **Prerequisite:** Stage Two (integrating `srt` and `caption` packages into `audio_visualizer`) must be completed before this work begins. As of 2026-03-15, Stage Two has **not** been completed — the `audio_visualizer.srt` and `audio_visualizer.caption` packages do not yet exist in `src/audio_visualizer/`.

## Overview

Stage Three restructures the application's GUI from a single-screen Audio Visualizer layout to a **multi-tab interface** with five tabs:

1. **Audio Visualizer** (default) — the current main screen
2. **SRT Gen** — generate SRT files from audio using `audio_visualizer.srt`
3. **SRT Edit** — view audio waveform alongside SRT timestamps and adjust them
4. **Caption Animate** — generate caption overlay videos from SRT using `audio_visualizer.caption`
5. **Render Composition** — composite background, audio, and outputs from other tabs into a final video

This plan researches each tab's requirements, explores how the current `MainWindow` architecture must change to support tabs, and identifies design options and trade-offs.

As of 2026-03-15, several topic areas remain intentionally open rather than fully decided:

- The final Stage Two `audio_visualizer.srt` and `audio_visualizer.caption` APIs do not yet exist in the host app
- The SRT Edit waveform stack still needs a repo-local compatibility spike before any dependency/version change is treated as final
- The Render Composition tab still needs an explicit cross-tab asset contract for alpha, duration, FPS, and audio-source behavior

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

### Key integration points with Local SRT

Based on the Local SRT project's API (`Projects to integrate/Local SRT/src/local_srt/api.py`):

| API Function | Purpose | Tab UI element |
|-------------|---------|---------------|
| `load_model(model_name, device, strict_cuda)` | Load Whisper model | Model selection dropdown (tiny/base/small/medium/large), device selector (cpu/cuda) |
| `transcribe_file(input_path, output_path, fmt, cfg, model, ...)` | Transcribe audio to SRT | Transcribe button, progress display |

### Current research gap - Stage Two surface mismatch

Stage Two research no longer assumes the entire Local SRT CLI surface comes forward unchanged. The current direction in `.agents/docs/V_0_6_0_RESEARCH_PLAN_2.md` drops batch transcription from the merged package while retaining broader output and alignment capabilities. The Stage Three research must therefore distinguish between:

- what the merged package is expected to support at all
- what the Stage Three GUI needs to expose in v0.6.0
- what can remain in an advanced panel or later follow-on work

| Capability area | Local SRT / Stage Two status | Impact on Stage Three research |
|-----------------|------------------------------|--------------------------------|
| Batch transcription | Stage Two research currently drops the batch API | The current Stage Three wording ("audio files", "file(s)") may no longer match the merged package surface |
| Output formats | Local SRT supports `srt`, `vtt`, `ass`, `txt`, `json` | The GUI needs to decide whether v0.6.0 exposes the full retained output set or a narrower subset |
| Word-level / Shorts outputs | Retained in Stage Two research | SRT Gen may need paired output path controls, not just a primary output path |
| Correction and script alignment | Retained in Stage Two research | The GUI needs to decide whether these appear in SRT Gen, SRT Edit, or both |
| Prompt / script file loading | Retained in Stage Two research | The GUI may need file inputs that map to `initial_prompt` / `script_path`, not just plain text fields |
| Side outputs / diagnostics | Retained in Stage Two research (`transcript_path`, `segments_path`, `json_bundle_path`, `keep_wav`) | These likely belong in an advanced or diagnostics area instead of the default form |

### Settings that need UI controls

From `ResolvedConfig` and `transcribe_file()` parameters:

| Category | Settings | Type |
|----------|---------|------|
| **Model** | `model_name` (tiny/base/small/medium/large), `device` (cpu/cuda), `strict_cuda` | Dropdowns, checkbox |
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

### Threading considerations

Model loading and transcription are long-running operations. The existing `QThreadPool` pattern from `MainWindow` can be reused:

- Model loading should happen on a background thread with progress feedback
- Transcription should happen on a background thread with progress reporting; cancelability still needs an explicit package/worker design
- Local SRT's `EventHandler` system maps well to Qt signals for progress reporting

### Design options for model lifecycle

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Load on demand** | Load model when user clicks "Transcribe"; cache for reuse | No upfront cost, simple | First transcription has noticeable delay |
| **B. Load on tab entry** | Load model when user switches to SRT Gen tab | Ready when user needs it | Wastes resources if user is just browsing tabs |
| **C. Explicit load button** | User clicks "Load Model" separately from "Transcribe" | User controls when the cost is paid; clear feedback | Extra step in the workflow |

---

## 4. SRT Edit Tab

### Purpose

Display an audio waveform alongside SRT timestamps and allow the user to adjust the timestamps visually.

### Required functionality (from TODO)

- View audio waveform
- View SRT timestamps overlaid on the waveform
- Adjust SRT timestamps (start/end times)

### Key technical challenges

| Challenge | Detail |
|-----------|--------|
| **Waveform rendering** | Need to render an audio waveform that can be zoomed and scrolled. Qt does not have a built-in waveform widget. |
| **SRT timestamp overlay** | SRT blocks must be displayed as regions on the waveform timeline. Each block needs draggable start/end handles. |
| **Audio playback sync** | User should be able to play audio from a specific timestamp to verify alignment. |
| **Large file handling** | Audio files can be long; waveform must support zooming and scrolling without loading the entire waveform at full resolution. |

### Design options for waveform rendering

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Custom QWidget with QPainter** | Draw waveform using `QPainter` on a custom `QWidget`. Pre-compute waveform data at multiple zoom levels using librosa/numpy. | Full control, no extra dependencies, consistent with project's existing Qt approach | Significant implementation effort; scrolling/zooming, hit-testing for drag handles all manual |
| **B. pyqtgraph** | Use `pyqtgraph` for waveform plotting with built-in zoom/pan/scroll | Battle-tested plotting, efficient for large datasets, built-in mouse interaction | New dependency; styling may not match the rest of the app; learning curve |
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

**Key risk — PySide6 compatibility:** pyqtgraph has documented compatibility issues with PySide6 6.9.x. The current host app pins `PySide6==6.9.1`, so any pyqtgraph adoption already implies a dependency review in the host repository. Upstream fixes landed across late 2025, but the exact support picture for this repo's Python 3.13 + PySide6 + QtMultimedia combination is still not something the research can treat as finalized without a local spike. **A repo-local spike test is essential before committing to pyqtgraph.**

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
| PySide6 6.9.2+ / 6.10.x | Upstream fixes landed before and around pyqtgraph `0.14.0`, but support is not stable enough to treat as guaranteed for this repo without a spike | Do not record a final PySide6/pyqtgraph pair in Decisions Made yet |
| Python 3.13 | This repo requires Python `>=3.13` | The spike must use the real project interpreter, not only upstream CI assumptions |

**Practical options:**
- Keep the current host pin and choose a custom Qt implementation (`QGraphicsView` or `QPainter`) for v0.6.0
- Run an explicit spike against one or more candidate PySide6/pyqtgraph pairs, then decide after the result is in-repo and reproducible
- Defer the final waveform library choice until Stage Two exists in the host repo and the dependency surface can be tested end-to-end

**Current research conclusion:** pyqtgraph remains attractive for time-to-prototype, but the dependency/version choice is still open. If a local spike fails or requires an undesirable Qt downgrade/upgrade, `QGraphicsView/QGraphicsScene` (Option D) is the strongest no-new-dependency alternative because it still provides a scene graph, built-in hit-testing, and coordinate transforms.

### SRT parsing/writing

The integrated `audio_visualizer.srt` package (from Local SRT) contains `SubtitleBlock` data class and output writers. The SRT Edit tab needs to:
1. Parse an existing SRT file into `SubtitleBlock` objects
2. Display them with timing information
3. Allow editing of start/end times and text
4. Write the modified SRT back to file

Local SRT's `output_writers.py` handles writing. However, the current standalone project only clearly exposes output writers plus `parse_srt_to_words()` for corrected-alignment workflows; it does **not** yet expose a general-purpose "load SRT into editable `SubtitleBlock` objects" API. That means SRT Edit still has an unresolved round-trip data-model question.

### Design options for editable subtitle parsing / round-tripping

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Add parsing API to `audio_visualizer.srt`** | Stage Two or early Stage Three adds a first-class parser/serializer pair around `SubtitleBlock` | Keeps subtitle logic in one package, reusable by SRT Gen and SRT Edit | Expands Stage Two / shared-package scope |
| **B. Add a Stage Three-local parser/editor model** | SRT Edit owns a small parser that converts `.srt` text into a tab-local editing model, then writes back via local logic or `output_writers.py` | Keeps Stage Two smaller, isolates editing concerns to the tab | Splits subtitle I/O logic across packages |
| **C. Add a third-party parsing dependency** | Use an existing SRT parsing library and map it into `SubtitleBlock` | Fastest path to robust parsing if the dependency is solid | Adds another dependency and another data model to reconcile |

### Design options for audio playback / sync

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Reuse `QMediaPlayer` / `QAudioOutput`** | Follow the current app's preview stack for playback and seeking | Consistent with current dependencies and code patterns | Need to verify seek precision and sync callbacks for editing workflows |
| **B. Custom audio playback via PyAV / numpy** | Decode and drive playback outside Qt Multimedia | Maximum timing control | Large new implementation surface; duplicates media capabilities already in the app |
| **C. Hybrid** | Use Qt Multimedia for playback, but keep waveform timebase and editing overlays fully custom | Lower playback implementation cost while keeping editing UI flexible | Requires careful sync bridging between playback position and custom visuals |

---

## 5. Caption Animate Tab

### Purpose

Select SRT files and generate caption overlay videos using `audio_visualizer.caption` (the integrated Caption Animator package).

### Required functionality (from TODO)

- Select SRT file(s)
- Configure caption generation settings
- Generate caption overlay video

### Key integration points with Caption Animator

Based on the Caption Animator project's API (`Projects to integrate/Caption Animator/src/caption_animator/api.py`):

| API Element | Purpose | Tab UI element |
|------------|---------|---------------|
| `render_subtitle(input_path, output_path, config, on_progress, on_event)` | Main render function | Render button, progress display |
| `RenderConfig.preset` | Styling preset name | Preset dropdown |
| `RenderConfig.fps` | Output FPS | FPS input |
| `RenderConfig.quality` | Output quality (small/medium/large) | Quality dropdown |
| `RenderConfig.safety_scale` | Scale factor for sizing | Scale input |
| `RenderConfig.apply_animation` | Whether to animate | Checkbox |
| `RenderConfig.reskin` | For ASS files: apply preset style | Checkbox |

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

### Current research gaps

| Gap | Detail |
|-----|--------|
| **Preset discovery** | `PresetLoader` defaults to cwd-relative `presets/`. The Stage Three tab needs an explicit embedded-app resource strategy. |
| **Style surface** | `RenderConfig` exposes only high-level render switches, but actual preset data also contains font, color, padding, margin, alignment, and animation configuration. |
| **Font determinism** | Sizing falls back to system fonts if `font_file` is empty. The GUI needs to decide whether built-in presets are sufficient or whether users must be able to choose fonts explicitly. |
| **Cancellation** | The current public API exposes progress callbacks but not a cancel handle or FFmpeg subprocess control. |

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

### Threading considerations

Caption rendering via FFmpeg is a long-running operation. Same QThreadPool pattern applies:
- `RenderConfig` + `on_progress` callback maps to Qt signals
- `on_event` callback provides `RenderEvent` objects for detailed status
- Progress is available today, but cancellation is **not** clearly available at the public API boundary. A Qt worker would need either a new cancellation seam or a first-pass UX that treats caption jobs as non-cancelable.

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

### Key technical challenges

| Challenge | Detail |
|-----------|--------|
| **Layer compositing** | Must combine multiple video/image layers (background, visualizer overlay, caption overlay) with proper alpha blending and positioning |
| **Layout editor** | Users need to position and size each layer. This requires some form of spatial editor. |
| **Timeline management** | Different layers may have different durations. Need to define how they align temporally. |
| **Video decoding** | Must decode input videos frame-by-frame for compositing. PyAV (already a dependency) can handle this. |
| **Audio handling** | Audio may come from the original audio file or from a video layer. User needs to select the audio source. |

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

### Cross-tab data flow

The Render Composition tab needs to receive outputs from other tabs. This is the strongest argument for a shared session/context object:

| Source Tab | Output | Used by Render Composition |
|-----------|--------|---------------------------|
| Audio Visualizer | Rendered visualizer video (MP4) | Visualizer layer |
| Caption Animate | Rendered caption video (MOV, transparent) | Caption overlay layer |
| SRT Gen | Generated SRT file | Could feed into Caption Animate first |

### Current research gap - cross-tab asset contract

The composition tab is the place where assumptions from the other tabs finally collide. The current plan identifies the need for background/audio/overlay inputs, but it does not yet define the concrete asset contract those tabs must satisfy.

| Asset type | Current producer behavior | Open questions for composition |
|------------|---------------------------|--------------------------------|
| Audio Visualizer output | Current app renders an MP4 visualizer video | Is this always an opaque layer? Can it be shorter than the final composition? |
| Caption Animate output | Quality-dependent output; `large` is ProRes 4444 with alpha, `medium` is ProRes 422 HQ without alpha | Which qualities are acceptable as overlay inputs? Should the composition tab require alpha-capable outputs only? |
| Background image | Static image loaded by the user | How is duration created: loop to audio length, fixed user length, or final render length? |
| Background video | Arbitrary duration / FPS / codec | Trim, loop, freeze-last-frame, or reject mismatched lengths? |
| Audio source | Standalone audio file or audio extracted from a video layer | Which source is authoritative? Is one source selected or are multiple sources mixed? |

### Design options for composition asset contract

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Restrict inputs to composition-friendly intermediates** | Require known-good inputs, e.g. alpha-capable caption overlays and standard visualizer outputs | Simplest composition logic, easiest to test | Pushes responsibility upstream to other tabs and user choices |
| **B. Auto-transcode incompatible assets** | Composition normalizes incoming assets (codec, alpha, FPS, duration prep) before building the final graph | More forgiving UX | Adds preprocessing time, temp-file management, and more FFmpeg complexity |
| **C. Render some layers directly in composition** | Composition may consume source SRT/audio and generate certain overlays itself instead of always reusing intermediate files | Maximum control over the final graph | Blurs tab boundaries and duplicates work already done in other tabs |

### Design options for timeline authority

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Selected audio source defines final duration** | Final composition length follows the chosen audio track; visual/video layers are trimmed, looped, or frozen to match | Natural fit for the current workflows where audio is central | Requires explicit rules for every non-audio layer |
| **B. Background defines final duration** | Background image/video drives duration; audio/overlays adapt to it | Good for video-first workflows | Less natural for the current short/video workflows described in `TODO` |
| **C. Per-layer start/end controls** | User sets offsets plus trim/loop/freeze behavior per layer | Most flexible | Largest UI and validation surface |

---

## 7. Settings Persistence

### Current state

`_collect_settings()` returns a flat dict with keys: `general`, `visualizer`, `specific`, `ui`. `_apply_settings()` restores from this dict. Auto-saved to `last_settings.json` on close.

### Problems

The current format only supports Audio Visualizer settings. Adding tabs requires expanding the format to include settings for all tabs.

### Design options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Expand existing format** | Add new top-level keys: `srt_gen`, `srt_edit`, `caption_animate`, `render_composition` alongside existing keys. Each tab's widget class implements its own `collect_settings()` / `apply_settings()`. | Backward-compatible (old settings files still load for visualizer tab), simple | Keys accumulate; single large JSON file |
| **B. Per-tab settings files** | Each tab saves/loads its own settings file in the config directory | Independent, no format conflicts | Multiple files to manage; cross-tab settings (like audio file path) duplicated |
| **C. Versioned format with migration** | Add a `version` key to the settings JSON. Migrate old formats on load. | Clean evolution path | Migration code adds complexity |

### Backward compatibility

Existing `last_settings.json` files contain only Audio Visualizer settings. The expanded format should:
1. Load old files without error (missing tab keys get defaults)
2. Save in the new expanded format going forward
3. Project save/load files (`.json`) should include all tabs

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
| SRT Gen | Model loading | Not at the current package API boundary | Yes (indeterminate) |
| SRT Gen | Transcription | Not at the current package API boundary | Yes (event callbacks) |
| Caption Animate | Caption rendering | Not at the current package API boundary | Yes (FFmpeg progress events) |
| Render Composition | Composition rendering | Depends on engine choice | Yes |

### Design options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Shared render thread pool** | All tabs share the existing max-1 `render_thread_pool` | Prevents resource contention, simple | Can only do one operation at a time across all tabs |
| **B. Per-tab thread pools** | Each tab manages its own QThreadPool | Tabs can run operations independently | Resource contention; user might accidentally run expensive operations in parallel |
| **C. Shared pool, per-tab workers** | Shared thread pool but each tab has its own worker class with appropriate signals | Controlled concurrency, tab-specific progress | Need to handle "pool busy" state across tabs |

### Current integration gap

Both Local SRT and Caption Animator currently expose progress/event callbacks but not a clear cancellation token or job handle. Stage Three therefore still needs a design choice:

- add cooperative cancellation support at the package or worker-adapter layer
- accept that some first-pass jobs are non-cancelable
- or move long-running subprocess ownership out of the package APIs and into Qt worker classes

---

## 9. Testing Considerations

### Existing test state

From `tests/`: `test_app_paths.py`, `test_logging.py`, `test_media_utils.py`. No UI tests exist.

### New testing needs

| Area | Test type | Notes |
|------|----------|-------|
| Tab widget creation | Unit | Verify each tab class instantiates without errors |
| Settings serialization | Unit | Each tab's `collect_settings()` / `apply_settings()` round-trips correctly |
| Settings backward compat | Unit | Old format `last_settings.json` loads without error |
| Cross-tab data flow | Integration | Output of one tab can be loaded by Render Composition |
| Worker classes | Unit | Each worker type emits correct signals |
| SRT parsing/editing | Unit | SRT Edit tab correctly modifies timestamps |

### Testing challenges

- UI tests with PySide6 require either `pytest-qt` or manual `QApplication` management
- Waveform rendering tests would need sample audio fixtures
- Caption rendering tests would need FFmpeg available in CI

---

## 10. MainWindow Code Review and Refactoring Analysis

A detailed code review of `mainWindow.py` (1544 lines) identified the following refactoring needs for tab decomposition.

### Code smells identified

| Smell | Location | Impact |
|-------|----------|--------|
| Magic `__getattr__` for lazy view loading | Lines 165-170 | No IDE autocomplete, runtime errors, side-effect-laden attribute access |
| 14-branch `if/elif` in `_build_visualizer_view()` | Lines 172-215 | Must edit MainWindow to add any new visualizer; not extensible |
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
- Delegates all tab-specific logic to tab classes

**View class improvements needed:**
- Each View subclass should add `apply_settings(data: dict)` method (counterpart to existing `read_view_values()`)
- `GeneralSettingsView` and `GeneralVisualizerView` should expose setter methods instead of allowing direct widget access

**Standardized patterns for all tabs:**
- Worker creation: `BaseTab._start_render_worker(worker, callbacks)`
- Progress reporting: consistent signal interface across all worker types
- Validation: each tab implements `validate_settings() -> (bool, str)`
- Settings: each tab implements `collect_settings() -> dict` and `apply_settings(dict)`
- Control disabling: each tab registers its editable controls explicitly

---

## 11. Global File Provider / Session Context

### Purpose

Per user decision, a global file provider should make all audio/video/graphics/SRT files commonly accessible to all screens. This combines shared state at the MainWindow level (Option B) with a structured session context (Option C).

### Design sketch

```
SessionContext:
    - audio_files: list[Path]        # Audio files loaded by the user
    - srt_files: list[Path]          # SRT files (generated or loaded)
    - video_files: list[Path]        # Video outputs (visualizer, caption)
    - image_files: list[Path]        # Background images
    - signals:
        - file_added(category: str, path: Path)
        - file_removed(category: str, path: Path)
```

Tabs register outputs (e.g., Audio Visualizer adds its rendered MP4, SRT Gen adds its generated SRT) and other tabs can browse/select from the pool. File pickers in each tab should show both the global pool and allow browsing the filesystem.

### Key considerations

- SessionContext should be owned by MainWindow and injected into each tab
- File entries should track their source (which tab produced them) for clarity
- The global pool supplements but does not replace per-tab file selection — users can always browse the filesystem directly
- SessionContext state should be included in project save/load

---

## 12. Implementation Sequencing

> Note: Section numbers below refer to research plan sections, not implementation order.

```
Stage Two (srt + caption packages)  ← MUST complete first
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

---

## 13. Risk Areas

| Risk | Mitigation |
|------|-----------|
| MainWindow refactor breaks existing functionality | Extract Audio Visualizer tab first; verify all existing features work before adding new tabs |
| Waveform rendering performance for large audio files | Use downsampled waveform data at multiple zoom levels; render only visible portion |
| Editable SRT round-tripping is not yet defined | Decide whether parsing/editing lives in `audio_visualizer.srt` or in the SRT Edit tab before implementation planning |
| SRT Edit interaction complexity (drag handles, snapping) | Phase 1: table + waveform display; Phase 2: draggable handles |
| FFmpeg filter_complex API surface in PyAV | Spike test the overlay filter with representative inputs early |
| Cross-tab asset contract is still open | Define alpha/FPS/duration/audio rules before committing to a composition backend |
| Caption preset discovery depends on cwd today | Decide on built-in/package-resource/app-data preset strategy before designing the preset dropdown |
| Long-running job cancellation is unclear at package boundaries | Decide whether cancellation support is required in v0.6.0 and where that seam lives |
| SessionContext complexity | Start with simple file list + signals; avoid over-engineering state management |
| Settings format migration | Load old files with silent defaults; save in new format going forward |
| pyqtgraph + PySide6 compatibility | Spike test required before committing; fallback to QGraphicsView if incompatible |
| Stage Two not yet complete | All Stage Three work is blocked until `audio_visualizer.srt` and `audio_visualizer.caption` packages exist with working APIs |

---

## 14. Phase 3 Follow-On Considerations

This section captures work that the feedback explicitly pushes out of Phase 2, so it remains visible when the later research and implementation planning starts.

| Topic | Why it is a Phase 3 concern | Main code areas |
|-------|------------------------------|-----------------|
| Shared-service extraction | Phase 2 starts with a minimal package merge rather than immediate app-wide service consolidation | future `audio_visualizer` service layer, job orchestration, worker ownership |
| Deeper caption-system integration | Phase 2 preserves the current high-level caption API | `audio_visualizer.caption` facade/service layer, later tab integration |
| PyAV-based caption rendering evaluation | Phase 2 retains the external ffmpeg/libass renderer | `audio_visualizer.caption.rendering`, shared media stack, composition workflows |
| Broader test-suite expansion | Phase 2 keeps the test migration scoped to unit tests plus host smoke tests | root pytest config, fixture migration, end-to-end coverage strategy |
| Rich resource management UI | Phase 2 can move presets/configs into app config/data dirs without yet building a GUI for editing or managing them | `audio_visualizer.app_paths`, preset/config managers, later tabs |

---

## 15. Decisions Made

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
| Research timing | This research plan will only be fully completed after Stage Two is implemented |

---

## 16. Clarifications Resolved

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
11. **Stage Two status:** Research plan will be finalized after Stage Two is complete.
12. **Tab container:** QStackedWidget + custom navigation.

---

## 17. Clarifications Required

1. **SRT Gen scope:** Should Stage Three stay single-file to match the current Stage Two direction, or should the GUI reintroduce multi-file/batch transcription even if the merged package drops `transcribe_batch()`?
2. **SRT Gen feature exposure:** For v0.6.0, should the tab expose only the core transcription controls, or also retained advanced features such as correction SRT, script/prompt loading, side outputs, diarization, and diagnostics?
3. **SRT Edit data model:** Should editable SRT parsing / round-tripping become part of `audio_visualizer.srt`, or may Stage Three own a tab-local parser/editor model?
4. **Waveform dependency:** After Stage Two exists in the host repo, should we authorize a repo-local pyqtgraph spike and possible Qt dependency change, or should Stage Three prefer a custom Qt implementation to avoid that dependency decision?
5. **Caption preset scope:** Should Caption Animate v0.6.0 expose built-in presets only, or should it also support external preset files and/or editable style overrides?
6. **Cancellation requirement:** Is cancelability a hard requirement for SRT Gen and Caption Animate in v0.6.0, even though the current package APIs expose progress callbacks but not explicit cancel handles?
7. **Composition asset contract:** For Render Composition, should overlay inputs be restricted to alpha-capable intermediates, should incompatible assets be auto-transcoded, or should some overlays be rendered directly during composition?
8. **Composition timeline authority:** What defines final duration and timing alignment: the selected audio source, the background asset, or per-layer start/end controls with trim/loop/freeze behavior?

When Stage Two is finished, this plan should be reviewed again to verify that the integrated `audio_visualizer.srt` and `audio_visualizer.caption` APIs match the assumptions and open questions recorded in Sections 3, 4, 5, 6, and 8.
