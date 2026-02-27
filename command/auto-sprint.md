---
name: 'auto-sprint'
description: 'Automated BMAD sprint pipeline - processes ALL remaining stories sequentially. Usage: /auto-sprint'
---

# BMAD Auto-Sprint Pipeline

You are the **sprint orchestrator**. Process ALL remaining stories in the current sprint by running the auto-story pipeline for each one sequentially.

---

## SETUP

1. **Read sprint-status.yaml** at `_bmad-output/implementation-artifacts/sprint-status.yaml`
   - If file not found: **HALT** — "No sprint-status.yaml found. Run /bmad-bmm-sprint-planning first."

2. **Build story list** — Parse all entries under `development_status:`
   - Separate epics (e.g., `epic-1`) from stories (e.g., `1-1-user-auth`)
   - Separate retrospectives (e.g., `epic-1-retrospective`)
   - Group stories by their epic

3. **Display sprint overview:**

```
## Sprint Status Overview

| Story Key            | Current Status  | Action          |
|----------------------|-----------------|-----------------|
| epic-1               | in-progress     | —               |
| 1-1-user-auth        | done            | SKIP            |
| 1-2-account-mgmt     | ready-for-dev   | START at Dev    |
| 1-3-plant-data       | backlog         | START at Create |
| epic-1-retrospective | optional        | SKIP until epic done |
| epic-2               | backlog         | —               |
| 2-1-personality      | backlog         | START at Create |
| ...                  | ...             | ...             |

**Total**: {total} stories | **Done**: {done} | **Remaining**: {remaining}
```

---

## EXECUTION

Process stories **in sprint-status.yaml order** (top to bottom):

### For EACH story (not epics, not retrospectives):

1. **Skip** if status == `done`

2. **Determine starting phase** from current status:
   | Status          | Starting Phase          |
   |-----------------|------------------------|
   | `backlog`       | Phase 1 (CREATE-STORY) |
   | `ready-for-dev` | Phase 3 (DEV-STORY)    |
   | `in-progress`   | Phase 3 (DEV-STORY)    |
   | `review`        | Phase 4 (CODE-REVIEW)  |

3. **Run auto-story pipeline** — Invoke /auto-story {story-key}
   - **Model selection**: Ensure all spawned teammates use model `sonnet`, except code review teammates which use model `opus`
   - This creates a team, processes the story through all remaining phases, and cleans up
   - Wait for the pipeline to complete before starting the next story

4. **Handle outcomes:**
   - **SUCCESS**: Continue to next story automatically
   - **HARD HALT**: Present to user:
     ```
     Story {story-key} encountered a HARD HALT: {reason}
     1. Continue to next story (skip this one)
     2. Stop the sprint pipeline
     ```

5. **Epic completion check**: After processing all stories in an epic:
   - If ALL stories in the epic are `done`: update epic status to `done`
   - If epic is `done` AND retrospective is `optional`:
     ```
     Epic {epic-id} is complete. Run retrospective? (optional)
     1. Skip retrospective
     2. Run /bmad-bmm-retrospective for this epic
     ```

---

## COMPLETION

After processing all stories (or user stops):

**Print sprint completion report:**

```
## SPRINT COMPLETION REPORT

### Story Results
| Story Key         | Final Status | Phases | Quality Gate | Issues    | Warnings        |
|-------------------|-------------|--------|--------------|-----------|-----------------|
| 1-1-user-auth     | done        | —      | —            | —         | (was already done) |
| 1-2-account-mgmt  | done        | 5/7    | PASS (95%)   | 2 medium  | none            |
| 1-3-plant-data    | done        | 7/7    | PASS (100%)  | 0         | none            |
| 2-1-personality   | HALTED      | 3/7    | —            | 1 critical | security issue  |
| ...               | ...         | ...    | ...          | ...       | ...             |

### Epic Status
| Epic    | Status      | Stories Done |
|---------|-------------|-------------|
| epic-1  | done        | 3/3         |
| epic-2  | in-progress | 1/3         |

### Sprint Summary
- **Stories Completed**: {n}/{total}
- **Stories Halted**: {n} (require manual attention)
- **Quality Gates**: {n} PASS, {n} CONCERNS, {n} FAIL, {n} WAIVED
- **Total Tech Debt Items**: {count MEDIUM/LOW across all stories}
- **Warnings**: {summary of convergence warnings}
```
