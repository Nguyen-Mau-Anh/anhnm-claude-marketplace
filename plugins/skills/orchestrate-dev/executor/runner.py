"""Pipeline runner for Layer 1 - orchestrate-dev.

IMPORTANT: The orchestrator ONLY coordinates and spawns agents.
It NEVER executes tasks directly in its own context.
All work (develop, lint fixes, test fixes) is done by spawned agents.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

from .config import ConfigLoader, DevConfig, StageConfig
from .spawner import ClaudeSpawner, TaskResult, BackgroundTask, TaskStatus
from .knowledge import KnowledgeBase, classify_error, extract_error_pattern


def log(msg: str) -> None:
    """Print with immediate flush for background visibility."""
    print(msg, flush=True)


@dataclass
class PipelineResult:
    """Result of the entire pipeline execution."""
    success: bool
    story_id: Optional[str] = None
    story_file: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    stage_results: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class PipelineRunner:
    """
    Execute Layer 1 pipeline stages.

    CRITICAL: This orchestrator ONLY spawns agents and coordinates.
    It NEVER executes any development tasks in its own context.
    All lint fixes, test fixes, and development work is done by spawned agents.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.config_loader = ConfigLoader(project_root)
        self.spawner = ClaudeSpawner(project_root)
        self.knowledge = KnowledgeBase(project_root)
        self.config: Optional[DevConfig] = None

    def _get_knowledge_limit(self, stage_name: str) -> Optional[int]:
        """
        Get max lessons limit from config for a stage.

        Returns:
            None = load all lessons
            int = limit to N lessons
        """
        if not self.config:
            return None  # Default to all lessons if no config

        # Get knowledge_base config section
        kb_config = self.config.raw_config.get('knowledge_base', {})

        # Check if knowledge base is disabled
        if not kb_config.get('enabled', True):
            return 0  # Don't load any lessons

        # Check for per-stage override
        stage_overrides = kb_config.get('stage_overrides', {})
        if stage_name in stage_overrides:
            stage_limit = stage_overrides[stage_name].get('max_lessons')
            if stage_limit == 0 or stage_limit is None:
                return None  # All lessons
            return stage_limit

        # Get global limit
        global_limit = kb_config.get('max_lessons_per_stage')
        if global_limit == 0 or global_limit is None:
            return None  # All lessons

        return global_limit

    def run(self, story_id: Optional[str] = None) -> PipelineResult:
        """Run the complete pipeline."""
        result = PipelineResult(success=False)

        try:
            # Step 0: Load config
            log("\n=== Step 0: Loading configuration ===")
            self.config = self.config_loader.load()
            self.spawner.set_config(self.config)
            log("  Config loaded successfully")

            # Step 1: Determine story
            log("\n=== Step 1: Determining story ===")
            story_id, story_file = self._resolve_story(story_id)
            result.story_id = story_id
            result.story_file = str(story_file) if story_file else None

            if not story_file:
                result.error = "Failed to create or find story file"
                log(f"  ERROR: {result.error}")
                return result

            log(f"  Story ID: {story_id}")
            log(f"  Story file: {story_file}")
            result.stage_results["create-story"] = "PASS"

            # Step 2: Validate story
            log("\n=== Step 2: Validating story ===")
            passed = self._run_stage("validate", story_id=story_id, story_file=str(story_file))
            result.stage_results["validate"] = "PASS" if passed else "SKIP" if self._is_disabled("validate") else "FAIL"
            if not passed and not self._is_disabled("validate") and self._should_abort("validate"):
                result.error = "Validation failed"
                return result

            # Step 3: Develop story
            log("\n=== Step 3: Developing story ===")
            passed = self._run_stage("develop", story_id=story_id, story_file=str(story_file))
            result.stage_results["develop"] = "PASS" if passed else "SKIP" if self._is_disabled("develop") else "FAIL"
            if not passed and not self._is_disabled("develop") and self._should_abort("develop"):
                result.error = "Development failed"
                return result

            # Step 4: Lint
            log("\n=== Step 4: Running lint ===")
            passed = self._run_stage("lint", story_id=story_id, story_file=str(story_file))
            result.stage_results["lint"] = "PASS" if passed else "SKIP" if self._is_disabled("lint") else "FAIL"
            if not passed and not self._is_disabled("lint") and self._should_abort("lint"):
                result.error = "Lint failed"
                return result

            # Step 5: Typecheck
            log("\n=== Step 5: Running typecheck ===")
            passed = self._run_stage("typecheck", story_id=story_id, story_file=str(story_file))
            result.stage_results["typecheck"] = "PASS" if passed else "SKIP" if self._is_disabled("typecheck") else "FAIL"
            if not passed and not self._is_disabled("typecheck") and self._should_abort("typecheck"):
                result.error = "Typecheck failed"
                return result

            # Step 6: Unit test
            log("\n=== Step 6: Running unit tests ===")
            passed = self._run_stage("unit-test", story_id=story_id, story_file=str(story_file))
            result.stage_results["unit-test"] = "PASS" if passed else "SKIP" if self._is_disabled("unit-test") else "FAIL"
            if not passed and not self._is_disabled("unit-test") and self._should_abort("unit-test"):
                result.error = "Unit tests failed"
                return result

            # Step 7: Code review
            log("\n=== Step 7: Running code review ===")
            passed = self._run_stage(
                "code-review",
                story_id=story_id,
                files_changed=", ".join(result.files_changed) if result.files_changed else "unknown"
            )
            result.stage_results["code-review"] = "PASS" if passed else "SKIP" if self._is_disabled("code-review") else "FAIL"
            # Code review is non-blocking by default

            # Determine overall success
            failed_stages = [s for s, status in result.stage_results.items() if status == "FAIL"]
            result.success = len(failed_stages) == 0

            self._print_summary(result)
            return result

        except Exception as e:
            result.error = str(e)
            log(f"\n!!! Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return result

    def _should_abort(self, stage_name: str) -> bool:
        """Check if pipeline should abort on stage failure."""
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            return True  # Abort by default if no config
        return stage_config.on_failure == "abort"

    def _is_disabled(self, stage_name: str) -> bool:
        """Check if a stage is disabled in config."""
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            return False  # Not disabled if no config (will be skipped anyway)
        return not stage_config.enabled

    def _run_stage(self, stage_name: str, **kwargs) -> bool:
        """
        Run a stage, auto-detecting execution type from config.

        Routes to _run_spawn_stage or _run_command_stage based on
        the 'execution' field in stage config.
        """
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            log(f"  No config for stage {stage_name}, skipping")
            return True

        if not stage_config.enabled:
            log(f"  Stage {stage_name} is disabled, skipping")
            return True

        execution_type = stage_config.execution
        log(f"  Execution type: {execution_type}")

        if execution_type == "spawn":
            return self._run_spawn_stage(stage_name, **kwargs)
        elif execution_type == "direct":
            return self._run_command_stage(stage_name)
        else:
            log(f"  Unknown execution type: {execution_type}, defaulting to spawn")
            return self._run_spawn_stage(stage_name, **kwargs)

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

            # Log progress every 30 seconds
            if time.time() - last_log >= 30:
                log(f"    ... {stage_name} still running ({elapsed:.0f}s)")
                last_log = time.time()

        result = task.get_result(block=False)
        log(f"  {stage_name} completed: success={result.success}, duration={result.duration_seconds:.1f}s")

        if not result.success and result.error:
            # Only show first 500 chars of error
            error_preview = result.error[:500] if result.error else ""
            log(f"    Error: {error_preview}...")

        return result

    def _resolve_story(self, story_id: Optional[str]) -> Tuple[Optional[str], Optional[Path]]:
        """Resolve or create story file."""
        if story_id:
            story_file = self.config_loader.find_story_file(story_id, self.config)
            if story_file:
                log(f"  Found existing story file")
                return story_id, story_file
            log(f"  Story file not found, creating...")

        # Create new story - SPAWN agent (never do in parent context)
        log("  Spawning create-story agent...")

        # Get lessons for create-story stage
        limit = self._get_knowledge_limit("create-story")
        lessons = self.knowledge.get_lessons_for_stage("create-story", limit=limit)

        kwargs = {}
        if lessons:
            log(f"  📚 Applying {len(lessons)} lesson(s) from previous runs")
            kwargs['known_issues'] = self.knowledge.format_for_prompt(lessons)
        else:
            kwargs['known_issues'] = ""

        task = self.spawner.spawn_stage("create-story", background=True, **kwargs)
        log(f"  Task started: {task.task_id}")

        task_result = self._wait_for_task(task, "create-story")

        if not task_result.success:
            log(f"  Failed to create story: {task_result.error}")
            return None, None

        log(f"  Story created ({task_result.duration_seconds:.1f}s)")

        # Parse story_id from output
        output = task_result.output
        log(f"  Output length: {len(output)} chars")

        if not story_id:
            import re
            patterns = [
                r'story[_-]?id[:\s]+([^\s\n]+)',
                r'created[:\s]+([^\s\n]+)\.md',
                r'(\d+-\d+-[\w-]+)\.md',
            ]
            for pattern in patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    story_id = match.group(1).replace('.md', '')
                    log(f"  Parsed story_id: {story_id}")
                    break

        # Find created story file
        if story_id:
            story_file = self.config_loader.find_story_file(story_id, self.config)
            if story_file:
                return story_id, story_file

        # Search for recently created .md files
        log(f"  Could not locate story file, searching...")
        for location in self.config.story_locations:
            search_dir = self.project_root / Path(location).parent
            if search_dir.exists():
                md_files = sorted(search_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
                if md_files:
                    story_file = md_files[0]
                    story_id = story_file.stem
                    log(f"  Found recent story: {story_id}")
                    return story_id, story_file

        return story_id, None

    def _run_spawn_stage(self, stage_name: str, **kwargs) -> bool:
        """
        Run a stage by spawning an agent.

        IMPORTANT: All work is done by the spawned agent.
        The orchestrator only waits for completion.

        Integrates knowledge base to inject lessons and capture fixes.
        """
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            log(f"  No config for stage {stage_name}, skipping")
            return True

        max_retries = stage_config.retry.max if stage_config.retry else 0

        # Get relevant lessons for this stage
        limit = self._get_knowledge_limit(stage_name)
        lessons = self.knowledge.get_lessons_for_stage(stage_name, limit=limit)
        lesson_ids = [l["id"] for l in lessons]

        if lessons:
            log(f"  📚 Applying {len(lessons)} lesson(s) from previous runs")
            # Add lessons to kwargs for prompt injection
            kwargs['known_issues'] = self.knowledge.format_for_prompt(lessons)
        else:
            kwargs['known_issues'] = ""

        first_error = None

        for attempt in range(max_retries + 1):
            log(f"  Spawning {stage_name} agent (attempt {attempt + 1}/{max_retries + 1})...")

            task = self.spawner.spawn_stage(stage_name, background=True, **kwargs)
            task_result = self._wait_for_task(task, stage_name)

            if task_result.success:
                log(f"  {stage_name} PASSED ({task_result.duration_seconds:.1f}s)")

                # Track prevention if lessons were shown and first attempt succeeded
                if lessons and attempt == 0:
                    self.knowledge.track_prevention(stage_name, lesson_ids)
                    log(f"  💡 {len(lessons)} lesson(s) helped prevent errors")

                # Capture lesson if this was a fix after failure
                if attempt > 0 and first_error:
                    lesson_id = self.knowledge.add_lesson(
                        stage=stage_name,
                        error_type=classify_error(first_error),
                        error_pattern=extract_error_pattern(first_error),
                        error_message=first_error,
                        context={
                            "file": kwargs.get("story_file", "unknown"),
                            "story_id": kwargs.get("story_id", "unknown")
                        },
                        fix={
                            "description": f"Fix applied after {attempt} retries",
                            "action": "retry_with_fix"
                        },
                        success=True,
                        story_id=kwargs.get("story_id")
                    )
                    log(f"  💡 Saved lesson: {lesson_id}")

                return True

            log(f"  {stage_name} FAILED")

            # Save first error for lesson capture
            if attempt == 0:
                first_error = task_result.error

            # If we have retries left and on_failure is fix_and_retry, spawn fix agent
            if attempt < max_retries and stage_config.on_failure == "fix_and_retry":
                log(f"  Attempt {attempt + 1} failed, will retry...")
                # The retry prompt in config should handle the fix
                # We just retry the stage which will attempt to fix
                continue

        # All retries exhausted
        if stage_config.on_failure == "continue":
            log(f"  {stage_name} failed but continuing (on_failure=continue)")
            return False  # Return false but don't abort

        log(f"  {stage_name} failed after {max_retries + 1} attempts")
        return False

    def _run_command_stage(self, stage_name: str) -> bool:
        """
        Run a bash command stage (lint, typecheck, test).

        IMPORTANT: The orchestrator ONLY runs the check command.
        If the check fails, it spawns a dev agent to fix.
        The orchestrator NEVER fixes issues itself.

        Integrates knowledge base to track errors and fixes.
        """
        stage_config = self.config.stages.get(stage_name)
        if not stage_config:
            log(f"  No config for stage {stage_name}, skipping")
            return True

        command = stage_config.command
        if not command:
            log(f"  No command for stage {stage_name}, skipping")
            return True

        max_retries = stage_config.retry.max if stage_config.retry else 0
        timeout = stage_config.timeout or 120

        # Get relevant lessons for this stage
        limit = self._get_knowledge_limit(stage_name)
        lessons = self.knowledge.get_lessons_for_stage(stage_name, limit=limit)
        lesson_ids = [l["id"] for l in lessons]

        if lessons:
            log(f"  📚 {len(lessons)} lesson(s) available for {stage_name}")

        first_error = None

        for attempt in range(max_retries + 1):
            log(f"  Running: {command} (attempt {attempt + 1}/{max_retries + 1})...")

            try:
                # Run the check command
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                if proc.returncode == 0:
                    log(f"  {stage_name} PASSED")

                    # Track prevention if lessons were available and first attempt succeeded
                    if lessons and attempt == 0:
                        self.knowledge.track_prevention(stage_name, lesson_ids)
                        log(f"  💡 {len(lessons)} lesson(s) helped prevent errors")

                    # Capture lesson if this was a fix after failure
                    if attempt > 0 and first_error:
                        lesson_id = self.knowledge.add_lesson(
                            stage=stage_name,
                            error_type=classify_error(first_error),
                            error_pattern=extract_error_pattern(first_error),
                            error_message=first_error,
                            context={"command": command},
                            fix={
                                "description": f"Fix applied after {attempt} retries",
                                "action": "fix_agent_applied"
                            },
                            success=True,
                            story_id=None
                        )
                        log(f"  💡 Saved lesson: {lesson_id}")

                    return True

                # Command failed - get errors
                errors = (proc.stdout + proc.stderr).strip()
                log(f"  {stage_name} FAILED (exit code {proc.returncode})")

                # Save first error for lesson capture
                if attempt == 0:
                    first_error = errors

                # If we have retries left, SPAWN an agent to fix (never fix in parent context)
                if attempt < max_retries and stage_config.on_failure == "fix_and_retry":
                    log(f"  Spawning dev agent to fix {stage_name} errors...")
                    log(f"  Error preview: {errors[:300]}...")

                    # Add lessons to fix agent context
                    fix_kwargs = {"errors": errors}
                    if lessons:
                        fix_kwargs['known_issues'] = self.knowledge.format_for_prompt(lessons)
                    else:
                        fix_kwargs['known_issues'] = ""

                    # Spawn fix agent with error context and lessons
                    fix_task = self.spawner.spawn_stage(
                        stage_name,
                        background=True,
                        **fix_kwargs
                    )
                    fix_result = self._wait_for_task(fix_task, f"{stage_name}-fix")

                    if fix_result.success:
                        log(f"  Fix agent completed, will retry {stage_name}...")
                    else:
                        log(f"  Fix agent failed: {fix_result.error[:200] if fix_result.error else 'unknown'}...")

                    # Continue to next attempt (re-run the command)
                    continue

            except subprocess.TimeoutExpired:
                log(f"  {stage_name} timed out after {timeout}s")

        # All retries exhausted
        if stage_config.on_failure == "continue":
            log(f"  {stage_name} failed but continuing (on_failure=continue)")
            return False

        log(f"  {stage_name} failed after {max_retries + 1} attempts")
        return False

    def _print_summary(self, result: PipelineResult) -> None:
        """Print final summary."""
        log("\n" + "=" * 50)
        log("ORCHESTRATE-DEV COMPLETE")
        log("=" * 50)
        log(f"Story ID: {result.story_id}")
        log(f"Story File: {result.story_file}")
        log(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        log("")
        log("Stage Results:")
        for stage, status in result.stage_results.items():
            if status == "PASS":
                marker = "✓"
            elif status == "SKIP":
                marker = "○"
            else:
                marker = "✗"
            log(f"  {marker} {stage}: {status}")

        if result.error:
            log(f"\nError: {result.error}")

        log("=" * 50)
