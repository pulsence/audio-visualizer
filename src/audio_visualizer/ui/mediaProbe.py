"""Media probing helpers for composition asset analysis.

Uses ffprobe (subprocess) to extract width, height, fps, duration,
alpha/audio presence, and codec info.  Provides helpers to classify
caption outputs and check composition compatibility.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# ffprobe availability
# ------------------------------------------------------------------

def _find_ffprobe() -> str | None:
    """Return the path to ffprobe, or ``None`` if not found."""
    return shutil.which("ffprobe")


# ------------------------------------------------------------------
# Core probe
# ------------------------------------------------------------------

_ALPHA_PIXEL_FORMATS: set[str] = {
    "rgba", "yuva420p", "yuva422p", "yuva444p",
    "rgba64le", "rgba64be", "argb", "abgr", "bgra",
    "gbrap", "gbrap10le", "gbrap12le", "gbrap16le",
    "ya8", "ya16le", "ya16be",
    "pal8",  # palette may include alpha
}


def probe_media(path: str | Path) -> dict[str, Any] | None:
    """Probe a media file using ffprobe and return metadata.

    Returns a dict with keys: width, height, fps, duration_ms,
    has_alpha, has_audio, codec_name, pix_fmt.
    Returns ``None`` when ffprobe is missing or the file cannot be read.
    """
    ffprobe = _find_ffprobe()
    if ffprobe is None:
        logger.warning("ffprobe not found on PATH; cannot probe media.")
        return None

    path = Path(path)
    if not path.is_file():
        logger.warning("File does not exist: %s", path)
        return None

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("ffprobe failed for %s: %s", path, exc)
        return None

    if result.returncode != 0:
        logger.warning(
            "ffprobe returned %d for %s: %s",
            result.returncode, path, result.stderr[:200],
        )
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("ffprobe output is not valid JSON for %s", path)
        return None

    return _parse_probe_output(data)


def _parse_probe_output(data: dict) -> dict[str, Any]:
    """Extract relevant fields from ffprobe JSON output."""
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec_name: str | None = None
    pix_fmt: str | None = None
    has_alpha = False
    has_audio = False

    for stream in streams:
        codec_type = stream.get("codec_type", "")

        if codec_type == "video" and width is None:
            width = stream.get("width")
            height = stream.get("height")
            codec_name = stream.get("codec_name")
            pix_fmt = stream.get("pix_fmt", "")

            if pix_fmt in _ALPHA_PIXEL_FORMATS:
                has_alpha = True

            # Parse FPS from r_frame_rate or avg_frame_rate
            fps = _parse_frame_rate(
                stream.get("r_frame_rate"),
                stream.get("avg_frame_rate"),
            )

        elif codec_type == "audio":
            has_audio = True

    # Duration: prefer format duration, fall back to stream duration
    duration_ms: int | None = None
    duration_str = fmt.get("duration")
    if duration_str is None:
        for stream in streams:
            if stream.get("duration"):
                duration_str = stream["duration"]
                break
    if duration_str is not None:
        try:
            duration_ms = int(float(duration_str) * 1000)
        except (ValueError, TypeError):
            pass

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_ms": duration_ms,
        "has_alpha": has_alpha,
        "has_audio": has_audio,
        "codec_name": codec_name,
        "pix_fmt": pix_fmt,
    }


def _parse_frame_rate(r_frame_rate: str | None, avg_frame_rate: str | None) -> float | None:
    """Parse a fractional frame-rate string like '30000/1001'."""
    for rate_str in (r_frame_rate, avg_frame_rate):
        if not rate_str or rate_str == "0/0":
            continue
        try:
            if "/" in rate_str:
                num, den = rate_str.split("/", 1)
                den_f = float(den)
                if den_f == 0:
                    continue
                return float(num) / den_f
            return float(rate_str)
        except (ValueError, ZeroDivisionError):
            continue
    return None


# ------------------------------------------------------------------
# Caption output classification
# ------------------------------------------------------------------

def classify_caption_output(asset: Any) -> str:
    """Classify a caption asset for composition readiness.

    Returns one of:
    - ``"alpha_ready"`` — asset has alpha channel and is overlay-ready.
    - ``"needs_normalization"`` — asset may work but needs transcoding.
    - ``"opaque"`` — asset has no alpha; treat as opaque unless re-rendered.
    """
    if asset is None:
        return "opaque"

    # Check explicit overlay-readiness flags first
    is_overlay = getattr(asset, "is_overlay_ready", None)
    has_alpha = getattr(asset, "has_alpha", None)
    preferred = getattr(asset, "preferred_for_overlay", None)

    if is_overlay and has_alpha:
        return "alpha_ready"

    if preferred and has_alpha:
        return "alpha_ready"

    if has_alpha:
        return "needs_normalization"

    # Check metadata for quality tier hints
    metadata = getattr(asset, "metadata", {}) or {}
    quality = metadata.get("quality_tier", "")

    if quality == "large":
        # Large tier is the preferred alpha-ready overlay
        if has_alpha is not False:
            return "alpha_ready"
    elif quality == "small":
        # Small requires normalization before trusted reuse
        return "needs_normalization"
    elif quality == "medium":
        # Medium is treated as opaque unless normalized
        return "opaque"

    if has_alpha is True:
        return "alpha_ready"

    return "opaque"


# ------------------------------------------------------------------
# Composition compatibility checks
# ------------------------------------------------------------------

def check_composition_compatibility(assets: list[Any]) -> list[str]:
    """Check a list of assets for composition incompatibilities.

    Returns a list of warning strings.  An empty list means all assets
    are compatible.
    """
    warnings: list[str] = []

    if not assets:
        return warnings

    # Collect resolutions and FPS values
    resolutions: list[tuple[int, int, str]] = []
    fps_values: list[tuple[float, str]] = []
    durations: list[tuple[int, str]] = []

    for asset in assets:
        name = getattr(asset, "display_name", "unknown")
        w = getattr(asset, "width", None)
        h = getattr(asset, "height", None)
        fps = getattr(asset, "fps", None)
        dur = getattr(asset, "duration_ms", None)
        has_audio = getattr(asset, "has_audio", None)
        role = getattr(asset, "role", None)

        if w is not None and h is not None:
            resolutions.append((w, h, name))
        if fps is not None:
            fps_values.append((fps, name))
        if dur is not None:
            durations.append((dur, name))

        # Audio Visualizer embedded audio warning
        source_tab = getattr(asset, "source_tab", None)
        if source_tab == "audio_visualizer" and has_audio:
            warnings.append(
                f"'{name}' from Audio Visualizer has embedded audio; "
                "this will be ignored unless explicitly selected as audio source."
            )

    # Resolution mismatch check
    if len(resolutions) > 1:
        base_w, base_h, base_name = resolutions[0]
        for w, h, name in resolutions[1:]:
            if w != base_w or h != base_h:
                warnings.append(
                    f"Resolution mismatch: '{base_name}' is {base_w}x{base_h} "
                    f"but '{name}' is {w}x{h}. Scaling will be applied."
                )

    # FPS mismatch check
    if len(fps_values) > 1:
        base_fps, base_name = fps_values[0]
        for fps, name in fps_values[1:]:
            if abs(fps - base_fps) > 0.5:
                warnings.append(
                    f"FPS mismatch: '{base_name}' is {base_fps:.2f} fps "
                    f"but '{name}' is {fps:.2f} fps."
                )

    # Duration mismatch check
    if len(durations) > 1:
        max_dur = max(d for d, _ in durations)
        min_dur = min(d for d, _ in durations)
        if max_dur > 0 and min_dur > 0:
            ratio = max_dur / min_dur
            if ratio > 2.0:
                warnings.append(
                    f"Large duration spread: shortest is {min_dur}ms, "
                    f"longest is {max_dur}ms (ratio {ratio:.1f}x)."
                )

    return warnings
