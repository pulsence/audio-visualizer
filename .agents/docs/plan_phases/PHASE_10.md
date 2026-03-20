# Phase 10: User Debug - 3

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

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
