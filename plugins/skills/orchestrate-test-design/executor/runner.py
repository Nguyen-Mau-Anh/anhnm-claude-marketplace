"""Pipeline runner for orchestrate-test-design.

IMPORTANT: The orchestrator ONLY coordinates and spawns agents.
It NEVER executes tasks directly in its own context.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

from .config import ConfigLoader, TestDesignConfig, StageConfig
from .spawner import ClaudeSpawner, TaskResult, BackgroundTask, TaskStatus


def log(msg: str) -> None:
    """Print with immediate flush for background visibility."""
    print(msg, flush=True)


@dataclass
class TestDesignResult:
    """Result of the test design pipeline execution."""
    success: bool
    story_id: Optional[str] = None
    story_file: Optional[str] = None
    tdm_file: Optional[str] = None
    test_cases_count: Dict[str, int] = field(default_factory=dict)
    validation_attempts: int = 0
    validation_passed: bool = False
    stage_results: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class TestDesignRunner:
    """
    Execute test design pipeline stages.

    CRITICAL: This orchestrator ONLY spawns agents and coordinates.
    It NEVER executes any design tasks in its own context.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.config_loader = ConfigLoader(project_root)
        self.spawner = ClaudeSpawner(project_root)
        self.config: Optional[TestDesignConfig] = None
        self.story_id: Optional[str] = None
        self.story_file: Optional[Path] = None
        self.tdm_file: Optional[Path] = None

    def run(self, story_id: str) -> TestDesignResult:
        """Run the complete test design pipeline."""
        result = TestDesignResult(success=False, story_id=story_id)
        started_at = datetime.utcnow().isoformat() + "Z"

        try:
            # Step 0: Load config
            log("\n=== Step 0: Loading configuration ===")
            self.config = self.config_loader.load()
            self.spawner.set_config(self.config)
            log("  Config loaded successfully")

            # Step 1: Find story file
            log("\n=== Step 1: Finding story file ===")
            self.story_id = story_id
            self.story_file = self.config_loader.find_story_file(story_id, self.config)

            if not self.story_file:
                result.error = f"Story file not found for ID: {story_id}"
                log(f"  ✗ {result.error}")
                self._write_status_file(result, started_at)
                return result

            log(f"  ✓ Story file found: {self.story_file}")
            result.story_file = str(self.story_file)

            # Create test artifacts directory structure
            test_artifacts_root = self.project_root / self.config.output.test_artifacts_root / story_id
            design_dir = test_artifacts_root / "design"
            design_dir.mkdir(parents=True, exist_ok=True)

            # Determine TDM output path (new unified structure)
            self.tdm_file = design_dir / self.config.output.tdm_file
            result.tdm_file = str(self.tdm_file)

            log(f"  Test artifacts directory: {test_artifacts_root}")
            log(f"  TDM will be saved to: {self.tdm_file}")

            # Step 2: Create TDM
            log("\n=== Step 2: Creating TDM ===")
            passed = self._run_stage(
                "create-tdm",
                story_id=story_id,
                story_file=str(self.story_file),
                tdm_output=str(self.tdm_file),
            )
            result.stage_results["create-tdm"] = "PASS" if passed else "FAIL"
            if not passed:
                result.error = "Failed to create TDM"
                self._write_status_file(result, started_at)
                return result

            # Step 3: Generate test cases
            log("\n=== Step 3: Generating test cases ===")
            passed = self._run_stage(
                "generate-test-cases",
                story_id=story_id,
                tdm_file=str(self.tdm_file),
            )
            result.stage_results["generate-test-cases"] = "PASS" if passed else "FAIL"
            if not passed:
                result.error = "Failed to generate test cases"
                self._write_status_file(result, started_at)
                return result

            # Step 4: Validate test cases (with retry loop)
            log("\n=== Step 4: Validating test cases ===")
            max_attempts = self.config.validation.max_attempts
            validation_errors = "None"

            for attempt in range(1, max_attempts + 1):
                log(f"  Validation attempt {attempt}/{max_attempts}...")
                result.validation_attempts = attempt

                passed = self._run_stage(
                    "validate",
                    story_id=story_id,
                    tdm_file=str(self.tdm_file),
                    validation_errors=validation_errors,
                )

                if passed:
                    log(f"  ✓ Validation passed on attempt {attempt}")
                    result.validation_passed = True
                    result.stage_results["validate"] = "PASS"
                    break
                else:
                    log(f"  ✗ Validation failed on attempt {attempt}")
                    # Store validation errors for next attempt
                    validation_errors = f"Attempt {attempt} failed - see TDM for issues"

                    # Write validation log
                    self._write_validation_log(story_id, attempt)

                    if attempt < max_attempts:
                        log(f"  Retrying validation...")

            if not result.validation_passed:
                result.error = f"Validation failed after {max_attempts} attempts"
                result.stage_results["validate"] = "FAIL"

            # Count test cases from TDM (if it exists)
            result.test_cases_count = self._count_test_cases()

            # Determine overall success
            result.success = result.validation_passed

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
        if task_result.error:
            error_preview = task_result.error[:300] if task_result.error else ""
            log(f"    Error: {error_preview}...")

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
        log(f"  {stage_name} completed: success={result.success}, duration={result.duration_seconds:.1f}s")

        return result

    def _count_test_cases(self) -> Dict[str, int]:
        """Count test cases by priority from TDM file."""
        counts = {
            "p0_smoke": 0,
            "p1_critical": 0,
            "p2_full": 0,
            "p3_extended": 0,
        }

        if not self.tdm_file or not self.tdm_file.exists():
            return counts

        try:
            import yaml
            with open(self.tdm_file, 'r') as f:
                tdm = yaml.safe_load(f)

            if tdm and "test_cases" in tdm:
                test_cases = tdm["test_cases"]
                if "smoke_p0" in test_cases:
                    counts["p0_smoke"] = len(test_cases["smoke_p0"])
                if "critical_sqa_p1" in test_cases:
                    counts["p1_critical"] = len(test_cases["critical_sqa_p1"])
                if "full_sqa_p2" in test_cases:
                    counts["p2_full"] = len(test_cases["full_sqa_p2"])
                if "full_sqa_p3" in test_cases:
                    counts["p3_extended"] = len(test_cases["full_sqa_p3"])

        except Exception as e:
            log(f"  Warning: Could not count test cases: {e}")

        return counts

    def _write_validation_log(self, story_id: str, attempt: int) -> None:
        """Write validation attempt log."""
        try:
            validation_dir = self.project_root / self.config.output.validation_dir / story_id
            validation_dir.mkdir(parents=True, exist_ok=True)

            log_file = validation_dir / f"attempt-{attempt}.json"
            log_data = {
                "attempt": attempt,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": "failed",
            }

            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)

        except Exception as e:
            log(f"  Warning: Could not write validation log: {e}")

    def _write_status_file(self, result: TestDesignResult, started_at: str) -> None:
        """Write status file for this test design run."""
        try:
            status_dir = self.project_root / self.config.output.status_dir
            status_dir.mkdir(parents=True, exist_ok=True)

            status_file = status_dir / f"status-{result.story_id}.json"
            status_data = {
                "story_id": result.story_id,
                "track": "test-design",
                "status": "complete" if result.success else "failed",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "outputs": {
                    "tdm_file": result.tdm_file,
                    "test_cases": result.test_cases_count,
                    "validation_attempts": result.validation_attempts,
                    "validation_passed": result.validation_passed,
                },
                "stage_results": result.stage_results,
                "error": result.error,
            }

            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2)

            log(f"\n  Status written to: {status_file}")

        except Exception as e:
            log(f"  Warning: Could not write status file: {e}")

    def _print_summary(self, result: TestDesignResult) -> None:
        """Print final summary."""
        log("\n" + "=" * 50)
        log("ORCHESTRATE-TEST-DESIGN COMPLETE")
        log("=" * 50)
        log(f"Story ID: {result.story_id}")
        log(f"Story File: {result.story_file}")
        log(f"TDM File: {result.tdm_file}")
        log(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        log("")
        log("Stage Results:")
        for stage, status in result.stage_results.items():
            marker = "✓" if status == "PASS" else "✗"
            log(f"  {marker} {stage}: {status}")

        log("")
        log("Test Cases Generated:")
        total = 0
        for priority, count in result.test_cases_count.items():
            log(f"  {priority}: {count}")
            total += count
        log(f"  Total: {total}")

        log("")
        log(
                f"Validation: {'PASSED' if result.validation_passed else 'FAILED'} "
                f"(attempts: {result.validation_attempts})"
            )

        if result.error:
            log(f"\nError: {result.error}")

        log("=" * 50)
