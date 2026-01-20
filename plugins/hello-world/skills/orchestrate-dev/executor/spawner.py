"""Claude CLI spawner for isolated agent execution."""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class TaskType(str, Enum):
    """Types of tasks for Layer 1."""
    CREATE_STORY = "create_story"
    VALIDATE_STORY = "validate_story"
    DEVELOP_STORY = "develop_story"
    CODE_REVIEW = "code_review"
    FIX_LINT = "fix_lint"
    FIX_TYPECHECK = "fix_typecheck"
    FIX_TESTS = "fix_tests"


@dataclass
class TaskResult:
    """Result from a Claude CLI invocation."""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0


# Autonomy instructions to prevent interactive prompts
AUTONOMY_INSTRUCTIONS = """
AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions.
"""

# Task-specific prompt templates
TASK_PROMPTS = {
    TaskType.CREATE_STORY: """
/bmad:bmm:workflows:create-story
{autonomy}
Create the next story from the epics/backlog.
Read the epics file and generate the story file.
Output: story_id and story_file path.
""",

    TaskType.VALIDATE_STORY: """
/bmad:bmm:workflows:implementation-readiness
{autonomy}
Validate story is ready for development.
Story file: {story_file}

Check:
- Clear acceptance criteria
- Well-defined tasks
- Dependencies documented

Output: PASS or FAIL with details.
""",

    TaskType.DEVELOP_STORY: """
/bmad:bmm:workflows:dev-story
{autonomy}
Implement the story following tasks in the story file.
Story file: {story_file}
Story ID: {story_id}

Follow red-green-refactor cycle for each task.
Output: List of files changed and implementation summary.
""",

    TaskType.CODE_REVIEW: """
/bmad:bmm:workflows:code-review
{autonomy}
Review the implemented code for story {story_id}.
Files changed: {files_changed}

Review for:
- Code quality
- Security issues
- Performance
- Architecture compliance

Output: Findings with severity levels.
""",

    TaskType.FIX_LINT: """
/bmad:bmm:agents:dev
{autonomy}
Fix the following lint errors:

{errors}

Apply fixes and ensure code passes linting.
Output: Summary of fixes applied.
""",

    TaskType.FIX_TYPECHECK: """
/bmad:bmm:agents:dev
{autonomy}
Fix the following TypeScript type errors:

{errors}

Apply fixes and ensure code passes type checking.
Output: Summary of fixes applied.
""",

    TaskType.FIX_TESTS: """
/bmad:bmm:agents:dev
{autonomy}
Fix the following failing tests:

{errors}

Fix either the tests or the implementation as appropriate.
Output: Summary of fixes applied.
""",
}


class ClaudeSpawner:
    """
    Spawn Claude CLI processes for isolated task execution.

    Each spawn creates a new Claude process via `claude --print`,
    ensuring full context isolation from the parent.
    """

    def __init__(
        self,
        project_root: Path,
        timeout_seconds: int = 600,
    ):
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds

    def build_prompt(self, task_type: TaskType, **kwargs) -> str:
        """Build the prompt for a task with autonomy instructions."""
        template = TASK_PROMPTS.get(task_type)
        if not template:
            raise ValueError(f"Unknown task type: {task_type}")

        kwargs["autonomy"] = AUTONOMY_INSTRUCTIONS
        return template.format(**kwargs).strip()

    def spawn(self, task_type: TaskType, **kwargs) -> TaskResult:
        """
        Spawn a Claude CLI process synchronously.

        Uses subprocess.run with argument list for safety.
        Returns TaskResult with output and success status.
        """
        prompt = self.build_prompt(task_type, **kwargs)

        # Build command as list (safe - no shell injection)
        cmd = ["claude", "--print", "-p", prompt]

        start_time = time.time()

        try:
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
