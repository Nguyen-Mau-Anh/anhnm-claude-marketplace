"""Sprint status storage - interfaces with BMAD's sprint-status.yaml."""

import yaml
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..models.story import SprintStatus, StoryStatus


class SprintStorage:
    """
    Read and write BMAD's sprint-status.yaml file.

    This is the source of truth for story status, shared with BMAD workflows.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self._status_file: Optional[Path] = None
        self._cached_status: Optional[SprintStatus] = None

    def find_status_file(self) -> Optional[Path]:
        """Find the sprint-status.yaml file in common locations."""
        # Common locations based on BMAD config
        possible_paths = [
            self.project_root / "state" / "sprint-status.yaml",
            self.project_root / "docs" / "stories" / "sprint-status.yaml",
            self.project_root / "docs" / "sprint-status.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                self._status_file = path
                return path

        return None

    def load(self) -> Optional[SprintStatus]:
        """Load sprint status from YAML file."""
        if not self._status_file:
            self.find_status_file()

        if not self._status_file or not self._status_file.exists():
            return None

        with open(self._status_file, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Parse BMAD sprint-status format
        self._cached_status = SprintStatus(
            generated=data.get("generated", datetime.now().isoformat()),
            project=data.get("project", "unknown"),
            project_key=data.get("project_key"),
            tracking_system=data.get("tracking_system", "file-system"),
            story_location=data.get("story_location", ""),
            development_status=data.get("development_status", {}),
        )

        return self._cached_status

    def save(self, status: Optional[SprintStatus] = None) -> None:
        """Save sprint status to YAML file."""
        if status:
            self._cached_status = status

        if not self._cached_status:
            raise ValueError("No status to save")

        if not self._status_file:
            raise ValueError("No status file path set")

        # Build YAML data preserving BMAD format
        data = {
            "generated": self._cached_status.generated,
            "project": self._cached_status.project,
            "project_key": self._cached_status.project_key,
            "tracking_system": self._cached_status.tracking_system,
            "story_location": self._cached_status.story_location,
            "development_status": self._cached_status.development_status,
        }

        # Write with comments for BMAD compatibility
        with open(self._status_file, "w") as f:
            f.write("# Sprint Status - Managed by Orchestrator\n")
            f.write(f"# Last updated: {datetime.now().isoformat()}\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def update_story_status(self, story_id: str, new_status: StoryStatus) -> None:
        """Update a single story's status and save."""
        if not self._cached_status:
            self.load()

        if not self._cached_status:
            raise ValueError("No sprint status loaded")

        self._cached_status.update_story_status(story_id, new_status)
        self.save()

    def get_actionable_stories(self) -> list[str]:
        """Get stories that are ready to be worked on."""
        if not self._cached_status:
            self.load()

        if not self._cached_status:
            return []

        return self._cached_status.get_actionable_stories()

    def get_progress(self) -> dict:
        """Get current progress statistics."""
        if not self._cached_status:
            self.load()

        if not self._cached_status:
            return {"total": 0, "done": 0, "remaining": 0, "percent_complete": 0}

        return self._cached_status.get_progress()

    @property
    def status_file_path(self) -> Optional[Path]:
        """Get the path to the status file."""
        return self._status_file

    def create_initial_status(self, project_name: str, stories: dict[str, str]) -> SprintStatus:
        """Create a new sprint status file."""
        self._status_file = self.project_root / "state" / "sprint-status.yaml"
        self._status_file.parent.mkdir(parents=True, exist_ok=True)

        self._cached_status = SprintStatus(
            generated=datetime.now().strftime("%m-%d-%Y %H:%M"),
            project=project_name,
            tracking_system="file-system",
            story_location="state/stories",
            development_status=stories,
        )

        self.save()
        return self._cached_status

    def discover_stories(self) -> dict[str, str]:
        """
        Auto-discover story files from common locations and parse their status.
        Returns a dict of story_id -> status.
        """
        stories = {}

        # Common story file locations
        story_paths = [
            self.project_root / "state" / "stories",
            self.project_root / "docs" / "stories",
            self.project_root / "stories",
        ]

        for story_dir in story_paths:
            if not story_dir.exists():
                continue

            # Find epic files (epic-*.md)
            for epic_file in story_dir.glob("epic-*.md"):
                epic_id = epic_file.stem  # e.g., "epic-1"
                stories[epic_id] = "backlog"

                # Parse epic file for stories
                content = epic_file.read_text()
                self._parse_stories_from_epic(content, stories)

            # Find standalone story files (story-*.md or *-story.md)
            for story_file in story_dir.glob("*.md"):
                if story_file.stem.startswith("epic-"):
                    continue
                # Extract story ID from filename
                story_id = story_file.stem
                if story_id not in stories:
                    stories[story_id] = "backlog"

        return stories

    def _parse_stories_from_epic(self, content: str, stories: dict) -> None:
        """Parse story IDs from epic file content."""
        import re

        # Look for story references like "Story 1.1", "story-1-1", etc.
        # Pattern matches: ## Story X.Y or ### Story X.Y or **Story X.Y**
        story_pattern = re.compile(r'(?:##\s*)?(?:\*\*)?Story\s+(\d+)[.\-](\d+)(?:\*\*)?', re.IGNORECASE)

        for match in story_pattern.finditer(content):
            epic_num, story_num = match.groups()
            story_id = f"{epic_num}-{story_num}"
            if story_id not in stories:
                stories[story_id] = "backlog"

        # Also look for story file references like [story-1-1.md] or (1-1-story-name.md)
        file_pattern = re.compile(r'[\[(](\d+-\d+(?:-[\w-]+)?)[.\]]')
        for match in file_pattern.finditer(content):
            story_id = match.group(1)
            if story_id not in stories:
                stories[story_id] = "backlog"

    def auto_initialize(self) -> Optional[SprintStatus]:
        """
        Auto-initialize sprint status by discovering existing stories.
        Creates sprint-status.yaml if stories are found.
        Returns the created status or None if no stories found.
        """
        # First check if status file already exists
        if self.find_status_file():
            return self.load()

        # Discover stories from file system
        stories = self.discover_stories()

        if not stories:
            return None

        # Determine project name from directory or use default
        project_name = self.project_root.name or "Unnamed Project"

        # Mark first story as ready-for-dev to start the pipeline
        first_story = None
        for story_id in sorted(stories.keys()):
            if not story_id.startswith("epic-") and "-" in story_id:
                first_story = story_id
                break

        if first_story:
            stories[first_story] = "ready-for-dev"

        return self.create_initial_status(project_name, stories)
