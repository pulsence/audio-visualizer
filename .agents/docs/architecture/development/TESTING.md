# Testing

This document describes the current test setup, existing tests, and coverage gaps.

## Test Setup

- **Framework:** pytest
- **Config:** `tests/conftest.py` adds `src/` to `sys.path` so that `audio_visualizer` can be imported directly
- **Run command:** `pytest tests/ -v`
- **Test directory:** `tests/`

## Existing Tests

### test_app_paths.py

- `test_app_paths_use_env_base(monkeypatch, tmp_path)` — Verifies that `get_config_dir()` and `get_data_dir()` respect environment variables (`LOCALAPPDATA` on Windows, `XDG_CONFIG_HOME`/`XDG_DATA_HOME` on Unix). Uses `monkeypatch` to set environment variables and `tmp_path` for isolated directories.

### test_logging.py

- `test_setup_logging_creates_file(monkeypatch, tmp_path)` — Verifies that `setup_logging()` creates a log file at the expected path within the config directory.

### test_media_utils.py

- `test_audio_load_and_chunk()` — Tests `AudioData.load_audio_data()` and `chunk_audio()` with the sample audio file at repo root (`sample_audio.mp3`). Verifies that audio loads successfully and chunks are created.

- `test_video_prepare_and_finalize(tmp_path)` — Tests `VideoData.prepare_container()` and `finalize()`. Creates a temporary video file and verifies the container is properly opened and closed.

## Coverage Gaps

The following areas have no test coverage:

- **Visualizer implementations** — No tests for any of the 14 visualizer types (`prepare_shapes()`, `generate_frame()`)
- **UI components** — No tests for `MainWindow`, `RenderDialog`, or any View classes
- **View validation** — No tests for `validate_view()` or `read_view_values()` on any View subclass
- **Render pipeline** — No integration tests for the full `RenderWorker` pipeline
- **Audio analysis** — No tests for `AudioData.analyze_audio()` (volume and chromagram computation)
- **Update checker** — No tests for `updater.py` functions
- **Settings persistence** — No tests for `_collect_settings()` / `_apply_settings()` serialization roundtrip
- **Color parsing** — No tests for the `_parse_color()` helpers used across chroma views
