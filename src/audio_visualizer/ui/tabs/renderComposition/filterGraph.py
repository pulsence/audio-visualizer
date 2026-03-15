"""FFmpeg filter_complex builder for composition rendering.

Generates the ``-filter_complex`` string and full ``ffmpeg`` command
from a :class:`CompositionModel`.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionLayer,
    CompositionModel,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def build_filter_graph(model: CompositionModel) -> str:
    """Generate an FFmpeg ``filter_complex`` string from *model*.

    Only enabled layers with a source (asset_path or asset_id) are
    included.  Layers are processed in z_order, each scaled and
    overlaid at its specified position.

    Parameters
    ----------
    model : CompositionModel
        The composition model containing layer definitions.

    Returns
    -------
    str
        The filter_complex string for FFmpeg.
    """
    layers = _get_renderable_layers(model)
    if not layers:
        return ""

    filters: list[str] = []
    # Input indices: 0 is always the first layer's input.
    # Additional inputs follow in layer order.
    # We build a chain: scale input -> overlay onto canvas/previous result.

    # Create a base canvas with the output resolution
    canvas_label = "canvas"
    filters.append(
        f"color=c=black:s={model.output_width}x{model.output_height}"
        f":r={model.output_fps}:d={_duration_seconds(model)}"
        f"[{canvas_label}]"
    )

    current_label = canvas_label
    for i, (input_idx, layer) in enumerate(layers):
        stream_label = f"in{input_idx}"
        scaled_label = f"scaled{i}"
        timeline_label = f"tl{i}"
        overlay_label = f"ovr{i}"

        layer_filters: list[str] = []

        # Scale to layer size
        layer_filters.append(
            f"[{stream_label}]scale={layer.width}:{layer.height}"
        )

        # Apply matte/key filters
        matte_filter = _build_matte_filter(layer)
        if matte_filter:
            layer_filters[-1] += f",{matte_filter}"

        # Apply timeline (trim + setpts)
        timeline = _build_timeline_filter(layer, model)
        if timeline:
            layer_filters[-1] += f",{timeline}"

        # Apply behavior_after_end
        behavior = _build_behavior_filter(layer, model)
        if behavior:
            layer_filters[-1] += f",{behavior}"

        layer_filters[-1] += f"[{scaled_label}]"
        filters.append(layer_filters[-1])

        # Overlay onto current canvas
        overlay_x = layer.x
        overlay_y = layer.y

        enable_expr = _build_enable_expr(layer)
        overlay_params = f"x={overlay_x}:y={overlay_y}:format=auto"
        if enable_expr:
            overlay_params += f":enable='{enable_expr}'"

        filters.append(
            f"[{current_label}][{scaled_label}]overlay={overlay_params}[{overlay_label}]"
        )
        current_label = overlay_label

    # Final output label
    filter_str = ";\n".join(filters)
    return filter_str


def build_ffmpeg_command(
    model: CompositionModel,
    output_path: str | Path,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build a complete FFmpeg command from *model*.

    Parameters
    ----------
    model : CompositionModel
        The composition model.
    output_path : str | Path
        Destination file path.
    extra_args : list[str] | None
        Additional FFmpeg arguments to insert before the output.

    Returns
    -------
    list[str]
        The FFmpeg command as a list of arguments.
    """
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd: list[str] = [ffmpeg, "-y"]

    layers = _get_renderable_layers(model)

    # Add input files for each layer
    for _input_idx, layer in layers:
        path = _resolve_layer_path(layer)
        if path:
            cmd.extend(["-i", str(path)])

    # Add audio source input
    audio_path = _resolve_audio_path(model)
    audio_input_idx: int | None = None
    if audio_path:
        audio_input_idx = len(layers)
        cmd.extend(["-i", str(audio_path)])

    # Build filter graph
    filter_str = build_filter_graph(model)
    if filter_str:
        cmd.extend(["-filter_complex", filter_str])

        # Map the final overlay output
        # The last overlay label is ovr{n-1}
        if layers:
            last_label = f"ovr{len(layers) - 1}"
            cmd.extend(["-map", f"[{last_label}]"])

    # Map audio
    if audio_input_idx is not None:
        cmd.extend(["-map", f"{audio_input_idx}:a?"])

    # Output settings
    duration_s = _duration_seconds(model)
    if duration_s > 0:
        cmd.extend(["-t", f"{duration_s:.3f}"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ])

    if audio_input_idx is not None:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(str(output_path))
    return cmd


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _get_renderable_layers(
    model: CompositionModel,
) -> list[tuple[int, CompositionLayer]]:
    """Return (input_index, layer) pairs for enabled layers with sources."""
    layers: list[tuple[int, CompositionLayer]] = []
    input_idx = 0
    for layer in model.get_layers_sorted():
        if not layer.enabled:
            continue
        if not _resolve_layer_path(layer):
            continue
        layers.append((input_idx, layer))
        input_idx += 1
    return layers


def _resolve_layer_path(layer: CompositionLayer) -> Path | None:
    """Return the file path for a layer, or None."""
    if layer.asset_path is not None:
        return layer.asset_path
    return None


def _resolve_audio_path(model: CompositionModel) -> Path | None:
    """Return the audio source path, or None."""
    return model.audio_source_path


def _duration_seconds(model: CompositionModel) -> float:
    """Return composition duration in seconds."""
    dur_ms = model.get_duration_ms()
    if dur_ms <= 0:
        return 10.0  # fallback
    return dur_ms / 1000.0


def _build_matte_filter(layer: CompositionLayer) -> str:
    """Build matte/key filter string from layer settings."""
    settings = layer.matte_settings
    mode = settings.get("mode", "none")

    if mode == "none":
        return ""

    key_target = settings.get("key_target", "#00FF00")
    # Convert hex color to FFmpeg color format
    color = key_target.lstrip("#")
    if len(color) == 6:
        color = f"0x{color}"

    if mode == "colorkey":
        threshold = settings.get("threshold", 0.1)
        blend = settings.get("blend", 0.0)
        parts = [f"colorkey=color={color}:similarity={threshold}:blend={blend}"]
    elif mode == "chromakey":
        similarity = settings.get("similarity", 0.1)
        blend = settings.get("blend", 0.0)
        parts = [f"chromakey=color={color}:similarity={similarity}:blend={blend}"]
    elif mode == "lumakey":
        threshold = settings.get("threshold", 0.1)
        softness = settings.get("softness", 0.0)
        parts = [f"lumakey=threshold={threshold}:tolerance={softness}"]
    else:
        return ""

    # Cleanup filters
    erode = settings.get("erode", 0)
    dilate = settings.get("dilate", 0)
    feather = settings.get("feather", 0)

    if erode > 0:
        parts.append(f"erosion=radius={erode}")
    if dilate > 0:
        parts.append(f"dilation=radius={dilate}")
    if feather > 0:
        parts.append(f"gblur=sigma={feather}")

    # Despill (approximate with hue shift)
    if settings.get("despill", False) and mode in ("colorkey", "chromakey"):
        parts.append("despill=type=green")

    # Invert alpha
    if settings.get("invert", False):
        parts.append("negate=negate_alpha=1")

    return ",".join(parts)


def _build_timeline_filter(layer: CompositionLayer, model: CompositionModel) -> str:
    """Build trim + setpts filter for layer timeline."""
    # If the layer has a non-zero start, offset it
    if layer.start_ms > 0:
        start_s = layer.start_ms / 1000.0
        return f"setpts=PTS-STARTPTS+{start_s}/TB"
    return ""


def _build_behavior_filter(layer: CompositionLayer, model: CompositionModel) -> str:
    """Build filter for behavior_after_end."""
    behavior = layer.behavior_after_end
    if behavior == "loop":
        # Loop is handled via stream_loop in input, not filter
        return ""
    # freeze_last_frame and hide are handled via enable expression
    return ""


def _build_enable_expr(layer: CompositionLayer) -> str:
    """Build an FFmpeg enable expression for layer timing."""
    start_s = layer.start_ms / 1000.0
    end_s = layer.end_ms / 1000.0

    if start_s <= 0 and end_s <= 0:
        return ""

    parts: list[str] = []
    if start_s > 0:
        parts.append(f"gte(t,{start_s})")
    if end_s > 0:
        if layer.behavior_after_end == "hide":
            parts.append(f"lte(t,{end_s})")
        # freeze_last_frame and loop don't need an end constraint

    if not parts:
        return ""
    return "*".join(parts)
