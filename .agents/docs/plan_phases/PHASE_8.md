# Phase 8: User Debug - 1

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

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
