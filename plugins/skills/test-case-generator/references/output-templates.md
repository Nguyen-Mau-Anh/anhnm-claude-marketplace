# Output Format Templates

## Table of Contents
- [Format Selection Guide](#format-selection-guide)
- [Structured Markdown](#structured-markdown)
- [Gherkin (BDD)](#gherkin-bdd)
- [Executable Test Code](#executable-test-code)
- [Lightweight Checklist](#lightweight-checklist)
- [Test Matrix](#test-matrix)

---

## Format Selection Guide

| Context Signal | Recommended Format |
|---|---|
| PRD/requirements input, no code context | Structured Markdown |
| User stories with acceptance criteria | Gherkin |
| Codebase present, specific framework detected | Executable Test Code |
| Quick ad-hoc check, informal request | Lightweight Checklist |
| Feature with many input combinations | Test Matrix + chosen format |
| API spec input | Executable Test Code (API tests) or Structured Markdown |

When uncertain, default to **Structured Markdown** — it's universally readable and easy to convert later.

---

## Structured Markdown

Use for requirements-based test case documentation.

### Single Test Case

```markdown
### TC-{MODULE}-{NNN}: {Brief descriptive title}

| Field | Value |
|---|---|
| **Priority** | P0 / P1 / P2 / P3 |
| **Suite** | Smoke / Sanity / Regression / Full |
| **Type** | Functional / Negative / Boundary / E2E / Performance |
| **Preconditions** | {What must be true before test runs} |

**Steps:**
1. {Action step}
2. {Action step}
3. {Action step}

**Expected Result:**
- {Observable outcome}

**Test Data:**
- {Any specific data needed, if applicable}
```

### Summary Table (for overview)

```markdown
| ID | Title | Priority | Suite | Type |
|---|---|---|---|---|
| TC-AUTH-001 | Valid login with email/password | P0 | Smoke | Functional |
| TC-AUTH-002 | Login with invalid password | P1 | Sanity | Negative |
| TC-AUTH-003 | Login with SQL injection attempt | P1 | Regression | Security |
```

---

## Gherkin (BDD)

Use when input is user stories or when team uses BDD frameworks (Cucumber, SpecFlow, Behave).

```gherkin
@smoke @P0 @auth
Feature: User Authentication
  As a registered user
  I want to log in to the application
  So that I can access my account

  Background:
    Given the application is running
    And the login page is displayed

  @happy-path
  Scenario: Successful login with valid credentials
    Given a registered user with email "user@example.com"
    When the user enters email "user@example.com"
    And the user enters password "ValidPass123"
    And the user clicks the login button
    Then the user should be redirected to the dashboard
    And a welcome message should be displayed

  @negative
  Scenario: Login with invalid password
    Given a registered user with email "user@example.com"
    When the user enters email "user@example.com"
    And the user enters password "WrongPassword"
    And the user clicks the login button
    Then an error message "Invalid credentials" should be displayed
    And the user should remain on the login page

  @boundary
  Scenario Outline: Login with boundary password lengths
    When the user enters email "user@example.com"
    And the user enters password "<password>"
    And the user clicks the login button
    Then the result should be "<result>"

    Examples:
      | password | result |
      | abc      | Error: minimum 8 characters |
      | 12345678 | Accepted (if valid) |
```

### Gherkin Tag Conventions
- Suite tags: `@smoke`, `@sanity`, `@regression`, `@full`
- Priority tags: `@P0`, `@P1`, `@P2`, `@P3`
- Type tags: `@happy-path`, `@negative`, `@boundary`, `@security`, `@e2e`
- Module tags: `@auth`, `@payment`, `@profile`, etc.

---

## Executable Test Code

Adapt to detected stack. Examples below for common frameworks.

### JUnit 5 (Java)

```java
@Tag("smoke")
@Tag("P0")
@DisplayName("Authentication Tests")
class AuthenticationTest {

    @Test
    @DisplayName("TC-AUTH-001: Valid login with email/password")
    void shouldLoginWithValidCredentials() {
        // Arrange
        var request = LoginRequest.of("user@example.com", "ValidPass123");

        // Act
        var response = authService.login(request);

        // Assert
        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getToken()).isNotBlank();
    }

    @Test
    @Tag("negative")
    @DisplayName("TC-AUTH-002: Login with invalid password")
    void shouldRejectInvalidPassword() {
        // Arrange
        var request = LoginRequest.of("user@example.com", "WrongPassword");

        // Act & Assert
        assertThrows(AuthenticationException.class,
            () -> authService.login(request));
    }

    @ParameterizedTest
    @Tag("boundary")
    @CsvSource({"'ab', false", "'12345678', true", "'a'.repeat(256), false"})
    @DisplayName("TC-AUTH-003: Password length boundaries")
    void shouldValidatePasswordLength(String password, boolean shouldPass) {
        // ...
    }
}
```

### Pytest (Python)

```python
import pytest

class TestAuthentication:
    """Authentication Tests"""

    @pytest.mark.smoke
    @pytest.mark.P0
    def test_valid_login(self, auth_service):
        """TC-AUTH-001: Valid login with email/password"""
        result = auth_service.login("user@example.com", "ValidPass123")
        assert result.success is True
        assert result.token is not None

    @pytest.mark.sanity
    @pytest.mark.negative
    def test_invalid_password(self, auth_service):
        """TC-AUTH-002: Login with invalid password"""
        with pytest.raises(AuthenticationError):
            auth_service.login("user@example.com", "WrongPassword")

    @pytest.mark.regression
    @pytest.mark.parametrize("password,expected", [
        ("ab", False),
        ("12345678", True),
        ("a" * 256, False),
    ])
    def test_password_length_boundary(self, auth_service, password, expected):
        """TC-AUTH-003: Password length boundaries"""
        # ...
```

### Playwright (E2E)

```typescript
import { test, expect } from '@playwright/test';

test.describe('Authentication @smoke @P0', () => {
  test('TC-AUTH-001: Valid login with email/password', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[data-testid="email"]', 'user@example.com');
    await page.fill('[data-testid="password"]', 'ValidPass123');
    await page.click('[data-testid="login-button"]');
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('.welcome-message')).toBeVisible();
  });
});
```

---

## Lightweight Checklist

Use for quick informal checks or when user needs a simple list.

```markdown
## Smoke Test Checklist — {Feature Name}

- [ ] **Login**: User can log in with valid credentials
- [ ] **Main page load**: Dashboard renders with data
- [ ] **Core action**: User can {primary action}
- [ ] **Logout**: User can log out successfully
- [ ] **Error state**: Application shows error page on server failure
```

---

## Test Matrix

Use when a feature has multiple input combinations. Combine with any format above.

```markdown
## Test Matrix: Payment Processing

| Payment Method | Amount | Currency | User Type | Expected | Priority | Suite |
|---|---|---|---|---|---|---|
| Credit Card | $10.00 | USD | Regular | Success | P0 | Smoke |
| Credit Card | $0.00 | USD | Regular | Reject | P1 | Sanity |
| Credit Card | $10,000 | USD | Regular | Review flag | P2 | Regression |
| PayPal | $10.00 | EUR | Guest | Success | P1 | Sanity |
| Credit Card | -$5.00 | USD | Regular | Reject | P1 | Regression |
| Bank Transfer | $10.00 | USD | Business | Success | P1 | Regression |
```
