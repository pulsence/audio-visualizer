# Local SRT

Local SRT generator using **faster-whisper** (offline transcription) and **ffmpeg** (media decoding).

This tool converts audio or video files into readable subtitle files with intelligent
punctuation-aware chunking, pacing heuristics, and presets for YouTube, Shorts, Podcasts, and Transcript output.

## Caveat Emptor

This project was primarily created for my personal use. I will not be responding to pull requests
period but I may respond to issues if they impact my use cases or I can easily respoduce the issue.
Feel free to fork and make whatever changes you would like. I was frustrated that a "turn key" local
SRT generator was not easily available; now there is.

I generated this tool primarily using an AI code assistant. The codebase has test coverage,
but not every path is exhaustively validated.

## Features

- Fully local transcription (no remote API calls)
- Uses `faster-whisper` for high-quality speech recognition
- Intelligent subtitle chunking (punctuation-aware, reading-speed constraints)
- Pipeline modes: `general`, `shorts` (dual-output with word-level animation SRT), `transcript` (large blocks)
- Presets for common use cases: `yt`, `shorts`, `podcast`, `transcript`
- Script helpers: initial prompt, script-guided text substitution, corrected SRT alignment
- Optional speaker diarization for Transcript mode (`pip install local-srt[diarize]`)
- CUDA support with automatic CPU fallback
- Batch processing with directory scanning
- Output formats: SRT, VTT, ASS, TXT, JSON

## Quick Start

```bash
pip install local-srt
srtgen input.mp4 -o output.srt
```

See the [User Guide](USER_GUIDE.md) for full documentation.

## Requirements

- Python 3.10+
- ffmpeg on PATH

## License

MIT
