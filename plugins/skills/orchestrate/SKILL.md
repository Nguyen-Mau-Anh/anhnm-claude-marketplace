---
name: orchestrate
description: Start autonomous AI development orchestration. Runs stories through dev, test, and review pipeline automatically. Use when user says "orchestrate", "start orchestration", "run development", or "process stories".
allowed-tools: Bash, Read, Write, Glob
---

# Orchestrate - AI Development Automation

Autonomous orchestration that processes stories through the full development pipeline by spawning separate Claude agents.

## How It Works

This skill runs a **Python orchestrator** that spawns **separate Claude CLI agents** for each phase:
1. **Dev Agent** - Implements the story (`claude --print`)
2. **Test Agent** - Runs tests (`claude --print`)
3. **Review Agent** - Code review (`claude --print`)

The orchestrator manages the pipeline and tracks status.

## Commands

| User Says | Action |
|-----------|--------|
| `/orchestrate` | Start full orchestration |
| `/orchestrate --dry-run` | Preview what would run |
| `/orchestrate status` | Show sprint status |
| `/orchestrate review` | List stories for review |
| `/orchestrate approve <id>` | Approve a completed story |

## Execution

**CRITICAL: You MUST use the Bash tool to run the Python orchestrator. Do NOT try to orchestrate manually.**

### Finding the Skill Location

The orchestrator Python code is located in this skill's directory. Use one of these methods:

#### Method 1: Using CLAUDE_SKILL_DIR (if available)
```bash
"${CLAUDE_SKILL_DIR}/run.sh" start
```

#### Method 2: Find the skill directory dynamically
```bash
# Find the orchestrate skill directory
ORCH_DIR=$(find . -path "*/skills/orchestrate/run.sh" -exec dirname {} \; 2>/dev/null | head -1)
if [ -z "$ORCH_DIR" ]; then
  ORCH_DIR=$(find ~/.claude -path "*/skills/orchestrate/run.sh" -exec dirname {} \; 2>/dev/null | head -1)
fi
"${ORCH_DIR}/run.sh" start
```

#### Method 3: Direct path (if installed locally)
```bash
# For local development in this marketplace
PYTHONPATH="./plugins/skills/orchestrate" python3 -m orchestrator start
```

### Command Reference

| Command | Execution |
|---------|-----------|
| `/orchestrate` | `"${ORCH_DIR}/run.sh" start` |
| `/orchestrate --dry-run` | `"${ORCH_DIR}/run.sh" start --dry-run` |
| `/orchestrate status` | `"${ORCH_DIR}/run.sh" status` |
| `/orchestrate review` | `"${ORCH_DIR}/run.sh" review` |
| `/orchestrate approve <id>` | `"${ORCH_DIR}/run.sh" approve <id>` |

## What the Orchestrator Does

When you run the orchestrator via Bash, it:

1. **Reads `sprint-status.yaml`** for actionable stories
2. **For each story, spawns Claude agents via `claude --print`**:
   - Phase 1: Dev agent implements the story
   - Phase 2: TEA agent runs tests
   - Phase 3: Code review agent
3. **Updates story status** after each phase
4. **Marks completed stories** for user review

### Agent Spawning Pattern

The Python code uses `ClaudeSpawner` which executes:
```python
subprocess.run(["claude", "--print", "-p", prompt], ...)
```

This spawns a **separate Claude process** - not running in parent context.

## Prerequisites

Before running, verify:

1. **sprint-status.yaml exists** - If not, run:
   ```bash
   "${ORCH_DIR}/run.sh" init
   ```

2. **Stories are ready** - Check for `ready-for-dev` or `drafted` status

3. **Dependencies installed** - The run.sh script auto-installs:
   - rich, typer, pydantic, pyyaml, aiofiles

## Error Handling

If orchestrator fails:
- No sprint-status.yaml → Run `init` command first
- No actionable stories → Show current status
- Claude spawn fails → Show error and continue to next story

## Example Session

```
User: /orchestrate status

Claude: [Runs via Bash]
$ ORCH_DIR=$(find . -path "*/skills/orchestrate/run.sh" -exec dirname {} \;)
$ "${ORCH_DIR}/run.sh" status

[Shows sprint status table]

User: /orchestrate

Claude: [Runs via Bash]
$ "${ORCH_DIR}/run.sh" start

[Orchestrator spawns Claude agents for each story]
[Shows live dashboard with progress]
```

## Output

After running, the orchestrator outputs:
- Stories processed
- Success/failure for each phase
- Stories ready for review
- Any errors encountered
