# anhnm Claude Marketplace

A personal Claude Code plugin marketplace for custom skills, hooks, commands, agents, and MCP servers.

## Recent Updates

### January 2026
- **Code Review Enhancement**: Added file filtering (max 20 files, 100KB each) and graceful cleanup handlers
- **Task Decomposition**: Auto-detect and process large stories (6+ tasks) task-by-task to prevent context overload
- **Story Validation**: New validation gate ensures all tasks and acceptance criteria are completed before marking stories done
- **Layer 0 Added**: New `orchestrate-prepare` skill for story preparation and validation pipeline
- **SKIP Status**: Support for disabling stages in orchestrate-dev configuration

## Quick Start

### Install the Marketplace

```bash
/plugin marketplace add anhnm/anhnm-claude-marketplace
```

### Browse & Install Plugins

```bash
/plugin
```

---

## Available Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [hello-world](plugins) | 1.0.1 | AI development automation with orchestration skills, commands, hooks, and agents |

### Featured Skills

#### Orchestration Skills (AI Development Automation)

| Skill | Layer | Description |
|-------|-------|-------------|
| `orchestrate-prepare` | Layer 0 | Story preparation and validation - creates stories from epics and validates readiness |
| `orchestrate-dev` | Layer 1 | Automated development pipeline with quality gates (lint, typecheck, test, code review) |
| `orchestrate` | Layer 2 | Full autonomous orchestration - processes stories through complete dev pipeline |

**Recent Improvements:**
- ✅ Story completion validation gate - ensures all tasks/acceptance criteria are completed
- ✅ Automatic task decomposition for large stories (6+ tasks)
- ✅ Automated code review with file filtering (max 20 files, 100KB each)
- ✅ Graceful cleanup handlers (SIGINT/SIGTERM)
- ✅ Fix-and-retry logic with configurable retry limits
- ✅ SKIP status for disabled stages
- ✅ Layer 0 (orchestrate-prepare) for story preparation pipeline

**Architecture:**
```
Layer 0: orchestrate-prepare → Story creation + validation
Layer 1: orchestrate-dev     → Development + quality checks (lint/test/review)
Layer 2: orchestrate         → Full autonomous pipeline orchestration
```

---

## Repository Structure

```
anhnm-claude-marketplace/
├── .claude-plugin/
│   └── marketplace.json        # Marketplace registry
├── .github/workflows/          # CI/CD validation
├── .husky/                     # Git hooks (pre-commit, commit-msg)
├── scripts/
│   ├── validate.js             # Plugin validator
│   ├── version.js              # Version manager
│   └── lint-json.js            # JSON linter
├── plugins/                    # Plugin components
│   ├── .claude-plugin/
│   │   └── plugin.json         # Plugin metadata
│   ├── commands/               # Slash commands
│   │   └── greet.md
│   ├── skills/                 # Agent skills
│   │   ├── greeting-assistant/
│   │   ├── orchestrate/        # Layer 2: Full orchestration
│   │   ├── orchestrate-dev/    # Layer 1: Dev pipeline with quality gates
│   │   └── orchestrate-prepare/# Layer 0: Story preparation
│   ├── hooks/                  # Event handlers
│   │   └── hooks.json
│   ├── agents/                 # Specialized agents
│   │   └── greeter.md
│   ├── CHANGELOG.md            # Version history
│   └── README.md               # Plugin docs
├── docs/
├── package.json
└── README.md
```

---

## Creating a New Plugin

### Quick Start (Recommended)

Use the scaffolding tool to create a new plugin with all boilerplate:

```bash
# Interactive mode - prompts for all options
npm run new-plugin

# Quick mode - creates plugin with all components
npm run new-plugin my-plugin "My plugin description"
```

This automatically:
- Creates the plugin directory structure at `plugins/my-plugin/`
- Generates `plugin.json`, `README.md`, `CHANGELOG.md`
- Creates example files for selected components
- Registers the plugin in `marketplace.json`

### Manual Setup

#### Step 1: Create Plugin Directory

```bash
mkdir -p plugins/my-plugin/{.claude-plugin,commands,skills,hooks,agents}
```

#### Step 2: Add Plugin Metadata

Create `plugins/my-plugin/.claude-plugin/plugin.json`:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Short description of what your plugin does",
  "author": {
    "name": "anhnm"
  },
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"],
  "components": {
    "commands": ["my-command"],
    "skills": ["my-skill"],
    "hooks": ["my-hook"],
    "agents": ["my-agent"]
  }
}
```

#### Step 3: Add Components (see sections below)

#### Step 4: Create Plugin README

Create `plugins/my-plugin/README.md` documenting your plugin.

#### Step 5: Create Changelog

Create `plugins/my-plugin/CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this plugin will be documented in this file.

## [1.0.0] - YYYY-MM-DD

### Added
- Initial release
- List your features here
```

#### Step 6: Register in Marketplace

Add to `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    {
      "name": "my-plugin",
      "path": "plugins/my-plugin",
      "description": "Short description"
    }
  ]
}
```

#### Step 7: Validate

```bash
npm run validate
```

---

## Plugin Components Guide

### Commands (`/commands`)

Slash commands users can invoke directly (e.g., `/my-command`).

**File:** `commands/<command-name>.md`

```markdown
# /my-command

Brief description of what this command does.

## Usage

\`\`\`
/my-command [arg1] [arg2]
\`\`\`

## Arguments

- `arg1` - Description of first argument
- `arg2` - (Optional) Description of second argument

## Description

Detailed explanation of what the command does and when to use it.

## Instructions

Step-by-step instructions for Claude on how to execute this command:

1. First, do this...
2. Then, do that...
3. Finally, return the result...

## Examples

- `/my-command foo` - Example with foo
- `/my-command foo bar` - Example with both args
```

---

### Skills (`/skills`)

Reusable capabilities that can be auto-invoked or manually triggered.

**File:** `skills/<skill-name>/SKILL.md`

```markdown
# Skill Name

Brief description of this skill's purpose.

## When to Use

Use this skill when:
- Condition 1
- Condition 2
- Condition 3

## Instructions

When this skill is active:

1. **Step One** - Description
2. **Step Two** - Description
3. **Step Three** - Description

## Example Behaviors

### Scenario 1
Description of how to behave in this scenario.

### Scenario 2
Description of how to behave in this scenario.

## Integration

Notes on how this skill works with other components.
```

---

### Hooks (`/hooks`)

Event handlers that trigger automatically at specific moments.

**File:** `hooks/hooks.json`

```json
{
  "hooks": [
    {
      "name": "my-hook",
      "event": "SessionStart",
      "description": "What this hook does",
      "command": "echo 'Hook executed!'"
    },
    {
      "name": "pre-edit-check",
      "event": "PreToolUse",
      "description": "Run before tool execution",
      "command": "node scripts/check.js"
    }
  ]
}
```

**Available Events:**

| Event | Description |
|-------|-------------|
| `SessionStart` | Runs when a Claude Code session starts |
| `PreToolUse` | Runs before a tool is executed |
| `PostToolUse` | Runs after a tool is executed |
| `Stop` | Runs when session is ending |

---

### Agents (`/agents`)

Specialized AI agents for specific tasks.

**File:** `agents/<agent-name>.md`

```markdown
# Agent Name

Brief description of this agent's purpose.

## Purpose

Detailed explanation of what this agent specializes in.

## Capabilities

- Capability 1
- Capability 2
- Capability 3

## When to Invoke

This agent should be invoked when:
- Condition 1
- Condition 2

## Behavior

1. Step one of agent behavior
2. Step two of agent behavior
3. Step three of agent behavior

## Example Interaction

User: "Example user input"

Agent: "Example agent response demonstrating behavior"
```

---

### MCP Servers (`.mcp.json`)

Model Context Protocol configuration for external tool integrations.

**File:** `plugins/my-plugin/.mcp.json`

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

---

## Version Management

### List All Versions

```bash
npm run version:list
```

### Bump Plugin Version

```bash
# Patch (1.0.0 → 1.0.1) - Bug fixes
npm run version:bump <plugin-name> patch -m "Fix description"

# Minor (1.0.0 → 1.1.0) - New features
npm run version:bump <plugin-name> minor -m "Add new feature"

# Major (1.0.0 → 2.0.0) - Breaking changes
npm run version:bump <plugin-name> major -m "Breaking change description"
```

### Interactive Mode

```bash
npm run version:interactive
```

### What Happens on Version Bump

1. `plugin.json` version is updated
2. `CHANGELOG.md` gets a new entry with date and message
3. Changes are ready to commit

---

## Development Workflow

### 1. Setup

```bash
# Clone and install
git clone https://github.com/anhnm/anhnm-claude-marketplace.git
cd anhnm-claude-marketplace
npm install
```

### 2. Create/Edit Plugin

```bash
# Create new plugin
mkdir -p plugins/my-plugin/{.claude-plugin,commands,skills,hooks,agents}

# Edit files...
```

### 3. Validate

```bash
# Full validation
npm run validate

# Marketplace only
npm run validate:marketplace

# Plugins only
npm run validate:plugins
```

### 4. Version Bump (if updating)

```bash
npm run version:bump my-plugin patch -m "Description of changes"
```

### 5. Commit

```bash
git add .
git commit -m "feat(my-plugin): add new plugin"
```

**Commit Message Format (Conventional Commits):**

```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert
```

### 6. Push

```bash
git push origin main
```

---

## Validation & Quality

### Pre-commit Hooks

Automatically runs on every commit:
- JSON linting
- Plugin structure validation
- Version format checking
- Commit message format validation

### Manual Validation

```bash
# All validations
npm run validate

# JSON syntax only
npm run lint:json *.json
```

### CI/CD

GitHub Actions validates on every push/PR:
- marketplace.json validity
- All plugin structures
- Required files presence

---

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run new-plugin` | Create a new plugin (interactive) |
| `npm run validate` | Full marketplace & plugin validation |
| `npm run validate:marketplace` | Validate marketplace.json only |
| `npm run validate:plugins` | Validate all plugins only |
| `npm run lint:json` | Lint JSON files |
| `npm run version:list` | List all plugin versions |
| `npm run version:bump` | Bump a plugin version |
| `npm run version:interactive` | Interactive version manager |

---

## Team Configuration

Auto-install this marketplace for your team by adding to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "anhnm-claude-marketplace": {
      "source": {
        "source": "github",
        "repo": "anhnm/anhnm-claude-marketplace"
      }
    }
  }
}
```

---

## Resources

- [Claude Code Documentation](https://code.claude.com/docs)
- [Plugin System Guide](https://code.claude.com/docs/en/plugins)
- [Skills Documentation](https://code.claude.com/docs/en/skills)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)

---

## License

MIT
