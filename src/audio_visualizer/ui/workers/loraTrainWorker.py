"""LoRA training background worker.

Runs LoRA fine-tuning through a QRunnable so the UI stays responsive.
Emits progress, completion, failure, and cancellation signals through
the shared WorkerBridge/WorkerSignals protocol.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from PySide6.QtCore import QRunnable

from audio_visualizer.events import AppEvent, AppEventEmitter, EventType
from audio_visualizer.srt.training.loraTrainer import LoraTrainingConfig
from audio_visualizer.ui.workers.workerBridge import WorkerBridge, WorkerSignals

logger = logging.getLogger(__name__)


class LoraTrainWorker(QRunnable):
    """QRunnable that runs a LoRA training job in the background.

    Parameters
    ----------
    config:
        The training configuration.
    """

    def __init__(self, config: LoraTrainingConfig) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._config = config
        self._cancel_flag = threading.Event()
        self._emitter = AppEventEmitter()
        self.signals = WorkerSignals()
        self._bridge = WorkerBridge(self._emitter, self.signals)

    def cancel(self) -> None:
        """Request cancellation of the training job."""
        self._cancel_flag.set()

    @property
    def is_canceled(self) -> bool:
        return self._cancel_flag.is_set()

    def run(self) -> None:
        """Execute the training job."""
        self._bridge.attach()
        try:
            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled before training started")
                return

            from audio_visualizer.srt.training.loraTrainer import train_lora

            ct2_dir = train_lora(
                self._config,
                emitter=self._emitter,
                cancel_flag=self._cancel_flag,
            )

            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled during training")
                return

            self.signals.completed.emit({
                "output_name": self._config.output_name,
                "ct2_dir": str(ct2_dir),
            })

        except RuntimeError as exc:
            if "cancelled" in str(exc).lower():
                self.signals.canceled.emit(str(exc))
            else:
                logger.exception("LoRA training failed: %s", exc)
                self.signals.failed.emit(str(exc), {"config": self._config.output_name})

        except Exception as exc:
            logger.exception("LoRA training failed: %s", exc)
            self.signals.failed.emit(str(exc), {"config": self._config.output_name})

        finally:
            self._bridge.detach()
