---
name: orchestrate-integrate
description: "Layer 3: Complete integration pipeline from story creation through PR merge. Delegates to Layer 2 (orchestrate-dev-test) for development and testing, then handles git/PR operations."
allowed-tools: Bash, Read, Write, Glob
---

# Orchestrate Integrate - Layer 3

Complete automated integration pipeline: story → development → quality checks → PR → CI/CD → merge.

## Commands

| User Says | Action |
|-----------|--------|
| `/orchestrate-integrate` | Auto-detect and integrate next story from backlog |
| `/orchestrate-integrate <story_id>` | Integrate specific story (e.g., `1-2-user-auth`) |
| `/orchestrate-integrate <file_path>` | Integrate story from file path (e.g., `docs/stories/1-2-user-auth.md`) |
| `/orchestrate-integrate <partial_name>` | Search and integrate story by partial name (e.g., `user-auth`) |

## Execution

**CRITICAL: You MUST run the Python executor via bash. Do NOT try to execute the pipeline steps manually.**

### Run the Executor

Run this single command - it checks dependencies and runs the complete pipeline:

```bash
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor
```

For a specific story:
```bash
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor 1-2-user-auth
```

### Command Reference

| Command | Full Execution |
|---------|----------------|
| `/orchestrate-integrate` | `python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null \|\| pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor` |
| `/orchestrate-integrate <story_input>` | `python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null \|\| pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor <story_input>` |

**Examples:**
```bash
# Auto-detect next story
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor

# Specific story ID
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor 1-2-user-auth

# Story file path
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor docs/stories/1-2-user-auth.md

# Partial name search
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-integrate" python3 -m executor user-auth
```

## How It Works

The Python executor runs a complete integration pipeline using a **hierarchical layer architecture**:

### Execution Model

1. **DELEGATE stages** → Calls lower layer skills (e.g., `/orchestrate-dev`)
2. **SPAWN stages** → Runs `claude --print -p "<prompt>"` as subprocess for BMAD workflows and git operations
3. **DIRECT stages** → Runs bash commands directly
4. **Fix-and-retry** → On failure, spawns fix agent, then retries

### Layer Hierarchy

```
Layer 3 (/orchestrate-integrate)
    │
    ├── Stage 1: Delegates to /orchestrate-dev-test (Layer 2)
    │       │
    │       ├── Spawns PARALLEL tracks:
    │       │   ├── Track 1: /orchestrate-dev (Layer 1)
    │       │   │       ↓
    │       │   │       ├── Delegates to /orchestrate-prepare (Layer 0)
    │       │   │       │       ├── create-story
    │       │   │       │       └── validate
    │       │   │       └── Development stages
    │       │   │               ├── develop
    │       │   │               ├── lint
    │       │   │               ├── typecheck
    │       │   │               ├── unit-test
    │       │   │               └── code-review
    │       │   │
    │       │   └── Track 2: /orchestrate-test-design (Parallel Track)
    │       │           ├── create-tdm
    │       │           ├── generate-test-cases
    │       │           └── validate
    │       │
    │       └── After parallel tracks complete:
    │               ├── deploy (optional)
    │               ├── smoke-tests (P0)
    │               └── critical-sqa (P1)
    │
    └── Stages 8-12: Run directly (Layer 3 specific)
            ├── git-commit
            ├── git-push
            ├── pr-create
            ├── pr-checks
            └── pr-merge
```

**Benefits of Hierarchical Design:**
- **No code duplication** - Stages 1-7 defined once in lower layers
- **True layering** - Each layer builds on previous layers
- **Composability** - Can run any layer independently
- **Single source of truth** - Each stage maintained in one place

## Configuration

### Auto-Discovery

On first run, the executor:
1. Checks for `docs/orchestrate-integrate.config.yaml`
2. If not found, copies `default.config.yaml` from skill folder
3. Uses the project config for all settings

### Customization

Edit `docs/orchestrate-integrate.config.yaml` to customize:

```yaml
# PR Settings
pr_settings:
  auto_merge: false                    # Set to true for automatic merge
  merge_method: "squash"               # "squash", "merge", or "rebase"
  delete_branch_after_merge: true
  require_reviews: 0                   # Minimum reviews before merge

# Git Settings
git_settings:
  branch_prefix: "feat/"               # Branch naming prefix
  base_branch: "main"                  # Target branch for PR

# Knowledge Base
knowledge_base:
  enabled: true                        # Enable learning system
  max_lessons_per_stage: null          # null = all lessons

# Stages
stages:
  pr-checks:
    timeout: 1800                      # 30 minutes max for CI/CD
    retry:
      max: 5                           # Max auto-fix attempts
```

## Pipeline Stages

| # | Stage | Execution | On Failure | Layer |
|---|-------|-----------|------------|-------|
| 1 | Layer 2 Execution | DELEGATE | Abort | 2 (dev-test) |
| 2 | Git Commit | SPAWN | Fix + Retry ×2 | 3 |
| 3 | Git Push | SPAWN | Fix + Retry ×2 | 3 |
| 4 | PR Create | SPAWN | Fix + Retry ×2 | 3 |
| 5 | PR Checks | SPAWN | Fix + Retry ×5 | 3 |
| 6 | PR Merge | SPAWN | Configurable | 3 |

**Layer 2 (orchestrate-dev-test) runs internally:**

| Track | Stages | Layer |
|-------|--------|-------|
| Dev (parallel) | create-story, validate, develop, lint, typecheck, unit-test, code-review | L0 + L1 |
| Test Design (parallel) | create-tdm, generate-test-cases, validate | Track |
| Sequential | deploy, smoke-tests, critical-sqa | L2 |

## Flow Diagram

```
/orchestrate-integrate [story_input]
    │
    ├── Input Resolution
    │   ├── None          → auto-detect in create-story
    │   ├── Story ID      → find or create file
    │   ├── File path     → use directly
    │   └── Partial name  → search and match
    │
    ├── DELEGATES TO LAYER 2 (orchestrate-dev-test)
    │   │
    │   ├── PARALLEL EXECUTION:
    │   │   │
    │   │   ├── Track 1 - LAYER 1 (orchestrate-dev)
    │   │   │   ├── LAYER 0: Story Preparation
    │   │   │   │   ├── create-story (if needed)
    │   │   │   │   └── validate (with retry)
    │   │   │   └── Development & Quality
    │   │   │       ├── develop
    │   │   │       ├── lint → auto-fix → retry
    │   │   │       ├── typecheck → auto-fix → retry
    │   │   │       ├── unit-test → auto-fix → retry
    │   │   │       └── code-review (non-blocking)
    │   │   │
    │   │   └── Track 2 - TEST DESIGN (parallel)
    │   │       ├── create-tdm
    │   │       ├── generate-test-cases
    │   │       └── validate test coverage
    │   │
    │   └── AFTER PARALLEL COMPLETION:
    │       ├── deploy to test env (optional)
    │       ├── smoke-tests (P0) → fix loop
    │       └── critical-sqa (P1) → fix loop
    │
    ├── LAYER 3: Git & PR Operations
    │   ├── git-commit
    │   ├── git-push
    │   ├── pr-create
    │   ├── pr-checks → loop until pass
    │   │   └── fail? → auto-fix → push → wait → retry
    │   └── pr-merge (if auto_merge: true)
    │
    └── Output: PR URL, merge status, lessons learned
```

## Knowledge Base Learning

Every stage uses the knowledge base to:
- **Load lessons** from previous runs (prevent known errors)
- **Track prevention** when lessons help avoid errors
- **Save new lessons** when errors are fixed
- **Improve over time** (fewer failures with each run)

Example:
```
First run:  lint fails → auto-fix → saves lesson
Second run: lint passes (lesson prevented error!) ✓
```

## Prerequisites

- BMAD installed (`.bmad/` folder)
- Epic files in `state/epics/` or `docs/epics/`
- Git repository initialized
- GitHub CLI (`gh`) installed and authenticated (for PR operations)
- CI/CD configured on GitHub (optional, for pr-checks stage)

## Output

After completion, shows:
- Story ID
- Story file path
- All stage results (PASS/FAIL/SKIPPED)
- PR URL
- PR status (merged or ready for review)
- Lessons saved/prevented count
- Total execution time

## Usage with Other Layers

```
Layer 0 (/orchestrate-prepare)         ← Story preparation only
    │
    └── creates story_id, story_file
            │
            ▼
Layer 1 (/orchestrate-dev)             ← Development + quality checks
    │                                     (also delegates to L0)
    └── develops code, runs tests
            │
            ├───────────────────┐
            │                   │ (parallel)
            ▼                   ▼
    [dev complete]    [test-design track]
            │                   │
            └───────┬───────────┘
                    ▼
Layer 2 (/orchestrate-dev-test)        ← Parallel dev + test + execution
    │
    └── deploys, runs smoke/SQA tests
            │
            ▼
Layer 3 (/orchestrate-integrate)       ← Git + PR + merge (YOU ARE HERE)
    │
    └── creates PR, monitors CI, merges
```

Layer 3 is a **complete standalone pipeline** that delegates to Layer 2, which orchestrates all development and testing before PR creation.

## Auto-Merge Behavior

**When `auto_merge: false` (default):**
- Pipeline stops after all CI/CD checks pass
- Outputs PR URL for manual review
- User clicks "Merge" on GitHub

**When `auto_merge: true`:**
- Pipeline automatically merges PR after checks pass
- Deletes feature branch (if configured)
- Story fully delivered to main branch

## Example Run

```bash
$ /orchestrate-integrate

[0:00] Input: (auto-detect)
[0:01] Auto-detecting next story from backlog...
[0:02] Found ready story: 1-3-password-reset
[0:05] ✓ Story validated
[2:30] ✓ Development complete
[5:15] ✓ Lint passed (3 lessons prevented errors)
[6:00] ✓ TypeCheck passed
[7:00] ✓ Tests passed
[8:00] ⚠ Code review: 2 suggestions
[8:30] ✓ Commit created
[8:35] ✓ Pushed to origin/feat/1-3-password-reset
[9:00] ✓ PR #42 created
[10:00] Monitoring CI/CD checks...
[13:00] ✓ All checks passed
[13:05] ⏳ PR ready for manual review (auto_merge: false)

✓ Story 1-3-password-reset ready!
  PR: https://github.com/user/repo/pull/42
  Status: READY_FOR_MERGE
  Lessons saved: 2 new
  Errors prevented: 5
  Time: 13 minutes
```
