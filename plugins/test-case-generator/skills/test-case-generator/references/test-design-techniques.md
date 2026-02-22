# Test Design Techniques

## Table of Contents
- [When to Apply Each Technique](#when-to-apply-each-technique)
- [Equivalence Partitioning](#equivalence-partitioning)
- [Boundary Value Analysis](#boundary-value-analysis)
- [Decision Table Testing](#decision-table-testing)
- [State Transition Testing](#state-transition-testing)
- [Negative Testing](#negative-testing)
- [Security-Aware Testing](#security-aware-testing)
- [Requirement Traceability](#requirement-traceability)

---

## When to Apply Each Technique

| Input/Feature Characteristic | Apply Technique |
|---|---|
| Input has defined valid ranges (age, price, quantity) | Equivalence Partitioning + Boundary Value |
| Multiple conditions combine to produce different outcomes | Decision Table |
| Feature has distinct states (draft → published → archived) | State Transition |
| User input that could be malicious | Negative + Security-Aware |
| Field with min/max constraints | Boundary Value |
| Complex business rules with many conditions | Decision Table |
| Workflow with sequential steps | State Transition |
| Any user-facing input | Negative Testing (always) |

---

## Equivalence Partitioning

Divide input domain into classes where all values in a class should behave identically.

**Process:**
1. Identify input parameter.
2. Define valid partition(s): ranges/sets that should produce the same result.
3. Define invalid partition(s): ranges/sets that should be rejected.
4. Pick one representative value from each partition.

**Example — Age field (valid: 18-120):**
| Partition | Range | Representative | Expected |
|---|---|---|---|
| Invalid low | < 18 | 10 | Reject |
| Valid | 18-120 | 45 | Accept |
| Invalid high | > 120 | 150 | Reject |
| Invalid type | non-numeric | "abc" | Reject |
| Empty | blank | "" | Reject |

---

## Boundary Value Analysis

Test at the exact edges of valid/invalid ranges. Defects cluster at boundaries.

**Process:**
1. Identify boundary values (min, max).
2. Test: min-1, min, min+1, max-1, max, max+1.

**Example — Password length (8-64 characters):**
| Value | Length | Expected |
|---|---|---|
| 7 chars | min-1 | Reject |
| 8 chars | min | Accept |
| 9 chars | min+1 | Accept |
| 63 chars | max-1 | Accept |
| 64 chars | max | Accept |
| 65 chars | max+1 | Reject |

---

## Decision Table Testing

For features with multiple conditions producing different outcomes.

**Process:**
1. List all conditions (inputs/states).
2. List all possible actions (outcomes).
3. Create table with all condition combinations.
4. Mark expected action for each combination.
5. Collapse duplicate columns (same actions for different conditions).

**Example — Shipping cost:**
| Condition | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| Order > $50 | Y | Y | N | N |
| Premium member | Y | N | Y | N |
| **Action** | | | | |
| Free shipping | ✓ | ✓ | ✓ | |
| Standard rate | | | | ✓ |

---

## State Transition Testing

For features where behavior depends on current state and transitions between states.

**Process:**
1. Identify all states.
2. Identify all events/triggers that cause transitions.
3. Map valid transitions (state + event → new state).
4. Test valid transitions and invalid transitions (events that should not work in certain states).

**Example — Order lifecycle:**
```
[Created] --pay--> [Paid] --ship--> [Shipped] --deliver--> [Delivered]
    |                 |                                          |
    +---cancel--->[Cancelled]                              [Returned]<--return--+
```

Test cases:
- Valid: Created → pay → Paid (should succeed)
- Valid: Paid → cancel → Cancelled (should succeed)
- Invalid: Shipped → pay (should reject — already paid)
- Invalid: Cancelled → ship (should reject — order cancelled)

---

## Negative Testing

Always generate negative test cases alongside positive ones. For every happy path, consider:

**Input-level negatives:**
- Empty/null/blank values
- Wrong data types (string where number expected)
- Values exceeding max length
- Special characters and unicode
- Extremely large values

**Business-logic negatives:**
- Unauthorized access (wrong role, no auth)
- Operations on wrong state (delete already-deleted item)
- Duplicate operations (submit twice)
- Concurrent modifications
- Expired/invalid tokens or sessions

**System-level negatives:**
- Network timeout / service unavailable
- Database connection failure
- Disk full / out of memory (if applicable)

---

## Security-Aware Testing

Include these checks for user-facing features:

| Category | Test |
|---|---|
| **Injection** | SQL injection in text fields, XSS in displayed fields, command injection in file names |
| **Auth/Authz** | Access without login, access another user's data, privilege escalation |
| **Data exposure** | Sensitive data in responses, PII in logs, tokens in URLs |
| **Input validation** | Oversized payloads, malformed JSON/XML, special characters |
| **Session** | Session fixation, concurrent sessions, session expiry |

Not all apply to every feature — include only relevant ones based on the feature's exposure.

---

## Requirement Traceability

When generating from requirements, ensure every requirement has at least one test case:

1. **Extract requirements**: Parse numbered requirements, user stories, or acceptance criteria.
2. **Map to test cases**: Each requirement → 1+ test cases. Tag with requirement ID.
3. **Coverage check**: List any requirements without test cases. Flag as gaps.
4. **Bidirectional trace**: Each test case references its source requirement.

Format:
```markdown
| Requirement | Test Cases | Coverage |
|---|---|---|
| REQ-001: User can register | TC-REG-001, TC-REG-002, TC-REG-003 | ✓ Full |
| REQ-002: Password policy | TC-REG-004, TC-REG-005 | ✓ Full |
| REQ-003: Email verification | — | ✗ Gap |
```
