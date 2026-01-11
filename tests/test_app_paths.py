import os
from pathlib import Path

from audio_visualizer.app_paths import APP_DIRNAME, get_config_dir, get_data_dir


def test_app_paths_use_env_base(monkeypatch, tmp_path):
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    config_dir = get_config_dir()
    data_dir = get_data_dir()

    assert config_dir.exists()
    assert data_dir.exists()
    assert APP_DIRNAME in str(config_dir)
    assert APP_DIRNAME in str(data_dir)
