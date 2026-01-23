---
name: orchestrate-integrate
description: "Layer 2: Complete integration pipeline from story creation through PR merge. Includes development, quality checks, PR creation, CI/CD monitoring, and automated merge."
allowed-tools: Bash, Read, Write, Glob
---

# Orchestrate Integrate - Layer 2

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

The Python executor runs a complete 12-stage pipeline with knowledge-based learning:

**Layer 0 Stages (Story Preparation):**
1. **create-story** → Auto-detect or create story from epics
2. **validate** → Validate story readiness with auto-fix retry

**Layer 1 Stages (Development & Quality):**
3. **develop** → Implement story following TDD
4. **lint** → Run lint checks with auto-fix
5. **typecheck** → Run TypeScript type checking with auto-fix
6. **unit-test** → Run unit tests with auto-fix
7. **code-review** → AI code review (non-blocking)

**Layer 2 Stages (Integration & Deployment):**
8. **git-commit** → Create commit with AI-generated message
9. **git-push** → Push to remote feature branch
10. **pr-create** → Create PR with AI-generated description
11. **pr-checks** → Monitor CI/CD, auto-fix failures (loop until pass)
12. **pr-merge** → Merge PR (configurable: auto or manual)

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
| 1 | Create Story | SPAWN | Abort | 0 |
| 2 | Validate | SPAWN | Fix + Retry ×2 | 0 |
| 3 | Develop | SPAWN | Fix + Retry ×2 | 1 |
| 4 | Lint | SPAWN | Fix + Retry ×3 | 1 |
| 5 | TypeCheck | DIRECT | Fix + Retry ×3 | 1 |
| 6 | Unit Test | DIRECT | Fix + Retry ×3 | 1 |
| 7 | Code Review | SPAWN | Continue (non-blocking) | 1 |
| 8 | Git Commit | SPAWN | Fix + Retry ×2 | 2 |
| 9 | Git Push | SPAWN | Fix + Retry ×2 | 2 |
| 10 | PR Create | SPAWN | Fix + Retry ×2 | 2 |
| 11 | PR Checks | SPAWN | Fix + Retry ×5 | 2 |
| 12 | PR Merge | SPAWN | Configurable | 2 |

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
    ├── LAYER 0: Story Preparation
    │   ├── create-story (if needed)
    │   └── validate (with retry)
    │
    ├── LAYER 1: Development & Quality
    │   ├── develop
    │   ├── lint → fail? → auto-fix → retry
    │   ├── typecheck → fail? → auto-fix → retry
    │   ├── unit-test → fail? → auto-fix → retry
    │   └── code-review (non-blocking)
    │
    ├── LAYER 2: Integration & Merge
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
Layer 0 (/orchestrate-prepare)      ← Story preparation only
    │
    └── creates story_id, story_file
            │
            ▼
Layer 1 (/orchestrate-dev)          ← Development + quality checks
    │
    └── develops code, runs tests
            │
            ▼
Layer 2 (/orchestrate-integrate)    ← Full pipeline + PR + merge (YOU ARE HERE)
    │
    └── merges to main
            │
            ▼
Layer 3 (/orchestrate-qa)           ← QA testing + bug fixing (future)
```

Layer 2 is a **complete standalone pipeline** that includes all previous layers' stages plus PR automation.

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
