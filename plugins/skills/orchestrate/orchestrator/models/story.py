"""Story and Sprint Status models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class StoryStatus(str, Enum):
    """Story status aligned with BMAD sprint-status.yaml."""

    # BMAD native states
    BACKLOG = "backlog"
    DRAFTED = "drafted"
    READY_FOR_DEV = "ready-for-dev"
    IN_PROGRESS = "in-progress"
    REVIEW = "review"
    DONE = "done"

    # Orchestrator extended states
    TESTING = "testing"
    NEEDS_FIX = "needs-fix"

    @classmethod
    def from_bmad(cls, status: str) -> "StoryStatus":
        """Convert BMAD status string to enum."""
        status_map = {
            "backlog": cls.BACKLOG,
            "drafted": cls.DRAFTED,
            "ready-for-dev": cls.READY_FOR_DEV,
            "in-progress": cls.IN_PROGRESS,
            "review": cls.REVIEW,
            "done": cls.DONE,
            "testing": cls.TESTING,
            "needs-fix": cls.NEEDS_FIX,
        }
        return status_map.get(status.lower(), cls.BACKLOG)

    def is_actionable(self) -> bool:
        """Check if story can be worked on by orchestrator."""
        return self in [
            StoryStatus.READY_FOR_DEV,
            StoryStatus.DRAFTED,
            StoryStatus.NEEDS_FIX,
        ]

    def is_complete(self) -> bool:
        """Check if story is in a terminal state."""
        return self == StoryStatus.DONE


class Story(BaseModel):
    """Represents a single story being processed."""

    id: str = Field(..., description="Story identifier (e.g., '1-1-user-auth')")
    epic_id: str = Field(..., description="Parent epic identifier")
    status: StoryStatus = Field(default=StoryStatus.BACKLOG)

    # Tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[str] = None

    # Results
    files_changed: list[str] = Field(default_factory=list)
    test_results: Optional[dict] = None
    review_notes: Optional[str] = None

    def mark_started(self, worker_id: str) -> None:
        """Mark story as started by a worker."""
        self.status = StoryStatus.IN_PROGRESS
        self.started_at = datetime.now()
        self.worker_id = worker_id

    def mark_testing(self) -> None:
        """Mark story as in testing phase."""
        self.status = StoryStatus.TESTING

    def mark_review(self) -> None:
        """Mark story as ready for user review."""
        self.status = StoryStatus.REVIEW

    def mark_done(self) -> None:
        """Mark story as completed."""
        self.status = StoryStatus.DONE
        self.completed_at = datetime.now()
        self.worker_id = None

    def mark_needs_fix(self, notes: str) -> None:
        """Mark story as needing fixes."""
        self.status = StoryStatus.NEEDS_FIX
        self.review_notes = notes


class EpicStatus(str, Enum):
    """Epic status aligned with BMAD."""

    BACKLOG = "backlog"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class SprintStatus(BaseModel):
    """Represents the sprint-status.yaml file structure."""

    generated: str = Field(..., description="Generation timestamp")
    project: str = Field(..., description="Project name")
    project_key: Optional[str] = None
    tracking_system: str = Field(default="file-system")
    story_location: str = Field(..., description="Path to story files")

    development_status: dict[str, str] = Field(
        default_factory=dict,
        description="Map of story_id -> status"
    )

    def get_stories_by_status(self, status: StoryStatus) -> list[str]:
        """Get all story IDs with a specific status."""
        return [
            story_id for story_id, s in self.development_status.items()
            if not story_id.startswith("epic-")  # Filter out epic entries
            and not story_id.endswith("-retrospective")  # Filter out retros
            and StoryStatus.from_bmad(s) == status
        ]

    def get_actionable_stories(self) -> list[str]:
        """Get all stories that can be worked on."""
        actionable = []
        for story_id, status in self.development_status.items():
            if story_id.startswith("epic-") or story_id.endswith("-retrospective"):
                continue
            story_status = StoryStatus.from_bmad(status)
            if story_status.is_actionable():
                actionable.append(story_id)
        return actionable

    def update_story_status(self, story_id: str, status: StoryStatus) -> None:
        """Update a story's status."""
        self.development_status[story_id] = status.value

    def get_progress(self) -> dict:
        """Get progress statistics."""
        stories = {
            k: v for k, v in self.development_status.items()
            if not k.startswith("epic-") and not k.endswith("-retrospective")
        }

        total = len(stories)
        done = sum(1 for s in stories.values() if s == "done")
        in_progress = sum(1 for s in stories.values() if s == "in-progress")

        return {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "remaining": total - done,
            "percent_complete": (done / total * 100) if total > 0 else 0,
        }
