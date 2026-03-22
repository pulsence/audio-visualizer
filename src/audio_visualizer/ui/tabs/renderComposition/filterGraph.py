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
    CompositionAudioLayer,
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
    """
    layers = _get_renderable_layers(model)
    if not layers:
        return ""

    filters: list[str] = []

    # Create a base canvas with the output resolution
    canvas_label = "canvas"
    filters.append(
        f"color=c=black:s={model.output_width}x{model.output_height}"
        f":r={model.output_fps}:d={_duration_seconds(model)}"
        f"[{canvas_label}]"
    )

    current_label = canvas_label
    for i, (input_idx, layer) in enumerate(layers):
        scaled_label = f"scaled{i}"
        overlay_label = f"ovr{i}"

        filters.append(_build_visual_stream_filter(input_idx, layer, scaled_label))

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

    filter_str = ";\n".join(filters)
    return filter_str


def build_preview_command(
    model: CompositionModel,
    timestamp_s: float,
    output_path: str | Path,
) -> list[str]:
    """Build an FFmpeg command to extract a single preview frame."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd: list[str] = [ffmpeg, "-y"]

    layers = _get_renderable_layers(model)

    for _input_idx, layer in layers:
        if _resolve_layer_path(layer):
            _add_visual_input(cmd, layer)

    filter_str = build_filter_graph(model)
    if filter_str:
        cmd.extend(["-filter_complex", filter_str])
        if layers:
            last_label = f"ovr{len(layers) - 1}"
            cmd.extend(["-map", f"[{last_label}]"])

    cmd.extend([
        "-ss", f"{timestamp_s:.3f}",
        "-vframes", "1",
        str(output_path),
    ])
    return cmd


def build_single_layer_preview_command(
    model: CompositionModel,
    layer: CompositionLayer,
    timestamp_s: float,
    output_path: str | Path,
) -> list[str]:
    """Build an FFmpeg command to preview a single layer at its actual dimensions."""
    import copy

    single_model = CompositionModel()
    # Use the layer's own dimensions as the canvas so it renders at native size
    single_model.output_width = layer.width
    single_model.output_height = layer.height
    single_model.output_fps = model.output_fps

    single_layer = copy.deepcopy(layer)
    single_layer.x = 0
    single_layer.y = 0
    single_model.layers.append(single_layer)

    return build_preview_command(single_model, timestamp_s, output_path)


def build_ffmpeg_command(
    model: CompositionModel,
    output_path: str | Path,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build a complete FFmpeg command from *model*."""
    from audio_visualizer.hwaccel import get_decode_flags
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd: list[str] = [ffmpeg, "-y"]
    cmd.extend(get_decode_flags())

    layers = _get_renderable_layers(model)

    # Add input files for each visual layer
    for _input_idx, layer in layers:
        _add_visual_input(cmd, layer)

    # Add audio layer inputs
    audio_layers = _get_audio_layers(model)
    audio_input_indices: list[int] = []
    for al in audio_layers:
        audio_input_indices.append(len(layers) + len(audio_input_indices))
        _add_audio_input(cmd, al)

    has_audio = bool(audio_input_indices)

    # Build filter graph
    filter_str = build_filter_graph(model)

    # Build audio mixing filter
    if len(audio_input_indices) > 1:
        audio_filters: list[str] = []
        audio_labels: list[str] = []
        for i, (input_idx, al) in enumerate(zip(audio_input_indices, audio_layers)):
            label = f"aud{i}"
            parts: list[str] = []
            eff_dur = al.effective_duration_ms()
            if eff_dur > 0:
                dur_s = eff_dur / 1000.0
                parts.append(f"atrim=duration={dur_s}")
            if al.start_ms > 0:
                delay_ms = al.start_ms
                parts.append(f"adelay={delay_ms}|{delay_ms}")
            if parts:
                audio_filters.append(f"[{input_idx}:a]{','.join(parts)}[{label}]")
            else:
                audio_filters.append(f"[{input_idx}:a]acopy[{label}]")
            audio_labels.append(f"[{label}]")

        mix_label = "amixed"
        audio_filters.append(
            f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration=longest[{mix_label}]"
        )

        if filter_str:
            filter_str += ";\n" + ";\n".join(audio_filters)
        else:
            filter_str = ";\n".join(audio_filters)

        cmd.extend(["-filter_complex", filter_str])
        if layers:
            last_label = f"ovr{len(layers) - 1}"
            cmd.extend(["-map", f"[{last_label}]"])
        cmd.extend(["-map", f"[{mix_label}]"])
    elif len(audio_input_indices) == 1:
        al = audio_layers[0]
        input_idx = audio_input_indices[0]
        parts_single: list[str] = []
        eff_dur = al.effective_duration_ms()
        if eff_dur > 0:
            dur_s = eff_dur / 1000.0
            parts_single.append(f"atrim=duration={dur_s}")
        if al.start_ms > 0:
            delay_ms = al.start_ms
            parts_single.append(f"adelay={delay_ms}|{delay_ms}")

        if parts_single:
            single_label = "aud0"
            audio_filter = f"[{input_idx}:a]{','.join(parts_single)}[{single_label}]"
            if filter_str:
                filter_str += ";\n" + audio_filter
            else:
                filter_str = audio_filter
            cmd.extend(["-filter_complex", filter_str])
            if layers:
                last_label = f"ovr{len(layers) - 1}"
                cmd.extend(["-map", f"[{last_label}]"])
            cmd.extend(["-map", f"[{single_label}]"])
        else:
            if filter_str:
                cmd.extend(["-filter_complex", filter_str])
                if layers:
                    last_label = f"ovr{len(layers) - 1}"
                    cmd.extend(["-map", f"[{last_label}]"])
            cmd.extend(["-map", f"{input_idx}:a?"])
    else:
        if filter_str:
            cmd.extend(["-filter_complex", filter_str])
            if layers:
                last_label = f"ovr{len(layers) - 1}"
                cmd.extend(["-map", f"[{last_label}]"])

    # Output settings
    duration_s = _duration_seconds(model)
    if duration_s > 0:
        cmd.extend(["-t", f"{duration_s:.3f}"])

    from audio_visualizer.hwaccel import select_encoder
    encoder = select_encoder("h264")
    logger.info("Render Composition using encoder: %s", encoder)

    cmd.extend([
        "-c:v", encoder,
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ])

    if has_audio:
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


def _get_audio_layers(model: CompositionModel) -> list[CompositionAudioLayer]:
    """Return enabled audio layers with resolved paths."""
    result: list[CompositionAudioLayer] = []
    for al in model.audio_layers:
        if al.asset_path and al.enabled:
            result.append(al)
    return result


def _add_visual_input(cmd: list[str], layer: CompositionLayer) -> None:
    """Add input arguments for a visual layer, with looping if needed."""
    path = _resolve_layer_path(layer)
    if not path:
        return
    requested = layer.effective_duration_ms()
    if (layer.source_kind == "video"
            and layer.source_duration_ms > 0
            and requested > layer.source_duration_ms):
        cmd.extend(["-stream_loop", "-1", "-i", str(path)])
    else:
        cmd.extend(["-i", str(path)])


def _add_audio_input(cmd: list[str], al: CompositionAudioLayer) -> None:
    """Add input arguments for an audio layer, with looping if needed."""
    eff_dur = al.effective_duration_ms()
    if al.source_duration_ms > 0 and eff_dur > al.source_duration_ms:
        cmd.extend(["-stream_loop", "-1", "-i", str(al.asset_path)])
    else:
        cmd.extend(["-i", str(al.asset_path)])


def _duration_seconds(model: CompositionModel) -> float:
    """Return composition duration in seconds."""
    dur_ms = model.get_duration_ms()
    if dur_ms <= 0:
        return 10.0  # fallback
    return dur_ms / 1000.0


def _build_visual_stream_filter(
    input_idx: int,
    layer: CompositionLayer,
    output_label: str,
) -> str:
    """Build the filter chain for a single visual input stream."""
    filters: list[str] = []
    requested_ms = layer.effective_duration_ms()

    if layer.source_kind == "video" and requested_ms > 0:
        filters.append(f"trim=duration={_seconds_string(requested_ms)}")

    filters.append(f"scale={layer.width}:{layer.height}")

    matte_filter = _build_matte_filter(layer)
    if matte_filter:
        filters.append(matte_filter)

    filters.append(_build_timeline_filter(layer, None))

    behavior = _build_behavior_filter(layer, None)
    if behavior:
        filters.append(behavior)

    return f"[{input_idx}:v]{','.join(filters)}[{output_label}]"


def _seconds_string(duration_ms: int) -> str:
    """Return a stable ffmpeg-friendly seconds string from milliseconds."""
    if duration_ms <= 0:
        return "0"
    seconds = duration_ms / 1000.0
    formatted = f"{seconds:.3f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _build_matte_filter(layer: CompositionLayer) -> str:
    """Build matte/key filter string from layer settings."""
    settings = layer.matte_settings
    mode = settings.get("mode", "none")

    if mode == "none":
        return ""

    key_target = settings.get("key_target", "#00FF00")
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

    erode = settings.get("erode", 0)
    dilate = settings.get("dilate", 0)
    feather = settings.get("feather", 0)

    if erode > 0:
        parts.append(f"erosion=radius={erode}")
    if dilate > 0:
        parts.append(f"dilation=radius={dilate}")
    if feather > 0:
        parts.append(f"gblur=sigma={feather}")

    if settings.get("despill", False) and mode in ("colorkey", "chromakey"):
        parts.append("despill=type=green")

    if settings.get("invert", False):
        parts.append("negate=negate_alpha=1")

    return ",".join(parts)


def _build_timeline_filter(layer: CompositionLayer, model: CompositionModel) -> str:
    """Build trim + setpts filter for layer timeline."""
    del model
    start_s = layer.start_ms / 1000.0
    if layer.start_ms > 0:
        return f"setpts=PTS-STARTPTS+{start_s}/TB"
    return "setpts=PTS-STARTPTS"


def _build_behavior_filter(layer: CompositionLayer, model: CompositionModel) -> str:
    """Build filter for behavior_after_end."""
    del layer, model
    return ""


def _build_enable_expr(layer: CompositionLayer) -> str:
    """Build an FFmpeg enable expression for layer timing."""
    start_s = layer.start_ms / 1000.0
    requested_ms = layer.effective_duration_ms()

    if start_s <= 0 and requested_ms <= 0:
        return ""

    parts: list[str] = []
    if start_s > 0:
        parts.append(f"gte(t,{start_s})")
    if requested_ms > 0 and layer.end_ms > layer.start_ms:
        parts.append(f"lt(t,{layer.end_ms / 1000.0})")

    if not parts:
        return ""
    return "*".join(parts)
