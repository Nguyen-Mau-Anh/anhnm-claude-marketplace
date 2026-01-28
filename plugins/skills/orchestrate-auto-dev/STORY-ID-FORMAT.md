# Story ID Format

## Current Format (v1.0.0+)

Story IDs follow the format: `{epic}-{story}-{description}`

**Examples:**
- `2-1-timetable-creation`
- `1-2-user-authentication`
- `3-5-payment-integration`

**NO "story-" prefix is used.**

## Sprint Status Mapping

Story IDs match the entries in `sprint-status.yaml`:

```yaml
development_status:
  epic-2: in-progress
  2-1-personality-system: backlog
  2-2-chat-interface: backlog
```

## File Locations

Story files are created at:
- `docs/sprint-artifacts/{story_id}.md`
- `docs/stories/{story_id}.md`
- `state/stories/{story_id}.md`

Example: `docs/sprint-artifacts/2-1-timetable-creation.md`

## Usage

### With Claude Code
```bash
/orchestrate-auto-dev 2-1-timetable-creation
```

### Direct Execution
```bash
./run 2-1-timetable-creation
```

## Agent Output Format

When creating a story, agents MUST output the story_id in one of these formats:

✅ **Supported formats:**
- `Story ID: 2-1-timetable-creation`
- `Created story: 2-1-timetable-creation`
- `Story: 2-1-timetable-creation`
- Just the ID on its own line: `2-1-timetable-creation`

❌ **NOT supported:**
- `story-2-1-timetable-creation` (legacy format, will be converted)

## Legacy Format

The old format `story-1-2-description` is automatically converted to `1-2-description` during extraction for backward compatibility.

## Why This Format?

1. **Consistency** - Matches sprint-status.yaml format
2. **Simplicity** - No redundant "story-" prefix
3. **Clarity** - Epic and story numbers are clear
4. **Standard** - Follows BMAD methodology conventions
