"""
Tests for size calculation functionality.
"""

import pytest
import pysubs2
from caption_animator.core.sizing import SizeCalculator, OverlaySize
from caption_animator.core.config import PresetConfig


class TestOverlaySize:
    """Test suite for OverlaySize dataclass."""

    def test_overlay_size_creation(self):
        """Test creating an OverlaySize instance."""
        size = OverlaySize(width=1920, height=1080)
        assert size.width == 1920
        assert size.height == 1080

    def test_overlay_size_attributes(self):
        """Test OverlaySize attributes are accessible."""
        size = OverlaySize(width=640, height=480)
        assert hasattr(size, 'width')
        assert hasattr(size, 'height')


class TestSizeCalculatorInit:
    """Test suite for SizeCalculator initialization."""

    def test_calculator_creation_with_defaults(self, sample_preset_config):
        """Test creating calculator with default safety scale."""
        # Need to use a preset with font_file=None to use fallback fonts
        preset = PresetConfig(
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
            margin_r=10
        )
        calculator = SizeCalculator(preset)
        assert calculator.preset == preset
        assert calculator.safety_scale == 1.12
        assert calculator.font is not None

    def test_calculator_custom_safety_scale(self, sample_preset_config):
        """Test creating calculator with custom safety scale."""
        preset = PresetConfig(
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
            margin_r=10
        )
        calculator = SizeCalculator(preset, safety_scale=1.5)
        assert calculator.safety_scale == 1.5


class TestSizeCalculatorCompute:
    """Test suite for size computation."""

    def test_compute_size_single_line(self, sample_srt_file):
        """Test computing size for single line subtitle."""
        preset = PresetConfig(
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
            max_width_px=0,  # No wrapping
            padding=[10, 10, 10, 10]
        )
        calculator = SizeCalculator(preset, safety_scale=1.0)

        subs = pysubs2.load(str(sample_srt_file))
        size = calculator.compute_size(subs)

        # Should return valid dimensions
        assert isinstance(size, OverlaySize)
        assert size.width > 0
        assert size.height > 0
        # Minimum dimensions
        assert size.width >= 64
        assert size.height >= 64

    def test_compute_size_multiline(self, sample_srt_file):
        """Test computing size for multi-line subtitles."""
        preset = PresetConfig(
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
            max_width_px=0,
            padding=[10, 10, 10, 10],
            line_spacing=5
        )
        calculator = SizeCalculator(preset, safety_scale=1.0)

        subs = pysubs2.load(str(sample_srt_file))
        size = calculator.compute_size(subs)

        # Multi-line should produce valid dimensions
        assert size.height > 64  # At least minimum dimension

    def test_safety_scale_increases_size(self, sample_srt_file):
        """Test that safety scale increases the computed size."""
        preset = PresetConfig(
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
            max_width_px=0,
            padding=[10, 10, 10, 10]
        )

        subs = pysubs2.load(str(sample_srt_file))

        calc1 = SizeCalculator(preset, safety_scale=1.0)
        size1 = calc1.compute_size(subs)

        calc2 = SizeCalculator(preset, safety_scale=1.5)
        size2 = calc2.compute_size(subs)

        # Higher safety scale should produce larger dimensions
        assert size2.width > size1.width
        assert size2.height > size1.height

    def test_padding_affects_size(self, sample_srt_file):
        """Test that padding affects the final size."""
        base_preset = PresetConfig(
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
            max_width_px=0,
            padding=[5, 5, 5, 5]
        )

        large_padding_preset = PresetConfig(
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
            max_width_px=0,
            padding=[50, 50, 50, 50]
        )

        subs = pysubs2.load(str(sample_srt_file))

        calc1 = SizeCalculator(base_preset, safety_scale=1.0)
        size1 = calc1.compute_size(subs)

        calc2 = SizeCalculator(large_padding_preset, safety_scale=1.0)
        size2 = calc2.compute_size(subs)

        # Larger padding should produce larger dimensions
        assert size2.width > size1.width
        assert size2.height > size1.height

    def test_dimensions_are_even(self, sample_srt_file):
        """Test that output dimensions are even numbers."""
        preset = PresetConfig(
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
            max_width_px=0,
            padding=[10, 10, 10, 10]
        )
        calculator = SizeCalculator(preset)

        subs = pysubs2.load(str(sample_srt_file))
        size = calculator.compute_size(subs)

        # Dimensions should be even (divisible by 2)
        assert size.width % 2 == 0, f"Width {size.width} is not even"
        assert size.height % 2 == 0, f"Height {size.height} is not even"

    def test_empty_subtitle_file(self, tmp_path):
        """Test handling of empty subtitle file."""
        preset = PresetConfig(
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
            max_width_px=0,
            padding=[10, 10, 10, 10]
        )
        calculator = SizeCalculator(preset)

        # Create minimal valid SRT file with no meaningful content
        empty_srt = tmp_path / "empty.srt"
        empty_srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n\n",
            encoding="utf-8"
        )

        subs = pysubs2.load(str(empty_srt))
        size = calculator.compute_size(subs)

        # Should still return minimum dimensions
        assert size.width >= 64
        assert size.height >= 64

    def test_wrapping_integration(self, tmp_path):
        """Test that text wrapping is integrated into size computation."""
        # Create subtitle with very long line
        long_srt = tmp_path / "long.srt"
        long_srt.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n"
            "This is a very long line that should definitely wrap when max width is set\n",
            encoding="utf-8"
        )

        preset = PresetConfig(
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
            max_width_px=300,  # Force wrapping
            padding=[10, 10, 10, 10],
            line_spacing=5
        )
        calculator = SizeCalculator(preset, safety_scale=1.0)

        subs = pysubs2.load(str(long_srt))
        size = calculator.compute_size(subs)

        # With wrapping, width should be constrained but height should increase
        # Width should be approximately max_width_px plus padding and safety
        assert size.width < 600  # Should be constrained
        assert size.height > 100  # Should be taller due to wrapping
