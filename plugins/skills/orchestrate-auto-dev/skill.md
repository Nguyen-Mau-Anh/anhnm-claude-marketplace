# orchestrate-auto-dev

**Version:** 1.0.0
**Layer:** 1
**Purpose:** Automated development orchestrator
**Command:** ./run

---

## Overview

Automated development orchestration skill that executes story development with minimal manual intervention.

## Usage

```bash
# From Claude CLI
/orchestrate-auto-dev <story_id>

# Example
/orchestrate-auto-dev 1-2-user-auth

# Direct execution (alternative)
# Unix/Linux/Mac
./run <story_id>

# Windows
run.bat <story_id>
```

## Requirements

- Python 3.8 or later (`python3` or `python` in PATH)
- Git

The skill auto-detects whether `python3` or `python` is available and uses the appropriate command.

## Configuration

Configuration file: `docs/orchestrate-auto-dev.config.yaml`

The default configuration is automatically copied to your project on first run.

### Key Settings

- **story_locations**: Paths to search for story files
- **stages**: Pipeline stages to execute
- **autonomy_instructions**: Instructions for autonomous agent execution

## Pipeline Stages

### 1. Development (develop)
- Executes story implementation
- Uses `/bmad:bmm:workflows:dev-story` workflow
- Timeout: 30 minutes

### 2. Quality Check (quality-check)
- Optional quality verification
- Disabled by default
- Configure as needed

## Output

The orchestrator tracks:
- `story_id`: Story identifier
- `story_file`: Path to story file
- `status`: Execution status

## Architecture

```
orchestrate-auto-dev/
├── executor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py          # CLI interface
│   ├── config.py       # Configuration loader
│   └── runner.py       # Pipeline runner
├── default.config.yaml # Default configuration
└── skill.md           # This file
```

## Future Enhancements

- Integration with `_common` library for shared utilities
- Enhanced quality checks
- Test automation integration
- CI/CD integration

---

**Status:** 🚧 In Development
