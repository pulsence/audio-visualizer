# Phase 11: Final Review and Release Preparation

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 11.

Finish the release with a full review, documentation updates, and version bump.

### 11.1: Final Code Review

**Tasks:**
1. Review all phases in this plan and ensure there are no feature gaps, regressions, or forgotten compatibility shims.
2. Review new modules for logging, error handling, and cleanup behavior.
3. Review the test suite for missing coverage, auto-pass tests, or poor module-to-test alignment.
4. Remove dead code or temporary scaffolding that is no longer needed.
5. Commit and push changes for this sub-phase.

**Files:**
- All modified source files
- All modified tests

**Success criteria:** The v0.7.0 implementation is internally consistent, free of obvious regressions, and no longer depends on temporary scaffolding or dead code paths.

### 11.2: Integration Testing

**Tasks:**
1. Run the full suite with `pytest tests/ -v`.
2. Fix any remaining failures.
3. Re-run the full suite until it passes cleanly.
4. Commit and push changes for this sub-phase.

**Files:**
- All affected test and source files

**Success criteria:** The full repository test suite passes against the completed v0.7.0 implementation.

### 11.3: Architecture Documentation Update

**Tasks:**
1. Update `.agents/docs/architecture/` to match the delivered code.
2. Update `ARCHITECTURE.md`.
3. Update `INDEX.md` so it reflects the Advanced tab, new training modules, bundle flow, and any new shared rendering infrastructure.
4. Commit and push changes for this sub-phase.

**Files:**
- `.agents/docs/architecture/`
- `.agents/docs/ARCHITECTURE.md`
- `.agents/docs/INDEX.md`

**Success criteria:** The repo documentation accurately reflects the v0.7.0 architecture and workflow changes.

### 11.4: Release Preparation

**Tasks:**
1. Update `readme.md` for v0.7.0 behavior and workflow changes.
2. Update the package version to `0.7.0` in `pyproject.toml`.
3. Update the version constant in `src/audio_visualizer/__init__.py`.
4. Run the final full test suite with `pytest tests/ -v`.
5. Commit and push changes for this sub-phase.

**Files:**
- `readme.md`
- `pyproject.toml`
- `src/audio_visualizer/__init__.py`

**Success criteria:** The codebase, docs, and package metadata all reflect v0.7.0 and are ready for release.
