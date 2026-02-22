---
name: test-case-generator
description: >
  Generate comprehensive test cases from requirements, PRDs, user stories, API specs, or existing code.
  Automatically suggests the right test suite (smoke, sanity, regression, full, E2E, API contract)
  based on context and user intent. Outputs in the most appropriate format — structured markdown,
  Gherkin (BDD), executable test code (JUnit, pytest, Playwright, etc.), or checklists.
  Use when the user asks to: create test cases, generate tests, write test plans, build test suites,
  define QA scenarios, create acceptance tests, or any test generation task from specifications or code.
---

# Test Case Generator

Generate test cases from any input source, with intelligent suite selection and format adaptation.

## Workflow

### 1. Analyze Input

Read the provided input and classify it:

| Input Type | Key Indicators |
|---|---|
| PRD / Requirements doc | Numbered requirements, feature descriptions, acceptance criteria sections |
| User stories | "As a [role], I want...", Given/When/Then, acceptance criteria |
| API spec | OpenAPI/Swagger YAML/JSON, endpoint definitions, schema objects |
| Code | Source files, function signatures, class definitions |
| Bug fix / Change description | Ticket reference, "fixed X", diff or change summary |
| Informal request | Conversational, "test the login", "check if search works" |

Extract testable requirements from the input:
- Functional requirements (what the system should do)
- Business rules and constraints
- Input/output specifications
- State transitions and workflows
- Error handling expectations
- Non-functional hints (performance, security)

### 2. Suggest Test Suite

Based on the input analysis, recommend the appropriate test suite(s). Consider:

- **User's explicit request**: If they say "smoke test" or "full coverage", honor it.
- **Input scope**: A full PRD → Full suite. A bug fix → Sanity suite.
- **User intent signals**: "quick check" → Smoke. "before release" → Regression.

Present the recommendation with a breakdown:
```
Recommended: Regression Suite (42 test cases)
├── Smoke (8 cases) — critical path coverage
├── Sanity (12 cases) — changed area + dependencies
└── Regression-specific (22 cases) — broader feature coverage

Run `smoke` for quick validation, or `regression` for pre-release confidence.
```

If unclear, ask the user which suite fits their situation.

For detailed suite definitions and selection criteria, consult [references/suite-strategy.md](references/suite-strategy.md).

### 3. Design Test Cases

Apply test design techniques appropriate to each requirement:

- **Input fields with ranges** → Equivalence partitioning + boundary value analysis
- **Multiple conditions** → Decision table testing
- **Stateful workflows** → State transition testing
- **User-facing inputs** → Always include negative tests
- **Security-sensitive features** → Include security-aware tests

For each test case, assign:
- **Priority** (P0-P3) based on risk and user impact
- **Suite tag** (smoke/sanity/regression/full) — the minimum suite it belongs to
- **Type** (functional/negative/boundary/security/E2E/performance)

For detailed techniques and examples, consult [references/test-design-techniques.md](references/test-design-techniques.md).

### 4. Choose Output Format

Select format based on context:

| Context | Format |
|---|---|
| No code context, general documentation | Structured Markdown tables |
| User stories as input, BDD team | Gherkin scenarios |
| Codebase present, framework detected | Executable test code |
| Quick informal request | Lightweight checklist |
| Many input combinations | Test matrix + primary format |

Detect tech stack from:
- Project files (pom.xml → Java, package.json → JS/TS, requirements.txt → Python)
- Existing test files (patterns and frameworks already in use)
- User mention of specific frameworks

For format templates and examples, consult [references/output-templates.md](references/output-templates.md).

### 5. Generate and Organize

Output structure:
1. **Summary**: Input analysis, suite recommendation, coverage stats.
2. **Test cases**: Organized by module/feature, tagged with priority and suite.
3. **Traceability matrix**: Map requirements → test cases (for PRD/requirements input).
4. **Coverage gaps**: Flag any requirements without test coverage.

### 6. Offer Refinement

After generating, offer to:
- Adjust suite scope (add/remove test cases for a different suite level)
- Change output format (convert markdown to Gherkin or code)
- Add depth to specific areas (more edge cases, more negative tests)
- Generate test data suggestions
- Prioritize differently based on user feedback

## Stack Detection Hints

When generating executable test code, match the project's existing patterns:

| Detected Stack | Test Framework | Assertion Style |
|---|---|---|
| Java + Spring Boot | JUnit 5 + Mockito | AssertJ preferred |
| Java + Maven/Gradle | JUnit 5 | AssertJ or Hamcrest |
| Python + Django/Flask | pytest | pytest assertions |
| Node.js + Express | Jest or Vitest | expect() |
| TypeScript + React | Jest/Vitest + Testing Library | expect() |
| Frontend E2E | Playwright | expect() with locators |
| Go | testing package | standard assertions |
| Rust | built-in #[test] | assert! macros |

If existing tests are found in the project, match their style (imports, naming conventions, assertion library, directory structure).

## Key Principles

- **No happy-path-only tests**: Every feature gets at least one negative test case.
- **Prioritize ruthlessly**: Not everything is P0. A realistic priority distribution: ~10% P0, ~30% P1, ~40% P2, ~20% P3.
- **Test independence**: Each test case should be runnable independently (no ordering dependency).
- **Descriptive names**: Test case titles should describe the scenario, not the implementation.
- **Traceable**: Every test case links back to its source requirement when requirements are provided.
