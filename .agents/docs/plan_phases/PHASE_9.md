# Phase 9: User Debug - 2

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

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

### 9.15: Phase 9 Code Review

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
