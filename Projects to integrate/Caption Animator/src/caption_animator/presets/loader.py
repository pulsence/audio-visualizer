"""
Preset loading and resolution.

This module handles loading presets from various sources including built-in
presets, file paths, and multi-preset files with named presets.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..core.config import PresetConfig
from .defaults import BUILTIN_PRESETS, get_builtin_preset

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


class PresetLoader:
    """
    Loads and resolves preset configurations.

    Supports multiple sources:
    - Built-in presets by name
    - Single preset files (JSON/YAML)
    - Multi-preset files with named presets (file.yaml:preset_name)
    - Search in preset directories

    Example:
        loader = PresetLoader()

        # Load built-in preset
        preset = loader.load("modern_box")

        # Load from file
        preset = loader.load("my_preset.json")

        # Load named preset from multi-preset file
        preset = loader.load("presets.yaml:fancy")
    """

    def __init__(self, preset_dirs: Optional[List[Path]] = None):
        """
        Initialize preset loader.

        Args:
            preset_dirs: Directories to search for preset files (default: ["presets"])
        """
        self.preset_dirs = preset_dirs or [Path("presets")]

    def load(self, preset_ref: str) -> PresetConfig:
        """
        Load a preset from various sources.

        Resolution order:
        1. Built-in presets (if name matches)
        2. Multi-preset file with name (if contains ':')
        3. Direct file path (if exists)
        4. Search in preset directories

        Args:
            preset_ref: Preset reference (name, path, or path:name)

        Returns:
            Loaded PresetConfig

        Raises:
            ValueError: If preset cannot be found or loaded
        """
        # 1. Check built-in presets
        if preset_ref in BUILTIN_PRESETS:
            preset_dict = get_builtin_preset(preset_ref)
            return PresetConfig.from_dict(preset_dict)

        # 2. Check for multi-preset file reference (path:name)
        if ":" in preset_ref:
            file_part, name_part = preset_ref.split(":", 1)
            file_path = Path(file_part)

            if file_path.exists():
                return self._load_named_preset(file_path, name_part)

        # 3. Try as direct file path
        file_path = Path(preset_ref)
        if file_path.exists():
            return self._load_single_preset(file_path)

        # 4. Search in preset directories
        resolved = self._resolve_in_directories(preset_ref)
        if resolved:
            return self._load_single_preset(resolved)

        # Not found
        raise ValueError(
            f"Preset '{preset_ref}' not found. "
            f"Tried: built-in presets, direct path, preset directories. "
            f"Available built-ins: {', '.join(sorted(BUILTIN_PRESETS.keys()))}"
        )

    def _load_single_preset(self, path: Path) -> PresetConfig:
        """Load a single preset from a file."""
        data = self._load_file(path)

        if not isinstance(data, dict):
            raise ValueError(f"Preset file '{path}' must contain a dictionary")

        # Check if it looks like a single preset or multi-preset file
        if self._is_single_preset(data):
            return PresetConfig.from_dict(data)
        else:
            raise ValueError(
                f"File '{path}' appears to contain multiple presets. "
                f"Use '{path}:preset_name' to specify which one."
            )

    def _load_named_preset(self, path: Path, name: str) -> PresetConfig:
        """Load a named preset from a multi-preset file."""
        data = self._load_file(path)

        if not isinstance(data, dict):
            raise ValueError(f"Preset file '{path}' must contain a dictionary")

        if name not in data:
            available = ", ".join(sorted(data.keys()))
            raise ValueError(
                f"Preset '{name}' not found in '{path}'. "
                f"Available: {available}"
            )

        preset_data = data[name]
        if not isinstance(preset_data, dict):
            raise ValueError(f"Preset '{name}' in '{path}' must be a dictionary")

        return PresetConfig.from_dict(preset_data)

    def _load_file(self, path: Path) -> Any:
        """Load a JSON or YAML file."""
        ext = path.suffix.lower()
        text = path.read_text(encoding="utf-8")

        if ext in (".yaml", ".yml"):
            if yaml is None:
                raise RuntimeError(
                    "PyYAML is not installed. Install with: pip install pyyaml"
                )
            return yaml.safe_load(text)

        if ext == ".json":
            return json.loads(text)

        raise ValueError(
            f"Unsupported preset file extension '{ext}'. "
            f"Use .json, .yaml, or .yml"
        )

    def _is_single_preset(self, data: dict) -> bool:
        """
        Check if a dictionary is a single preset vs multi-preset file.

        Single presets have keys like font_size, padding, etc.
        Multi-preset files have preset names as keys.
        """
        # Check for common preset keys
        preset_keys = {"font_size", "padding", "max_width_px", "font_name", "animation"}
        return any(key in data for key in preset_keys)

    def _resolve_in_directories(self, name: str) -> Optional[Path]:
        """
        Search for preset file in preset directories.

        Tries:
        - name (exact)
        - name.json
        - name.yaml
        - name.yml
        """
        for directory in self.preset_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            # Try exact name
            candidate = directory / name
            if candidate.exists() and candidate.is_file():
                return candidate

            # Try with extensions
            for ext in [".json", ".yaml", ".yml"]:
                candidate = directory / (name + ext)
                if candidate.exists() and candidate.is_file():
                    return candidate

        return None

    def list_available(self) -> Dict[str, str]:
        """
        List all available presets with their sources.

        Returns:
            Dictionary mapping preset names to their sources
        """
        presets: Dict[str, str] = {}

        # Add built-in presets
        for name in BUILTIN_PRESETS.keys():
            presets[name] = "built-in"

        # Scan preset directories
        for directory in self.preset_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            for path in directory.iterdir():
                if path.is_file() and path.suffix.lower() in (".json", ".yaml", ".yml"):
                    presets[path.name] = str(path.relative_to(Path.cwd()))

        return presets
