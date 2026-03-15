# Creating a Task Plan

This document defines how to create task plans for Audio Visualizer feature development.

## Task Plan Structure

Every task plan should be broken down into **numbered task phases**. These phases are major feature implementations which are numbered:

```
## Phase N: Major Feature Name
```

### Task Blocks

Each phase is broken into task blocks with a descriptive title:

```
### N.N: Feature Description
```

### Task Block Contents

Each task block must contain:
1. A list of tasks to complete
2. A short description of the feature
3. The files to modify or create

### Post-Task Completion

After completing a task block, the following must be done:

1. Create/update tests for new features
2. Run tests: `pytest tests/ -v`
3. Update `.agents/docs/` architecture documentation as needed
4. Run `git add` on all modified files and `git commit` with a message following the format in `COMMIT_MESSAGE.md` (see [COMMIT_MESSAGE.md](./COMMIT_MESSAGE.md)) and then `git push`.

### Success Criteria

Each task block must have a `**success criteria:**` which clearly describes what a successful implementation results in.

### Code Review Phase
Every Major Feature phase should have a final code review phase with tasks:
- Review the changes and ensure the phase is entirely implemented
- Review code for deprecated code or dead code
- Review tests to ensure they are well-structured

### Changelog

Every Major Feature phase should end with a task summarizing the changes.

## Final Review Phase

Every task plan ends with a final phase for code review and final documentation review.

### Code Review Phase
The purpose of this sub phase is ensure code quality after all previous stages were completed.

**Tasks**:
- Review all phases in this plan and ensure there are no gaps or bugs remaining in the implementation
- Review all changes for unintended regressions
- Review for deprecated code, dead code, or legacy compatibility shims — remove them
- Review all new modules for proper error handling and logging
- Review test suite:
  - No auto-pass tests
  - Test structure matches project module structure
  - All new features have tests
- Commit and push changes for this sub-phase.

### Integration Testing
The purpose of this sub phase is to ensure all testing passes.

**Tasks**:
- Run all existing tests: `pytest tests/ -v`
- Commit and push changes for this sub-phase.

### Architecture Documentation Update

**Tasks**:
- Update all `.agents/docs/architecture/` files to reflect changes made in this plan
- Update `ARCHITECTURE.md` top-level overview
- Commit and push changes for this sub-phase.
**Files**: All architecture docs listed above

**Success criteria**: Architecture docs accurately reflect codebase.

### Release Preparation

**Tasks**:
- Update `readme.md` to reflect changes in this new version.
- Update version in `pyproject.toml` and `readme.md` to new version
- Run final full test suite: `pytest tests/ -v`
- Commit and push changes for this sub-phase.

**Files**:
- `pyproject.toml`
- `readme.md` 
