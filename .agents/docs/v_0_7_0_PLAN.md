# v0.7.0 Feature Development — Plan Index

> **Breaking Release**: v0.7.0 intentionally breaks saved project backward compatibility for Render Composition because user-facing coordinates move from top-left origin to center origin.

**Authoritative note:** This index and the linked phase documents are the implementation source of truth for v0.7.0.

This file is intentionally streamlined. The full task breakdown for each numbered phase now lives in `.agents/docs/plan_phases/`.

## Shared Implementation Rules

1. The JSON bundle is the primary subtitle data format for the SRT Gen -> SRT Edit -> Caption Animator workflow. ASS remains an internal rendering format, not the authoring format.
2. Bundle v2 is the canonical schema. Legacy bundle handling must go through a shared reader/normalizer in `srt.io`, not through one-off compatibility logic.
3. The center-origin coordinate change is a hard schema break. Old composition payloads must be rejected with a clear user-facing message instead of being silently loaded with wrong positions.
4. Caption Animator's MP4 output is the primary reusable artifact for users and for inter-tab handoff. Any transparent overlay MOV stays optional and advanced/internal only.
5. The Advanced tab increases the shell from 6 tabs to 7 tabs. Shell registration, settings persistence, recipes, tests, and docs must all be updated together.
6. The official desktop build must ship the playback and training capabilities needed by v0.7.0. Source installs may still use extras where helpful, but the release build path must explicitly include them.
7. Per-speaker adaptation for v0.7.0 means per-speaker prompts and replacement rules plus one shared LoRA. Per-speaker LoRA model swapping is not part of this release.
8. Every numbered sub-phase in the linked phase docs must finish with tests, any needed architecture-doc updates, and a `git add` / commit / push using the format in `COMMIT_MESSAGE.md`.

## Phase Files

| Phase | Focus | Detailed file | Status |
|---|---|---|---|
| 1 | Cross-cutting foundations: bundle schema, persistence gating, dependencies, Advanced tab shell | [PHASE_1.md](./plan_phases/PHASE_1.md) | Complete |
| 2 | Shared GPU / hardware-acceleration work across all render paths | [PHASE_2.md](./plan_phases/PHASE_2.md) | Complete |
| 3 | Render Composition coordinate break, layout fixes, audio controls, linked layers | [PHASE_3.md](./plan_phases/PHASE_3.md) | Complete |
| 4 | Render Composition real-time GPU playback, scrubbing, waveform, transport | [PHASE_4.md](./plan_phases/PHASE_4.md) | Complete |
| 5 | Advanced tab correction database and prompt / dictionary management | [PHASE_5.md](./plan_phases/PHASE_5.md) | Complete |
| 6 | Advanced tab training export, LoRA training, model selection, speaker adaptation | [PHASE_6.md](./plan_phases/PHASE_6.md) | Complete |
| 7 | SRT Edit bundle loading, word-level editing, timeline interaction upgrades | [PHASE_7.md](./plan_phases/PHASE_7.md) | Complete |
| 8 | SRT Edit markdown support and right-sidebar controls restructure | [PHASE_8.md](./plan_phases/PHASE_8.md) | Complete |
| 9 | SRT Gen script input, model management UI, bundle-from-SRT flow | [PHASE_9.md](./plan_phases/PHASE_9.md) | Complete |
| 10 | Caption Animator bundle input, markdown-to-ASS, new animations, output consolidation | [PHASE_10.md](./plan_phases/PHASE_10.md) | Complete |
| 11 | Refinement - 1 | [PHASE_11.md](./plan_phases/PHASE_11.md) | Pending |
| 12 | Final review, integration testing, architecture docs, release prep | [PHASE_12.md](./plan_phases/PHASE_12.md) | Pending |

## Recommended Execution Order

1. Complete [PHASE_1.md](./plan_phases/PHASE_1.md) before starting feature work in later phases.
2. Complete [PHASE_2.md](./plan_phases/PHASE_2.md) before shipping later render-path work in [PHASE_3.md](./plan_phases/PHASE_3.md), [PHASE_4.md](./plan_phases/PHASE_4.md), and [PHASE_10.md](./plan_phases/PHASE_10.md).
3. Complete [PHASE_5.md](./plan_phases/PHASE_5.md) before [PHASE_6.md](./plan_phases/PHASE_6.md).
4. Complete [PHASE_7.md](./plan_phases/PHASE_7.md) before [PHASE_8.md](./plan_phases/PHASE_8.md).
5. Complete [PHASE_9.md](./plan_phases/PHASE_9.md) before [PHASE_10.md](./plan_phases/PHASE_10.md) wherever bundle input or markdown rendering depends on the SRT Gen output path.
6. Complete [PHASE_11.md](./plan_phases/PHASE_11.md) after the major feature-delivery phases and before final release work in [PHASE_12.md](./plan_phases/PHASE_12.md).
7. Finish with [PHASE_12.md](./plan_phases/PHASE_12.md).

## Cross-Phase Dependency Map

- Bundle-first subtitle workflow: [PHASE_1.md](./plan_phases/PHASE_1.md) -> [PHASE_7.md](./plan_phases/PHASE_7.md) -> [PHASE_9.md](./plan_phases/PHASE_9.md) -> [PHASE_10.md](./plan_phases/PHASE_10.md)
- Render workflow: [PHASE_1.md](./plan_phases/PHASE_1.md) -> [PHASE_2.md](./plan_phases/PHASE_2.md) -> [PHASE_3.md](./plan_phases/PHASE_3.md) -> [PHASE_4.md](./plan_phases/PHASE_4.md) -> [PHASE_10.md](./plan_phases/PHASE_10.md)
- Advanced/training workflow: [PHASE_1.md](./plan_phases/PHASE_1.md) -> [PHASE_5.md](./plan_phases/PHASE_5.md) -> [PHASE_6.md](./plan_phases/PHASE_6.md)

## Usage

Use this file to navigate and understand cross-phase rules. Use each linked phase file for implementation details, file targets, success criteria, test expectations, and the required commit-and-push close-out work for every sub-phase.

## Completion Status

Audit refreshed on 2026-03-24 against the current implementation and research plan.

- Phases 1 through 10 are complete.
- Verification baseline: `.venv/bin/python -m pytest tests/ -q` passed with `1369` tests.
- Remaining work is tracked in Phases 11 and 12.
