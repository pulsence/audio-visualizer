# Caption Animator

Render stylized subtitle overlays (SRT/ASS) into a transparent video (ProRes 4444 with alpha) for DaVinci Resolve. The tool sizes a tight overlay canvas based on the maximum caption bounds, then renders the subtitles via FFmpeg/libass.

## Caveat Emptor
This project was primarily created for my personal use. I will not be responding to pull requests or issues unless they directly impact my use cases.

I generated this tool primarily using an AI code assistant and so all the code branches are not
explored or tested, but they should be fairly correct.

## Features
- **SRT and ASS inputs** - ASS styling is preserved by default
- **Preset-driven styling** - JSON/YAML presets for SRT conversion and optional ASS reskin
- **Plugin-based animations** - Easy to add custom animations (fade, slide_up, scale_settle, blur_settle, word_reveal)
- **Tight overlay sizing** - Minimal output video size based on caption bounds
- **ProRes 4444 output** - Alpha channel for easy positioning in Resolve
- **Interactive mode** - Tweak settings and re-render without restarting
- **Programmatic API** - Use as Python library for custom workflows

## Installation

### From Source (Recommended for Development)
```bash
pip install -e .
```

This installs the `caption-animator` command globally.

### Requirements
- Python 3.9+
- FFmpeg available on PATH
- Dependencies: `pysubs2`, `Pillow`, `PyYAML` (installed automatically)

## Quick Start

### Command-Line Usage
```bash
# Render from SRT using built-in preset
caption-animator test.srt --preset modern_box --out overlay.mov

# Render from SRT using custom preset file
caption-animator test.srt --preset presets/preset.json --out overlay.mov

# Render from ASS (keeps existing styling unless you reskin)
caption-animator test.ass --out overlay.mov

# Reskin an ASS with a preset and strip existing overrides
caption-animator test.ass --preset presets/preset.json --reskin --strip-overrides --out overlay.mov

# Keep the intermediate ASS file
caption-animator test.srt --preset modern_box --keep-ass

# Interactive mode for tweaking
caption-animator test.srt --interactive

# List available presets
caption-animator --list-presets
```

### Python Module Usage
```bash
# Can also run as module
python -m caption_animator test.srt --preset modern_box --out overlay.mov
```

### Programmatic API

#### High-Level API (Recommended)
```python
from caption_animator import render_subtitle, RenderConfig

result = render_subtitle(
    input_path="input.srt",
    output_path="output.mov",
    config=RenderConfig(preset="modern_box", quality="large"),
    on_progress=lambda msg: print(msg)
)

if result.success:
    print(f"Rendered: {result.output_path}")
    print(f"Size: {result.width}x{result.height}")
```

**RenderConfig options:**
- `preset` - Preset name or file path (default: "modern_box")
- `fps` - Frame rate (default: "30")
- `quality` - "small" (H.264), "medium" (ProRes 422 HQ), "large" (ProRes 4444)
- `safety_scale` - Edge clipping margin (default: 1.12)
- `apply_animation` - Enable/disable animation (default: True)
- `reskin` - Apply preset style to ASS files (default: False)

#### Lower-Level API (Advanced)
```python
from caption_animator import (
    SubtitleFile, PresetLoader, AnimationRegistry,
    SizeCalculator, StyleBuilder, FFmpegRenderer, EventEmitter
)
from pathlib import Path

# 1. Load subtitle and preset
sub = SubtitleFile.load(Path("input.srt"))
preset = PresetLoader().load("modern_box")

# 2. Build and apply style
style_builder = StyleBuilder(preset)
style = style_builder.build("Default")
sub.apply_style(style, preset, wrap_text=True)

# 3. Apply animation
if preset.animation:
    animation = AnimationRegistry.create(
        preset.animation.type,
        preset.animation.params
    )
    sub.apply_animation(animation)

# 4. Calculate size and positioning
size_calc = SizeCalculator(preset, safety_scale=1.12)
size = size_calc.compute_size(sub.subs)
position = size_calc.compute_anchor_position(size)
sub.apply_center_positioning(position, size)
sub.set_play_resolution(size)

# 5. Save working ASS and render
ass_path = Path("work.ass")
sub.save(ass_path)

emitter = EventEmitter()
emitter.subscribe(lambda event: print(f"[{event.event_type}] {event.message}"))

renderer = FFmpegRenderer(emitter, show_progress=True, quality="large")
renderer.render(ass_path, Path("output.mov"), size, fps="30", duration_sec=120.0)
```

## Presets and Animation Configuration

Presets define fonts, colors, layout, and animations. They can be:
- **Built-in preset name**: `modern_box` or `clean_outline`
- **Single JSON/YAML preset file**: `presets/my_preset.json`
- **Multi-preset file**: `path/to/presets.json:preset_name`

### Built-in Presets
- **modern_box** - Clean box style with slide-up animation
- **clean_outline** - Outline style with fade animation

Animation settings live under the `animation` key in preset files.

See [libass documentation](https://github.com/libass/libass?tab=readme-ov-file) for more details on ASS styling.

### Example Preset (JSON)
```json
{
  "font_file": "C:/Windows/Fonts/arialbd.ttf",
  "font_name": "Arial",
  "font_size": 62,
  "primary_color": "#FFFFFF",
  "outline_color": "#000000",
  "outline_px": 6,
  "padding": [44, 70, 56, 70],
  "animation": { 
    "type": "slide_up",
    "in_ms": 140,
    "out_ms": 120,
    "move_px": 26
  }
}
```

### Built-in Animation Types

| Animation | Parameters | Description |
|-----------|-----------|-------------|
| `fade` | `in_ms`, `out_ms` | Fade in/out effect |
| `slide_up` | `in_ms`, `out_ms`, `move_px` | Slide up from below |
| `scale_settle` | `in_ms`, `out_ms`, `start_scale`, `end_scale`, `accel` | Scale from large to normal |
| `blur_settle` | `in_ms`, `out_ms`, `start_blur`, `end_blur`, `accel` | Blur to sharp transition |
| `word_reveal` | `in_ms`, `out_ms`, `timing_mode`, `word_delay_ms` | Karaoke-style word-by-word reveal |

### Creating Custom Animations

The plugin-based architecture makes adding animations trivial:

```python
from caption_animator.animations import BaseAnimation, AnimationRegistry

@AnimationRegistry.register
class BounceAnimation(BaseAnimation):
    animation_type = "bounce"

    def validate_params(self):
        # Validate required parameters
        pass

    def generate_ass_override(self, event_context=None):
        return r"\bounce_tag"

    def apply_to_event(self, event, **kwargs):
        event.text = self._inject_override(event.text, self.generate_ass_override())
```

Save as `src/caption_animator/animations/bounce.py` and it's automatically discovered!

## Advanced Usage

### Interactive Mode
```bash
caption-animator test.srt --interactive
```

Allows tweaking preset values and re-rendering without restarting:
```
> set font_size 72
> set animation.move_px 40
> render
> quit
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--list-presets` | List all available presets |
| `--preset NAME` | Use built-in or file preset |
| `--out PATH` | Output video path (default: `<input>.mov`) |
| `--fps FPS` | Framerate (default: 30) |
| `--safety-scale N` | Multiplier to avoid edge clipping (default: 1.12) |
| `--keep-ass` | Save intermediate ASS file |
| `--interactive`, `-i` | Enter interactive mode |
| `--reskin` | Apply preset style to ASS files |
| `--strip-overrides` | Remove existing ASS tags when reskinning |
| `--no-animation` | Disable animation injection |
| `--quiet` | Suppress progress output |

See `caption-animator --help` for all options.

## Architecture

The refactored architecture uses a plugin-based system:

```
src/caption_animator/
├── animations/      # Plugin system - add animations here
├── core/           # Config, styling, sizing, subtitle handling
├── text/           # Text wrapping, measurement, ASS utilities
├── rendering/      # FFmpeg integration with progress tracking
├── presets/        # Preset loading and built-in presets
├── cli/            # Command-line interface and interactive mode
└── utils/          # File utilities
```

## Development

### Install in Development Mode
```bash
pip install -e .
```

### Run Tests
```bash
# End-to-end test
caption-animator test.srt --preset modern_box --out test_output.mov

# With custom preset
caption-animator test.srt --preset presets/word_highlight.json --out test_output.mov

# Interactive mode test
caption-animator test.srt --interactive
```

### Code Quality
```bash
# Format code
black src/

# Lint
ruff check src/

# Type check
mypy src/caption_animator
```

## Notes
- For deterministic sizing, prefer presets with `font_file` pointing to a TTF/OTF file
- ASS inputs require a preset for sizing unless you use `--reskin` or explicitly pass `--preset`
- The overlay size is computed once per subtitle file; use `--safety-scale` if you see edge clipping
- Multi-line subtitles automatically use `\N` escape sequences for proper ASS rendering


## License
See `LICENSE`.
