"""Tests for LoRA training pipeline, dataset export, and per-speaker adaptation.

Tests the config validation, capability gating, dataset export, training
UI wiring, LoRA model selection, and per-speaker replacement rules.
Training itself requires GPU and is not exercised in these tests.
"""
from __future__ import annotations

import csv
import json
import struct
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from audio_visualizer.core.correctionDb import CorrectionDatabase


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Return a CorrectionDatabase backed by a temp file."""
    return CorrectionDatabase(db_path=tmp_path / "test_corrections.db")


def _make_wav(path: Path, duration_ms: int = 500, sample_rate: int = 16000) -> None:
    """Write a minimal valid WAV file with silence."""
    num_samples = int(sample_rate * duration_ms / 1000)
    pcm_data = b"\x00\x00" * num_samples  # 16-bit silence
    channels = 1
    sample_width = 2
    data_size = len(pcm_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * channels * sample_width,
        channels * sample_width,
        sample_width * 8,
        b"data",
        data_size,
    )
    with open(path, "wb") as f:
        f.write(header)
        f.write(pcm_data)


# ------------------------------------------------------------------
# 6.1: Training Data Export
# ------------------------------------------------------------------


class TestTrainingDataExport:
    """Test CorrectionDatabase.export_training_dataset."""

    def test_export_empty_db(self, db, tmp_path):
        output_dir = tmp_path / "export"
        exported, skipped, warnings = db.export_training_dataset(output_dir)
        assert exported == 0
        assert skipped == 0
        assert len(warnings) == 1
        assert "No correction pairs" in warnings[0]

    def test_export_missing_source_file(self, db, tmp_path):
        db.record_correction(
            source_media_path="/nonexistent/audio.wav",
            time_start_ms=0,
            time_end_ms=1000,
            original_text="wrong",
            corrected_text="right",
        )
        output_dir = tmp_path / "export"
        exported, skipped, warnings = db.export_training_dataset(output_dir)
        assert exported == 0
        assert skipped == 1
        assert any("not found" in w for w in warnings)

        # metadata.csv should still be written (empty data section)
        csv_path = output_dir / "metadata.csv"
        assert csv_path.is_file()

    def test_export_with_valid_source(self, db, tmp_path):
        # Create a source WAV file
        source_wav = tmp_path / "source.wav"
        _make_wav(source_wav, duration_ms=2000)

        db.record_correction(
            source_media_path=str(source_wav),
            time_start_ms=0,
            time_end_ms=500,
            original_text="wrong",
            corrected_text="right",
            speaker_label="Alice",
        )

        output_dir = tmp_path / "export"

        # Mock PyAV extraction since it requires proper container
        with patch(
            "audio_visualizer.core.correctionDb._extract_audio_segment"
        ) as mock_extract:
            # Simulate writing a clip file
            def fake_extract(source_path, output_path, start_ms, end_ms, sample_rate=16000):
                _make_wav(output_path, duration_ms=end_ms - start_ms)

            mock_extract.side_effect = fake_extract

            exported, skipped, warnings = db.export_training_dataset(output_dir)

        assert exported == 1
        assert skipped == 0
        assert len(warnings) == 0

        # Check metadata.csv
        csv_path = output_dir / "metadata.csv"
        assert csv_path.is_file()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["file_name"] == "clip_00000.wav"
        assert rows[0]["text"] == "right"
        assert rows[0]["original_text"] == "wrong"
        assert rows[0]["speaker_label"] == "Alice"

        # Check clip file exists
        assert (output_dir / "clip_00000.wav").is_file()

    def test_export_invalid_time_range(self, db, tmp_path):
        source_wav = tmp_path / "source.wav"
        _make_wav(source_wav)

        db.record_correction(
            source_media_path=str(source_wav),
            time_start_ms=1000,
            time_end_ms=500,  # end < start
            original_text="wrong",
            corrected_text="right",
        )

        output_dir = tmp_path / "export"
        exported, skipped, warnings = db.export_training_dataset(output_dir)
        assert exported == 0
        assert skipped == 1
        assert any("invalid time range" in w for w in warnings)

    def test_export_progress_callback(self, db, tmp_path):
        source_wav = tmp_path / "source.wav"
        _make_wav(source_wav, duration_ms=2000)

        db.record_correction(
            source_media_path=str(source_wav),
            time_start_ms=0,
            time_end_ms=500,
            original_text="a",
            corrected_text="b",
        )

        output_dir = tmp_path / "export"
        progress_calls: list[tuple] = []

        def on_progress(current, total, message):
            progress_calls.append((current, total, message))

        with patch(
            "audio_visualizer.core.correctionDb._extract_audio_segment"
        ) as mock_extract:
            mock_extract.side_effect = lambda **kw: _make_wav(kw["output_path"])

            def fake_extract(source_path, output_path, start_ms, end_ms, sample_rate=16000):
                _make_wav(output_path, duration_ms=end_ms - start_ms)

            mock_extract.side_effect = fake_extract
            db.export_training_dataset(output_dir, progress_callback=on_progress)

        assert len(progress_calls) >= 1
        # Last call should be "Export complete"
        assert "complete" in progress_calls[-1][2].lower()


# ------------------------------------------------------------------
# 6.2: LoRA Training Config Validation
# ------------------------------------------------------------------


class TestLoraTrainingConfig:
    """Test LoraTrainingConfig and validate_training_config."""

    def test_default_config(self):
        from audio_visualizer.srt.training.loraTrainer import LoraTrainingConfig

        config = LoraTrainingConfig()
        assert config.base_model_name == "base"
        assert config.num_epochs == 3
        assert config.learning_rate == 1e-4
        assert config.batch_size == 4
        assert config.lora_rank == 8

    def test_validate_valid_config(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        # Create a valid dataset
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        metadata = dataset_dir / "metadata.csv"
        with open(metadata, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file_name", "text"])
            writer.writeheader()
            for i in range(10):
                _make_wav(dataset_dir / f"clip_{i:05d}.wav")
                writer.writerow({"file_name": f"clip_{i:05d}.wav", "text": f"sample {i}"})

        config = LoraTrainingConfig(
            dataset_dir=dataset_dir,
            output_name="test_model",
        )
        errors = validate_training_config(config)
        assert errors == []

    def test_validate_missing_dataset(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        config = LoraTrainingConfig(
            dataset_dir=tmp_path / "nonexistent",
            output_name="test",
        )
        errors = validate_training_config(config)
        assert any("does not exist" in e for e in errors)

    def test_validate_missing_metadata(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        config = LoraTrainingConfig(
            dataset_dir=dataset_dir,
            output_name="test",
        )
        errors = validate_training_config(config)
        assert any("metadata.csv" in e for e in errors)

    def test_validate_empty_dataset(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        metadata = dataset_dir / "metadata.csv"
        with open(metadata, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file_name", "text"])
            writer.writeheader()
            # No rows

        config = LoraTrainingConfig(
            dataset_dir=dataset_dir,
            output_name="test",
        )
        errors = validate_training_config(config)
        assert any("empty" in e.lower() for e in errors)

    def test_validate_bad_model_name(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        metadata = dataset_dir / "metadata.csv"
        with open(metadata, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file_name", "text"])
            writer.writeheader()
            for i in range(10):
                writer.writerow({"file_name": f"clip_{i}.wav", "text": f"sample {i}"})

        config = LoraTrainingConfig(
            base_model_name="nonexistent_model",
            dataset_dir=dataset_dir,
            output_name="test",
        )
        errors = validate_training_config(config)
        assert any("Unknown base model" in e for e in errors)

    def test_validate_empty_output_name(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "metadata.csv").write_text(
            "file_name,text\nclip.wav,hello\n", encoding="utf-8"
        )

        config = LoraTrainingConfig(
            dataset_dir=dataset_dir,
            output_name="",
        )
        errors = validate_training_config(config)
        assert any("empty" in e.lower() for e in errors)

    def test_validate_bad_hyperparams(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            validate_training_config,
        )

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "metadata.csv").write_text(
            "file_name,text\nclip.wav,hello\n", encoding="utf-8"
        )

        config = LoraTrainingConfig(
            dataset_dir=dataset_dir,
            output_name="test",
            num_epochs=0,
            learning_rate=-1.0,
            batch_size=0,
            lora_rank=0,
        )
        errors = validate_training_config(config)
        assert len(errors) >= 4  # At least one error per bad param


class TestLoraTrainingGating:
    """Test that training is gated behind capability checks."""

    def test_train_lora_requires_training_stack(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            train_lora,
        )

        config = LoraTrainingConfig(
            dataset_dir=tmp_path,
            output_name="test",
        )

        with patch("audio_visualizer.capabilities.has_training_stack", return_value=False):
            with pytest.raises(RuntimeError, match="Training stack unavailable"):
                train_lora(config)

    def test_train_lora_requires_cuda(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import (
            LoraTrainingConfig,
            train_lora,
        )

        config = LoraTrainingConfig(
            dataset_dir=tmp_path,
            output_name="test",
        )

        with patch("audio_visualizer.capabilities.has_training_stack", return_value=True):
            with patch("audio_visualizer.capabilities.has_cuda", return_value=False):
                with pytest.raises(RuntimeError, match="CUDA is required"):
                    train_lora(config)


class TestLoraModelsDir:
    """Test the LoRA models directory utilities."""

    def test_get_lora_models_dir(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import get_lora_models_dir

        with patch("audio_visualizer.srt.training.loraTrainer.get_data_dir", return_value=tmp_path):
            d = get_lora_models_dir()
            assert d == tmp_path / "lora_models"
            assert d.is_dir()

    def test_list_trained_models(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import list_trained_models

        models_dir = tmp_path / "lora_models"
        models_dir.mkdir()
        (models_dir / "model_a").mkdir()
        (models_dir / "model_b").mkdir()
        (models_dir / "not_a_dir.txt").write_text("ignored")

        with patch("audio_visualizer.srt.training.loraTrainer.get_data_dir", return_value=tmp_path):
            models = list_trained_models()
            assert models == ["model_a", "model_b"]

    def test_list_trained_models_empty(self, tmp_path):
        from audio_visualizer.srt.training.loraTrainer import list_trained_models

        with patch("audio_visualizer.srt.training.loraTrainer.get_data_dir", return_value=tmp_path):
            models = list_trained_models()
            assert models == []


# ------------------------------------------------------------------
# 6.4: LoRA Selection - Job Spec and Model Resolution
# ------------------------------------------------------------------


class TestSrtGenJobSpecLora:
    """Test lora_name field in SrtGenJobSpec."""

    def test_job_spec_default_no_lora(self):
        from audio_visualizer.ui.workers.srtGenWorker import SrtGenJobSpec
        from audio_visualizer.srt.models import PipelineMode, ResolvedConfig

        spec = SrtGenJobSpec(
            input_path=Path("/input.wav"),
            output_path=Path("/output.srt"),
            fmt="srt",
            cfg=ResolvedConfig(),
            model_name="base",
            device="auto",
            language=None,
            word_level=True,
            mode=PipelineMode.GENERAL,
        )
        assert spec.lora_name is None

    def test_job_spec_with_lora(self):
        from audio_visualizer.ui.workers.srtGenWorker import SrtGenJobSpec
        from audio_visualizer.srt.models import PipelineMode, ResolvedConfig

        spec = SrtGenJobSpec(
            input_path=Path("/input.wav"),
            output_path=Path("/output.srt"),
            fmt="srt",
            cfg=ResolvedConfig(),
            model_name="base",
            device="auto",
            language=None,
            word_level=True,
            mode=PipelineMode.GENERAL,
            lora_name="my_lora",
        )
        assert spec.lora_name == "my_lora"


class TestLoraModelResolution:
    """Test _resolve_lora_ct2_path helper."""

    def test_resolve_existing_lora(self, tmp_path):
        from audio_visualizer.ui.workers.srtGenWorker import _resolve_lora_ct2_path

        models_dir = tmp_path / "lora_models"
        ct2_dir = models_dir / "my_model" / "ct2"
        ct2_dir.mkdir(parents=True)

        with patch(
            "audio_visualizer.srt.training.loraTrainer.get_lora_models_dir",
            return_value=models_dir,
        ):
            result = _resolve_lora_ct2_path("my_model")
            assert result == ct2_dir

    def test_resolve_missing_lora(self, tmp_path):
        from audio_visualizer.ui.workers.srtGenWorker import _resolve_lora_ct2_path

        models_dir = tmp_path / "lora_models"
        models_dir.mkdir()

        with patch(
            "audio_visualizer.srt.training.loraTrainer.get_lora_models_dir",
            return_value=models_dir,
        ):
            result = _resolve_lora_ct2_path("nonexistent")
            assert result is None


# ------------------------------------------------------------------
# 6.4: Model Manager Cache Keys
# ------------------------------------------------------------------


class TestModelManagerCacheKeys:
    """Test that ModelManager distinguishes base from LoRA models."""

    def test_model_info_includes_lora_name(self):
        from audio_visualizer.srt.modelManager import ModelInfo

        info = ModelInfo(
            model_name="base",
            device="cpu",
            compute_type="float32",
            lora_name="my_lora",
        )
        assert info.lora_name == "my_lora"

    def test_model_info_default_no_lora(self):
        from audio_visualizer.srt.modelManager import ModelInfo

        info = ModelInfo(
            model_name="base",
            device="cpu",
            compute_type="float32",
        )
        assert info.lora_name is None


# ------------------------------------------------------------------
# 6.5: Per-Speaker Adaptation
# ------------------------------------------------------------------


class TestPerSpeakerReplacement:
    """Test per-speaker replacement rules applied during pipeline post-processing."""

    def test_apply_rules_to_text(self):
        from audio_visualizer.srt.core.pipeline import _apply_rules_to_text

        rules = [
            {"pattern": "gonna", "replacement": "going to", "is_regex": False},
            {"pattern": "wanna", "replacement": "want to", "is_regex": False},
        ]
        assert _apply_rules_to_text("I'm gonna do it", rules) == "I'm going to do it"
        assert _apply_rules_to_text("I wanna go", rules) == "I want to go"

    def test_apply_regex_rules(self):
        from audio_visualizer.srt.core.pipeline import _apply_rules_to_text

        rules = [
            {"pattern": r"\bum+\b", "replacement": "", "is_regex": True},
        ]
        assert _apply_rules_to_text("so umm like", rules) == "so  like"

    def test_apply_invalid_regex_skipped(self):
        from audio_visualizer.srt.core.pipeline import _apply_rules_to_text

        rules = [
            {"pattern": r"[invalid", "replacement": "", "is_regex": True},
        ]
        # Should not raise, just skip the invalid regex
        result = _apply_rules_to_text("test text", rules)
        assert result == "test text"

    def test_correction_db_replacements_with_speakers(self, db):
        from audio_visualizer.srt.core.pipeline import _apply_correction_db_replacements
        from audio_visualizer.srt.models import SubtitleBlock

        # Add per-speaker rules
        db.add_replacement_rule("gonna", "going to", speaker_label="Alice")
        db.add_replacement_rule("wanna", "want to", speaker_label="Bob")

        subs = [
            SubtitleBlock(start=0.0, end=1.0, lines=["I'm gonna go"], speaker="Alice"),
            SubtitleBlock(start=1.0, end=2.0, lines=["I wanna try"], speaker="Bob"),
            SubtitleBlock(start=2.0, end=3.0, lines=["gonna wanna"], speaker=None),
        ]

        with patch(
            "audio_visualizer.core.correctionDb.CorrectionDatabase",
            return_value=db,
        ):
            result = _apply_correction_db_replacements(subs, None)

        # Alice: "gonna" -> "going to"
        assert result[0].lines == ["I'm going to go"]
        # Bob: "wanna" -> "want to"
        assert result[1].lines == ["I want to try"]
        # No speaker, no global rules -> unchanged
        assert result[2].lines == ["gonna wanna"]

    def test_correction_db_replacements_global_fallback(self, db):
        from audio_visualizer.srt.core.pipeline import _apply_correction_db_replacements
        from audio_visualizer.srt.models import SubtitleBlock

        # Add global rules (no speaker)
        db.add_replacement_rule("gonna", "going to")

        subs = [
            SubtitleBlock(start=0.0, end=1.0, lines=["I'm gonna go"], speaker="Alice"),
            SubtitleBlock(start=1.0, end=2.0, lines=["gonna try"], speaker=None),
        ]

        with patch(
            "audio_visualizer.core.correctionDb.CorrectionDatabase",
            return_value=db,
        ):
            result = _apply_correction_db_replacements(subs, None)

        # Both should get the global rule applied
        assert result[0].lines == ["I'm going to go"]
        assert result[1].lines == ["going to try"]

    def test_correction_db_replacements_both_speaker_and_global(self, db):
        from audio_visualizer.srt.core.pipeline import _apply_correction_db_replacements
        from audio_visualizer.srt.models import SubtitleBlock

        # Global rule
        db.add_replacement_rule("um", "")
        # Per-speaker rule
        db.add_replacement_rule("gonna", "going to", speaker_label="Alice")

        subs = [
            SubtitleBlock(
                start=0.0, end=1.0,
                lines=["um gonna go"], speaker="Alice"
            ),
        ]

        with patch(
            "audio_visualizer.core.correctionDb.CorrectionDatabase",
            return_value=db,
        ):
            result = _apply_correction_db_replacements(subs, None)

        # Per-speaker first, then global
        assert result[0].lines == [" going to go"]

    def test_correction_db_unavailable_returns_unmodified(self):
        from audio_visualizer.srt.core.pipeline import _apply_correction_db_replacements
        from audio_visualizer.srt.models import SubtitleBlock

        subs = [
            SubtitleBlock(start=0.0, end=1.0, lines=["original text"]),
        ]

        with patch(
            "audio_visualizer.core.correctionDb.CorrectionDatabase",
            side_effect=Exception("DB unavailable"),
        ):
            result = _apply_correction_db_replacements(subs, None)

        assert result[0].lines == ["original text"]


# ------------------------------------------------------------------
# 6.3: LoRA Training UI (widget tests)
# ------------------------------------------------------------------


class TestAdvancedTabTrainingUI:
    """Test LoRA training controls in AdvancedTab."""

    @pytest.fixture
    def tab(self, qtbot, tmp_path):
        from PySide6.QtWidgets import QApplication
        from audio_visualizer.ui.tabs.advancedTab import AdvancedTab

        tab = AdvancedTab()
        qtbot.addWidget(tab)

        # Inject temp DB
        db = CorrectionDatabase(db_path=tmp_path / "test.db")
        tab._db = db
        return tab

    def test_training_controls_exist(self, tab):
        """Verify LoRA training controls are present."""
        assert hasattr(tab, "_train_base_model_combo")
        assert hasattr(tab, "_train_dataset_edit")
        assert hasattr(tab, "_train_output_name_edit")
        assert hasattr(tab, "_train_epochs_spin")
        assert hasattr(tab, "_train_lr_spin")
        assert hasattr(tab, "_train_batch_size_spin")
        assert hasattr(tab, "_train_lora_rank_spin")
        assert hasattr(tab, "_train_start_btn")
        assert hasattr(tab, "_train_cancel_btn")
        assert hasattr(tab, "_train_progress_bar")
        assert hasattr(tab, "_trained_models_list")

    def test_export_training_btn_exists(self, tab):
        """Verify export training data button is present."""
        assert hasattr(tab, "_export_training_btn")

    def test_collect_settings_includes_training(self, tab):
        """Settings should include training config."""
        settings = tab.collect_settings()
        assert "training" in settings
        training = settings["training"]
        assert "base_model" in training
        assert "epochs" in training
        assert "learning_rate" in training
        assert "batch_size" in training
        assert "lora_rank" in training

    def test_apply_settings_restores_training(self, tab):
        """apply_settings should restore training config."""
        tab.apply_settings({
            "training": {
                "base_model": "small",
                "dataset_dir": "/some/path",
                "output_name": "my_model",
                "epochs": 5,
                "learning_rate": 0.001,
                "batch_size": 8,
                "lora_rank": 16,
            },
        })
        assert tab._train_base_model_combo.currentText() == "small"
        assert tab._train_dataset_edit.text() == "/some/path"
        assert tab._train_output_name_edit.text() == "my_model"
        assert tab._train_epochs_spin.value() == 5
        assert tab._train_lr_spin.value() == 0.001
        assert tab._train_batch_size_spin.value() == 8
        assert tab._train_lora_rank_spin.value() == 16

    def test_trained_models_refresh(self, tab, tmp_path):
        """Refresh should list trained model directories."""
        models_dir = tmp_path / "lora_models"
        models_dir.mkdir()
        (models_dir / "model_a").mkdir()
        (models_dir / "model_b").mkdir()

        with patch.object(tab, "_get_lora_models_dir", return_value=models_dir):
            tab._refresh_trained_models()

        assert tab._trained_models_list.count() == 2

    def test_capability_label_updates(self, tab):
        """Capability label should reflect training stack status."""
        with patch("audio_visualizer.capabilities.has_training_stack", return_value=False):
            tab._update_training_capability_label()
        assert "unavailable" in tab._training_capability_label.text().lower()


# ------------------------------------------------------------------
# 6.4: SrtGenTab LoRA dropdown
# ------------------------------------------------------------------


class TestSrtGenTabLora:
    """Test LoRA adapter dropdown in SrtGenTab."""

    @pytest.fixture
    def tab(self, qtbot):
        from audio_visualizer.ui.tabs.srtGenTab import SrtGenTab

        tab = SrtGenTab()
        qtbot.addWidget(tab)
        return tab

    def test_lora_combo_exists(self, tab):
        """LoRA combo box should be present."""
        assert hasattr(tab, "_lora_combo")
        # Default should be "(none)"
        assert tab._lora_combo.currentText() == "(none)"
        assert tab._selected_lora_name() is None

    def test_lora_refresh(self, tab, tmp_path):
        """Refreshing should populate from trained models directory."""
        with patch(
            "audio_visualizer.srt.training.loraTrainer.list_trained_models",
            return_value=["model_a", "model_b"],
        ):
            tab._refresh_lora_models()

        assert tab._lora_combo.count() == 3  # (none) + 2 models
        assert tab._lora_combo.itemText(1) == "model_a"
        assert tab._lora_combo.itemText(2) == "model_b"

    def test_collect_settings_includes_lora(self, tab):
        """Settings should include lora_name."""
        settings = tab.collect_settings()
        assert "lora_name" in settings

    def test_apply_settings_restores_lora(self, tab):
        """apply_settings should restore lora selection."""
        with patch(
            "audio_visualizer.srt.training.loraTrainer.list_trained_models",
            return_value=["my_lora"],
        ):
            tab.apply_settings({"lora_name": "my_lora"})
            # After refresh + apply, should be selected
            assert tab._lora_combo.currentData() == "my_lora"
