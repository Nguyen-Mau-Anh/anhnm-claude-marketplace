"""Claude CLI spawner for isolated agent execution."""

import os
import signal
import subprocess
import time
import threading
import atexit
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Union
from enum import Enum


from .config import TestDesignConfig, StageConfig


class TaskStatus(str, Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    """Result from a Claude CLI invocation."""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0
    status: TaskStatus = TaskStatus.COMPLETED


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
        """Get the task result."""
        if block:
            while not self.is_done():
                time.sleep(poll_interval)

        if self._result:
            return self._result

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

    Supports both blocking and background (non-blocking) execution modes.
    """

    def __init__(
        self,
        project_root: Path,
        timeout_seconds: int = 600,
        config: Optional[TestDesignConfig] = None,
    ):
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds
        self.config = config
        self._task_counter = 0
        self._active_tasks: Dict[str, BackgroundTask] = {}
        self._all_spawned_processes: List[subprocess.Popen] = []

        # Register cleanup handler
        atexit.register(self._cleanup_all_processes)

    def set_config(self, config: TestDesignConfig) -> None:
        """Set the config after initialization."""
        self.config = config

    def build_prompt_from_config(
        self,
        stage_name: str,
        **kwargs
    ) -> Optional[str]:
        """Build prompt from config stage definition."""
        if not self.config:
            raise ValueError("Config not set. Call set_config() first.")

        stage = self.config.stages.get(stage_name)
        if not stage or not stage.prompt:
            return None

        kwargs["autonomy"] = self.config.autonomy_instructions
        kwargs["project_root"] = str(self.project_root)

        try:
            return stage.prompt.format(**kwargs).strip()
        except KeyError:
            # Provide defaults for missing keys
            kwargs_with_defaults = {
                "autonomy": self.config.autonomy_instructions,
                "project_root": str(self.project_root),
                "story_id": kwargs.get("story_id", "{story_id}"),
                "story_file": kwargs.get("story_file", "{story_file}"),
                "tdm_output": kwargs.get("tdm_output", "{tdm_output}"),
                "tdm_file": kwargs.get("tdm_file", "{tdm_file}"),
                "validation_errors": kwargs.get("validation_errors", "None"),
            }
            return stage.prompt.format(**kwargs_with_defaults).strip()

    def _build_command(self, prompt: str) -> List[str]:
        """Build the claude CLI command."""
        return [
            "claude",
            "--print",
            "--model", "sonnet",
            "--permission-mode", "bypassPermissions",
            "--no-session-persistence",
            "--output-format", "text",
            "-p", prompt
        ]

    def spawn_background(
        self,
        stage_name: str,
        timeout: Optional[int] = None,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        **kwargs
    ) -> BackgroundTask:
        """Spawn Claude CLI in the background (non-blocking)."""
        prompt = self.build_prompt_from_config(stage_name, **kwargs)

        if not prompt:
            task = BackgroundTask(
                task_id=f"task_{self._task_counter}",
                stage_name=stage_name,
                status=TaskStatus.FAILED,
            )
            task._result = TaskResult(
                success=False,
                output="",
                error=f"No prompt found for stage: {stage_name}",
                exit_code=-1,
                status=TaskStatus.FAILED,
            )
            return task

        if timeout is None and self.config:
            stage = self.config.stages.get(stage_name)
            if stage:
                timeout = stage.timeout
        timeout = timeout or self.timeout_seconds

        self._task_counter += 1
        task_id = f"task_{self._task_counter}_{stage_name}"
        task = BackgroundTask(
            task_id=task_id,
            stage_name=stage_name,
            timeout=timeout,
        )

        def run_task():
            self._execute_task(task, prompt, on_complete)

        task._thread = threading.Thread(target=run_task, daemon=True)
        task._thread.start()

        self._active_tasks[task_id] = task
        return task

    def _execute_task(
        self,
        task: BackgroundTask,
        prompt: str,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
    ) -> None:
        """Execute task in background thread."""
        cmd = self._build_command(prompt)
        task.start_time = time.time()
        task.status = TaskStatus.RUNNING

        print(f"[spawner] Starting task {task.task_id}, timeout={task.timeout}s", flush=True)

        temp_dir = self.project_root / ".orchestrate-temp"
        temp_dir.mkdir(exist_ok=True)

        stdout_path = temp_dir / f"{task.task_id}.stdout"
        stderr_path = temp_dir / f"{task.task_id}.stderr"

        stdout_file = open(stdout_path, 'w+')
        stderr_file = open(stderr_path, 'w+')

        task._stdout_file = str(stdout_path)
        task._stderr_file = str(stderr_path)

        try:
            task.process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )

            print(f"[spawner] Process started with PID {task.process.pid}", flush=True)
            self._all_spawned_processes.append(task.process)

            poll_interval = 0.5
            last_log = time.time()

            while task.process.poll() is None:
                time.sleep(poll_interval)
                elapsed = time.time() - task.start_time

                if time.time() - last_log >= 30:
                    print(f"[spawner] Task {task.task_id} still running ({elapsed:.0f}s)", flush=True)
                    last_log = time.time()

                if elapsed > task.timeout:
                    print(f"[spawner] Task {task.task_id} TIMEOUT after {elapsed:.0f}s", flush=True)
                    self._kill_process_tree(task.process)
                    task.status = TaskStatus.TIMEOUT
                    break

            exit_code = task.process.returncode if task.process.returncode is not None else -1
            print(f"[spawner] Task {task.task_id} process ended, exit_code={exit_code}", flush=True)

            if task.process in self._all_spawned_processes:
                self._all_spawned_processes.remove(task.process)

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

            stdout_content = self._read_and_cleanup(task._stdout_file)
            stderr_content = self._read_and_cleanup(task._stderr_file)

            duration = time.time() - task.start_time

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

            print(f"[spawner] Task {task.task_id} completed: success={task._result.success}", flush=True)

        except Exception as e:
            print(f"[spawner] Task {task.task_id} EXCEPTION: {e}", flush=True)
            import traceback
            traceback.print_exc()

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

        if on_complete and task._result:
            try:
                on_complete(task._result)
            except Exception as e:
                print(f"[spawner] Callback error: {e}", flush=True)

    def _read_and_cleanup(self, filepath: Optional[str], keep_file: bool = False) -> str:
        """Read content from temp file and optionally delete it."""
        if not filepath:
            return ""

        if not os.path.exists(filepath):
            return ""

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            if not keep_file:
                os.unlink(filepath)

            return content
        except Exception as e:
            print(f"[spawner] Error reading {filepath}: {e}", flush=True)
            if not keep_file:
                try:
                    os.unlink(filepath)
                except:
                    pass
            return ""

    def spawn_stage(
        self,
        stage_name: str,
        timeout: Optional[int] = None,
        background: bool = False,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        **kwargs
    ) -> Union[TaskResult, BackgroundTask]:
        """Spawn Claude CLI for a specific stage."""
        if background:
            return self.spawn_background(stage_name, timeout, on_complete, **kwargs)

        prompt = self.build_prompt_from_config(stage_name, **kwargs)

        if not prompt:
            return TaskResult(
                success=False,
                output="",
                error=f"No prompt found for stage: {stage_name}",
                exit_code=-1,
                duration_seconds=0.0,
            )

        if timeout is None and self.config:
            stage = self.config.stages.get(stage_name)
            if stage:
                timeout = stage.timeout

        return self.spawn_with_prompt(prompt, timeout, stage_name=stage_name)

    def spawn_with_prompt(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        stage_name: Optional[str] = None,
    ) -> TaskResult:
        """Spawn Claude CLI with a pre-built prompt (blocking)."""
        actual_timeout = timeout or self.timeout_seconds
        cmd = self._build_command(prompt)

        temp_dir = self.project_root / ".orchestrate-temp"
        temp_dir.mkdir(exist_ok=True)

        task_label = stage_name if stage_name else "task"
        task_id = f"{task_label}_{int(time.time())}"
        stdout_path = temp_dir / f"{task_id}.stdout"
        stderr_path = temp_dir / f"{task_id}.stderr"

        stdout_file = open(stdout_path, 'w+')
        stderr_file = open(stderr_path, 'w+')

        print(f"[spawner] Blocking spawn: {task_label}", flush=True)

        start_time = time.time()
        process = None

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )

            print(f"[spawner] Process started with PID {process.pid}", flush=True)
            self._all_spawned_processes.append(process)

            poll_interval = 0.5
            last_log = time.time()
            while process.poll() is None:
                time.sleep(poll_interval)
                elapsed = time.time() - start_time

                if time.time() - last_log >= 30:
                    print(f"[spawner] {task_label} still running ({elapsed:.0f}s)", flush=True)
                    last_log = time.time()

                if elapsed > actual_timeout:
                    print(f"[spawner] {task_label} TIMEOUT", flush=True)
                    self._kill_process_tree(process)

                    stdout_file.flush()
                    stdout_file.close()
                    stderr_file.flush()
                    stderr_file.close()
                    time.sleep(0.1)

                    stdout_content = self._read_and_cleanup(str(stdout_path))
                    stderr_content = self._read_and_cleanup(str(stderr_path))

                    return TaskResult(
                        success=False,
                        output=stdout_content,
                        error=f"Task timed out after {actual_timeout}s. stderr: {stderr_content}",
                        exit_code=-1,
                        duration_seconds=time.time() - start_time,
                        status=TaskStatus.TIMEOUT,
                    )

            print(f"[spawner] Task completed, exit_code={process.returncode}", flush=True)

            if process in self._all_spawned_processes:
                self._all_spawned_processes.remove(process)

            stdout_file.flush()
            stdout_file.close()
            stderr_file.flush()
            stderr_file.close()
            time.sleep(0.1)

            stdout_content = self._read_and_cleanup(str(stdout_path))
            stderr_content = self._read_and_cleanup(str(stderr_path))
            duration = time.time() - start_time

            return TaskResult(
                success=process.returncode == 0,
                output=stdout_content,
                error=stderr_content if stderr_content else None,
                exit_code=process.returncode,
                duration_seconds=duration,
            )

        except Exception as e:
            print(f"[spawner] Task EXCEPTION: {e}", flush=True)
            duration = time.time() - start_time
            self._kill_process_tree(process)
            try:
                stdout_file.close()
                stderr_file.close()
            except:
                pass
            self._read_and_cleanup(str(stdout_path))
            self._read_and_cleanup(str(stderr_path))

            return TaskResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_seconds=duration,
            )

    def _kill_process_tree(self, process: Optional[subprocess.Popen]) -> None:
        """Kill a process and all its children."""
        if not process:
            return

        pid = process.pid

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

        print(f"[spawner] CLEANUP: Killing {len(self._all_spawned_processes)} spawned processes...", flush=True)

        for process in self._all_spawned_processes:
            try:
                if process.poll() is not None:
                    continue

                pid = process.pid
                print(f"[spawner] CLEANUP: Killing process {pid}...", flush=True)
                self._kill_process_tree(process)
                time.sleep(0.1)

            except (ProcessLookupError, OSError) as e:
                print(f"[spawner] CLEANUP: Error killing process: {e}", flush=True)

        print(f"[spawner] CLEANUP: Complete", flush=True)

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
