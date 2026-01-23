---
name: orchestrate-prepare
description: "Layer 0: Story preparation and validation. Creates story from epics and validates it's ready for development."
allowed-tools: Bash, Read, Write, Glob
---

# Orchestrate Prepare - Layer 0

Automated story preparation pipeline: creates and validates stories.

## Commands

| User Says | Action |
|-----------|--------|
| `/orchestrate-prepare` | Create next story from backlog |
| `/orchestrate-prepare <story_id>` | Prepare specific story (e.g., `1-2-user-auth`) |

## Execution

**CRITICAL: You MUST run the Python executor via bash. Do NOT try to execute the pipeline steps manually.**

### Run the Executor

Run this single command - it checks dependencies and runs the pipeline:

```bash
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor
```

For a specific story:
```bash
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor <story_id>
```

### Command Reference

| Command | Full Execution |
|---------|----------------|
| `/orchestrate-prepare` | `python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null \|\| pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor` |
| `/orchestrate-prepare <story_id>` | `python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null \|\| pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor <story_id>` |

**Example:**
```bash
# Create next story from backlog
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor

# Prepare specific story
python3 -c "import rich, typer, pydantic, yaml" 2>/dev/null || pip install -q rich typer pydantic pyyaml; PYTHONPATH="${PWD}/.claude/skills/orchestrate-prepare" python3 -m executor 1-2-user-auth
```

## How It Works

The Python executor spawns isolated Claude agents for each stage:

1. **create-story** → Spawns `/bmad:bmm:workflows:create-story` to generate story from epics
2. **validate** → Spawns `/bmad:bmm:workflows:implementation-readiness` to validate story

## Configuration

### Auto-Discovery

On first run, the executor:
1. Checks for `docs/orchestrate-prepare.config.yaml`
2. If not found, copies `default.config.yaml` from skill folder
3. Uses the project config for all settings

### Customization

Edit `docs/orchestrate-prepare.config.yaml` to customize:

```yaml
stages:
  create-story:
    enabled: true
    timeout: 3600

  validate:
    enabled: true
    retry:
      max: 2  # Retry validation up to 2 times
```

## Pipeline Stages

| # | Stage | Execution | On Failure |
|---|-------|-----------|------------|
| 1 | Create Story | SPAWN | Abort |
| 2 | Validate | SPAWN | Fix + Retry ×2 |

## Flow Diagram

```
/orchestrate-prepare
    │
    ├── Check story file exists?
    │   ├── NO  → SPAWN: create-story workflow
    │   └── YES → continue
    │
    ├── SPAWN: validate workflow
    │   └── fail → Retry ×2
    │
    └── Output: story_id, story_file
```

## Prerequisites

- BMAD installed (`.bmad/` folder)
- Epic files in `state/epics/` or `docs/epics/`
- Sprint status file (for backlog)

## Output

After completion, shows:
- Story ID
- Story file path
- Validation status
- Overall status (success/failed)

## Usage with Higher Layers

Layer 0 is the foundation that other layers build on:

```
Layer 0 (/orchestrate-prepare)      ← You are here
    │
    └── creates story_id, story_file
            │
            ▼
Layer 1 (/orchestrate-dev)          ← Uses Layer 0's output
    │
    └── develops code
            │
            ▼
Layer 2 (/orchestrate-integrate)    ← Full dev pipeline + PR + merge
    │
    └── merges to main
            │
            ▼
Layer 3 (/orchestrate-qa)           ← Runs QA tests
```

Layer 1+ can call Layer 0 automatically, or you can run Layer 0 standalone to just prepare stories.
