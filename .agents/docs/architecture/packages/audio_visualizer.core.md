# audio_visualizer.core

Core modules that handle application bootstrap, logging, platform paths, and update checking. These are the top-level modules in `src/audio_visualizer/` (not in a `core/` subdirectory).

## visualizer.py

Application bootstrap module.

### Functions

- **`_resolve_icon_path() -> Path | None`** — Resolves the application icon path. Checks `sys._MEIPASS` for PyInstaller frozen builds, otherwise looks relative to the source file. Returns `None` if no icon found.

- **`main()`** — Creates a `QApplication`, sets the application icon, instantiates `MainWindow`, shows it, and runs the Qt event loop. This is the primary entry point for the application.

## app_logging.py

File-based logging configuration.

### Functions

- **`setup_logging() -> Path`** — Configures Python's `logging` module:
  - Log file: `{config_dir}/audio_visualizer.log` (via `get_config_dir()`)
  - Handler: `FileHandler` with UTF-8 encoding
  - Level: `INFO`
  - Format: `%(asctime)s %(levelname)s %(name)s - %(message)s`
  - Returns the path to the log file

## app_paths.py

Platform-specific directory management.

### Constants

- `APP_DIRNAME = "audio_visualizer"` — Directory name used for config and data storage

### Functions

- **`_ensure_dir(path: Path) -> Path`** — Creates the directory (and parents) if it doesn't exist. Returns the path.

- **`get_config_dir() -> Path`** — Returns the platform-specific config directory:
  - Windows: `{LOCALAPPDATA}/audio_visualizer`
  - Unix: `{XDG_CONFIG_HOME}/audio_visualizer` (or `~/.config/audio_visualizer`)

- **`get_data_dir() -> Path`** — Returns the platform-specific data directory:
  - Windows: `{LOCALAPPDATA}/audio_visualizer`
  - Unix: `{XDG_DATA_HOME}/audio_visualizer` (or `~/.local/share/audio_visualizer`)

## updater.py

GitHub release update checker.

### Constants

- `DEFAULT_REPO_OWNER = "pulsence"` — Default GitHub repo owner
- `DEFAULT_REPO_NAME = "audio-visualizer"` — Default GitHub repo name
- `GITHUB_API_BASE = "https://api.github.com"` — GitHub API base URL

### Functions

- **`get_current_version() -> str`** — Returns `__version__` from the package.

- **`_get_repo() -> tuple[str, str]`** — Returns `(owner, name)` from the `AUDIO_VISUALIZER_REPO` environment variable (format: `owner/name`), falling back to defaults.

- **`_normalize_version(version: str)`** — Normalizes a version string, using `packaging.version.Version` when available and otherwise falling back to a numeric tuple comparison.

- **`is_update_available(current_version: str, latest_version: str) -> bool`** — Returns `True` if `latest_version` is newer than `current_version`.

- **`fetch_latest_release(timeout_seconds: int = 8) -> dict`** — Fetches the latest release from the GitHub API. Returns a dict with keys `"version"`, `"name"`, `"url"`. Raises `RuntimeError` on network or parsing errors.
