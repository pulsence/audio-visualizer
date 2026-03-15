"""
Pytest configuration and shared fixtures for Caption Animator tests.
"""

import pytest
from pathlib import Path
from PIL import ImageFont
from io import StringIO
import tempfile


@pytest.fixture
def sample_srt_content():
    """Sample SRT subtitle content with multi-line captions."""
    return """1
00:00:00,000 --> 00:00:02,000
This is a single line caption

2
00:00:02,000 --> 00:00:05,000
This is a multi-line caption
that spans two lines

3
00:00:05,000 --> 00:00:08,000
Line one
Line two
Line three

4
00:00:08,000 --> 00:00:10,000
Short text
"""


@pytest.fixture
def sample_srt_file(tmp_path, sample_srt_content):
    """Create a temporary SRT file for testing."""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(sample_srt_content, encoding="utf-8")
    return srt_file


@pytest.fixture
def mock_font():
    """
    Create a mock font for testing text measurement.
    Uses a simple default font available on most systems.
    """
    try:
        # Try to load a basic font
        font = ImageFont.truetype("arial.ttf", size=48)
    except (OSError, IOError):
        try:
            # Fallback to another common font
            font = ImageFont.truetype("DejaVuSans.ttf", size=48)
        except (OSError, IOError):
            # Last resort: use default font
            font = ImageFont.load_default()
    return font


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for output files."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_preset_config():
    """Sample PresetConfig for testing."""
    from caption_animator.core.config import PresetConfig, AnimationConfig

    return PresetConfig(
        font_name="Arial",
        font_size=48,
        bold=True,
        italic=False,
        primary_color="#FFFFFF",
        outline_color="#000000",
        outline_px=2.0,
        shadow_px=1.0,
        alignment=2,
        margin_v=20,
        margin_l=10,
        margin_r=10,
        animation=AnimationConfig(
            type="fade",
            params={"in_ms": 200, "out_ms": 200}
        )
    )


@pytest.fixture
def simple_text_lines():
    """Simple text lines for wrapping tests."""
    return [
        "Short",
        "This is a longer line that should wrap",
        "Multiple words here that need wrapping to fit width",
        ""
    ]


@pytest.fixture
def multiline_text():
    """Multi-line text for measurement tests."""
    return "Line one\\NLine two\\NLine three"
