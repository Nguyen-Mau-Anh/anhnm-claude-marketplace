"""Pipeline status management with YAML persistence.

Manages status files for tracking pipeline execution state.
"""

import yaml
import fcntl
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

from .file_utils import safe_write, safe_read, ensure_dir
from .logger import Logger

logger = Logger("status_manager")


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Stage execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class StageInfo:
    """Information about a pipeline stage."""
    name: str
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class PipelineState:
    """Complete pipeline state."""
    story_id: str
    story_file: str
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_seconds: Optional[float] = None
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class StatusManager:
    """
    Manage pipeline status with YAML persistence.

    Features:
    - Atomic writes for safety
    - File locking for concurrent access
    - Stage-level tracking
    - Metadata support
    - Status history
    """

    def __init__(self, project_root: Path, skill_name: str = "orchestrator"):
        """
        Initialize status manager.

        Args:
            project_root: Project root directory
            skill_name: Name of the orchestrator skill
        """
        self.project_root = Path(project_root)
        self.skill_name = skill_name
        self.status_dir = self.project_root / ".orchestrate-temp"
        ensure_dir(self.status_dir)
        self._state: Optional[PipelineState] = None
        self._status_file: Optional[Path] = None

    def initialize(
        self,
        story_id: str,
        story_file: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Initialize status tracking for a pipeline run.

        Args:
            story_id: Story identifier
            story_file: Path to story file
            metadata: Optional metadata dictionary

        Returns:
            Path to status file
        """
        logger.info(f"Initializing status tracking for story {story_id}")
        self._status_file = self.status_dir / f"status_{story_id}_{self.skill_name}.yaml"

        self._state = PipelineState(
            story_id=story_id,
            story_file=story_file,
            status=PipelineStatus.RUNNING,
            started_at=self._now(),
            metadata=metadata or {},
        )

        self._save()
        logger.debug(f"Status file created: {self._status_file}")
        return self._status_file

    def load(self, story_id: str) -> bool:
        """
        Load existing status for a story.

        Args:
            story_id: Story identifier

        Returns:
            True if loaded successfully, False if not found
        """
        logger.debug(f"Loading status for story {story_id}")
        self._status_file = self.status_dir / f"status_{story_id}_{self.skill_name}.yaml"

        if not self._status_file.exists():
            logger.warning(f"Status file not found: {self._status_file}")
            return False

        try:
            content = safe_read(self._status_file)
            data = yaml.safe_load(content)
            self._state = PipelineState(**data)
            logger.info(f"Loaded status for story {story_id}: {self._state.status.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to load status: {e}")
            return False

    def update_pipeline_status(self, status: PipelineStatus) -> None:
        """Update overall pipeline status."""
        if not self._state:
            raise ValueError("Status not initialized. Call initialize() first.")

        old_status = self._state.status
        self._state.status = status
        logger.info(f"Pipeline status: {old_status.value} → {status.value}")

        if status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED):
            self._state.completed_at = self._now()
            if self._state.started_at:
                start_time = datetime.fromisoformat(self._state.started_at)
                end_time = datetime.fromisoformat(self._state.completed_at)
                self._state.total_duration_seconds = (end_time - start_time).total_seconds()
                logger.info(f"Pipeline completed in {self._state.total_duration_seconds:.1f}s")

        self._save()

    def stage_start(self, stage_name: str) -> None:
        """Mark stage as started."""
        if not self._state:
            raise ValueError("Status not initialized.")

        logger.info(f"Stage started: {stage_name}")
        stage_info = StageInfo(
            name=stage_name,
            status=StageStatus.RUNNING,
            started_at=self._now(),
        )

        self._state.stages[stage_name] = asdict(stage_info)
        self._save()

    def stage_end(
        self,
        stage_name: str,
        status: StageStatus,
        error: Optional[str] = None
    ) -> None:
        """Mark stage as completed."""
        if not self._state:
            raise ValueError("Status not initialized.")

        if stage_name not in self._state.stages:
            # Stage wasn't started, create it
            self.stage_start(stage_name)

        stage = self._state.stages[stage_name]
        old_status = stage.get('status', 'unknown')
        stage['status'] = status.value
        stage['completed_at'] = self._now()

        if error:
            stage['error'] = error
            logger.error(f"Stage {stage_name} failed: {error[:100]}")

        # Calculate duration
        if stage.get('started_at'):
            start_time = datetime.fromisoformat(stage['started_at'])
            end_time = datetime.fromisoformat(stage['completed_at'])
            stage['duration_seconds'] = (end_time - start_time).total_seconds()
            logger.info(f"Stage {stage_name}: {old_status} → {status.value} ({stage['duration_seconds']:.1f}s)")
        else:
            logger.info(f"Stage {stage_name}: {old_status} → {status.value}")

        self._save()

    def increment_retry(self, stage_name: str) -> int:
        """
        Increment retry count for a stage.

        Args:
            stage_name: Stage name

        Returns:
            New retry count
        """
        if not self._state:
            raise ValueError("Status not initialized.")

        if stage_name not in self._state.stages:
            self.stage_start(stage_name)

        stage = self._state.stages[stage_name]
        stage['retry_count'] = stage.get('retry_count', 0) + 1
        logger.info(f"Stage {stage_name} retry count incremented to {stage['retry_count']}")
        self._save()

        return stage['retry_count']

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata entry."""
        if not self._state:
            raise ValueError("Status not initialized.")

        self._state.metadata[key] = value
        logger.debug(f"Added metadata: {key} = {value}")
        self._save()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get status summary.

        Returns:
            Dictionary with summary information
        """
        if not self._state:
            logger.debug("No state available for summary")
            return {}

        stages_summary = {}
        for stage_name, stage_data in self._state.stages.items():
            stages_summary[stage_name] = {
                'status': stage_data.get('status'),
                'duration': stage_data.get('duration_seconds'),
                'retry_count': stage_data.get('retry_count', 0),
            }

        logger.debug(f"Generated summary for story {self._state.story_id}: {len(stages_summary)} stages")

        return {
            'story_id': self._state.story_id,
            'status': self._state.status.value,
            'started_at': self._state.started_at,
            'completed_at': self._state.completed_at,
            'duration': self._state.total_duration_seconds,
            'stages': stages_summary,
        }

    def get_status_file_path(self) -> Optional[Path]:
        """Get path to status file."""
        return self._status_file

    def _save(self) -> None:
        """Save status to YAML file with atomic write."""
        if not self._state or not self._status_file:
            return

        try:
            # Convert state to dict
            state_dict = asdict(self._state)

            # Update timestamp
            state_dict['last_updated'] = self._now()

            # Serialize to YAML
            yaml_content = yaml.dump(
                state_dict,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )

            # Atomic write
            safe_write(self._status_file, yaml_content, atomic=True)
            logger.debug(f"Saved status to {self._status_file.name}")

        except Exception as e:
            logger.warning(f"Failed to save status: {e}")
            # Don't crash - continue execution

    def _save_with_lock(self) -> None:
        """Save with file locking (for concurrent access)."""
        if not self._state or not self._status_file:
            return

        lock_file = self._status_file.with_suffix('.lock')

        try:
            # Acquire lock
            logger.debug(f"Acquiring file lock for {self._status_file.name}")
            with open(lock_file, 'w') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

                # Save while holding lock
                self._save()

                # Release lock (automatic on close)
                logger.debug(f"Released file lock for {self._status_file.name}")

        except Exception as e:
            logger.warning(f"Failed to save with lock: {e}")
            # Fallback to non-locked save
            self._save()

    def _now(self) -> str:
        """Get current timestamp as ISO string."""
        return datetime.now().isoformat()
