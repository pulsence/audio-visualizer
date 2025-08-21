# Overview
The purpose of this porject is to produce a visualization of any audio source in a video format.

## Current Capabilites
Current the program can create videos from an audio file visualizing the audio volume across time
as rectangles. These rectangles can have round corners. They can flow from the left to right or
from a center point outwards.

## Todo:
### General:
- Look in python graphics programming
- Create a UI
- Impliment multithreading (multiprocessing module)

### Visualizers
- Rectangles
    - Use supersampling to improve rounded corners (img = img.resize((width // 2, height // 2), resample=Image.LANCZOS))
    - Reimpliment each draw function to be frame independent
- Circles
    - Make circles work (include supersampling)
- Future visualizers
    - Frequency spectrum based
    - Wave forms
    - Cloud/Particles