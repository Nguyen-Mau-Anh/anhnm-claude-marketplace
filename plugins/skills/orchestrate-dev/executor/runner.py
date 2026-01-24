"""Pipeline runner for Layer 1 - orchestrate-dev.

IMPORTANT: The orchestrator ONLY coordinates and spawns agents.
It NEVER executes tasks directly in its own context.
All work (develop, lint fixes, test fixes) is done by spawned agents.
"""

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

from .config import ConfigLoader, DevConfig, StageConfig
from .spawner import ClaudeSpawner, TaskResult, BackgroundTask, TaskStatus
from .knowledge import KnowledgeBase, classify_error, extract_error_pattern
from .task_decomposer import (
    parse_story_tasks,
    should_decompose,
    get_incomplete_tasks,
    format_task_for_agent,
    format_tasks_summary,
)
from .task_tracker import TaskTrackerManager


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
        self.task_tracker = TaskTrackerManager(project_root)
        self.config: Optional[DevConfig] = None
        self.story_id: Optional[str] = None
        self.story_file: Optional[Path] = None

    def _get_knowledge_limit(self, stage_name: str) -> Optional[int]:
        """
        Get max lessons limit from config for a stage.

        Returns:
            None = load all lessons
            int = limit to N lessons
        """
        if not self.config:
            return None  # Default to all lessons if no config

        # Get knowledge_base config
        kb_config = self.config.knowledge_base

        # Check if knowledge base is disabled
        if not kb_config.enabled:
            return 0  # Don't load any lessons

        # Check for per-stage override
        if kb_config.stage_overrides and stage_name in kb_config.stage_overrides:
            stage_limit = kb_config.stage_overrides[stage_name].get('max_lessons')
            if stage_limit == 0 or stage_limit is None:
                return None  # All lessons
            return stage_limit

        # Get global limit
        global_limit = kb_config.max_lessons_per_stage
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

            # Step 1: Resolve story (check if exists, delegate to Layer 0 if needed)
            log("\n=== Step 1: Resolving story ===")

            # Check if story file exists
            story_file = None
            if story_id:
                story_file = self.config_loader.find_story_file(story_id, self.config)
                if story_file:
                    log(f"  ✓ Story file found: {story_file}")
                else:
                    log(f"  Story file not found for ID: {story_id}")

            # If no story file, delegate to Layer 0 for story preparation
            if not story_file:
                log("  Delegating to Layer 0 for story preparation...")

                # Run layer-0-execution stage (delegates to /orchestrate-prepare)
                success = self._run_stage("layer-0-execution", story_id=story_id)

                if not success:
                    result.error = "Layer 0 (story preparation) failed"
                    log(f"  ✗ {result.error}")
                    return result

                # After Layer 0, we should have story_id and story_file set by delegation
                story_id = self.story_id
                story_file = self.story_file

                if not story_file or not story_file.exists():
                    result.error = "Layer 0 completed but no story file created"
                    log(f"  ✗ {result.error}")
                    return result

                log(f"  ✓ Layer 0 complete")
                result.stage_results["layer-0-execution"] = "PASS"

            # Store story info
            self.story_id = story_id
            self.story_file = story_file
            result.story_id = story_id
            result.story_file = str(story_file)

            log(f"  Story ID: {story_id}")
            log(f"  Story file: {story_file}")

            # Initialize task tracking
            tracker_file = self.task_tracker.initialize(story_id, str(story_file))
            log(f"  Task tracking: {tracker_file}")

            # Step 2: Validate story
            log("\n=== Step 2: Validating story ===")
            passed = self._run_stage("validate", story_id=story_id, story_file=str(story_file))
            result.stage_results["validate"] = "PASS" if passed else "SKIP" if self._is_disabled("validate") else "FAIL"
            if not passed and not self._is_disabled("validate") and self._should_abort("validate"):
                result.error = "Validation failed"
                return result

            # Step 3: Develop story (auto task-by-task if tasks exist)
            log("\n=== Step 3: Developing story ===")

            # Parse tasks from story file
            tasks = parse_story_tasks(story_file)
            log(f"  Story has {format_tasks_summary(tasks)}")

            # Auto-detect if decomposition is needed
            if should_decompose(tasks):
                log(f"  Using task-by-task execution ({len(get_incomplete_tasks(tasks))} incomplete tasks found)")
                passed = self._run_task_by_task_development(story_id, str(story_file), tasks)

                # Task-by-task handles retries internally, so if it returns False, always abort
                # This prevents parallel execution when tasks fail
                result.stage_results["develop"] = "PASS" if passed else "FAIL"
                if not passed and not self._is_disabled("develop"):
                    result.error = "Development failed (task-by-task execution)"
                    log(f"  [CRITICAL] Task-by-task development failed, aborting pipeline")
                    return result
            else:
                log(f"  Using standard dev-story workflow (no incomplete tasks found)")
                # Track main develop stage
                self.task_tracker.add_task(
                    task_id="develop-main",
                    description="Execute /bmad:bmm:workflows:dev-story",
                )
                self.task_tracker.update_status("develop-main", "running")
                dev_start = time.time()
                passed = self._run_stage("develop", story_id=story_id, story_file=str(story_file))
                dev_duration = time.time() - dev_start
                self.task_tracker.update_status(
                    "develop-main",
                    "completed" if passed else "failed",
                    duration_seconds=dev_duration,
                )

                # For standard execution, respect on_failure setting
                result.stage_results["develop"] = "PASS" if passed else "SKIP" if self._is_disabled("develop") else "FAIL"
                if not passed and not self._is_disabled("develop") and self._should_abort("develop"):
                    result.error = "Development failed"
                    return result

            # Step 3.5: Validate story completion (CRITICAL GATE)
            log("\n=== Step 3.5: Validating story completion ===")
            passed = self._run_stage("story-validation", story_id=story_id, story_file=str(story_file))
            result.stage_results["story-validation"] = "PASS" if passed else "SKIP" if self._is_disabled("story-validation") else "FAIL"
            if not passed and not self._is_disabled("story-validation") and self._should_abort("story-validation"):
                result.error = "Story validation failed - story is incomplete"
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

            # Collect files changed from git (limit to prevent overload)
            files_changed_list = self._get_changed_files(limit=20)
            result.files_changed = files_changed_list

            passed = self._run_stage(
                "code-review",
                story_id=story_id,
                files_changed=", ".join(files_changed_list) if files_changed_list else "No files changed"
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

        if execution_type == "delegate":
            # Delegate to another layer
            return self._run_delegate_stage(stage_name, **kwargs)
        elif execution_type == "spawn":
            return self._run_spawn_stage(stage_name, **kwargs)
        elif execution_type == "direct":
            return self._run_command_stage(stage_name)
        else:
            log(f"  Unknown execution type: {execution_type}, defaulting to spawn")
            return self._run_spawn_stage(stage_name, **kwargs)

    def _extract_layer_outputs(self, layer_output: str) -> Dict:
        """
        Extract story_id and story_file from layer output.

        Looks for patterns like:
        - "Story ID: 1-2-user-auth"
        - "Story: 1-2-user-auth"
        - "Story file: state/stories/1-2-user-auth.md"
        - "File: state/stories/1-2-user-auth.md"
        """
        outputs = {}

        # Try to extract story ID
        # Pattern 1: "Story ID: <id>"
        story_id_match = re.search(r'Story ID:\s*(\S+)', layer_output, re.IGNORECASE)
        if not story_id_match:
            # Pattern 2: "Story: <id>"
            story_id_match = re.search(r'Story:\s*(\d+-\d+-[\w-]+)', layer_output)

        if story_id_match:
            outputs['story_id'] = story_id_match.group(1)
            log(f"  Extracted story_id: {outputs['story_id']}")

        # Try to extract story file
        # Pattern 1: "Story file: <path>"
        story_file_match = re.search(r'Story file:\s*(\S+\.md)', layer_output, re.IGNORECASE)
        if not story_file_match:
            # Pattern 2: "File: <path>"
            story_file_match = re.search(r'File:\s*(\S+\.md)', layer_output)

        if story_file_match:
            outputs['story_file'] = story_file_match.group(1)
            log(f"  Extracted story_file: {outputs['story_file']}")

        return outputs

    def _run_delegate_stage(self, stage_name: str, **kwargs) -> bool:
        """
        Run a stage by delegating to another layer skill.

        REFACTORED: Uses direct Python import instead of subprocess for reliability.

        Returns:
            bool: True if delegation succeeded
        """
        stage_config = self.config.stages.get(stage_name)
        if not stage_config or not stage_config.delegate_to:
            log(f"  ✗ Stage {stage_name} is missing delegate_to configuration")
            return False

        layer_skill = stage_config.delegate_to
        log(f"  Delegating to layer: {layer_skill}")

        # Determine what to pass as story input
        story_input = kwargs.get("story_id") or kwargs.get("story_file")

        # REFACTORED: Direct Python import for /orchestrate-prepare
        if layer_skill == "/orchestrate-prepare":
            result = self._delegate_to_layer0(story_input, stage_config.timeout)
        else:
            # Fallback to subprocess for unknown layers
            log(f"  Using subprocess delegation for {layer_skill}")
            result = self.spawner.spawn_layer(
                layer_skill=layer_skill,
                story_input=story_input,
                timeout=stage_config.timeout
            )

        if result.success:
            log(f"  ✓ Layer {layer_skill} succeeded")

            # Extract outputs from layer (story_id, story_file)
            extracted = self._extract_layer_outputs(result.output)

            # Update self attributes so subsequent stages can use them
            if extracted.get("story_id"):
                self.story_id = extracted["story_id"]
                log(f"  Updated story_id: {self.story_id}")

            if extracted.get("story_file"):
                self.story_file = Path(extracted["story_file"])
                log(f"  Updated story_file: {self.story_file}")

            return True
        else:
            log(f"  ✗ Layer {layer_skill} failed: {result.error}")
            return False

    def _delegate_to_layer0(self, story_input: Optional[str], timeout: int) -> TaskResult:
        """
        Delegate to Layer 0 by calling Python executor directly (NOT via Claude CLI).

        Bypasses unreliable Claude CLI and calls Python executor directly.
        """
        log(f"    Delegating to Layer 0 (direct Python executor)")
        if story_input:
            log(f"    Story input: {story_input}")

        start_time = time.time()

        try:
            # Build command to run Layer 0 Python executor directly
            layer0_path = self.project_root / ".claude" / "skills" / "orchestrate-prepare"

            # Check if Layer 0 exists
            if not layer0_path.exists():
                return TaskResult(
                    success=False,
                    output="",
                    error=f"Layer 0 not found at: {layer0_path}\nPlease install orchestrate-prepare skill.",
                    exit_code=-1,
                    duration_seconds=0,
                )

            # Command: python3 -m executor [story_input]
            cmd = ["python3", "-m", "executor"]
            if story_input:
                cmd.append(story_input)

            # Run with proper timeout and capture output
            result = subprocess.run(
                cmd,
                cwd=str(layer0_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**subprocess.os.environ, "PYTHONPATH": str(layer0_path)}
            )

            duration = time.time() - start_time

            # Check result
            if result.returncode == 0:
                # Success
                output_lines = [
                    f"✓ Layer 0 complete ({duration:.1f}s)",
                ]

                # Try to extract story info from output
                if "Story ID:" in result.stdout:
                    for line in result.stdout.split('\n'):
                        if "Story ID:" in line or "Story file:" in line:
                            output_lines.append(f"    {line.strip()}")

                return TaskResult(
                    success=True,
                    output="\n".join(output_lines),
                    error=None,
                    exit_code=0,
                    duration_seconds=duration,
                )
            else:
                # Failure
                error_msg = f"Layer 0 failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr}"

                return TaskResult(
                    success=False,
                    output=result.stdout or "",
                    error=error_msg,
                    exit_code=result.returncode,
                    duration_seconds=duration,
                )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            log(f"  ✗ Layer 0 timed out after {timeout}s")

            return TaskResult(
                success=False,
                output=e.stdout.decode() if e.stdout else "",
                error=f"Layer 0 timed out after {timeout}s",
                exit_code=-1,
                duration_seconds=duration,
                status=TaskStatus.TIMEOUT,
            )

        except Exception as e:
            duration = time.time() - start_time
            log(f"  ✗ Layer 0 delegation failed: {e}")
            import traceback
            traceback.print_exc()

            return TaskResult(
                success=False,
                output="",
                error=f"Layer 0 delegation error: {str(e)}",
                exit_code=-1,
                duration_seconds=duration,
            )

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

    def _run_task_by_task_development(
        self,
        story_id: str,
        story_file: str,
        tasks: List,
    ) -> bool:
        """
        Execute story development task-by-task with separate agents.

        Each task gets a fresh agent context to prevent context overload
        and ensure focused implementation.

        Args:
            story_id: Story identifier
            story_file: Path to story file
            tasks: List of Task objects to implement

        Returns:
            True if all tasks completed successfully, False otherwise
        """
        incomplete_tasks = get_incomplete_tasks(tasks)

        if not incomplete_tasks:
            log("  All tasks already complete!")
            return True

        log(f"  Executing {len(incomplete_tasks)} tasks one-by-one with fresh agents...")

        # Register all tasks with tracker
        for task in incomplete_tasks:
            task_preview = task.content.split('\n')[0][:80]
            self.task_tracker.add_task(
                task_id=f"task-{task.index}",
                description=task_preview,
                task_index=task.index,
            )

        # Get knowledge base limit for develop stage
        limit = self._get_knowledge_limit("develop")

        for task in incomplete_tasks:
            log(f"\n  --- Task #{task.index}/{len(tasks)} ---")
            task_preview = task.content.split('\n')[0][:80]
            log(f"  {task_preview}...")

            # Get lessons for develop stage (same as normal develop)
            lessons = self.knowledge.get_lessons_for_stage("develop", limit=limit)
            lesson_ids = [l["id"] for l in lessons]

            if lessons:
                log(f"  📚 Applying {len(lessons)} lesson(s)")

            # Create focused prompt for this specific task
            task_prompt = format_task_for_agent(task, story_id, story_file)

            # Add autonomy instructions and known issues
            full_prompt = f"""
/bmad:bmm:workflows:dev-story
{self.config.autonomy_instructions}

{self.knowledge.format_for_prompt(lessons) if lessons else ""}

{task_prompt}
"""

            # Spawn agent for this task
            log(f"  Spawning agent for task #{task.index}...")
            self.task_tracker.update_status(f"task-{task.index}", "running")

            task_start_time = time.time()
            task_bg = self.spawner.spawn_agent(
                prompt=full_prompt,
                background=True,
                task_id_prefix=f"develop-task-{task.index}"
            )

            # Wait for task completion
            task_result = self._wait_for_task(task_bg, f"task-{task.index}")
            task_duration = time.time() - task_start_time

            if not task_result.success:
                log(f"  Task #{task.index} FAILED: {task_result.error[:200] if task_result.error else 'unknown'}...")
                self.task_tracker.update_status(
                    f"task-{task.index}",
                    "failed",
                    error=task_result.error[:500] if task_result.error else "Unknown error",
                    duration_seconds=task_duration,
                )

                # Try to fix with retry
                stage_config = self.config.stages.get("develop")
                if stage_config and stage_config.retry and stage_config.retry.max > 0:
                    log(f"  Retrying task #{task.index}...")
                    attempt = self.task_tracker.increment_attempt(f"task-{task.index}")
                    self.task_tracker.update_status(f"task-{task.index}", "running")

                    retry_start = time.time()
                    retry_task = self.spawner.spawn_agent(
                        prompt=full_prompt,
                        background=True,
                        task_id_prefix=f"develop-task-{task.index}-retry"
                    )
                    retry_result = self._wait_for_task(retry_task, f"task-{task.index}-retry")
                    retry_duration = time.time() - retry_start

                    if retry_result.success:
                        log(f"  Task #{task.index} PASSED on retry")
                        self.task_tracker.update_status(
                            f"task-{task.index}",
                            "completed",
                            duration_seconds=retry_duration,
                        )
                        continue
                    else:
                        self.task_tracker.update_status(
                            f"task-{task.index}",
                            "failed",
                            error=retry_result.error[:500] if retry_result.error else "Unknown error",
                            duration_seconds=retry_duration,
                        )

                log(f"  Task #{task.index} failed after retry, aborting")
                return False

            log(f"  Task #{task.index} PASSED")
            self.task_tracker.update_status(
                f"task-{task.index}",
                "completed",
                duration_seconds=task_duration,
            )

            # Track prevention if lessons were shown
            if lessons:
                self.knowledge.track_prevention("develop", lesson_ids)

        log(f"\n  All {len(incomplete_tasks)} tasks completed successfully!")
        return True

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

    def _get_changed_files(self, limit: int = 20) -> List[str]:
        """
        Get list of changed files from git.

        Args:
            limit: Maximum number of files to return (prevents overload)

        Returns:
            List of changed file paths (relative to project root)
        """
        try:
            # Get files changed in working directory + staged
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

                # Filter out large or binary files
                filtered_files = []
                for file_path in files[:limit]:  # Apply limit
                    full_path = self.project_root / file_path

                    # Skip if file doesn't exist
                    if not full_path.exists():
                        continue

                    # Skip if file is too large (> 100KB)
                    if full_path.stat().st_size > 100 * 1024:
                        log(f"  Skipping large file: {file_path} ({full_path.stat().st_size / 1024:.1f}KB)")
                        continue

                    # Skip binary files (common extensions)
                    if file_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar', '.gz')):
                        continue

                    filtered_files.append(file_path)

                return filtered_files

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            log(f"  Warning: Could not get changed files from git: {e}")

        return []

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

        # Print task tracking summary
        task_summary = self.task_tracker.get_summary()
        if task_summary and task_summary.get('total_tasks', 0) > 0:
            log("")
            log("Sub-Tasks Summary:")
            log(f"  Total: {task_summary['total_tasks']}")
            log(f"  Completed: {task_summary['completed']}")
            log(f"  Failed: {task_summary['failed']}")
            log(f"  Pending: {task_summary['pending']}")
            log(f"  Success Rate: {task_summary['success_rate']}")
            tracker_file = self.task_tracker.get_tracker_file_path()
            if tracker_file:
                log(f"  Details: {tracker_file}")

        if result.error:
            log(f"\nError: {result.error}")

        log("=" * 50)

        # Mark tracking as completed
        self.task_tracker.mark_completed()
