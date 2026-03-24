# audio_visualizer.caption

Subtitle overlay rendering with animated effects. Takes SRT, ASS, or bundle JSON subtitle files and produces transparent video overlays for the UI worker to turn into a user-facing MP4 delivery artifact. Heavy imports (pysubs2, Pillow, etc.) are deferred until first access via `__getattr__`-based lazy loading.

## Package Exports (`__init__.py`)

Lazy-loaded via `_EXPORTS` dict and `__getattr__`:

| Export | Source Module | Description |
|--------|--------------|-------------|
| `render_subtitle` | `.captionApi` | Main entry point: render subtitle file to transparent video |
| `RenderConfig` | `.captionApi` | Configuration dataclass for rendering |
| `RenderResult` | `.captionApi` | Result dataclass from rendering |
| `list_presets` | `.captionApi` | List all available presets |
| `list_animations` | `.captionApi` | List all available animations |
| `PresetConfig` | `.core.config` | Complete preset configuration dataclass |
| `AnimationConfig` | `.core.config` | Animation configuration dataclass |
| `SubtitleFile` | `.core.subtitle` | High-level pysubs2 wrapper |
| `SizeCalculator` | `.core.sizing` | Overlay dimension calculator |
| `StyleBuilder` | `.core.style` | ASS style generator from presets |
| `FFmpegRenderer` | `.rendering.ffmpegRenderer` | FFmpeg-based video renderer |
| `PresetLoader` | `.presets.loader` | Preset loading and resolution |
| `AnimationRegistry` | `.animations.registry` | Central animation plugin registry |
| `BaseAnimation` | `.animations.baseAnimation` | Abstract base for animations |

## Public API (`captionApi.py`)

### `render_subtitle(input_path, output_path, config=None, on_progress=None, on_event=None) -> RenderResult`

Main entry point for rendering. Orchestrates the full pipeline:
1. Load and validate input subtitle file (`.srt`, `.ass`, or bundle JSON)
2. Load preset configuration
3. Build ASS style and apply to subtitle events
4. Apply animation (fade, slide, scale, blur, word reveal, word highlight, typewriter, and related word-aware effects)
5. Compute tight overlay dimensions with safety margins
6. Apply center positioning
7. Render transparent video via FFmpeg

Returns `RenderResult` with `success=False` on error (does not raise). Accepts both simple `on_progress` callback and full `on_event` callback for `AppEvent` integration.

### `RenderConfig`

Configuration dataclass: `preset` ("modern_box"), `fps` ("30"), `quality` ("small"/"medium"/"large"), `safety_scale` (1.12), `apply_animation` (True), `reskin` (False).

### `RenderResult`

Result dataclass: `success`, `output_path`, `width`, `height`, `duration_ms`, `error`.

### `list_presets() -> dict`

Returns dictionary mapping preset names to their sources ("built-in" or file path).

### `list_animations() -> dict`

Returns dictionary mapping animation types to their metadata (class name, default params, docstring).

## Core Subpackage (`core/`)

### Config (`core/config.py`)

#### `AnimationConfig`

Animation configuration extracted from a preset. Fields: `type` (str), `params` (Dict). Factory methods: `from_dict(data)`, `to_dict()`.

#### `PresetConfig`

Complete preset configuration dataclass. Fields:
- **Font:** `font_file`, `font_name` ("Arial"), `font_size` (64), `bold`, `italic`
- **Colors:** `primary_color` ("#FFFFFF"), `outline_color` ("#000000"), `shadow_color` ("#000000")
- **Styling:** `outline_px` (4.0), `shadow_px` (2.0), `blur_px` (0.0)
- **Layout:** `line_spacing` (8), `max_width_px` (1200), `padding` ([40, 60, 50, 60]), `alignment` (2), `margin_l/r/v` (0), `wrap_style` (2)
- **Animation:** `animation: Optional[AnimationConfig]`

Methods: `from_dict(data)`, `to_dict()`, `merge_with(other)`, `to_json()`, `from_json()`.

### Style (`core/style.py`)

#### `StyleBuilder`

Builds `pysubs2.SSAStyle` objects from `PresetConfig`.

- `__init__(preset: PresetConfig)`
- `build(style_name="Default") -> pysubs2.SSAStyle` -- Convert preset to ASS style
- `parse_color(color: str) -> (r, g, b)` -- Parse "#RRGGBB" to RGB tuple (static)
- `make_pysubs2_color(rgb, alpha=0) -> pysubs2.Color` -- Create pysubs2 Color (static)

### Sizing (`core/sizing.py`)

#### `OverlaySize`

Dataclass: `width: int`, `height: int`.

#### `SizeCalculator`

Computes tight overlay dimensions for all subtitle events.

- `__init__(preset: PresetConfig, safety_scale=1.12)` -- Loads font for measurement
- `compute_size(subs: pysubs2.SSAFile) -> OverlaySize` -- Measure all events, add padding/outline/shadow allowances, apply safety scale, ensure even dimensions
- `compute_anchor_position(size: OverlaySize) -> (x, y)` -- Compute center anchor within padded area

### Subtitle (`core/subtitle.py`)

#### `SubtitleFile`

High-level wrapper around `pysubs2.SSAFile`.

- `load(path: Path) -> SubtitleFile` -- Class method. Load `.srt`, `.ass`, or bundle JSON input via the shared bundle reader when needed
- `apply_style(style, preset, wrap_text=True)` -- Apply ASS style to all events, optionally wrap text
- `apply_animation(animation, size=None, position=None)` -- Apply animation to all events
- `apply_center_positioning(position, size)` -- Force center alignment with `\an5\pos()` tags
- `get_duration_ms() -> int` -- Maximum end time across all events
- `set_play_resolution(size)` -- Set PlayResX/PlayResY
- `save(path, format="ass")` -- Save subtitle file

## Animations Subpackage (`animations/`)

Plugin-based animation system with decorator registration and lazy loading.

### `BaseAnimation` (`animations/baseAnimation.py`)

Abstract base class for all animations. Subclasses must set `animation_type` and implement:

- `validate_params()` -- Validate required parameters
- `generate_ass_override(event_context=None) -> str` -- Generate ASS override tags
- `apply_to_event(event: pysubs2.SSAEvent, **kwargs)` -- Modify subtitle event text

Optional overrides:
- `needs_positioning() -> bool` -- Whether position data is needed
- `supports_placeholder_substitution() -> bool` -- Whether placeholders are used
- `substitute_placeholders(text, position) -> str` -- Replace placeholders with coordinates
- `get_default_params() -> Dict` -- Default parameter values

Helper methods: `_clamp(val, min, max)`, `_inject_override(text, override)`.

### `AnimationRegistry` (`animations/registry.py`)

Central registry with class methods:

- `register(animation_class)` -- Decorator to register an animation class
- `create(animation_type, params) -> BaseAnimation` -- Factory method
- `get(animation_type) -> Type[BaseAnimation]` -- Get class by type name
- `list_types() -> List[str]` -- List registered animation type names
- `get_info() -> Dict` -- Metadata about all registered animations
- `get_defaults(animation_type) -> Dict` -- Default params for a type
- `clear()` -- Clear all registrations (for testing)

### Built-in Animations

| Type | Class | Default Params | Description |
|------|-------|---------------|-------------|
| `fade` | `FadeAnimation` | `in_ms=120, out_ms=120` | Simple fade in/out using `\fad()` |
| `slide_up` | `SlideUpAnimation` | `in_ms=140, out_ms=120, move_px=26` | Slide up with `\move()` tags |
| `scale_settle` | `ScaleSettleAnimation` | Varies | Scale effect using `\t(\fscx\fscy)` |
| `blur_settle` | `BlurSettleAnimation` | Varies | Blur-to-sharp effect using `\t(\blur)` |
| `word_reveal` | `WordRevealAnimation` | Varies | Per-word reveal with `\alpha` tags |
| `word_highlight` | `WordHighlightAnimation` | Varies | Per-word emphasis/highlight using bundle or estimated timing |
| `typewriter` | `TypewriterAnimation` | Varies | Character-by-character reveal with optional blinking cursor |

All animation modules are lazily imported on first registry access.

## Rendering Subpackage (`rendering/`)

### `FFmpegRenderer` (`rendering/ffmpegRenderer.py`)

Renders ASS subtitles to transparent video using FFmpeg with libass.

- `__init__(emitter, loglevel="error", show_progress=True, ffmpeg_path=None, quality="small")`
- `render(ass_path, output_path, size, fps, duration_sec)` -- Execute FFmpeg render

Quality presets:
| Quality | Codec | Pixel Format | Description |
|---------|-------|-------------|-------------|
| `small` | H.264 (shared encoder selection with fallback) | yuva420p | Smallest files, alpha support |
| `medium` | ProRes 422 HQ | yuv422p10le | Mid-size, no alpha |
| `large` | ProRes 4444 | yuva444p10le | Largest, full alpha support |

Emits events: `LOG` (FFmpeg command), `RENDER_START`, `RENDER_PROGRESS` (frame, time, speed), `RENDER_COMPLETE`.

### `ProgressTracker` (`rendering/progressTracker.py`)

Simple progress tracker that emits `STAGE` events via `AppEventEmitter`.

- `step(message)` -- Emit a progress step event
- `reset()` -- Reset the timer

## Presets Subpackage (`presets/`)

### `PresetLoader` (`presets/loader.py`)

Loads and resolves preset configurations from multiple sources.

Resolution order:
1. Built-in presets (by name)
2. Multi-preset file with named preset (`path:name`)
3. Direct file path (JSON/YAML)
4. Search in preset directories

Supports JSON and YAML formats. YAML requires PyYAML.

### Built-in Presets (`presets/defaults.py`)

| Preset | Font | Size | Style | Animation |
|--------|------|------|-------|-----------|
| `clean_outline` | Arial 64 | Normal | White text, black outline (5px) | fade (120ms in/out) |
| `modern_box` | Arial 62 | Bold | White text, black outline (6px) + shadow (3px) | slide_up (140ms in, 120ms out, 26px) |

Functions: `get_builtin_preset(name) -> Dict`, `list_builtin_presets() -> List[str]`.

## Text Subpackage (`text/`)

### Measurement (`text/measurement.py`)

- `measure_multiline(text, font, line_spacing_px) -> (width, height, line_count)` -- Measure multi-line text dimensions using Pillow
- `measure_single_line(text, font) -> int` -- Measure single line width

### Utils (`text/utils.py`)

- `strip_ass_tags(text) -> str` -- Remove `{...}` ASS override blocks
- `ass_newlines_to_real(text) -> str` -- Convert `\N` / `\n` to real newlines
- `real_newlines_to_ass(text) -> str` -- Convert real newlines to `\N`
- `normalize_whitespace(text) -> str` -- Normalize line endings and collapse spaces

### Wrapper (`text/wrapper.py`)

- `wrap_text_to_width(text, font, max_width_px) -> str` -- Greedy word-wrapping using Pillow font measurement. Returns text with `\n` line breaks.

## Utils Subpackage (`utils/`)

### Files (`utils/files.py`)

- `ensure_parent_dir(path)` -- Create parent directory if needed

## Event Integration

The caption package uses `AppEventEmitter` from `audio_visualizer.events` throughout. Events emitted:

| EventType | When |
|-----------|------|
| `LOG` | FFmpeg command details, debug info |
| `STAGE` | Pipeline step progress (loading, styling, sizing, rendering) |
| `RENDER_START` | FFmpeg render begins |
| `RENDER_PROGRESS` | FFmpeg frame/time/speed updates (every 0.5s) |
| `RENDER_COMPLETE` | FFmpeg render finishes |

## Dependencies

- **pysubs2** -- ASS/SRT subtitle file parsing and manipulation
- **Pillow** -- Font loading and text measurement for sizing
- **PyYAML** (optional) -- YAML preset file loading
- **ffmpeg** (external) -- Video rendering with libass subtitle filter
