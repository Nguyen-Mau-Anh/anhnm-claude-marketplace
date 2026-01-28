# Common Orchestration Utilities

Shared utilities library for all orchestration skills.

## Philosophy

**One file per utility** - Each utility has a single responsibility and lives in its own file for:
- Easy navigation
- Clear dependencies
- Simple testing
- Independent versioning

## Utilities (Phase 1 & 2 Complete)

### Phase 1: Core Infrastructure ✅
- **spawner.py** - Agent execution & process management with real-time output
- **config_loader.py** - Generic YAML configuration loading
- **logger.py** - Structured logging with timestamps
- **status_manager.py** - Pipeline state persistence

### Phase 2: Learning & Reliability ✅
- **knowledge_base.py** - Lessons learned system
- **retry_handler.py** - Retry logic with backoff
- **file_utils.py** - Safe file operations
- **validators.py** - Input validation

## Usage

```python
from pathlib import Path
from _common import (
    ClaudeSpawner,      # Spawn Claude agents
    ConfigLoader,       # Load configurations
    Logger, LogLevel,   # Structured logging
    StatusManager,      # Track pipeline state
    KnowledgeBase,      # Learn from errors
    RetryHandler,       # Retry with backoff
    safe_read,          # Safe file operations
    validate_story_id,  # Input validation
)

# Create story-specific logger (recommended)
logger = Logger.for_story(
    story_id="1-2-auth-feature",
    project_root=Path.cwd(),
    level=LogLevel.INFO
)
# Log file: .orchestrate-temp/logs/stories/1-2-auth-feature.log

# Create spawner with logging
spawner = ClaudeSpawner(
    project_root=Path.cwd(),
    logger=logger,
    show_output=True  # Real-time output streaming
)

# Spawn agent
logger.stage_start("implementation")
result = spawner.spawn_agent(
    prompt="Implement feature X",
    timeout=600
)
logger.stage_end("implementation", success=result.success, duration_seconds=result.duration_seconds)

logger.info(f"Success: {result.success}")
```

## Documentation

See `../docs/` for detailed guides:
- **COMMON-TOOLS-LIST.md** - Complete tool catalog
- **IMPLEMENTATION-STATUS.md** - Progress tracking
- **SPAWNER-GUIDE.md** - Spawner usage guide

## Testing

See `../tests/` for test scripts:
- **test_spawner.py** - Test spawner with real-time output

Run tests:
```bash
python3 tests/test_spawner.py --mode realtime
```

## Dependencies

**Core Python (stdlib):**
- pathlib, dataclasses, typing, enum
- subprocess, threading, signal, atexit
- datetime, hashlib, re
- tempfile, shutil, fcntl, os

**Third Party:**
- `yaml` - YAML parsing
- `pydantic` - Data validation

## Version

1.0.0 - Phase 1 & 2 Complete

## Structure

```
orchestrate-auto-dev/
├── _common/              ← You are here
│   ├── README.md        (this file)
│   ├── __init__.py      (exports)
│   └── *.py             (8 utilities)
│
├── docs/                ← Documentation
│   ├── COMMON-TOOLS-LIST.md
│   ├── IMPLEMENTATION-STATUS.md
│   └── SPAWNER-GUIDE.md
│
└── tests/               ← Test scripts
    └── test_spawner.py
```
