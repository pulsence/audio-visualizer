# audio_visualizer.visualizers

Rendering engine for all visualizer types. Contains the abstract base class, data models for audio and video, and all concrete visualizer implementations.

## Package Exports (`__init__.py`)

- `Visualizer` — Re-exported from `genericVisualizer`

## Base Class

### Visualizer (`genericVisualizer.py`)

Abstract base class for all visualizer implementations.

**Constructor:** `(audio_data: AudioData, video_data: VideoData, x, y, super_sampling)`
- Stores references to `audio_data` and `video_data`
- Scales `x` and `y` offsets by `super_sampling` factor

**Abstract Methods** (raise `NotImplementedError`):
- `prepare_shapes()` — Called once before rendering. Sets up shape data structures, positions, colors.
- `generate_frame(frame_index: int)` — Called per frame. Returns a numpy array representing the frame image.

## Data Models (`utilities.py`)

### AudioData

Manages audio file loading and frame-level analysis.

**Attributes:**
- `file_path: str` — Path to the source audio file
- `audio_samples: ndarray` — Raw audio samples from librosa
- `sample_rate: int` — Sample rate in Hz
- `audio_frames: list` — Audio chunks split by frame boundaries
- `average_volumes: list[float]` — Average volume per frame
- `max_volume, min_volume: float` — Global volume extremes
- `chromagrams: list` — 12-bin chroma feature array per frame
- `last_error: str` — Error message from the most recent operation

**Methods:**
- `load_audio_data(duration_seconds=None) -> bool` — Loads audio via `librosa.load()`. Optional duration limit for previews.
- `chunk_audio(fps: int)` — Splits `audio_samples` into per-frame chunks based on `fps` and `sample_rate`.
- `analyze_audio()` — Computes `average_volumes[]` and `chromagrams[]` for each frame. Calculates `max_volume` and `min_volume`.

### VideoData

Manages video container creation and codec configuration.

**Attributes:**
- `video_width, video_height: int` — Output video dimensions
- `fps: int` — Frames per second
- `file_path: str` — Output video file path
- `codec: str` — Video codec name selected by the user (for example `"h264"`, `"hevc"`, `"vp9"`, `"av1"`, `"mpeg4"`)
- `bitrate: int | None` — Optional bitrate setting in bits per second
- `crf: int` — Optional CRF quality setting
- `hardware_accel: bool` — GPU acceleration flag
- `container` — PyAV container object (set during `prepare_container`)
- `stream` — PyAV video stream object
- `last_error: str` — Error message from the most recent operation

**Methods:**
- `prepare_container() -> bool` — Creates a PyAV output container and video stream. When hardware acceleration is enabled, it first tries `h264_nvenc` or `hevc_nvenc` for those codecs and falls back to the requested software codec on failure.
- `finalize() -> bool` — Flushes the stream and closes the container.

## Enums (`utilities.py`)

### VisualizerOptions

All 14 visualizer types:

| Value | Category | Description |
|-------|----------|-------------|
| `VOLUME_RECTANGLE` | Volume | Rectangles sized by volume with flow history |
| `VOLUME_CIRCLE` | Volume | Circles sized by volume with flow history |
| `VOLUME_LINE` | Volume | Smooth spline line driven by volume |
| `VOLUME_FORCE_LINE` | Volume | Mass-spring rope with volume impulses |
| `CHROMA_RECTANGLE` | Chroma | 12 rectangles for chroma bands |
| `CHROMA_CIRCLE` | Chroma | 12 circles for chroma bands |
| `CHROMA_LINE` | Chroma | Smooth spline through 12 chroma points |
| `CHROMA_LINES` | Chroma | 12 separate lines with history (one per band) |
| `CHROMA_FORCE_RECTANGLE` | Chroma | 12 rectangles with physics |
| `CHROMA_FORCE_CIRCLE` | Chroma | 12 circles with physics |
| `CHROMA_FORCE_LINE` | Chroma | Mass-spring rope with 12 chroma anchors |
| `CHROMA_FORCE_LINES` | Chroma | 12 independent mass-spring ropes |
| `WAVEFORM` | Special | Static waveform of entire audio |
| `COMBINED_RECTANGLE` | Special | Volume rectangles + chroma rectangles combined |

### VisualizerFlow

- `LEFT_TO_RIGHT` — History flows left to right
- `OUT_FROM_CENTER` — History flows outward from center

### VisualizerAlignment

- `BOTTOM` — Shapes anchored to bottom of frame
- `CENTER` — Shapes centered vertically

## Volume Visualizers (`volume/`)

### RectangleVisualizer

Multiple rectangles whose height is driven by volume, with flow history. Supports all 4 combinations of alignment (bottom/center) and flow (left-to-right/center).

**Parameters:** `box_height`, `box_width`, `border_width`, `spacing`, `corner_radius`, `bg_color`, `border_color`, `alignment`, `flow`, `super_sampling`

### CircleVisualizer

Expanding circles driven by volume with flow history. Auto-calculates number of circles from available width.

**Parameters:** `max_radius`, `border_width`, `spacing`, `bg_color`, `border_color`, `alignment`, `flow`, `super_sampling`

### LineVisualizer

Smooth Catmull-Rom spline line driven by volume. Maintains a height history array that shifts each frame.

**Parameters:** `max_height`, `line_thickness`, `spacing`, `color`, `alignment`, `flow`, `smoothness`, `super_sampling`

### ForceLineVisualizer

Mass-spring rope simulation driven by volume impulses at a single injection point.

**Parameters:** `line_thickness`, `points_count`, `color`, `alignment`, `flow`, `tension`, `damping`, `impulse_strength`, `gravity`, `super_sampling`

## Chroma Visualizers (`chroma/`)

All chroma visualizers use 12 bands (one per semitone in the chromagram).

### RectangleVisualizer

12 rectangles whose height is driven by chroma band intensity. Supports color modes (single, gradient, per-band).

**Parameters:** `box_height`, `border_width`, `spacing`, `corner_radius`, `bg_color`, `border_color`, `alignment`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `super_sampling`

### CircleVisualizer

12 circles whose radius is driven by chroma band intensity.

**Parameters:** `border_width`, `spacing`, `bg_color`, `border_color`, `alignment`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `super_sampling`

### LineVisualizer

Smooth Catmull-Rom spline through 12 chroma-driven points.

**Parameters:** `max_height`, `line_thickness`, `color`, `alignment`, `smoothness`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `super_sampling`

### LineBandsVisualizer

12 separate smooth lines (one per chroma band) with flow history. Each line's height is driven by its corresponding chroma band.

**Parameters:** `max_height`, `line_thickness`, `spacing`, `color`, `alignment`, `flow`, `smoothness`, `band_spacing`, `band_colors`, `super_sampling`

### ForceRectangleVisualizer

12 rectangles with physics simulation (gravity + force from chroma intensity).

**Parameters:** `box_height`, `border_width`, `spacing`, `corner_radius`, `bg_color`, `border_color`, `alignment`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `gravity`, `force_strength`, `super_sampling`

### ForceCircleVisualizer

12 circles with physics simulation. Radius driven by force vs. gravity.

**Parameters:** `border_width`, `spacing`, `bg_color`, `border_color`, `alignment`, `color_mode`, `gradient_start`, `gradient_end`, `band_colors`, `gravity`, `force_strength`, `super_sampling`

### ForceLineVisualizer

Mass-spring rope with 12 anchor points corresponding to chroma bands. Points between anchors simulate spring physics.

**Parameters:** `line_thickness`, `points_count`, `color`, `alignment`, `tension`, `damping`, `force_strength`, `gravity`, `smoothness`, `super_sampling`

### ForceLinesVisualizer

12 independent mass-spring ropes (one per chroma band) with per-band colors.

**Parameters:** `line_thickness`, `points_count`, `color`, `alignment`, `tension`, `damping`, `force_strength`, `gravity`, `smoothness`, `band_spacing`, `band_colors`, `super_sampling`

## Special Visualizers

### WaveformVisualizer (`waveform/`)

Pre-renders the complete audio waveform during `prepare_shapes()`. `generate_frame()` returns the same static image for every frame.

**Parameters:** `line_thickness`, `color`, `alignment`, `super_sampling`

### RectangleCombinedVisualizer (`combined/`)

Combines volume-driven rectangles (bottom layer) with chroma-driven rectangles (top layer). The volume rectangles use flow history while the chroma rectangles show the current 12-band state.

**Parameters:** `box_height`, `box_width`, `border_width`, `spacing`, `corner_radius`, `chroma_box_height`, `chroma_corner_radius`, `volume_color`, `chroma_color`, `border_color`, `alignment`, `flow`, `super_sampling`

## Rendering Techniques

### Catmull-Rom Splines

Line-based visualizers use `_catmull_rom()` or `_catmull_rom_segment()` for smooth curve interpolation through control points. The `smoothness` parameter controls the number of interpolation samples between points.

### Physics Simulation

Force-based visualizers use a velocity/displacement model:
- Each frame: `velocity += force * chroma_value - gravity * displacement`
- Displacement clamped to non-negative values
- Spring-based visualizers add tension and damping terms

### Super-Sampling

All visualizers accept a `super_sampling` factor that scales coordinates and dimensions by the given multiplier. The final output is rendered at the scaled resolution.

### Flow History

Volume visualizers maintain arrays of past values. Each frame, new values are inserted and old values shift, creating a flowing animation effect. Two flow modes are supported: left-to-right and out-from-center.
