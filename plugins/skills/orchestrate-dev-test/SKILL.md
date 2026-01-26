# orchestrate-dev-test (L2)

**Purpose:** L2 orchestrator that wraps L1 and adds parallel test design + test execution.

**Layer:** 2

---

## Skill Overview

You are the **orchestrate-dev-test** skill (Layer 2). Your job is to:

1. **Check test requirement** - Skip tests for certain story types
2. **Spawn parallel tracks** - Dev (L1) and Test Design run simultaneously
3. **Wait for sync point** - Both tracks must complete
4. **Deploy to test environment** - Local or cloud
5. **Generate test scripts** - Via TEA using TDM
6. **Execute tests** - Smoke (P0) then Critical SQA (P1)
7. **Fix loop** - Auto-fix failures, max 3 attempts

---

## Invocation

```bash
/orchestrate-dev-test <story-id>
```

Or invoked automatically by L3 (orchestrate-integrate).

---

## Prerequisites

Before running, ensure:
- [ ] Story exists at `state/stories/{story-id}.md` (or L0 will create it)
- [ ] `docs/architecture.md` contains deployment section (optional)
- [ ] Test framework configured (Playwright/Jest)

---

## Execution Flow

### Step 1: Check Test Requirement

```yaml
skip_if_story_type:
  - environment-setup
  - documentation
  - config-change
  - dependency-update

require_if_story_type:
  - feature
  - bugfix
  - refactor
  - api-change
```

**If skip:** Run only L1 (dev), skip test track entirely, pass to L3.

### Step 2: Spawn Parallel Tracks

Spawn both tracks simultaneously:
- Dev track (L1): `/orchestrate-dev`
- Test track: `/orchestrate-test-design`

### Step 3: Wait for Sync Point

Wait for both tracks to complete. If either fails, abort.

### Step 4: Deploy to Test Environment

1. Read deployment config from `docs/architecture.md`
2. Determine target (local or cloud)
3. Execute deployment
4. Wait for health check
5. Record test env URL in `state/test-env/{story-id}.json`

### Step 5: Generate Test Scripts via TEA

Invoke TEA with TDM as source of truth:
- Output: `tests/smoke/{story-id}/*.spec.ts`
- Output: `tests/sqa/critical/{story-id}/*.spec.ts`

### Step 6: Run Tests (Two Phases)

#### Phase 1: Smoke Tests (P0)
- Run `npm run test:smoke`
- If PASS -> Continue to Phase 2
- If FAIL -> Enter fix loop

#### Phase 2: Critical SQA Tests (P1)
- Run `npm run test:sqa:critical`
- If PASS -> L2 Complete
- If FAIL -> Enter fix loop

### Step 7: Fix Loop (on failure)

```yaml
fix_loop:
  max_attempts: 3
  steps:
    1. Analyze test failure output
    2. Identify root cause in CODE (not tests)
    3. Fix the code
    4. Redeploy application
    5. Rerun failed test phase
```

---

## Output Files

### Status File

Write to `state/l2/status-{story-id}.json`:

```json
{
  "story_id": "{story-id}",
  "layer": "L2",
  "status": "complete",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "tracks": {
    "dev": {
      "status": "complete",
      "duration_seconds": 1234
    },
    "test_design": {
      "status": "complete",
      "duration_seconds": 567
    }
  },
  "deployment": {
    "method": "docker-compose",
    "url": "http://localhost:3000",
    "status": "healthy"
  },
  "test_execution": {
    "smoke_p0": {
      "status": "passed",
      "tests_run": 5,
      "tests_passed": 5
    },
    "critical_sqa_p1": {
      "status": "passed",
      "tests_run": 10,
      "tests_passed": 10
    },
    "fix_attempts": 0
  },
  "ready_for_l3": true
}
```

---

## Integration Points

### Wrapped by L3 (orchestrate-integrate)

L3 calls L2 before creating PR:
```
L3 invokes -> L2 completes -> L3 creates PR -> CI runs P2-P3
```

### Wraps L1 (orchestrate-dev)

L2 spawns L1 in parallel with test design:
```
L2 spawns -> L1 (dev) + test-design (parallel)
```

---

## Success Criteria

L2 is complete when:
- [ ] Dev track (L1) completed successfully
- [ ] Test design track completed successfully
- [ ] Application deployed to test environment (if applicable)
- [ ] Smoke tests (P0) all passing
- [ ] Critical SQA tests (P1) all passing
- [ ] Status file written with `ready_for_l3: true`
