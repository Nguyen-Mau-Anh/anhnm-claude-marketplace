# Test Suite Strategy Guide

## Table of Contents
- [Suite Types](#suite-types)
- [Selection Criteria](#selection-criteria)
- [Risk-Based Prioritization](#risk-based-prioritization)
- [Suite Composition Rules](#suite-composition-rules)

---

## Suite Types

### Smoke Test
- **Purpose**: Verify critical paths are not broken. Gate for further testing.
- **Scope**: 5-15 test cases covering core functionality only.
- **When to suggest**: After a build/deploy, quick dev check, CI pipeline gate, hotfix verification.
- **Coverage target**: ~10-20% of total cases — only P0 (critical) flows.
- **Time budget**: < 15 minutes execution.
- **Focus**: Login/auth, main user journey, core CRUD, payment/checkout (if applicable).

### Sanity Test
- **Purpose**: Verify a specific area works after a targeted change.
- **Scope**: 10-30 test cases focused on the changed module + immediate dependencies.
- **When to suggest**: After a bug fix, after a feature change in a specific module.
- **Coverage target**: Deep coverage of affected area, shallow coverage of adjacent areas.
- **Time budget**: 15-60 minutes execution.
- **Focus**: Changed functionality + regression of directly related features.

### Regression Test
- **Purpose**: Ensure existing functionality still works after changes.
- **Scope**: 30-100+ test cases covering all major features.
- **When to suggest**: Before a release, after significant refactoring, sprint end testing.
- **Coverage target**: ~60-80% of total cases — all P0 and P1 flows.
- **Time budget**: 1-4 hours execution.
- **Focus**: All previously working features, integration points, data flows.

### Full/Comprehensive Test
- **Purpose**: Thorough validation including edge cases, negative scenarios, boundaries.
- **Scope**: All test cases including edge cases and negative paths.
- **When to suggest**: Major release, new feature complete testing, compliance/audit needs.
- **Coverage target**: ~95%+ of total cases — P0, P1, P2, and edge cases.
- **Time budget**: 4+ hours execution.
- **Focus**: Everything including error handling, boundary values, concurrency, performance hints.

### E2E (End-to-End) Test
- **Purpose**: Validate complete user journeys across system boundaries.
- **Scope**: 5-20 scenario-based test cases following real user workflows.
- **When to suggest**: Integration testing, pre-production validation, cross-service changes.
- **Coverage target**: Complete user journeys from entry to exit.
- **Time budget**: 30 minutes - 2 hours execution.
- **Focus**: Multi-step workflows, cross-service data flow, real-world usage patterns.

### API Contract Test
- **Purpose**: Verify API endpoints meet their specification.
- **Scope**: Per-endpoint: request/response validation, status codes, error handling.
- **When to suggest**: API changes, new endpoints, OpenAPI spec provided as input.
- **Coverage target**: All endpoints × (happy path + error cases + edge cases).
- **Time budget**: 15-60 minutes execution.
- **Focus**: Request validation, response schema, status codes, auth, rate limiting.

---

## Selection Criteria

Analyze these factors to auto-suggest the appropriate suite:

| Signal | Suggests |
|---|---|
| User says "quick check" / "just verify" / "does it work" | Smoke |
| Input is a bug fix or small change description | Sanity |
| Input mentions "release" / "sprint end" / "before deploy" | Regression |
| Input is a full PRD or comprehensive feature spec | Full |
| Input describes multi-step user workflows | E2E |
| Input is an OpenAPI/Swagger spec | API Contract |
| User says "everything" / "thorough" / "complete" | Full |
| User says "critical paths only" | Smoke |
| CI/CD pipeline context | Smoke (gate) + targeted Regression |

### Combo Suggestions

Sometimes recommend multiple suites organized by phase:
- **Pre-merge**: Smoke + Sanity (for changed area)
- **Pre-release**: Smoke + Regression + E2E
- **New feature launch**: Full + E2E
- **Hotfix**: Smoke + Sanity (for fix area)

---

## Risk-Based Prioritization

Assign priority to each test case:

| Priority | Criteria | Include in |
|---|---|---|
| **P0 — Critical** | Blocks core functionality, data loss, security | All suites |
| **P1 — High** | Major feature broken, significant UX impact | Sanity, Regression, Full, E2E |
| **P2 — Medium** | Minor feature issue, workaround exists | Regression, Full |
| **P3 — Low** | Cosmetic, edge case, rare scenario | Full only |

### Risk Assessment Factors
- **User impact**: How many users affected? How severe?
- **Business impact**: Revenue, compliance, reputation risk?
- **Change frequency**: Areas that change often need more coverage.
- **Complexity**: Complex logic = higher defect probability.
- **Dependencies**: Features with many integrations = higher risk.

---

## Suite Composition Rules

When generating test cases, organize them with suite tags so users can filter:

1. **Tag every test case** with the minimum suite it belongs to (smoke/sanity/regression/full).
2. **A smoke test is always a subset of regression**, which is always a subset of full.
3. **E2E and API Contract are orthogonal** — they can overlap with other suites.
4. **When suggesting a suite**, show the count breakdown: "Recommended: Regression (45 cases — includes 8 smoke, 15 sanity, 22 regression-specific)."
5. **Allow mix-and-match**: User should be able to say "smoke + the auth-related sanity tests."
