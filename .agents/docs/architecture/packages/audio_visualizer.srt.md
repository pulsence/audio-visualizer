# audio_visualizer.srt

Subtitle generation from media files using faster-whisper. Provides a pipeline that transcribes audio/video to timed subtitle blocks and writes them in multiple output formats (SRT, VTT, ASS, TXT, JSON). Heavy imports are deferred until first access via `__getattr__`-based lazy loading.

## Package Exports (`__init__.py`)

Lazy-loaded via `_EXPORTS` dict and `__getattr__`:

| Export | Source Module | Description |
|--------|--------------|-------------|
| `transcribe_file` | `.srtApi` | Transcribe a single media file and write outputs |
| `load_model` | `.srtApi` | Load a faster-whisper model for reuse |
| `TranscriptionResult` | `.srtApi` | Public result dataclass for transcription |
| `ModelManager` | `.modelManager` | Thread-safe Whisper model lifecycle manager |
| `ModelInfo` | `.modelManager` | Metadata about a loaded model |
| `FormattingConfig` | `.models` | Subtitle formatting constraints |
| `TranscriptionConfig` | `.models` | Model transcription tuning parameters |
| `SilenceConfig` | `.models` | Silence detection parameters |
| `ResolvedConfig` | `.models` | Nested configuration container |
| `PipelineMode` | `.models` | Enum: GENERAL, SHORTS, TRANSCRIPT |
| `SubtitleBlock` | `.models` | A subtitle cue with timing and text |
| `WordItem` | `.models` | A single transcribed word with timing |
| `PRESETS` | `.config` | Built-in configuration presets (shorts, yt, podcast, transcript) |
| `load_config_file` | `.config` | Load configuration from a JSON file |
| `apply_overrides` | `.config` | Apply overrides to a base ResolvedConfig |

## Public API (`srtApi.py`)

### `load_model(model_name, device, strict_cuda, emitter=None) -> (model, device_used, compute_type)`

Loads a faster-whisper model. Emits `MODEL_LOAD` events on success or failure. Supports `device` values: `"auto"`, `"cpu"`, `"cuda"`. When `strict_cuda=True`, raises `RuntimeError` if CUDA initialization fails; otherwise falls back to CPU.

### `transcribe_file(*, input_path, output_path, fmt, cfg, model, ...) -> TranscriptionResult`

Transcribes a single media file through the full pipeline:
1. Convert audio to 16kHz mono WAV
2. Run faster-whisper transcription
3. Chunk and format subtitle blocks
4. Write outputs in the requested format

All parameters after `*` are keyword-only. Emits `STAGE` and `PROGRESS` events via the optional `emitter` parameter. Returns a `TranscriptionResult` with `success=False` on error (does not raise).

### `TranscriptionResult`

Dataclass with fields: `success`, `input_path`, `output_path`, `subtitles`, `segments`, `device_used`, `compute_type_used`, `error`, `transcript_path`, `segments_path`, `json_bundle_path`, `elapsed`.

## Model Manager (`modelManager.py`)

### `ModelManager`

Thread-safe Whisper model lifecycle manager. Holds a single model instance and its metadata. Uses a `threading.Lock` for all access.

**Methods:**
- `load(model_name, device="auto", strict_cuda=False) -> model` -- Load or reuse a model. If a different model is loaded, unloads it first.
- `get_model() -> Optional[model]` -- Return the current model instance.
- `is_loaded() -> bool` -- Check if a model is currently loaded.
- `model_info() -> Optional[ModelInfo]` -- Return metadata about the loaded model.
- `unload()` -- Release the currently loaded model.

### `ModelInfo`

Dataclass with fields: `model_name`, `device`, `compute_type`.

## Data Models (`models.py`)

### `FormattingConfig`

Subtitle formatting and timing constraints. Key fields: `max_chars` (42), `max_lines` (2), `target_cps` (17.0), `min_dur` (1.0), `max_dur` (6.0), `allow_commas`, `allow_medium`, `prefer_punct_splits`, `min_gap` (0.08), `pad` (0.0).

### `TranscriptionConfig`

Model tuning parameters: `vad_filter`, `condition_on_previous_text`, `no_speech_threshold`, `log_prob_threshold`, `compression_ratio_threshold`, `initial_prompt`.

### `SilenceConfig`

Silence detection parameters: `silence_min_dur` (0.2), `silence_threshold_db` (-35.0).

### `ResolvedConfig`

Nested container holding `formatting: FormattingConfig`, `transcription: TranscriptionConfig`, `silence: SilenceConfig`.

### `PipelineMode`

Enum: `GENERAL`, `SHORTS`, `TRANSCRIPT`. Controls subtitle chunking strategy.

### `SubtitleBlock`

A subtitle cue: `start: float`, `end: float`, `lines: List[str]`, `speaker: Optional[str]`.

### `WordItem`

A single transcribed word: `start: float`, `end: float`, `text: str`.

## Configuration (`config.py`)

### `PRESETS`

Built-in preset dictionaries: `"shorts"`, `"yt"`, `"podcast"`, `"transcript"`. Each preset defines `formatting`, `transcription`, and `silence` sections.

### `load_config_file(path: Optional[str]) -> Dict`

Load a JSON config file. Returns empty dict if path is None.

### `apply_overrides(base: ResolvedConfig, overrides: Dict) -> ResolvedConfig`

Apply configuration overrides to a base config, returning a new `ResolvedConfig`.

## Core Subpackage (`core/`)

### Pipeline (`core/pipeline.py`)

`transcribe_file_internal(...)` -- The internal transcription pipeline called by `srtApi.transcribe_file`. Orchestrates four stages:
1. Audio conversion (to 16kHz mono WAV via ffmpeg)
2. Transcription (via faster-whisper model)
3. Chunking and formatting (subtitle block generation)
4. Output writing (SRT/VTT/ASS/TXT/JSON)

Emits `STAGE`, `PROGRESS`, and `LOG` events throughout. Supports diarization, script alignment, correction SRT alignment, and dry-run mode.

Returns `CoreTranscriptionResult` dataclass.

### Whisper Wrapper (`core/whisperWrapper.py`)

`init_whisper_model_internal(model_name, device, strict_cuda, emitter=None) -> (model, device_used, compute_type)` -- Initializes a `faster_whisper.WhisperModel` with automatic device and compute type selection. Tries CUDA with float16 first, falls back to CPU with int8.

### Subtitle Generation (`core/subtitleGeneration.py`)

Functions for converting transcription segments and words into subtitle blocks:

- `collect_words(segments) -> List[WordItem]` -- Extract word-level timing from segments
- `chunk_segments_to_subtitles(segments, cfg) -> List[SubtitleBlock]` -- Segment-level subtitle generation
- `chunk_words_to_subtitles(words, cfg, silences) -> List[SubtitleBlock]` -- Word-level with silence-aware splitting
- `chunk_segments_to_transcript_blocks(segments, cfg, silences) -> List[SubtitleBlock]` -- Larger transcript-style blocks with speaker labels
- `words_to_subtitles(words) -> List[SubtitleBlock]` -- One word per subtitle
- `apply_silence_alignment(subs, silences) -> List[SubtitleBlock]` -- Align timing to silence boundaries
- `hygiene_and_polish(subs, *, min_gap, pad, silence_intervals) -> List[SubtitleBlock]` -- Remove empties, sort, merge duplicates, enforce gaps, monotonic timing

### Text Processing (`core/textProcessing.py`)

Low-level text manipulation:

- `normalize_spaces(text) -> str` -- Collapse whitespace, strip
- `wrap_text_lines(text, max_chars) -> List[str]` -- Word-wrap into lines
- `split_text_into_blocks(text, max_chars, max_lines, ...) -> List[str]` -- Hierarchical punctuation splitting for subtitle-sized blocks
- `distribute_time(start, end, parts) -> List[Tuple]` -- Proportional timing distribution
- `enforce_timing(blocks, min_dur, max_dur) -> List[Tuple]` -- Enforce min/max duration constraints

### Alignment (`core/alignment.py`)

- `align_corrected_srt(corrected_srt, words) -> List[WordItem]` -- Align corrected SRT words to whisper word timings using `difflib.SequenceMatcher`
- `align_script_to_segments(script_sentences, segments) -> List[object]` -- Replace segment text with script sentences using diff-based matching

### Diarization (`core/diarization.py`)

Optional speaker diarization via pyannote.audio:

- `is_diarization_available() -> bool` -- Check if pyannote.audio is installed
- `load_diarization_pipeline(hf_token) -> pipeline` -- Load pyannote speaker diarization pipeline
- `run_diarization(pipeline, audio_path) -> List[Tuple]` -- Run diarization, return (start, end, speaker_label) tuples
- `assign_speakers(segments, diarization) -> List` -- Assign speakers to segments by maximum overlap

## IO Subpackage (`io/`)

### Audio Helpers (`io/audioHelpers.py`)

- `detect_silences(wav_path, *, min_silence_dur, silence_threshold_db) -> List[Tuple]` -- Detect silent regions using ffmpeg's silencedetect filter
- `to_wav_16k_mono(input_path, wav_path)` -- Convert audio/video to 16kHz mono WAV

### Output Writers (`io/outputWriters.py`)

- `write_srt(subs, out_path, *, max_chars, max_lines)` -- Write SRT format
- `write_vtt(subs, out_path, *, max_chars, max_lines)` -- Write WebVTT format
- `write_ass(subs, out_path, *, max_chars, max_lines)` -- Write ASS format
- `write_txt(subs, out_path)` -- Write plain text transcript
- `write_json_bundle(out_path, *, input_file, device_used, ...)` -- Write complete JSON bundle with metadata
- `segments_to_jsonable(segments, *, include_words) -> List[Dict]` -- Convert segments to JSON-serializable format

All file writers use atomic write (write to `.tmp`, then `os.replace`).

### Script Reader (`io/scriptReader.py`)

- `read_docx(path) -> str` -- Read a `.docx` file via `python-docx` and return normalized text (capped at 900 chars)

### System Helpers (`io/systemHelpers.py`)

- `ensure_parent_dir(path)` -- Create parent directory if needed
- `ffmpeg_ok() -> bool` / `ffprobe_ok() -> bool` -- Check for ffmpeg/ffprobe on PATH
- `run_cmd_text(cmd) -> (returncode, stdout, stderr)` -- Run a command and capture output
- `probe_duration_seconds(path) -> Optional[float]` -- Probe media file duration via ffprobe

## Model Management (`modelManagement.py`)

Standalone model management utilities (separate from `ModelManager`):

- `diagnose() -> DiagnoseResult` -- System diagnostics (Python version, platform, ffmpeg/ffprobe versions, faster-whisper version)
- `list_downloaded_models() -> List[Tuple[str, str]]` -- List downloaded Whisper models (name, path)
- `list_available_models() -> List[str]` -- List all available Whisper model names
- `download_model(model_name) -> str` -- Download a model from the internet
- `delete_model(model_name) -> str` -- Delete a cached model from disk

## Format Helpers (`formatHelpers.py`)

- `format_duration(seconds) -> str` -- Format duration as HH:MM:SS or MM:SS

## Event Integration

All public API functions accept an optional `emitter: AppEventEmitter` parameter from `audio_visualizer.events`. Events emitted:

| EventType | When |
|-----------|------|
| `LOG` | General status messages and errors |
| `PROGRESS` | Transcription progress (percent, segment count, ETA) |
| `STAGE` | Pipeline stage transitions (1. Convert audio, 2. Transcribe, 3. Chunk, 4. Write) |
| `MODEL_LOAD` | Model load success/failure with device and compute type info |

## Dependencies

- **faster-whisper** -- Whisper speech recognition model
- **python-docx** -- .docx file reading for script alignment
- **ffmpeg** (external) -- Audio conversion and silence detection
- **pyannote.audio** (optional) -- Speaker diarization
