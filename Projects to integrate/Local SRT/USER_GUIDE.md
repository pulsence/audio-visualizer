# Local SRT User Guide

This guide documents the current CLI behavior for Local SRT 0.3.0.

## Installation

Install from PyPI:

```bash
python -m pip install local-srt
```

For speaker diarization support:

```bash
pip install local-srt[diarize]
```

Install from a GitHub download:

1. Download the repository (zip) from GitHub and extract it.
2. From the extracted folder, run:

```bash
python -m pip install .
```

Requirements:

- Python 3.10+
- `ffmpeg` available on `PATH` (required)
- `ffprobe` available on `PATH` (recommended)

Models are downloaded automatically on first use when a model is not present in the local cache.

## Installing ffmpeg

### Windows

```powershell
winget install Gyan.FFmpeg
```

or

```powershell
choco install ffmpeg
```

### macOS

```bash
brew install ffmpeg
```

### Linux

```bash
sudo apt install ffmpeg
```

## Basic Usage

Transcribe a single file to SRT:

```bash
srtgen input.mp4 -o output.srt
```

Choose a different output format:

```bash
srtgen input.mp4 --format vtt
```

Generate word-level cues (per-word subtitles):

```bash
srtgen input.mp4 --word-level
```

Notes:

- `--output` is only valid when a single input expands to a single file.
- For directory or multi-file input, use `--outdir`.

## Supported Inputs

Directory inputs are scanned recursively for these extensions:

- `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`
- `.mp4`, `.mkv`, `.mov`, `.webm`, `.m4v`

If you pass an explicit file path or glob, other formats may work if ffmpeg can decode them.

## Supported Outputs

Primary output formats (via `--format`):

- `srt`, `vtt`, `ass`, `txt`, `json`

Additional outputs:

- `--emit-transcript PATH` writes a plain-text transcript (`.txt`)
- `--emit-segments PATH` writes a segments JSON file (`.segments.json`)
- `--emit-bundle PATH` writes a full JSON bundle (`.bundle.json`)

If an `--emit-*` path is a directory or ends with a trailing slash, a per-input file is created inside that directory.

## Models

Select a faster-whisper model:

```bash
srtgen input.mp4 --model small
```

Common model names:

- `tiny`, `base`, `small`, `medium`, `large-v3`

Defaults and related flags:

- `--model` default: `medium`
- `--device` choices: `auto`, `cpu`, `cuda` (default: `auto`)
- `--strict-cuda` fails instead of falling back to CPU if CUDA init fails

Model management (run without input files):

- `--list-models`
- `--list-available-models`
- `--download-model NAME`
- `--delete-model NAME`

## Language

Use `--language` to force a language code (example: `en`). If omitted, faster-whisper auto-detects the language.

```bash
srtgen input.mp4 --language en
```

## Presets

Use `--preset` to apply preset tuning:

```bash
srtgen input.mp4 --preset shorts
srtgen input.mp4 --preset yt
srtgen input.mp4 --preset podcast
srtgen input.mp4 --preset transcript
```

Preset values (defaults are from the base config):

| Setting | Default | shorts | yt | podcast | transcript |
| --- | --- | --- | --- | --- | --- |
| `max_chars` | 42 | 18 | 42 | 40 | 80 |
| `max_lines` | 2 | 1 | 2 | 2 | 4 |
| `target_cps` | 17.0 | 18.0 | 17.0 | 16.0 | 17.0 |
| `min_dur` | 1.0 | 0.7 | 1.0 | 0.9 | 2.0 |
| `max_dur` | 6.0 | 3.0 | 6.0 | 5.0 | 30.0 |
| `prefer_punct_splits` | False | False | False | True | True |
| `allow_commas` | True | True | True | True | True |
| `allow_medium` | True | True | True | True | True |
| `min_gap` | 0.08 | 0.08 | 0.08 | 0.08 | 0.08 |
| `pad` | 0.00 | 0.00 | 0.00 | 0.05 | 0.00 |

These values map to `formatting.*` in the config file.

## Pipeline Modes

Use `--mode` to select the pipeline mode (default: `general`):

```bash
srtgen input.mp4 --mode general
srtgen input.mp4 --mode shorts
srtgen input.mp4 --mode transcript
```

Notes:

- `general` is the default pipeline.
- `shorts` writes two outputs: the primary sentence-level SRT and a word-level SRT for animation.
- `transcript` produces larger, paragraph-like blocks and splits at detected silences and the `max_dur` limit.

Shorts defaults:

- Word SRT path defaults to `<stem>.words.srt` next to the primary output.
- Override the word SRT path with `--word-srt PATH`.

Transcript notes:

- Transcript mode applies the `transcript` formatting defaults (80 chars, 4 lines, 30s max).
- Use `--preset transcript` if you want those settings with `--mode general`.
- Use `--diarize` to enable speaker-labeled output in Transcript mode.
- When speaker labels are present, outputs prefix lines as `Speaker: text`.

## Formatting Options

These flags control chunking and readability. Defaults are shown in parentheses.

- `--max_chars` (42): Max characters per line.
- `--max_lines` (2): Max lines per subtitle cue.
- `--target_cps` (17.0): Target characters per second.
- `--min_dur` (1.0): Minimum cue duration in seconds.
- `--max_dur` (6.0): Maximum cue duration in seconds.
- `--no-comma-split` (default: allow commas): Do not split on commas.
- `--no-medium-split` (default: allow): Do not split on `;` or `:`.
- `--prefer-punct-splits` (default: off): Prefer punctuation splits even if text fits.
- `--min-gap` (0.08): Minimum gap between cues in seconds.
- `--pad` (0.00): Pad cues into nearby silence in seconds.

## Silence Settings

Silence-aware splitting and alignment are always enabled.

- `--silence-min-dur` (0.2): Minimum silence duration to consider (seconds).
- `--silence-threshold` (-35.0): Silence threshold in dB (example: `-35`).

## Transcription Options

- `--word-level`: Output one subtitle per word.
- `--word-srt`: Shorts mode only. Override the word-level SRT output path.
- `--prompt`: Provide an initial prompt string for transcription.
- `--prompt-file`: Provide a prompt file (`.docx` or `.txt`) for transcription.
- `--no-condition-on-previous-text`: Disable conditioning on previous text.
- `--no-speech-threshold`: Override the no-speech threshold.
- `--log-prob-threshold`: Override the log probability threshold.
- `--compression-ratio-threshold`: Override the compression ratio threshold.
- `--vad-filter` / `--no-vad-filter`: Enable or disable VAD filtering.

Notes:

- Word timestamps are always collected so that silence alignment can run and JSON outputs can include per-word timing.
- Voice activity detection (VAD) is controlled by the config key `vad_filter` (default: true) and can be overridden by `--vad-filter`/`--no-vad-filter`.

## Script Input

Bias transcription with an initial prompt:

- `--prompt "TEXT"`: Provide an initial prompt string.
- `--prompt-file PATH`: Read a prompt from a `.docx` or `.txt` file.

Notes:

- `.docx` prompts use paragraph text and list items; list items are treated as separate sentence units.
- Prompts are truncated to roughly 900 characters to stay within Whisper token limits.

## Script-Guided Substitution

Use a script as the authoritative text source at the sentence level:

- `--script PATH`: Provide a `.docx` or `.txt` script file.

Behavior:

- Script sentences replace matched Whisper segment text while preserving segment timestamps.
- Unmatched audio (ad-libs or skipped lines) keeps the original Whisper text.

## Corrected SRT Alignment

Regenerate word-level outputs from a corrected sentence SRT:

- `--correction-srt PATH`: Align corrected text to Whisper word timestamps.

Shorts workflow:

1. Run `--mode shorts` to generate the sentence SRT.
2. Edit the sentence SRT text.
3. Re-run with `--mode shorts --correction-srt corrected.srt` to regenerate the word-level SRT.

## Speaker Diarization

Enable speaker labels for Transcript output:

Installation:

- `pip install local-srt[diarize]`

Usage:

- `--diarize`: Enable speaker diarization (Transcript mode only).
- `--hf-token TOKEN`: HuggingFace token for diarization.
- `HF_TOKEN`: Environment variable fallback for `--hf-token`.

Notes:

- Diarization runs only in Transcript mode (`--mode transcript`).
- Output prefixes each cue with `Speaker: text` when labels are available.

## Batch Processing

Directory input (recursive scan):

```bash
srtgen videos/
```

Multiple inputs with a shared output directory:

```bash
srtgen a.mp3 b.mp3 --outdir out/
```

Keep directory structure under `--outdir`:

```bash
srtgen videos/ --outdir out/ --keep-structure
```

Notes:

- Directory scanning is always recursive. There is no `--recursive` flag.
- Use `--glob` to add an extra glob pattern (example: `--glob "*.wav"`).
- Use `--root` to set the base root used with `--keep-structure`.
- Use `--overwrite` to overwrite existing outputs.
- Use `--continue-on-error` to keep processing other files after a failure.

## Config File

Use `--config path/to/config.json` to apply overrides from a JSON file. CLI args always override config values, and presets are applied after the config file.

Precedence order:

- Defaults
- `--config` JSON
- `--preset` preset
- `--mode` pipeline defaults
- CLI flags

Accepted keys (nested JSON object):

- `formatting`: `max_chars`, `max_lines`, `target_cps`, `min_dur`, `max_dur`
- `formatting`: `allow_commas`, `allow_medium`, `prefer_punct_splits`
- `formatting`: `min_gap`, `pad`
- `transcription`: `vad_filter`, `initial_prompt`
- `silence`: `silence_min_dur`, `silence_threshold_db`

Example:

```json
{
  "formatting": {
    "max_chars": 40,
    "max_lines": 2,
    "target_cps": 16.0,
    "min_dur": 0.9,
    "max_dur": 5.0,
    "allow_commas": true,
    "allow_medium": true,
    "prefer_punct_splits": false,
    "min_gap": 0.08,
    "pad": 0.05
  },
  "transcription": {
    "vad_filter": true
  },
  "silence": {
    "silence_min_dur": 0.2,
    "silence_threshold_db": -35.0
  }
}
```

## Diagnostics

Use `srtgen --diagnose` to print system information and exit. Output includes:

- Tool version
- Python version
- Platform
- ffmpeg and ffprobe versions
- faster-whisper version (if installed)
- Detected `ffmpeg` and `ffprobe` paths

## Dry Run

Use `--dry-run` to validate inputs and show the resolved config without running transcription. When not combined with `--quiet`, the resolved config is printed as JSON.

## Temp Files

- `--keep_wav` keeps the temporary 16 kHz mono WAV file.
- `--tmpdir PATH` sets the directory for temporary WAV output.

## Logging and Debugging

- `--quiet` reduces output to errors only.
- `--no-progress` disables the progress line.
- `--debug` prints stack traces for errors.
- `--version` prints the tool version and exits.

## Library Usage

Minimal usage:

```python
from pathlib import Path
from local_srt import ResolvedConfig, load_model, transcribe_file

model, device_used, compute_type = load_model(
    model_name="small",
    device="auto",
    strict_cuda=False,
)

result = transcribe_file(
    input_path=Path("input.mp3"),
    output_path=Path("output.srt"),
    fmt="srt",
    cfg=ResolvedConfig(),
    model=model,
    device_used=device_used,
    compute_type_used=compute_type,
)

print(result.success, result.output_path)
```

With event handling:

```python
from local_srt import EventEmitter, LogEvent, ProgressEvent

emitter = EventEmitter()

def handler(event):
    if isinstance(event, LogEvent):
        print(event.message)
    elif isinstance(event, ProgressEvent):
        print(f"{event.percent:5.1f}%")

emitter.subscribe(handler)
```

Pass the handler into API calls:

```python
model, device_used, compute_type = load_model(
    model_name="small",
    device="auto",
    strict_cuda=False,
    event_handler=emitter,
)

result = transcribe_file(
    input_path=Path("input.mp3"),
    output_path=Path("output.srt"),
    fmt="srt",
    cfg=ResolvedConfig(),
    model=model,
    device_used=device_used,
    compute_type_used=compute_type,
    event_handler=emitter,
)
```

Batch usage (single model load):

```python
from local_srt import transcribe_batch

inputs = [Path("a.mp3"), Path("b.mp3")]
batch = transcribe_batch(
    input_paths=inputs,
    outdir=Path("out"),
    fmt="srt",
    cfg=ResolvedConfig(),
    model=model,
    device_used=device_used,
    compute_type_used=compute_type,
    event_handler=emitter,
)

print(batch.successful, batch.failed)
```

## Troubleshooting

**ffmpeg not found**

Verify ffmpeg is on PATH:

```bash
ffmpeg -version
```

**CUDA errors**

- Ensure NVIDIA drivers are installed.
- The tool falls back to CPU automatically unless `--strict-cuda` is set.
