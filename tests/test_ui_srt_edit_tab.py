"""Widget-level tests for SrtEditTab session integration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.sessionContext import SessionAsset, SessionContext
from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry
from audio_visualizer.ui.tabs.srtEditTab import SrtEditTab


class TestSrtEditTabSessionIntegration:
    def test_selecting_session_audio_loads_the_asset(self, monkeypatch):
        tab = SrtEditTab()
        ctx = SessionContext()
        tab.set_session_context(ctx)

        audio_path = Path("/tmp/session-audio.wav")
        ctx.register_asset(
            SessionAsset(
                id="audio1",
                display_name="Session Audio",
                path=audio_path,
                category="audio",
            )
        )

        monkeypatch.setattr(
            tab,
            "_load_waveform_data",
            lambda path: (np.array([0.0, 0.25, 0.0]), 44100),
        )

        tab._audio_combo.setCurrentIndex(1)
        assert tab._audio_path == str(audio_path)

    def test_waveform_loading_reuses_session_cache(self, monkeypatch):
        tab = SrtEditTab()
        ctx = SessionContext()
        tab.set_session_context(ctx)

        audio_path = Path("/tmp/cached-audio.wav")
        ctx.register_asset(
            SessionAsset(
                id="audio1",
                display_name="Cached Audio",
                path=audio_path,
                category="audio",
            )
        )

        calls = {"count": 0}

        def fake_load(_path, sr=None, mono=True):
            calls["count"] += 1
            return np.array([0.0, 0.5, 0.0]), 44100

        import librosa

        monkeypatch.setattr(librosa, "load", fake_load)
        first = tab._load_waveform_data(str(audio_path))
        second = tab._load_waveform_data(str(audio_path))

        assert calls["count"] == 1
        assert np.array_equal(first[0], second[0])
        assert first[1] == second[1] == 44100

    def test_save_registers_subtitle_asset(self, tmp_path):
        tab = SrtEditTab()
        ctx = SessionContext()
        tab.set_session_context(ctx)

        output_path = tmp_path / "edited.srt"
        tab._subtitle_path = str(output_path)
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=1000, text="Hello world")
        ]

        tab._on_save()

        assets = ctx.list_assets(category="subtitle")
        assert len(assets) == 1
        assert assets[0].path == output_path
        assert assets[0].source_tab == "srt_edit"
        assert assets[0].role == "subtitle_source"
