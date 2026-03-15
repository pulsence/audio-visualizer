# v0.6.0 Stage Two - Package Integration Implementation Plan

This plan implements Phase 2 of the v0.6.0 work: merging Local SRT and Caption Animator into the Audio Visualizer codebase as internal packages. All decisions follow from the research plan in `V_0_6_0_RESEARCH_PLAN_2.md`.

**Scope:** Package integration only. GUI tab work (Stage Three) is out of scope.

**Source research:** `V_0_6_0_RESEARCH_PLAN_2.md`

---

## Phase 1: Shared Event Protocol and Infrastructure

### 1.1: Shared Event Protocol

Create the app-wide event protocol that both merged packages will emit through. This replaces Local SRT's `BaseEvent` hierarchy and Caption Animator's `RenderEvent`/`EventType` with a single system.

**Tasks:**
- Define `EventLevel` enum mapping to Python `logging` levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- Define `EventType` enum covering all event kinds from both packages: `LOG`, `PROGRESS`, `STAGE`, `JOB_START`, `JOB_COMPLETE`, `RENDER_START`, `RENDER_PROGRESS`, `RENDER_COMPLETE`, `MODEL_LOAD`
- Define `AppEvent` dataclass with fields: `event_type`, `message`, `level`, `timestamp`, `data` (optional dict for domain-specific payload like percent, frame, speed, etc.)
- Implement `AppEventEmitter` with `subscribe()`, `unsubscribe()`, and `emit()` methods. Include `enable()`/`disable()` toggle from Caption Animator's emitter.
- Create/update tests for the event protocol
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create `src/audio_visualizer/events.py`
- Create `tests/test_events.py`

**Success criteria:** `AppEvent`, `AppEventEmitter`, `EventLevel`, and `EventType` are importable from `audio_visualizer.events`. All unit tests pass. The protocol covers every event kind currently emitted by both Local SRT and Caption Animator.

### 1.2: Event-to-Logging Bridge

Create a thin bridge subscriber that forwards `AppEvent` instances to Python `logging`, so all package diagnostic output reaches the host app's log file.

**Tasks:**
- Implement `LoggingBridge` class that accepts a `logging.Logger` and subscribes to an `AppEventEmitter`
- Map `EventLevel` values to Python `logging` levels (`DEBUG` → `logging.DEBUG`, etc.)
- Format event messages using `event.message` and relevant `event.data` fields
- Filter out high-frequency progress events from the log file (only log `PROGRESS` at `DEBUG` level to avoid log spam)
- Create/update tests for the logging bridge
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/events.py` (add `LoggingBridge` class)
- Modify `tests/test_events.py` (add bridge tests)

**Success criteria:** A `LoggingBridge` connected to an `AppEventEmitter` forwards events to a Python `logging.Logger` at the correct log levels. Progress events are filtered to `DEBUG` level. Tests verify the bridge behavior.

### 1.3: Update Dependencies in pyproject.toml

Add all new dependencies from both packages to the host app's default install.

**Tasks:**
- Add `faster-whisper>=1.0.0` (from Local SRT)
- Add `python-docx>=1.1.0` (from Local SRT)
- Add `pysubs2>=1.6.0` (from Caption Animator)
- Add `PyYAML>=6.0` (from Caption Animator)
- Add `pyannote.audio>=3.0` under a `[diarize]` optional extra (from Local SRT)
- Add `pytest-mock` to the `[dev]` extra (needed for ported tests)
- Verify existing `Pillow` version constraint is compatible with Caption Animator's `>=10.0.0` requirement (current is `==11.3.0`, which satisfies it)
- Run `pip install -e .` to verify dependency resolution
- Create/update tests for new features
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `pyproject.toml`

**Success criteria:** `pip install -e .` succeeds. All new dependencies are resolvable. Existing tests still pass.

### 1.4: Phase 1 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured

**Phase 1 Changelog:**
- Added shared `AppEvent` protocol with `EventLevel`, `EventType`, `AppEventEmitter`
- Added `LoggingBridge` to forward package events to Python `logging`
- Added `faster-whisper`, `python-docx`, `pysubs2`, `PyYAML` as default dependencies
- Added `[diarize]` optional extra for `pyannote.audio`

---

## Phase 2: Local SRT Package Integration

### 2.1: Create Package Structure and Relocate Modules

Create the `audio_visualizer.srt` package directory structure, move all retained Local SRT source files into it, rename modules to match host app conventions, and rewrite all internal imports.

**Target directory structure:**

```
src/audio_visualizer/srt/
├── __init__.py                 # Lazy-loading facade (task 2.5)
├── srtApi.py                   # Public API (from api.py)
├── models.py                   # Data classes (from models.py)
├── config.py                   # Presets, config loading (from config.py)
├── core/
│   ├── __init__.py
│   ├── pipeline.py             # Main transcription pipeline (from core.py)
│   ├── whisperWrapper.py       # Whisper model init (from whisper_wrapper.py)
│   ├── textProcessing.py       # Text splitting/wrapping (from text_processing.py)
│   ├── subtitleGeneration.py   # Subtitle block building (from subtitle_generation.py)
│   ├── alignment.py            # Corrected-SRT and script alignment (from alignment.py)
│   └── diarization.py          # Speaker diarization (from diarization.py)
├── io/
│   ├── __init__.py
│   ├── audioHelpers.py         # WAV conversion, silence detection (from audio.py)
│   ├── systemHelpers.py        # ffmpeg/ffprobe checks, file ops (from system.py)
│   ├── outputWriters.py        # .srt, .vtt, .ass, .txt, JSON bundle (from output_writers.py)
│   └── scriptReader.py         # .docx/.txt prompt loading (from script_reader.py)
├── modelManagement.py          # Diagnostics, cache management (from model_management.py)
└── formatHelpers.py            # format_duration() utility (from logging_utils.py)
```

**Tasks:**
- Create the directory tree under `src/audio_visualizer/srt/`
- Copy each source file from `Projects to integrate/Local SRT/src/local_srt/` to its target location using the rename mapping above
- Remove `batch.py` (dropped per research plan decisions)
- Remove `cli.py` (CLI entry point dropped per research plan decisions)
- Rewrite all `from local_srt.X import Y` and `import local_srt.X` statements to use `audio_visualizer.srt` paths throughout every relocated module
- Update cross-module references to use new module names (e.g., `from audio_visualizer.srt.core.pipeline import ...` instead of `from local_srt.core import ...`)
- Verify every module is importable with `python -c "from audio_visualizer.srt.X import Y"` for critical exports
- Create/update tests for new features
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create all files listed in the target directory structure above (except `__init__.py` root, which is task 2.5)
- Create placeholder `src/audio_visualizer/srt/__init__.py` (empty or minimal, replaced in task 2.5)

**Success criteria:** All Local SRT modules are relocated and importable under `audio_visualizer.srt.*`. No references to `local_srt` remain in the relocated code. `batch.py` and `cli.py` are not present. Internal imports resolve correctly.

### 2.2: Create Reusable Model Manager

Add a first-class model lifecycle manager inside `audio_visualizer.srt` so that the GUI layer can reuse loaded models across transcription jobs without reloading.

**Tasks:**
- Create `ModelManager` class that wraps `whisperWrapper.init_whisper_model_internal()`
- Support `load()`, `get_model()`, `is_loaded()`, `unload()`, and `model_info()` methods
- Ensure thread-safety for future Qt worker usage (the model manager may be accessed from multiple threads)
- Emit `MODEL_LOAD` events through the shared `AppEventEmitter`
- Store model metadata (name, device, compute type) for diagnostics
- Create/update tests for the model manager
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create `src/audio_visualizer/srt/modelManager.py`
- Create `tests/test_srt_model_manager.py`

**Success criteria:** `ModelManager` loads a Whisper model once and returns the same instance on subsequent calls. `unload()` releases the model. `model_info()` returns device and compute type. Events are emitted through the shared protocol.

### 2.3: Adapt Local SRT Events to Shared Protocol

Replace the Local SRT event system with the shared `AppEvent` protocol from Phase 1.

**Tasks:**
- Update `srtApi.py` (`transcribe_file`, `load_model`) to accept an `AppEventEmitter` instead of `EventHandler`
- Update `core/pipeline.py` to emit `AppEvent` instances instead of `LogEvent`, `StageEvent`, `ProgressEvent`, etc.
- Map Local SRT event types to shared `EventType` values:
  - `LogEvent` → `EventType.LOG` (preserve `level`)
  - `WarnEvent` → `EventType.LOG` with `EventLevel.WARNING`
  - `ErrorEvent` → `EventType.LOG` with `EventLevel.ERROR`
  - `ProgressEvent` → `EventType.PROGRESS` (preserve percent, segment_count, elapsed, eta in `data`)
  - `StageEvent` → `EventType.STAGE` (preserve stage name, number, total in `data`)
  - `FileStartEvent` → `EventType.JOB_START`
  - `FileCompleteEvent` → `EventType.JOB_COMPLETE`
  - `ModelLoadEvent` → `EventType.MODEL_LOAD`
- Remove the old `events.py` file from the srt package (the shared protocol in `audio_visualizer.events` replaces it)
- Update the model manager from task 2.2 if needed
- Update `core/whisperWrapper.py` to use the shared emitter
- Create/update tests for event emission
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/srt/srtApi.py`
- Modify `src/audio_visualizer/srt/core/pipeline.py`
- Modify `src/audio_visualizer/srt/core/whisperWrapper.py`
- Modify `src/audio_visualizer/srt/modelManager.py`
- Delete `src/audio_visualizer/srt/events.py` (if it was created as a temporary shim in 2.1)
- Create or modify `tests/test_srt_events.py`

**Success criteria:** All `audio_visualizer.srt` event emission uses the shared `AppEvent` protocol. No references to old Local SRT event classes remain. Event data payloads preserve the information previously carried by the old event types.

### 2.4: Relocate Presets and Configs to App Data Directories

Move Local SRT's config example files into the app's data directory structure and update config loading to use `audio_visualizer.app_paths.get_data_dir()`.

**Tasks:**
- Update `config.py` to load JSON config files from `get_data_dir() / "srt" / "configs"` instead of the old package-relative `configs/` directory
- Keep the built-in `PRESETS` dictionary in code as the primary source (no change needed, these are already in-code)
- Provide a first-run helper that copies bundled example configs to the data directory if they don't exist
- Include the example configs (`podcast_config.json`, `yt_config.json`) as package data under `src/audio_visualizer/srt/`
- Create/update tests for config loading from the new paths
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/srt/config.py`
- Create `src/audio_visualizer/srt/configs/podcast_config.json` (copy from Local SRT)
- Create `src/audio_visualizer/srt/configs/yt_config.json` (copy from Local SRT)
- Modify `pyproject.toml` (add package-data entry for config files)
- Create or modify `tests/test_srt_config.py`

**Success criteria:** `load_config_file()` resolves config files from the app data directory. Built-in presets remain accessible in code. Example configs are bundled as package data and can be copied to the user's data directory.

### 2.5: Create Lazy-Loading __init__.py Facade

Create the `audio_visualizer.srt` package facade that uses `__getattr__`-based lazy loading to defer heavy imports.

**Tasks:**
- Implement `__getattr__` lazy loading following Local SRT's existing pattern
- Export the public API surface: `transcribe_file`, `load_model`, `TranscriptionResult`, `ModelManager`, `ResolvedConfig`, `PipelineMode`, `SubtitleBlock`, `WordItem`, `FormattingConfig`, `TranscriptionConfig`, `SilenceConfig`, `PRESETS`, `load_config_file`, `apply_overrides`
- Do NOT export batch-related APIs (dropped)
- Verify that `import audio_visualizer.srt` does not trigger loading of `faster_whisper` or other heavy dependencies
- Define `__all__` for the exported names
- Create/update tests verifying lazy loading behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/srt/__init__.py`
- Create `tests/test_srt_imports.py`

**Success criteria:** `import audio_visualizer.srt` succeeds without loading `faster_whisper`. Accessing `audio_visualizer.srt.transcribe_file` triggers the lazy import. All public names are listed in `__all__`.

### 2.6: Phase 2 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify no references to `local_srt` remain anywhere in `src/audio_visualizer/`
- Verify `batch.py` and `cli.py` are not present

**Phase 2 Changelog:**
- Added `audio_visualizer.srt` package with full transcription pipeline
- Added `ModelManager` for reusable Whisper model lifecycle
- Restructured Local SRT into `core/`, `io/` subpackages with camelCase module names
- Adapted event system to shared `AppEvent` protocol
- Relocated config examples to app data directory structure
- Implemented lazy-loading facade for deferred `faster-whisper` imports
- Dropped batch transcription API and standalone `srtgen` CLI entry point

---

## Phase 3: Caption Animator Package Integration

### 3.1: Create Package Structure and Relocate Modules

Create the `audio_visualizer.caption` package directory structure, move all Caption Animator source files into it, rename modules to match host app conventions, and rewrite all internal imports.

**Target directory structure:**

```
src/audio_visualizer/caption/
├── __init__.py                     # Lazy-loading facade (task 3.5)
├── captionApi.py                   # Public API (from api.py)
├── core/
│   ├── __init__.py
│   ├── config.py                   # PresetConfig, AnimationConfig (from core/config.py)
│   ├── sizing.py                   # SizeCalculator (from core/sizing.py)
│   ├── style.py                    # StyleBuilder (from core/style.py)
│   └── subtitle.py                 # SubtitleFile (from core/subtitle.py)
├── text/
│   ├── __init__.py
│   ├── measurement.py              # Text measurement (from text/measurement.py)
│   ├── wrapper.py                  # Text wrapping (from text/wrapper.py)
│   └── utils.py                    # Text utilities (from text/utils.py)
├── presets/
│   ├── __init__.py
│   ├── defaults.py                 # Built-in presets (from presets/defaults.py)
│   └── loader.py                   # Preset loading (from presets/loader.py)
├── rendering/
│   ├── __init__.py
│   ├── ffmpegRenderer.py           # FFmpeg renderer (from rendering/ffmpeg.py)
│   └── progressTracker.py          # Progress tracking (from rendering/progress.py)
├── animations/
│   ├── __init__.py
│   ├── baseAnimation.py            # Base class (from animations/base.py)
│   ├── registry.py                 # Plugin registry (from animations/registry.py)
│   ├── fadeAnimation.py            # Fade (from animations/fade.py)
│   ├── slideAnimation.py           # Slide (from animations/slide.py)
│   ├── scaleAnimation.py           # Scale (from animations/scale.py)
│   ├── blurAnimation.py            # Blur (from animations/blur.py)
│   └── wordRevealAnimation.py      # Word reveal (from animations/word_reveal.py)
└── utils/
    ├── __init__.py
    └── files.py                    # File utilities (from utils/files.py)
```

**Tasks:**
- Create the directory tree under `src/audio_visualizer/caption/`
- Copy each source file from `Projects to integrate/Caption Animator/src/caption_animator/` to its target location using the rename mapping above
- Remove `cli/` directory entirely (CLI entry point dropped per research plan decisions)
- Remove `__main__.py` (CLI entry removed)
- Rewrite all `from caption_animator.X import Y` and `import caption_animator.X` statements to use `audio_visualizer.caption` paths
- Remove dead config fields from `PresetConfig`: `video_codec`, `video_quality`, `h264_crf`, `prores_profile` (confirmed unused by the rendering code path — `FFmpegRenderer` uses its own `quality` parameter)
- Remove dead CLI flags that were parser-only: `--strip-overrides`, `--no-preset-for-ass` are gone with the CLI
- Verify every module is importable with `python -c "from audio_visualizer.caption.X import Y"` for critical exports
- Create/update tests for new features
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create all files listed in the target directory structure above (except root `__init__.py`, which is task 3.5)
- Create placeholder `src/audio_visualizer/caption/__init__.py`

**Success criteria:** All Caption Animator modules are relocated and importable under `audio_visualizer.caption.*`. No references to `caption_animator` remain in the relocated code. `cli/` and `__main__.py` are not present. Dead config fields and parser-only flags are removed.

### 3.2: Adapt Caption Events to Shared Protocol

Replace the Caption Animator event system with the shared `AppEvent` protocol from Phase 1.

**Tasks:**
- Update `captionApi.py` (`render_subtitle`) to accept an `AppEventEmitter` instead of separate `on_progress`/`on_event` callbacks
- Maintain backward compatibility by also accepting the old callback signatures during the transition (convert internally to emitter subscriptions)
- Update `rendering/ffmpegRenderer.py` to emit `AppEvent` instances instead of `RenderEvent`
- Update `rendering/progressTracker.py` to use the shared emitter
- Map Caption Animator event types to shared `EventType` values:
  - `EventType.STEP` → `EventType.STAGE`
  - `EventType.RENDER_START` → `EventType.RENDER_START`
  - `EventType.RENDER_PROGRESS` → `EventType.RENDER_PROGRESS` (preserve frame, time, speed in `data`)
  - `EventType.RENDER_COMPLETE` → `EventType.RENDER_COMPLETE`
  - `EventType.DEBUG` → `EventType.LOG` with `EventLevel.DEBUG`
  - `EventType.WARNING` → `EventType.LOG` with `EventLevel.WARNING`
  - `EventType.ERROR` → `EventType.LOG` with `EventLevel.ERROR`
- Remove the old `core/events.py` from the caption package (replaced by shared protocol)
- Create/update tests for event emission
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/caption/captionApi.py`
- Modify `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- Modify `src/audio_visualizer/caption/rendering/progressTracker.py`
- Delete `src/audio_visualizer/caption/core/events.py`
- Create or modify `tests/test_caption_events.py`

**Success criteria:** All `audio_visualizer.caption` event emission uses the shared `AppEvent` protocol. No references to old Caption Animator event classes remain. The `on_progress` and `on_event` callback parameters on `render_subtitle()` still work via internal adaptation.

### 3.3: Fix Preset Loading for Embedded Usage

Update the preset system to work without cwd-relative path assumptions now that the package is embedded inside the host app.

**Tasks:**
- Update `PresetLoader.__init__()` default `preset_dirs` to use `audio_visualizer.app_paths.get_data_dir() / "caption" / "presets"` instead of `Path("presets")`
- Keep built-in presets (`clean_outline`, `modern_box`) available via `defaults.py` in-code — these require no file system access
- Copy Caption Animator's example preset files into `src/audio_visualizer/caption/presets/examples/` so the merged package still ships editable file-based presets
- Provide a first-run helper that copies bundled example presets to the data directory if they don't exist
- Load bundled example presets via package resources instead of cwd-relative paths
- Update `captionApi.py` to pass the corrected preset directories when constructing `PresetLoader`
- Modify packaging so the bundled example preset files are included in installs
- Create/update tests for preset loading from the new paths
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/caption/presets/loader.py`
- Modify `src/audio_visualizer/caption/captionApi.py`
- Create `src/audio_visualizer/caption/presets/examples/preset.json`
- Create `src/audio_visualizer/caption/presets/examples/word_highlight.json`
- Modify `pyproject.toml` (add package-data entry for example preset files)
- Create or modify `tests/test_caption_presets.py`

**Success criteria:** `PresetLoader` resolves presets from the app data directory. Built-in presets load without file system access. Bundled example preset files are shipped with the package and can be copied into the user's data directory. No cwd-relative path assumptions remain.

### 3.4: Remove Caption Animator Old Event Module

Ensure the old Caption Animator `core/events.py` is fully removed and all references point to the shared protocol.

**Tasks:**
- Verify `core/events.py` was deleted in task 3.2
- Search for any remaining references to `RenderEvent`, `EventType` (the old one), or `EventHandler` (Caption Animator's Protocol class) across the caption package
- Update any remaining references to use the shared `AppEvent` types
- Verify all caption package modules import events from `audio_visualizer.events`
- Create/update tests for new features
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Potentially modify any remaining files in `src/audio_visualizer/caption/` that reference old event types

**Success criteria:** No references to `RenderEvent`, old `EventType`, or Caption Animator's `EventHandler` Protocol remain in the caption package.

### 3.5: Create Lazy-Loading __init__.py Facade

Create the `audio_visualizer.caption` package facade using `__getattr__`-based lazy loading, matching the pattern established in `audio_visualizer.srt`.

**Tasks:**
- Implement `__getattr__` lazy loading following the same pattern as `audio_visualizer.srt`
- Export the public API surface: `render_subtitle`, `RenderConfig`, `RenderResult`, `list_presets`, `list_animations`, `PresetConfig`, `AnimationConfig`, `SubtitleFile`, `SizeCalculator`, `StyleBuilder`, `FFmpegRenderer`, `PresetLoader`, `AnimationRegistry`, `BaseAnimation`
- Verify that `import audio_visualizer.caption` does not trigger loading of `pysubs2`, `Pillow`, or `PyYAML`
- Define `__all__` for the exported names
- Create/update tests verifying lazy loading behavior
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Modify `src/audio_visualizer/caption/__init__.py`
- Create `tests/test_caption_imports.py`

**Success criteria:** `import audio_visualizer.caption` succeeds without loading `pysubs2`. Accessing `audio_visualizer.caption.render_subtitle` triggers the lazy import. All public names are listed in `__all__`.

### 3.6: Phase 3 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify no references to `caption_animator` remain anywhere in `src/audio_visualizer/`
- Verify `cli/` and `__main__.py` are not present
- Verify dead config fields (`video_codec`, `video_quality`, `h264_crf`, `prores_profile`) are removed

**Phase 3 Changelog:**
- Added `audio_visualizer.caption` package with full subtitle rendering pipeline
- Preserved high-level `render_subtitle()` API as the app-facing entry point
- Retained external ffmpeg/libass renderer
- Adapted event system to shared `AppEvent` protocol
- Fixed preset loading for embedded usage (no cwd-relative paths)
- Implemented lazy-loading facade for deferred `pysubs2`/`Pillow` imports
- Removed dead `PresetConfig` codec fields, CLI, and parser-only flags
- Dropped standalone `caption-animator` CLI entry point

---

## Phase 4: Test Migration and Smoke Tests

### 4.1: Port Local SRT Unit Tests

Port the unit-level tests from Local SRT's test suite with import path rewrites.

**Tests to port (unit-level only):**
- `test_models.py` → `tests/test_srt_models.py`
- `test_config.py` → `tests/test_srt_config.py`
- `test_text_processing.py` → `tests/test_srt_text_processing.py`
- `test_subtitle_generation.py` → `tests/test_srt_subtitle_generation.py`
- `test_alignment.py` → `tests/test_srt_alignment.py`
- `test_output_writers.py` → `tests/test_srt_output_writers.py`
- `test_events.py` → adapt into `tests/test_srt_events.py` (using shared protocol)
- `test_logging_utils.py` → `tests/test_srt_format_helpers.py`
- `test_audio.py` → `tests/test_srt_audio.py`
- `test_system.py` → `tests/test_srt_system.py`
- `test_script_reader.py` → `tests/test_srt_script_reader.py`

**Tests NOT ported:**
- `test_batch.py` (batch feature dropped)
- `test_integration.py` (integration tests excluded per plan scope)
- `test_pipeline.py` (integration-level, excluded)
- `test_api.py` (integration-level, replaced by smoke tests in 4.3)
- `test_diarization.py` (requires optional dependency and model downloads)
- `test_helpers.py` (test-internal helpers, not needed)

**Tasks:**
- Copy each test file to its new location under `tests/`
- Rewrite all `from local_srt.X import Y` to `from audio_visualizer.srt.X import Y` using new module paths
- Update fixture imports and paths
- Copy required fixture files (`.wav`, `.txt`, `.srt`, `.docx`) to `tests/fixtures/srt/`
- Port `conftest.py` fixtures needed by the ported tests into the root `tests/conftest.py`
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create all test files listed above under `tests/`
- Create `tests/fixtures/srt/` directory with required fixture files

**Success criteria:** All ported unit tests pass with the new import paths. No references to `local_srt` remain in test files.

### 4.2: Port Caption Animator Unit Tests

Port the unit-level tests from Caption Animator's test suite with import path rewrites.

**Tests to port:**
- `test_core/test_sizing.py` → `tests/test_caption_sizing.py`
- `test_text/test_measurement.py` → `tests/test_caption_measurement.py`
- `test_text/test_wrapper.py` → `tests/test_caption_wrapper.py`
- `test_animations/test_word_reveal.py` → `tests/test_caption_word_reveal.py`

**Tasks:**
- Copy each test file to its new location under `tests/`
- Rewrite all `from caption_animator.X import Y` to `from audio_visualizer.caption.X import Y` using new module paths
- Update fixture imports and conftest references
- Port `conftest.py` fixtures into the root `tests/conftest.py`
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create all test files listed above under `tests/`

**Success criteria:** All ported unit tests pass with the new import paths. No references to `caption_animator` remain in test files.

### 4.3: Add Host-Level Smoke Tests

Add new smoke tests that verify the merged packages work correctly from the host app's perspective.

**Tasks:**
- Add import smoke tests: verify `import audio_visualizer.srt` and `import audio_visualizer.caption` succeed
- Add lazy-loading verification: verify that importing the packages does not load heavy dependencies
- Add config/preset loading smoke tests: verify preset loading from app data directories
- Add event protocol smoke test: verify both packages emit through the shared `AppEventEmitter` correctly
- Add logging bridge smoke test: verify events reach a Python `logging.Logger` via `LoggingBridge`
- Add missing-binary behavior test: verify graceful behavior when `ffmpeg`/`ffprobe` are not on PATH
- Add a fixture-backed host-level smoke test for one `audio_visualizer.srt.transcribe_file()` run using bundled test fixtures and the merged public API
- Add a fixture-backed host-level smoke test for one `audio_visualizer.caption.render_subtitle()` run using bundled subtitle fixtures and the merged public API
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create `tests/test_srt_smoke.py`
- Create `tests/test_caption_smoke.py`
- Create `tests/test_integration_smoke.py` (cross-package event and logging tests)
- Reuse fixtures under `tests/fixtures/srt/`
- Create `tests/fixtures/caption/sample.srt`

**Success criteria:** All smoke tests pass. Import tests verify lazy loading. Event tests verify the shared protocol works end-to-end with the logging bridge. The smoke suite exercises one full `transcribe_file()` path and one full `render_subtitle()` path through the merged host-level APIs using bundled fixtures.

### 4.4: Phase 4 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify no auto-pass tests exist
- Verify test structure matches project module structure

**Phase 4 Changelog:**
- Ported 11 Local SRT unit test modules
- Ported 4 Caption Animator unit test modules
- Added host-level smoke tests for imports, lazy loading, events, logging bridge, missing-binary behavior, and one fixture-backed end-to-end API path per merged package
- Migrated test fixtures to `tests/fixtures/srt/`
- Added caption smoke-test fixtures under `tests/fixtures/caption/`

---

## Phase 5: Final Review

### 5.1: Code Review

Perform a final code-quality and regression review across all Stage Two integration work before release prep.

**Tasks:**

- Review all phases in this plan and ensure there are no gaps or bugs remaining in the implementation
- Review all changes for unintended regressions
- Review for deprecated code, dead code, or legacy compatibility shims — remove them
- Review all new modules for proper error handling and logging
- Review test suite:
  - No auto-pass tests
  - Test structure matches project module structure
  - All new features have tests
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Potentially modify any files changed in Phases 1-4, especially under `src/audio_visualizer/`, `tests/`, and `.agents/docs/`

**Success criteria:** No known implementation gaps remain from Phases 1-4. Regressions, dead code, and stale compatibility shims have been removed or intentionally documented. The merged packages, shared event system, and test suite structure are ready for the final pass.

### 5.2: Integration Testing

Run the final integration and regression test pass across the merged codebase before documentation and release updates are finalized.

**Tasks:**

- Run all existing tests: `pytest tests/ -v`
- Verify no pre-existing tests regressed
- Verify the fixture-backed SRT and caption smoke tests pass in the same suite run
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- No new files planned; if regressions are found, modify the affected files under `src/audio_visualizer/` and `tests/`

**Success criteria:** The full pytest suite passes, including the host-level smoke coverage for both merged packages. No pre-existing tests regress.

### 5.3: Architecture Documentation Update

**Tasks:**
- Create `audio_visualizer.srt` package doc at `.agents/docs/architecture/packages/audio_visualizer.srt.md`
- Create `audio_visualizer.caption` package doc at `.agents/docs/architecture/packages/audio_visualizer.caption.md`
- Create `audio_visualizer.events` module doc or add to existing core package doc
- Update `ARCHITECTURE.md` top-level overview to reflect the expanded package structure
- Update `INDEX.md` to include new package doc links
- Update `.agents/docs/architecture/development/OVERVIEW.md` with new system map
- Update `.agents/docs/architecture/development/TESTING.md` with new test coverage areas
- Update `CODING_PATTERNS.md` if naming conventions were refined
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- Create `.agents/docs/architecture/packages/audio_visualizer.srt.md`
- Create `.agents/docs/architecture/packages/audio_visualizer.caption.md`
- Modify `.agents/docs/ARCHITECTURE.md`
- Modify `.agents/docs/INDEX.md`
- Modify `.agents/docs/architecture/development/OVERVIEW.md`
- Modify `.agents/docs/architecture/development/TESTING.md`
- Potentially modify `.agents/docs/CODING_PATTERNS.md`

**Success criteria:** Architecture docs accurately reflect the codebase after the merge.

### 5.4: Release Preparation

**Tasks:**
- Update `readme.md` to reflect the new `audio_visualizer.srt` and `audio_visualizer.caption` packages
- Update version in `pyproject.toml` and `src/audio_visualizer/__init__.py` to `0.6.0`
- Update version in `readme.md` to `0.6.0`
- Run final full test suite: `pytest tests/ -v`
- Commit following `COMMIT_MESSAGE.md` format

**Files:**
- `pyproject.toml`
- `src/audio_visualizer/__init__.py`
- `readme.md`

**Success criteria:** Release-facing documentation reflects the merged package capabilities. Version strings are updated to `0.6.0`. The final full test suite passes.
