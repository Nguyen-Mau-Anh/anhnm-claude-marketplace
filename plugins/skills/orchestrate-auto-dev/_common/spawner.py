"""Claude CLI spawner for isolated agent execution.

Skill-agnostic spawner with logging, real-time output streaming, and critical error handling.
"""

import os
import signal
import subprocess
import tempfile
import time
import threading
import atexit
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, Dict, List, Union, Any
from enum import Enum

from .logger import Logger, LogLevel


class TaskStatus(str, Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CRITICAL_ERROR = "critical_error"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    RECOVERABLE = "recoverable"      # Can retry or continue
    CRITICAL = "critical"            # Requires human intervention
    FATAL = "fatal"                  # Must stop entire pipeline


class EscalationAction(str, Enum):
    """Actions to take on critical errors."""
    CONTINUE = "continue"            # Log error and continue to next step
    STOP_PIPELINE = "stop_pipeline"  # Stop entire pipeline
    RETRY = "retry"                  # Attempt retry before escalating
    ASK_HUMAN = "ask_human"          # Request human decision


@dataclass
class CriticalError:
    """Critical error information for escalation."""
    message: str
    severity: ErrorSeverity
    task_id: str
    stage_name: str
    error_details: Optional[str] = None
    suggested_action: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class TaskResult:
    """Result from a Claude CLI invocation."""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0
    status: TaskStatus = TaskStatus.COMPLETED
    error_severity: Optional[ErrorSeverity] = None
    critical_error: Optional[CriticalError] = None


@dataclass
class BackgroundTask:
    """Handle to a background spawned task."""
    task_id: str
    stage_name: str
    process: Optional[subprocess.Popen] = None
    status: TaskStatus = TaskStatus.PENDING
    start_time: float = 0.0
    timeout: int = 600
    _result: Optional[TaskResult] = None
    _thread: Optional[threading.Thread] = None
    _stdout_file: Optional[str] = None
    _stderr_file: Optional[str] = None

    def is_running(self) -> bool:
        """Check if task is still running."""
        return self.status == TaskStatus.RUNNING

    def is_done(self) -> bool:
        """Check if task has completed (success or failure)."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT)

    def get_result(self, block: bool = True, poll_interval: float = 1.0) -> TaskResult:
        """
        Get the task result.

        Args:
            block: If True, wait for completion. If False, return current state.
            poll_interval: How often to check status when blocking.

        Returns:
            TaskResult with current or final state.
        """
        if block:
            while not self.is_done():
                time.sleep(poll_interval)

        if self._result:
            return self._result

        # Return current state if not done
        return TaskResult(
            success=False,
            output="",
            error="Task still running",
            exit_code=-1,
            duration_seconds=time.time() - self.start_time if self.start_time else 0,
            status=self.status,
        )

    def elapsed_seconds(self) -> float:
        """Get elapsed time since task started."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0


class ClaudeSpawner:
    """
    Spawn Claude CLI processes for isolated task execution.

    Features:
    - Skill-agnostic design
    - Real-time output streaming (optional)
    - Comprehensive logging
    - Background and blocking execution
    - Process cleanup on exit
    - Critical error handling with escalation
    - Human intervention support
    """

    def __init__(
        self,
        project_root: Path,
        timeout_seconds: int = 600,
        model: str = "sonnet",
        logger: Optional[Logger] = None,
        show_output: bool = True,
        progress_interval: Optional[int] = None,
        on_critical_error: Optional[Callable[[CriticalError], EscalationAction]] = None,
        default_escalation: EscalationAction = EscalationAction.STOP_PIPELINE,
        max_retries: int = 2,
    ):
        """
        Initialize spawner.

        Args:
            project_root: Project root directory
            timeout_seconds: Default timeout for tasks
            model: Claude model to use (sonnet, opus, haiku)
            logger: Logger instance for tracking (creates one if None)
            show_output: If True, stream agent output to console in real-time
            progress_interval: Seconds between progress logs (None = adaptive)
            on_critical_error: Callback for critical errors (returns action to take)
            default_escalation: Default action for critical errors if no callback
            max_retries: Maximum retry attempts for recoverable errors
        """
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.show_output = show_output
        self.progress_interval = progress_interval
        self.on_critical_error = on_critical_error
        self.default_escalation = default_escalation
        self.max_retries = max_retries
        self._task_counter = 0
        self._active_tasks: Dict[str, BackgroundTask] = {}
        self._all_spawned_processes: List[subprocess.Popen] = []
        self._critical_errors: List[CriticalError] = []

        # Logger setup
        if logger:
            self.logger = logger
        else:
            log_file = project_root / ".orchestrate-temp/logs/spawner.log"
            self.logger = Logger(
                name="spawner",
                level=LogLevel.INFO,
                log_file=log_file
            )

        # Register cleanup handler
        atexit.register(self._cleanup_all_processes)

        self.logger.info(f"Spawner initialized: model={model}, timeout={timeout_seconds}s, show_output={show_output}")
        self.logger.info(f"Error handling: escalation={default_escalation.value}, max_retries={max_retries}")

    def set_config(self, config: Any) -> None:
        """
        Set or update configuration for the spawner.

        Args:
            config: Configuration object with pipeline settings
        """
        self.config = config
        self.logger.debug("Spawner config updated")

    def _classify_error_severity(
        self,
        exit_code: int,
        error_output: str,
        status: TaskStatus
    ) -> ErrorSeverity:
        """
        Classify error severity based on exit code and error output.

        Args:
            exit_code: Process exit code
            error_output: stderr content
            status: Task status

        Returns:
            ErrorSeverity level
        """
        # Fatal errors (must stop pipeline)
        if status == TaskStatus.TIMEOUT:
            return ErrorSeverity.FATAL

        # Critical errors (need human intervention)
        critical_patterns = [
            "API rate limit",
            "Authentication failed",
            "Permission denied",
            "Out of memory",
            "Disk full",
            "Network unreachable",
            "Internal server error",
            "CRITICAL",
        ]

        error_lower = error_output.lower()
        for pattern in critical_patterns:
            if pattern.lower() in error_lower:
                return ErrorSeverity.CRITICAL

        # Recoverable errors (can retry)
        recoverable_patterns = [
            "Connection timeout",
            "Temporary failure",
            "Resource temporarily unavailable",
            "Try again",
        ]

        for pattern in recoverable_patterns:
            if pattern.lower() in error_lower:
                return ErrorSeverity.RECOVERABLE

        # Default based on exit code
        if exit_code == 0:
            return ErrorSeverity.RECOVERABLE  # Success, but marked as error
        elif exit_code < 0:
            return ErrorSeverity.CRITICAL  # Signal termination
        elif exit_code >= 100:
            return ErrorSeverity.CRITICAL  # High exit codes usually critical
        else:
            return ErrorSeverity.RECOVERABLE  # Standard errors

    def _handle_critical_error(
        self,
        error: CriticalError
    ) -> EscalationAction:
        """
        Handle a critical error and determine action.

        Args:
            error: Critical error information

        Returns:
            Action to take (CONTINUE, STOP_PIPELINE, RETRY, ASK_HUMAN)
        """
        # Log the critical error
        self.logger.error("=" * 60)
        self.logger.error(f"CRITICAL ERROR in {error.task_id} ({error.stage_name})")
        self.logger.error(f"Severity: {error.severity.value}")
        self.logger.error(f"Message: {error.message}")
        if error.error_details:
            self.logger.error(f"Details: {error.error_details[:500]}")
        if error.suggested_action:
            self.logger.error(f"Suggested: {error.suggested_action}")
        self.logger.error("=" * 60)

        # Store in history
        self._critical_errors.append(error)

        # Call user-provided handler if available
        if self.on_critical_error:
            try:
                action = self.on_critical_error(error)
                self.logger.info(f"Critical error handler returned: {action.value}")
                return action
            except Exception as e:
                self.logger.error(f"Critical error handler failed: {e}")
                # Fall through to default

        # Use default escalation
        self.logger.warn(f"Using default escalation: {self.default_escalation.value}")
        return self.default_escalation

    def _execute_escalation_action(
        self,
        action: EscalationAction,
        task_result: TaskResult,
        task_id: str
    ) -> bool:
        """
        Execute the escalation action.

        Args:
            action: Escalation action to execute
            task_result: Result that triggered escalation
            task_id: Task identifier

        Returns:
            True if pipeline should continue, False if should stop
        """
        if action == EscalationAction.CONTINUE:
            self.logger.warn(f"Continuing despite error in {task_id}")
            return True

        elif action == EscalationAction.STOP_PIPELINE:
            self.logger.error(f"Stopping pipeline due to critical error in {task_id}")
            return False

        elif action == EscalationAction.RETRY:
            self.logger.info(f"Retry action requested for {task_id}")
            # Note: Actual retry logic handled by caller
            return True

        elif action == EscalationAction.ASK_HUMAN:
            self.logger.warn(f"Human intervention required for {task_id}")
            # Log request for human intervention
            self.logger.error("⚠️  HUMAN INTERVENTION REQUIRED ⚠️")
            self.logger.error("Please review the error above and take appropriate action")
            # Pipeline should stop and wait for human decision
            return False

        else:
            self.logger.error(f"Unknown escalation action: {action}")
            return False

    def get_critical_errors(self) -> List[CriticalError]:
        """Get list of all critical errors encountered."""
        return self._critical_errors.copy()

    def _build_command(self, prompt: str) -> List[str]:
        """Build the claude CLI command."""
        return [
            "claude",
            "--print",
            "--model", self.model,
            "--permission-mode", "bypassPermissions",
            "--no-session-persistence",
            "--output-format", "text",
            "-p", prompt
        ]

    def _get_progress_interval(self, timeout: int) -> int:
        """
        Calculate adaptive progress interval based on timeout.

        Args:
            timeout: Task timeout in seconds

        Returns:
            Interval in seconds between progress logs

        Strategy:
        - Real-time logging: Every 1s for all tasks
        """
        if self.progress_interval is not None:
            # User override
            return self.progress_interval

        # Real-time progress logging
        return 1  # Every 1s for real-time updates

    def spawn_agent(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        background: bool = False,
        task_id_prefix: Optional[str] = None,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        show_output: Optional[bool] = None,
    ) -> Union[TaskResult, BackgroundTask]:
        """
        Spawn a Claude agent with a custom prompt.

        Args:
            prompt: The complete prompt to send to Claude
            timeout: Override timeout in seconds
            background: If True, run in background and return immediately
            task_id_prefix: Prefix for task ID (helps with debugging)
            on_complete: Callback for when background task completes
            show_output: Override instance show_output setting

        Returns:
            TaskResult (blocking) or BackgroundTask (background)
        """
        actual_show = show_output if show_output is not None else self.show_output

        # Log the spawn request
        self.logger.info(f"Spawning agent: prefix={task_id_prefix}, timeout={timeout}, background={background}")
        self.logger.debug(f"Prompt preview: {prompt[:200]}...")

        if not background:
            return self.spawn_blocking(
                prompt=prompt,
                timeout=timeout,
                stage_name=task_id_prefix or "agent",
                show_output=actual_show
            )

        # Background execution
        actual_timeout = timeout or self.timeout_seconds

        self._task_counter += 1
        task_id = f"{task_id_prefix or 'agent'}_{self._task_counter}"
        task = BackgroundTask(
            task_id=task_id,
            stage_name=task_id_prefix or "agent",
            timeout=actual_timeout,
        )

        def run_task():
            self._execute_task(task, prompt, on_complete, actual_show)

        task._thread = threading.Thread(target=run_task, daemon=True)
        task._thread.start()

        self._active_tasks[task_id] = task
        return task

    def spawn_blocking(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        stage_name: Optional[str] = None,
        show_output: Optional[bool] = None,
    ) -> TaskResult:
        """
        Spawn Claude CLI with a prompt (blocking).

        Shows real-time output by tailing stdout file while process runs.

        Args:
            prompt: Prompt to send to Claude
            timeout: Timeout in seconds
            stage_name: Optional stage name for logging
            show_output: If True, stream output to console in real-time

        Returns:
            TaskResult with execution results
        """
        actual_timeout = timeout or self.timeout_seconds
        actual_show = show_output if show_output is not None else self.show_output
        task_label = stage_name if stage_name else "task"

        # Log start
        self.logger.info(f"Starting blocking spawn: {task_label}, timeout={actual_timeout}s")
        start_time = time.time()

        cmd = self._build_command(prompt)
        temp_dir = self.project_root / ".orchestrate-temp"
        temp_dir.mkdir(exist_ok=True)

        task_id = f"{task_label}_{int(time.time())}"
        stdout_path = temp_dir / f"{task_id}.stdout"
        stderr_path = temp_dir / f"{task_id}.stderr"

        stdout_file = open(stdout_path, 'w+')
        stderr_file = open(stderr_path, 'w+')

        self.logger.debug(f"Temp files: stdout={stdout_path}, stderr={stderr_path}")

        process = None
        tail_thread = None
        stop_tailing = threading.Event()

        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )

            self.logger.info(f"Process started: PID={process.pid}")
            self._all_spawned_processes.append(process)

            # Start output streaming if enabled
            if actual_show:
                def tail_output():
                    """Stream stdout to console in real-time."""
                    last_position = 0
                    print(f"\n{'='*60}")
                    print(f"  Agent Output ({task_label})")
                    print(f"{'='*60}\n")

                    while not stop_tailing.is_set():
                        try:
                            # Flush to ensure data is written
                            stdout_file.flush()

                            # Read new content
                            with open(stdout_path, 'r') as f:
                                f.seek(last_position)
                                new_content = f.read()
                                if new_content:
                                    print(new_content, end='', flush=True)
                                    last_position = f.tell()
                        except:
                            pass

                        time.sleep(0.1)  # Check every 100ms

                tail_thread = threading.Thread(target=tail_output, daemon=True)
                tail_thread.start()

            # Poll for completion
            poll_interval = 0.5
            last_log = time.time()
            progress_interval = self._get_progress_interval(actual_timeout)

            while process.poll() is None:
                time.sleep(poll_interval)
                elapsed = time.time() - start_time

                # Log progress at adaptive intervals
                if time.time() - last_log >= progress_interval:
                    self.logger.info(f"{task_label} still running ({elapsed:.0f}s)")
                    last_log = time.time()

                # Check timeout
                if elapsed > actual_timeout:
                    self.logger.error(f"{task_label} TIMEOUT after {elapsed:.0f}s")
                    self._kill_process_tree(process)

                    # Stop tailing
                    stop_tailing.set()
                    if tail_thread:
                        tail_thread.join(timeout=1)

                    stdout_file.flush()
                    stdout_file.close()
                    stderr_file.flush()
                    stderr_file.close()
                    time.sleep(0.1)

                    stdout_content = self._read_and_cleanup(str(stdout_path))
                    stderr_content = self._read_and_cleanup(str(stderr_path))

                    duration = time.time() - start_time
                    self.logger.error(f"Task timed out: duration={duration:.1f}s")

                    # Timeout is always FATAL
                    critical_error = CriticalError(
                        message=f"Task timed out after {actual_timeout}s",
                        severity=ErrorSeverity.FATAL,
                        task_id=task_id,
                        stage_name=task_label,
                        error_details=(
                            f"stdout: {stdout_content[:500]}, stderr: {stderr_content[:500]}"
                            if stderr_content else stdout_content[:500]
                        ),
                        suggested_action="Increase timeout or optimize task complexity",
                        timestamp=time.time()
                    )

                    escalation_action = self._handle_critical_error(critical_error)

                    result = TaskResult(
                        success=False,
                        output=stdout_content,
                        error=f"Task timed out after {actual_timeout}s. stderr: {stderr_content}",
                        exit_code=-1,
                        duration_seconds=duration,
                        status=TaskStatus.TIMEOUT,
                        error_severity=ErrorSeverity.FATAL,
                        critical_error=critical_error
                    )

                    should_continue = self._execute_escalation_action(
                        escalation_action, result, task_id
                    )

                    if not should_continue:
                        raise RuntimeError(
                            f"Pipeline stopped due to timeout in {task_label}"
                        )

                    return result

            # Stop tailing
            stop_tailing.set()
            if tail_thread:
                tail_thread.join(timeout=1)
                if actual_show:
                    print(f"\n{'='*60}\n")

            # Process completed
            exit_code = process.returncode
            self.logger.info(f"Process completed: exit_code={exit_code}")

            # Remove from tracking
            if process in self._all_spawned_processes:
                self._all_spawned_processes.remove(process)

            # Close and sync files
            stdout_file.flush()
            stdout_file.close()
            stderr_file.flush()
            stderr_file.close()
            time.sleep(0.1)

            # Read final output
            stdout_content = self._read_and_cleanup(str(stdout_path))
            stderr_content = self._read_and_cleanup(str(stderr_path))
            duration = time.time() - start_time

            # Log results
            self.logger.info(f"Task completed: success={exit_code == 0}, duration={duration:.1f}s")
            self.logger.debug(f"Output size: {len(stdout_content)} chars")

            # Log agent output to file (not to console)
            if stdout_content and not actual_show:
                # Only log to file if we didn't already show output in real-time
                self.logger.separator("-", 60)
                self.logger.info(f"Agent Output ({task_label}):")
                self.logger.separator("-", 60)
                # Write full output to file only (not to console)
                for line in stdout_content.splitlines():
                    self.logger.write_to_file_only(line)
                self.logger.separator("-", 60)

            # Log stderr if any
            if stderr_content:
                self.logger.warn("Agent Errors:")
                self.logger.separator("-", 60)
                for line in stderr_content.splitlines():
                    self.logger.write_to_file_only(f"[ERROR] {line}")
                self.logger.separator("-", 60)

            # Classify error severity if task failed
            error_severity = None
            critical_error = None

            if exit_code != 0:
                error_severity = self._classify_error_severity(
                    exit_code, stderr_content, TaskStatus.FAILED
                )

                # Handle critical/fatal errors
                if error_severity in (ErrorSeverity.CRITICAL, ErrorSeverity.FATAL):
                    critical_error = CriticalError(
                        message=f"Task failed with exit code {exit_code}",
                        severity=error_severity,
                        task_id=task_id,
                        stage_name=task_label,
                        error_details=stderr_content[:1000] if stderr_content else None,
                        suggested_action="Review error logs and retry or fix the issue",
                        timestamp=time.time()
                    )

                    escalation_action = self._handle_critical_error(critical_error)

                    # Build result with critical error info
                    result = TaskResult(
                        success=False,
                        output=stdout_content,
                        error=stderr_content if stderr_content else None,
                        exit_code=process.returncode,
                        duration_seconds=duration,
                        status=TaskStatus.CRITICAL_ERROR if error_severity == ErrorSeverity.CRITICAL else TaskStatus.FAILED,
                        error_severity=error_severity,
                        critical_error=critical_error
                    )

                    # Execute escalation action
                    should_continue = self._execute_escalation_action(
                        escalation_action, result, task_id
                    )

                    if not should_continue:
                        raise RuntimeError(
                            f"Pipeline stopped due to critical error in {task_label}: {critical_error.message}"
                        )

                    return result

            return TaskResult(
                success=process.returncode == 0,
                output=stdout_content,
                error=stderr_content if stderr_content else None,
                exit_code=process.returncode,
                duration_seconds=duration,
                error_severity=error_severity,
                critical_error=critical_error
            )

        except Exception as e:
            self.logger.error(f"Exception during spawn: {e}")

            # Stop tailing
            stop_tailing.set()
            if tail_thread:
                tail_thread.join(timeout=1)

            duration = time.time() - start_time
            self._kill_process_tree(process)

            try:
                stdout_file.close()
                stderr_file.close()
            except:
                pass

            self._read_and_cleanup(str(stdout_path))
            self._read_and_cleanup(str(stderr_path))

            # Exception is always CRITICAL
            critical_error = CriticalError(
                message=f"Exception during task execution: {type(e).__name__}",
                severity=ErrorSeverity.CRITICAL,
                task_id=task_id,
                stage_name=task_label,
                error_details=str(e),
                suggested_action="Review logs and fix the underlying issue",
                timestamp=time.time()
            )

            escalation_action = self._handle_critical_error(critical_error)

            result = TaskResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_seconds=duration,
                status=TaskStatus.CRITICAL_ERROR,
                error_severity=ErrorSeverity.CRITICAL,
                critical_error=critical_error
            )

            should_continue = self._execute_escalation_action(
                escalation_action, result, task_id
            )

            if not should_continue:
                raise RuntimeError(
                    f"Pipeline stopped due to exception in {task_label}: {e}"
                ) from e

            return result

    def spawn_skill(
        self,
        skill_name: str,
        args: Optional[str] = None,
        timeout: int = 3600,
        show_output: Optional[bool] = None,
    ) -> TaskResult:
        """
        Spawn another orchestrate skill or workflow.

        Args:
            skill_name: Skill to call (e.g., "/orchestrate-prepare")
            args: Optional arguments to pass to the skill
            timeout: Max execution time in seconds
            show_output: If True, stream output to console

        Returns:
            TaskResult with success/failure
        """
        prompt = f"{skill_name} {args}" if args else skill_name

        self.logger.info(f"Delegating to skill: {skill_name}")
        if args:
            self.logger.debug(f"Args: {args}")

        return self.spawn_blocking(
            prompt,
            timeout,
            stage_name=skill_name.replace('/', '_'),
            show_output=show_output
        )

    def spawn_stage(
        self,
        stage_config: Any,
        background: bool = False,
        use_task_prompt: bool = False,
        **kwargs
    ) -> Union[TaskResult, BackgroundTask]:
        """
        Spawn an agent for a pipeline stage with template formatting.

        Selects the appropriate prompt template (task_prompt vs prompt/story_prompt)
        and formats it with the provided kwargs.

        Args:
            stage_config: StageConfig object with prompt templates and settings
            background: If True, run in background
            use_task_prompt: If True, use task_prompt instead of prompt/story_prompt
            **kwargs: Template variables (story_id, task_index, task_content, etc.)

        Returns:
            TaskResult (blocking) or BackgroundTask (background)
        """
        # Select prompt template
        if use_task_prompt and hasattr(stage_config, 'task_prompt') and stage_config.task_prompt:
            prompt_template = stage_config.task_prompt
            self.logger.debug("Using task_prompt template")
        elif hasattr(stage_config, 'story_prompt') and stage_config.story_prompt:
            prompt_template = stage_config.story_prompt
            self.logger.debug("Using story_prompt template")
        elif hasattr(stage_config, 'prompt') and stage_config.prompt:
            prompt_template = stage_config.prompt
            self.logger.debug("Using prompt template")
        else:
            raise ValueError(f"No prompt template found in stage config")

        # Format prompt with kwargs
        try:
            formatted_prompt = prompt_template.format(**kwargs)
        except KeyError as e:
            self.logger.error(f"Missing template variable: {e}")
            raise ValueError(f"Missing required template variable in prompt: {e}")

        # Get timeout from stage config
        timeout = getattr(stage_config, 'timeout', self.timeout_seconds)

        # Get stage name for logging
        stage_name = kwargs.get('stage_name', 'stage')

        self.logger.info(f"Spawning stage agent: {stage_name}, timeout={timeout}s, background={background}")
        self.logger.debug(f"Formatted prompt length: {len(formatted_prompt)} chars")

        # Spawn agent
        return self.spawn_agent(
            prompt=formatted_prompt,
            timeout=timeout,
            background=background,
            task_id_prefix=stage_name,
            show_output=self.show_output
        )

    def _execute_task(
        self,
        task: BackgroundTask,
        prompt: str,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        show_output: bool = True,
    ) -> None:
        """
        Execute task in background thread.

        Args:
            task: Background task to execute
            prompt: Prompt to send to Claude
            on_complete: Callback when task completes
            show_output: Stream output to console
        """
        cmd = self._build_command(prompt)
        task.start_time = time.time()
        task.status = TaskStatus.RUNNING

        self.logger.info(f"Starting background task: {task.task_id}, timeout={task.timeout}s")

        temp_dir = self.project_root / ".orchestrate-temp"
        temp_dir.mkdir(exist_ok=True)

        stdout_path = temp_dir / f"{task.task_id}.stdout"
        stderr_path = temp_dir / f"{task.task_id}.stderr"

        stdout_file = open(stdout_path, 'w+')
        stderr_file = open(stderr_path, 'w+')

        task._stdout_file = str(stdout_path)
        task._stderr_file = str(stderr_path)

        stop_tailing = threading.Event()
        tail_thread = None

        try:
            # Start process
            task.process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )

            self.logger.info(f"Background process started: PID={task.process.pid}")
            self._all_spawned_processes.append(task.process)

            # Start output streaming if enabled
            if show_output:
                def tail_output():
                    last_position = 0
                    print(f"\n{'='*60}")
                    print(f"  Background Task Output ({task.task_id})")
                    print(f"{'='*60}\n")

                    while not stop_tailing.is_set():
                        try:
                            stdout_file.flush()
                            with open(stdout_path, 'r') as f:
                                f.seek(last_position)
                                new_content = f.read()
                                if new_content:
                                    print(new_content, end='', flush=True)
                                    last_position = f.tell()
                        except:
                            pass
                        time.sleep(0.1)

                tail_thread = threading.Thread(target=tail_output, daemon=True)
                tail_thread.start()

            # Poll for completion
            poll_interval = 0.5
            last_log = time.time()
            progress_interval = self._get_progress_interval(task.timeout)

            while task.process.poll() is None:
                time.sleep(poll_interval)
                elapsed = time.time() - task.start_time

                # Log progress at adaptive intervals
                if time.time() - last_log >= progress_interval:
                    self.logger.info(f"Task {task.task_id} still running ({elapsed:.0f}s)")
                    last_log = time.time()

                if elapsed > task.timeout:
                    self.logger.error(f"Task {task.task_id} TIMEOUT")
                    self._kill_process_tree(task.process)
                    task.status = TaskStatus.TIMEOUT
                    break

            # Stop tailing
            stop_tailing.set()
            if tail_thread:
                tail_thread.join(timeout=1)

            # Process finished
            exit_code = task.process.returncode if task.process.returncode is not None else -1
            self.logger.info(f"Task {task.task_id} ended: exit_code={exit_code}")

            if task.process in self._all_spawned_processes:
                self._all_spawned_processes.remove(task.process)

            # Close files
            try:
                stdout_file.flush()
                os.fsync(stdout_file.fileno())
            except:
                pass
            stdout_file.close()

            try:
                stderr_file.flush()
                os.fsync(stderr_file.fileno())
            except:
                pass
            stderr_file.close()

            time.sleep(0.1)

            # Read output
            stdout_content = self._read_and_cleanup(task._stdout_file)
            stderr_content = self._read_and_cleanup(task._stderr_file)
            duration = time.time() - task.start_time

            # Log output to file
            if stdout_content and not show_output:
                # Only log to file if we didn't already show output in real-time
                self.logger.separator("-", 60)
                self.logger.info(f"Background Task Output ({task.task_id}):")
                self.logger.separator("-", 60)
                for line in stdout_content.splitlines():
                    self.logger.write_to_file_only(line)
                self.logger.separator("-", 60)

            if stderr_content:
                self.logger.warn(f"Background Task Errors ({task.task_id}):")
                self.logger.separator("-", 60)
                for line in stderr_content.splitlines():
                    self.logger.write_to_file_only(f"[ERROR] {line}")
                self.logger.separator("-", 60)

            # Build result
            if task.status == TaskStatus.TIMEOUT:
                task._result = TaskResult(
                    success=False,
                    output=stdout_content,
                    error=f"Task timed out after {task.timeout}s. stderr: {stderr_content}",
                    exit_code=-1,
                    duration_seconds=duration,
                    status=TaskStatus.TIMEOUT,
                )
            else:
                success = task.process.returncode == 0
                task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

                task._result = TaskResult(
                    success=success,
                    output=stdout_content,
                    error=stderr_content if stderr_content else None,
                    exit_code=task.process.returncode,
                    duration_seconds=duration,
                    status=task.status,
                )

            self.logger.info(f"Task {task.task_id} completed: success={task._result.success}, duration={duration:.1f}s")

        except Exception as e:
            self.logger.error(f"Task {task.task_id} exception: {e}")

            # Stop tailing
            stop_tailing.set()
            if tail_thread:
                tail_thread.join(timeout=1)

            duration = time.time() - task.start_time
            self._kill_process_tree(task.process)

            try:
                stdout_file.close()
                stderr_file.close()
            except:
                pass
            self._read_and_cleanup(task._stdout_file)
            self._read_and_cleanup(task._stderr_file)

            task.status = TaskStatus.FAILED
            task._result = TaskResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_seconds=duration,
                status=TaskStatus.FAILED,
            )

        # Call completion callback
        if on_complete and task._result:
            try:
                on_complete(task._result)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    def _read_and_cleanup(self, filepath: Optional[str], keep_file: bool = False) -> str:
        """Read content from temp file and optionally delete it."""
        if not filepath or not os.path.exists(filepath):
            return ""

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            if not keep_file:
                os.unlink(filepath)

            return content
        except Exception as e:
            self.logger.error(f"Error reading {filepath}: {e}")
            if not keep_file:
                try:
                    os.unlink(filepath)
                except:
                    pass
            return ""

    def _kill_process_tree(self, process: Optional[subprocess.Popen]) -> None:
        """Kill a process and all its children."""
        if not process:
            return

        pid = process.pid
        self.logger.debug(f"Killing process tree: PID={pid}")

        if os.name != 'nt':
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(0.3)

                if process.poll() is None:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

            except (ProcessLookupError, PermissionError, OSError):
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.3)
                    if process.poll() is None:
                        os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
        else:
            try:
                process.kill()
            except (ProcessLookupError, OSError):
                pass

    def _cleanup_all_processes(self) -> None:
        """Cleanup handler called on exit to kill all orphaned processes."""
        if not self._all_spawned_processes:
            return

        self.logger.warn(f"CLEANUP: Killing {len(self._all_spawned_processes)} spawned processes")

        for process in self._all_spawned_processes:
            try:
                if process.poll() is not None:
                    continue

                self._kill_process_tree(process)
                time.sleep(0.1)

            except (ProcessLookupError, OSError) as e:
                self.logger.error(f"Cleanup error: {e}")

        self.logger.info("Cleanup complete")

    def get_active_tasks(self) -> Dict[str, BackgroundTask]:
        """Get all active (running) background tasks."""
        return {
            k: v for k, v in self._active_tasks.items()
            if v.is_running()
        }

    def wait_all(self, poll_interval: float = 1.0) -> Dict[str, TaskResult]:
        """Wait for all background tasks to complete."""
        results = {}
        for task_id, task in self._active_tasks.items():
            results[task_id] = task.get_result(block=True, poll_interval=poll_interval)
        return results
