"""
CLI command implementations.
"""

import sys
from pathlib import Path

from ..presets.loader import PresetLoader
from ..presets.defaults import list_builtin_presets


def list_presets_command() -> int:
    """
    List all available presets.

    Returns:
        Exit code (0 for success)
    """
    print("Available presets:\n", file=sys.stderr)

    # Built-in presets
    builtin = list_builtin_presets()
    if builtin:
        print("Built-in:", file=sys.stderr)
        for name in builtin:
            print(f"  {name}", file=sys.stderr)
    else:
        print("Built-in: (none)", file=sys.stderr)

    # Presets from directories
    presets_dir = Path("presets")
    found_files = []

    if presets_dir.exists() and presets_dir.is_dir():
        for path in sorted(presets_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in (".json", ".yaml", ".yml"):
                found_files.append(path.name)

    if found_files:
        print("\npresets/ directory:", file=sys.stderr)
        for name in found_files:
            print(f"  {name}", file=sys.stderr)
    else:
        print("\npresets/ directory: (none found)", file=sys.stderr)

    print(
        "\nUsage:\n"
        "  --preset <name>              # Built-in preset\n"
        "  --preset presets/<file>      # File in presets/ directory\n"
        "  --preset <file>:name         # Named preset in multi-preset file\n",
        file=sys.stderr
    )

    return 0
