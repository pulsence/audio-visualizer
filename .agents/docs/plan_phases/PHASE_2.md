# Phase 2: GPU Hardware Acceleration

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 2.

Apply consistent hardware-accelerated encoding and fallback behavior across all three render paths.

### 2.1: Encoder Detection and Selection

Build the shared encoder-detection and selection layer.

**Tasks:**
1. Create `core/hwaccel.py` with `detect_encoders()`, `select_encoder(codec="h264")`, and `get_decode_flags()`.
2. Probe the actual FFmpeg build available to the app with `ffmpeg -encoders` for subprocess-based paths.
3. Probe PyAV codec availability for the PyAV render path.
4. Use encoder priority `h264_nvenc` -> `h264_qsv` -> `h264_amf` -> `h264_mf` -> `libx264`.
5. Cache detection results so every render does not re-probe.
6. Log both the detected encoders and the encoder selected for each render.

**Files:**
- `src/audio_visualizer/core/hwaccel.py`

**Success criteria:** The app can reliably detect the shipped encoder capabilities on the host and consistently select the highest-priority usable encoder before each render starts.

**Close-out:** Add or update tests for encoder selection and fallback ordering, run the relevant tests and `pytest tests/ -v` when shared rendering utilities changed, update `.agents/docs/architecture/` docs if render infrastructure changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 2.2: Apply HW Acceleration to the Audio Visualizer Render Path

Fix hardware-accelerated encoding in the PyAV-based Audio Visualizer render path.

**Tasks:**
1. Update `VideoWriter` in `visualizers/utilities.py` to use `select_encoder()` instead of maintaining a separate inline encoder map.
2. Add runtime fallback so a failed hardware-encoder open or write automatically retries with software encoding.
3. Log the final encoder actually used after fallback resolution.

**Files:**
- `src/audio_visualizer/visualizers/utilities.py`
- `src/audio_visualizer/core/hwaccel.py`

**Success criteria:** Audio Visualizer renders use hardware encoding when available, recover automatically to software when runtime incompatibilities occur, and always report the actual encoder used.

**Close-out:** Add or update tests for runtime fallback behavior where feasible, run the relevant tests and `pytest tests/ -v` when shared rendering utilities changed, update `.agents/docs/architecture/` docs if render-path behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 2.3: Apply HW Acceleration to the Render Composition Path

Replace hardcoded software encoding in the FFmpeg composition builder.

**Tasks:**
1. Update `filterGraph.py` to use `select_encoder()` for H.264 output instead of hardcoded `libx264`.
2. Apply `get_decode_flags()` so decode acceleration uses `-hwaccel auto` in subprocess renders.
3. Add runtime fallback: if a hardware-encoder FFmpeg invocation fails, retry automatically with software encoding.
4. Surface the encoder actually used in the render progress UI or status output.

**Files:**
- `src/audio_visualizer/ui/tabs/renderComposition/filterGraph.py`
- `src/audio_visualizer/core/hwaccel.py`

**Success criteria:** Render Composition uses the best available hardware encoder when possible, retries automatically on hardware-specific failures, and exposes the actual encoder used to the user.

**Close-out:** Add or update tests for composition encoder selection and fallback handling, run the relevant tests and `pytest tests/ -v` when shared rendering utilities changed, update `.agents/docs/architecture/` docs if composition rendering changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 2.4: Apply HW Acceleration to the Caption Render Path

Replace hardcoded software encoding in caption rendering.

**Tasks:**
1. Update `_build_h264_args()` in `ffmpegRenderer.py` to use `select_encoder()`.
2. Add decode acceleration flags for FFmpeg input handling.
3. Add runtime fallback on caption-render encoder failure.
4. Surface the actual encoder used in caption-render progress output.

**Files:**
- `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- `src/audio_visualizer/core/hwaccel.py`

**Success criteria:** Caption renders use the best available hardware encoder when possible, retry cleanly on runtime failures, and log the encoder actually used.

**Close-out:** Add or update tests for caption encoder selection and fallback handling, run the relevant tests and `pytest tests/ -v` when shared rendering utilities changed, update `.agents/docs/architecture/` docs if caption rendering changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 2.5: Phase 2 Review

**Tasks:**
1. Review all three render paths to make sure they now share one encoder-selection contract.
2. Remove obsolete per-path encoder selection code or dead fallback branches.
3. Verify logging and user-facing status output consistently report the actual encoder used.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 2 implementation files
- Phase 2 tests

**Success criteria:** Hardware acceleration behavior is consistent, observable, and recoverable across Audio Visualizer, Render Composition, and Caption Animator.

### 2.6: Phase 2 Changelog

**Tasks:**
1. Summarize encoder detection, fallback behavior, and UI/reporting updates made in Phase 2.
2. Note any platform-specific caveats that implementers should preserve in later render work.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 2 implementation notes

**Success criteria:** Later phases can rely on a single shared hardware-acceleration strategy instead of re-solving encoder selection per feature.
