"""Tests for composition filter graph generation, timeline math, and matte controls."""

from pathlib import Path

import pytest

from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
    build_ffmpeg_command,
    build_filter_graph,
    _build_enable_expr,
    _build_matte_filter,
    _duration_seconds,
)
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionLayer,
    CompositionModel,
)


# ------------------------------------------------------------------
# Filter graph generation
# ------------------------------------------------------------------


class TestBuildFilterGraph:
    def test_empty_model_returns_empty(self):
        model = CompositionModel()
        assert build_filter_graph(model) == ""

    def test_single_layer_produces_filter(self):
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        model.output_fps = 30.0
        model.add_layer(CompositionLayer(
            display_name="BG",
            layer_type="background",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            z_order=0, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        assert graph != ""
        assert "scale=" in graph
        assert "overlay=" in graph
        assert "color=" in graph

    def test_multiple_layers_chain_overlays(self):
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        model.add_layer(CompositionLayer(
            display_name="BG",
            layer_type="background",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            z_order=0, end_ms=5000,
        ))
        model.add_layer(CompositionLayer(
            display_name="Overlay",
            layer_type="visualizer",
            asset_path=Path("/tmp/overlay.mp4"),
            x=100, y=100, width=800, height=600,
            z_order=1, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        # Should have two overlay operations
        assert "ovr0" in graph
        assert "ovr1" in graph
        assert "x=100" in graph

    def test_disabled_layers_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="Enabled",
            asset_path=Path("/tmp/a.mp4"),
            enabled=True, end_ms=5000,
        ))
        model.add_layer(CompositionLayer(
            display_name="Disabled",
            asset_path=Path("/tmp/b.mp4"),
            enabled=False, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        # Only one overlay
        assert "ovr0" in graph
        assert "ovr1" not in graph

    def test_layers_without_source_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="NoSource",
            enabled=True, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        assert graph == ""


# ------------------------------------------------------------------
# Matte filter generation
# ------------------------------------------------------------------


class TestMatteFilter:
    def test_none_mode(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "none"
        assert _build_matte_filter(layer) == ""

    def test_colorkey_mode(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "colorkey"
        layer.matte_settings["key_target"] = "#00FF00"
        layer.matte_settings["threshold"] = 0.3
        layer.matte_settings["blend"] = 0.1
        result = _build_matte_filter(layer)
        assert "colorkey" in result
        assert "0x00FF00" in result
        assert "similarity=0.3" in result
        assert "blend=0.1" in result

    def test_chromakey_mode(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "chromakey"
        layer.matte_settings["key_target"] = "#0000FF"
        layer.matte_settings["similarity"] = 0.2
        layer.matte_settings["blend"] = 0.05
        result = _build_matte_filter(layer)
        assert "chromakey" in result
        assert "0x0000FF" in result

    def test_lumakey_mode(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "lumakey"
        layer.matte_settings["threshold"] = 0.5
        layer.matte_settings["softness"] = 0.2
        result = _build_matte_filter(layer)
        assert "lumakey" in result
        assert "threshold=0.5" in result
        assert "tolerance=0.2" in result

    def test_erode_dilate_feather(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "colorkey"
        layer.matte_settings["erode"] = 2
        layer.matte_settings["dilate"] = 3
        layer.matte_settings["feather"] = 4
        result = _build_matte_filter(layer)
        assert "erosion=radius=2" in result
        assert "dilation=radius=3" in result
        assert "gblur=sigma=4" in result

    def test_despill(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "chromakey"
        layer.matte_settings["despill"] = True
        result = _build_matte_filter(layer)
        assert "despill" in result

    def test_invert(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "colorkey"
        layer.matte_settings["invert"] = True
        result = _build_matte_filter(layer)
        assert "negate" in result

    def test_no_cleanup_when_zero(self):
        layer = CompositionLayer(display_name="Test")
        layer.matte_settings["mode"] = "colorkey"
        layer.matte_settings["erode"] = 0
        layer.matte_settings["dilate"] = 0
        layer.matte_settings["feather"] = 0
        layer.matte_settings["despill"] = False
        layer.matte_settings["invert"] = False
        result = _build_matte_filter(layer)
        assert "erosion" not in result
        assert "dilation" not in result
        assert "gblur" not in result


# ------------------------------------------------------------------
# Timeline / enable expression
# ------------------------------------------------------------------


class TestTimeline:
    def test_no_timing_no_enable(self):
        layer = CompositionLayer(display_name="Test", start_ms=0, end_ms=0)
        assert _build_enable_expr(layer) == ""

    def test_start_only(self):
        layer = CompositionLayer(display_name="Test", start_ms=2000, end_ms=0)
        expr = _build_enable_expr(layer)
        assert "gte(t,2.0)" in expr

    def test_start_and_end_hide(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=1000, end_ms=5000,
            behavior_after_end="hide",
        )
        expr = _build_enable_expr(layer)
        assert "gte(t,1.0)" in expr
        assert "lte(t,5.0)" in expr

    def test_freeze_last_frame_no_end_constraint(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=0, end_ms=5000,
            behavior_after_end="freeze_last_frame",
        )
        expr = _build_enable_expr(layer)
        # freeze_last_frame should not add lte constraint
        assert "lte" not in expr

    def test_loop_no_end_constraint(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=0, end_ms=5000,
            behavior_after_end="loop",
        )
        expr = _build_enable_expr(layer)
        assert "lte" not in expr


# ------------------------------------------------------------------
# Duration
# ------------------------------------------------------------------


class TestDuration:
    def test_duration_from_model(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="L1",
            end_ms=10000, enabled=True,
        ))
        assert _duration_seconds(model) == 10.0

    def test_duration_fallback(self):
        model = CompositionModel()
        assert _duration_seconds(model) == 10.0  # fallback


# ------------------------------------------------------------------
# FFmpeg command building
# ------------------------------------------------------------------


class TestBuildFFmpegCommand:
    def test_basic_command_structure(self):
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        model.output_fps = 30.0
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")

        assert Path(cmd[0]).stem.lower() == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(Path("/tmp/bg.mp4")) in cmd
        assert "-filter_complex" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert Path(cmd[-1]) == Path("/tmp/output.mp4")

    def test_audio_source_included(self):
        model = CompositionModel()
        model.audio_source_path = Path("/tmp/audio.mp3")
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        assert str(Path("/tmp/audio.mp3")) in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd

    def test_no_audio_source(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        assert str(Path("/tmp/audio.mp3")) not in cmd

    def test_extra_args(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_ffmpeg_command(
            model, "/tmp/output.mp4",
            extra_args=["-threads", "4"],
        )
        assert "-threads" in cmd
        assert "4" in cmd

    def test_empty_model_no_filter(self):
        model = CompositionModel()
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        # Still produces a command, but no filter_complex
        assert "-filter_complex" not in cmd


# ------------------------------------------------------------------
# Matte settings serialization round-trip
# ------------------------------------------------------------------


class TestMatteSettingsSerialization:
    def test_matte_settings_in_model_dict(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Keyed")
        layer.matte_settings = {
            "mode": "chromakey",
            "key_target": "#FF0000",
            "threshold": 0.2,
            "similarity": 0.3,
            "blend": 0.1,
            "softness": 0.05,
            "erode": 1,
            "dilate": 2,
            "feather": 3,
            "despill": True,
            "invert": False,
        }
        model.add_layer(layer)

        data = model.to_dict()
        restored = CompositionModel.from_dict(data)

        ms = restored.layers[0].matte_settings
        assert ms["mode"] == "chromakey"
        assert ms["key_target"] == "#FF0000"
        assert ms["threshold"] == 0.2
        assert ms["similarity"] == 0.3
        assert ms["blend"] == 0.1
        assert ms["softness"] == 0.05
        assert ms["erode"] == 1
        assert ms["dilate"] == 2
        assert ms["feather"] == 3
        assert ms["despill"] is True
        assert ms["invert"] is False
