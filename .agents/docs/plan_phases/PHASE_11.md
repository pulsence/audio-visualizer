# Phase 11: Refinement - 1

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 11.

This phase follows the same structure as the past User Debug phases: collect reported issues, record clarified decisions and findings, then map the work into concrete implementation subphases before final release review.

## Reported Changes to Make

Every item in this section is in scope for Phase 11 and must map to one of the implementation subphases below. Each item should end with automated regression coverage or an explicit manual verification note when the behavior is difficult to exercise in tests.

- General
  - THERE IS TO BE NO MIGRATION CODE. All the migration and versioning code added in Phase 1 for the json bundles must be removed
    and bundles are not to be versioned.
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

## Phase 11 Planning Notes

- Record clarified product decisions, scope cuts, and verification requirements here as reported issues are triaged.
- Preserve the contracts from Phases 1-10 unless this phase explicitly replaces them.
- For pointer-heavy, playback-heavy, or FFmpeg-heavy fixes that are difficult to assert fully in tests, add a brief manual verification checklist in addition to targeted automated coverage.

## Phase 11 Resolved Findings

- Record investigation outcomes and implementation decisions here before or while breaking the work into subphases.
- Convert ambiguous reports into repo-backed concrete tasks before implementation begins.

### 11.1: General and Cross-Workflow Fixes

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

### 11.2: Workflow Screen Fixes

Address reported refinement issues for Audio Visualizer, SRT Gen, and SRT Edit.

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

### 11.3: Caption, Composition, and Render Pipeline Fixes

Address reported refinement issues for Caption Animate, Render Composition, and any shared rendering pipeline behavior touched by the reported fixes.

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

### 11.4: Phase 11 Code Review

**Tasks:**
- Review the changes and ensure the phase is entirely implemented.
- Review code for deprecated code or dead code.
- Review tests to ensure they are well-structured.
- Verify the refinement fixes did not weaken existing v0.7.0 guarantees, especially cross-tab integration, session behavior, and shared-worker/render behavior.

**Files:**
- Phase 11 implementation files
- Phase 11 tests

**Phase 11 Changelog:**
- Added a dedicated refinement phase immediately after Phase 10 and before final release review.
- Structured Phase 11 to follow the repo's past User Debug phase format: reported changes, planning notes, resolved findings, implementation subphases, and code review.
- Reserved explicit slots for cross-workflow fixes, workflow-screen fixes, and caption/composition/render fixes driven by reported refinement items.
