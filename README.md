# anhnm Claude Marketplace

A personal collection of plugins for Claude Code.

## Structure

- **`/plugins`** - Custom plugins with skills, commands, hooks, and agents

## Installation

```bash
/plugin marketplace add anhnm/anhnm-claude-marketplace
```

Then browse and install via `/plugin > Discover`.

## Available Skills

| Skill | Description |
|-------|-------------|
| `java-developer` | Expert Java/Spring Boot development — architecture, code quality, and patterns |
| `test-case-generator` | Generate test cases from PRDs/specs with auto suite selection and flexible output |
| `orchestrate-auto-dev` | Automated development pipeline with quality gates |
| `orchestrate-test-design` | Test design and planning orchestration |

## Plugin Structure

```
plugins/
├── .claude-plugin/
│   └── plugin.json
├── commands/
├── skills/
├── hooks/
├── agents/
└── README.md
```

## License

MIT
