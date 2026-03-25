# Phase 13: Refinement - 3

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 13.

This phase exists to capture any third-wave refinement issues discovered after Phase 12 verification and before final release review.

## Reported Changes to Make

Every item in this section is in scope for Phase 13 and must map to one of the implementation subphases below. Each item should end with automated regression coverage or an explicit manual verification note when the behavior is difficult to exercise in tests.

- General
  - Add reported general refinement items here.
- Audio Visualizer Screen
  - Add reported Audio Visualizer refinement items here.
- SRT Gen Screen
  - Add reported SRT Gen refinement items here.
- SRT Edit Screen
  - Add reported SRT Edit refinement items here.
- Caption Animate Screen
  - Add reported Caption Animate refinement items here.
- Render Composition
  - Add reported Render Composition refinement items here.
- Advanced / Assets / Shared Infrastructure
  - Add reported Advanced tab, Assets tab, session, queue, persistence, or worker refinement items here.

## Phase 13 Planning Notes

- Preserve the contracts from Phases 1-12 unless this phase explicitly replaces them.
- Use this phase only for issues that are discovered after Phase 12 verification or that were intentionally deferred out of Phase 12 scope.
- If a Phase 13 item overrides a decision made in earlier refinement phases, record that override explicitly in the resolved findings before implementation starts.
- For pointer-heavy, playback-heavy, or FFmpeg-heavy fixes that are difficult to assert fully in tests, add a brief manual verification checklist in addition to targeted automated coverage.

## Phase 13 Resolved Findings

- Record investigation outcomes and implementation decisions here before or while breaking the work into subphases.
- Convert ambiguous reports into repo-backed concrete tasks before implementation begins.

### 13.1: General and Cross-Workflow Fixes

**Tasks:**
1. Triage and implement the General and Advanced / Assets / Shared Infrastructure items listed above.
2. Ensure the fixes preserve the shared implementation rules in the main plan index and do not regress the phase contracts already delivered.
3. Add automated regression coverage where practical and explicit manual verification notes where full automation is not realistic.
4. Run tests: `pytest tests/ -v`.
5. Update `.agents/docs/` architecture documentation as needed.
6. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify the relevant shared UI, persistence, asset, worker, documentation, and test files.

**Success criteria:** All reported general and cross-workflow refinement items assigned to this subphase are resolved without weakening the shared app-shell, session, or background-job contracts established earlier in the plan.

### 13.2: Workflow Screen Fixes

**Tasks:**
1. Triage and implement the Audio Visualizer Screen, SRT Gen Screen, and SRT Edit Screen items listed above.
2. Keep the fixes aligned with the shared bundle-first, queue, playback, and persistence behavior where applicable.
3. Add automated regression coverage where practical and explicit manual verification notes where full automation is not realistic.
4. Run tests: `pytest tests/ -v`.
5. Update `.agents/docs/` architecture documentation as needed.
6. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify the relevant tab, view-model/document, worker, documentation, and test files.

**Success criteria:** All reported workflow-screen refinement items assigned to this subphase are resolved, and the affected tabs behave consistently with the v0.7.0 workflow contracts established in earlier phases.

### 13.3: Caption, Composition, and Render Pipeline Fixes

**Tasks:**
1. Triage and implement the Caption Animate Screen and Render Composition items listed above, plus any linked shared render-pipeline fixes they require.
2. Preserve the shared render-queue, asset-registration, and output-contract behavior already defined in the main plan.
3. Add automated regression coverage where practical and explicit manual verification notes where full automation is not realistic.
4. Run tests: `pytest tests/ -v`.
5. Update `.agents/docs/` architecture documentation as needed.
6. Commit following `COMMIT_MESSAGE.md` format and then push.

**Files:**
- Modify the relevant caption, composition, worker, shared rendering, documentation, and test files.

**Success criteria:** All reported caption/composition/render refinement items assigned to this subphase are resolved without regressing the shared render pipeline, output handoff, or downstream integration paths.

### 13.4: Phase 13 Code Review

**Tasks:**
1. Review the changes and ensure the phase is entirely implemented.
2. Review code for deprecated code or dead code.
3. Review tests to ensure they are well-structured.
4. Verify the refinement fixes did not weaken existing v0.7.0 guarantees, especially cross-tab integration, session behavior, and shared-worker/render behavior.
5. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 13 implementation files
- Phase 13 tests

**Success criteria:** The third refinement pass closes all newly reported issues without regressing the v0.7.0 guarantees already stabilized in the earlier refinement phases.

### 13.5: Phase 13 Changelog

**Tasks:**
1. Summarize the new issues resolved in this third refinement pass.
2. Record any Phase 13 decisions that superseded or narrowed Phase 11 or Phase 12 implementation assumptions.
3. Commit and push any documentation-only cleanup from this sub-phase.

**Files:**
- Phase 13 implementation notes

**Success criteria:** The project has a dedicated third refinement log before final review and release-preparation work begins.
