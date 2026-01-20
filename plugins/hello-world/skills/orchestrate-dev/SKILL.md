---
name: orchestrate-dev
description: "Layer 1: Automated story development with quality checks. Creates/validates story, develops code, runs lint/typecheck/tests, and performs code review."
allowed-tools: Bash, Read, Write, Glob
---

# Orchestrate Dev - Layer 1

Automated story development pipeline with quality gates.

## Execution Model

- **BMAD workflows** → Spawned as separate `claude --print` processes (fully isolated)
- **Bash commands** → Direct execution (lint, typecheck, test)
- **Fix-and-retry** → Spawns dev agent to fix failures

## Commands

| User Says | Action |
|-----------|--------|
| `/orchestrate-dev` | Run next story from backlog |
| `/orchestrate-dev 1-2-user-auth` | Develop specific story |

## Execution

**IMPORTANT: Before running, ensure dependencies are installed.**

### Step 1: Install Dependencies

```bash
pip install -q -r "${PWD}/.claude/skills/orchestrate-dev/requirements.txt" 2>/dev/null || pip install rich typer pydantic pyyaml
```

### Step 2: Run Pipeline

```bash
PYTHONPATH="${PWD}/.claude/skills/orchestrate-dev" python3 -m executor
```

### Command Reference

| Command | Full Execution |
|---------|----------------|
| `/orchestrate-dev` | `PYTHONPATH="${PWD}/.claude/skills/orchestrate-dev" python3 -m executor` |
| `/orchestrate-dev {story_id}` | `PYTHONPATH="${PWD}/.claude/skills/orchestrate-dev" python3 -m executor {story_id}` |

## Configuration

### Auto-Discovery

On first run, the executor:
1. Checks for `docs/orchestrate-dev.config.yaml`
2. If not found, copies `default.config.yaml` from skill folder
3. Uses the project config for all settings

### Customization

Edit `docs/orchestrate-dev.config.yaml` to customize:

```yaml
stages:
  lint:
    command: "pnpm lint"      # Change package manager

  typecheck:
    command: "pnpm typecheck"

  unit-test:
    command: "pnpm test"
    retry:
      max: 5                  # More retries
```

## Pipeline Stages

| # | Stage | Execution | On Failure |
|---|-------|-----------|------------|
| 1 | Create Story | SPAWN | Abort |
| 2 | Validate | SPAWN | Fix + Retry ×2 |
| 3 | Develop | SPAWN | Fix + Retry ×3 |
| 4 | Lint | DIRECT | Fix + Retry ×2 |
| 5 | Typecheck | DIRECT | Fix + Retry ×2 |
| 6 | Unit Test | DIRECT | Fix + Retry ×3 |
| 7 | Code Review | SPAWN | Continue (non-blocking) |

## Flow Diagram

```
/orchestrate-dev
    │
    ├── Check story file exists?
    │   ├── NO  → SPAWN: create-story workflow
    │   └── YES → continue
    │
    ├── SPAWN: validate workflow
    │   └── fail → SPAWN: dev agent fix → retry ×2
    │
    ├── SPAWN: dev-story workflow
    │   └── fail → SPAWN: dev agent fix → retry ×3
    │
    ├── DIRECT: npm run lint
    │   └── fail → SPAWN: dev agent fix → retry ×2
    │
    ├── DIRECT: npm run typecheck
    │   └── fail → SPAWN: dev agent fix → retry ×2
    │
    ├── DIRECT: npm test
    │   └── fail → SPAWN: dev agent fix → retry ×3
    │
    ├── SPAWN: code-review workflow (non-blocking)
    │
    └── Output summary
```

## Prerequisites

- Story files in `state/stories/` or `docs/stories/`
- BMAD installed (`.bmad/` folder)
- Package.json with lint/typecheck/test scripts

## Output

After completion, shows:
- Story ID and file path
- Stage results (PASS/FAIL)
- Files changed
- Review findings
- Overall status
