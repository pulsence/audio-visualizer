# Phase 7: Workflow Recipes and Cross-Tab Integration Polish

**Parent plan:** [PLAN_3.md](../PLAN_3.md)

This phase file is extracted from the Stage Three implementation plan. Shared target-state details, contracts, and cross-phase rules remain defined in [PLAN_3.md](../PLAN_3.md).

### 7.1: Add workflow recipes as a separate versioned artifact

Recipes are reusable workflow templates, not project saves, so they need their own schema, storage, and import/export flow.

**Tasks:**
- Create a versioned recipe schema that stores enabled stages, per-tab settings subsets, asset-role expectations, output naming rules, and references to presets/layouts/lint profiles, using the concrete structure from the "Workflow recipe schema" section above
- Store the recipe library under the app config/data area rather than in the repo root
- Support recipe import/export as explicit `.avrecipe.json` files
- Add "save recipe" and "apply recipe" flows at the shell level and in relevant tabs
- Resolve asset roles through `SessionContext` first, then fall back to filesystem prompts when bindings are missing
- Keep recipes distinct from project save/load artifacts and auto-saved last-session settings
- Exclude transient UI state from recipes just as with normal settings saves: recipes should capture workflow intent, not the user's last zoom level, current playback position, or in-progress output temp paths
- Create/update tests for recipe round-trip, versioning, import/export, asset-role resolution, and missing-binding handling
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create `src/audio_visualizer/ui/workflowRecipes.py`
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/settingsSchema.py`
- Modify relevant tab files under `src/audio_visualizer/ui/tabs/`
- Create `tests/test_workflow_recipes.py`

**Success criteria:** Recipes can be saved, imported, exported, and applied as reusable workflow templates without being confused with project files or machine-local autosaves.

### 7.2: Finish cross-tab workflow and status UX

Once all five tabs exist, the shell and tabs need a final integration pass so the application feels like one coherent workflow rather than five separate tools sharing a window.

**Tasks:**
- Finish session-aware file pickers across all tabs so users can choose between current-session assets and raw filesystem paths consistently
- Add explicit handoff actions between tabs for common flows such as SRT Gen -> SRT Edit, SRT Edit -> Caption Animate, and Caption Animate/Audio Visualizer -> Composition
- Polish the shared status area, tab badges, busy-state messaging, and completion notifications now that all long-running job types exist
- Ensure the shared analysis cache invalidates correctly when source assets or relevant analysis settings change
- Review render-preview behavior across all render-producing tabs and keep `RenderDialog` invocation consistent
- Create/update integration tests for cross-tab handoff flows, busy-state behavior, and shared-status updates
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Modify `src/audio_visualizer/ui/mainWindow.py`
- Modify `src/audio_visualizer/ui/jobStatusWidget.py`
- Modify relevant files under `src/audio_visualizer/ui/tabs/`
- Modify `src/audio_visualizer/ui/sessionContext.py`
- Create `tests/test_ui_integration.py`

**Success criteria:** Cross-tab asset handoff feels intentional, users retain visibility into background work from anywhere in the app, and the Stage Three workflow operates like a unified production pipeline.

### 7.3: Add end-to-end migration and integration coverage

Before final review, Stage Three needs test coverage for the new whole-app behaviors that do not fit inside any one tab's unit tests.

**Tasks:**
- Add integration tests for loading old Audio Visualizer-only settings into the new multi-tab schema
- Add end-to-end session-flow tests covering SRT Gen output registration, SRT Edit reuse, Caption Animate render registration, and Composition consumption
- Add workflow-recipe application tests that bind asset roles into a populated `SessionContext`
- Add regression coverage for shared undo-action rebinding, shared busy-state blocking, and completion notifications
- Run tests: `pytest tests/ -v`
- Update `.agents/docs/` architecture documentation as needed
- Commit following `COMMIT_MESSAGE.md` format and then push

**Files:**
- Create or modify `tests/test_ui_integration.py`
- Create or modify `tests/test_ui_settings_schema.py`
- Create or modify `tests/test_workflow_recipes.py`

**Success criteria:** The repo has automated coverage for the Stage Three migration path and the most important cross-tab workflows, not just isolated tab widgets.

### 7.4: Phase 7 Code Review

- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured
- Verify recipes remain separate from project saves and that cross-tab workflows use `SessionContext` consistently

**Phase 7 Changelog:**
- Added versioned workflow recipes with import/export and asset-role resolution
- Polished cross-tab workflow, status, and handoff UX
- Added end-to-end migration and integration coverage for the multi-tab app
