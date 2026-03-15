# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

### Changed

### Fixed

## [0.3.0] - 2026-02-24

### Added

- Added deterministic pipeline tests with shared fixtures and SRT comparison helper.
- Added opt-in integration tests with real audio fixtures and baseline SRTs.
- Added reference transcript comparison with WER-based tolerance for minor transcription drift.
- Added integration test tooling: `--update-baselines` flag and pytest markers.
- Audio fixtures live in `tests/fixtures/audio/`; baselines in `tests/fixtures/baselines/`.
- Added `FormattingConfig`, `TranscriptionConfig`, and `SilenceConfig` as importable dataclasses.
- Added `PipelineMode` enum (`general`, `shorts`, `transcript`) and `--mode` CLI flag (default: `general`).
- Added `mode: PipelineMode` parameter to `transcribe_file()` and `transcribe_batch()` API functions.
- Added diagnostic transcription flags: `--no-condition-on-previous-text`, `--no-speech-threshold`, `--log-prob-threshold`, `--compression-ratio-threshold`, `--vad-filter/--no-vad-filter`.
- Added Shorts mode dual-output: sentence-level SRT plus word-level SRT (default `<stem>.words.srt`, override with `--word-srt`).
- Added Transcript mode large-block chunker and `transcript` preset for paragraph-style output.
- Added optional `speaker` label on `SubtitleBlock` with speaker prefixes in SRT/VTT/ASS outputs when set.
- Added script prompt inputs: `--prompt` and `--prompt-file` (including `.docx` support).
- Added script-guided substitution with `--script` to replace matched segments using script text.
- Added corrected SRT alignment with `--correction-srt` for Shorts word-level regeneration.
- Added optional diarization extra: `pip install local-srt[diarize]`.
- Added `--diarize` and `--hf-token` for speaker-labeled transcript output.

### Changed

- **Breaking:** `ResolvedConfig` is now a nested container; all fields moved to `formatting`, `transcription`, or `silence` sub-configs (e.g. `cfg.max_chars` → `cfg.formatting.max_chars`).
- **Breaking:** `apply_overrides()` now requires nested dict format (`{"formatting": {...}, "transcription": {...}, "silence": {...}}`); flat top-level keys are ignored.
- **Breaking:** Removed `use_silence_split` flag and user-facing `--word-timestamps`; silence detection, word timestamps, and silence alignment are always active.

### Fixed
## 0.2.0 - 2026-02-01

- Local transcription using faster-whisper with ffmpeg-based media decoding.
- CLI `srtgen` supports SRT, VTT, ASS, TXT, and JSON outputs.
- Preset modes for `yt`, `shorts`, and `podcast` to tune chunking and pacing.
- Silence-aware splitting and alignment with optional word-level subtitle output.
- Batch processing with directory scanning, `--outdir`, and `--keep-structure`.
- Model management commands: list, download, and delete cached models.
- Diagnostic output via `--diagnose` and progress/event logging in the CLI.
