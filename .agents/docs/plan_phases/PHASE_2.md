# Phase 2: Extract the Audio Visualizer Tab

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

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
