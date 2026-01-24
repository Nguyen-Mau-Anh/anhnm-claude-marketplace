"""Task tracking system for orchestrate-dev.

Tracks sub-tasks created during development stages and their statuses.
Creates a temp YAML file per story to track progress.
"""

import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class SubTask:
    """A sub-task tracked during development."""
    id: str
    description: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    attempt: int = 1
    task_index: Optional[int] = None


@dataclass
class TaskTracker:
    """Tracks sub-tasks for a story development session."""
    story_id: str
    story_file: str
    started_at: str
    completed_at: Optional[str] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    sub_tasks: List[Dict[str, Any]] = field(default_factory=list)


class TaskTrackerManager:
    """
    Manager for tracking sub-tasks during development.

    Creates and maintains a YAML file in .orchestrate-temp/ directory
    that tracks all sub-tasks and their statuses.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.temp_dir = self.project_root / ".orchestrate-temp"
        self.temp_dir.mkdir(exist_ok=True)
        self.tracker_file: Optional[Path] = None
        self.tracker: Optional[TaskTracker] = None

    def initialize(self, story_id: str, story_file: str) -> Path:
        """
        Initialize task tracking for a story.

        Args:
            story_id: Story identifier
            story_file: Path to story file

        Returns:
            Path to the tracker YAML file
        """
        self.tracker_file = self.temp_dir / f"tasks_{story_id}.yaml"

        self.tracker = TaskTracker(
            story_id=story_id,
            story_file=story_file,
            started_at=self._now(),
        )

        self._save()
        return self.tracker_file

    def load(self, story_id: str) -> bool:
        """
        Load existing tracker for a story.

        Args:
            story_id: Story identifier

        Returns:
            True if loaded successfully, False if not found
        """
        self.tracker_file = self.temp_dir / f"tasks_{story_id}.yaml"

        if not self.tracker_file.exists():
            return False

        with open(self.tracker_file, 'r') as f:
            data = yaml.safe_load(f)
            self.tracker = TaskTracker(**data)

        return True

    def add_task(
        self,
        task_id: str,
        description: str,
        task_index: Optional[int] = None,
    ) -> None:
        """
        Add a new sub-task to tracking.

        Args:
            task_id: Unique task identifier
            description: Task description
            task_index: Optional task index (for task-by-task execution)
        """
        if not self.tracker:
            raise ValueError("Tracker not initialized. Call initialize() first.")

        sub_task = SubTask(
            id=task_id,
            description=description,
            status="pending",
            created_at=self._now(),
            task_index=task_index,
        )

        self.tracker.sub_tasks.append(asdict(sub_task))
        self.tracker.total_tasks += 1
        self._save()

    def update_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """
        Update status of a sub-task.

        Args:
            task_id: Task identifier
            status: New status ("pending", "running", "completed", "failed")
            error: Error message if failed
            duration_seconds: Duration in seconds if completed
        """
        if not self.tracker:
            raise ValueError("Tracker not initialized.")

        for task in self.tracker.sub_tasks:
            if task['id'] == task_id:
                old_status = task['status']
                task['status'] = status

                if status == "running":
                    task['started_at'] = self._now()
                    # Clear completed_at when restarting (for retries)
                    task['completed_at'] = None
                    task['duration_seconds'] = None
                elif status in ("completed", "failed"):
                    task['completed_at'] = self._now()
                    if duration_seconds is not None:
                        task['duration_seconds'] = duration_seconds
                    if error:
                        task['error'] = error

                    # Update counters
                    if old_status != "completed" and status == "completed":
                        self.tracker.completed_tasks += 1
                    if old_status != "failed" and status == "failed":
                        self.tracker.failed_tasks += 1

                break

        self._save()

    def increment_attempt(self, task_id: str) -> int:
        """
        Increment retry attempt counter for a task.

        Args:
            task_id: Task identifier

        Returns:
            New attempt number
        """
        if not self.tracker:
            raise ValueError("Tracker not initialized.")

        for task in self.tracker.sub_tasks:
            if task['id'] == task_id:
                task['attempt'] = task.get('attempt', 1) + 1
                self._save()
                return task['attempt']

        return 1

    def mark_completed(self) -> None:
        """Mark the entire tracking session as completed."""
        if not self.tracker:
            return

        self.tracker.completed_at = self._now()
        self._save()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of task tracking.

        Returns:
            Dictionary with summary statistics
        """
        if not self.tracker:
            return {}

        pending = sum(1 for t in self.tracker.sub_tasks if t['status'] == 'pending')
        running = sum(1 for t in self.tracker.sub_tasks if t['status'] == 'running')
        completed = self.tracker.completed_tasks
        failed = self.tracker.failed_tasks

        return {
            'story_id': self.tracker.story_id,
            'total_tasks': self.tracker.total_tasks,
            'pending': pending,
            'running': running,
            'completed': completed,
            'failed': failed,
            'success_rate': f"{completed / self.tracker.total_tasks * 100:.1f}%" if self.tracker.total_tasks > 0 else "0%",
        }

    def get_tracker_file_path(self) -> Optional[Path]:
        """Get the path to the tracker file."""
        return self.tracker_file

    def _save(self) -> None:
        """Save tracker to YAML file."""
        if not self.tracker or not self.tracker_file:
            return

        with open(self.tracker_file, 'w') as f:
            yaml.dump(asdict(self.tracker), f, default_flow_style=False, sort_keys=False)

    def _now(self) -> str:
        """Get current timestamp as ISO string."""
        return datetime.now().isoformat()
