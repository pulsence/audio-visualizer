"""SRT Gen tab — batch transcription UI.

Provides a full settings surface for ResolvedConfig, a batch input file
queue, model and device selection, output controls, and a cancellable
transcription worker.  Completed outputs are registered as SessionAssets.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QRunnable, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.events import AppEvent, AppEventEmitter, EventType
from audio_visualizer.srt.config import PRESETS, apply_overrides, load_config_file
from audio_visualizer.srt.modelManager import ModelManager
from audio_visualizer.srt.models import (
    FormattingConfig,
    PipelineMode,
    ResolvedConfig,
    SilenceConfig,
    TranscriptionConfig,
)
from audio_visualizer.ui.sessionContext import SessionAsset
from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.workers.workerBridge import WorkerBridge, WorkerSignals
from audio_visualizer.ui.workers.srtGenWorker import SrtGenJobSpec, SrtGenWorker

logger = logging.getLogger(__name__)

# Supported audio/video file extensions for the input picker.
_INPUT_FILTERS = (
    "Media files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma *.mp4 *.mkv *.webm *.avi *.mov);;"
    "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "Video files (*.mp4 *.mkv *.webm *.avi *.mov);;"
    "All files (*)"
)

# Display name -> internal model identifier mapping
_MODEL_MAP: dict[str, str] = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large": "large-v3",
    "turbo": "turbo",
}
_MODEL_NAMES = list(_MODEL_MAP.keys())
_DEVICES = ["auto", "cpu", "cuda"]
_FORMATS = ["srt", "vtt", "ass", "txt", "json"]
_MODES = ["general", "transcript", "shorts"]


class _ModelLoadWorker(QRunnable):
    """Background worker that loads a Whisper model via ModelManager."""

    def __init__(
        self,
        model_manager: ModelManager,
        display_name: str,
        model_name: str,
        device: str,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model_manager = model_manager
        self._display_name = display_name
        self._model_name = model_name
        self._device = device
        self._cancel_flag = threading.Event()
        self._emitter = AppEventEmitter()
        self.signals = WorkerSignals()
        self._bridge = WorkerBridge(self._emitter, self.signals)

    def cancel(self) -> None:
        self._cancel_flag.set()

    def run(self) -> None:
        self._bridge.attach()
        try:
            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled before model load")
                return

            self._emitter.emit(
                AppEvent(
                    event_type=EventType.JOB_START,
                    message=f"Loading model '{self._display_name}'",
                    data={
                        "job_type": "model_load",
                        "owner_tab_id": "srt_gen",
                        "label": f"Loading model '{self._display_name}'",
                    },
                )
            )
            self._emitter.emit(
                AppEvent(
                    event_type=EventType.STAGE,
                    message="Loading model",
                    data={"stage_number": 0, "total_stages": 1},
                )
            )
            self._model_manager.load(
                model_name=self._model_name,
                device=self._device,
                strict_cuda=False,
                emitter=self._emitter,
            )

            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled after model load")
                return

            info = self._model_manager.model_info()
            self.signals.completed.emit(
                {
                    "display_name": self._display_name,
                    "model_name": self._model_name,
                    "device": info.device if info else self._device,
                    "compute_type": info.compute_type if info else "",
                }
            )
        except Exception as exc:
            logger.exception("Model load failed: %s", exc)
            self.signals.failed.emit(str(exc), {"model_name": self._model_name})
        finally:
            self._bridge.detach()


class SrtGenTab(BaseTab):
    """Batch SRT transcription tab with full ResolvedConfig settings."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "srt_gen"

    @property
    def tab_title(self) -> str:
        return "SRT Gen"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = parent
        self._active_worker: Optional[SrtGenWorker] = None
        self._active_model_worker: Optional[_ModelLoadWorker] = None
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
        self._model_manager = ModelManager()
        self._model_loaded = False
        self._loaded_model_name: str | None = None

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)

        # Wrap everything in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(4, 4, 4, 4)

        self._build_input_section()
        self._build_output_section()
        self._build_model_section()
        self._build_general_options_section()
        self._build_advanced_sections()
        self._build_controls_section()

        scroll_content.setLayout(self._content_layout)
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll)
        self.setLayout(root_layout)

    # ==================================================================
    # Input section
    # ==================================================================

    def _build_input_section(self) -> None:
        group = QGroupBox("Input Files")
        layout = QVBoxLayout()

        # Preset / config import row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("(none)")
        for name in PRESETS:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo)

        self._import_config_btn = QPushButton("Import Config...")
        self._import_config_btn.clicked.connect(self._on_import_config)
        preset_row.addWidget(self._import_config_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # Queue list — compact by default, grows as files are added
        self._input_list = QListWidget()
        self._input_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._input_list.setMaximumHeight(120)
        layout.addWidget(self._input_list)

        # Add / remove buttons
        btn_row = QHBoxLayout()
        self._add_files_btn = QPushButton("Add Files...")
        self._add_files_btn.clicked.connect(self._on_add_files)
        btn_row.addWidget(self._add_files_btn)

        self._add_session_btn = QPushButton("Add from Session")
        self._add_session_btn.clicked.connect(self._on_add_session_files)
        btn_row.addWidget(self._add_session_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._on_remove_selected)
        btn_row.addWidget(self._remove_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._on_clear_queue)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        self._content_layout.addWidget(group)

    # ==================================================================
    # Output section
    # ==================================================================

    def _build_output_section(self) -> None:
        group = QGroupBox("Output")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Output Directory:"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Same directory as input file")
        layout.addWidget(self._output_dir_edit, 1)

        self._output_dir_btn = QPushButton("Browse...")
        self._output_dir_btn.clicked.connect(self._on_browse_output_dir)
        layout.addWidget(self._output_dir_btn)

        layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(_FORMATS)
        layout.addWidget(self._format_combo)

        group.setLayout(layout)
        self._content_layout.addWidget(group)

    # ==================================================================
    # Model section
    # ==================================================================

    def _build_model_section(self) -> None:
        group = QGroupBox("Model")
        layout = QVBoxLayout()

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        self._model_combo.addItems(_MODEL_NAMES)
        self._model_combo.setCurrentText("base")
        controls.addWidget(self._model_combo)

        controls.addWidget(QLabel("Device:"))
        self._device_combo = QComboBox()
        self._device_combo.addItems(_DEVICES)
        controls.addWidget(self._device_combo)

        self._load_model_btn = QPushButton("Load Model")
        self._load_model_btn.clicked.connect(self._on_load_model)
        controls.addWidget(self._load_model_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self._model_status_label = QLabel("No model loaded")
        layout.addWidget(self._model_status_label)

        group.setLayout(layout)
        self._content_layout.addWidget(group)

    # ==================================================================
    # General options
    # ==================================================================

    def _build_general_options_section(self) -> None:
        group = QGroupBox("General Options")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(_MODES)
        layout.addWidget(self._mode_combo)

        layout.addWidget(QLabel("Language:"))
        self._language_edit = QLineEdit()
        self._language_edit.setPlaceholderText("auto-detect")
        self._language_edit.setMaximumWidth(120)
        layout.addWidget(self._language_edit)

        self._word_level_cb = QCheckBox("Word-level timestamps")
        self._word_level_cb.setChecked(True)
        self._word_level_cb.toggled.connect(self._on_word_level_toggled)
        layout.addWidget(self._word_level_cb)

        self._word_level_warning = QLabel(
            "<span style='color: orange;'>Warning: word-level off reduces subtitle quality</span>"
        )
        self._word_level_warning.setVisible(False)
        layout.addWidget(self._word_level_warning)

        layout.addStretch()
        group.setLayout(layout)
        self._content_layout.addWidget(group)

    # ==================================================================
    # Advanced collapsible sections
    # ==================================================================

    def _build_advanced_sections(self) -> None:
        # Toggle button
        self._advanced_toggle = QCheckBox("Show Advanced Settings")
        self._advanced_toggle.setChecked(False)
        self._advanced_toggle.toggled.connect(self._on_advanced_toggled)
        self._content_layout.addWidget(self._advanced_toggle)

        # Container for all advanced groups
        self._advanced_container = QWidget()
        adv_layout = QVBoxLayout()
        adv_layout.setContentsMargins(0, 0, 0, 0)

        self._build_formatting_group(adv_layout)
        self._build_transcription_group(adv_layout)
        self._build_silence_group(adv_layout)
        self._build_side_outputs_group(adv_layout)
        self._build_diarization_group(adv_layout)
        self._build_diagnostics_group(adv_layout)

        self._advanced_container.setLayout(adv_layout)
        self._advanced_container.setVisible(False)
        self._content_layout.addWidget(self._advanced_container)

    # -- Formatting ----------------------------------------------------

    def _build_formatting_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Formatting")
        layout = QVBoxLayout()
        defaults = FormattingConfig()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Max chars:"))
        self._fmt_max_chars = QSpinBox()
        self._fmt_max_chars.setRange(1, 500)
        self._fmt_max_chars.setValue(defaults.max_chars)
        row1.addWidget(self._fmt_max_chars)

        row1.addWidget(QLabel("Max lines:"))
        self._fmt_max_lines = QSpinBox()
        self._fmt_max_lines.setRange(1, 20)
        self._fmt_max_lines.setValue(defaults.max_lines)
        row1.addWidget(self._fmt_max_lines)

        row1.addWidget(QLabel("Target CPS:"))
        self._fmt_target_cps = QDoubleSpinBox()
        self._fmt_target_cps.setRange(1.0, 100.0)
        self._fmt_target_cps.setDecimals(1)
        self._fmt_target_cps.setValue(defaults.target_cps)
        row1.addWidget(self._fmt_target_cps)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Min dur:"))
        self._fmt_min_dur = QDoubleSpinBox()
        self._fmt_min_dur.setRange(0.0, 60.0)
        self._fmt_min_dur.setDecimals(2)
        self._fmt_min_dur.setValue(defaults.min_dur)
        row2.addWidget(self._fmt_min_dur)

        row2.addWidget(QLabel("Max dur:"))
        self._fmt_max_dur = QDoubleSpinBox()
        self._fmt_max_dur.setRange(0.0, 300.0)
        self._fmt_max_dur.setDecimals(2)
        self._fmt_max_dur.setValue(defaults.max_dur)
        row2.addWidget(self._fmt_max_dur)

        row2.addWidget(QLabel("Min gap:"))
        self._fmt_min_gap = QDoubleSpinBox()
        self._fmt_min_gap.setRange(0.0, 10.0)
        self._fmt_min_gap.setDecimals(2)
        self._fmt_min_gap.setValue(defaults.min_gap)
        row2.addWidget(self._fmt_min_gap)

        row2.addWidget(QLabel("Pad:"))
        self._fmt_pad = QDoubleSpinBox()
        self._fmt_pad.setRange(0.0, 10.0)
        self._fmt_pad.setDecimals(2)
        self._fmt_pad.setValue(defaults.pad)
        row2.addWidget(self._fmt_pad)
        row2.addStretch()
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self._fmt_allow_commas = QCheckBox("Allow commas")
        self._fmt_allow_commas.setChecked(defaults.allow_commas)
        row3.addWidget(self._fmt_allow_commas)

        self._fmt_allow_medium = QCheckBox("Allow medium")
        self._fmt_allow_medium.setChecked(defaults.allow_medium)
        row3.addWidget(self._fmt_allow_medium)

        self._fmt_prefer_punct = QCheckBox("Prefer punct splits")
        self._fmt_prefer_punct.setChecked(defaults.prefer_punct_splits)
        row3.addWidget(self._fmt_prefer_punct)
        row3.addStretch()
        layout.addLayout(row3)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # -- Transcription -------------------------------------------------

    def _build_transcription_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Transcription")
        layout = QVBoxLayout()
        defaults = TranscriptionConfig()

        row1 = QHBoxLayout()
        self._tx_vad_filter = QCheckBox("VAD filter")
        self._tx_vad_filter.setChecked(defaults.vad_filter)
        row1.addWidget(self._tx_vad_filter)

        self._tx_condition_prev = QCheckBox("Condition on previous text")
        self._tx_condition_prev.setChecked(defaults.condition_on_previous_text)
        row1.addWidget(self._tx_condition_prev)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("No-speech threshold:"))
        self._tx_no_speech = QDoubleSpinBox()
        self._tx_no_speech.setRange(0.0, 1.0)
        self._tx_no_speech.setDecimals(2)
        self._tx_no_speech.setSingleStep(0.05)
        self._tx_no_speech.setValue(defaults.no_speech_threshold)
        row2.addWidget(self._tx_no_speech)

        row2.addWidget(QLabel("Log-prob threshold:"))
        self._tx_log_prob = QDoubleSpinBox()
        self._tx_log_prob.setRange(-10.0, 0.0)
        self._tx_log_prob.setDecimals(1)
        self._tx_log_prob.setSingleStep(0.1)
        self._tx_log_prob.setValue(defaults.log_prob_threshold)
        row2.addWidget(self._tx_log_prob)

        row2.addWidget(QLabel("Compression ratio:"))
        self._tx_compression = QDoubleSpinBox()
        self._tx_compression.setRange(0.0, 20.0)
        self._tx_compression.setDecimals(1)
        self._tx_compression.setSingleStep(0.1)
        self._tx_compression.setValue(defaults.compression_ratio_threshold)
        row2.addWidget(self._tx_compression)
        row2.addStretch()
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Initial prompt:"))
        self._tx_initial_prompt = QLineEdit()
        self._tx_initial_prompt.setPlaceholderText("Optional initial prompt for the model")
        row3.addWidget(self._tx_initial_prompt, 1)
        layout.addLayout(row3)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # -- Silence -------------------------------------------------------

    def _build_silence_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Silence Detection")
        layout = QHBoxLayout()
        defaults = SilenceConfig()

        layout.addWidget(QLabel("Min duration:"))
        self._sil_min_dur = QDoubleSpinBox()
        self._sil_min_dur.setRange(0.0, 10.0)
        self._sil_min_dur.setDecimals(2)
        self._sil_min_dur.setValue(defaults.silence_min_dur)
        layout.addWidget(self._sil_min_dur)

        layout.addWidget(QLabel("Threshold (dB):"))
        self._sil_threshold = QDoubleSpinBox()
        self._sil_threshold.setRange(-100.0, 0.0)
        self._sil_threshold.setDecimals(1)
        self._sil_threshold.setValue(defaults.silence_threshold_db)
        layout.addWidget(self._sil_threshold)

        layout.addStretch()
        group.setLayout(layout)
        parent_layout.addWidget(group)

    # -- Side outputs --------------------------------------------------

    def _build_side_outputs_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Side Outputs")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self._out_transcript = QCheckBox("Transcript (.txt)")
        self._out_transcript.setChecked(False)
        row1.addWidget(self._out_transcript)

        self._out_segments = QCheckBox("Segments (.json)")
        self._out_segments.setChecked(False)
        row1.addWidget(self._out_segments)

        self._out_json_bundle = QCheckBox("JSON bundle")
        self._out_json_bundle.setChecked(True)
        row1.addWidget(self._out_json_bundle)
        row1.addStretch()
        layout.addLayout(row1)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # -- Diarization ---------------------------------------------------

    def _build_diarization_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Diarization")
        layout = QVBoxLayout()

        row = QHBoxLayout()
        self._diarize_cb = QCheckBox("Enable speaker diarization")
        self._diarize_cb.setChecked(False)
        row.addWidget(self._diarize_cb)

        row.addWidget(QLabel("HuggingFace token:"))
        self._hf_token_edit = QLineEdit()
        self._hf_token_edit.setPlaceholderText("Required for diarization")
        self._hf_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        row.addWidget(self._hf_token_edit, 1)
        layout.addLayout(row)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    # -- Diagnostics ---------------------------------------------------

    def _build_diagnostics_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Diagnostics")
        layout = QHBoxLayout()

        self._diag_keep_wav = QCheckBox("Keep intermediate WAV")
        self._diag_keep_wav.setChecked(False)
        layout.addWidget(self._diag_keep_wav)

        self._diag_dry_run = QCheckBox("Dry run (no output files)")
        self._diag_dry_run.setChecked(False)
        layout.addWidget(self._diag_dry_run)

        layout.addStretch()
        group.setLayout(layout)
        parent_layout.addWidget(group)

    # ==================================================================
    # Controls (start / cancel / progress)
    # ==================================================================

    def _build_controls_section(self) -> None:
        group = QGroupBox("Transcription")
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Generate SRTs")
        self._start_btn.clicked.connect(self._start_transcription)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_job)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        # Scrolling event log
        self._event_log = QPlainTextEdit()
        self._event_log.setReadOnly(True)
        self._event_log.setMaximumHeight(150)
        self._event_log.setPlaceholderText("Event log will appear here during transcription...")
        layout.addWidget(self._event_log)

        group.setLayout(layout)
        self._content_layout.addWidget(group)

    # ==================================================================
    # Slot handlers
    # ==================================================================

    def _on_add_files(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
        start_dir = resolve_browse_directory(
            session_context=self.session_context
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select audio/video files", start_dir, _INPUT_FILTERS,
        )
        for p in paths:
            self._add_input_path(p)

    def _on_add_session_files(self) -> None:
        ctx = self.session_context
        if ctx is None:
            QMessageBox.information(self, "No Session", "No session context available.")
            return
        audio_assets = ctx.list_assets(category="audio")
        if not audio_assets:
            QMessageBox.information(self, "No Audio", "No audio assets in the current session.")
            return
        for asset in audio_assets:
            self._add_input_path(str(asset.path))

    def _on_remove_selected(self) -> None:
        for item in self._input_list.selectedItems():
            self._input_list.takeItem(self._input_list.row(item))

    def _on_clear_queue(self) -> None:
        self._input_list.clear()

    def _on_browse_output_dir(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
        start_dir = resolve_browse_directory(
            self._output_dir_edit.text(), self.session_context
        )
        d = QFileDialog.getExistingDirectory(self, "Select output directory", start_dir)
        if d:
            self._output_dir_edit.setText(d)

    def _on_word_level_toggled(self, checked: bool) -> None:
        self._word_level_warning.setVisible(not checked)

    def _on_advanced_toggled(self, checked: bool) -> None:
        self._advanced_container.setVisible(checked)

    def _on_preset_changed(self, name: str) -> None:
        if name == "(none)":
            return
        preset = PRESETS.get(name)
        if preset is None:
            return
        self._apply_config_dict(preset)
        logger.info("Applied preset '%s'", name)

    def _on_import_config(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory

        start_dir = resolve_browse_directory(session_context=self.session_context)
        path, _ = QFileDialog.getOpenFileName(
            self, "Import config file", start_dir, "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            data = load_config_file(path)
            self._apply_config_dict(data)
            logger.info("Imported config from '%s'", path)
        except Exception as exc:
            QMessageBox.warning(self, "Config Error", f"Failed to load config:\n{exc}")

    def _on_load_model(self) -> None:
        """Load or unload the selected Whisper model in a background thread."""
        if self._model_loaded:
            # Unload the model
            self._model_manager.unload()
            self._sync_model_state_from_manager()
            self._append_event("Model unloaded.")
            return

        if self._active_model_worker is not None:
            self._append_event("Model load already in progress.")
            self._status_label.setText("Model load already in progress.")
            return

        display_name = self._model_combo.currentText()
        model_id = _MODEL_MAP.get(display_name, display_name)
        device = self._device_combo.currentText()
        self._status_label.setText(f"Loading model '{display_name}'...")
        self._load_model_btn.setEnabled(False)
        self._append_event(f"Loading model '{display_name}' ({model_id}) on {device}...")
        worker = _ModelLoadWorker(
            model_manager=self._model_manager,
            display_name=display_name,
            model_name=model_id,
            device=device,
        )
        worker.signals.stage.connect(self._on_stage)
        worker.signals.log.connect(self._on_log)
        worker.signals.completed.connect(self._on_model_load_completed)
        worker.signals.failed.connect(self._on_model_load_failed)
        worker.signals.canceled.connect(self._on_model_load_canceled)
        self._active_model_worker = worker
        self._thread_pool.start(worker)

    def _on_model_load_completed(self, data: dict[str, Any]) -> None:
        self._active_model_worker = None
        self._load_model_btn.setEnabled(True)
        self._sync_model_state_from_manager()
        device_info = data.get("device", "unknown")
        display_name = data.get("display_name", self._model_combo.currentText())
        self._status_label.setText(f"Model '{display_name}' loaded on {device_info}")
        self._append_event(f"Model '{display_name}' loaded on {device_info}")

    def _on_model_load_failed(self, error_message: str, data: dict[str, Any]) -> None:
        self._active_model_worker = None
        self._load_model_btn.setEnabled(True)
        self._sync_model_state_from_manager()
        self._status_label.setText(f"Failed to load model: {error_message}")
        self._append_event(f"Model load failed: {error_message}")

    def _on_model_load_canceled(self, message: str) -> None:
        self._active_model_worker = None
        self._load_model_btn.setEnabled(True)
        self._sync_model_state_from_manager()
        self._status_label.setText(f"Cancelled: {message}")
        self._append_event(f"Cancelled: {message}")

    def _set_model_state(self, loaded: bool, display_name: str | None) -> None:
        """Update model-loaded UI state."""
        self._model_loaded = loaded
        self._loaded_model_name = display_name
        if loaded and display_name:
            info = self._model_manager.model_info()
            device_info = info.device if info else ""
            self._model_status_label.setText(
                f"Loaded: {display_name}" + (f" ({device_info})" if device_info else "")
            )
            self._load_model_btn.setText("Unload Model")
        else:
            self._model_status_label.setText("No model loaded")
            self._load_model_btn.setText("Load Model")
            self._load_model_btn.setEnabled(True)

    def _sync_model_state_from_manager(self) -> None:
        info = self._model_manager.model_info()
        if info is None:
            self._set_model_state(False, None)
            return

        display_name = next(
            (name for name, model_id in _MODEL_MAP.items() if model_id == info.model_name),
            info.model_name,
        )
        self._set_model_state(True, display_name)

    def _append_event(self, text: str) -> None:
        """Append a line to the scrolling event log."""
        self._event_log.appendPlainText(text)
        # Auto-scroll to bottom
        sb = self._event_log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    # ==================================================================
    # Helper methods
    # ==================================================================

    def _add_input_path(self, path: str) -> None:
        """Add a file path to the input queue if not already present."""
        for i in range(self._input_list.count()):
            if self._input_list.item(i).text() == path:
                return
        self._input_list.addItem(path)

    def _get_input_paths(self) -> list[str]:
        """Return all paths currently in the input queue."""
        return [
            self._input_list.item(i).text()
            for i in range(self._input_list.count())
        ]

    def _apply_config_dict(self, data: dict[str, Any]) -> None:
        """Apply a config dict (from preset or file) to the UI controls."""
        fmt = data.get("formatting", {})
        if fmt:
            if "max_chars" in fmt:
                self._fmt_max_chars.setValue(int(fmt["max_chars"]))
            if "max_lines" in fmt:
                self._fmt_max_lines.setValue(int(fmt["max_lines"]))
            if "target_cps" in fmt:
                self._fmt_target_cps.setValue(float(fmt["target_cps"]))
            if "min_dur" in fmt:
                self._fmt_min_dur.setValue(float(fmt["min_dur"]))
            if "max_dur" in fmt:
                self._fmt_max_dur.setValue(float(fmt["max_dur"]))
            if "allow_commas" in fmt:
                self._fmt_allow_commas.setChecked(bool(fmt["allow_commas"]))
            if "allow_medium" in fmt:
                self._fmt_allow_medium.setChecked(bool(fmt["allow_medium"]))
            if "prefer_punct_splits" in fmt:
                self._fmt_prefer_punct.setChecked(bool(fmt["prefer_punct_splits"]))
            if "min_gap" in fmt:
                self._fmt_min_gap.setValue(float(fmt["min_gap"]))
            if "pad" in fmt:
                self._fmt_pad.setValue(float(fmt["pad"]))

        tx = data.get("transcription", {})
        if tx:
            if "vad_filter" in tx:
                self._tx_vad_filter.setChecked(bool(tx["vad_filter"]))
            if "condition_on_previous_text" in tx:
                self._tx_condition_prev.setChecked(bool(tx["condition_on_previous_text"]))
            if "no_speech_threshold" in tx:
                self._tx_no_speech.setValue(float(tx["no_speech_threshold"]))
            if "log_prob_threshold" in tx:
                self._tx_log_prob.setValue(float(tx["log_prob_threshold"]))
            if "compression_ratio_threshold" in tx:
                self._tx_compression.setValue(float(tx["compression_ratio_threshold"]))
            if "initial_prompt" in tx:
                self._tx_initial_prompt.setText(str(tx["initial_prompt"]))

        sil = data.get("silence", {})
        if sil:
            if "silence_min_dur" in sil:
                self._sil_min_dur.setValue(float(sil["silence_min_dur"]))
            if "silence_threshold_db" in sil:
                self._sil_threshold.setValue(float(sil["silence_threshold_db"]))

    def _build_resolved_config(self) -> ResolvedConfig:
        """Build a ResolvedConfig from the current UI state."""
        return ResolvedConfig(
            formatting=FormattingConfig(
                max_chars=self._fmt_max_chars.value(),
                max_lines=self._fmt_max_lines.value(),
                target_cps=self._fmt_target_cps.value(),
                min_dur=self._fmt_min_dur.value(),
                max_dur=self._fmt_max_dur.value(),
                allow_commas=self._fmt_allow_commas.isChecked(),
                allow_medium=self._fmt_allow_medium.isChecked(),
                prefer_punct_splits=self._fmt_prefer_punct.isChecked(),
                min_gap=self._fmt_min_gap.value(),
                pad=self._fmt_pad.value(),
            ),
            transcription=TranscriptionConfig(
                vad_filter=self._tx_vad_filter.isChecked(),
                condition_on_previous_text=self._tx_condition_prev.isChecked(),
                no_speech_threshold=self._tx_no_speech.value(),
                log_prob_threshold=self._tx_log_prob.value(),
                compression_ratio_threshold=self._tx_compression.value(),
                initial_prompt=self._tx_initial_prompt.text(),
            ),
            silence=SilenceConfig(
                silence_min_dur=self._sil_min_dur.value(),
                silence_threshold_db=self._sil_threshold.value(),
            ),
        )

    def _resolve_output_path(self, input_path: Path, fmt: str) -> Path:
        """Determine the output file path for a given input."""
        from audio_visualizer.ui.sessionFilePicker import resolve_output_directory

        parent = resolve_output_directory(
            explicit_directory=self._output_dir_edit.text().strip(),
            session_context=self.session_context,
            source_path=input_path,
        )
        return parent / f"{input_path.stem}.{fmt}"

    def _resolve_side_output(self, input_path: Path, ext: str, enabled: bool) -> Optional[Path]:
        """Return a side-output path if the checkbox is enabled, else None."""
        if not enabled:
            return None
        from audio_visualizer.ui.sessionFilePicker import resolve_output_directory

        parent = resolve_output_directory(
            explicit_directory=self._output_dir_edit.text().strip(),
            session_context=self.session_context,
            source_path=input_path,
        )
        return parent / f"{input_path.stem}{ext}"

    # ==================================================================
    # BaseTab contract
    # ==================================================================

    def validate_settings(self) -> tuple[bool, str]:
        if self._input_list.count() == 0:
            return False, "No input files in the queue."
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "input_files": self._get_input_paths(),
            "output_dir": self._output_dir_edit.text(),
            "format": self._format_combo.currentText(),
            "model": self._model_combo.currentText(),
            "device": self._device_combo.currentText(),
            "mode": self._mode_combo.currentText(),
            "language": self._language_edit.text(),
            "word_level": self._word_level_cb.isChecked(),
            "preset": self._preset_combo.currentText(),
            "formatting": {
                "max_chars": self._fmt_max_chars.value(),
                "max_lines": self._fmt_max_lines.value(),
                "target_cps": self._fmt_target_cps.value(),
                "min_dur": self._fmt_min_dur.value(),
                "max_dur": self._fmt_max_dur.value(),
                "allow_commas": self._fmt_allow_commas.isChecked(),
                "allow_medium": self._fmt_allow_medium.isChecked(),
                "prefer_punct_splits": self._fmt_prefer_punct.isChecked(),
                "min_gap": self._fmt_min_gap.value(),
                "pad": self._fmt_pad.value(),
            },
            "transcription": {
                "vad_filter": self._tx_vad_filter.isChecked(),
                "condition_on_previous_text": self._tx_condition_prev.isChecked(),
                "no_speech_threshold": self._tx_no_speech.value(),
                "log_prob_threshold": self._tx_log_prob.value(),
                "compression_ratio_threshold": self._tx_compression.value(),
                "initial_prompt": self._tx_initial_prompt.text(),
            },
            "silence": {
                "silence_min_dur": self._sil_min_dur.value(),
                "silence_threshold_db": self._sil_threshold.value(),
            },
            "side_outputs": {
                "transcript": self._out_transcript.isChecked(),
                "segments": self._out_segments.isChecked(),
                "json_bundle": self._out_json_bundle.isChecked(),
            },
            "diarize": self._diarize_cb.isChecked(),
            "hf_token": self._hf_token_edit.text(),
            "diagnostics": {
                "keep_wav": self._diag_keep_wav.isChecked(),
                "dry_run": self._diag_dry_run.isChecked(),
            },
            "advanced_visible": self._advanced_toggle.isChecked(),
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        # Input files
        self._input_list.clear()
        for p in data.get("input_files", []):
            self._input_list.addItem(p)

        # Output
        self._output_dir_edit.setText(data.get("output_dir", ""))
        fmt = data.get("format", "srt")
        idx = self._format_combo.findText(fmt)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)

        # Model — handle both display names and internal identifiers
        model = data.get("model", "base")
        # If stored value is an internal id, find its display name
        display = next((k for k, v in _MODEL_MAP.items() if v == model), model)
        idx = self._model_combo.findText(display)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

        device = data.get("device", "auto")
        idx = self._device_combo.findText(device)
        if idx >= 0:
            self._device_combo.setCurrentIndex(idx)

        # General
        mode = data.get("mode", "general")
        idx = self._mode_combo.findText(mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)

        self._language_edit.setText(data.get("language", ""))
        self._word_level_cb.setChecked(data.get("word_level", True))

        # Preset
        preset = data.get("preset", "(none)")
        idx = self._preset_combo.findText(preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)

        # Formatting
        fmt_data = data.get("formatting", {})
        if fmt_data:
            self._fmt_max_chars.setValue(fmt_data.get("max_chars", 42))
            self._fmt_max_lines.setValue(fmt_data.get("max_lines", 2))
            self._fmt_target_cps.setValue(fmt_data.get("target_cps", 17.0))
            self._fmt_min_dur.setValue(fmt_data.get("min_dur", 1.0))
            self._fmt_max_dur.setValue(fmt_data.get("max_dur", 6.0))
            self._fmt_allow_commas.setChecked(fmt_data.get("allow_commas", True))
            self._fmt_allow_medium.setChecked(fmt_data.get("allow_medium", True))
            self._fmt_prefer_punct.setChecked(fmt_data.get("prefer_punct_splits", False))
            self._fmt_min_gap.setValue(fmt_data.get("min_gap", 0.08))
            self._fmt_pad.setValue(fmt_data.get("pad", 0.0))

        # Transcription
        tx_data = data.get("transcription", {})
        if tx_data:
            self._tx_vad_filter.setChecked(tx_data.get("vad_filter", True))
            self._tx_condition_prev.setChecked(tx_data.get("condition_on_previous_text", True))
            self._tx_no_speech.setValue(tx_data.get("no_speech_threshold", 0.6))
            self._tx_log_prob.setValue(tx_data.get("log_prob_threshold", -1.0))
            self._tx_compression.setValue(tx_data.get("compression_ratio_threshold", 2.4))
            self._tx_initial_prompt.setText(tx_data.get("initial_prompt", ""))

        # Silence
        sil_data = data.get("silence", {})
        if sil_data:
            self._sil_min_dur.setValue(sil_data.get("silence_min_dur", 0.2))
            self._sil_threshold.setValue(sil_data.get("silence_threshold_db", -35.0))

        # Side outputs
        side = data.get("side_outputs", {})
        self._out_transcript.setChecked(side.get("transcript", False))
        self._out_segments.setChecked(side.get("segments", False))
        self._out_json_bundle.setChecked(side.get("json_bundle", True))

        # Diarization
        self._diarize_cb.setChecked(data.get("diarize", False))
        self._hf_token_edit.setText(data.get("hf_token", ""))

        # Diagnostics
        diag = data.get("diagnostics", {})
        self._diag_keep_wav.setChecked(diag.get("keep_wav", False))
        self._diag_dry_run.setChecked(diag.get("dry_run", False))

        # Advanced toggle
        self._advanced_toggle.setChecked(data.get("advanced_visible", False))

    # ==================================================================
    # Global busy
    # ==================================================================

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        if owner_tab_id == self.tab_id:
            return
        self._start_btn.setEnabled(not is_busy)

    # ==================================================================
    # Transcription lifecycle
    # ==================================================================

    def _start_transcription(self) -> None:
        valid, msg = self.validate_settings()
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return

        if self._active_model_worker is not None:
            QMessageBox.information(
                self,
                "Model Loading",
                "Wait for the current model load to finish before generating SRTs.",
            )
            return

        if self._main_window and hasattr(self._main_window, "try_start_job"):
            if not self._main_window.try_start_job(self.tab_id):
                return

        input_paths = self._get_input_paths()
        fmt = self._format_combo.currentText()
        cfg = self._build_resolved_config()
        mode_str = self._mode_combo.currentText()
        mode = PipelineMode(mode_str)
        language = self._language_edit.text().strip() or None
        word_level = self._word_level_cb.isChecked()
        display_name = self._model_combo.currentText()
        model_name = _MODEL_MAP.get(display_name, display_name)
        device = self._device_combo.currentText()

        self._event_log.clear()
        self._append_event(f"Starting transcription with model '{display_name}' ({model_name})")
        self._append_event(f"Processing {len(input_paths)} file(s)...")
        diarize = self._diarize_cb.isChecked()
        hf_token = self._hf_token_edit.text().strip() or None
        keep_wav = self._diag_keep_wav.isChecked()
        dry_run = self._diag_dry_run.isChecked()

        jobs: list[SrtGenJobSpec] = []
        for p_str in input_paths:
            inp = Path(p_str)
            out = self._resolve_output_path(inp, fmt)
            jobs.append(SrtGenJobSpec(
                input_path=inp,
                output_path=out,
                fmt=fmt,
                cfg=dataclasses.replace(
                    cfg,
                    formatting=dataclasses.replace(cfg.formatting),
                    transcription=dataclasses.replace(cfg.transcription),
                    silence=dataclasses.replace(cfg.silence),
                ),
                model_name=model_name,
                device=device,
                language=language,
                word_level=word_level,
                mode=mode,
                transcript_path=self._resolve_side_output(inp, ".transcript.txt", self._out_transcript.isChecked()),
                segments_path=self._resolve_side_output(inp, ".segments.json", self._out_segments.isChecked()),
                json_bundle_path=self._resolve_side_output(inp, ".bundle.json", self._out_json_bundle.isChecked()),
                diarize=diarize,
                hf_token=hf_token,
                dry_run=dry_run,
                keep_wav=keep_wav,
            ))

        emitter = AppEventEmitter()
        worker = SrtGenWorker(jobs=jobs, emitter=emitter)
        self._active_worker = worker

        # Connect signals
        worker.signals.progress.connect(self._on_progress)
        worker.signals.stage.connect(self._on_stage)
        worker.signals.log.connect(self._on_log)
        worker.signals.completed.connect(self._on_transcription_completed)
        worker.signals.failed.connect(self._on_transcription_failed)
        worker.signals.canceled.connect(self._on_transcription_canceled)

        # Update UI
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Starting transcription...")
        if self._main_window and hasattr(self._main_window, "show_job_status"):
            self._main_window.show_job_status(
                "srt_gen",
                self.tab_id,
                f"Generating SRTs for {len(jobs)} file(s)...",
            )

        if self._main_window and hasattr(self._main_window, "render_thread_pool"):
            self._main_window.render_thread_pool.start(worker)
        else:
            self._thread_pool.start(worker)
        logger.info("Started SRT Gen worker with %d files", len(jobs))

    def cancel_job(self) -> None:
        if self._active_worker is not None:
            self._active_worker.cancel()
            self._status_label.setText("Cancelling...")
            logger.info("Cancel requested for SRT Gen worker")

    # ==================================================================
    # Worker signal handlers
    # ==================================================================

    def _on_progress(self, percent: float, message: str, data: dict) -> None:
        if percent >= 0:
            self._progress_bar.setValue(int(percent))
            if (
                self._active_worker is not None
                and self._main_window
                and hasattr(self._main_window, "update_job_progress")
            ):
                self._main_window.update_job_progress(percent, message or "")
        if message:
            self._status_label.setText(message)
            self._append_event(message)
            if (
                self._active_worker is not None
                and self._main_window
                and hasattr(self._main_window, "update_job_status")
            ):
                self._main_window.update_job_status(message)

    def _on_stage(self, name: str, index: int, total: int, data: dict) -> None:
        self._status_label.setText(name)
        stage_text = f"[Stage {index}/{total}] {name}" if index >= 0 and total > 0 else name
        self._append_event(stage_text)
        if (
            self._active_worker is not None
            and self._main_window
            and hasattr(self._main_window, "update_job_status")
        ):
            self._main_window.update_job_status(name)

    def _on_log(self, level: str, message: str, data: dict) -> None:
        logger.log(
            logging.getLevelName(level) if isinstance(level, str) else logging.INFO,
            "SRT Gen: %s",
            message,
        )
        self._append_event(f"[{level}] {message}")

    def _on_transcription_completed(self, data: dict) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(100)

        results = data.get("results", [])
        total = data.get("total", 0)
        succeeded = sum(1 for r in results if r.get("success"))
        failed = total - succeeded

        summary = (
            f"Completed: {succeeded}/{total} succeeded"
            + (f", {failed} failed" if failed else "")
        )
        self._status_label.setText(summary)
        self._append_event(summary)

        # The model was loaded by the worker — update UI state
        self._sync_model_state_from_manager()

        # Register outputs as session assets
        for r in results:
            if not r.get("success"):
                continue
            self._register_result_assets(r)

        if self._main_window and hasattr(self._main_window, "show_job_completed"):
            self._main_window.show_job_completed(summary, owner_tab_id=self.tab_id)
        logger.info("SRT Gen batch completed: %d/%d succeeded", succeeded, total)

    def _on_file_completed(self, result: dict) -> None:
        """Handle per-file completion (called from completed data)."""
        if result.get("success"):
            self._register_result_assets(result)

    def _on_transcription_failed(self, error_message: str, data: dict) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Failed: {error_message}")
        self._append_event(f"FAILED: {error_message}")
        self._sync_model_state_from_manager()
        if self._main_window and hasattr(self._main_window, "show_job_failed"):
            self._main_window.show_job_failed(error_message, owner_tab_id=self.tab_id)
        logger.error("SRT Gen batch failed: %s", error_message)

    def _on_transcription_canceled(self, message: str) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(f"Cancelled: {message}")
        self._append_event(f"Cancelled: {message}")
        self._sync_model_state_from_manager()
        if self._main_window and hasattr(self._main_window, "show_job_canceled"):
            self._main_window.show_job_canceled(message, owner_tab_id=self.tab_id)
        logger.info("SRT Gen batch cancelled: %s", message)

    # ==================================================================
    # Session asset registration
    # ==================================================================

    def _register_result_assets(self, result: dict) -> None:
        """Register output files from a transcription result as SessionAssets."""
        output_path = result.get("output_path")
        if output_path:
            out = Path(output_path)
            if out.exists():
                self.register_output_asset(SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=out.name,
                    path=out,
                    category="subtitle",
                    source_tab=self.tab_id,
                    role="subtitle_source",
                ))

        transcript_path = result.get("transcript_path")
        if transcript_path:
            tp = Path(transcript_path)
            if tp.exists():
                self.register_output_asset(SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=tp.name,
                    path=tp,
                    category="transcript",
                    source_tab=self.tab_id,
                ))

        segments_path = result.get("segments_path")
        if segments_path:
            sp = Path(segments_path)
            if sp.exists():
                self.register_output_asset(SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=sp.name,
                    path=sp,
                    category="segments",
                    source_tab=self.tab_id,
                ))

        json_bundle_path = result.get("json_bundle_path")
        if json_bundle_path:
            jp = Path(json_bundle_path)
            if jp.exists():
                self.register_output_asset(SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=jp.name,
                    path=jp,
                    category="json_bundle",
                    source_tab=self.tab_id,
                ))
