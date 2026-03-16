# audio_visualizer.ui.views

Settings view system for all visualizer types. Each visualizer type has a corresponding View subclass that collects and validates user input, and a Settings class that packages the validated values.

## Package Exports (`__init__.py`)

- `View` — Re-exported from `general.generalView`
- `Fonts` — Re-exported from `general.utilities`

## Base Classes

### View (`general/generalView.py`)

Abstract base class for all settings panels.

- **`__init__()`** — Initializes a `QGridLayout` and a `QWidget` controller
- **`get_view_in_layout() -> QLayout`** — Returns the layout containing all widgets
- **`get_view_in_widget() -> QWidget`** — Returns the controller widget
- **`validate_view() -> bool`** — Subclass override: validates inputs, returns `True` if valid
- **`read_view_values() -> object`** — Subclass override: returns a Settings object with parsed values

### Fonts (`general/utilities.py`)

Static font definitions used across views:

- `h1_font` — QFont, 24pt, bold
- `h2_font` — QFont, 16pt, underlined

## General Views (`general/`)

### GeneralSettingsView

Collects general application settings: audio file path, video output path, resolution, FPS, codec, bitrate, CRF, hardware acceleration, include audio toggle.

- **Settings class:** `GeneralSettings`
- **Fields:** `video_width`, `video_height`, `fps`, `codec`, `bitrate`, `crf`, `hardware_accel`, `include_audio`, `audio_file_path`, `video_file_path`
- Receives `WorkspaceContext` from `AudioVisualizerTab` so file dialogs can honor the session project folder.

### GeneralVisualizerView

Collects general visualizer settings: position offset, alignment, background color, border color, border width, spacing, super-sampling factor.

- **Settings class:** `GeneralVisualizerSettings`
- **Fields:** `visualizer_type`, `alignment`, `x`, `y`, `bg_color`, `border_color`, `border_width`, `spacing`, `super_sampling`
- **Color parsing:** `_parse_color(text) -> tuple[int, int, int]` — parses `"R, G, B"` format
- Uses `ClickableColorSwatch` widgets so swatches and buttons both open the color dialog.

### CombinedVisualizerView

Collects combined volume+chroma rectangle settings.

- **Settings class:** `CombinedVisualizerSettings`
- **Fields:** `box_height`, `box_width`, `corner_radius`, `flow`, `chroma_box_height`, `chroma_corner_radius`

### WaveformVisualizerView

Collects waveform visualizer settings.

- **Settings class:** `WaveformVisualizerSettings`
- **Fields:** `line_thickness`

## Volume Views (`volume/`)

### RectangleVolumeVisualizerView

- **Settings:** `RectangleVolumeVisualizerSettings`
- **Fields:** `box_height`, `box_width`, `corner_radius`, `flow`

### CircleVolumeVisualizerView

- **Settings:** `CircleVolumeVisualizerSettings`
- **Fields:** `radius`, `flow`

### LineVolumeVisualizerView

- **Settings:** `LineVolumeVisualizerSettings`
- **Fields:** `max_height`, `line_thickness`, `flow`, `smoothness`

### ForceLineVolumeVisualizerView

- **Settings:** `ForceLineVolumeVisualizerSettings`
- **Fields:** `line_thickness`, `points_count`, `tension`, `damping`, `impulse_strength`, `gravity`, `flow`

## Chroma Views (`chroma/`)

### RectangleChromaVisualizerView

- **Settings:** `RectangleChromaVisualizerSettings`
- **Fields:** `box_height`, `corner_radius`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`

### CircleChromeVisualizerView

- **Settings:** `CircleChromeVisualizerSettings`
- **Fields:** `color_mode` ("Single", "Gradient", "Per-band"), `gradient_start`, `gradient_end`, `band_colors`

### LineChromaVisualizerView

- **Settings:** `LineChromaVisualizerSettings`
- **Fields:** `max_height`, `line_thickness`, `smoothness`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`

### LineChromaBandsVisualizerView

- **Settings:** `LineChromaBandsVisualizerSettings`
- **Fields:** `max_height`, `line_thickness`, `smoothness`, `flow`, `band_colors` (12 colors), `band_spacing`
- Uses tabbed interface (QTabWidget) with 2 tabs x 6 bands for 12 band color inputs

### ForceRectangleChromaVisualizerView

- **Settings:** `ForceRectangleChromaVisualizerSettings`
- **Fields:** `box_height`, `corner_radius`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `gravity`, `force_strength`
- Uses a `QTabWidget` with 2 x 6 band editors for per-band colors.

### ForceCircleChromaVisualizerView

- **Settings:** `ForceCircleChromaVisualizerSettings`
- **Fields:** `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `gravity`, `force_strength`
- Uses a `QTabWidget` with 2 x 6 band editors for per-band colors.

### ForceLineChromaVisualizerView

- **Settings:** `ForceLineChromaVisualizerSettings`
- **Fields:** `line_thickness`, `points_count`, `tension`, `damping`, `force_strength`, `gravity`, `smoothness`

### ForceLinesChromaVisualizerView

- **Settings:** `ForceLinesChromaVisualizerSettings`
- **Fields:** `line_thickness`, `points_count`, `smoothness`, `tension`, `damping`, `force_strength`, `gravity`, `band_spacing`, `band_colors` (12 colors via tabbed interface)

## Color Modes

Several chroma views support three color modes:

| Mode | Description |
|------|-------------|
| Single | One color for all 12 bands (uses border color) |
| Gradient | Linear gradient from `gradient_start` to `gradient_end` across 12 bands |
| Per-band | Individual `"R, G, B"` color for each of the 12 chroma bands |

All views parse colors from `"R, G, B"` text format using `_parse_color()` helpers.
