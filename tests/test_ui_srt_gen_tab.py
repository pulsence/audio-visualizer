"""Tests for SrtGenTab from audio_visualizer.ui.tabs.srtGenTab."""

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

app = QApplication.instance() or QApplication([])

import pytest
from unittest.mock import MagicMock

from audio_visualizer.ui.workspaceContext import WorkspaceContext
from audio_visualizer.ui.tabs.srtGenTab import SrtGenTab


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSrtGenTabIdentity:
    def test_tab_id_and_title(self):
        tab = SrtGenTab()
        assert tab.tab_id == "srt_gen"
        assert tab.tab_title == "SRT Gen"


class TestSrtGenTabSettings:
    def test_collect_settings_structure(self):
        tab = SrtGenTab()
        settings = tab.collect_settings()

        # Top-level keys
        expected_keys = {
            "input_files",
            "output_dir",
            "format",
            "model",
            "device",
            "mode",
            "language",
            "word_level",
            "preset",
            "formatting",
            "transcription",
            "silence",
            "side_outputs",
            "diarize",
            "hf_token",
            "diagnostics",
            "advanced_visible",
        }
        assert set(settings.keys()) == expected_keys

        # Formatting sub-keys
        fmt_keys = {
            "max_chars", "max_lines", "target_cps", "min_dur", "max_dur",
            "allow_commas", "allow_medium", "prefer_punct_splits",
            "min_gap", "pad",
        }
        assert set(settings["formatting"].keys()) == fmt_keys

        # Transcription sub-keys
        tx_keys = {
            "vad_filter", "condition_on_previous_text",
            "no_speech_threshold", "log_prob_threshold",
            "compression_ratio_threshold", "initial_prompt",
        }
        assert set(settings["transcription"].keys()) == tx_keys

        # Silence sub-keys
        sil_keys = {"silence_min_dur", "silence_threshold_db"}
        assert set(settings["silence"].keys()) == sil_keys

        # Side outputs sub-keys
        side_keys = {"transcript", "segments", "json_bundle"}
        assert set(settings["side_outputs"].keys()) == side_keys

        # Diagnostics sub-keys
        diag_keys = {"keep_wav", "dry_run"}
        assert set(settings["diagnostics"].keys()) == diag_keys

    def test_apply_settings_roundtrip(self):
        tab = SrtGenTab()

        # Modify settings from defaults
        custom = {
            "input_files": ["/tmp/test1.mp3", "/tmp/test2.wav"],
            "output_dir": "/tmp/output",
            "format": "vtt",
            "model": "medium",
            "device": "cuda",
            "mode": "shorts",
            "language": "en",
            "word_level": False,
            "preset": "(none)",
            "formatting": {
                "max_chars": 20,
                "max_lines": 1,
                "target_cps": 15.0,
                "min_dur": 0.5,
                "max_dur": 3.0,
                "allow_commas": False,
                "allow_medium": False,
                "prefer_punct_splits": True,
                "min_gap": 0.1,
                "pad": 0.05,
            },
            "transcription": {
                "vad_filter": False,
                "condition_on_previous_text": False,
                "no_speech_threshold": 0.5,
                "log_prob_threshold": -0.5,
                "compression_ratio_threshold": 3.0,
                "initial_prompt": "test prompt",
            },
            "silence": {
                "silence_min_dur": 0.3,
                "silence_threshold_db": -40.0,
            },
            "side_outputs": {
                "transcript": True,
                "segments": True,
                "json_bundle": False,
            },
            "diarize": True,
            "hf_token": "hf_test_token",
            "diagnostics": {
                "keep_wav": True,
                "dry_run": True,
            },
            "advanced_visible": True,
        }

        tab.apply_settings(custom)
        restored = tab.collect_settings()

        assert restored["input_files"] == custom["input_files"]
        assert restored["output_dir"] == custom["output_dir"]
        assert restored["format"] == custom["format"]
        assert restored["model"] == custom["model"]
        assert restored["device"] == custom["device"]
        assert restored["mode"] == custom["mode"]
        assert restored["language"] == custom["language"]
        assert restored["word_level"] == custom["word_level"]
        assert restored["formatting"] == custom["formatting"]
        assert restored["transcription"]["vad_filter"] == custom["transcription"]["vad_filter"]
        assert restored["transcription"]["condition_on_previous_text"] == custom["transcription"]["condition_on_previous_text"]
        assert restored["transcription"]["initial_prompt"] == custom["transcription"]["initial_prompt"]
        assert restored["silence"] == custom["silence"]
        assert restored["side_outputs"] == custom["side_outputs"]
        assert restored["diarize"] == custom["diarize"]
        assert restored["hf_token"] == custom["hf_token"]
        assert restored["diagnostics"] == custom["diagnostics"]
        assert restored["advanced_visible"] == custom["advanced_visible"]


class TestSrtGenTabValidation:
    def test_validate_empty_queue_fails(self):
        tab = SrtGenTab()
        valid, msg = tab.validate_settings()
        assert valid is False
        assert "input" in msg.lower()

    def test_validate_with_file_passes(self):
        tab = SrtGenTab()
        tab._add_input_path("/tmp/test.mp3")
        valid, msg = tab.validate_settings()
        assert valid is True
        assert msg == ""

    def test_resolve_output_path_prefers_project_folder(self, tmp_path):
        tab = SrtGenTab()
        ctx = WorkspaceContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)
        tab.set_workspace_context(ctx)

        output_path = tab._resolve_output_path(tmp_path / "input.mp3", "srt")

        assert output_path == project_folder / "input.srt"


class TestSrtGenTabGlobalBusy:
    def test_set_global_busy(self):
        tab = SrtGenTab()
        assert tab._start_btn.isEnabled() is True

        # Another tab is busy — our start button should be disabled
        tab.set_global_busy(True, owner_tab_id="audio_visualizer")
        assert tab._start_btn.isEnabled() is False

        # Another tab finished — re-enable
        tab.set_global_busy(False, owner_tab_id="audio_visualizer")
        assert tab._start_btn.isEnabled() is True

    def test_set_global_busy_own_tab_ignored(self):
        tab = SrtGenTab()
        # When we are the owner, set_global_busy should not disable our button
        tab.set_global_busy(True, owner_tab_id="srt_gen")
        assert tab._start_btn.isEnabled() is True


class TestSrtGenTabEventLog:
    def test_event_log_no_max_height(self):
        tab = SrtGenTab()
        assert tab._event_log.maximumHeight() == 16777215  # QWIDGETSIZE_MAX

    def test_event_log_has_expanding_policy(self):
        from PySide6.QtWidgets import QSizePolicy
        tab = SrtGenTab()
        policy = tab._event_log.sizePolicy()
        assert policy.verticalPolicy() == QSizePolicy.Policy.Expanding


class _FakeSignal:
    def connect(self, _slot):
        return None


class _FakeWorker:
    def __init__(self, *args, **kwargs):
        self.captured_kwargs = kwargs
        self.signals = MagicMock(
            progress=_FakeSignal(),
            stage=_FakeSignal(),
            log=_FakeSignal(),
            completed=_FakeSignal(),
            failed=_FakeSignal(),
            canceled=_FakeSignal(),
        )

    def cancel(self):
        return None


class _FakeMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.try_start_calls = []
        self.job_status_calls = []
        self.render_thread_pool = MagicMock()

    def try_start_job(self, owner_tab_id):
        self.try_start_calls.append(owner_tab_id)
        return True

    def show_job_status(self, job_type, owner_tab, label):
        self.job_status_calls.append((job_type, owner_tab, label))


class TestSrtGenJobShellIntegration:
    def test_start_transcription_claims_global_job_slot(self, monkeypatch):
        main_window = _FakeMainWindow()
        tab = SrtGenTab(main_window)
        tab._add_input_path("/tmp/test.mp3")

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.srtGenTab.SrtGenWorker",
            _FakeWorker,
        )

        tab._start_transcription()

        assert main_window.try_start_calls == ["srt_gen"]
        assert len(main_window.job_status_calls) == 1
        assert main_window.job_status_calls[0][0] == "srt_gen"
        main_window.render_thread_pool.start.assert_called_once()

    def test_worker_constructed_without_model_manager(self, monkeypatch):
        """SrtGenWorker must not receive model_manager from the tab."""
        main_window = _FakeMainWindow()
        tab = SrtGenTab(main_window)
        tab._add_input_path("/tmp/test.mp3")

        captured_workers = []
        original_fake = _FakeWorker

        class _CapturingWorker(original_fake):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured_workers.append(self)

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.srtGenTab.SrtGenWorker",
            _CapturingWorker,
        )

        tab._start_transcription()

        assert len(captured_workers) == 1
        assert "model_manager" not in captured_workers[0].captured_kwargs


class TestSrtGenTabDeviceInfo:
    def test_completion_shows_device_info(self):
        """After batch completion, event log should include device info."""
        tab = SrtGenTab()

        data = {
            "results": [{"success": True}],
            "total": 1,
            "device_used": "cuda",
            "compute_type_used": "float16",
        }
        tab._on_transcription_completed(data)

        log_text = tab._event_log.toPlainText()
        assert "Last run used cuda" in log_text

    def test_completion_shows_cpu_fallback_when_cuda_requested(self):
        """When CUDA was requested but CPU was used, show fallback message."""
        tab = SrtGenTab()
        # Set the device combo to cuda
        idx = tab._device_combo.findText("cuda")
        if idx >= 0:
            tab._device_combo.setCurrentIndex(idx)

        data = {
            "results": [{"success": True}],
            "total": 1,
            "device_used": "cpu",
            "compute_type_used": "int8",
        }
        tab._on_transcription_completed(data)

        log_text = tab._event_log.toPlainText()
        assert "Last run used CPU (CUDA unavailable)" in log_text

    def test_model_load_shows_cpu_fallback(self):
        """Model load status shows fallback when CUDA was requested but CPU used."""
        tab = SrtGenTab()
        # Set the device combo to cuda
        idx = tab._device_combo.findText("cuda")
        if idx >= 0:
            tab._device_combo.setCurrentIndex(idx)

        data = {
            "display_name": "Small",
            "model_name": "small",
            "device": "cpu",
            "compute_type": "int8",
        }
        tab._on_model_load_completed(data)

        assert "CPU (CUDA unavailable)" in tab._status_label.text()
