# Phase 7: SRT Edit — Bundle Loading and Word-Level Editing

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 7.

Implement bundle loading, word-level timeline editing, inline word rows, and timeline interaction improvements.

### 7.1: Bundle Loading in SRT Edit

Load normalized JSON bundles into the SRT Edit document model and preserve them on save.

**Tasks:**
1. Update SRT Edit load flows to accept `.json` and `.bundle.json`.
2. Use `read_json_bundle()` as the only bundle entry point.
3. Populate `SubtitleEntry` objects with words and provenance fields.
4. Update asset pickers to show both subtitle assets and bundle assets.
5. Add a "Save Bundle" flow that preserves word timing and metadata through bundle v2.
6. Add an "Export SRT" flow that emits plain subtitle output without bundle-only metadata.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEditTab.py`
- `src/audio_visualizer/ui/tabs/srtEdit/parser.py`
- `src/audio_visualizer/srt/io/outputWriters.py`

**Success criteria:** SRT Edit can round-trip bundle-backed documents with word timing and provenance, while still exporting plain SRT when requested.

**Close-out:** Add or update tests for SRT Edit bundle load/save/export behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if bundle-editing behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.2: Word-Level Timeline View

Display and edit word regions directly on the waveform timeline.

**Tasks:**
1. Add a segment-versus-word view toggle to the waveform UI.
2. In word view, render a `LinearRegionItem` per visible word.
3. Style word regions distinctly from segment regions.
4. Clamp word boundaries within their parent segment and against neighboring words.
5. Update word-region bounds when the parent segment changes.
6. Allow dragging word regions to change timing.
7. Push timing changes back into the document model.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`

**Success criteria:** Word regions appear inside their parent segments, drag interactions respect segment and neighbor bounds, and timing changes update the underlying document state.

**Close-out:** Add or update tests for word-region constraints and model synchronization, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if waveform behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.3: Word-Level Table Editing

Add inline word rows to the subtitle table.

**Tasks:**
1. Add expand/collapse support per subtitle row in `SubtitleTableModel`.
2. Insert inline word rows below the parent subtitle row with visual indentation.
3. Show word text, start time, and end time in the word rows.
4. Make word text editable inline.
5. Maintain a stable mapping from displayed table rows back to subtitle-row and word-row indices.
6. Add undo commands for word text edits and word timing edits.
7. Sync selection between word rows and timeline word regions.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/tableModel.py`
- `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- `src/audio_visualizer/ui/tabs/srtEditTab.py`

**Success criteria:** Users can expand a subtitle row to edit word rows inline, undo those edits, and see table selection synchronized with the timeline.

**Close-out:** Add or update tests for row mapping, inline editing, and undo behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if table-model behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.4: Timeline Segment Border Expansion on Hover

Make region boundaries easier to grab.

**Tasks:**
1. Subclass the relevant region item behavior so hover state can widen the visual boundary.
2. Increase the line width on hover.
3. Restore the normal width on hover leave.
4. Apply the same affordance to both segment and word regions.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`

**Success criteria:** Hovering any editable segment or word boundary visibly increases the grab affordance without permanently changing non-hovered items.

**Close-out:** Add or update tests for hover-state visuals where practical, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if timeline interaction changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.5: Pan-to-Segment Instead of Zoom

Change row selection behavior so the timeline pans first and zooms only when needed.

**Tasks:**
1. Update `highlight_region()` to preserve the current zoom level when the selected segment fits in view.
2. Center the segment in the current viewport when it fits.
3. Only zoom out when the segment is wider than the visible window.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`

**Success criteria:** Selecting a segment keeps the current zoom when possible and only zooms when necessary to reveal an oversized segment.

**Close-out:** Add or update tests for pan-versus-zoom behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if timeline navigation changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.6: Split at Playhead and Context Menus

Add playhead-aware splitting and contextual editing actions to both timeline and table.

**Tasks:**
1. Update split behavior so it uses the playhead when the playhead is inside the selected segment and falls back to midpoint otherwise.
2. Add matching context menus to timeline regions and table rows.
3. Expose Split at Playhead, Merge with Next, Merge with Previous, Delete Segment, and Edit Text actions.
4. Route those actions through existing undoable command paths.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEditTab.py`
- `src/audio_visualizer/ui/tabs/srtEdit/commands.py`
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`

**Success criteria:** Users can trigger the same segment actions from both the timeline and table, and split-at-playhead honors the playhead when the segment contains it.

**Close-out:** Add or update tests for context menus and split-at-playhead behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if action flow changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.7: Drag-to-Select for New Segment Creation

Allow new subtitle creation from empty timeline drags.

**Tasks:**
1. Detect drags in empty waveform space.
2. Show a temporary selection region during the drag.
3. Keep the selection visible after mouse release.
4. Add a right-click menu offering Create Blank Segment and Create Segment from Clipboard.
5. Insert the new segment through the normal undoable add-entry path.
6. Dismiss the temporary selection on Escape or click-away.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- `src/audio_visualizer/ui/tabs/srtEditTab.py`

**Success criteria:** Users can drag out a region on empty waveform space and convert it into a new segment through the context menu without bypassing normal document ordering and undo behavior.

**Close-out:** Add or update tests for drag-to-select creation and selection dismissal behavior, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if waveform creation behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.8: Segment Overlap Prevention and Auto-Ordering

Keep subtitle and word timing ordered and non-overlapping.

**Tasks:**
1. Insert new subtitle entries in sorted order.
2. Re-sort and re-index entries after timestamp edits when needed.
3. Clamp segment drags so they cannot overlap neighboring segments.
4. Apply the same clamping rules to word edits inside each segment.

**Files:**
- `src/audio_visualizer/ui/tabs/srtEdit/document.py`
- `src/audio_visualizer/ui/tabs/srtEdit/waveformView.py`
- `src/audio_visualizer/ui/tabs/srtEditTab.py`

**Success criteria:** Neither subtitle segments nor words can be dragged into overlapping, invalid order, and newly created segments land in the correct sorted position automatically.

**Close-out:** Add or update tests for sorting and overlap prevention, run the relevant tests and `pytest tests/ -v` when shared SRT Edit behavior changed, update `.agents/docs/architecture/` docs if document-ordering rules changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 7.9: Phase 7 Review

**Tasks:**
1. Review bundle load/save behavior, word timeline editing, inline word rows, and timeline interaction changes together.
2. Remove temporary adapters or duplicate word-editing paths that bypass the normalized bundle/document contract.
3. Verify tests cover both timeline and table editing paths.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 7 implementation files
- Phase 7 tests

**Success criteria:** SRT Edit supports bundle-backed word-level editing through one coherent document model and one coherent undo model.

### 7.10: Phase 7 Changelog

**Tasks:**
1. Summarize bundle-backed editing, word-level UI, and interaction changes added in Phase 7.
2. Note any document or undo-stack rules Phase 8 must preserve.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 7 implementation notes

**Success criteria:** The markdown and sidebar work in Phase 8 can build directly on the finalized word-level editing model.
