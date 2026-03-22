# Phase 6: Advanced Screen — LoRA Training and Adaptation

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 6.

Implement dataset export, LoRA training, model selection, and the v0.7.0 per-speaker adaptation scope.

### 6.1: Training Data Export

Export correction data into a training dataset.

**Tasks:**
1. Add dataset-export support to `CorrectionDatabase`.
2. For each correction record, extract the source media segment by time range using PyAV.
3. Write audio clips and a `metadata.csv` suitable for training.
4. Skip missing source files with warnings instead of failing the whole export.
5. Add an "Export Training Data" action in `AdvancedTab`.

**Files:**
- `src/audio_visualizer/core/correctionDb.py`
- `src/audio_visualizer/ui/tabs/advancedTab.py`

**Success criteria:** Users can export a usable training dataset from recorded corrections and receive clear feedback about skipped files.

**Close-out:** Add or update tests for dataset export and missing-file handling where practical, run the relevant tests and `pytest tests/ -v` when shared correction/training behavior changed, update `.agents/docs/architecture/` docs if training-export behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 6.2: LoRA Training Pipeline

Build the LoRA training and conversion pipeline.

**Tasks:**
1. Create `srt/training/loraTrainer.py` with a typed training config and a `train_lora()` entry point.
2. Load the base Whisper model through Transformers, apply PEFT LoRA training, and emit progress via the shared app event system.
3. Create `srt/training/loraConverter.py` to merge adapters and convert them to CTranslate2 format.
4. Store trained models under `app_paths.data_dir() / "lora_models"`.
5. Guard heavy imports and runtime entry with `has_training_stack()`.
6. Validate CUDA availability and dataset size before training begins.

**Files:**
- `src/audio_visualizer/srt/training/loraTrainer.py`
- `src/audio_visualizer/srt/training/loraConverter.py`
- `src/audio_visualizer/srt/training/__init__.py`
- `src/audio_visualizer/core/capabilities.py`

**Success criteria:** The app can train a LoRA from exported data, convert it into the runtime model format, and fail fast with a clear message when the environment cannot support training.

**Close-out:** Add or update tests for training-stack gating and config validation where practical, run the relevant tests and `pytest tests/ -v` when shared training behavior changed, update `.agents/docs/architecture/` docs if training architecture changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 6.3: LoRA Training UI

Add the user-facing training controls to the Advanced tab.

**Tasks:**
1. Add controls for base model selection, dataset source selection, output name, and key hyperparameters.
2. Run training through a background worker so the UI stays responsive.
3. Show progress, ETA, and cancellation state.
4. Show a list of trained models with delete support.
5. Surface capability failures and validation errors in the UI before or during training start.

**Files:**
- `src/audio_visualizer/ui/tabs/advancedTab.py`
- `src/audio_visualizer/ui/workers/loraTrainWorker.py`
- `src/audio_visualizer/srt/training/loraTrainer.py`

**Success criteria:** Users can launch, monitor, and cancel LoRA training from the Advanced tab and manage trained models without leaving the app.

**Close-out:** Add or update tests for training UI validation and worker wiring where practical, run the relevant tests and `pytest tests/ -v` when shared Advanced-tab or worker behavior changed, update `.agents/docs/architecture/` docs if training UI changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 6.4: LoRA Selection in SRT Gen

Allow transcription jobs to use a trained LoRA-backed model.

**Tasks:**
1. Add a "LoRA Adapter" dropdown to `SrtGenTab`.
2. Populate the dropdown from the trained-model output directory.
3. Add `lora_name` to the SRT Gen job spec.
4. Update model loading so selecting a LoRA uses the merged CTranslate2 model path rather than the base model path.
5. Make sure model caching keys distinguish base models from merged LoRA models.

**Files:**
- `src/audio_visualizer/ui/tabs/srtGenTab.py`
- `src/audio_visualizer/ui/workers/srtGenWorker.py`
- `src/audio_visualizer/srt/modelManager.py`

**Success criteria:** SRT Gen can use a selected trained LoRA model when available and cleanly fall back to the base model when no adapter is selected.

**Close-out:** Add or update tests for LoRA model selection and model-manager cache keys, run the relevant tests and `pytest tests/ -v` when shared SRT Gen behavior changed, update `.agents/docs/architecture/` docs if transcription model-loading behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 6.5: Per-Speaker Adaptation for v0.7.0

Implement the supported per-speaker adaptation scope without per-speaker LoRA model swapping.

**Tasks:**
1. Use per-speaker prompt terms from the correction DB when diarization labels are available.
2. Apply per-speaker replacement rules during transcription or post-processing when diarization labels are available.
3. Fall back to global prompt terms and replacement rules when a speaker label is absent.
4. Use the one shared LoRA model for all speakers.
5. Explicitly do not implement per-speaker merged-model swapping in v0.7.0.

**Files:**
- `src/audio_visualizer/ui/tabs/srtGenTab.py`
- `src/audio_visualizer/srt/core/pipeline.py`
- `src/audio_visualizer/core/correctionDb.py`

**Success criteria:** Speaker-aware prompts and replacement rules work when diarization labels exist, unlabeled segments still use the global path, and the release scope remains limited to one shared LoRA model.

**Close-out:** Add or update tests for per-speaker prompt and dictionary application, run the relevant tests and `pytest tests/ -v` when shared SRT Gen behavior changed, update `.agents/docs/architecture/` docs if speaker-adaptation behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 6.6: Phase 6 Review

**Tasks:**
1. Review training export, training runtime, UI controls, model loading, and per-speaker adaptation together.
2. Remove temporary training-path shortcuts or duplicate capability checks introduced during implementation.
3. Verify the release scope still matches one shared LoRA plus per-speaker prompts and dictionaries.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 6 implementation files
- Phase 6 tests

**Success criteria:** The Advanced-tab training flow is coherent end to end and does not accidentally expand into unsupported per-speaker model-swapping behavior.

### 6.7: Phase 6 Changelog

**Tasks:**
1. Summarize dataset export, training, model selection, and speaker-adaptation behavior added in Phase 6.
2. Call out the explicit v0.7.0 scope limit around per-speaker LoRA.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 6 implementation notes

**Success criteria:** Later phases can treat the LoRA workflow and adaptation scope as settled release decisions.
