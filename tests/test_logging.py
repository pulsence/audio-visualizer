import logging
import os

from audio_visualizer.app_logging import setup_logging


def test_setup_logging_creates_file(monkeypatch, tmp_path):
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    log_path = setup_logging()
    logging.getLogger(__name__).info("log test")
    assert log_path.exists()
