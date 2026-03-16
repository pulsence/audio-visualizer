# Phase 10: Final Review

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 10.1: Code Review

Perform a final code-quality and regression review across the full Stage Three implementation before final documentation and release work.

**Tasks:**
- Review all phases in this plan and ensure there are no gaps or bugs remaining in the implementation
- Review all changes for unintended regressions
- Review for deprecated code, dead code, or legacy compatibility shims and remove them
- Review all new modules for proper error handling, cancellation safety, and logging
- Review the full test suite:
  - No auto-pass tests
  - Test structure matches the new module structure
  - All new features have tests
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Potentially modify any files changed in Phases 1-9, especially under `src/audio_visualizer/`, `tests/`, and `.agents/docs/`

**Success criteria:** No known Stage Three implementation gaps remain, and the multi-tab app is ready for the final test/documentation/release pass.

### 10.2: Integration Testing

Run the full regression and integration pass against the completed Stage Three application.

**Tasks:**
- Run all existing tests: `pytest tests/ -v`
- Verify no pre-existing tests regressed on the new Qt dependency lane
- Verify the full Stage Three integration coverage passes in the same suite run
- Verify the multi-tab application launches and all tabs instantiate successfully in the project environment
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- No new files planned; if regressions are found, modify the affected files under `src/audio_visualizer/` and `tests/`

**Success criteria:** The full test suite passes and the multi-tab application starts successfully with all Stage Three tabs and worker flows intact.

### 10.3: Architecture Documentation Update

**Tasks:**
- Update `ARCHITECTURE.md` to reflect the tab-based app structure, `SessionContext`, worker architecture, and new persistence model
- Update `INDEX.md` to reference the new Stage Three UI architecture and any new package docs
- Update `.agents/docs/architecture/development/OVERVIEW.md` with the new end-to-end tab workflow
- Update `.agents/docs/architecture/development/UI.md` for the new `MainWindow`, tab classes, shared status shell, and undo/menu behavior
- Update `.agents/docs/architecture/development/RENDERING.md` for the new worker model, cancel boundaries, caption rendering, and composition rendering
- Update `.agents/docs/architecture/development/TESTING.md` for the new Qt/widget/integration coverage
- Add or update package docs for any new `ui` subpackages introduced by Stage Three
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `.agents/docs/ARCHITECTURE.md`
- Modify `.agents/docs/INDEX.md`
- Modify `.agents/docs/architecture/development/OVERVIEW.md`
- Modify `.agents/docs/architecture/development/UI.md`
- Modify `.agents/docs/architecture/development/RENDERING.md`
- Modify `.agents/docs/architecture/development/TESTING.md`
- Potentially create additional package docs under `.agents/docs/architecture/packages/`

**Success criteria:** The architecture docs accurately describe the Stage Three codebase and workflow model.

### 10.4: Release Preparation

**Tasks:**
- Update `readme.md` to reflect the new multi-tab workflow, SRT editing, caption animation, render composition, and workflow-recipe features
- Align version strings across `pyproject.toml`, `src/audio_visualizer/__init__.py`, and `readme.md` for the Stage Three release number
- Run final full test suite: `pytest tests/ -v`
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `pyproject.toml`
- Modify `src/audio_visualizer/__init__.py`
- Modify `readme.md`

**Success criteria:** Release-facing documentation and version strings match the completed Stage Three feature set, and the final full test suite passes.
