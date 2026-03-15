# Creating a Research Plan

This document defines how to create research plans for Audio Visualizer feature development. Research plans are deep-dive explorations that thoroughly describe the current codebase state, design options, and trade-offs for a set of proposed changes. They are descriptive documents — they document realities and present options, they do not prescribe scope or make implementation decisions on the user's behalf.

## When to Create a Research Plan

A research plan is created when the user asks for one explicitly (e.g., "create a research plan for vX.Y.Z"). The output is saved to `.agents/future_plans/v_X_Y_Z_RESEARCH_PLAN.md` — this is a living document that the user iterates on before producing a task plan via [CREATE_IMPLEMENTATION_PLAN.md](./CREATE_IMPLEMENTATION_PLAN.md).

When a research plan is superseded (a new version's plan replaces it), move the old file to `.agents/docs/past_plans/` with a versioned filename (e.g., `v_0_6_0_RESEARCH_PLAN.md`).

## Core Principles

1. **Describe realities, don't prescribe solutions.** A research plan documents what the code does today, identifies problems and gaps factually, and presents design options with trade-offs. It does NOT assert what is or isn't in scope — that is the user's decision.

2. **Ground every claim in the codebase.** Reference specific files, classes, functions, and data flows. Include code snippets or signatures where they clarify the design. A research plan without code-level detail cannot produce an accurate implementation plan.

3. **Present options, not conclusions.** When there are design choices, document all reasonable alternatives with pros, cons, and trade-offs. Use tables to compare options across multiple dimensions. The user chooses — the plan informs.

4. **Leave scope decisions as clarification questions.** If a topic could reasonably be included or excluded from the version, don't decide — ask. Put scope and priority questions in the Clarifications Required section.

5. **Be thorough.** Each topic area should be explored in enough depth that someone could write an implementation plan from the research alone. Shallow descriptions that gloss over details or leave the reader guessing defeat the purpose.

## Research Plan Structure

### Title

```markdown
# vX.Y.Z Topic Name — Research Plan
```

### Overview

A concise summary of the areas of work being researched and any important constraints or context. This section answers: *What topics does this plan explore and what is the context behind them?*

If there are constraints that affect the entire plan, state them here:

```markdown
> **Breaking Release**: vX.Y.Z is a breaking release. Settings format changes
> are unconstrained — there is no obligation to maintain backward compatibility.
```

### Numbered Topic Sections

Each major area of work gets a numbered top-level section (e.g., `## 1. New Visualizer Type`). Within each section, explore the topic thoroughly using whatever subsections the topic demands.

Sections are **not required to follow a rigid template** — adapt the structure to the complexity and nature of the topic. However, every section should at minimum cover:

- **Current state** — what exists today in the codebase, referencing specific files and code
- **Problems or gaps** — what is wrong, missing, or inadequate, stated factually
- **Design options** — alternatives considered, with pros and cons for each

For complex topics, sections will naturally expand to cover:

- Detailed technical designs with code snippets showing proposed signatures, class structures, or data flows
- Tables comparing current vs. proposed state, or comparing design options
- Migration concerns and backwards compatibility considerations
- Dependency ordering (what must exist before this can be built)

**Example of a well-structured section:**

```markdown
## 1. Spectrum Visualizer Type

**Current state — existing visualizer architecture:**

| Component | File | Role |
|-----------|------|------|
| `Visualizer` base | `visualizers/genericVisualizer.py` | Defines `prepare_shapes()` / `generate_frame()` |
| `AudioData` | `visualizers/utilities.py` | Provides `chromagrams[]` and `average_volumes[]` |
| View base | `ui/views/general/generalView.py` | Defines `validate_view()` / `read_view_values()` |

**Gap:** No visualizer currently uses FFT frequency-bin data directly —
all existing types use either pre-computed volume or chromagram features.

**Design options:**

| Option | Pros | Cons |
|--------|------|------|
| Add FFT to AudioData | Reuses existing pipeline | Increases memory for all visualizers |
| Compute per-frame in visualizer | No AudioData changes | Slower, redundant computation |
```

### Testing Considerations

A section covering testing strategy across the areas of work: what new test infrastructure is needed, what existing tests are affected, what coverage gaps exist, and what integration testing is required.

### Implementation Sequencing

A section documenting the dependency ordering between topic sections. This helps the user understand what must be done first and what can be parallelized. Include both hard dependencies and soft sequencing preferences.

```markdown
## N. Implementation Sequencing

Section 1 (AudioData changes) ← Section 2 (New Visualizer) — visualizer depends on new audio features
Section 3 (UI improvements)   — independent, can proceed in parallel
```

### Risk Areas

A table documenting risks and their mitigations across all topic areas:

```markdown
## N. Risk Areas

| Risk | Mitigation |
|------|-----------|
| New audio analysis doubles memory usage | Lazy computation, only when visualizer type requires it |
| Physics simulation unstable at high FPS | Clamp velocity and force values |
```

### Decisions Made

A table recording all design decisions that have been finalized through the clarification process. This becomes the authoritative reference when producing an implementation plan.

```markdown
## N. Decisions Made

| Topic | Decision |
|-------|---------|
| FFT computation | Compute in AudioData, cache per frame |
| Color system | Use per-band colors for all chroma visualizers |
```

### Clarifications Resolved

Once clarification questions are answered, record the resolutions here as a numbered list. This tracks the evolution of the plan and provides context for why decisions were made.

```markdown
## N. Clarifications Resolved

1. FFT bin count defaults to 64 but is configurable per visualizer.
2. New visualizer types do not require backwards-compatible settings files.
```

### Clarifications Required

Every research plan must end with a **Clarifications Required** section. This is a numbered list of questions for the user — decisions that the researcher could not make unilaterally and needs the user to resolve. **Scope decisions belong here.**

```markdown
## N. Clarifications Required

1. **Scope**: Should vX.Y.Z include the spectrum visualizer, or defer to a later release?
2. **Dependencies**: Should we add scipy as a required dependency for FFT, or use numpy's FFT?
3. **UI**: Should new visualizer settings use tabs or inline panels?
```

Guidelines for clarification questions:
- Be specific — include enough context that the user can answer without re-reading the entire plan
- Group related questions together
- Indicate the default or recommended answer where you have one
- After the user answers, update the plan to reflect their decisions and move resolved items to the Decisions Made / Clarifications Resolved sections

## Writing Guidelines

### Grounding in the Codebase

Every claim about current behavior must reference the actual code:

- Name specific files, classes, and functions
- Include code snippets or signatures where they clarify the design
- Use tables to compare current vs. proposed state
- Note the exact codebase version or date the research was conducted against

### Design Decision Documentation

When documenting design decisions:

1. **State the decision clearly** — what was chosen and what was rejected
2. **Explain the rationale** — why this option wins over alternatives
3. **Note trade-offs** — what is given up by this choice
4. **Record constraints** — what external factors influenced the decision

Use tables for comparing options when there are multiple dimensions:

```markdown
| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Option A | Simple, familiar | Doesn't scale | Rejected |
| Option B | Scales well, clean API | More complex migration | **Chosen** |
```

### Scope Neutrality

Research plans must not assert what is or isn't in scope for a release. Instead:

- Describe each topic area thoroughly regardless of whether it will ultimately be included
- When a topic's inclusion is uncertain, note it as a clarification question
- Present the full picture so the user can make informed scope decisions
- Do not use language like "this should be deferred" or "this must be included" — instead, describe the dependencies and trade-offs and let the user decide
