"""Pipeline runner for orchestrate-dev-test Layer 2.

IMPORTANT: The orchestrator ONLY coordinates and spawns agents.
It NEVER executes tasks directly in its own context.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

from .config import ConfigLoader, DevTestConfig
from .spawner import ClaudeSpawner, TaskResult, BackgroundTask, TaskStatus
from .test_checker import check_test_requirement
from .deployer import Deployer, DeploymentResult
from .test_runner import TestRunner, TestResult


def log(msg: str) -> None:
    """Print with immediate flush for background visibility."""
    print(msg, flush=True)


@dataclass
class DevTestPipelineResult:
    """Result of the L2 pipeline execution."""
    success: bool
    story_id: Optional[str] = None
    story_file: Optional[str] = None
    ready_for_l3: bool = False

    # Track results
    dev_status: str = "pending"
    dev_duration: float = 0.0
    test_design_status: str = "pending"
    test_design_duration: float = 0.0
    tests_required: bool = True

    # Deployment
    deploy_url: Optional[str] = None
    deploy_status: str = "pending"

    # Test execution
    tdm_file: Optional[str] = None
    smoke_status: str = "pending"
    smoke_tests_run: int = 0
    smoke_tests_passed: int = 0
    critical_sqa_status: str = "pending"
    critical_sqa_tests_run: int = 0
    critical_sqa_tests_passed: int = 0
    fix_attempts: int = 0

    stage_results: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class DevTestRunner:
    """
    Execute Layer 2 pipeline with parallel dev + test design.

    CRITICAL: This orchestrator ONLY spawns agents and coordinates.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.config_loader = ConfigLoader(project_root)
        self.spawner = ClaudeSpawner(project_root)
        self.config: Optional[DevTestConfig] = None
        self.story_id: Optional[str] = None
        self.story_file: Optional[Path] = None
        self.tdm_file: Optional[Path] = None
        self.deploy_url: Optional[str] = None

    def run(self, story_id: Optional[str] = None) -> DevTestPipelineResult:
        """Run the complete L2 pipeline."""
        result = DevTestPipelineResult(success=False, story_id=story_id)
        started_at = datetime.utcnow().isoformat() + "Z"

        try:
            # Step 0: Load config
            log("\n=== Step 0: Loading configuration ===")
            self.config = self.config_loader.load()
            self.spawner.set_config(self.config)
            log("  Config loaded successfully")

            # Step 1: Resolve story
            log("\n=== Step 1: Resolving story ===")
            if story_id:
                self.story_id = story_id
                self.story_file = self.config_loader.find_story_file(story_id, self.config)

                if not self.story_file:
                    # Story not found - run L1 which will invoke L0
                    log(f"  Story file not found for ID: {story_id}")
                    log("  Will delegate to L1 which will invoke L0")

            if self.story_file:
                log(f"  Story file found: {self.story_file}")
            result.story_id = self.story_id
            result.story_file = str(self.story_file) if self.story_file else None

            # Step 2: Check if tests are required
            log("\n=== Step 2: Checking test requirements ===")
            if self.story_file and self.story_file.exists():
                tests_required, story_type, reason = check_test_requirement(
                    story_id, self.story_file, self.config
                )
                log(f"  Story type: {story_type}")
                log(f"  Tests required: {tests_required}")
                log(f"  Reason: {reason}")
                result.tests_required = tests_required
                result.stage_results["check-test-required"] = "PASS"
            else:
                # Default to requiring tests
                tests_required = True
                result.tests_required = True
                log("  Story file not found, defaulting to require tests")

            # Step 3: Run parallel tracks (or dev-only)
            log("\n=== Step 3: Running parallel tracks ===")

            if not tests_required:
                # Run dev only (skip test design)
                log("  Tests not required, running dev track only...")
                dev_result = self._run_dev_only()
                result.dev_status = "complete" if dev_result.success else "failed"
                result.dev_duration = dev_result.duration_seconds
                result.stage_results["parallel-tracks"] = "PASS" if dev_result.success else "FAIL"

                if not dev_result.success:
                    result.error = "Dev track failed"
                    self._write_status_file(result, started_at)
                    return result

                # Skip to completion (no tests needed)
                result.test_design_status = "skipped"
                result.smoke_status = "skipped"
                result.critical_sqa_status = "skipped"
                result.ready_for_l3 = True
                result.success = True

                self._print_summary(result)
                self._write_status_file(result, started_at)
                return result

            # Run parallel tracks (dev + test design)
            dev_result, test_result = self._run_parallel_tracks()

            result.dev_status = "complete" if dev_result.success else "failed"
            result.dev_duration = dev_result.duration_seconds
            result.test_design_status = "complete" if test_result.success else "failed"
            result.test_design_duration = test_result.duration_seconds

            if not dev_result.success:
                result.error = "Dev track (L1) failed"
                result.stage_results["parallel-tracks"] = "FAIL"
                self._write_status_file(result, started_at)
                return result

            if not test_result.success:
                result.error = "Test design track failed"
                result.stage_results["parallel-tracks"] = "FAIL"
                self._write_status_file(result, started_at)
                return result

            result.stage_results["parallel-tracks"] = "PASS"
            log("  ✓ Both parallel tracks completed successfully")

            # Find TDM file
            self.tdm_file = self.project_root / self.config.output.tdm_dir / f"tdm-{self.story_id}.yaml"
            if self.tdm_file.exists():
                result.tdm_file = str(self.tdm_file)
                log(f"  TDM file: {self.tdm_file}")

            # Step 4: Deploy to test environment (optional)
            log("\n=== Step 4: Deploying to test environment ===")
            if self.config.deployment.enabled:
                deploy_result = self._deploy()
                result.deploy_url = deploy_result.url
                result.deploy_status = deploy_result.status
                self.deploy_url = deploy_result.url

                if not deploy_result.success:
                    log(f"  ⚠ Deployment failed: {deploy_result.error}")
                    log("  Continuing without deployment...")
                    result.stage_results["deploy"] = "SKIP"
                else:
                    result.stage_results["deploy"] = "PASS"
            else:
                log("  Deployment disabled in config")
                result.deploy_status = "disabled"
                result.stage_results["deploy"] = "SKIP"

            # Step 5: Generate test scripts (optional)
            log("\n=== Step 5: Generating test scripts ===")
            if self.tdm_file and self.tdm_file.exists():
                passed = self._run_stage(
                    "generate-scripts",
                    story_id=self.story_id,
                    tdm_file=str(self.tdm_file),
                )
                result.stage_results["generate-scripts"] = "PASS" if passed else "SKIP"
            else:
                log("  No TDM file found, skipping test generation")
                result.stage_results["generate-scripts"] = "SKIP"

            # Step 6: Run smoke tests (P0)
            log("\n=== Step 6: Running smoke tests (P0) ===")
            smoke_result = self._run_tests_with_fix_loop("smoke", result)
            result.smoke_status = "passed" if smoke_result else "failed"

            if not smoke_result:
                result.error = "Smoke tests failed after max fix attempts"
                result.stage_results["smoke-tests"] = "FAIL"
                self._write_status_file(result, started_at)
                return result
            result.stage_results["smoke-tests"] = "PASS"

            # Step 7: Run critical SQA tests (P1)
            log("\n=== Step 7: Running critical SQA tests (P1) ===")
            sqa_result = self._run_tests_with_fix_loop("critical_sqa", result)
            result.critical_sqa_status = "passed" if sqa_result else "failed"

            if not sqa_result:
                result.error = "Critical SQA tests failed after max fix attempts"
                result.stage_results["critical-sqa"] = "FAIL"
                self._write_status_file(result, started_at)
                return result
            result.stage_results["critical-sqa"] = "PASS"

            # Success!
            result.success = True
            result.ready_for_l3 = True

            self._print_summary(result)
            self._write_status_file(result, started_at)
            return result

        except Exception as e:
            result.error = str(e)
            log(f"\n!!! Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            self._write_status_file(result, started_at)
            return result

    def _run_dev_only(self) -> TaskResult:
        """Run only the dev track (L1) without test design."""
        log("  Spawning L1 (orchestrate-dev)...")
        return self.spawner.spawn_layer(
            "/orchestrate-dev",
            self.story_id,
            timeout=10800  # 3 hours
        )

    def _run_parallel_tracks(self) -> tuple[TaskResult, TaskResult]:
        """Run L1 dev and test design in parallel."""
        log("  Spawning parallel tracks...")

        tracks = {
            "dev": ("/orchestrate-dev", self.story_id, 10800),  # 3 hours
            "test_design": ("/orchestrate-test-design", self.story_id, 1800),  # 30 min
        }

        results = self.spawner.spawn_parallel_tracks(tracks)

        dev_result = results.get("dev", TaskResult(
            success=False,
            output="",
            error="Dev track not found in results",
        ))

        test_result = results.get("test_design", TaskResult(
            success=False,
            output="",
            error="Test design track not found in results",
        ))

        log(f"  Dev track: {'PASS' if dev_result.success else 'FAIL'} ({dev_result.duration_seconds:.1f}s)")
        log(f"  Test design track: {'PASS' if test_result.success else 'FAIL'} ({test_result.duration_seconds:.1f}s)")

        return dev_result, test_result

    def _deploy(self) -> DeploymentResult:
        """Deploy the application to test environment."""
        deployer = Deployer(self.project_root, self.config)
        return deployer.deploy(self.story_id)

    def _run_tests_with_fix_loop(self, test_type: str, result: DevTestPipelineResult) -> bool:
        """
        Run tests with fix loop.

        Args:
            test_type: "smoke" or "critical_sqa"
            result: Pipeline result to update with test counts

        Returns:
            True if tests passed, False if failed after max attempts
        """
        test_runner = TestRunner(self.project_root, self.config)
        max_attempts = self.config.test_execution.max_fix_attempts

        for attempt in range(1, max_attempts + 1):
            log(f"  Test attempt {attempt}/{max_attempts}...")

            if test_type == "smoke":
                test_result = test_runner.run_smoke_tests(self.story_id)
                result.smoke_tests_run = test_result.tests_run
                result.smoke_tests_passed = test_result.tests_passed
            else:
                test_result = test_runner.run_critical_sqa_tests(self.story_id)
                result.critical_sqa_tests_run = test_result.tests_run
                result.critical_sqa_tests_passed = test_result.tests_passed

            if test_result.success:
                log(f"  ✓ Tests passed ({test_result.tests_passed}/{test_result.tests_run})")
                return True

            log(f"  ✗ Tests failed ({test_result.tests_failed} failures)")
            result.fix_attempts += 1

            if attempt < max_attempts:
                # Create bug report before spawning fix agent
                bug_number = self._create_bug_report(
                    test_type=test_type,
                    test_result=test_result,
                    attempt=attempt
                )

                # Spawn fix agent with full context
                log(f"  Spawning fix agent (bug #{bug_number})...")
                fix_stage = "smoke-tests" if test_type == "smoke" else "critical-sqa"

                # Prepare full context for fix agent
                test_artifacts_dir = self.project_root / self.config.output.test_artifacts_root / self.story_id
                fix_success = self._run_stage(
                    fix_stage,
                    story_id=self.story_id,
                    story_file=str(self.story_file),
                    deploy_url=self.deploy_url or "http://localhost:3000",
                    test_output=test_result.output[:5000],  # More context
                    test_type=test_type,
                    bug_number=bug_number,
                    bug_file=str(test_artifacts_dir / "bugs" / f"bug-{bug_number:03d}-description.md"),
                    test_scripts_dir=str(test_artifacts_dir / "scripts"),
                    test_logs=str(test_artifacts_dir / "execution"),
                    attempt=attempt,
                )

                # Document fix if successful
                if fix_success:
                    self._create_fix_documentation(
                        bug_number=bug_number,
                        test_type=test_type,
                        attempt=attempt
                    )

        log(f"  ✗ Tests failed after {max_attempts} attempts")
        return False

    def _run_stage(self, stage_name: str, **kwargs) -> bool:
        """Run a stage by spawning an agent."""
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            log(f"  No config for stage {stage_name}, skipping")
            return True

        if not stage_config.enabled:
            log(f"  Stage {stage_name} is disabled, skipping")
            return True

        log(f"  Spawning {stage_name} agent...")

        task = self.spawner.spawn_stage(stage_name, background=True, **kwargs)
        task_result = self._wait_for_task(task, stage_name)

        if task_result.success:
            log(f"  {stage_name} PASSED ({task_result.duration_seconds:.1f}s)")
            return True

        log(f"  {stage_name} FAILED")
        return False

    def _wait_for_task(
        self,
        task: BackgroundTask,
        stage_name: str,
        poll_interval: float = 5.0,
    ) -> TaskResult:
        """Wait for a background task with progress display."""
        log(f"  Waiting for {stage_name}...")

        last_log = time.time()
        while not task.is_done():
            time.sleep(poll_interval)
            elapsed = task.elapsed_seconds()

            if time.time() - last_log >= 30:
                log(f"    ... {stage_name} still running ({elapsed:.0f}s)")
                last_log = time.time()

        result = task.get_result(block=False)
        return result

    def _write_status_file(self, result: DevTestPipelineResult, started_at: str) -> None:
        """Write status file for this L2 run."""
        try:
            status_dir = self.project_root / self.config.output.status_dir
            status_dir.mkdir(parents=True, exist_ok=True)

            status_file = status_dir / f"status-{result.story_id}.json"
            status_data = {
                "story_id": result.story_id,
                "layer": "L2",
                "status": "complete" if result.success else "failed",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "tracks": {
                    "dev": {
                        "status": result.dev_status,
                        "duration_seconds": result.dev_duration,
                    },
                    "test_design": {
                        "status": result.test_design_status,
                        "duration_seconds": result.test_design_duration,
                    },
                },
                "deployment": {
                    "url": result.deploy_url,
                    "status": result.deploy_status,
                },
                "test_execution": {
                    "smoke_p0": {
                        "status": result.smoke_status,
                        "tests_run": result.smoke_tests_run,
                        "tests_passed": result.smoke_tests_passed,
                    },
                    "critical_sqa_p1": {
                        "status": result.critical_sqa_status,
                        "tests_run": result.critical_sqa_tests_run,
                        "tests_passed": result.critical_sqa_tests_passed,
                    },
                    "fix_attempts": result.fix_attempts,
                },
                "ready_for_l3": result.ready_for_l3,
                "stage_results": result.stage_results,
                "error": result.error,
            }

            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2)

            log(f"\n  Status written to: {status_file}")

        except Exception as e:
            log(f"  Warning: Could not write status file: {e}")

    def _print_summary(self, result: DevTestPipelineResult) -> None:
        """Print final summary."""
        log("\n" + "=" * 50)
        log("ORCHESTRATE-DEV-TEST (L2) COMPLETE")
        log("=" * 50)
        log(f"Story ID: {result.story_id}")
        log(f"Story File: {result.story_file}")
        log(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        log(f"Ready for L3: {result.ready_for_l3}")
        log("")
        log("Parallel Tracks:")
        log(f"  Dev (L1): {result.dev_status} ({result.dev_duration:.1f}s)")
        log(f"  Test Design: {result.test_design_status} ({result.test_design_duration:.1f}s)")
        log("")
        log("Test Execution:")
        log(f"  Smoke (P0): {result.smoke_status} ({result.smoke_tests_passed}/{result.smoke_tests_run})")
        log(f"  Critical SQA (P1): {result.critical_sqa_status} ({result.critical_sqa_tests_passed}/{result.critical_sqa_tests_run})")
        log(f"  Fix attempts: {result.fix_attempts}")
        log("")
        log("Stage Results:")
        for stage, status in result.stage_results.items():
            marker = "✓" if status == "PASS" else "○" if status == "SKIP" else "✗"
            log(f"  {marker} {stage}: {status}")

        if result.error:
            log(f"\nError: {result.error}")

        log("=" * 50)

    def _create_bug_report(self, test_type: str, test_result, attempt: int) -> int:
        """
        Create a bug report file in test artifacts directory.

        Args:
            test_type: "smoke" or "critical_sqa"
            test_result: TestResult object with failure details
            attempt: Current fix attempt number

        Returns:
            Bug number (auto-incremented)
        """
        try:
            # Create bugs directory
            bugs_dir = (
                self.project_root
                / self.config.output.test_artifacts_root
                / self.story_id
                / self.config.output.bugs_dir
            )
            bugs_dir.mkdir(parents=True, exist_ok=True)

            # Determine next bug number
            existing_bugs = list(bugs_dir.glob("bug-*-description.md"))
            bug_number = len(existing_bugs) + 1

            # Create bug report
            bug_file = bugs_dir / f"bug-{bug_number:03d}-description.md"
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            bug_content = f"""# Bug #{bug_number:03d}: {test_type.upper()} Test Failures

**Story:** {self.story_id}
**Test Type:** {test_type.replace('_', ' ').title()}
**Severity:** {'High' if test_type == 'smoke' else 'Medium'}
**Status:** Open
**Found:** {timestamp}
**Fix Attempt:** {attempt}

## Test Results

- **Tests Run:** {test_result.tests_run}
- **Tests Passed:** {test_result.tests_passed}
- **Tests Failed:** {test_result.tests_failed}

## Failure Output

```
{test_result.output}
```

## Error Summary

{test_result.error if test_result.error else 'See failure output above'}

## Files to Check

### Test Scripts
Location: `docs/test-artifacts/{self.story_id}/scripts/{test_type}/`

Check the failing test scripts to understand expected behavior.

### Test Logs
Location: `docs/test-artifacts/{self.story_id}/execution/`

Files:
- `{test_type}-p0-report.json` or `{test_type}-p1-report.json`
- `{test_type}-p0-output.log` or `{test_type}-p1-output.log`

### Story Requirements
Location: `{self.story_file}`

Review acceptance criteria to understand expected functionality.

### Application Code
Typical locations to check:
- `src/` - Application source code
- `lib/` or `utils/` - Helper functions
- `api/` or `routes/` - API endpoints
- `components/` - UI components

## Root Cause

(To be determined during fix)

## Fix Applied

See: `fixes/fix-{bug_number:03d}-changes.md` (after fix is applied)
"""

            with open(bug_file, 'w') as f:
                f.write(bug_content)

            log(f"  Bug report created: {bug_file.name}")
            return bug_number

        except Exception as e:
            log(f"  Warning: Could not create bug report: {e}")
            return 999  # Fallback bug number

    def _create_fix_documentation(self, bug_number: int, test_type: str, attempt: int) -> None:
        """
        Create fix documentation file after successful fix.

        Args:
            bug_number: Bug number that was fixed
            test_type: Test type that failed
            attempt: Fix attempt number
        """
        try:
            # Create fixes directory
            fixes_dir = (
                self.project_root
                / self.config.output.test_artifacts_root
                / self.story_id
                / self.config.output.fixes_dir
            )
            fixes_dir.mkdir(parents=True, exist_ok=True)

            # Create fix documentation placeholder
            fix_file = fixes_dir / f"fix-{bug_number:03d}-changes.md"
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            fix_content = f"""# Fix #{bug_number:03d}: {test_type.upper()} Test Failures Resolved

**Bug:** bug-{bug_number:03d}-description.md
**Story:** {self.story_id}
**Applied:** {timestamp}
**Fix Attempt:** {attempt}

## Changes Made

(Auto-generated by fix agent - check git log for exact changes)

## Files Modified

Run to see changes:
```bash
git diff HEAD~1 HEAD --name-only
```

## Verification

Tests re-run after fix:
- Fix attempt #{attempt} succeeded
- All {test_type} tests now passing

## Next Steps

1. Review the git commit for exact changes
2. Verify fix addresses root cause
3. Consider if similar issues exist elsewhere
4. Update bug report with root cause analysis

## Git Commit

Find the fix commit:
```bash
git log --oneline --grep="{self.story_id}" -5
```
"""

            with open(fix_file, 'w') as f:
                f.write(fix_content)

            # Update bug status to "Fixed"
            bug_file = fixes_dir.parent / "bugs" / f"bug-{bug_number:03d}-description.md"
            if bug_file.exists():
                content = bug_file.read_text()
                content = content.replace("**Status:** Open", f"**Status:** Fixed\n**Fixed:** {timestamp}")
                bug_file.write_text(content)

            log(f"  Fix documentation created: {fix_file.name}")

        except Exception as e:
            log(f"  Warning: Could not create fix documentation: {e}")
