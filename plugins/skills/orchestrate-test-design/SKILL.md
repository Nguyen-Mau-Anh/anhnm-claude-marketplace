# orchestrate-test-design

**Purpose:** Test design track that creates TDM, generates test cases, and validates them.

**Type:** Parallel Track (runs alongside Layer 1 development, spawned by Layer 2)

**Note:** This is NOT a sequential layer in the hierarchy. It runs in **parallel** with `orchestrate-dev` (L1) when spawned by `orchestrate-dev-test` (L2). Can also run independently.

---

## Skill Overview

You are the **orchestrate-test-design** skill. Your job is to:

1. **Read story** - Extract acceptance criteria
2. **Create TDM** - Test Design Matrix using ISTQB techniques
3. **Generate test cases** - For all priorities (P0-P3)
4. **Validate test cases** - Ensure coverage and correctness
5. **Fix if needed** - Max 3 attempts

---

## Invocation

```bash
/orchestrate-test-design <story-id>
```

Or called by L2 (orchestrate-dev-test) in parallel with L1 (orchestrate-dev).

---

## Prerequisites

- [ ] Story file exists at `state/stories/{story-id}.md`
- [ ] Story has acceptance criteria defined

---

## Execution Flow

### Step 1: Read Story

Read story file from `state/stories/{story-id}.md`.

Extract:
- Story ID and title
- Acceptance criteria (ACs)
- Story type (feature, bugfix, etc.)
- Any technical constraints

### Step 2: Create TDM (Test Design Matrix)

Generate TDM file at `docs/test-design/matrices/tdm-{story-id}.yaml`.

#### 2.1 Requirements Analysis

For each acceptance criterion:
- Determine if testable
- Identify input/output patterns
- Detect applicable ISTQB techniques

#### 2.2 Select ISTQB Techniques

Apply these techniques based on patterns:

| Pattern Detected | Technique |
|------------------|-----------|
| Input validation, formats | Equivalence Partitioning (EP) |
| Numeric limits, lengths | Boundary Value Analysis (BVA) |
| Multiple conditions | Decision Table (DT) |
| Workflow, status changes | State Transition (ST) |
| Security concerns | Error Guessing (EG) |
| User journeys | Use Case (UC) |

### Step 3: Generate Test Cases

From the test design, generate concrete test cases organized by priority.

#### Priority Assignment Rules

| Priority | Category | Criteria |
|----------|----------|----------|
| P0 (Smoke) | Happy path + basic error | Core functionality, must work |
| P1 (Critical) | Security, boundaries, edge | Important but not blocking |
| P2 (Standard) | All remaining edge cases | Nice to have coverage |
| P3 (Extended) | Performance, accessibility | Non-functional requirements |

### Step 4: Validate Test Cases

Perform validation checks:

#### Coverage Validation

- All acceptance criteria have at least one test
- Smoke suite includes error cases (not just happy paths)
- Critical SQA includes security basics
- Critical SQA includes boundary tests

#### Quality Validation

- Each test has clear expected result
- Each test maps to at least one AC
- No duplicate test cases
- Test steps are actionable

### Step 5: Fix Loop (if validation fails)

If validation fails, attempt to fix:

- Max 3 attempts
- Identify missing coverage
- Generate additional test cases
- Re-validate

---

## Output Files

### TDM File

Write to `docs/test-design/matrices/tdm-{story-id}.yaml`

### Status File

Write to `state/test-design/status-{story-id}.json`:

```json
{
  "story_id": "{story-id}",
  "track": "test-design",
  "status": "complete",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "outputs": {
    "tdm_file": "docs/test-design/matrices/tdm-{story-id}.yaml",
    "test_cases": {
      "p0_smoke": 5,
      "p1_critical": 10,
      "p2_full": 8,
      "p3_extended": 5
    },
    "validation_attempts": 1,
    "validation_passed": true,
    "coverage": {
      "acceptance_criteria": "100%",
      "techniques_used": ["EP", "BVA", "EG", "ST"]
    }
  },
  "error": null
}
```

---

## ISTQB Technique Reference

### Equivalence Partitioning (EP)
- Divide inputs into valid/invalid classes
- Test one value from each class
- **Use for:** Input fields, formats, types

### Boundary Value Analysis (BVA)
- Test at boundaries: min-1, min, min+1, max-1, max, max+1
- **Use for:** Numeric limits, string lengths, array sizes

### Decision Table (DT)
- Map conditions to actions
- Cover all combinations
- **Use for:** Complex business rules, multiple conditions

### State Transition (ST)
- Identify states and transitions
- Test valid and invalid transitions
- **Use for:** Workflows, status changes, sessions

### Error Guessing (EG)
- Based on experience and common bugs
- Security attack vectors
- **Use for:** Security tests, edge cases, known problem areas

### Use Case (UC)
- Test user journeys end-to-end
- Main flow, alternate flows, exception flows
- **Use for:** User-facing features, workflows

---

## Success Criteria

Test design track is complete when:
- [ ] TDM file created at `docs/test-design/matrices/tdm-{story-id}.yaml`
- [ ] All acceptance criteria have test coverage
- [ ] Smoke suite includes error cases (not just happy paths)
- [ ] Critical SQA includes security and boundary tests
- [ ] Validation passed
- [ ] Status file written with `status: "complete"`
