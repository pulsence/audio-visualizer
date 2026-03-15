# Visualizers

This document describes the visualizer architecture, lifecycle, and how to add new visualizer types.

## Visualizer Base Class Lifecycle

Every visualizer follows this lifecycle:

1. **Construction** — The Visualizer subclass is instantiated with `AudioData`, `VideoData`, position offsets, super-sampling factor, and type-specific parameters.

2. **`prepare_shapes()`** — Called once before rendering begins. Sets up data structures: shape lists, position arrays, color lists, velocity arrays (for physics-based types). This is where the visualizer pre-computes anything that doesn't depend on per-frame audio data.

3. **`generate_frame(frame_index)`** — Called once per frame during rendering. Reads audio data for the given frame (from `audio_data.average_volumes[frame_index]` or `audio_data.chromagrams[frame_index]`), updates shape state, draws to a Pillow `Image`, and returns the result as a numpy array.

## Audio Analysis Pipeline

```
audio file
    → librosa.load(file_path)
    → audio_samples (numpy array), sample_rate

audio_samples
    → chunk_audio(fps)
    → audio_frames[] (one chunk per video frame)

audio_frames[]
    → analyze_audio()
    → average_volumes[] (mean absolute amplitude per frame)
    → chromagrams[] (12-bin chroma feature per frame)
    → max_volume, min_volume (global extremes)
```

Volume-based visualizers use `average_volumes[]`. Chroma-based visualizers use `chromagrams[]` (12 values per frame, one per semitone: C, C#, D, ..., B). Combined visualizers use both.

## Visualizer Categories

### Volume Visualizers

Drive shapes by overall audio volume. Maintain history arrays that shift each frame to create flowing animations. Support two flow modes (`VisualizerFlow`):
- `LEFT_TO_RIGHT` — new values enter on the left, shift right
- `OUT_FROM_CENTER` — new values enter at center, push outward

### Chroma Visualizers

Drive 12 shapes (one per chroma band) by chromagram intensity. Two sub-categories:
- **Static chroma** — shapes sized directly by current chroma values
- **Force chroma** — physics simulation where chroma values apply force against gravity

### Special Visualizers

- **Waveform** — renders the complete audio waveform once during `prepare_shapes()`; `generate_frame()` returns the same static image
- **Combined** — layers volume rectangles with chroma rectangles in a single frame

## Super-Sampling

The `super_sampling` parameter scales all coordinates and dimensions. A value of 2 renders at 2x resolution. The base `Visualizer.__init__()` multiplies `x` and `y` offsets by this factor, and subclasses apply it to their shape dimensions.

## Adding a New Visualizer

To add a new visualizer type:

### 1. Create the Visualizer subclass

Create a new file in the appropriate `visualizers/` subdirectory (e.g., `visualizers/volume/newVisualizer.py`).

```python
from audio_visualizer.visualizers.genericVisualizer import Visualizer

class NewVisualizer(Visualizer):
    def __init__(self, audio_data, video_data, x, y, super_sampling, ...):
        super().__init__(audio_data, video_data, x, y, super_sampling)
        # Store type-specific parameters

    def prepare_shapes(self):
        # Initialize data structures

    def generate_frame(self, frame_index):
        # Generate and return numpy array for this frame
```

### 2. Create the View subclass

Create a corresponding view in `ui/views/` (e.g., `ui/views/volume/newVisualizerView.py`).

```python
from audio_visualizer.ui.views.general.generalView import View

class NewVisualizerSettings:
    def __init__(self):
        # Typed fields for validated user input

class NewVisualizerView(View):
    def __init__(self):
        super().__init__()
        # Create Qt widgets for settings

    def validate_view(self) -> bool:
        # Validate inputs, return True if valid

    def read_view_values(self) -> NewVisualizerSettings:
        # Parse and return settings
```

### 3. Add to VisualizerOptions enum

In `visualizers/utilities.py`, add the new type to the `VisualizerOptions` enum:

```python
class VisualizerOptions(Enum):
    # ... existing entries ...
    NEW_TYPE = "New Type"
```

### 4. Wire registration points in MainWindow

In `ui/mainWindow.py`, update the following locations:

1. **`_VIEW_ATTRIBUTE_MAP`** — Add mapping from attribute name to `VisualizerOptions.NEW_TYPE`
2. **`_build_visualizer_view()`** — Add case to create the new View instance
3. **`validate_render_settings()`** — Add validation branch for the new type
4. **`_create_visualizer()`** — Add case to create the new Visualizer instance with collected settings
5. **`_collect_settings()`** — Add serialization for the new view's settings
6. **`_apply_settings()`** — Add deserialization to restore the new view's settings
