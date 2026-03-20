# Testing

This document describes the current test setup, existing tests, and coverage gaps.

## Test Setup

- **Framework:** pytest
- **Config:** `tests/conftest.py` adds `src/` to `sys.path` so that `audio_visualizer` can be imported directly
- **Run command:** `pytest tests/ -v`
- **Test directory:** `tests/`
- **Test count:** 938 tests currently pass across all packages

## Existing Tests

### Core / Original Package

#### test_app_paths.py

- `test_app_paths_use_env_base(monkeypatch, tmp_path)` — Verifies that `get_config_dir()` and `get_data_dir()` respect environment variables (`LOCALAPPDATA` on Windows, `XDG_CONFIG_HOME`/`XDG_DATA_HOME` on Unix). Uses `monkeypatch` to set environment variables and `tmp_path` for isolated directories.

#### test_logging.py

- `test_setup_logging_creates_file(monkeypatch, tmp_path)` — Verifies that `setup_logging()` creates a log file at the expected path within the config directory.

#### test_media_utils.py

- `test_audio_load_and_chunk()` — Tests `AudioData.load_audio_data()` and `chunk_audio()` with the sample audio file at repo root (`sample_audio.mp3`). Verifies that audio loads successfully and chunks are created.

- `test_video_prepare_and_finalize(tmp_path)` — Tests `VideoData.prepare_container()` and `finalize()`. Creates a temporary video file and verifies the container is properly opened and closed.

### Events

#### test_events.py

Tests the shared `AppEvent` protocol from `audio_visualizer.events`:
- `AppEvent` creation with defaults and custom fields
- `AppEventEmitter` subscribe, emit, unsubscribe, enable/disable
- `LoggingBridge` forwarding events to Python logging
- `EventType` and `EventLevel` enum values

### SRT Package

#### test_srt_models.py

Tests all data models in `audio_visualizer.srt.models`:
- `FormattingConfig`, `TranscriptionConfig`, `SilenceConfig` defaults and custom values
- `ResolvedConfig` nested construction
- `PipelineMode` enum values
- `SubtitleBlock` and `WordItem` creation

#### test_srt_config.py

Tests configuration management in `audio_visualizer.srt.config`:
- `PRESETS` dictionary structure and content
- `load_config_file()` with valid/invalid/missing files
- `apply_overrides()` with single and multiple sections

#### test_srt_text_processing.py

Tests text utilities in `audio_visualizer.srt.core.textProcessing`:
- `normalize_spaces()` with various whitespace patterns
- `wrap_text_lines()` with different widths
- `split_text_into_blocks()` with punctuation splitting
- `distribute_time()` proportional timing
- `enforce_timing()` min/max duration constraints

#### test_srt_subtitle_generation.py

Tests subtitle generation in `audio_visualizer.srt.core.subtitleGeneration`:
- `collect_words()` from mock segments
- `chunk_segments_to_subtitles()` with various configurations
- `chunk_words_to_subtitles()` with silence-aware splitting
- `words_to_subtitles()` one-word-per-subtitle mode
- `apply_silence_alignment()` timing adjustment
- `hygiene_and_polish()` cleanup and merging

#### test_srt_alignment.py

Tests alignment utilities in `audio_visualizer.srt.core.alignment`:
- `align_corrected_srt()` with mock corrected SRT files
- `align_script_to_segments()` with script sentences and mock segments

#### test_srt_output_writers.py

Tests output writers in `audio_visualizer.srt.io.outputWriters`:
- `write_srt()` format and content
- `write_vtt()` WebVTT format
- `write_ass()` ASS format
- `write_txt()` plain text
- `write_json_bundle()` complete JSON output
- Time formatting functions (`format_srt_time`, `format_vtt_time`, `format_ass_time`)

#### test_srt_events.py

Tests SRT-specific event emission patterns:
- Event emission during model loading
- Event emission during transcription stages

#### test_srt_format_helpers.py

Tests `format_duration()` with various time values.

#### test_srt_audio.py

Tests audio helpers (may require ffmpeg):
- `detect_silences()` with mock audio
- `to_wav_16k_mono()` conversion

#### test_srt_system.py

Tests system helpers in `audio_visualizer.srt.io.systemHelpers`:
- `ensure_parent_dir()` directory creation
- `ffmpeg_ok()` / `ffprobe_ok()` dependency checks
- `run_cmd_text()` command execution

#### test_srt_script_reader.py

Tests `read_docx()` for .docx file reading.

#### test_srt_smoke.py

Smoke tests for SRT package imports and lazy loading:
- Package importability
- Lazy-loaded attribute access
- Public API function signatures

### Caption Package

#### test_caption_sizing.py

Tests overlay size computation in `audio_visualizer.caption.core.sizing`:
- `SizeCalculator` with various presets
- `OverlaySize` dataclass
- `compute_anchor_position()` center calculation
- Even dimension enforcement

#### test_caption_measurement.py

Tests text measurement in `audio_visualizer.caption.text.measurement`:
- `measure_multiline()` with single and multiple lines
- `measure_single_line()` width calculation

#### test_caption_wrapper.py

Tests text wrapping in `audio_visualizer.caption.text.wrapper`:
- `wrap_text_to_width()` with various widths and fonts
- Preservation of existing line breaks

#### test_caption_word_reveal.py

Tests the word reveal animation plugin:
- `WordRevealAnimation` parameter validation
- ASS override tag generation
- Event application

#### test_caption_smoke.py

Smoke tests for caption package imports and lazy loading:
- Package importability
- Lazy-loaded attribute access
- Public API function signatures

### Integration

#### test_integration_smoke.py

Cross-package integration tests:
- Both srt and caption packages can be imported together
- Shared events module works across packages
- No import conflicts between packages

## Phase 11 Test Updates

- Tests updated to remove references to `VALID_LAYER_TYPES`, `ChangeAudioSourceCommand`, and `PRESET_NAMES`.
- Legacy audio source migration tests removed.
- Added Render Composition command-generation tests that verify real FFmpeg input labels, audio/video loop handling, and single-layer preview timing.
- Added UI tests for audio full-length reset semantics, visual z-order ordering in the unified layer list, and Caption Animate audio-path/session-asset synchronization.

## Coverage Gaps

The following areas have no test coverage:

- **Visualizer implementations** — No tests for any of the 14 visualizer types (`prepare_shapes()`, `generate_frame()`)
- **UI components** — `MainWindow`, major tabs, and some view helpers are covered, but `RenderDialog` and most individual View subclasses still lack direct tests
- **View validation** — `GeneralSettingsView` has path-normalization tests, but most View subclasses still lack direct `validate_view()` / `read_view_values()` coverage
- **Render pipeline** — No integration tests for the full `RenderWorker` pipeline
- **Audio analysis** — No tests for `AudioData.analyze_audio()` (volume and chromagram computation)
- **Update checker** — No tests for `updater.py` functions
- **Settings persistence** — Main window and several tabs have settings roundtrip tests, but there is no single end-to-end test covering the full persisted schema across every tab and session asset combination
- **Color parsing** — No tests for the `_parse_color()` helpers used across chroma views
- **SRT full pipeline** — No end-to-end test of `transcribe_file()` (requires a Whisper model download)
- **Caption full render** — No end-to-end test of `render_subtitle()` (requires FFmpeg with libass support)
- **ModelManager** — No tests for thread-safe model loading/unloading lifecycle
- **Diarization** — No tests for `diarization.py` (requires pyannote.audio)
- **Caption animations (partial)** — Only `WordRevealAnimation` is tested; `FadeAnimation`, `SlideUpAnimation`, `ScaleSettleAnimation`, and `BlurSettleAnimation` lack dedicated tests
- **PresetLoader** — No tests for multi-source preset resolution (file, directory, YAML)
- **FFmpegRenderer** — No tests for FFmpeg command construction or progress parsing
- **StyleBuilder** — No tests for ASS style generation from presets
