# Phase 4: Render Composition — Real-Time GPU Playback

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 4.

Implement the real-time playback engine, transport controls, timeline scrubbing, and waveform display.

### 4.1: Timeline Scrubbing

Enable continuous playhead scrubbing on the timeline.

**Tasks:**
1. Detect mouse press near the playhead line in `TimelineWidget`.
2. Track drag movement and update `playhead_ms` continuously.
3. Emit `playhead_changed` during the drag so preview updates stay synchronized.
4. Change the cursor appropriately while scrubbing.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`

**Success criteria:** Users can drag the playhead smoothly, the preview seeks accordingly, and normal timeline clicks still behave correctly.

**Close-out:** Add or update tests for scrub drag behavior and playhead updates, run the relevant tests and `pytest tests/ -v` when shared composition timeline behavior changed, update `.agents/docs/architecture/` docs if timeline interaction changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 4.2: Audio Waveform on the Timeline

Display low-resolution waveform envelopes for audio tracks.

**Tasks:**
1. Add a waveform utility that computes an RMS envelope from source media using PyAV.
2. Cache envelopes per source path so redraws and scrolls stay cheap.
3. Render the envelope into audio track items using `QPainterPath`.
4. Scale drawing to both the track geometry and the currently visible timeline window.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/timelineWidget.py`

**Success criteria:** Audio tracks show a usable waveform without degrading normal timeline performance.

**Close-out:** Add or update tests for waveform caching and painting helpers where practical, run the relevant tests and `pytest tests/ -v` when shared composition timeline behavior changed, update `.agents/docs/architecture/` docs if waveform behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 4.3: GPU-Composited Playback Engine

Build the real-time compositor using `QOpenGLWidget`, PyAV decode, and `sounddevice`.

**Tasks:**
1. Create `ui/tabs/renderComposition/playbackEngine.py`.
2. Implement `CompositorWidget(QOpenGLWidget)` with texture management and `QOpenGLTextureBlitter`-based layer compositing.
3. Implement per-video-layer decode workers that decode frames with PyAV and push bounded frame queues.
4. Implement audio decode, mixing, and `sounddevice` playback using an audio-master clock.
5. Drive video presentation from the audio clock so late frames are dropped and early frames are repeated.
6. Implement seek/flush behavior for both decode and audio playback.
7. Gate runtime initialization through `core/capabilities.py` and fall back to the existing static preview workflow if OpenGL context creation or audio-device startup fails.
8. Structure the playback engine so tests can instantiate it without a physical audio device, for example through a dummy backend, injectable audio output, or a no-device fallback mode.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`
- `src/audio_visualizer/core/capabilities.py`

**Success criteria:** Multi-layer preview playback runs with synchronized audio and video on supported machines, seeking works, z-order and alpha blending are correct, and the tab stays usable with a graceful fallback when required runtime capabilities are unavailable.

**Close-out:** Add or update tests for capability gating, playback-engine lifecycle, and no-device fallback behavior where practical, run the relevant tests and `pytest tests/ -v` when shared composition or startup behavior changed, update `.agents/docs/architecture/` docs if playback architecture changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 4.4: Transport Controls

Wire the new playback engine into the Render Composition tab.

**Tasks:**
1. Add transport controls for Play/Pause, Stop, Jump to Start, and Jump to End.
2. Replace or augment the existing preview area with the compositor widget.
3. Bind Space to Play/Pause.
4. Keep the paused state seekable so the playhead drives a static compositor frame.
5. Connect timeline scrub events to playback-engine seek.
6. Feed playback position updates back into the timeline without creating feedback loops.

**Files:**
- `src/audio_visualizer/ui/tabs/renderCompositionTab.py`
- `src/audio_visualizer/ui/tabs/renderComposition/playbackEngine.py`

**Success criteria:** Transport controls work, playback updates the timeline, paused scrubbing shows the correct frame, and seek interactions do not create control-loop glitches.

**Close-out:** Add or update tests for transport actions and playhead synchronization where practical, run the relevant tests and `pytest tests/ -v` when shared composition UI changed, update `.agents/docs/architecture/` docs if playback control flow changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 4.5: Phase 4 Review

**Tasks:**
1. Review scrubbing, waveform display, playback fallback logic, and transport controls as one integrated preview workflow.
2. Remove temporary preview glue or dead code paths replaced by the new engine.
3. Verify test coverage reflects the fallback-first runtime model and not only the fully capable machine path.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 4 implementation files
- Phase 4 tests

**Success criteria:** Render Composition playback is robust on capable systems and still safe on systems lacking OpenGL or a usable audio device.

### 4.6: Phase 4 Changelog

**Tasks:**
1. Summarize scrubbing, waveform, playback-engine, and transport-control changes delivered in Phase 4.
2. Note any host capability assumptions or test harness requirements future work must preserve.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 4 implementation notes

**Success criteria:** Future composition work can treat the real-time playback engine and its fallback rules as settled infrastructure.
