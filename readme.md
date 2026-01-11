# Overview
The purpose of this project is to produce a visualization of any audio source in a video format. You can select an audio file and then generate a visual representation based upon the volume profile of the audio. Other off-the-shelf visualization generators work by pitch (and so work only with music) or involved paid services. This program enables you to generate basic audio visualizes for free.

This program was created with the use case of making "audiograms" from podcast voice content. With a video produced by this program, one can easily overlay it on top of a video or image in any
video editing program.

This program comes with no support or warranty. It is licensed under the MIT License. I do not  intend to take feature requests and will be maintaining it for my personal use. I make it freely available since it could be of some use to others.

## Current Capabilities
Current the program can create videos from an audio file visualizing the audio volume and chromagraph (pitch scale) across time as rectangles or circles. In both cases the shapes can be align along a bottom axis or center axis. The direction of flow can be either left to right or out from the center when visualizing volume.

# Dependencies:
- av
- numpy
- librosa
- PIL (Pillow)
- Pyside 6

# Set Up
Install Python 3 (3.13 was version this was developed in).
Run 'pip install -r requirements.txt' to install required packages.
Run `python -m audio_visualizer` from the project root.

## Run Scripts
- Windows: `run.bat`
- Bash (Linux/macOS): `run.sh`
