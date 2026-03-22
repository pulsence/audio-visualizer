"""LoRA training and model conversion for Whisper fine-tuning.

This sub-package provides the training pipeline for creating LoRA
adapters and converting them to CTranslate2 format for inference.
Heavy imports (torch, transformers, peft) are deferred until needed.
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "LoraTrainingConfig": (".loraTrainer", "LoraTrainingConfig"),
    "train_lora": (".loraTrainer", "train_lora"),
    "validate_training_config": (".loraTrainer", "validate_training_config"),
    "convert_lora_to_ct2": (".loraConverter", "convert_lora_to_ct2"),
    "list_trained_models": (".loraTrainer", "list_trained_models"),
    "get_lora_models_dir": (".loraTrainer", "get_lora_models_dir"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))
