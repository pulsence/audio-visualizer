"""
Subtitle file wrapper.

This module provides a high-level wrapper around pysubs2 for working with
subtitle files.  Supports loading from .srt, .ass, and JSON bundle files.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pysubs2

from ..animations.baseAnimation import BaseAnimation
from ..core.config import PresetConfig
from ..core.style import StyleBuilder
from ..core.sizing import OverlaySize
from ..text.utils import normalize_whitespace, ass_newlines_to_real, real_newlines_to_ass
from ..text.wrapper import wrap_text_to_width


class SubtitleFile:
    """
    High-level wrapper around pysubs2.SSAFile.

    Provides convenient methods for applying styles, animations, and
    transformations to subtitle files.

    Example:
        # Load subtitle file
        sub = SubtitleFile.load(Path("input.srt"))

        # Load from bundle with word-level timing
        sub = SubtitleFile.load_bundle(Path("transcript.json"))
        print(sub.has_word_timing)  # True

        # Apply style
        preset = PresetConfig.from_dict({...})
        style = StyleBuilder(preset).build()
        sub.apply_style(style, preset)

        # Apply animation
        from audio_visualizer.caption.animations import AnimationRegistry
        animation = AnimationRegistry.create("fade", {"in_ms": 120, "out_ms": 120})
        sub.apply_animation(animation)

        # Save
        sub.save(Path("output.ass"))
    """

    def __init__(self, subs: pysubs2.SSAFile, source_format: str):
        """
        Initialize subtitle wrapper.

        Args:
            subs: Loaded pysubs2 SSAFile
            source_format: Original format ("srt", "ass", "bundle", etc.)
        """
        self.subs = subs
        self.source_format = source_format

        # Word-level timing from bundle files.  Each entry maps an event
        # index to a list of dicts: [{"start": float, "end": float, "text": str}, ...]
        self._word_timing: Dict[int, List[Dict[str, Any]]] = {}

    @property
    def has_word_timing(self) -> bool:
        """Return True if precise word-level timing data is available."""
        return bool(self._word_timing)

    def get_word_timing(self, event_index: int) -> Optional[List[Dict[str, Any]]]:
        """Return word timing for a specific event, or None."""
        return self._word_timing.get(event_index)

    @classmethod
    def load(cls, path: Path) -> "SubtitleFile":
        """
        Load subtitle file from path.

        Args:
            path: Path to subtitle file (.srt, .ass, or .json bundle)

        Returns:
            SubtitleFile instance

        Raises:
            ValueError: If file format is unsupported
        """
        ext = path.suffix.lower().lstrip(".")

        if ext == "json":
            return cls.load_bundle(path)

        if ext not in ("srt", "ass"):
            raise ValueError(f"Unsupported subtitle format: {ext}. Use .srt, .ass, or .json bundle")

        subs = pysubs2.load(str(path))
        return cls(subs, source_format=ext)

    @classmethod
    def load_bundle(cls, path: Path) -> "SubtitleFile":
        """Load a JSON bundle file and convert to subtitle events.

        Uses ``read_json_bundle()`` from the SRT IO package as the
        sole entry point for bundle reading.  Word-level timing is
        extracted and stored so that word-aware animations can use
        precise timestamps instead of estimation.

        Args:
            path: Path to a ``.json`` bundle file.

        Returns:
            SubtitleFile with ``source_format="bundle"`` and
            ``has_word_timing`` set to True when word data exists.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid JSON bundle.
        """
        from audio_visualizer.srt.io.bundleReader import read_json_bundle

        bundle = read_json_bundle(path)

        subs = pysubs2.SSAFile()
        word_timing: Dict[int, List[Dict[str, Any]]] = {}

        for idx, sub_entry in enumerate(bundle.get("subtitles", [])):
            start_sec = float(sub_entry.get("start", 0))
            end_sec = float(sub_entry.get("end", 0))
            text = sub_entry.get("text", "")

            event = pysubs2.SSAEvent(
                start=int(start_sec * 1000),
                end=int(end_sec * 1000),
                text=text,
            )
            subs.events.append(event)

            # Extract word-level timing if present
            words = sub_entry.get("words", [])
            if words:
                wt_list: List[Dict[str, Any]] = []
                for w in words:
                    # WordItem objects have .start, .end, .text attributes
                    if hasattr(w, "start"):
                        wt_list.append({
                            "start": float(w.start),
                            "end": float(w.end),
                            "text": getattr(w, "text", ""),
                        })
                    elif isinstance(w, dict):
                        wt_list.append({
                            "start": float(w.get("start", 0)),
                            "end": float(w.get("end", 0)),
                            "text": w.get("text", ""),
                        })
                if wt_list:
                    word_timing[idx] = wt_list

        instance = cls(subs, source_format="bundle")
        instance._word_timing = word_timing
        return instance

    def apply_style(
        self,
        style: pysubs2.SSAStyle,
        preset: PresetConfig,
        wrap_text: bool = True
    ) -> None:
        """
        Apply ASS style to all events.

        Args:
            style: The pysubs2 SSAStyle to apply
            preset: Preset config (used for wrapping settings)
            wrap_text: Whether to wrap text to max_width_px
        """
        # Set style in stylesheet
        self.subs.styles["Default"] = style

        # Update script info
        self.subs.info["WrapStyle"] = str(preset.wrap_style)
        self.subs.info["ScaledBorderAndShadow"] = "yes"
        self.subs.info["ScriptType"] = "v4.00+"

        # Assign style to all events and optionally wrap
        if wrap_text:
            font = self._get_font_for_wrapping(preset)

            for event in self.subs.events:
                if not isinstance(event, pysubs2.SSAEvent):
                    continue

                event.style = "Default"

                # Convert ASS newlines to real, normalize, wrap, convert back
                text = ass_newlines_to_real(event.text)
                text = normalize_whitespace(text)
                text = wrap_text_to_width(text, font, preset.max_width_px)
                event.text = real_newlines_to_ass(text)
        else:
            for event in self.subs.events:
                if isinstance(event, pysubs2.SSAEvent):
                    event.style = "Default"

    def apply_animation(
        self,
        animation: BaseAnimation,
        size: Optional[OverlaySize] = None,
        position: Optional[tuple] = None
    ) -> None:
        """
        Apply animation to all events.

        Args:
            animation: Animation instance to apply
            size: Overlay size (required for some animations)
            position: (x, y) position (required for some animations)
        """
        for event in self.subs.events:
            if not isinstance(event, pysubs2.SSAEvent):
                continue

            kwargs = {}
            if size:
                kwargs["size"] = size
            if position:
                kwargs["position"] = position

            animation.apply_to_event(event, **kwargs)

    def apply_center_positioning(
        self,
        position: tuple,
        size: OverlaySize
    ) -> None:
        """
        Force all events to be centered at a specific position.

        Uses \\an5 (center alignment) and \\pos() tags.

        Args:
            position: (x, y) coordinates for center
            size: Overlay size (used for PlayRes settings)
        """
        x, y = position
        pos_override = rf"\an5\pos({x},{y})"

        for event in self.subs.events:
            if not isinstance(event, pysubs2.SSAEvent):
                continue

            # Inject position override at start of text
            text = event.text
            if text.startswith("{") and "}" in text:
                end = text.find("}")
                head = text[1:end]
                rest = text[end + 1:]
                event.text = "{" + pos_override + head + "}" + rest
            else:
                event.text = "{" + pos_override + "}" + text

        # Also update the style alignment
        if "Default" in self.subs.styles:
            self.subs.styles["Default"].alignment = 5

    def get_duration_ms(self) -> int:
        """
        Get the maximum end time across all events.

        Returns:
            Duration in milliseconds
        """
        max_end = 0
        for event in self.subs.events:
            if isinstance(event, pysubs2.SSAEvent):
                max_end = max(max_end, int(event.end))
        return max_end

    def set_play_resolution(self, size: OverlaySize) -> None:
        """
        Set the PlayResX and PlayResY in script info.

        Args:
            size: Overlay size to use as resolution
        """
        self.subs.info["PlayResX"] = str(size.width)
        self.subs.info["PlayResY"] = str(size.height)

    def save(self, path: Path, format: str = "ass") -> None:
        """
        Save subtitle file.

        Args:
            path: Output file path
            format: Output format (default: "ass")
        """
        self.subs.save(str(path), format_=format)

    def _get_font_for_wrapping(self, preset: PresetConfig):
        """Get font for text wrapping (imported here to avoid circular deps)."""
        from ..core.sizing import SizeCalculator
        calc = SizeCalculator(preset)
        return calc.font
