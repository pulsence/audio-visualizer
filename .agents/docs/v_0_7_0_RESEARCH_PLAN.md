# v0.7.0 Feature Development — Research Plan

> **Breaking Release**: v0.7.0 breaks saved project backward compatibility (center-origin coordinate change).
> Research conducted against codebase at commit `0ba75b2` on 2026-03-22.

## Overview

This plan explores six areas of work specified in the v0.7.0 TODO:

1. **SRT Edit Screen** — Timeline interaction improvements, segment operations, word-level editing, markdown text styling, UI restructure
2. **Render Composition Screen** — Real-time GPU-composited playback, audio volume, timeline scrubbing, waveform display, track ordering, center-origin coordinates, layout fixes
3. **SRT Gen Screen** — Script-assisted transcription, model management UI, bundle-from-SRT
4. **Caption Animator** — New animations (word highlight, typewriter), JSON bundle input, markdown text styling, render output consolidation, render queue alignment
5. **Audio Visualizer Screen** — GPU hardware acceleration fix across all render paths
6. **Advanced Screen (new tab)** — LoRA training, correction data management, per-speaker adaptation

**Primary data format decision:** The JSON bundle becomes the primary data format flowing through the SRT Gen → SRT Edit → Caption Animator pipeline (see section 4.2).

**Cross-cutting implementation contracts discovered during review:**
- The current JSON bundle writer, SRT models, and SRT Edit resync helper do **not** agree on a single word-level schema yet. Bundle versioning and a normalized loader have to be treated as foundation work, not an implementation detail.
- The center-origin change affects persisted composition data inside settings/project files and recipe-driven workflows. "No migration" is only safe if old payloads are explicitly version-gated or rejected instead of silently loaded.
- The current app shell, settings schema, and recipe schema all assume six tabs. Adding an Advanced tab requires persistence and shell updates outside the tab implementation itself.
- The current caption workflow deliberately produces both a user-facing MP4 and a composition-facing overlay MOV. User feedback resolves the direction here: the single MP4 must be reusable across tabs, and any overlay-specific artifact can only be optional/internal.
- Real-time playback and in-app LoRA training both introduce dependencies that are not currently in `pyproject.toml` or the Windows PyInstaller build flow, but user feedback resolves the packaging direction: ship them inside the desktop app rather than pushing training into a separate environment.

---

## 1. SRT Edit Screen

### 1.1 Current State

| Component | File | Role |
|-----------|------|------|
| `SrtEditTab` | `ui/tabs/srtEditTab.py` (989 lines) | Main tab: split pane with waveform + table + QA sidebar |
| `SubtitleDocument` | `ui/tabs/srtEdit/document.py` | Data model: ordered `SubtitleEntry` list with dirty tracking |
| `SubtitleTableModel` | `ui/tabs/srtEdit/tableModel.py` | Qt table model (6 columns: #, Start, End, Duration, Text, Speaker) |
| `WaveformView` | `ui/tabs/srtEdit/waveformView.py` | pyqtgraph-based audio timeline with `LinearRegionItem` segments |
| `commands.py` | `ui/tabs/srtEdit/commands.py` | Undo stack: edit, add, remove, split, merge, move, batch resync |
| `parser.py` | `ui/tabs/srtEdit/parser.py` | SRT/ASS/VTT I/O via pysubs2 |
| `resync.py` | `ui/tabs/srtEdit/resync.py` | Bulk timing: global shift, 2-point stretch, FPS, silence snap |
| `lint.py` | `ui/tabs/srtEdit/lint.py` | QA profiles with auto-fixable rules |

**Current layout structure:**
```
QVBoxLayout (root):
├── Source Pickers Row (audio combo + subtitle combo)
├── Main Splitter (QSplitter, Vertical)
│   ├── WaveformView (pyqtgraph PlotWidget)
│   └── Bottom Panel (QHBoxLayout)
│       ├── QTableView (3× stretch)
│       └── QA Panel (1× stretch): Lint Profile combo + Run Lint + issue list
├── Resync Toolbar: Global Shift, Shift from Cursor, 2-Point Stretch, FPS Correction, Silence Snap
└── Playback & Edit Toolbar: Play/Pause/Stop | Add/Remove/Split/Merge | Save/Export
```

### 1.2 Load SRT Bundle for Word-Level Pairings

**Decision:** SRT Edit defaults to reading JSON bundles. Bundle loading via `srt.io` for DRY.

**Current bundle schema today (`srt/io/outputWriters.py`):**

```json
{
  "tool_version": "...",
  "input_file": "...",
  "device_used": "...",
  "compute_type_used": "...",
  "config": {...},
  "segments": [
    {
      "start": 0.0,
      "end": 1.2,
      "text": "...",
      "words": [{"start": 0.0, "end": 0.3, "word": "..."}]
    }
  ],
  "subtitles": [
    {"start": 0.0, "end": 1.2, "text": "..."}
  ]
}
```

**Gap:** The current codebase does not yet have a single canonical word-level contract. There are three independent representations that disagree on both field naming and data structure:

1. **`WordItem` dataclass** (`srt/models.py`): Uses field name `text` (`WordItem.text`). This is the app's own data model, but it is **not actually used by the bundle writer** — the writer bypasses `WordItem` entirely.
2. **`write_json_bundle()`** (`srt/io/outputWriters.py`): Consumes raw faster-whisper `Word` objects directly (which have a `.word` attribute, not `.text`) and emits them as `segments[].words[].word` — nested inside each segment.
3. **`reapply_word_timing()`** (`ui/tabs/srtEdit/resync.py`): Reads `json_bundle_data.get("words", [])` — expecting a **top-level** `words[]` key with `.text` fields. However, the current bundle schema has **no top-level `words` key**; words are nested inside `segments[].words[]`. This means the function would receive an empty list from the current bundle format unless someone pre-flattens the data before calling it.

This is not just a field-naming mismatch — it is a **structural mismatch**: the bundle nests words inside segments, while the consumer expects a flat top-level list. Additionally, the pipeline routes around `WordItem` entirely (faster-whisper `Word` → bundle JSON, skipping the app's own model), so simply renaming a field on `WordItem` would not fix the disconnect. The normalized loader must bridge all three representations.

Additional missing pieces:
- The bundle has no stable IDs, no explicit subtitle-to-word mapping, no preserved original/generated text field, and no bundle schema version.

Without resolving that contract first, the later plans for word editing, correction tracking, markdown persistence, and caption animation all depend on inferred structure instead of stable data.

**Required changes:**
1. **Bundle loader in `srt.io`** — Add `read_json_bundle()` that normalizes legacy/current bundle variants into one in-memory structure. Reused by SRT Edit and Caption Animator.
2. **Bundle schema versioning** — Add `bundle_version` and treat the upcoming format as a new contract rather than silently overloading the current writer output.
3. **Stable identifiers** — Add stable `id` fields for subtitle cues and, if word editing persists back to disk, stable IDs or deterministic ordering for words.
4. **Provenance fields** — Persist enough metadata for later correction tracking (`original_text`, source media path or asset id, model/device/compute type, optional speaker/confidence fields when available).
5. **SRT Edit parser** — `_load_subtitle()` gains `.json`/`.bundle.json` support.
6. **Asset listing** — List both `category="subtitle"` and `category="json_bundle"` assets.
7. **`SubtitleEntry` extension** — Add `words: list[WordItem]` plus source/provenance fields needed for correction tracking.
8. **Save options** — "Save Bundle" (preserves word timing + metadata) and "Export SRT" (plain).

### 1.3 Full Word-Level Editing UI

**Decision:** Full word-level editing with timeline tab switcher and expandable table rows.

**Timeline word view — using separate `LinearRegionItem` per word:**

Options A and C from the prior draft were similar: both use `LinearRegionItem`. The difference is that Option A creates standalone `LinearRegionItem` objects placed at word positions with manual constraint logic to enforce parent bounds, while Option C nests them within the parent's `LinearRegionItem` using `setBounds()` for automatic clamping. In practice, pyqtgraph `LinearRegionItem` does not support true nesting — `setBounds()` sets absolute x-limits on the region, so Option C still requires manual constraint updates when the parent moves. The approaches converge to the same implementation: standalone `LinearRegionItem` per word with dynamically updated bounds matching the parent segment edges.

**Table expansion — Decision: Option B (flat table with inline word rows).**

Insert/remove word rows inline below parent segment row with visual indentation. Keeps `QTableView` and existing `SubtitleTableModel`. Must manage row indices carefully but avoids rewriting the model as a tree model.

**Data model changes:**
- `SubtitleEntry` needs: `words: list[WordItem]` field (optional, empty if no word-level data)
- `WordItem` from `srt/models.py` currently has: `start: float`, `end: float`, `text: str`
- If bundle payloads continue to store `word`, the shared loader should normalize persisted `word` -> in-memory `text`
- New undo commands: `EditWordTimestampCommand`, `EditWordTextCommand`

### 1.4 Timeline Segment Border Expansion on Highlight

**Decision: Option A** — Increase `LinearRegionItem` line width on hover via `hoverEvent` on all segments.

Subclass `LinearRegionItem` or its `InfiniteLine` children. Override `hoverEvent` to toggle between normal (1px) and wide (4-6px) pen via `setPen()`. Apply to all segments, not just the highlighted one.

### 1.5 Table Row Selection: Pan Instead of Zoom

**Design — Pan to center, auto-zoom only if segment doesn't fit:**

```python
def highlight_region(self, index):
    lo, hi = entry.start_ms, entry.end_ms
    current_range = self.viewRange()[0]
    view_width = current_range[1] - current_range[0]
    segment_width = hi - lo
    center = (lo + hi) / 2
    if segment_width <= view_width:
        self.setXRange(center - view_width / 2, center + view_width / 2, padding=0)
    else:
        self.setXRange(lo - segment_width * 0.1, hi + segment_width * 0.1)
```

### 1.6 Split Segment at Playhead

**Decision:** Split uses playhead if within segment, falls back to midpoint. Context menus on both timeline and table.

**Context menu items:**
- Split at Playhead
- Merge with Next / Merge with Previous
- Delete Segment
- Edit Text

### 1.7 Drag-to-Select for New Segment Creation

**Decision:** Mouse release does NOT automatically create an entry. After drag-selection, user right-clicks to choose:
- "Create Blank Segment" — creates segment with empty text
- "Create Segment from Clipboard" — creates segment with text from clipboard

**Design:**
- Mouse press in empty area starts drag.
- Temporary `LinearRegionItem` in semi-transparent blue tracks mouse movement.
- Mouse release: selection remains visible as a temporary highlight.
- Right-click context menu offers creation options.
- On creation, `AddEntryCommand` is pushed. Entry inserted at sorted position (see 1.8).

### 1.8 Segment Overlap Prevention and Auto-Ordering

**Design for auto-ordering:**
- Insert new entries at sorted position using `bisect.insort` on `start_ms`.
- After any timestamp edit, call `_ensure_sorted()` to reposition.
- `_reindex()` ensures indices match order.

**Design for overlap prevention during drag:**
- Clamp boundary values: start ≥ previous entry's end, end ≤ next entry's start.

### 1.9 Markdown Text Styling Support

**Current state — no formatting layer exists:**
- `SubtitleEntry.text` is a plain Python string with no formatting metadata.
- `MultilineTextDelegate` uses `QPlainTextEdit` — no syntax highlighting or formatting preview.
- Text flows as plain text through the entire pipeline: SRT Edit → bundle/SRT file → Caption Animator.
- The word_reveal animation tokenizer (`_tokenize_words()` in `wordRevealAnimation.py`) uses regex `\w+(?:'\w+)?[^\w\s]*|[^\w\s]+` which does not understand markdown delimiters.

**Gap:** Users need to add markdown-style formatting to subtitle text in SRT Edit that flows through to Caption Animator for styled rendering. Required markdown support:
- `**bold text**` — rendered as bold in captions
- `*italic text*` — rendered as italic in captions
- Highlight targeting uses inline `==...==` markup so italics and highlight intent stay unambiguous.

**Design — End-to-end markdown support:**

| Layer | Change Required |
|-------|----------------|
| `SubtitleEntry.text` | Store markdown source directly in the text field (e.g., `"Hello **world**"`) |
| `QPlainTextEdit` editor | Add `QSyntaxHighlighter` subclass for markdown — highlight `**...**` and `*...*` with visual formatting cues |
| Table cell rendering | Optional: render markdown preview in delegate's `paint()` using `QTextDocument` with HTML conversion |
| Bundle I/O | Preserve markdown in `subtitles[].text` field — no conversion needed (it's just text) |
| SRT file export | Strip markdown markers for plain SRT compatibility, or preserve them (user choice) |
| Caption Animator parser | Parse markdown markers → convert to ASS override tags: `**bold**` → `{\b1}bold{\b0}`, `*italic*` → `{\i1}italic{\i0}` |
| Highlight targeting | Use inline `==word==` markup; do **not** overload italics markup |
| Word tokenizer | Strip markdown delimiters before tokenization, then re-inject ASS tags at correct positions |
| Animation plugins | Update word_reveal, word_highlight, typewriter to handle ASS-tagged text correctly |

**Markdown-to-ASS conversion table:**

| Markdown | ASS Override |
|----------|-------------|
| `**bold**` | `{\b1}bold{\b0}` |
| `*italic*` | `{\i1}italic{\i0}` |
| `==highlight target==` | Animation-specific targeting marker; converted before or alongside ASS styling |

**Implementation approach:**
1. Text is stored with markdown markers in the bundle and in `SubtitleEntry.text`.
2. SRT Edit shows markdown with syntax highlighting in the editor.
3. When Caption Animator loads the bundle, a markdown-to-ASS conversion layer transforms markers to ASS override tags before passing to pysubs2/animation plugins.
4. Animation plugins (word_reveal, typewriter) strip ASS tags before tokenizing, then re-inject at correct positions in the output.

### 1.10 Controls Layout Restructure

**Decision:** Merge all control buttons into the existing right sidebar panel.

**Design:**
- Move all bottom toolbar buttons into the QA/Lint right sidebar.
- Sidebar sections: Playback controls, Edit operations, Resync operations, QA/Lint.
- Add `QPlainTextEdit` with markdown syntax highlighting for segment text editing (appears when segment is selected).
- Remove bottom toolbars entirely.

---

## 2. Render Composition Screen

### 2.1 Current State

| Component | File | Role |
|-----------|------|------|
| `RenderCompositionTab` | `ui/tabs/renderCompositionTab.py` (2100+ lines) | Main tab: layer list + settings + preview + timeline |
| `CompositionModel` | `ui/tabs/renderComposition/model.py` (371 lines) | `CompositionLayer` + `CompositionAudioLayer` dataclasses, CRUD |
| `TimelineWidget` | `ui/tabs/renderComposition/timelineWidget.py` (511 lines) | Timeline with drag/trim/reorder, playhead, scroll/zoom |
| `commands.py` | `ui/tabs/renderComposition/commands.py` (335 lines) | 14 QUndoCommand subclasses |
| `filterGraph.py` | `ui/tabs/renderComposition/filterGraph.py` (429 lines) | FFmpeg filter_complex builder |
| `presets.py` | `ui/tabs/renderComposition/presets.py` (217 lines) | Layout presets + user preset save/load |

### 2.2 Audio Volume Control

**Design:**
- Add `volume: float` (0.0–2.0, default 1.0) and `muted: bool` (default False) to `CompositionAudioLayer`.
- UI: Volume slider (0–200%) + mute toggle button in audio settings page.
- **Mute/unmute also controllable directly on the timeline** (e.g., mute icon on audio track items).
- FFmpeg: Add `volume={value}` filter. If muted, skip audio input.
- Timeline: Muted audio layers shown with dimmed color.

### 2.3 Real-Time GPU-Composited Playback

**Decision:** Full GPU compositing from the start. No half measures.

**Architecture — Custom `QOpenGLWidget` compositor:**

| Component | Library | Role |
|-----------|---------|------|
| Video decode | PyAV (`thread_type="AUTO"`, software) | Decode each layer's video to numpy arrays |
| Frame upload | PyOpenGL + `QOpenGLWidget` | Upload numpy frames as GL textures |
| Compositing | `QOpenGLTextureBlitter` | Position, scale, blend layers in z-order |
| Audio decode | PyAV | Decode audio layers to float32 numpy arrays |
| Audio mixing | numpy | Mix layers with volume/mute per layer |
| Audio output | `sounddevice` (PortAudio callback) | Low-latency callback-based playback |
| A/V sync | Audio-master clock | Audio callback tracks position; video presents matching frames |
| Seeking | PyAV seek + flush | Seek all decode threads, present new frame |

**New dependencies:** `PyOpenGL` and `sounddevice` (both accepted).

**Packaging/runtime prerequisites:**
- Add both dependencies to `pyproject.toml`; they are not currently installed by the base project dependency set.
- Update the Windows PyInstaller build path to bundle the required runtime pieces (`PyOpenGL` imports and PortAudio for `sounddevice`).
- Add runtime feature gating: if OpenGL context creation, `sounddevice` import, or audio device initialization fails, the tab should fall back to the existing preview workflow instead of leaving playback broken.
- Keep tests and CI able to instantiate the playback widget without requiring a physical audio device.

**Performance (1080p 2-layer):** ~10-16ms per frame total → 60-100fps headroom at 30fps target.

**Threading model:**
```
Main Thread (Qt event loop)
├── QTimer (16ms) → poll audio clock → QOpenGLWidget.update()
├── paintGL() → upload latest frames → draw textured quads via QOpenGLTextureBlitter

Decode Thread (per video layer)
├── PyAV decode loop → frame.to_ndarray() → push to bounded deque

Audio Thread (sounddevice C callback)
├── read from pre-mixed ring buffer → increment sample counter (audio clock)
```

**Compositing detail:**
- `QOpenGLTextureBlitter` is a PySide6 built-in class that handles vertex data, shaders, buffers, and matrix calculations for blitting textures onto quads.
- `targetTransform(targetRect, viewportSize)` computes the positioning/scaling transform.
- Call `blit()` per layer in z-order with `glEnable(GL_BLEND)` + `glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)`.
- Pre-allocate GL textures per layer; update via `glTexSubImage2D` (~0.5-1ms per 1080p RGBA frame).

**Audio-master clock pattern:**
- Audio callback increments sample counter → derives media time in seconds.
- `QTimer` polls audio clock position, finds video frame with closest PTS, uploads and displays.
- If video is late: drop frames. If early: repeat previous frame.

**Seeking:**
1. Signal all decode threads to flush and seek their PyAV containers.
2. Pause audio, seek ring buffer to new position.
3. Decode one frame per layer at new position, upload and display.
4. Resume playback if it was playing.

**Transport controls:**
- Play/Pause toggle, Stop, Jump to Start (`|<<`), Jump to End (`>>|`).
- Spacebar binding via `keyPressEvent`.
- Auto-updating preview: `playhead_changed` → 400ms debounced preview render.

### 2.4 Timeline Scrubbing

**Design — Continuous drag scrubbing:**
- Detect mouse press near playhead line (~5px tolerance).
- Track mouse movement, update `playhead_ms` continuously.
- Emit `playhead_changed` → debounced preview update.

### 2.5 Audio Waveform on Timeline

**Decision:** Low-resolution RMS envelope (~100 samples/sec).

**Design:** Compute RMS envelope, cache per source, draw as filled `QPainterPath` in `paintEvent()`.

### 2.6 Track Ordering: Visual Up, Audio Down

**Design:** Sort visual items by z **descending** (highest z at top row). Audio items in list order.

### 2.7 Video with Audio: Dual Track Insertion

**Decision:** Auto-create linked layers. Popup on delete. Mute/unmute on audio layers.

**Design:**
1. Extend `_probe_media_dimensions()` to detect audio streams. Auto-create both layers.
2. Add `linked_layer_id: Optional[str]` to both model types.
3. On delete: `QMessageBox` — "Delete both" / "Delete only this" / "Cancel".
4. Mute toggle in audio layer list item, settings panel, **and timeline**.

### 2.8 Center-Origin Coordinate System

**Decision:** Break backward compatibility. No migration.

**Conversion:** `fx = (output_width / 2) + ux - (layer_width / 2)`, `fy = (output_height / 2) + uy - (layer_height / 2)`.

**Persistence impact that must be addressed explicitly:**
- `CompositionModel.to_dict()` / `from_dict()` currently serialize top-left coordinates into project/settings payloads.
- The app auto-loads persisted settings/project files, and workflow recipes can restore tab settings that assume the current coordinate system.
- "No migration" therefore still requires a version bump and rejection path for old composition payloads; otherwise old files will load successfully with incorrect positions.
- Layout presets in `renderComposition/presets.py` also need to be reviewed because they currently compute top-left coordinates directly.

### 2.9 Visual Asset Resize Controls

**Design:** Ratio lock checkbox (default on). "Original Size" and "Fit to Output" buttons.

### 2.10 Settings Panel Label/Form Alignment

**Design — `QGridLayout`/`QFormLayout` restructure:**

Visual Position & Size:
```
Row 0:  X: [spin]    Y: [spin]
Row 1:  W: [spin]    H: [spin]   [Lock Ratio]
Row 2:  Z: [spin]    [Original Size] [Fit to Output]
```

Audio settings:
```
Name:          [edit field]
Source:        [label] [Browse...]
Start (ms):    [spin]
Duration (ms): [spin]    ☑ Full Length
Volume:        [slider 0-200%]   [Mute]
```

---

## 3. SRT Gen Screen

### 3.1 Current State

| Component | File | Role |
|-----------|------|------|
| `SrtGenTab` | `ui/tabs/srtGenTab.py` | Batch transcription UI with full config surface |
| `SrtGenWorker` | `ui/workers/srtGenWorker.py` | Background worker: model load + batch transcription |
| `pipeline.py` | `srt/core/pipeline.py` | 4-stage pipeline: WAV → transcribe → chunk → write |
| `ModelManager` | `srt/modelManager.py` | Thread-safe single-model cache |
| `modelManagement.py` | `srt/modelManagement.py` | Standalone model list/download/delete/diagnose |

### 3.2 Script-Assisted Transcription

**Decision:** Per-file script input.

**Design:** Add `script_path: Optional[Path]` to `SrtGenJobSpec`. File picker for `.txt`/`.docx`.

### 3.3 Model Management UI

**Decision:** Add to the application settings dialog.

**Design:** "Whisper Models" section in Settings dialog. Table with model status, download/delete, progress bar.

### 3.4 Bundle from Existing SRT

**Decision:** Only extract word-level timing by running Whisper and mapping words to existing SRT segments without changing text. Assumes the user's SRT has already been corrected.

**Design:**
1. SRT Gen accepts SRT file + audio file as input.
2. Runs Whisper transcription to get word-level timestamps.
3. Maps Whisper words to existing SRT segment boundaries using alignment (reuse `align_script_to_segments()` or similar).
4. Produces a bundle with the corrected SRT text + Whisper word-level timing.
5. SRT text is NOT changed — only word-level timing is extracted and attached.

**Implementation gap:** `align_script_to_segments()` currently aligns sentence text to segment-like objects; it is not yet a cue-to-word alignment layer for arbitrary corrected subtitle files. v0.7.0 needs a dedicated subtitle-cue-to-word alignment helper with:
- clear matching rules for punctuation/casing differences,
- failure behavior when a cue cannot be matched confidently,
- a way to mark bundle entries as estimated vs confidently aligned.

### 3.5 LoRA Selection in SRT Gen

**Design:**
- SRT Gen model selection gains a "LoRA Adapter" dropdown alongside the base model selector.
- Lists available LoRAs from the Advanced Screen's training output directory.
- When a LoRA is selected, the corresponding merged CTranslate2 model is loaded by `ModelManager`.
- "None" option for base model without adaptation.

---

## 4. Caption Animator

### 4.1 Current State

| Component | File | Role |
|-----------|------|------|
| `CaptionAnimateTab` | `ui/tabs/captionAnimateTab.py` (1900+ lines) | Full UI: input/output, style, animation, preview, render |
| `AnimationRegistry` | `caption/animations/registry.py` | Plugin registry with `@register` decorator |
| `BaseAnimation` | `caption/animations/baseAnimation.py` | Abstract base |
| `ffmpegRenderer.py` | `caption/rendering/ffmpegRenderer.py` | FFmpeg rendering with quality tiers |

**Existing animations (8):** fade, slide_up, scale_settle, blur_settle, word_reveal, pulse, beat_pop, emphasis_glow.

### 4.2 JSON Bundle as Primary Format

**Decision:** JSON bundle is the primary data format. ASS is only the internal rendering format.

**Bundle pipeline:**
```
SRT Gen ─── produces ──→ .bundle.json (default) or .srt (option)
   │        also: load SRT+audio → produce bundle (word-level timing extraction)
   │
SRT Edit ── reads ────→ .bundle.json (default) or .srt/.vtt/.ass
   │        saves ────→ .bundle.json (preserves word timing) or .srt (export)
   │
Caption ─── reads ────→ .bundle.json (full animations) or .srt (limited animations)
Animator    generates → ASS internally for FFmpeg rendering
```

**Caption Animator changes:**
- Accept `.bundle.json` alongside `.srt`/`.ass`.
- Add `load_from_bundle()` to `SubtitleFile`.
- When bundle loaded: word-level animations use precise Whisper timestamps.
- When only SRT loaded: word-level animations use estimated timing — limited but functional.
- UI indicates which animations require word-level data.

### 4.3 Markdown Text Styling in Captions

**Decision:** Markdown is used for full styling, not just highlighting. `**Bold**`, `*Italics*`, etc.

**Design — Markdown-to-ASS conversion in Caption Animator:**

When Caption Animator loads text (from bundle or SRT), a conversion layer transforms markdown to ASS override tags before passing to pysubs2/animation plugins:

| Markdown | ASS Override | Visual Effect |
|----------|-------------|---------------|
| `**bold**` | `{\b1}bold{\b0}` | Bold text |
| `*italic*` | `{\i1}italic{\i0}` | Italic text |
| `==word==` | Context-dependent | Used by word_highlight animation as emphasis target |

**Animation plugin updates:**
- Word tokenizers strip ASS tags before splitting into tokens, then re-inject at correct positions.
- word_highlight animation can use `==word==` markers as explicit highlight targets (in addition to sequential highlighting).
- Markdown markers preserved in bundle text fields — conversion happens at render time.

### 4.4 Word Highlight Animation

**Decision:** Full styling — color + scale + glow.

**Design:** Per-frame ASS event generation. Each word's active period gets an event with highlight color (`\c`), scale (`\fscx`, `\fscy`), glow blur (`\blur`). Transition via `\t` tags.

**Parameters:** `highlight_color`, `highlight_scale` (100-150%), `highlight_blur` (0-10), `transition_ms`, `mode` ("even"/"weighted"/"word_level").

### 4.5 Typewriter Animation

**Design:** Per-character `\k` tags. Parameters: `chars_per_second` (default 20), `cursor_char`, `cursor_blink_ms`.

### 4.6 Render Output Consolidation

**Revised decision:** The single MP4 is the primary user-facing and inter-tab reusable output. Users should be able to render a single MP4 from Caption Animator and use that same file in Render Composition or outside the app. The current overlay intermediate (`*_caption_overlay.mov`) can remain as an optional/internal artifact for higher-fidelity composition workflows, but it must not be required for normal handoff.

**Design:**
- Continue generating the user-facing MP4 delivery file, optionally with muxed audio, and register it as a first-class reusable asset.
- Ensure Render Composition accepts that MP4 as a normal video source; this already aligns with the current visual-layer ingest model and existing matte/key controls (`colorkey`, `chromakey`, `lumakey`) for cases where the user wants to knock out the background.
- If an alpha/overlay-ready intermediate is still generated, treat it as an advanced/internal artifact for composition quality optimization, not as the main artifact the user is expected to manage.
- Default UI messaging should center the MP4 output. Any overlay artifact should be hidden or clearly labeled as optional advanced output.

### 4.7 Render Queue Alignment

**Design:** Ensure worker holds thread pool slot for full FFmpeg duration. Add shared render queue status indicator.

---

## 5. Audio Visualizer Screen

### 5.1 GPU Hardware Acceleration Fix

**Decision:** Fix across all three render paths.

**Current state:**

| Path | Codec | HW Accel? | Status |
|------|-------|-----------|--------|
| Audio Visualizer (PyAV) | h264_nvenc (attempted) | Silent fallback | Broken |
| Composition (FFmpeg) | libx264 (hardcoded) | None | Software only |
| Caption (FFmpeg) | libx264 (hardcoded) | None | Software only |

**Design:**
1. Detect available HW encoders at startup (nvenc/qsv/amf).
2. Encoder priority: NVIDIA → Intel → AMD → software.
3. Apply to all three render paths.
4. Add `-hwaccel auto` for FFmpeg input (decode acceleration).
5. Log actual encoder used. UI feedback in render progress area.

**Implementation notes that need to be reflected in code:**
- Separate **encoder selection** from **decode acceleration**. `-hwaccel auto` only affects decoding and does not, by itself, move a filter-heavy render onto GPU.
- Probe encoder availability with the actual FFmpeg build being shipped, and keep a per-render fallback path because available encoders can still fail at runtime for pixel-format/filtergraph reasons.
- The packaged app targets Windows in CI; MediaFoundation encoders (`h264_mf` / `hevc_mf`) are worth evaluating as an additional Windows-specific fallback instead of assuming only NVENC/QSV/AMF exist.

---

## 6. Advanced Screen (New Tab)

### 6.1 Overview

**Decision:** Create a new "Advanced" tab as the last entry in the navigation sidebar. This screen houses LoRA training, correction data management, and per-speaker adaptation tools.

**Application-shell impact outside the tab itself:**
- Add the tab to `MainWindow` lazy registration / instantiation.
- Add persistence slots in `ui/settingsSchema.py`.
- Decide whether workflow recipes should persist any Advanced-tab state and update `workflowRecipes.py` accordingly.
- Update tests and docs that currently assume exactly six tabs.

### 6.2 Correction Data Management

**Design — SQLite database for correction tracking:**

SRT Edit automatically tracks correction data when users edit text in segments. A SQLite database provides centralized, queryable storage for:

1. **Correction pairs:** original generated text ↔ corrected text, with source audio path, timestamps, speaker label (from diarization), and confidence score.
2. **Prompt/dictionary auto-population:** Query the DB for frequently corrected terms → auto-suggest for `initial_prompt` and post-processing dictionary.
3. **Training data export:** Extract audio+text pairs from the DB in HuggingFace datasets format for LoRA training.

**Database schema (conceptual):**

```sql
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY,
    audio_path TEXT NOT NULL,         -- Source audio file
    start_ms INTEGER NOT NULL,        -- Segment start
    end_ms INTEGER NOT NULL,          -- Segment end
    original_text TEXT NOT NULL,       -- Whisper-generated text
    corrected_text TEXT NOT NULL,      -- User-corrected text
    speaker_label TEXT,               -- From diarization (nullable)
    model_name TEXT,                  -- Which Whisper model was used
    lora_name TEXT,                   -- Which LoRA was active (nullable)
    confidence REAL,                  -- Whisper confidence score
    created_at TEXT NOT NULL          -- ISO timestamp
);

CREATE TABLE prompt_terms (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,        -- Domain term
    frequency INTEGER DEFAULT 1,     -- How often it was corrected to this
    speaker_label TEXT                -- Per-speaker term (nullable)
);

CREATE TABLE replacement_rules (
    id INTEGER PRIMARY KEY,
    pattern TEXT NOT NULL,            -- What Whisper produces
    replacement TEXT NOT NULL,        -- What it should be
    speaker_label TEXT,               -- Per-speaker rule (nullable)
    frequency INTEGER DEFAULT 1
);
```

**SRT Edit integration:**
- When a user edits text in a segment that originated from a bundle (has original generated text), the correction is automatically recorded in the DB.
- No extra user action required — corrections are tracked silently.
- DB stored in the application's data directory (`app_paths.py` data dir).

**Required provenance/write semantics:**
- `SubtitleEntry` needs enough origin data to distinguish "edited corrected text" from plain SRT imports with no model provenance.
- DB writes should happen on a committed action boundary (for example save/apply/explicit field commit), not every keystroke, or undo/redo will create duplicate correction rows.
- The correction record should keep both the immutable original generated text and the most recent accepted correction, plus bundle/entry IDs where available.

### 6.3 LoRA Training

**Design:**
- "Train LoRA" section in the Advanced screen.
- Inputs: base model selection, training data source (corrections DB or manual folder), hyperparameters (epochs, learning rate, LoRA rank).
- Process: Extract audio+text pairs → HuggingFace Transformers + PEFT LoRA training → merge adapter → convert to CTranslate2 → register in ModelManager.
- Progress: Training runs in background thread with progress bar and ETA.
- Output: Named LoRA stored in application data directory, selectable in SRT Gen.

**Dependency reality:** The current project does not yet ship the training stack needed for this path (`torch`, `transformers`, `peft`, dataset tooling, model conversion helpers), but user feedback resolves the strategy: these ship as required desktop-app dependencies. That means v0.7.0 must also cover:
- `pyproject.toml` dependency updates,
- build/installer updates for the Windows release workflow,
- startup/import performance considerations for heavier ML dependencies,
- feature gating and user-facing diagnostics when the host machine cannot actually train effectively despite the dependencies being present.

### 6.4 Per-Speaker LoRA Adaptation

**Feasibility analysis:**

CTranslate2/faster-whisper **cannot swap LoRA adapters at runtime** — each adapter must be pre-merged into a full model copy (~1.5-3 GB each). This makes per-speaker LoRA expensive in storage and load time.

**Recommended layered approach (practical for v0.7.0):**

| Layer | Approach | Per-Speaker? | Effort |
|-------|----------|-------------|--------|
| 1 | `initial_prompt` with speaker vocabulary | Yes — per-speaker prompt templates | Trivial |
| 2 | Post-processing dictionary | Yes — per-speaker rules in SQLite | Low |
| 3 | Single LoRA trained on all speakers | No — one model covers all | Medium |
| 4 | Per-speaker LoRA (future) | Yes — separate merged models | High |

**For v0.7.0:** Implement layers 1-3. Per-speaker adaptation is achieved by combining diarization labels with per-speaker prompts and dictionaries stored in the SQLite DB. The single LoRA trained on all speakers' correction data captures shared acoustic patterns.

**Per-speaker LoRA (future consideration):**
- Requires pre-merging each speaker's LoRA into a separate CTranslate2 model.
- Group segments by speaker from diarization, load each speaker's model, transcribe their segments.
- Practical only for 2-4 speakers with substantial audio per speaker.
- Research (PI-Whisper, SAML) validates the concept but requires custom implementation beyond what PEFT provides out of the box.

### 6.5 Prompt/Dictionary Management

**Design:**
- View and edit prompt terms and replacement rules from the SQLite DB.
- Auto-populated from correction data; user can add/remove manually.
- Per-speaker filtering when diarization labels are available.
- Export prompt as text for `initial_prompt` parameter.
- Export dictionary as JSON for post-processing.

---

## 7. Testing Considerations

| Area | Existing Tests | New Tests Needed |
|------|---------------|-----------------|
| SRT Edit word-level | None | Bundle loading, word-level data model, word boundary constraints |
| SRT Edit timeline | `test_ui_srt_edit_tab.py`, `test_srt_edit_model.py` | Pan-vs-zoom, border width on hover, context menu, drag-to-select with right-click, overlap prevention, auto-resort |
| SRT Edit markdown | None | Markdown syntax highlighting, markdown preservation in bundle, markdown-to-ASS conversion |
| SRT Edit controls | None | Controls panel layout, text editing box sync |
| Render Comp playback | None | QOpenGLWidget compositor, transport controls, spacebar, scrubbing, A/V sync, audio-master clock |
| Render Comp audio | Filter graph tests | Volume filter, mute (settings + timeline), waveform envelope |
| Render Comp tracks | Timeline tests | Z-order rendering, video+audio dual insertion, linked layer delete popup |
| Render Comp coordinates | Filter graph tests | Center-origin conversion, default positioning |
| SRT Gen script | None for UI | Per-file script picker |
| SRT Gen bundle-from-SRT | None | Word-level extraction, text preservation, alignment |
| SRT Gen LoRA selection | None | LoRA dropdown, merged model loading |
| Caption bundle input | None | Bundle loading, animation availability indicators |
| Caption markdown | None | Markdown-to-ASS conversion, tokenizer with ASS tags |
| Caption animations | Animation tests | word_highlight per-frame events, typewriter, markdown-styled text |
| Caption render output | Render tests | Delivery MP4 asset registration, reuse of that MP4 in Render Composition, optional/internal overlay artifact, optional audio mux |
| Hardware acceleration | None | Encoder detection, fallback logging, all three paths |
| Advanced screen | None | SQLite correction tracking, LoRA training pipeline, prompt/dictionary management |
| Persistence/schema | `test_ui_settings_schema.py`, `test_workflow_recipes.py` | Schema/version bump behavior, rejection of pre-center-origin composition payloads, Advanced tab persistence |
| Packaging/dependencies | None | Import gating for `PyOpenGL` / `sounddevice`, PyInstaller smoke coverage, optional training-dependency gating |

---

## 8. Implementation Sequencing

```
Cross-cutting foundations:
  Bundle schema contract        — before Sections 1, 3, 4, and 6
  Settings/recipe versioning    — before 2.8 and 6.1 ship
  Dependency/packaging strategy — before 2.3 and 6.3 ship

Section 5 (GPU Accel)        — Foundation: affects all render paths, do first
Section 6 (Advanced Screen)  — New tab + SQLite DB; can start early
Section 1 (SRT Edit)         — Depends on 6.2 (SQLite) for correction tracking
Section 2 (Render Comp)      — Independent after Section 5
Section 3 (SRT Gen)          — Depends on 6.3 (LoRA) for adapter selection
Section 4 (Caption)          — Benefits from 1.2 (bundle format) and 1.9 (markdown)

Within Section 1:
  1.2 (Bundle loading)       — Foundation for everything
  1.3 (Word-level editing)   ← depends on 1.2
  1.9 (Markdown styling)     — Independent, but informs 1.10 (sidebar text editor)
  1.8 (Overlap prevention)   — Do early
  1.4 (Border expansion)     — Independent
  1.5 (Pan vs zoom)          — Independent
  1.6 (Split at playhead)    — Independent
  1.7 (Drag-to-select)       ← after 1.8
  1.10 (Controls restructure) ← after 1.9 (markdown editor in sidebar)

Within Section 2:
  2.8 (Center-origin coords) — Do early (affects all position logic)
  2.10 (Layout fix)          — Independent
  2.2 (Audio volume/mute)    — Independent
  2.4 (Scrubbing)            ← before 2.3
  2.3 (GPU playback)         ← depends on 2.4
  2.5 (Waveform)             — Independent
  2.6 (Track ordering)       — Independent
  2.7 (Video+audio)          — Independent
  2.9 (Resize controls)      — Independent

Within Section 4:
  4.2 (Bundle input)         — Do first
  4.3 (Markdown styling)     ← after 1.9 (shared markdown-to-ASS logic)
  4.4 (Word highlight)       ← after 4.2
  4.5 (Typewriter)           — Independent
  4.6 (Output consolidation) — Independent
  4.7 (Render queue)         — Independent

Within Section 6:
  6.2 (SQLite DB)            — Foundation for 6.3-6.5
  6.3 (LoRA training)        ← depends on 6.2
  6.5 (Prompt/dictionary)    ← depends on 6.2
  6.4 (Per-speaker)          — Future consideration, not v0.7.0 implementation
```

---

## 9. Risk Areas

| Risk | Mitigation |
|------|-----------|
| pyqtgraph word-level region constraints | Prototype early; fall back to custom `QGraphicsItem` if needed |
| Flat table inline word rows (index management complexity) | Careful index tracking; comprehensive test coverage |
| QOpenGLWidget compositor complexity | Follow proven `QOpenGLTextureBlitter` pattern; texture management is well-documented |
| PyAV software decode may not hit 30fps for 3+ layers | Profile early; 2 layers is ~10-16ms with headroom; add hwaccel if needed |
| Audio-video sync drift | Audio-master clock pattern; correct frame presentation from audio position |
| Markdown-to-ASS conversion edge cases | Thorough test matrix; handle nested/overlapping markers |
| Italics markup and highlight targeting share the same syntax | Use distinct representations (`*italic*` vs `==highlight==`) before implementation |
| Word tokenizer breaking on ASS tags | Strip tags before tokenization, re-inject at positions |
| SQLite DB corruption or concurrent access | WAL mode for concurrent reads; single-writer pattern from UI thread |
| LoRA training requires GPU + sufficient data | UI validates CUDA availability and dataset size before starting |
| Training stack dramatically increases dependency footprint | Ship as required dependencies per user feedback, but budget for build size, startup cost, and clear capability diagnostics |
| FFmpeg HW encoder detection unreliable | Startup probe with fallback chain; log actual encoder |
| Center-origin coordinate change silently mispositions old saved data | Bump schema / reject old composition payloads instead of only documenting the break |
| Bundle format tight coupling between tabs | `read_json_bundle()` in `srt.io` as single source of truth; version the format |
| Single-MP4 reuse and overlay-quality composition pull in different directions | Make MP4 the primary reusable asset, and keep any overlay artifact optional/internal only when it materially improves composition quality |

---

## 10. Decisions Made

| Topic | Decision |
|-------|---------|
| Word-level editing scope | Full: timeline tab switcher, inline expandable table rows (Option B), word bounds constrained to parent |
| Timeline word regions | `LinearRegionItem` per word with dynamically updated bounds (Options A and C converge) |
| Table expansion | Option B: flat table with inline word rows and visual indentation |
| Border expansion | Option A: hover-based line width increase on all segments |
| Context menu location | Both timeline and table |
| Split outside segment | Fall back to midpoint |
| Drag-to-select creation | Right-click after selection → "Create Blank" or "Create from Clipboard" |
| Playback engine | Full GPU compositing (QOpenGLWidget + QOpenGLTextureBlitter + sounddevice) |
| New dependencies | PyOpenGL and sounddevice accepted as app-shipped dependencies |
| Waveform resolution | Low-resolution RMS envelope (~100 samples/sec) |
| Linked layer deletion | Popup: "Delete both" / "Delete only this" / "Cancel" |
| Audio mute/unmute | Available in settings panel AND timeline interface |
| Script input | Per-file |
| Model management location | Settings dialog |
| Model training approach | LoRA + correction SRT feedback loop; SQLite DB for correction tracking |
| LoRA training location | New Advanced tab (last in sidebar) |
| LoRA selection | Dropdown in SRT Gen alongside base model selector |
| Per-speaker LoRA | Layers 1-3 for v0.7.0 (prompt + dictionary + single LoRA); per-speaker LoRA deferred |
| Bundle from existing SRT | Extract word-level timing only; do not change SRT text |
| Primary data format | JSON bundle (SRT Gen → SRT Edit → Caption Animator) |
| Word-level format | JSON bundle carries data; ASS is internal rendering format only |
| Text styling | Markdown syntax (`**bold**`, `*italic*`) in text, converted to ASS at render time |
| Specific word highlighting | Inline text markup `==word==` |
| Caption deliverables | The single MP4 is the primary reusable asset for users and inter-tab handoff; any overlay artifact is optional/internal only |
| Coordinate system | Center-origin; break backward compatibility; explicit schema/version gate for old payloads |
| Hardware acceleration | Fix across all three render paths |
| Controls restructure | Merge into existing right sidebar |
| Advanced tab integration | Update shell registration, settings persistence, and recipe implications together |
| LoRA dependency strategy | Ship the full training stack as required desktop-app dependencies |

---

## 11. Clarifications Resolved

1. **Word-level UI scope:** Full implementation.
2. **Context menu scope:** Both timeline and table.
3. **Split outside segment:** Fall back to midpoint.
4. **Playback engine:** Full GPU compositing. No half measures.
5. **Waveform resolution:** Low-resolution RMS.
6. **Linked layer deletion:** Popup. Mute/unmute on audio layers.
7. **Script input:** Per-file.
8. **Model management:** Settings dialog.
9. **Model training:** LoRA + correction feedback loop via SQLite DB. Advanced screen.
10. **Audio merge:** Complete — removed.
11. **Word highlight style:** Full styling (color + scale + glow).
12. **Specific word highlighting:** Inline text markup `==word==`.
13. **Single file output:** The user-facing MP4 is the primary reusable artifact and can be fed into Render Composition; any overlay artifact stays optional/internal.
14. **Word-level SRT input format:** JSON bundle primary; ASS internal only.
15. **Real-time playback:** Full GPU compositing from the start.
16. **Coordinate migration:** Break backward compatibility, but reject or version-gate old persisted composition payloads.
17. **Hardware acceleration:** All three render paths.
18. **Controls restructure:** Merge into existing right sidebar.
19. **Timeline word view:** LinearRegionItem per word (A and C converge).
20. **Table expansion:** Option B (flat table with inline rows).
21. **Border expansion:** Option A (hover-based width increase on all segments).
22. **Bundle from SRT:** Extract word-level timing only; preserve SRT text.
23. **New dependencies:** PyOpenGL and sounddevice accepted as shipped dependencies.
24. **Text styling:** Full markdown (`**bold**`, `*italic*`) with `==word==` as the explicit highlight-target representation.
25. **Drag-to-select behavior:** Right-click after selection to create (blank or from clipboard).
26. **Mute/unmute location:** Both settings panel and timeline interface.
27. **LoRA training location:** New Advanced tab as last sidebar entry.
28. **Overlay artifact retention:** The current `*_caption_overlay.mov` may remain for advanced/internal workflows, but the main handoff artifact is the MP4.
29. **Advanced tab persistence impact:** Treat as shell/schema work, not just a new widget.
30. **LoRA dependency strategy:** Ship the full training stack as required desktop-app dependencies.

---

## 12. Clarifications Required

(No outstanding clarifications — recent feedback has been integrated.)
