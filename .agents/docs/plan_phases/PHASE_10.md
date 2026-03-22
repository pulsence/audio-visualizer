# Phase 10: Caption Animator — Bundle Input, Markdown, and New Animations

[Back to Plan Index](../v_0_7_0_PLAN.md)

Follow the shared implementation rules in the main plan index. This file contains the detailed execution steps for Phase 10.

Make Caption Animator fully bundle-aware, markdown-aware, and aligned with the new output handoff strategy.

### 10.1: JSON Bundle Input

Allow Caption Animator to load bundle v2 files directly.

**Tasks:**
1. Add a bundle-loading entry point to caption subtitle loading.
2. Use `read_json_bundle()` as the only bundle reader.
3. Accept bundle files in the Caption Animator file picker.
4. Feed precise bundle word timing into word-aware animations.
5. For plain subtitle input, fall back to estimated timing and mark word-level animation quality accordingly in the UI.

**Files:**
- `src/audio_visualizer/caption/core/subtitle.py`
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- `src/audio_visualizer/srt/io/bundleReader.py`

**Success criteria:** Caption Animator can load bundle files directly, use real word timing when available, and fall back gracefully when only plain subtitle timing exists.

**Close-out:** Add or update tests for bundle loading and timing fallback behavior, run the relevant tests and `pytest tests/ -v` when shared caption or bundle behavior changed, update `.agents/docs/architecture/` docs if subtitle-input behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.2: Markdown-to-ASS Conversion

Convert markdown source styling into ASS override tags at render time.

**Tasks:**
1. Create a `markdown_to_ass()` conversion helper in the caption core.
2. Convert `**bold**` and `*italic*` to ASS override tags at render time.
3. Preserve `==highlight==` markers for animation targeting rather than turning them into static ASS styling too early.
4. Handle nested markers correctly.
5. Update word-aware animation tokenization so it strips ASS tags before tokenization and re-injects styling in the output.
6. Update existing word-aware animations such as `word_reveal`, `pulse`, `beat_pop`, and `emphasis_glow` to use the ASS-aware tokenization path.

**Files:**
- `src/audio_visualizer/caption/core/markdownToAss.py`
- `src/audio_visualizer/caption/rendering/ffmpegRenderer.py`
- `src/audio_visualizer/caption/animations/wordRevealAnimation.py`
- `src/audio_visualizer/caption/animations/`

**Success criteria:** Markdown source text renders correctly as styled ASS output without breaking word-based animation tokenization or highlight targeting.

**Close-out:** Add or update tests for markdown conversion and ASS-aware tokenization, run the relevant tests and `pytest tests/ -v` when shared caption text behavior changed, update `.agents/docs/architecture/` docs if caption text-processing behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.3: Word Highlight Animation

Add a word highlight animation plugin.

**Tasks:**
1. Create `wordHighlightAnimation.py` and register it.
2. Generate per-word ASS events with highlight color, scale, and blur styling.
3. Support `even`, `weighted`, and `word_level` timing modes.
4. Treat `==word==` markers as explicit emphasis targets.
5. Add UI controls for the new animation parameters.

**Files:**
- `src/audio_visualizer/caption/animations/wordHighlightAnimation.py`
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`

**Success criteria:** Caption Animator can highlight words one by one using either estimated or real word timing, and explicit `==...==` markup receives stronger emphasis treatment.

**Close-out:** Add or update tests for word highlight timing modes and marker handling, run the relevant tests and `pytest tests/ -v` when shared caption animation behavior changed, update `.agents/docs/architecture/` docs if animation capabilities changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.4: Typewriter Animation

Add a typewriter animation plugin.

**Tasks:**
1. Create `typewriterAnimation.py` and register it.
2. Reveal text character by character using ASS timing constructs.
3. Add cursor character and blink timing options.
4. Add UI controls for the new animation parameters.

**Files:**
- `src/audio_visualizer/caption/animations/typewriterAnimation.py`
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`

**Success criteria:** Caption Animator can render a configurable typewriter effect with a blinking cursor and user-controlled reveal speed.

**Close-out:** Add or update tests for typewriter timing and cursor behavior, run the relevant tests and `pytest tests/ -v` when shared caption animation behavior changed, update `.agents/docs/architecture/` docs if animation capabilities changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.5: Render Output Consolidation

Make the MP4 the primary output and keep overlay export optional.

**Tasks:**
1. Change the default caption-render handoff so the user-facing MP4 is the main output artifact.
2. Make transparent overlay output optional behind an advanced checkbox, defaulting off.
3. Register the MP4 as the first-class reusable session asset.
4. Keep any optional overlay artifact clearly labeled as an advanced composition helper.
5. Update the render worker if needed so output-path handling, asset registration, and cleanup all match the new output priority.

**Files:**
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- `src/audio_visualizer/ui/workers/captionRenderWorker.py`

**Success criteria:** A normal caption render produces and registers the MP4 as the primary reusable output, while overlay output remains optional and clearly advanced.

**Close-out:** Add or update tests for output selection and asset registration, run the relevant tests and `pytest tests/ -v` when shared caption render behavior changed, update `.agents/docs/architecture/` docs if output-handling behavior changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.6: Render Queue Alignment

Keep caption renders aligned with the shared app render queue.

**Tasks:**
1. Verify the caption render worker holds the shared render-thread slot for the full FFmpeg runtime.
2. Add a shared render queue status indicator visible across tabs.
3. Make sure queue reporting names the active tab or job and reflects idle state cleanly.

**Files:**
- `src/audio_visualizer/ui/tabs/captionAnimateTab.py`
- `src/audio_visualizer/ui/workers/captionRenderWorker.py`
- `src/audio_visualizer/ui/mainWindow.py`

**Success criteria:** Render jobs remain serialized across tabs and the app clearly reports whether the shared render queue is busy or idle.

**Close-out:** Add or update tests for queue-state reporting where practical, run the relevant tests and `pytest tests/ -v` when shared render-queue behavior changed, update `.agents/docs/architecture/` docs if render orchestration changed, then `git add`, commit with the required `COMMIT_MESSAGE.md` format, and `git push`.

### 10.7: Phase 10 Review

**Tasks:**
1. Review bundle input, markdown conversion, new animations, output handling, and queue behavior together.
2. Remove any duplicate subtitle-loading or output-registration logic replaced by the new bundle-first path.
3. Verify tests cover both word-aware and fallback subtitle timing paths.
4. Commit and push any cleanup changes from this sub-phase.

**Files:**
- Phase 10 implementation files
- Phase 10 tests

**Success criteria:** Caption Animator cleanly participates in the bundle-first workflow and hands off a primary MP4 artifact without conflicting output paths.

### 10.8: Phase 10 Changelog

**Tasks:**
1. Summarize bundle input, markdown rendering, animation additions, output consolidation, and queue updates from Phase 10.
2. Call out the rule that the MP4 is the default handoff artifact and the overlay is optional.
3. Commit and push any documentation updates from this sub-phase.

**Files:**
- Phase 10 implementation notes

**Success criteria:** The release can describe Caption Animator as fully aligned with the v0.7.0 bundle-first and MP4-first workflow.
