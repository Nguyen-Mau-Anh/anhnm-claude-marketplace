# Hello World Plugin

An example plugin demonstrating all Claude Code plugin components.

## Components

### Commands (`/commands`)
- **`/greet`** - A simple greeting command

### Skills (`/skills`)
- **`greeting-assistant`** - Provides friendly, context-aware greetings

### Hooks (`/hooks`)
- **`session-welcome`** - Displays welcome message on session start

### Agents (`/agents`)
- **`greeter`** - Specialized agent for user onboarding

## Installation

```bash
/plugin marketplace add anhnm/anhnm-claude-marketplace
/plugin install hello-world
```

## Usage

After installation:
- Use `/greet` to test the greeting command
- The welcome hook runs automatically on session start
- The greeting-assistant skill activates contextually

## Structure

```
hello-world/
├── .claude-plugin/
│   └── plugin.json      # Plugin metadata
├── commands/
│   └── greet.md         # Slash command definition
├── skills/
│   └── greeting-assistant/
│       └── SKILL.md     # Skill definition
├── hooks/
│   └── hooks.json       # Hook configurations
├── agents/
│   └── greeter.md       # Agent definition
└── README.md
```

## License

MIT
