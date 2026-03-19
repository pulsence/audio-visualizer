# Rendering Architecture

This document describes the threading model, video encoding pipeline, and audio muxing process.

## Threading Model

### Render Thread Pool

`MainWindow.render_thread_pool` is a `QThreadPool` with `maxThreadCount=1`. This ensures only one render runs at a time. Renders are executed via `RenderWorker(QRunnable)` instances submitted to this pool.

### Background Thread Pool

`MainWindow._background_thread_pool` is a separate `QThreadPool` used for non-render background tasks like `UpdateCheckWorker` and `_WaveformLoadWorker`. This prevents update checks and waveform audio loading from blocking renders.

### Signal Communication

`RenderWorker` communicates with the UI thread via Qt signals:

| Signal | Parameters | Purpose |
|--------|-----------|---------|
| `finished` | `VideoData` | Render completed successfully |
| `error` | `str` | Render failed with error message |
| `status` | `str` | Status text update (e.g., "Loading audio...") |
| `progress` | `int, int, float` | current_frame, total_frames, elapsed_seconds |
| `canceled` | — | Render was canceled |

## Video Pipeline

`RenderWorker.run()` executes the full render pipeline:

```
1. Load audio
   AudioData.load_audio_data(duration_seconds)
   → audio_samples, sample_rate

2. Chunk audio
   AudioData.chunk_audio(fps)
   → audio_frames[]

3. Analyze audio
   AudioData.analyze_audio()
   → average_volumes[], chromagrams[]

4. Prepare video container
   VideoData.prepare_container()
   → PyAV container + video stream

5. (Optional) Prepare audio mux
   _prepare_audio_mux()
   → audio resampler + output audio stream

6. Prepare visualizer
   Visualizer.prepare_shapes()

7. Generate frames (main loop)
   for i in range(len(audio_frames)):
       frame = Visualizer.generate_frame(i)
       encode frame to video stream
       check for cancellation
       emit progress signal

8. (Optional) Mux audio
   _mux_audio()
   → encode audio samples to audio stream

9. Finalize
   VideoData.finalize()
   → flush streams, close container
```

## Codec Configuration

`VideoData.prepare_container()` configures the video stream:

- **Codec:** The user-selected codec (currently one of `h264`, `hevc`, `vp9`, `av1`, or `mpeg4`)
- **Hardware acceleration:** If `hardware_accel` is True, attempts hardware-accelerated codec first (e.g., `h264_nvenc`), falls back to software codec on failure
- **Bitrate:** Optional bitrate setting in bits per second
- **CRF:** Optional Constant Rate Factor for quality control
- **Container format:** Determined by output file extension (typically `.mp4`)

## Audio Muxing

When `include_audio` is enabled:

1. **`_prepare_audio_mux()`** — Creates an AAC audio stream in the output container and sets up a PyAV `AudioResampler` to convert the input audio format to the output stream's expected format.

2. **`_mux_audio()`** — After all video frames are written:
   - Demuxes and decodes the input audio stream
   - Stops at the preview cutoff when `preview_seconds` is set
   - Resamples decoded frames to match the output stream format
   - Encodes and muxes the resampled frames into the container

## Cancellation

- `MainWindow.cancel_render()` calls `_active_render_worker.cancel()`
- `RenderWorker.cancel()` sets `_cancel_requested = True`
- `_check_canceled()` is called between frames; if set, it calls `_cleanup_on_cancel()` (closes containers) and emits the `canceled` signal
- `MainWindow.render_canceled()` resets the UI controls

## Progress Reporting

During the frame generation loop, `RenderWorker` emits `progress(current_frame, total_frames, elapsed_seconds)` signals. `MainWindow.render_progress_update()` uses these to:

- Update the progress bar value and maximum
- Calculate and display ETA using `_format_duration()`
- Update the status label with frame count and time remaining

## Preview Rendering

Preview renders use the same pipeline with two differences:

- `preview_seconds` parameter limits `AudioData.load_audio_data()` to load only the specified duration (5 seconds for live preview, 30 seconds for render preview)
- Output is written to `{data_dir}/preview_output.mp4` instead of the user-specified path

## Caption Delivery Output

`CaptionAnimateTab._create_delivery_output()` writes the final file to a temporary path then renames it to the target, avoiding FFmpeg in-place read/write conflicts. A process lock guards `_captured_process`. Preview temp files are cleaned up on rerender, failure, cancel, and close.

## Post-Render Playback

After a full render completes, `render_finished()` opens a `RenderDialog` — a modal `QDialog` with a `QMediaPlayer`, `QVideoWidget`, `QAudioOutput`, and volume slider. The video loops automatically. Volume persists across dialog instances via a class variable.
