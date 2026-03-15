import sys
from collections import namedtuple
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import pytest
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audio_visualizer.srt.models import WordItem


# ---------------------------------------------------------------------------
# pytest configuration (SRT markers / options)
# ---------------------------------------------------------------------------

Segment = namedtuple("Segment", ["start", "end", "text", "words"])


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Update integration test baseline SRT files.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: integration tests with real audio")
    config.addinivalue_line("markers", "slow: slow tests")


# ---------------------------------------------------------------------------
# SRT fixtures (ported from Local SRT project)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_word_items() -> Callable[[List[Tuple[str, float, float]]], List[WordItem]]:
    """Build a WordItem list from (text, start, end) tuples."""

    def _make(words: List[Tuple[str, float, float]]) -> List[WordItem]:
        return [WordItem(float(start), float(end), text) for text, start, end in words]

    return _make


@pytest.fixture
def mock_segments() -> Callable[[List[Dict[str, Any]]], List[Segment]]:
    """Build mock whisper segments from dicts."""

    def _make(data: List[Dict[str, Any]]) -> List[Segment]:
        segments: List[Segment] = []
        for item in data:
            segments.append(
                Segment(
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", 0.0)),
                    text=item.get("text", ""),
                    words=item.get("words"),
                )
            )
        return segments

    return _make


@pytest.fixture
def mock_silence_intervals() -> List[Tuple[float, float]]:
    """Return a fixed silence interval list for reuse."""
    return [(1.0, 1.4), (3.0, 3.6)]


@pytest.fixture
def update_baselines(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-baselines"))


# ---------------------------------------------------------------------------
# Caption Animator fixtures (ported from Caption Animator project)
# ---------------------------------------------------------------------------


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
    from audio_visualizer.caption.core.config import PresetConfig, AnimationConfig

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
