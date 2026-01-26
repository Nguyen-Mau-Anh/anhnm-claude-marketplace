"""Test execution handler for orchestrate-dev-test.

Runs smoke and critical SQA tests with fix loop support.
Saves all outputs to test artifacts directory.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .config import DevTestConfig


@dataclass
class TestResult:
    """Result of a test execution."""
    success: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    output: str
    error: Optional[str] = None


class TestRunner:
    """Run tests with fix loop support."""

    def __init__(self, project_root: Path, config: DevTestConfig):
        self.project_root = Path(project_root)
        self.config = config

    def run_smoke_tests(self, story_id: str) -> TestResult:
        """Run P0 smoke tests and save results."""
        smoke_config = self.config.test_execution.smoke or {}
        command = smoke_config.get("command", "npm run test:smoke")
        timeout = smoke_config.get("timeout", 600)

        # Find story-specific test scripts (check multiple locations)
        test_script_path = self._find_test_scripts(story_id, "smoke")
        if test_script_path:
            print(f"[test_runner] Found test scripts at: {test_script_path}")
            command = f"{command} -- {test_script_path}"
        else:
            print(f"[test_runner] No story-specific scripts found, running all smoke tests")

        result = self._run_tests(command, timeout)

        # Save test execution results to artifacts directory
        self._save_test_results(story_id, "smoke-p0", result)

        return result

    def run_critical_sqa_tests(self, story_id: str) -> TestResult:
        """Run P1 critical SQA tests and save results."""
        sqa_config = self.config.test_execution.critical_sqa or {}
        command = sqa_config.get("command", "npm run test:sqa:critical")
        timeout = sqa_config.get("timeout", 900)

        # Find story-specific test scripts (check multiple locations)
        test_script_path = self._find_test_scripts(story_id, "sqa/critical")
        if test_script_path:
            print(f"[test_runner] Found test scripts at: {test_script_path}")
            command = f"{command} -- {test_script_path}"
        else:
            print(f"[test_runner] No story-specific scripts found, running all critical SQA tests")

        result = self._run_tests(command, timeout)

        # Save test execution results to artifacts directory
        self._save_test_results(story_id, "critical-sqa-p1", result)

        return result

    def _find_test_scripts(self, story_id: str, test_type: str) -> Optional[Path]:
        """
        Find test scripts for a story.

        Checks in priority order:
        1. New structure: docs/test-artifacts/{story_id}/scripts/{test_type}/
        2. Legacy structure: tests/{test_type}/{story_id}/

        Args:
            story_id: Story identifier
            test_type: Test type path (e.g., "smoke", "sqa/critical")

        Returns:
            Path to test scripts directory if found, None otherwise
        """
        # Check new unified structure first
        new_path = (
            self.project_root
            / self.config.output.test_artifacts_root
            / story_id
            / self.config.output.scripts_dir
            / test_type
        )
        if new_path.exists() and any(new_path.iterdir()):
            return new_path

        # Check legacy structure
        legacy_path = self.project_root / "tests" / test_type / story_id
        if legacy_path.exists() and any(legacy_path.iterdir()):
            return legacy_path

        # Also check if files are directly in test_type dir (not in story_id subdir)
        legacy_path_alt = self.project_root / "tests" / test_type
        if legacy_path_alt.exists():
            # Look for files matching story ID pattern
            matching_files = list(legacy_path_alt.glob(f"*{story_id}*"))
            if matching_files:
                return legacy_path_alt

        return None

    def _run_tests(self, command: str, timeout: int) -> TestResult:
        """Execute test command and parse results."""
        print(f"[test_runner] Running: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout + result.stderr

            # Parse test counts from output
            tests_run, tests_passed, tests_failed = self._parse_test_output(output)

            success = result.returncode == 0 and tests_failed == 0

            return TestResult(
                success=success,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                output=output,
                error=None if success else output,
            )

        except subprocess.TimeoutExpired as e:
            return TestResult(
                success=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output=e.stdout.decode() if e.stdout else "",
                error=f"Tests timed out after {timeout}s",
            )
        except Exception as e:
            return TestResult(
                success=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output="",
                error=str(e),
            )

    def _parse_test_output(self, output: str) -> tuple[int, int, int]:
        """
        Parse test counts from various test framework outputs.

        Returns (tests_run, tests_passed, tests_failed)
        """
        import re

        # Jest pattern: "Tests: X passed, Y failed, Z total"
        jest_match = re.search(
            r'Tests:\s*(?:(\d+)\s*passed)?,?\s*(?:(\d+)\s*failed)?,?\s*(\d+)\s*total',
            output
        )
        if jest_match:
            passed = int(jest_match.group(1) or 0)
            failed = int(jest_match.group(2) or 0)
            total = int(jest_match.group(3) or 0)
            return total, passed, failed

        # Playwright pattern: "X passed, Y failed"
        playwright_match = re.search(
            r'(\d+)\s*passed.*?(\d+)\s*failed',
            output
        )
        if playwright_match:
            passed = int(playwright_match.group(1))
            failed = int(playwright_match.group(2))
            return passed + failed, passed, failed

        # Vitest pattern: "Tests: X passed, Y failed, Z total"
        vitest_match = re.search(
            r'✓\s*(\d+).*✗\s*(\d+)',
            output
        )
        if vitest_match:
            passed = int(vitest_match.group(1))
            failed = int(vitest_match.group(2))
            return passed + failed, passed, failed

        # Generic pattern: count checkmarks and X marks
        passed = len(re.findall(r'[✓✔]', output))
        failed = len(re.findall(r'[✗✘✕]', output))

        if passed or failed:
            return passed + failed, passed, failed

        # Default: assume success if no failures detected
        return 0, 0, 0

    def check_test_framework(self) -> Optional[str]:
        """Detect which test framework the project uses."""
        # Check for config files
        if (self.project_root / "jest.config.js").exists():
            return "jest"
        if (self.project_root / "jest.config.ts").exists():
            return "jest"
        if (self.project_root / "playwright.config.ts").exists():
            return "playwright"
        if (self.project_root / "playwright.config.js").exists():
            return "playwright"
        if (self.project_root / "vitest.config.ts").exists():
            return "vitest"
        if (self.project_root / "cypress.config.ts").exists():
            return "cypress"
        if (self.project_root / "cypress.config.js").exists():
            return "cypress"

        # Check package.json
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                import json
                data = json.loads(package_json.read_text())
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }

                if "jest" in deps:
                    return "jest"
                if "@playwright/test" in deps:
                    return "playwright"
                if "vitest" in deps:
                    return "vitest"
                if "cypress" in deps:
                    return "cypress"

            except Exception:
                pass

        return None

    def _save_test_results(self, story_id: str, test_type: str, result: TestResult) -> None:
        """
        Save test execution results to test artifacts directory.

        Args:
            story_id: Story identifier
            test_type: Test type (e.g., "smoke-p0", "critical-sqa-p1")
            result: Test execution result
        """
        try:
            # Create test artifacts directory structure
            test_artifacts_root = self.project_root / self.config.output.test_artifacts_root / story_id
            execution_dir = test_artifacts_root / self.config.output.execution_dir
            execution_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            # Save test report (JSON)
            report_file = execution_dir / f"{test_type}-report.json"
            report_data = {
                "test_type": test_type,
                "timestamp": timestamp,
                "success": result.success,
                "tests_run": result.tests_run,
                "tests_passed": result.tests_passed,
                "tests_failed": result.tests_failed,
                "error": result.error,
            }
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)

            # Save full test output (log)
            log_file = execution_dir / f"{test_type}-output.log"
            with open(log_file, 'w') as f:
                f.write(f"=== Test Execution: {test_type} ===\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Story ID: {story_id}\n")
                f.write(f"Success: {result.success}\n")
                f.write(f"Tests Run: {result.tests_run}\n")
                f.write(f"Tests Passed: {result.tests_passed}\n")
                f.write(f"Tests Failed: {result.tests_failed}\n")
                f.write("\n" + "=" * 70 + "\n\n")
                f.write(result.output)

            # Save timestamped run (for history)
            run_file = execution_dir / f"run-{timestamp}.json"
            run_data = {
                **report_data,
                "story_id": story_id,
                "output_truncated": result.output[:5000] if len(result.output) > 5000 else result.output,
            }
            with open(run_file, 'w') as f:
                json.dump(run_data, f, indent=2)

            print(f"[test_runner] Test results saved to: {execution_dir}")
            print(f"  - Report: {report_file.name}")
            print(f"  - Log: {log_file.name}")
            print(f"  - Run history: {run_file.name}")

        except Exception as e:
            print(f"[test_runner] Warning: Could not save test results: {e}")
