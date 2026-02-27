---
name: 'auto-story'
description: 'Automated BMAD story pipeline - processes a story from creation through dev, review, QA to done. Usage: /auto-story [story-key]'
---

# BMAD Auto-Story Pipeline

You are the **team lead** orchestrating the BMAD implementation pipeline for story "$ARGUMENTS". Your job: create an agent team, spawn fresh teammates for each phase, and coordinate the full story lifecycle autonomously.

Each teammate is a fresh Claude Code session that invokes BMAD skills directly. You coordinate by reading artifact files between phases and applying convergence detection to prevent infinite fix loops.

---

## SETUP

1. **Parse story key** from "$ARGUMENTS"
   - If empty: auto-discover by reading `_bmad-output/implementation-artifacts/sprint-status.yaml` and finding the FIRST story with status "backlog" (top to bottom)
   - Store the resolved `{story-key}` for all phases

2. **Read sprint-status.yaml** at `_bmad-output/implementation-artifacts/sprint-status.yaml`
   - Find the story's current status
   - Determine the **starting phase**:

   | Current Status  | Start From                    |
   |-----------------|-------------------------------|
   | `backlog`       | Phase 1 (CREATE-STORY)        |
   | `ready-for-dev` | Phase 3 (DEV-STORY)           |
   | `in-progress`   | Phase 3 (DEV-STORY resume)    |
   | `review`        | Phase 4 (CODE-REVIEW)         |
   | `done`          | SKIP — story already complete |

3. **Locate story file** (if starting from Phase 3+): search `_bmad-output/implementation-artifacts/` for `{story-key}.md`

4. **Create team** called `auto-{story-key}`

---

## GLOBAL RULES

1. **Fresh teammate per phase** — Spawn a NEW teammate for each phase. Never reuse. This matches BMAD's "fresh context per workflow" design.
2. **YOLO mode** — Tell every teammate: "Choose YOLO mode (y) when the workflow asks for input to auto-complete all sections."
3. **Evaluate by reading files** — Between phases, YOU (the lead) read sprint-status.yaml and story files directly. Don't rely solely on teammate messages.
4. **Sequential by default, parallel where noted** — Most phases run sequentially. Phase 3 runs DEV and QA-PREPARE in parallel to save time.
5. **Shutdown after each phase** — Shut down each teammate before spawning the next phase's teammates.
6. **No user interaction** — All phases run autonomously EXCEPT Phase 6 (correct-course), which pauses for user decision.
7. **Model selection** — Use model `sonnet` for all spawned teammates. Exception: use model `opus` for code review teammates (Phase 4 `reviewer-{n}`).

---

## CONVERGENCE DETECTION

For Phases 2 and 4 (validation/review loops), track severity between rounds:

**After each round:**
1. Count issues by severity: CRITICAL, HIGH, MEDIUM, LOW
2. Compare with previous round's counts
3. Decide:

| Condition                                  | Action                              |
|--------------------------------------------|-------------------------------------|
| No CRITICAL or HIGH issues                 | **PROCEED** — clean                 |
| CRITICAL/HIGH count decreased vs last round | **RETRY** — progress being made     |
| CRITICAL/HIGH count same or increased       | **PROCEED + WARN** — stale loop     |
| CRITICAL security vulnerability + stale     | **HARD HALT** — report to user      |

**Hard cap**: Maximum 3 rounds per convergence loop. After round 3, proceed regardless with warnings logged.

---

## PHASE 1: CREATE-STORY

**Goal**: Create a context-rich story file ready for development.

**Spawn teammate** `sm-create`:
> You are Bob (Scrum Master). Run the skill /bmad-bmm-create-story for story "{story-key}".
> When the workflow prompts for input on generated sections, choose YOLO mode (respond "y") to auto-complete without pausing.
> When done, message me with:
> 1. The story file path
> 2. Whether sprint-status.yaml shows "ready-for-dev" for this story
> 3. Any issues encountered

**Lead evaluates:**
- Read `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Verify story status == `ready-for-dev`
- If NOT: **HALT** — "Story creation failed for {story-key}"
- If YES: store `{story-file-path}`, **PROCEED** to Phase 2

**Shut down** `sm-create`.

---

## PHASE 2: VALIDATE-STORY (convergence loop)

**Goal**: Ensure story quality before development begins.

**Round {n}** — Spawn teammate `sm-validate-{n}`:
> You are Bob (Scrum Master). Validate the story file at `{story-file-path}`.
> Load the validation checklist at `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`.
> Execute the full checklist against the story. Fix ALL issues you find directly in the story file.
> When the checklist asks for user choices, choose "all" to apply all improvements.
> When done, message me with: counts of CRITICAL, HIGH, MEDIUM, LOW issues found and fixed.

**Lead evaluates** — Apply CONVERGENCE DETECTION:
- Parse teammate's severity report
- If **PROCEED**: go to Phase 3
- If **RETRY**: shut down, spawn new teammate for next round
- If **HARD HALT**: report to user and stop

**Shut down** `sm-validate-{n}`.

---

## PHASE 3: DEV-STORY + QA-PREPARE (parallel)

**Goal**: Implement the story AND prepare QA test infrastructure simultaneously.

These two teammates run **in parallel** — dev implements while QA prepares test cases, scripts, and environment. This saves time so QA execution (Phase 5) can start immediately after code review.

### 3a: DEV-STORY

**Spawn teammate** `dev-impl`:
> You are Amelia (Developer). Run the skill /bmad-bmm-dev-story for the story at `{story-file-path}`.
> When the workflow prompts for input, choose YOLO mode (respond "y").
> Execute ALL tasks in exact order from the story file. Follow red-green-refactor cycle.
> Do NOT pause for milestones or session boundaries. Continue until ALL tasks are checked [x].
> If you encounter a HALT condition (missing deps, 3 consecutive failures, missing config), message me immediately.
> When done, message me with:
> 1. Task completion count (e.g., "8/8 tasks complete")
> 2. Test results (all passing? any failures?)
> 3. Any HALT conditions encountered

### 3b: QA-PREPARE (runs in parallel with 3a)

**Spawn teammate** `qa-prepare`:
> You are Murat (Test Architect). Your job is to prepare the full QA test infrastructure while the developer implements the story. Work from the story file at `{story-file-path}`.
>
> Do these steps in order:
>
> **Step 1 — Test Framework Setup**: Run the skill /bmad-tea-testarch-framework to set up or verify the test automation environment (Playwright, test runner, config). Choose YOLO mode (y) when prompted. If the framework is already set up, confirm it's ready and skip to Step 2.
>
> **Step 2 — Test Design**: Run the skill /bmad-tea-testarch-test-design to create a risk-based test plan from the story's Acceptance Criteria. Choose YOLO mode (y). Design test cases covering: happy paths, edge cases, error scenarios, and cross-browser considerations for this story.
>
> **Step 3 — ATDD (Acceptance Test-Driven Development)**: Run the skill /bmad-tea-testarch-atdd to generate failing acceptance test stubs from the story's ACs. Choose YOLO mode (y). These are higher-level BDD-style tests that verify the final product behavior. The developer is writing unit/integration tests in parallel — your ATDD tests complement theirs at the acceptance level.
>
> When done, message me with:
> 1. Test framework status (new setup or already existed)
> 2. Number of test cases designed (from test design)
> 3. Number of ATDD acceptance test stubs generated
> 4. Test design document location
> 5. ATDD test file locations
> 6. Any blockers or concerns

### Lead evaluates (wait for BOTH teammates):

**For dev-impl:**
- Read the story file: verify ALL tasks and subtasks marked `[x]`
- Read sprint-status.yaml: verify status == `review`
- If all tasks `[x]` AND status == `review`: dev is **DONE**
- If teammate reported HALT: **HARD HALT** — report to user
- If tasks incomplete but no HALT: **HARD HALT** — implementation failed

**For qa-prepare:**
- Confirm test framework is ready
- Confirm test design document exists
- If qa-prepare failed: **WARN** but don't halt — QA can still generate tests in Phase 5

**Shut down** `dev-impl` and `qa-prepare`.
**PROCEED** to Phase 4 only when BOTH are done.

---

## PHASE 4: CODE-REVIEW (convergence loop)

**Goal**: Adversarial review to catch bugs, security issues, and quality problems.

**Round {n}** — Spawn teammate `reviewer-{n}`:
> You are Amelia (Developer) in code review mode. Run the skill /bmad-bmm-code-review for the story at `{story-file-path}`.
> When the workflow prompts for input, choose YOLO mode (respond "y").
> When the review presents options for handling findings, always choose "Option 1: Fix automatically" if available.
> When done, message me with:
> 1. Severity counts: CRITICAL, HIGH, MEDIUM, LOW
> 2. What you fixed
> 3. Whether you found any architectural violations (keywords: "architecture violation", "pattern violation", "structural issue")

**Lead evaluates** — Apply CONVERGENCE DETECTION:
- Read story file → find "Senior Developer Review (AI)" section
- Count CRITICAL, HIGH, MEDIUM, LOW findings
- Check for architectural violation keywords

| Condition                        | Action                                               |
|----------------------------------|------------------------------------------------------|
| Architectural violation detected | **TRIGGER Phase 6** (correct-course, pause for user) |
| No CRITICAL/HIGH                 | **PROCEED** to Phase 5                               |
| CRITICAL/HIGH decreased          | Shut down reviewer → spawn dev-fix → new reviewer    |
| CRITICAL/HIGH stale              | **PROCEED + WARN** in report                         |
| CRITICAL security + stale        | **HARD HALT** — report to user                       |

**Dev-fix sub-phase** (when review needs fixes before retry):
Spawn teammate `dev-fix-{n}`:
> You are Amelia (Developer). Read the story file at `{story-file-path}`.
> Look for the "Review Follow-ups (AI)" section. Fix ONLY the CRITICAL and HIGH severity issues.
> Run ALL tests afterward to ensure no regressions.
> When done, message me with: what you fixed and full test results.

**Shut down** `reviewer-{n}` and `dev-fix-{n}` after each round.

---

## PHASE 5: QA-EXECUTE

**Goal**: Complete the test suite and execute all tests against the implemented code.

Phase 3b prepared: test framework, test design, and ATDD acceptance test stubs. This phase **expands coverage, completes the ATDD tests, and runs everything**.

**Spawn teammate** `qa-execute`:
> You are Murat (Test Architect). The test framework, test design, and ATDD stubs were prepared in Phase 3b.
>
> Run the skill /bmad-tea-testarch-automate to expand test coverage for the story at `{story-file-path}`.
> Choose YOLO mode (y) when prompted.
>
> Context:
> - Check `_bmad-output/test-artifacts/` for test design docs and ATDD stubs from Phase 3b
> - The developer has already written unit and integration tests during implementation
> - Your job: complete the ATDD acceptance tests against the real implementation, add any missing E2E coverage, and run the full test suite
> - Focus on web E2E tests using Playwright (set up in Phase 3b)
>
> When done, message me with:
> 1. Total tests: ATDD acceptance tests + dev tests + new automation tests
> 2. Pass/fail counts for each test level (unit, integration, E2E, acceptance)
> 3. Any CRITICAL bugs found (describe each with severity)
> 4. Test coverage vs story acceptance criteria (which ACs are covered, which are not)

**Lead evaluates:**
- Parse test results from teammate's report
- If no CRITICAL bugs: **PROCEED** to Phase 5b (Quality Gate)
- If CRITICAL bugs AND first round: spawn dev-bugfix, then re-test (max 2 rounds)
- If CRITICAL bugs AND stale (same bugs after fix): **PROCEED + WARN**

**Dev-bugfix sub-phase** (when QA finds critical bugs):
Spawn teammate `dev-bugfix`:
> You are Amelia (Developer). Read the story file at `{story-file-path}` and the QA test results.
> Fix the CRITICAL bugs identified by QA. Run ALL tests (unit + integration + E2E + acceptance). Message me with results.

**Shut down** `qa-execute` and `dev-bugfix`.

---

## PHASE 5b: QUALITY-GATE

**Goal**: Verify requirements coverage and test quality before marking story as done.

This phase uses TEA's traceability workflow to map requirements to tests and make a data-driven release gate decision.

**Spawn teammate** `qa-gate`:
> You are Murat (Test Architect). Run the skill /bmad-tea-testarch-trace for the story at `{story-file-path}`.
> Choose YOLO mode (y) when prompted.
>
> Context:
> - Story file with acceptance criteria: `{story-file-path}`
> - Test files: written by dev (unit/integration) + ATDD acceptance tests + E2E automation tests
> - Gate scope: `story` (this is a per-story quality gate)
>
> Map every story acceptance criterion to at least one test. Identify any gaps.
> Apply the gate decision logic and report the result.
>
> When done, message me with:
> 1. Gate decision: PASS, CONCERNS, FAIL, or WAIVED
> 2. Coverage percentage (P0, P1, P2 requirements)
> 3. Any uncovered acceptance criteria
> 4. Traceability matrix location

**Lead evaluates:**
- If gate == **PASS**: **STORY DONE** → go to COMPLETION
- If gate == **CONCERNS**: **PROCEED + WARN** — log gaps as tech debt in report
- If gate == **FAIL**: Present to user:
  ```
  Quality gate FAILED for {story-key}:
  {list uncovered P0/P1 requirements}

  Options:
  1. Spawn dev to add missing test coverage, then re-gate
  2. Override gate (WAIVE) and proceed
  3. Stop the pipeline
  ```
- If gate == **WAIVED**: **PROCEED** with waiver noted in report

**Shut down** `qa-gate`.

---

## PHASE 6: CORRECT-COURSE (conditional — user interaction required)

**Trigger**: Architectural violations detected in Phase 4.

**Action**: PAUSE the pipeline and present to the user:

```
## Architectural Violations Detected in {story-key}

The code review found the following architectural violations:
{list each violation with details}

**Options:**
1. Run /bmad-bmm-correct-course to formally address the issue
2. Proceed anyway (accept the violations as tech debt)
3. Stop the pipeline — I'll fix this manually
```

- If user chooses 1: Spawn teammate to run `/bmad-bmm-correct-course`, then resume from Phase 4
- If user chooses 2: Continue to Phase 5 with violations logged
- If user chooses 3: **HALT** pipeline

---

## COMPLETION

1. **Update sprint-status.yaml**: Set `{story-key}` status to `done`
   - If all stories in the epic are `done`, set epic status to `done`

2. **Clean up team**: Ensure all teammates are shut down, then clean up the team

3. **Print final report**:

```
## AUTO-STORY PIPELINE REPORT: {story-key}

| Phase           | Status  | Rounds | Details                        |
|-----------------|---------|--------|--------------------------------|
| Create Story    | {status} | 1     | {story file path}              |
| Validate Story  | {status} | {n}/3 | {issues found/fixed}           |
| Dev Story       | {status} | 1     | {tasks}/{total} tasks, {tests} |
| QA Prepare      | {status} | 1     | framework: {status}, test design: {n} cases, ATDD: {n} stubs |
| Code Review     | {status} | {n}/3 | {severity breakdown}           |
| QA Execute      | {status} | {n}/2 | {total} tests, {passing} pass, {failing} fail |
| Quality Gate    | {status} | 1     | {PASS/CONCERNS/FAIL}: {coverage}% coverage |
| Correct Course  | {status} | -     | {details or "N/A"}             |

**Final Status**: {story-key} = "done"
**Remaining Issues**: {list MEDIUM/LOW items as tech debt}
**Warnings**: {list any stale-loop or convergence warnings}
**Total Teammates Spawned**: {count}
```
