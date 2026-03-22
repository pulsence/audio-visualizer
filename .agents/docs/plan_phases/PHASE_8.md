# Phase 8: SRT Edit — Markdown Styling and Controls Restructure

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 8.

Add markdown-aware editing and move the tab's controls into the right sidebar.

### 8.1: Markdown Syntax Highlighting in SRT Edit

Add markdown-aware editing visuals to SRT Edit text inputs.

**Tasks:**
1. Create a markdown syntax highlighter for `**bold**`, `*italic*`, and `==highlight==`.
2. Apply the highlighter to the in-table text editor.
3. Reuse the same highlighter for the sidebar editor added later in this phase.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/markdownHighlighter.py`
- `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`

**Success criteria:** SRT Edit text entry surfaces markdown intent clearly while preserving the underlying raw markdown source.

**Close-out:** Add or update tests for markdown highlighting where practical, run the relevant tests and `pytest tests/ -v` when shared SRT Edit text-edit behavior changed, update `.agents/docs/architecture/` docs if editing behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 8.2: Controls Layout Restructure

Move the bottom toolbars into the existing right sidebar.

**Tasks:**
1. Move playback, edit, and resync controls into the right sidebar.
2. Organize the sidebar into clear sections for playback, edit, resync, and QA/lint.
3. Add a sidebar `QPlainTextEdit` for the selected segment's text and apply the markdown highlighter to it.
4. Keep the sidebar editor bidirectionally synchronized with table/document selection and editing.
5. Remove the old bottom toolbars.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEditTab.py`
- `src/audio_visualizer/ui/tabs/srtEdit/markdownHighlighter.py`

**Success criteria:** All SRT Edit controls live in the right sidebar, the selected segment can be edited there with markdown awareness, and the old bottom toolbars are gone.

**Close-out:** Add or update tests for sidebar control wiring and editor synchronization where practical, run the relevant tests and `pytest tests/ -v` when shared SRT Edit UI changed, update `.agents/docs/architecture/` docs if the tab layout changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 8.3: Markdown Preservation in Bundle I/O and SRT Export

Make markdown round-trip correctly through the bundle path and configurable through SRT export.

**Tasks:**
1. Verify bundle v2 save/load preserves markdown source text exactly.
2. Add a markdown-stripping helper for plain-text SRT export.
3. Offer a user choice for SRT export: preserve markdown markers or strip them.
4. Keep markdown-to-ASS conversion deferred to Caption Animator instead of pre-rendering styled text into bundle storage.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/parser.py`
- `src/audio_visualizer/srt/io/bundleReader.py`
- `src/audio_visualizer/srt/io/outputWriters.py`

**Success criteria:** Markdown round-trips through bundle save/load untouched, and SRT export can either preserve or remove markdown markers intentionally.

**Close-out:** Add or update tests for markdown preservation and stripping behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit or bundle behavior changed, update `.agents/docs/architecture/` docs if text-format rules changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 8.4: Phase 8 Review

**Tasks:**
1. Review markdown highlighting, sidebar editing, and export behavior together.
2. Remove any duplicate text-edit widgets or dead toolbar code replaced by the sidebar.
3. Verify tests cover both markdown storage and markdown-aware editing behavior.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 8 implementation files
- Phase 8 tests

**Success criteria:** SRT Edit now has one coherent markdown-aware editing path and one coherent layout.

### 8.5: Phase 8 Changelog

**Tasks:**
1. Summarize markdown editing and sidebar layout changes added in Phase 8.
2. Call out the rule that markdown stays as source text until Caption Animator render time.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 8 implementation notes

**Success criteria:** Later caption work can rely on markdown being preserved as source text all the way out of SRT Edit.

---

## Phase 8 Completion Summary

All sub-phases (8.1 through 8.5) are complete.

### Changes Delivered

**8.1 — Markdown Syntax Highlighting:**
- Created `markdownHighlighter.py` with `MarkdownHighlighter` (QSyntaxHighlighter) supporting `**bold**`, `*italic*`, `==highlight==`.
- Applied to in-table `MultilineTextDelegate` editor and sidebar segment editor.
- Delimiter characters rendered in subdued colour; content gets full visual treatment.
- Bold detection takes priority over italic to avoid false matches on `**` delimiters.

**8.2 — Controls Layout Restructure:**
- Moved all playback, edit, save/export, and resync controls into the right sidebar.
- Sidebar organized into QGroupBox sections: Segment Text, Playback, Edit, Save/Export, Resync, QA/Lint.
- Added sidebar `QPlainTextEdit` for selected segment text with `MarkdownHighlighter` attached.
- Bidirectional sync: selecting a table row loads the text; editing in the sidebar pushes undo commands back to the document and table.
- Removed old bottom toolbars (`_resync_toolbar`, `controls_layout`) and unused imports.

**8.3 — Markdown Preservation in Bundle I/O and SRT Export:**
- Verified bundle v2 save/load preserves markdown text exactly (including `original_text` field).
- Added `strip_markdown()` helper in `parser.py` for plain-text export.
- `write_srt_file` and `document.save_srt` accept `strip_md` parameter.
- Export dialog asks user whether to strip or preserve markdown markers.
- Markdown-to-ASS conversion is deferred to Caption Animator (not pre-rendered into bundle storage).

**8.4 — Review:**
- Removed dead toolbar code and unused imports.
- Verified all 1219 tests pass with zero failures.

### Key Design Rule
**Markdown stays as source text until Caption Animator render time.** The SRT Edit tab stores `**bold**`, `*italic*`, and `==highlight==` as literal markdown in the document and bundle. The highlighter provides visual feedback only. Stripping happens exclusively at the SRT/VTT export boundary when the user requests it. Caption Animator is responsible for converting markdown to ASS styling at render time.

### Test Coverage
70 tests in `test_ui_srt_edit_tab.py` covering:
- Markdown highlighting (bold, italic, highlight, mixed, nested, delegate integration)
- Sidebar editor sync (selection, text changes, undo, grouped controls)
- Markdown stripping (all patterns, mixed, nested, empty string)
- Bundle round-trip (markdown preserved in text and original_text)
- SRT export (with strip, without strip, document-level save_srt)
