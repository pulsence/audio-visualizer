# v0.6.0 Stage Three - Multi-Tab Workflow UI Implementation Plan

This plan implements Stage Three of the v0.6.0 work: refactoring the current single-screen application into a multi-tab workflow desktop app with shared session assets, cancellable background jobs, SRT editing, caption animation, render composition, and workflow recipes.

**Scope:** Stage Three only. Stage Two package integration (`audio_visualizer.srt`, `audio_visualizer.caption`, and shared events) is assumed complete.

**Source research:** `V_0_6_0_RESEARCH_PLAN_3.md`

**Authoritative note:** This document is the implementation source of truth. `V_0_6_0_RESEARCH_PLAN_3.md` is background context only and should not be required to carry out the work below.

---

## Stage Three Target State

Stage Three ends with the application restructured as a five-screen workflow desktop app hosted inside a thin `MainWindow` shell. The finished app must have these top-level screens in this order:

1. `Audio Visualizer` — default landing screen; preserves the current product workflow
2. `SRT Gen` — transcription screen using `audio_visualizer.srt`
3. `SRT Edit` — waveform-backed subtitle editor with undo/redo, QA, and resync
4. `Caption Animate` — subtitle-to-overlay renderer using `audio_visualizer.caption`
5. `Render Composition` — final compositor for background/audio/overlay assembly

### MainWindow target layout

After Stage Three, `MainWindow` should be a thin shell with this shape:

```text
MainWindow
├── menu bar
│   ├── File
│   ├── Edit (Undo/Redo rebound to active tab when available)
│   └── Help
├── central widget
│   ├── NavigationSidebar (QListWidget-backed custom nav)
│   └── QStackedWidget
│       ├── AudioVisualizerTab
│       ├── SrtGenTab
│       ├── SrtEditTab
│       ├── CaptionAnimateTab
│       └── RenderCompositionTab
└── JobStatusWidget
    ├── active job label
    ├── progress indicator
    ├── status text
    └── cancel button
```

### Required application behavior

- Navigation uses `QStackedWidget` plus a custom sidebar, not `QTabWidget`.
- The app keeps one shared long-running user-job pool (`QThreadPool`, max 1) for render/transcribe/analyze/export work.
- Update checks keep using a separate background pool.
- The shell always shows active-job state, even when the user switches away from the source tab.
- Source tabs also show their own detailed progress views when focused.
- The sidebar shows a busy badge/spinner on tabs that own active work.
- Starting a second user job while the shared pool is busy is blocked with a clear status message; v0.6.0 does not support multiple simultaneous heavy jobs across tabs.
- Render completion should not auto-open a blocking modal dialog. Instead, show a completion notification with actions such as `Preview`, `Open Output`, and `Open Folder`. `RenderDialog` opens only when the user explicitly chooses preview.
- File-picking UIs across all tabs must support both current-session assets from `SessionContext` and raw filesystem browsing.

### Tab responsibilities

| Tab | Responsibilities | Primary outputs |
|-----|------------------|-----------------|
| `AudioVisualizerTab` | Current visualizer UI, live preview, visualizer rendering | Rendered visualizer video |
| `SrtGenTab` | Batch input queue, transcription settings, model lifecycle, cancellable queue execution | Subtitle file plus JSON/transcript/segment sidecars |
| `SrtEditTab` | Editable subtitle document model, waveform timeline, playback, undo/redo, QA, resync | Edited subtitle file |
| `CaptionAnimateTab` | Preset/style editing, cancellable caption rendering, audio-reactive animation | Caption overlay video |
| `RenderCompositionTab` | Layer layout, preset layouts, timeline rules, matte/key settings, final composition render | Final composed video |

### Chosen architectural decisions

These decisions are fixed for this implementation plan and should not be reopened during implementation unless a hard blocker is found:

| Topic | Decision |
|-------|---------|
| Tab host | `QStackedWidget` with custom navigation sidebar |
| MainWindow scope | Thin shell only; all workflow logic belongs in tab classes |
| Shared state | `SessionContext` owned by `MainWindow` and injected into tabs |
| Shared job model | Shared user-job pool (max 1) plus per-tab worker classes |
| Undo/redo | `QUndoStack` via `BaseTab`; used by SRT Edit and Render Composition only |
| SRT Gen scope | GUI-level batch orchestration over the existing single-file `transcribe_file()` API |
| SRT Edit parser strategy | Tab-local subtitle parser/editor model, not a Stage Two `audio_visualizer.srt` API expansion |
| Waveform stack | `pyqtgraph==0.14.0` on `PySide6==6.10.2` |
| Caption presets | Support built-ins, explicit preset files, and app-data preset library |
| Caption cancellation | In-process cancel by terminating FFmpeg |
| SRT cancellation | Cooperative queue checks plus killable subprocess boundary for per-file work |
| Composition engine | FFmpeg `filter_complex` renderer with hybrid auto-transcode/direct-render behavior |
| Composition timeline | Per-layer start/end with loop/trim/freeze behavior; final duration is max enabled layer end |
| Workflow reuse | Separate versioned recipe files, not merged into project saves or autosave state |

### Shared tab contract

Every tab class created in Stage Three must follow the same minimum contract through `BaseTab`:

- `tab_id: str` — stable storage and routing key such as `audio_visualizer`, `srt_gen`, `srt_edit`, `caption_animate`, `render_composition`
- `tab_title: str` — display label used in navigation/status UI
- `validate_settings() -> tuple[bool, str]` — tab-local validation before starting work
- `collect_settings() -> dict` — serializable settings payload with no live widget instances
- `apply_settings(data: dict) -> None` — restore settings from saved/project/recipe state
- `set_session_context(context: SessionContext) -> None`
- `set_global_busy(is_busy: bool, owner_tab_id: str | None) -> None` — disable or enable start controls based on shared-pool state
- `register_output_assets(...)` helpers or equivalent tab-local asset publication path
- optional undo helpers:
  - `_init_undo_stack(limit: int)`
  - `_push_command(command: QUndoCommand)`
  - `_clear_undo_stack()`
  - `undo_action()`
  - `redo_action()`

Tabs that render or run background work must also use the shared worker bridge/signal contract rather than emitting custom incompatible Qt signal shapes.

### Shared worker contract

All Stage Three workers should expose a consistent Qt-facing signal vocabulary so `MainWindow`, `JobStatusWidget`, and tabs can react uniformly:

- `started(job_type: str, owner_tab_id: str, label: str)`
- `stage(name: str, index: int | None, total: int | None, data: dict | None)`
- `progress(percent: float | None, message: str, data: dict | None)`
- `log(level: str, message: str, data: dict | None)`
- `completed(result: dict)` — includes output paths, asset metadata, and any follow-up actions
- `failed(error_message: str, data: dict | None)`
- `canceled(message: str | None)`

The bridge between `AppEventEmitter` and Qt signals should preserve stage/progress payloads rather than flattening them into plain strings. This is especially important for SRT Gen and Caption Animate, where downstream UI needs actual progress values, stage names, device/compute metadata, frame counts, and timing information.

### SessionContext contract

`SessionContext` is the cross-tab file provider and metadata registry for the whole app. It must carry enough information that downstream tabs can use outputs without lazily reprobe-opening every file.

#### Required `SessionAsset` fields

At minimum, each registered asset must carry:

- `id: str`
- `display_name: str`
- `path: Path`
- `category: str`
  - allowed starting categories for v0.6.0: `audio`, `subtitle`, `video`, `image`, `json_bundle`, `segments`, `transcript`, `config`, `preset`
- `source_tab: str | None`
- `role: str | None`
  - common roles: `primary_audio`, `subtitle_source`, `caption_overlay`, `visualizer_output`, `background`, `final_render`
- `width: int | None`
- `height: int | None`
- `fps: float | None`
- `duration_ms: int | None`
- `has_alpha: bool | None`
- `has_audio: bool | None`
- `is_overlay_ready: bool | None`
- `preferred_for_overlay: bool | None`
- `metadata: dict[str, object]`

#### Required `metadata` payloads by asset type

- Audio Visualizer outputs:
  - `include_audio_in_output`
  - `resolution`
  - `codec`
  - `visualizer_type`
- SRT Gen primary subtitles:
  - `format`
  - `mode`
  - `language`
  - `word_level_enabled`
  - `diarization_enabled`
- SRT Gen JSON bundles:
  - `contains_segments`
  - `contains_word_timing`
  - `contains_speaker_labels`
- Caption Animate outputs:
  - `quality`
  - `preset_name`
  - `render_quality`
  - `alpha_expected`
- Composition outputs:
  - `audio_source_asset_id`
  - `layer_count`
  - `export_profile`

#### Analysis cache contract

`SessionContext` must also own a lightweight reusable analysis cache keyed by:

`(asset_identity, analysis_type, settings_signature)`

Where:
- `asset_identity` is a stable value derived from asset id plus normalized path or fingerprint
- `analysis_type` starts with `waveform`, `silence`, and `audio_reactive`
- `settings_signature` captures the parameters that would change the analysis output

This cache exists so:
- SRT Edit can reuse waveform and silence data
- Caption Animate can reuse audio-reactive analysis
- Multiple tabs do not independently recompute the same long-running audio analysis

### Cross-tab asset rules

These are concrete v0.6.0 rules and should be implemented as-is:

- Audio Visualizer outputs are treated as video assets first. If they contain audio, that embedded audio is ignored by Composition unless the user explicitly selects it as the authoritative audio source.
- SRT Gen should register the primary subtitle file plus all generated sidecars. JSON bundles are especially important because SRT Edit resync features depend on them.
- Caption Animate outputs are classified like this:
  - `large` quality (ProRes 4444, `yuva444p10le` — has alpha channel) is the preferred reusable alpha-capable overlay intermediate
  - `small` quality (H.264, `yuva420p`) may be accepted for reuse only after Composition auto-normalizes it into a composition-friendly intermediate
  - `medium` quality (ProRes 422 HQ, `yuv422p10le` — no alpha channel) should be treated as opaque unless Composition explicitly normalizes or re-renders it
- Static images default to stretching across the full composition duration unless the user trims them earlier.
- Background video, visualizer video, and caption overlay layers support per-layer start/end time plus `loop`, `trim`, or `freeze_last_frame` behavior.
- Composition uses exactly one authoritative audio source in v0.6.0. The app does not need multi-track audio mixing in this release.
- SRT/ASS subtitle files may be rendered directly inside Composition only when the user intentionally chooses a direct-render caption layer path; otherwise Composition consumes the already-rendered overlay asset from Caption Animate.

### Settings, project, and recipe schemas

Stage Three needs three related but distinct storage artifacts:

1. App autosave state
2. Project save/load files
3. Workflow recipe files

#### App autosave / project schema

Use a versioned JSON shape with stable top-level sections. The exact implementation may use dataclasses or helper objects, but the stored structure should be equivalent to:

```json
{
  "version": 1,
  "ui": {
    "last_active_tab": "audio_visualizer",
    "window": {
      "width": 1600,
      "height": 1000,
      "maximized": false
    }
  },
  "tabs": {
    "audio_visualizer": {},
    "srt_gen": {},
    "srt_edit": {},
    "caption_animate": {},
    "render_composition": {}
  },
  "session": {
    "assets": [],
    "roles": {}
  }
}
```

Implementation rules:

- Autosave state lives under `get_config_dir()` and continues replacing the old `last_settings.json`.
- Project files may reuse the same schema shape but should omit purely machine-local window state when appropriate.
- The old pre-Stage-Three settings shape (`general`, `visualizer`, `specific`, `ui`) must migrate into `tabs.audio_visualizer`.
- Missing new-tab keys must silently default on load.
- Do not persist ephemeral state such as current playback position, waveform zoom, transient progress status, or selection highlights.

#### Workflow recipe schema

Recipes are not project saves. They are reusable workflow templates. The stored shape should be equivalent to:

```json
{
  "version": 1,
  "name": "Shorts Caption Workflow",
  "enabled_stages": {
    "srt_gen": true,
    "srt_edit": true,
    "caption_animate": true,
    "render_composition": true
  },
  "asset_roles": {
    "primary_audio": null,
    "subtitle_source": null,
    "caption_source": null,
    "background": null
  },
  "tabs": {
    "srt_gen": {},
    "srt_edit": {},
    "caption_animate": {},
    "render_composition": {}
  },
  "references": {
    "caption_preset": null,
    "layout_preset": null,
    "lint_profile": "pipeline_default"
  },
  "export": {
    "naming_rule": "{audio_stem}_final",
    "target_dir": null
  }
}
```

Recipe rules:

- Store recipes under the app data/config area, not in the repo root.
- Support explicit import/export as `.avrecipe.json`.
- Prefer semantic asset roles over absolute paths.
- Allow absolute or relative asset bindings only when the user intentionally saves them.
- Keep recipes versioned independently from project files so they can evolve without breaking session saves.

### Composition control surface

Render Composition must implement these concrete v0.6.0 controls:

- layer position: `x`, `y`
- layer size: `width`, `height`
- z-order
- layer timing:
  - `start_ms`
  - `end_ms`
  - `behavior_after_end`: `freeze_last_frame`, `hide`, `loop`
- audio source selector:
  - one standalone audio asset or one embedded stream from a selected video asset
- matte/key controls:
  - `mode`: `colorkey`, `chromakey`, `lumakey`
  - `key_target`
  - `threshold`/`similarity`
  - `blend`/`softness`
  - cleanup values for erode/dilate/feather
  - despill controls
  - invert toggle
  - alpha/matte debug preview toggle

### Subtitle QA and resync baseline

SRT Edit must ship with:

- inline warnings in the subtitle table
- a dedicated QA issue panel
- three named lint profiles:
  - `pipeline_default` — mirrors current SRT formatting defaults
  - `accessible_general`
  - `short_form_social`
- undoable machine-fix actions
- preview-based resync operations:
  - global shift
  - shift from cursor onward
  - two-point stretch
  - FPS drift correction
  - silence snap
  - segment/word timing reapply

Important implementation rules:

- word-level resync quality depends on JSON bundles generated with `word_level=True`
- speaker-aware resync is only available when speaker labels exist, which currently means transcript-mode transcriptions
- silence snap may directly import internal SRT helpers if they are not exported through `audio_visualizer.srt.__init__`

---

## Phase Files

- [x] [PHASE_1.md](./plan_phases/PHASE_1.md) - Foundation, Dependency Lane, and MainWindow Decomposition
- [x] [PHASE_2.md](./plan_phases/PHASE_2.md) - Extract the Audio Visualizer Tab
- [x] [PHASE_3.md](./plan_phases/PHASE_3.md) - Build the SRT Gen Tab
- [x] [PHASE_4.md](./plan_phases/PHASE_4.md) - Build the SRT Edit Tab
- [x] [PHASE_5.md](./plan_phases/PHASE_5.md) - Build the Caption Animate Tab
- [x] [PHASE_6.md](./plan_phases/PHASE_6.md) - Build the Render Composition Tab
- [x] [PHASE_7.md](./plan_phases/PHASE_7.md) - Workflow Recipes and Cross-Tab Integration Polish
- [ ] [PHASE_8.md](./plan_phases/PHASE_8.md) - User Debug - 1
- [ ] [PHASE_9.md](./plan_phases/PHASE_9.md) - User Debug - 2
- [ ] [PHASE_10.md](./plan_phases/PHASE_10.md) - Final Review

---
Implementation details for each phase live exclusively in the phase files above.
