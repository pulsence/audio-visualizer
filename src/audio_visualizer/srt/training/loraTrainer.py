"""LoRA fine-tuning pipeline for Whisper models.

Provides a typed training configuration and a ``train_lora()`` entry point
that loads a base Whisper model through Transformers, applies PEFT LoRA
training, and emits progress via the shared app event system.

Training is guarded behind ``has_training_stack()`` and ``has_cuda()``
capability checks.  When the training stack is unavailable, functions
raise clear errors rather than importing heavy dependencies.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

from audio_visualizer.app_paths import get_data_dir
from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType

logger = logging.getLogger(__name__)

# Whisper model name -> HuggingFace model identifier
_HF_MODEL_MAP = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large": "openai/whisper-large-v3",
    "large-v3": "openai/whisper-large-v3",
    "turbo": "openai/whisper-large-v3-turbo",
}


def get_lora_models_dir() -> Path:
    """Return the directory where trained LoRA models are stored."""
    d = get_data_dir() / "lora_models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_trained_models() -> List[str]:
    """Return a sorted list of trained model names."""
    d = get_lora_models_dir()
    if not d.is_dir():
        return []
    return sorted(
        item.name
        for item in d.iterdir()
        if item.is_dir()
    )


@dataclass
class LoraTrainingConfig:
    """Typed configuration for a LoRA training run."""

    base_model_name: str = "base"
    dataset_dir: Path = field(default_factory=lambda: Path("."))
    output_name: str = "lora_model"
    num_epochs: int = 3
    learning_rate: float = 1e-4
    batch_size: int = 4
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    warmup_steps: int = 50
    save_steps: int = 500
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    fp16: bool = True


def validate_training_config(config: LoraTrainingConfig) -> List[str]:
    """Validate a training config and return a list of error messages.

    An empty list means the config is valid.  This function does NOT
    require the training stack to be installed — it only checks the
    config values and filesystem state.
    """
    errors: List[str] = []

    if config.base_model_name not in _HF_MODEL_MAP:
        errors.append(
            f"Unknown base model '{config.base_model_name}'. "
            f"Valid models: {', '.join(sorted(_HF_MODEL_MAP.keys()))}"
        )

    dataset_dir = Path(config.dataset_dir)
    if not dataset_dir.is_dir():
        errors.append(f"Dataset directory does not exist: {dataset_dir}")
    else:
        metadata_csv = dataset_dir / "metadata.csv"
        if not metadata_csv.is_file():
            errors.append(f"Dataset missing metadata.csv: {metadata_csv}")
        else:
            # Check minimum sample count
            try:
                with open(metadata_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    sample_count = sum(1 for _ in reader)
                if sample_count < 1:
                    errors.append("Dataset metadata.csv is empty — no training samples.")
                elif sample_count < 5:
                    errors.append(
                        f"Dataset has only {sample_count} sample(s). "
                        "At least 5 are recommended for meaningful training."
                    )
            except Exception as exc:
                errors.append(f"Cannot read metadata.csv: {exc}")

    if not config.output_name or not config.output_name.strip():
        errors.append("Output name must not be empty.")

    if config.num_epochs < 1:
        errors.append("Number of epochs must be at least 1.")

    if config.learning_rate <= 0:
        errors.append("Learning rate must be positive.")

    if config.batch_size < 1:
        errors.append("Batch size must be at least 1.")

    if config.lora_rank < 1:
        errors.append("LoRA rank must be at least 1.")

    return errors


def _emit(emitter: Optional[AppEventEmitter], event: AppEvent) -> None:
    if emitter is not None:
        emitter.emit(event)


def train_lora(
    config: LoraTrainingConfig,
    *,
    emitter: Optional[AppEventEmitter] = None,
    cancel_flag: Optional[threading.Event] = None,
) -> Path:
    """Train a LoRA adapter on the given dataset.

    Parameters
    ----------
    config:
        Training configuration.
    emitter:
        Optional event emitter for progress reporting.
    cancel_flag:
        Optional threading.Event to request cancellation.

    Returns
    -------
    Path
        The directory containing the merged CTranslate2 model.

    Raises
    ------
    RuntimeError
        If the training stack or CUDA is unavailable.
    ValueError
        If the config fails validation.
    """
    from audio_visualizer.capabilities import has_training_stack, has_cuda

    if not has_training_stack():
        raise RuntimeError(
            "Training stack unavailable. Install torch, transformers, peft, "
            "and ctranslate2 to enable LoRA training."
        )

    if not has_cuda():
        raise RuntimeError(
            "CUDA is required for LoRA training but is not available."
        )

    # Validate config
    errors = validate_training_config(config)
    if errors:
        raise ValueError("Training config validation failed:\n" + "\n".join(errors))

    _emit(emitter, AppEvent(
        event_type=EventType.JOB_START,
        message=f"Starting LoRA training: {config.output_name}",
        data={
            "job_type": "lora_training",
            "owner_tab_id": "advanced",
            "label": f"Training LoRA: {config.output_name}",
        },
    ))

    # Heavy imports — only reached when training stack is confirmed
    import torch
    from transformers import (
        WhisperForConditionalGeneration,
        WhisperProcessor,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, TaskType

    if cancel_flag and cancel_flag.is_set():
        raise RuntimeError("Training cancelled before model load.")

    # Resolve HF model ID
    hf_model_id = _HF_MODEL_MAP.get(config.base_model_name)
    if not hf_model_id:
        raise ValueError(f"Unknown base model: {config.base_model_name}")

    _emit(emitter, AppEvent(
        event_type=EventType.STAGE,
        message="Loading base model",
        data={"stage_number": 1, "total_stages": 4},
    ))

    processor = WhisperProcessor.from_pretrained(hf_model_id)
    model = WhisperForConditionalGeneration.from_pretrained(
        hf_model_id,
        torch_dtype=torch.float16 if config.fp16 else torch.float32,
    )

    if cancel_flag and cancel_flag.is_set():
        raise RuntimeError("Training cancelled after model load.")

    _emit(emitter, AppEvent(
        event_type=EventType.STAGE,
        message="Applying LoRA configuration",
        data={"stage_number": 2, "total_stages": 4},
    ))

    # Apply LoRA
    lora_config = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=["q_proj", "v_proj"],
        task_type=TaskType.SEQ_2_SEQ_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    _emit(emitter, AppEvent(
        event_type=EventType.STAGE,
        message="Preparing dataset",
        data={"stage_number": 3, "total_stages": 4},
    ))

    # Load dataset from metadata.csv
    dataset = _load_training_dataset(
        config.dataset_dir, processor, model.config
    )

    if cancel_flag and cancel_flag.is_set():
        raise RuntimeError("Training cancelled after dataset load.")

    # Output directory
    output_dir = get_lora_models_dir() / config.output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = output_dir / "adapter"

    _emit(emitter, AppEvent(
        event_type=EventType.STAGE,
        message="Training LoRA adapter",
        data={"stage_number": 4, "total_stages": 4},
    ))

    # Training arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(adapter_dir),
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        warmup_steps=config.warmup_steps,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        max_grad_norm=config.max_grad_norm,
        fp16=config.fp16,
        save_steps=config.save_steps,
        logging_steps=10,
        remove_unused_columns=False,
        predict_with_generate=False,
        report_to="none",
    )

    # Progress callback
    progress_callback = _make_progress_callback(
        emitter, config.num_epochs, cancel_flag
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        callbacks=[progress_callback] if progress_callback else [],
    )

    trainer.train()

    # Save adapter
    model.save_pretrained(str(adapter_dir))
    processor.save_pretrained(str(adapter_dir))

    _emit(emitter, AppEvent(
        event_type=EventType.LOG,
        message="LoRA adapter saved, converting to CTranslate2 format...",
    ))

    # Convert to CTranslate2
    from audio_visualizer.srt.training.loraConverter import convert_lora_to_ct2

    ct2_dir = convert_lora_to_ct2(
        adapter_dir=adapter_dir,
        output_dir=output_dir / "ct2",
        base_model_name=config.base_model_name,
        emitter=emitter,
    )

    # Save config metadata
    config_meta = {
        "base_model_name": config.base_model_name,
        "hf_model_id": hf_model_id,
        "output_name": config.output_name,
        "num_epochs": config.num_epochs,
        "learning_rate": config.learning_rate,
        "batch_size": config.batch_size,
        "lora_rank": config.lora_rank,
        "lora_alpha": config.lora_alpha,
        "ct2_dir": str(ct2_dir),
    }
    with open(output_dir / "training_config.json", "w", encoding="utf-8") as f:
        json.dump(config_meta, f, indent=2)

    _emit(emitter, AppEvent(
        event_type=EventType.JOB_COMPLETE,
        message=f"LoRA training complete: {config.output_name}",
        data={"output_name": config.output_name, "output_dir": str(output_dir)},
    ))

    logger.info("LoRA training complete: %s at %s", config.output_name, output_dir)
    return ct2_dir


def _load_training_dataset(
    dataset_dir: Path,
    processor: Any,
    model_config: Any,
) -> Any:
    """Load a training dataset from metadata.csv and audio clips.

    Returns a torch Dataset suitable for Seq2SeqTrainer.
    """
    import torch
    from torch.utils.data import Dataset as TorchDataset
    import numpy as np

    metadata_path = dataset_dir / "metadata.csv"
    samples: List[dict] = []
    with open(metadata_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clip_path = dataset_dir / row["file_name"]
            if clip_path.is_file():
                samples.append({
                    "audio_path": str(clip_path),
                    "text": row["text"],
                })

    if not samples:
        raise ValueError("No valid audio samples found in the dataset.")

    class WhisperLoraDataset(TorchDataset):
        def __init__(self, samples, processor, model_config):
            self.samples = samples
            self.processor = processor
            self.model_config = model_config

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            sample = self.samples[idx]
            # Load audio
            audio = _load_audio_file(sample["audio_path"])
            # Process
            input_features = self.processor(
                audio,
                sampling_rate=16000,
                return_tensors="pt",
            ).input_features.squeeze(0)
            # Tokenize text
            labels = self.processor.tokenizer(
                sample["text"],
                return_tensors="pt",
            ).input_ids.squeeze(0)

            return {
                "input_features": input_features,
                "labels": labels,
            }

    return WhisperLoraDataset(samples, processor, model_config)


def _load_audio_file(path: str) -> Any:
    """Load an audio file as a numpy array at 16kHz."""
    import numpy as np

    try:
        import av

        container = av.open(path)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
        frames = []
        for frame in container.decode(audio=0):
            resampled = resampler.resample(frame)
            for r_frame in resampled:
                arr = r_frame.to_ndarray().flatten()
                frames.append(arr)
        container.close()
        if frames:
            return np.concatenate(frames).astype(np.float32)
        return np.zeros(16000, dtype=np.float32)
    except Exception:
        # Fallback: read raw WAV
        import struct
        with open(path, "rb") as f:
            data = f.read()
        # Skip WAV header (44 bytes typically)
        if data[:4] == b"RIFF":
            pcm_start = data.index(b"data") + 8 if b"data" in data else 44
            pcm_data = data[pcm_start:]
            samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
            samples /= 32768.0
            return samples
        return np.zeros(16000, dtype=np.float32)


def _make_progress_callback(
    emitter: Optional[AppEventEmitter],
    num_epochs: int,
    cancel_flag: Optional[threading.Event],
) -> Any:
    """Create a Transformers TrainerCallback for progress reporting."""
    if emitter is None and cancel_flag is None:
        return None

    from transformers import TrainerCallback

    class LoraProgressCallback(TrainerCallback):
        def on_step_end(self, args, state, control, **kwargs):
            if cancel_flag and cancel_flag.is_set():
                control.should_training_stop = True
                return

            if emitter and state.max_steps > 0:
                percent = (state.global_step / state.max_steps) * 100
                eta = None
                if state.global_step > 0 and hasattr(state, "log_history") and state.log_history:
                    # Simple ETA estimate
                    elapsed = state.log_history[-1].get("epoch", 0)
                    if elapsed > 0:
                        eta_msg = f" (epoch {elapsed:.1f}/{num_epochs})"
                    else:
                        eta_msg = ""
                else:
                    eta_msg = ""

                emitter.emit(AppEvent(
                    event_type=EventType.PROGRESS,
                    message=f"Training: step {state.global_step}/{state.max_steps}{eta_msg}",
                    data={"percent": percent},
                ))

        def on_epoch_end(self, args, state, control, **kwargs):
            if cancel_flag and cancel_flag.is_set():
                control.should_training_stop = True
                return

            if emitter:
                current_epoch = int(state.epoch) if state.epoch else 0
                emitter.emit(AppEvent(
                    event_type=EventType.LOG,
                    message=f"Completed epoch {current_epoch}/{num_epochs}",
                ))

    return LoraProgressCallback()
