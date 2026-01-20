"""Pipeline runner for Layer 1 - orchestrate-dev."""

import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import ConfigLoader, DevConfig
from .spawner import ClaudeSpawner, TaskType, TaskResult


console = Console()


@dataclass
class PipelineResult:
    """Result of the entire pipeline execution."""
    success: bool
    story_id: Optional[str] = None
    story_file: Optional[str] = None
    files_changed: list[str] = field(default_factory=list)
    lint_result: str = "NOT_RUN"
    typecheck_result: str = "NOT_RUN"
    test_results: str = "NOT_RUN"
    review_findings: list[str] = field(default_factory=list)
    stage_results: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class PipelineRunner:
    """
    Execute Layer 1 pipeline stages.

    Stages:
    1. Create story (SPAWN) - if file doesn't exist
    2. Validate (SPAWN)
    3. Develop (SPAWN)
    4. Lint (DIRECT)
    5. Typecheck (DIRECT)
    6. Unit test (DIRECT)
    7. Code review (SPAWN)
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.config_loader = ConfigLoader(project_root)
        self.spawner = ClaudeSpawner(project_root)
        self.config: Optional[DevConfig] = None

    def run(self, story_id: Optional[str] = None) -> PipelineResult:
        """Run the complete pipeline."""
        result = PipelineResult(success=False)

        try:
            # Step 0: Load config
            console.print("\n[bold blue]Step 0: Loading configuration...[/bold blue]")
            self.config = self.config_loader.load()

            # Step 1: Determine story
            console.print("\n[bold blue]Step 1: Determining story...[/bold blue]")
            story_id, story_file = self._resolve_story(story_id)
            result.story_id = story_id
            result.story_file = str(story_file) if story_file else None

            if not story_file:
                result.error = "Failed to create or find story file"
                return result

            console.print(f"  Story ID: {story_id}")
            console.print(f"  Story file: {story_file}")
            result.stage_results["create-story"] = "PASS"

            # Step 2: Validate story
            console.print("\n[bold blue]Step 2: Validating story...[/bold blue]")
            if not self._run_validate(story_file, result):
                return result
            result.stage_results["validate"] = "PASS"

            # Step 3: Develop story
            console.print("\n[bold blue]Step 3: Developing story...[/bold blue]")
            if not self._run_develop(story_id, story_file, result):
                return result
            result.stage_results["develop"] = "PASS"

            # Step 4: Lint
            console.print("\n[bold blue]Step 4: Running lint...[/bold blue]")
            if not self._run_lint(result):
                return result
            result.stage_results["lint"] = "PASS"

            # Step 5: Typecheck
            console.print("\n[bold blue]Step 5: Running typecheck...[/bold blue]")
            if not self._run_typecheck(result):
                return result
            result.stage_results["typecheck"] = "PASS"

            # Step 6: Unit test
            console.print("\n[bold blue]Step 6: Running unit tests...[/bold blue]")
            if not self._run_unit_test(result):
                return result
            result.stage_results["unit-test"] = "PASS"

            # Step 7: Code review (non-blocking)
            console.print("\n[bold blue]Step 7: Running code review...[/bold blue]")
            self._run_code_review(story_id, result)
            result.stage_results["code-review"] = "PASS"

            # Success
            result.success = True
            self._print_summary(result)
            return result

        except Exception as e:
            result.error = str(e)
            console.print(f"\n[red]Pipeline failed: {e}[/red]")
            return result

    def _resolve_story(self, story_id: Optional[str]) -> tuple[Optional[str], Optional[Path]]:
        """Resolve or create story file."""
        if story_id:
            # Check if story file exists
            story_file = self.config_loader.find_story_file(story_id, self.config)
            if story_file:
                console.print(f"  [green]Found existing story file[/green]")
                return story_id, story_file

            # Story ID provided but file doesn't exist - create it
            console.print(f"  [yellow]Story file not found, creating...[/yellow]")

        # Create new story
        console.print("  [dim]Spawning create-story workflow...[/dim]")
        task_result = self.spawner.spawn(TaskType.CREATE_STORY)

        if not task_result.success:
            console.print(f"  [red]Failed to create story: {task_result.error}[/red]")
            return None, None

        # Parse story_id from output (simplified - would need better parsing)
        # For now, assume output contains "story_id: X" or similar
        output = task_result.output
        console.print(f"  [green]Story created ({task_result.duration_seconds:.1f}s)[/green]")

        # Try to find the created story
        # This is simplified - in practice would parse the output
        if story_id:
            story_file = self.config_loader.find_story_file(story_id, self.config)
            return story_id, story_file

        return story_id, None

    def _run_validate(self, story_file: Path, result: PipelineResult) -> bool:
        """Run validation stage with retry."""
        stage_config = self.config.stages.get("validate")
        max_retries = stage_config.retry.max if stage_config and stage_config.retry else 2

        for attempt in range(max_retries + 1):
            console.print(f"  [dim]Spawning validate workflow (attempt {attempt + 1})...[/dim]")

            task_result = self.spawner.spawn(
                TaskType.VALIDATE_STORY,
                story_file=str(story_file)
            )

            if task_result.success:
                console.print(f"  [green]Validation passed ({task_result.duration_seconds:.1f}s)[/green]")
                return True

            if attempt < max_retries:
                console.print(f"  [yellow]Validation failed, attempting fix...[/yellow]")
                # Spawn fix agent - for now just retry
                # In full implementation, would spawn dev agent with errors

        console.print(f"  [red]Validation failed after {max_retries + 1} attempts[/red]")
        result.error = "Validation failed"
        result.stage_results["validate"] = "FAIL"
        return False

    def _run_develop(self, story_id: str, story_file: Path, result: PipelineResult) -> bool:
        """Run development stage with retry."""
        stage_config = self.config.stages.get("develop")
        max_retries = stage_config.retry.max if stage_config and stage_config.retry else 3

        for attempt in range(max_retries + 1):
            console.print(f"  [dim]Spawning dev-story workflow (attempt {attempt + 1})...[/dim]")

            task_result = self.spawner.spawn(
                TaskType.DEVELOP_STORY,
                story_id=story_id,
                story_file=str(story_file)
            )

            if task_result.success:
                console.print(f"  [green]Development complete ({task_result.duration_seconds:.1f}s)[/green]")
                # Parse files changed from output (simplified)
                result.files_changed = ["(see output for details)"]
                return True

            if attempt < max_retries:
                console.print(f"  [yellow]Development failed, attempting fix...[/yellow]")

        console.print(f"  [red]Development failed after {max_retries + 1} attempts[/red]")
        result.error = "Development failed"
        result.stage_results["develop"] = "FAIL"
        return False

    def _run_lint(self, result: PipelineResult) -> bool:
        """Run lint stage (direct) with fix-and-retry."""
        stage_config = self.config.stages.get("lint")
        command = stage_config.command if stage_config else "npm run lint"
        max_retries = stage_config.retry.max if stage_config and stage_config.retry else 2

        for attempt in range(max_retries + 1):
            console.print(f"  [dim]Running: {command} (attempt {attempt + 1})...[/dim]")

            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if proc.returncode == 0:
                    console.print(f"  [green]Lint passed[/green]")
                    result.lint_result = "PASS"
                    return True

                errors = proc.stdout + proc.stderr
                console.print(f"  [yellow]Lint failed[/yellow]")

                if attempt < max_retries:
                    console.print(f"  [dim]Spawning dev agent to fix lint errors...[/dim]")
                    fix_result = self.spawner.spawn(TaskType.FIX_LINT, errors=errors)
                    if not fix_result.success:
                        console.print(f"  [yellow]Fix attempt failed[/yellow]")

            except subprocess.TimeoutExpired:
                console.print(f"  [red]Lint timed out[/red]")

        console.print(f"  [red]Lint failed after {max_retries + 1} attempts[/red]")
        result.lint_result = "FAIL"
        result.error = "Lint failed"
        result.stage_results["lint"] = "FAIL"
        return False

    def _run_typecheck(self, result: PipelineResult) -> bool:
        """Run typecheck stage (direct) with fix-and-retry."""
        stage_config = self.config.stages.get("typecheck")
        command = stage_config.command if stage_config else "npm run typecheck"
        max_retries = stage_config.retry.max if stage_config and stage_config.retry else 2

        for attempt in range(max_retries + 1):
            console.print(f"  [dim]Running: {command} (attempt {attempt + 1})...[/dim]")

            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=180
                )

                if proc.returncode == 0:
                    console.print(f"  [green]Typecheck passed[/green]")
                    result.typecheck_result = "PASS"
                    return True

                errors = proc.stdout + proc.stderr
                console.print(f"  [yellow]Typecheck failed[/yellow]")

                if attempt < max_retries:
                    console.print(f"  [dim]Spawning dev agent to fix type errors...[/dim]")
                    fix_result = self.spawner.spawn(TaskType.FIX_TYPECHECK, errors=errors)
                    if not fix_result.success:
                        console.print(f"  [yellow]Fix attempt failed[/yellow]")

            except subprocess.TimeoutExpired:
                console.print(f"  [red]Typecheck timed out[/red]")

        console.print(f"  [red]Typecheck failed after {max_retries + 1} attempts[/red]")
        result.typecheck_result = "FAIL"
        result.error = "Typecheck failed"
        result.stage_results["typecheck"] = "FAIL"
        return False

    def _run_unit_test(self, result: PipelineResult) -> bool:
        """Run unit test stage (direct) with fix-and-retry."""
        stage_config = self.config.stages.get("unit-test")
        command = stage_config.command if stage_config else "npm test"
        max_retries = stage_config.retry.max if stage_config and stage_config.retry else 3

        for attempt in range(max_retries + 1):
            console.print(f"  [dim]Running: {command} (attempt {attempt + 1})...[/dim]")

            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if proc.returncode == 0:
                    console.print(f"  [green]Unit tests passed[/green]")
                    result.test_results = "PASS"
                    return True

                errors = proc.stdout + proc.stderr
                console.print(f"  [yellow]Tests failed[/yellow]")

                if attempt < max_retries:
                    console.print(f"  [dim]Spawning dev agent to fix tests...[/dim]")
                    fix_result = self.spawner.spawn(TaskType.FIX_TESTS, errors=errors)
                    if not fix_result.success:
                        console.print(f"  [yellow]Fix attempt failed[/yellow]")

            except subprocess.TimeoutExpired:
                console.print(f"  [red]Tests timed out[/red]")

        console.print(f"  [red]Tests failed after {max_retries + 1} attempts[/red]")
        result.test_results = "FAIL"
        result.error = "Unit tests failed"
        result.stage_results["unit-test"] = "FAIL"
        return False

    def _run_code_review(self, story_id: str, result: PipelineResult) -> None:
        """Run code review stage (spawn, non-blocking)."""
        console.print(f"  [dim]Spawning code-review workflow...[/dim]")

        task_result = self.spawner.spawn(
            TaskType.CODE_REVIEW,
            story_id=story_id,
            files_changed=", ".join(result.files_changed)
        )

        if task_result.success:
            console.print(f"  [green]Code review complete ({task_result.duration_seconds:.1f}s)[/green]")
            # Parse findings from output (simplified)
            result.review_findings = ["See output for details"]
        else:
            console.print(f"  [yellow]Code review had issues (non-blocking)[/yellow]")
            result.review_findings = [f"Error: {task_result.error}"]

    def _print_summary(self, result: PipelineResult) -> None:
        """Print final summary."""
        table = Table(title="Pipeline Summary")
        table.add_column("Stage", style="cyan")
        table.add_column("Status", style="green")

        for stage, status in result.stage_results.items():
            style = "green" if status == "PASS" else "red"
            table.add_row(stage, f"[{style}]{status}[/{style}]")

        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]ORCHESTRATE-DEV COMPLETE[/bold green]\n\n"
            f"Story ID: {result.story_id}\n"
            f"Story File: {result.story_file}\n"
            f"Status: {'SUCCESS' if result.success else 'FAILED'}",
            title="Result"
        ))
        console.print(table)
