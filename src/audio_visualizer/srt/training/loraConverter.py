"""LoRA adapter merge and CTranslate2 conversion.

Merges LoRA adapters into the base Whisper model and converts the
result to CTranslate2 format for efficient inference with faster-whisper.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Optional

from audio_visualizer.events import AppEvent, AppEventEmitter, EventType

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


def _emit(emitter: Optional[AppEventEmitter], event: AppEvent) -> None:
    if emitter is not None:
        emitter.emit(event)


def convert_lora_to_ct2(
    adapter_dir: Path,
    output_dir: Path,
    base_model_name: str,
    *,
    quantization: str = "float16",
    emitter: Optional[AppEventEmitter] = None,
) -> Path:
    """Merge LoRA adapters and convert to CTranslate2 format.

    Parameters
    ----------
    adapter_dir:
        Directory containing the saved PEFT adapter (from ``save_pretrained``).
    output_dir:
        Target directory for the CTranslate2 model files.
    base_model_name:
        Whisper model name (e.g. ``"base"``, ``"large-v3"``).
    quantization:
        CTranslate2 quantization type (default ``"float16"``).
    emitter:
        Optional event emitter for progress reporting.

    Returns
    -------
    Path
        The directory containing the converted CTranslate2 model.
    """
    from audio_visualizer.capabilities import has_training_stack

    if not has_training_stack():
        raise RuntimeError(
            "Training stack unavailable. Cannot convert LoRA adapter."
        )

    hf_model_id = _HF_MODEL_MAP.get(base_model_name)
    if not hf_model_id:
        raise ValueError(f"Unknown base model: {base_model_name}")

    _emit(emitter, AppEvent(
        event_type=EventType.LOG,
        message="Loading base model and merging LoRA adapters...",
    ))

    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    from peft import PeftModel

    # Load base model
    base_model = WhisperForConditionalGeneration.from_pretrained(
        hf_model_id,
        torch_dtype=torch.float16,
    )

    # Load and merge LoRA
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    model = model.merge_and_unload()

    # Save the merged model to a temp location for CTranslate2 conversion
    merged_dir = output_dir.parent / "merged_hf"
    merged_dir.mkdir(parents=True, exist_ok=True)

    _emit(emitter, AppEvent(
        event_type=EventType.LOG,
        message="Saving merged model...",
    ))

    model.save_pretrained(str(merged_dir))
    # Also save the processor/tokenizer alongside the merged model
    processor = WhisperProcessor.from_pretrained(str(adapter_dir))
    processor.save_pretrained(str(merged_dir))

    _emit(emitter, AppEvent(
        event_type=EventType.LOG,
        message="Converting to CTranslate2 format...",
    ))

    # Convert to CTranslate2
    import ctranslate2

    output_dir.mkdir(parents=True, exist_ok=True)
    converter = ctranslate2.converters.TransformersConverter(
        str(merged_dir),
        copy_files=["tokenizer.json", "preprocessor_config.json"],
    )
    converter.convert(
        str(output_dir),
        quantization=quantization,
        force=True,
    )

    # Clean up the merged HF directory
    try:
        shutil.rmtree(merged_dir)
    except Exception:
        logger.warning("Could not clean up merged model directory: %s", merged_dir)

    _emit(emitter, AppEvent(
        event_type=EventType.LOG,
        message=f"CTranslate2 conversion complete: {output_dir}",
    ))

    logger.info("LoRA->CT2 conversion complete: %s", output_dir)
    return output_dir
