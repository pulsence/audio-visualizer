# Phase 11: User Debug - 4

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

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
