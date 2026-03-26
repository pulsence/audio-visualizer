"""Matte/key helpers shared by preview and playback rendering."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PySide6.QtGui import QColor, QImage

logger = logging.getLogger(__name__)


def apply_matte_to_image(
    image: QImage | None,
    matte_settings: dict[str, Any] | None,
) -> QImage | None:
    """Return a copy of *image* with matte settings applied."""
    if image is None or image.isNull():
        return image

    settings = matte_settings or {}
    mode = str(settings.get("mode", "none") or "none").lower()
    if mode == "none":
        return image

    try:
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        width = rgba.width()
        height = rgba.height()
        rgba_data = np.frombuffer(
            rgba.constBits(),
            dtype=np.uint8,
        ).reshape((height, width, 4)).copy()

        alpha_factor = _alpha_factor_for_matte(rgba_data, mode, settings)
        rgba_data[..., 3] = np.clip(
            rgba_data[..., 3].astype(np.float32) * alpha_factor,
            0.0,
            255.0,
        ).astype(np.uint8)

        if settings.get("despill", False) and mode in {"colorkey", "chromakey"}:
            _apply_green_despill(rgba_data, alpha_factor)

        if settings.get("invert", False):
            rgba_data[..., 3] = 255 - rgba_data[..., 3]

        return QImage(
            rgba_data.data,
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
    except Exception:
        logger.warning("Failed to apply matte settings to preview image.", exc_info=True)
        return image


def _alpha_factor_for_matte(
    rgba_data: np.ndarray,
    mode: str,
    settings: dict[str, Any],
) -> np.ndarray:
    rgb = rgba_data[..., :3].astype(np.float32) / 255.0
    if mode in {"colorkey", "chromakey"}:
        key_color = _resolve_key_color(settings.get("key_target", "#00FF00"))
        target_rgb = np.array(key_color, dtype=np.float32) / 255.0
        distance = np.sqrt(np.mean(np.square(rgb - target_rgb), axis=2))
        threshold_key = "threshold" if mode == "colorkey" else "similarity"
        threshold = _clamp_unit_float(settings.get(threshold_key, 0.1))
        blend = _clamp_unit_float(settings.get("blend", 0.0))
        if blend > 0.0:
            return np.clip((distance - threshold) / blend, 0.0, 1.0)
        return (distance > threshold).astype(np.float32)

    if mode == "lumakey":
        threshold = _clamp_unit_float(settings.get("threshold", 0.1))
        softness = _clamp_unit_float(settings.get("softness", 0.0))
        luma = (
            (rgb[..., 0] * 0.2126)
            + (rgb[..., 1] * 0.7152)
            + (rgb[..., 2] * 0.0722)
        )
        if softness > 0.0:
            return np.clip((luma - threshold) / softness, 0.0, 1.0)
        return (luma >= threshold).astype(np.float32)

    return np.ones(rgba_data.shape[:2], dtype=np.float32)


def _apply_green_despill(rgba_data: np.ndarray, alpha_factor: np.ndarray) -> None:
    key_strength = 1.0 - alpha_factor
    red = rgba_data[..., 0].astype(np.float32)
    green = rgba_data[..., 1].astype(np.float32)
    blue = rgba_data[..., 2].astype(np.float32)
    despilled_green = np.minimum(green, np.maximum(red, blue))
    rgba_data[..., 1] = np.clip(
        (green * alpha_factor) + (despilled_green * key_strength),
        0.0,
        255.0,
    ).astype(np.uint8)


def _resolve_key_color(value: Any) -> tuple[int, int, int]:
    color = QColor(str(value or "#00FF00"))
    if not color.isValid():
        color = QColor("#00FF00")
    return (color.red(), color.green(), color.blue())


def _clamp_unit_float(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
