# Release Statement Template

Use this template when drafting GitHub release notes for Audio Visualizer.
Copy the block below, replace all `{{ PLACEHOLDER }}` tokens, then delete this header section.

---

## Audio Visualizer v{{ VERSION }} ({{ DATE YYYY-MM-DD }})

{{ One-paragraph executive summary. Describe the major themes of this release in 2–4 sentences.
   Name the high-level feature areas (e.g. "new visualizer types", "rendering improvements") without
   listing every item — the sections below cover details. }}

### What's New

{{ One bullet per major user-visible feature area. Start each bullet with "Added".
   Group related items into a single bullet rather than fragmenting. }}

- Added {{ feature area 1 }}: {{ brief capability description }}.
- Added {{ feature area 2 }}: {{ brief capability description }}.
- Added {{ feature area 3 }}: {{ brief capability description }}.

### Upgrade Notes

{{ Omit this section entirely if there are no breaking changes or new required settings. }}

- New/updated settings:
  - `{{ setting }}` — {{ what it controls }}
  - `{{ setting }}` — {{ what it controls }}
- {{ Breaking change description }}: {{ old behavior }} changed to {{ new behavior }}.
  - {{ Migration step if needed. }}

### Summary Changelog

- **Added**
  - {{ Fine-grained item. Use same phrasing style as "What's New" but more specific. }}
  - {{ Fine-grained item. }}
- **Changed**
  - {{ Behavior or interface change. }}
  - {{ Behavior or interface change. }}
- **Fixed**
  - {{ Bug or hardening fix. }}
  - {{ Bug or hardening fix. }}

---

## Authoring Guidelines

### Header

```
## Audio Visualizer vX.Y.Z (YYYY-MM-DD)
```

Use the full semantic version and the release date in ISO format.

### Executive Summary

- 2–4 sentences maximum.
- Name major feature *areas* (e.g. "physics-based visualizers", "rendering pipeline improvements")
  rather than individual items.
- Mention the rough count of significant additions only if it adds clarity (e.g. "4 new chroma
  visualizer types").

### What's New

- One bullet per major feature area. Consolidate tightly related items.
- Each bullet starts with **"Added"** (present perfect, not gerund).
- Order: most impactful / most user-visible items first.
- Omit internal-only refactors here; those belong in Summary Changelog > Changed.

### Upgrade Notes

Include this section **only** when one or more of the following apply:

| Trigger | Example |
|---------|---------|
| New required settings or dependencies | New Python version requirement |
| Breaking changes to project file format | Settings JSON schema change |
| Changed rendering behavior | Default codec or resolution change |
| Removed visualizer types or options | Deprecated visualizer removed |

List each item as a sub-bullet with a short description.

### Summary Changelog

Three subsections in order: **Added**, **Changed**, **Fixed**.

- Items are finer-grained than "What's New" bullets — one item per concrete component or behavior.
- Omit subsections with no entries.
- Use the same verb-first, present-tense style as the example (`Added`, `Changed`, `Fixed` prefix
  is the subsection heading, not repeated on each line).
