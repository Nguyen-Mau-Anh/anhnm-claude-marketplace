"""Claude CLI spawner for autonomous agent/workflow invocation."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    """Types of tasks the orchestrator can execute."""

    CREATE_STORIES = "create_stories"
    DEVELOP_STORY = "develop_story"
    TEST_STORY = "test_story"
    REVIEW_CODE = "review_code"
    FIX_BUG = "fix_bug"


@dataclass
class TaskResult:
    """Result from a Claude CLI invocation."""

    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0


# Verified autonomy instructions from testing
AUTONOMY_INSTRUCTIONS = """
AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions.
"""

# Task-specific prompt templates (verified patterns)
TASK_PROMPTS = {
    TaskType.CREATE_STORIES: """
/bmad:bmm:agents:sm
{autonomy}
Create stories from the PRD in docs/.
Read the epics and generate story files for each story.
Output: list of created story IDs.
""",

    TaskType.DEVELOP_STORY: """
/bmad:bmm:agents:dev
{autonomy}
Implement story {story_id} following the story file tasks.
Read the story file at {story_path}.
Execute red-green-refactor cycle for each task.
Run tests to verify implementation.
Output: summary of files changed and test results.
""",

    TaskType.TEST_STORY: """
/bmad:bmm:agents:tea
Apply knowledge from /bmad:bmm:workflows:testarch-test-design
{autonomy}
Test story {story_id} with comprehensive coverage.
Generate unit tests and integration tests.
Run all tests and report results.
Output: test results summary with pass/fail counts.
""",

    TaskType.REVIEW_CODE: """
/bmad:bmm:agents:dev
Execute /bmad:bmm:workflows:code-review in YOLO mode
{autonomy}
Review story {story_id} implementation.
Find at least 3 potential issues.
Output: findings in structured format with severity.
""",

    TaskType.FIX_BUG: """
/bmad:bmm:agents:dev
{autonomy}
Fix bug in story {story_id}: {bug_description}
Apply fix and run tests to verify.
Output: fix summary and test results.
""",
}


class ClaudeSpawner:
    """
    Spawn Claude CLI processes for autonomous task execution.

    Uses verified autonomy patterns from testing:
    - Natural language autonomy instructions
    - Agent + workflow contextual chaining
    - Safe subprocess spawning with argument list (no shell injection)
    """

    def __init__(
        self,
        project_root: Path,
        timeout_seconds: int = 600,  # 10 minutes default
    ):
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds

    def build_prompt(
        self,
        task_type: TaskType,
        **kwargs,
    ) -> str:
        """Build the prompt for a task with autonomy instructions."""
        template = TASK_PROMPTS.get(task_type)
        if not template:
            raise ValueError(f"Unknown task type: {task_type}")

        # Insert autonomy instructions
        kwargs["autonomy"] = AUTONOMY_INSTRUCTIONS

        # Format the template
        return template.format(**kwargs).strip()

    async def spawn_async(
        self,
        task_type: TaskType,
        **kwargs,
    ) -> TaskResult:
        """
        Spawn a Claude CLI process asynchronously.

        Uses asyncio.create_subprocess_exec with argument list for safety.
        Returns TaskResult with output and success status.
        """
        import time

        prompt = self.build_prompt(task_type, **kwargs)

        # Build command as list (safe - no shell injection)
        cmd = ["claude", "--print", "-p", prompt]

        start_time = time.time()

        try:
            # Use create_subprocess_exec (safer than shell=True)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_seconds,
            )

            duration = time.time() - start_time

            return TaskResult(
                success=proc.returncode == 0,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else None,
                exit_code=proc.returncode or 0,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            proc.kill()
            duration = time.time() - start_time
            return TaskResult(
                success=False,
                output="",
                error=f"Task timed out after {self.timeout_seconds} seconds",
                exit_code=-1,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_seconds=duration,
            )

    def spawn_sync(
        self,
        task_type: TaskType,
        **kwargs,
    ) -> TaskResult:
        """
        Spawn a Claude CLI process synchronously.

        Uses subprocess.run with argument list for safety (no shell=True).
        For single-threaded prototype execution.
        """
        import time

        prompt = self.build_prompt(task_type, **kwargs)

        # Build command as list (safe - no shell injection)
        cmd = ["claude", "--print", "-p", prompt]

        start_time = time.time()

        try:
            # Use subprocess.run with list args (safe, no shell injection)
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            duration = time.time() - start_time

            return TaskResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.stderr else None,
                exit_code=result.returncode,
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TaskResult(
                success=False,
                output="",
                error=f"Task timed out after {self.timeout_seconds} seconds",
                exit_code=-1,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_seconds=duration,
            )
