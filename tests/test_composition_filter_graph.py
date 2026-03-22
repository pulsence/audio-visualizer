"""Tests for composition filter graph generation, timeline math, and matte controls."""

from pathlib import Path

import pytest

from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
    build_ffmpeg_command,
    build_filter_graph,
    build_single_layer_preview_command,
    build_preview_command,
    _build_enable_expr,
    _build_matte_filter,
    _duration_seconds,
)
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
    center_to_ffmpeg,
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
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            z_order=0, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        assert graph != ""
        assert "[0:v]" in graph
        assert "scale=" in graph
        assert "overlay=" in graph
        assert "color=" in graph

    def test_multiple_layers_chain_overlays(self):
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            z_order=0, end_ms=5000,
        ))
        model.add_layer(CompositionLayer(
            display_name="Overlay",
            asset_path=Path("/tmp/overlay.mp4"),
            center_x=100, center_y=100, width=800, height=600,
            z_order=1, end_ms=5000,
        ))
        graph = build_filter_graph(model)
        # Should have two overlay operations
        assert "ovr0" in graph
        assert "ovr1" in graph
        # center_x=100 -> ffmpeg_x = (1920/2)+100-(800/2) = 660
        assert "x=660" in graph

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

    def test_start_and_end_respected(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=1000, end_ms=5000,
            behavior_after_end="hide",
        )
        expr = _build_enable_expr(layer)
        assert "gte(t,1.0)" in expr
        assert "lt(t,5.0)" in expr

    def test_freeze_last_frame_still_stops_at_timeline_end(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=0, end_ms=5000,
            behavior_after_end="freeze_last_frame",
        )
        expr = _build_enable_expr(layer)
        assert "lt(t,5.0)" in expr

    def test_loop_still_stops_at_timeline_end(self):
        layer = CompositionLayer(
            display_name="Test",
            start_ms=0, end_ms=5000,
            behavior_after_end="loop",
        )
        expr = _build_enable_expr(layer)
        assert "lt(t,5.0)" in expr


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
        # Encoder may be hardware-accelerated or libx264
        cv_idx = cmd.index("-c:v")
        assert "h264" in cmd[cv_idx + 1] or "libx264" in cmd[cv_idx + 1]
        assert Path(cmd[-1]) == Path("/tmp/output.mp4")

    def test_audio_source_included(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Audio",
            asset_path=Path("/tmp/audio.mp3"),
            enabled=True,
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
# Preview command
# ------------------------------------------------------------------


class TestBuildPreviewCommand:
    def test_preview_command_has_vframes(self):
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_preview_command(model, 2.5, "/tmp/preview.png")
        assert "-vframes" in cmd
        assert "1" in cmd
        assert "-ss" in cmd
        assert "2.500" in cmd
        assert str(Path("/tmp/preview.png")) in cmd

    def test_preview_command_has_filter(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_preview_command(model, 0.0, "/tmp/preview.png")
        assert "-filter_complex" in cmd

    def test_preview_command_no_audio(self):
        """Preview commands should not include audio codec flags."""
        model = CompositionModel()
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Audio",
            asset_path=Path("/tmp/audio.mp3"),
            enabled=True,
        ))
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        cmd = build_preview_command(model, 1.0, "/tmp/preview.png")
        assert "-c:a" not in cmd

    def test_single_layer_preview_uses_same_visual_timing_rules(self):
        model = CompositionModel()
        layer = CompositionLayer(
            display_name="Looped Video",
            asset_path=Path("/tmp/loop.mp4"),
            source_kind="video",
            source_duration_ms=3000,
            start_ms=1000,
            end_ms=7000,
            width=1920,
            height=1080,
        )
        model.add_layer(layer)

        cmd = build_single_layer_preview_command(model, layer, 2.0, "/tmp/layer_preview.png")
        cmd_str = " ".join(cmd)

        assert "-stream_loop" in cmd
        assert "trim=duration=6" in cmd_str
        assert "setpts=PTS-STARTPTS+1.0/TB" in cmd_str


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


# ------------------------------------------------------------------
# Audio layers in FFmpeg command
# ------------------------------------------------------------------


class TestAudioLayersInFFmpegCommand:
    def test_single_audio_layer_included(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        assert str(Path("/tmp/music.mp3")) in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd

    def test_single_audio_layer_with_delay(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=10000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            start_ms=2000,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert "adelay=2000|2000" in cmd_str

    def test_single_audio_layer_with_trim(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=10000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            duration_ms=5000,
            use_full_length=False,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert "atrim=duration=5.0" in cmd_str

    def test_multiple_audio_layers_produce_amix(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=10000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            enabled=True,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Narration",
            asset_path=Path("/tmp/narration.wav"),
            start_ms=1000,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert str(Path("/tmp/music.mp3")) in cmd
        assert str(Path("/tmp/narration.wav")) in cmd
        assert "amix=inputs=2" in cmd_str
        assert "[amixed]" in cmd_str

    def test_disabled_audio_layer_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Disabled",
            asset_path=Path("/tmp/disabled.mp3"),
            enabled=False,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        assert str(Path("/tmp/disabled.mp3")) not in cmd

    def test_audio_layer_without_path_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080,
            end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="No Path",
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        # Should not have audio codec since no valid audio layer
        assert "-c:a" not in cmd

    def test_audio_layer_longer_than_source_uses_stream_loop_and_trim(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920,
            height=1080,
            end_ms=12000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Looped Music",
            asset_path=Path("/tmp/music.mp3"),
            source_duration_ms=3000,
            duration_ms=9000,
            use_full_length=False,
            enabled=True,
        ))

        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)

        assert "-stream_loop" in cmd
        assert "atrim=duration=9.0" in cmd_str

    def test_video_layer_longer_than_source_uses_stream_loop_and_trim(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="Looped Video",
            asset_path=Path("/tmp/video.mp4"),
            source_kind="video",
            source_duration_ms=2000,
            start_ms=1000,
            end_ms=7000,
            width=1920,
            height=1080,
        ))

        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)

        assert "-stream_loop" in cmd
        assert "trim=duration=6" in cmd_str
        assert "setpts=PTS-STARTPTS+1.0/TB" in cmd_str


# ------------------------------------------------------------------
# Center-origin coordinate math
# ------------------------------------------------------------------


class TestCenterOriginCoordinates:
    def test_centered_layer(self):
        """center_x=0, center_y=0 should place layer in the center."""
        x, y = center_to_ffmpeg(0, 0, 800, 600, 1920, 1080)
        assert x == (1920 // 2) - (800 // 2)
        assert y == (1080 // 2) - (600 // 2)

    def test_offset_layer(self):
        """center_x=100, center_y=-50 should shift from center."""
        x, y = center_to_ffmpeg(100, -50, 800, 600, 1920, 1080)
        assert x == (1920 // 2) + 100 - (800 // 2)
        assert y == (1080 // 2) - 50 - (600 // 2)

    def test_fullscreen_layer_at_center_zero(self):
        """A full-screen layer at (0,0) should map to FFmpeg (0,0)."""
        x, y = center_to_ffmpeg(0, 0, 1920, 1080, 1920, 1080)
        assert x == 0
        assert y == 0

    def test_center_origin_in_filter_graph(self):
        """Overlay uses center-to-topleft coordinates."""
        model = CompositionModel()
        model.output_width = 1920
        model.output_height = 1080
        # center_x=0, center_y=0, smaller layer -> should be centred
        model.add_layer(CompositionLayer(
            display_name="Centered",
            asset_path=Path("/tmp/vid.mp4"),
            center_x=0, center_y=0,
            width=800, height=600,
            end_ms=5000,
        ))
        graph = build_filter_graph(model)
        # FFmpeg x = 960-400 = 560, y = 540-300 = 240
        assert "x=560" in graph
        assert "y=240" in graph


# ------------------------------------------------------------------
# Audio volume and mute in FFmpeg command
# ------------------------------------------------------------------


class TestAudioVolumeAndMute:
    def test_volume_filter_applied(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080, end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Quiet",
            asset_path=Path("/tmp/music.mp3"),
            volume=0.5,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert "volume=0.5" in cmd_str

    def test_default_volume_no_filter(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080, end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Normal",
            asset_path=Path("/tmp/music.mp3"),
            volume=1.0,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert "volume=" not in cmd_str

    def test_muted_layer_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080, end_ms=5000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Muted",
            asset_path=Path("/tmp/music.mp3"),
            muted=True,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        assert str(Path("/tmp/music.mp3")) not in cmd
        assert "-c:a" not in cmd

    def test_volume_in_multi_audio_mix(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            width=1920, height=1080, end_ms=10000,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            volume=0.8,
            enabled=True,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Narration",
            asset_path=Path("/tmp/narration.wav"),
            volume=1.5,
            enabled=True,
        ))
        cmd = build_ffmpeg_command(model, "/tmp/output.mp4")
        cmd_str = " ".join(cmd)
        assert "volume=0.8" in cmd_str
        assert "volume=1.5" in cmd_str
        assert "amix=inputs=2" in cmd_str

