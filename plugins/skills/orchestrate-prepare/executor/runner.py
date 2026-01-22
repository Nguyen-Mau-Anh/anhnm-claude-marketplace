"""Pipeline runner for Layer 0 - orchestrate-prepare.

Layer 0: Story creation and validation only.
"""

from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from .config import ConfigLoader, PrepareConfig, StageConfig
from .spawner import ClaudeSpawner, TaskResult


def log(msg: str) -> None:
    """Print with immediate flush for background visibility."""
    print(msg, flush=True)


@dataclass
class PipelineResult:
    """Result of Layer 0 execution."""
    success: bool
    story_id: Optional[str] = None
    story_file: Optional[str] = None
    validation_status: str = "not_run"
    stage_results: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class PipelineRunner:
    """
    Execute Layer 0 pipeline: create-story + validate.

    This is the innermost layer that prepares stories for development.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.config_loader = ConfigLoader(project_root)
        self.spawner = ClaudeSpawner(project_root)
        self.config: Optional[PrepareConfig] = None

    def run(self, story_id: Optional[str] = None) -> PipelineResult:
        """Run Layer 0: create-story + validate."""
        result = PipelineResult(success=False)

        try:
            # Step 0: Load config
            log("\n=== Step 0: Loading configuration ===")
            self.config = self.config_loader.load()
            self.spawner.set_config(self.config)
            log("  ✓ Config loaded successfully")

            # Step 1: Create/find story
            log("\n=== Step 1: Create or find story ===")
            story_id, story_file = self._resolve_story(story_id)
            result.story_id = story_id
            result.story_file = str(story_file) if story_file else None

            if not story_file:
                result.error = "Failed to create or find story file"
                log(f"  ✗ ERROR: {result.error}")
                return result

            log(f"  ✓ Story ID: {story_id}")
            log(f"  ✓ Story file: {story_file}")
            result.stage_results["create-story"] = "PASS"

            # Step 2: Validate story
            log("\n=== Step 2: Validating story ===")
            passed = self._run_stage("validate", story_id=story_id, story_file=str(story_file))
            result.stage_results["validate"] = "PASS" if passed else "FAIL"
            result.validation_status = "passed" if passed else "failed"

            if not passed:
                result.error = "Story validation failed"
                log(f"  ✗ ERROR: {result.error}")
                return result

            log(f"  ✓ Story validated successfully")

            # Success!
            result.success = True
            log("\n" + "=" * 50)
            log("✓ Layer 0 complete: Story is ready for development")
            log(f"  Story: {story_id}")
            log(f"  File: {story_file}")
            log("=" * 50)

            return result

        except Exception as e:
            result.error = f"Pipeline error: {e}"
            log(f"\n✗ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return result

    def _resolve_story(self, story_id: Optional[str]) -> tuple[Optional[str], Optional[Path]]:
        """
        Resolve story ID and file path.

        Returns: (story_id, story_file_path)
        """
        # If story_id provided, check if file exists
        if story_id:
            story_file = self.config_loader.find_story_file(story_id, self.config)
            if story_file:
                log(f"  ✓ Found existing story: {story_file}")
                return story_id, story_file

            # Story ID provided but file doesn't exist - need to create it
            log(f"  Story file not found for {story_id}, will create it")

        # Need to create story (either no ID provided, or ID provided but file missing)
        if self._is_enabled("create-story"):
            created_story_id, created_file = self._run_create_story_stage(story_id)
            if created_story_id and created_file:
                return created_story_id, created_file
            else:
                log("  ✗ Failed to create story")
                return None, None
        else:
            log("  ✗ create-story stage is disabled and story doesn't exist")
            return None, None

    def _run_create_story_stage(self, story_id: Optional[str]) -> tuple[Optional[str], Optional[Path]]:
        """Run the create-story stage and extract story_id and file path."""
        stage_config = self.config.stages.get("create-story")
        if not stage_config:
            log("  ✗ create-story stage not configured")
            return None, None

        log("  Running create-story workflow...")

        # Spawn agent with context variables
        result = self.spawner.spawn_stage(
            stage_name="create-story",
            timeout=stage_config.timeout,
            story_id=story_id if story_id else "",
            story_file="",
        )

        if not result.success:
            log(f"  ✗ create-story failed: {result.error}")
            return None, None

        # Parse output to find story_id and file path
        # The workflow should output something like:
        # "Created story: 1-2-user-auth at docs/stories/1-2-user-auth.md"
        story_id_created, story_file = self._parse_create_story_output(result.output, story_id)

        if story_id_created and story_file:
            log(f"  ✓ Created story: {story_id_created}")
            log(f"  ✓ File: {story_file}")
            return story_id_created, story_file
        else:
            log("  ✗ Failed to parse story ID and file from create-story output")
            return None, None

    def _parse_create_story_output(self, output: str, hint_story_id: Optional[str]) -> tuple[Optional[str], Optional[Path]]:
        """
        Parse create-story output to extract story_id and file path.

        Looks for patterns like:
        - "story_id: 1-2-user-auth"
        - "Created: docs/stories/1-2-user-auth.md"
        - "Story file: docs/stories/1-2-user-auth.md"
        """
        import re

        story_id = None
        story_file = None

        # Try to find story_id in output
        # Pattern 1: "story_id: X" or "Story ID: X"
        match = re.search(r'story[_\s]id:\s*([0-9]+-[0-9]+-[a-z0-9-]+)', output, re.IGNORECASE)
        if match:
            story_id = match.group(1)

        # Pattern 2: If hint provided, use it
        if not story_id and hint_story_id:
            story_id = hint_story_id

        # Pattern 3: Look for story ID in file path
        if not story_id:
            match = re.search(r'([0-9]+-[0-9]+-[a-z0-9-]+)\.md', output)
            if match:
                story_id = match.group(1)

        # Try to find story file path
        # Pattern 1: Full path mentioned
        for location_template in self.config.story_locations:
            if story_id:
                location = location_template.replace("${story_id}", story_id)
                path = self.project_root / location
                if path.exists():
                    story_file = path
                    break

        return story_id, story_file

    def _run_stage(self, stage_name: str, **context) -> bool:
        """
        Run a single stage with retry logic.

        Returns: True if stage passed, False otherwise
        """
        stage_config = self.config.stages.get(stage_name)
        if not stage_config or not stage_config.enabled:
            log(f"  ⊘ Stage '{stage_name}' disabled or not configured")
            return True  # Treat disabled as pass

        max_attempts = 1 + (stage_config.retry.max if stage_config.retry else 0)

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                log(f"  → Retry {attempt - 1}/{stage_config.retry.max}")

            # Spawn agent with context variables
            log(f"  Running {stage_name}...")
            result = self.spawner.spawn_stage(
                stage_name=stage_name,
                timeout=stage_config.timeout,
                **context
            )

            if result.success:
                log(f"  ✓ {stage_name} passed")
                return True

            log(f"  ✗ {stage_name} failed: {result.error}")

            # Check if we should retry
            if attempt < max_attempts and stage_config.on_failure == "fix_and_retry":
                log(f"  Attempting fix...")
                # For now, just retry. In the future, could spawn fix agent here
                continue

            # No more retries or not configured to retry
            return False

        return False

    def _build_prompt(self, stage_config: StageConfig, **context) -> str:
        """Build prompt with variable substitution."""
        if not stage_config.prompt:
            return f"{stage_config.workflow}\n{self.config.autonomy_instructions}"

        # Replace variables
        prompt = stage_config.prompt
        prompt = prompt.replace("{autonomy}", self.config.autonomy_instructions)
        prompt = prompt.replace("{project_root}", str(self.project_root))

        for key, value in context.items():
            placeholder = "{" + key + "}"
            prompt = prompt.replace(placeholder, str(value) if value else "")

        return prompt

    def _is_enabled(self, stage_name: str) -> bool:
        """Check if a stage is enabled."""
        stage = self.config.stages.get(stage_name)
        return stage is not None and stage.enabled

    def _should_abort(self, stage_name: str) -> bool:
        """Check if stage failure should abort pipeline."""
        stage = self.config.stages.get(stage_name)
        return stage is None or stage.on_failure == "abort"
