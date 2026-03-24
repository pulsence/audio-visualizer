# Rendering Architecture

This document describes the shared job model, worker signaling, render/cancel boundaries, and the three heavy output paths used by the Stage Three UI: Audio Visualizer render, Caption Animate render, and Render Composition export.

## Shared Job Model

### User-job pool

`MainWindow.render_thread_pool` is a shared `QThreadPool` with `maxThreadCount=1`.

- `AudioVisualizerTab`, `SrtGenTab`, `CaptionAnimateTab`, and `RenderCompositionTab` all submit heavy work into this pool.
- `MainWindow.try_start_job()` blocks a second render/transcribe/export while one job is active.
- `MainWindow.set_global_busy()` disables start controls in non-owner tabs and shows a busy indicator on the owning sidebar item.

### Background pool

`MainWindow._background_thread_pool` is reserved for lightweight background work that should not consume the one user-job slot.

- Update checks run through `UpdateCheckWorker`.
- SRT Edit waveform loading uses `_WaveformLoadWorker`.

## Worker Signaling

Stage Three workers expose Qt-facing lifecycle state so tabs and the shell can react consistently.

### Shared signal vocabulary

`audio_visualizer.ui.workers.workerBridge.WorkerSignals` defines:

- `started(job_type, owner_tab_id, label)`
- `stage(name, index, total, data)`
- `progress(percent, message, data)`
- `log(level, message, data)`
- `completed(result)`
- `failed(error_message, data)`
- `canceled(message)`

### Worker implementations

- `SrtGenWorker` uses `AppEventEmitter` + `WorkerBridge` to forward shared `events.py` payloads into `WorkerSignals`.
- `CaptionRenderWorker` does the same while wrapping the caption package render API.
- `CompositionWorker` emits the same `WorkerSignals` contract directly around the FFmpeg subprocess lifecycle.
- `RenderWorker` (the legacy Audio Visualizer worker defined in `mainWindow.py`) still uses its older render-specific signals because it predates the shared worker bridge. `AudioVisualizerTab` adapts those signals into the same global job-status shell methods.

## Global Status And Completion Flow

The shell does not auto-open preview dialogs on completion.

- Tabs call `MainWindow.show_job_status()`, `update_job_progress()`, `show_job_completed()`, `show_job_failed()`, and `show_job_canceled()` to drive the persistent `JobStatusWidget`.
- Completed jobs with an output path expose `Preview`, `Open Output`, and `Open Folder`.
- `RenderDialog` is only opened when the user explicitly clicks `Preview`.
- Terminal job rows auto-clear after 5 seconds unless the user dismisses them sooner.

## Audio Visualizer Render Path

`AudioVisualizerTab` still owns the original PyAV-based frame renderer.

### Pipeline

`RenderWorker.run()` performs:

1. `AudioData.load_audio_data()` to load source samples.
2. `AudioData.chunk_audio()` and `AudioData.analyze_audio()` to derive per-frame inputs.
3. `VideoData.prepare_container()` to open the output container/stream.
4. Optional `_prepare_audio_mux()` when audio inclusion is enabled.
5. `Visualizer.prepare_shapes()` and the frame-generation loop.
6. Optional `_mux_audio()` after video frames are encoded.
7. `VideoData.finalize()` to flush/close the container.

### Progress and cancellation

- Frame progress is emitted as `(current_frame, total_frames, elapsed_seconds)`.
- Audio muxing emits a second progress channel so the tab can weight encode and mux work into one user-facing percentage.
- Cancellation is cooperative: the worker checks its cancel flag between frame writes and before/within audio mux cleanup.

### Preview behavior

- Live preview renders clamp to 5 seconds.
- Manual preview renders clamp to 30 seconds.
- Preview outputs are shown in-tab and are not registered as session assets.
- Final renders register a `visualizer_output` asset and surface completion through `JobStatusWidget`.

## SRT Generation

`SrtGenWorker` is not a renderer, but it participates in the same shared user-job lane and status model.

- The worker loads the Whisper model on the same worker thread that performs transcription to avoid cross-thread CUDA/cuBLAS issues.
- Model loading is wrapped in a one-thread executor so cancellation can still poll while `load_model()` blocks.
- Batch cancellation is cooperative between files; per-file work stops at the next safe boundary exposed by the underlying transcription pipeline.

## Caption Animate Render Path

`CaptionAnimateTab` submits `CaptionRenderWorker`, which wraps `caption.captionApi.render_subtitle()`.

### Overlay render

- The caption package generates/loads subtitle styling, applies markdown-aware animations, measures the required overlay size, writes an intermediate ASS file, and runs FFmpeg to render the overlay video.
- Worker progress, stage, and completion metadata are forwarded through `WorkerBridge`.
- H.264 overlay renders use the shared encoder-selection layer with automatic fallback to software encoding when a hardware encoder fails at runtime.

### Delivery output

- When the user requests a delivery MP4, `_create_delivery_output()` writes to a temporary file in the target directory and renames it into place after FFmpeg succeeds.
- This avoids in-place read/write conflicts when the overlay artifact and delivery artifact would otherwise overlap.
- The delivery MP4 is the primary user-facing artifact. It now uses the same shared H.264 encoder-selection and fallback strategy as the other FFmpeg render paths.

### Cancellation

- `CaptionRenderWorker` monkey-patches `subprocess.Popen` during render so it can capture the FFmpeg process handle.
- `cancel()` sets a flag and terminates the captured FFmpeg subprocess.
- Partial outputs are cleaned up on cancel/failure.

### Preview behavior

- Render previews are real FFmpeg renders capped to about 5 seconds via `RenderConfig.max_duration_sec`.
- Preview outputs are temporary and do not register `SessionAsset` entries.

## Render Composition Export Path

`RenderCompositionTab` builds a `CompositionModel` and submits `CompositionWorker`.

### Command generation

`audio_visualizer.ui.tabs.renderComposition.filterGraph` builds both preview and full-render commands.

- `build_ffmpeg_command()` constructs the final export command.
- `build_preview_command()` renders a single timeline frame.
- `build_single_layer_preview_command()` renders one selected visual layer in isolation using the same timing helpers.

### Layer timing and looping

- Visual layers use scale/overlay filters plus enable expressions derived from timeline timing.
- Video layers longer than their source duration use `-stream_loop -1`, then trim/shift inside the filter graph so preview and final export follow the same timing model.
- Audio layers support `adelay`, `atrim`, looping, and `amix=duration=longest` for layered audio output.
- Timeline loop markers come from the same source-duration data used to build the FFmpeg command.

### Cancellation and failure handling

- `CompositionWorker.cancel()` terminates the FFmpeg subprocess.
- Progress is parsed from FFmpeg `stderr` by reading `time=` updates and converting them against `CompositionModel.get_duration_ms()`.
- Recent stderr output is included in the failure message when FFmpeg exits non-zero.

### Completion behavior

- Successful exports register a `final_render` video asset in `WorkspaceContext`.
- Completion is surfaced through `JobStatusWidget`; the user may then preview/open the result from the status row.

## RenderDialog

`RenderDialog` remains the shared media preview dialog used by the explicit `Preview` action.

- It wraps `QMediaPlayer`, `QVideoWidget`, and `QAudioOutput`.
- The remembered output volume is stored at the dialog class level.
