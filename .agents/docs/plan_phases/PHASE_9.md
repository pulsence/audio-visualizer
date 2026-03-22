# Phase 9: SRT Gen — Script Input, Model Management, and Bundle-from-SRT

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 9.

Expand SRT Gen so it can use scripts, manage models, and create bundle v2 data from existing subtitle files.

### 9.1: Script-Assisted Transcription

Add per-file script input to guide transcription.

**Tasks:**
1. Add `script_path` to the SRT Gen job spec.
2. Add a `.txt` / `.docx` picker per input item in the batch list UI.
3. Pass the script path through the worker into the transcription pipeline.
4. Reuse the existing script-alignment support in `srt/core/alignment.py` where appropriate.

**Files:**
- `src/audio_visualizer/ui/workers/srtGenWorker.py`
- `src/audio_visualizer/ui/tabs/srtGenTab.py`
- `src/audio_visualizer/srt/core/pipeline.py`

**Success criteria:** Each SRT Gen input item can optionally carry a script file and the pipeline uses it to improve the transcription result.

**Close-out:** Add or update tests for per-file script selection and pipeline wiring, run the relevant tests and `pytest tests/ -v` when shared SRT Gen behavior changed, update `.agents/docs/architecture/` docs if transcription inputs changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 9.2: Model Management UI

Add Whisper-model management controls to the Settings dialog.

**Tasks:**
1. Extend `SettingsDialog` with a "Whisper Models" section.
2. Show model name, size, and install state.
3. Add download actions with progress feedback.
4. Add delete actions with confirmation.
5. Wire the UI to `modelManagement.py` helper functions.

**Files:**
- `src/audio_visualizer/ui/settingsDialog.py`
- `src/audio_visualizer/srt/modelManagement.py`

**Success criteria:** Users can inspect, download, and delete Whisper models from the app's Settings dialog.

**Close-out:** Add or update tests for settings-dialog model management where practical, run the relevant tests and `pytest tests/ -v` when shared settings behavior changed, update `.agents/docs/architecture/` docs if settings UI structure changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 9.3: Bundle from Existing SRT

Create bundle v2 data by aligning Whisper word timing onto an existing subtitle file without changing the subtitle text.

**Tasks:**
1. Add a "Bundle from SRT" mode in SRT Gen that accepts an existing subtitle file plus source audio/video.
2. Run Whisper to obtain word-level timing.
3. Create a dedicated cue-to-word alignment helper for matching Whisper words to existing subtitle cues.
4. Handle punctuation and casing differences explicitly.
5. Mark alignment quality in the produced bundle using `alignment_status` and `alignment_confidence`.
6. Preserve the user's subtitle text exactly while attaching aligned word timing.

**Files:**
- `src/audio_visualizer/ui/tabs/srtGenTab.py`
- `src/audio_visualizer/srt/core/alignment.py`
- `src/audio_visualizer/ui/workers/srtGenWorker.py`
- `src/audio_visualizer/srt/io/outputWriters.py`

**Success criteria:** Bundle-from-SRT produces a valid v2 bundle that preserves the original subtitle text, attaches usable word timing, and records whether each cue alignment was confident or estimated.

**Close-out:** Add or update tests for cue-to-word alignment quality and bundle output, run the relevant tests and `pytest tests/ -v` when shared SRT Gen or bundle behavior changed, update `.agents/docs/architecture/` docs if alignment behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 9.4: Phase 9 Review

**Tasks:**
1. Review script input, settings-based model management, and bundle-from-SRT behavior together.
2. Remove temporary alignment shortcuts or duplicate model-management wiring introduced during implementation.
3. Verify tests cover both normal transcription jobs and bundle-from-SRT generation.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 9 implementation files
- Phase 9 tests

**Success criteria:** SRT Gen can now generate or enrich the bundle-first subtitle workflow without fragmenting its model-management or alignment behavior.

### 9.5: Phase 9 Changelog

**Tasks:**
1. Summarize script input, model management, and bundle-from-SRT capabilities added in Phase 9.
2. Note the new bundle alignment metadata so Caption Animator and SRT Edit do not re-infer it.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 9 implementation notes

**Success criteria:** Caption Animator and the remaining subtitle workflow can now treat SRT Gen as a complete bundle producer.
