"""Configuration loader for orchestrate-auto-dev.

This module imports and re-exports the enhanced config loader from _common
for backward compatibility and easy access.
"""

from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel, Field

# Import enhanced config loader from _common
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "_common"))

from config_loader import ConfigLoader as BaseConfigLoader, RetryConfig  # noqa: E402


class StageConfig(BaseModel):
    """Configuration for a single stage."""
    order: float = 0
    enabled: bool = True
    execution: str = "spawn"  # "spawn", "direct", "spawn_per_task", or "delegate"
    type: str = "bmad_workflow"
    workflow: Optional[str] = None
    command: Optional[str] = None
    delegate_to: Optional[str] = None
    timeout: int = 300
    task_timeout: Optional[int] = None  # Per-task timeout for spawn_per_task execution
    on_failure: str = "abort"  # "abort", "fix_and_retry", "continue"
    blocking: bool = True
    description: Optional[str] = None
    prompt: Optional[str] = None
    task_prompt: Optional[str] = None  # Prompt template for single task execution
    story_prompt: Optional[str] = None  # Prompt template for all-at-once execution
    retry: Optional[RetryConfig] = None
    condition: Optional[str] = None


class KnowledgeBaseConfig(BaseModel):
    """Knowledge base configuration."""
    enabled: bool = True
    max_lessons_per_stage: Optional[int] = None
    min_encounter_count: int = 1
    stage_overrides: Dict[str, Dict] = Field(default_factory=dict)


class TaskDecompositionConfig(BaseModel):
    """Task decomposition configuration."""
    enabled: bool = True
    mode: str = "per_task"  # "per_task" or "single"


class GitSettings(BaseModel):
    """Git settings configuration."""
    branch_prefix: str = "feat/"
    base_branch: str = "main"


class PRSettings(BaseModel):
    """PR settings configuration."""
    auto_merge: bool = False
    merge_method: str = "squash"  # "merge", "squash", "rebase"
    delete_branch_after_merge: bool = True


class AutoDevConfig(BaseModel):
    """Auto Dev configuration model."""
    name: str = "orchestrate-auto-dev"
    version: str = "1.0.0"
    description: str = "Automated development orchestrator - Complete story-to-PR pipeline"
    layer: int = 1

    autonomy_instructions: str = """AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions."""

    story_locations: List[str] = Field(default_factory=lambda: [
        "state/stories/${story_id}.md",
        "docs/stories/${story_id}.md",
        "docs/sprint-artifacts/${story_id}.md",
    ])

    # Knowledge base configuration
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)

    # Task decomposition configuration
    task_decomposition: TaskDecompositionConfig = Field(default_factory=TaskDecompositionConfig)

    # Git and PR settings
    git_settings: GitSettings = Field(default_factory=GitSettings)
    pr_settings: PRSettings = Field(default_factory=PRSettings)

    stages: Dict[str, StageConfig] = Field(default_factory=dict)

    output: List[str] = Field(default_factory=lambda: [
        "story_id", "story_file", "status", "pr_url"
    ])


class ConfigLoader(BaseConfigLoader):
    """Enhanced config loader for orchestrate-auto-dev."""

    def __init__(self, project_root: Path, logger: Optional[any] = None):
        """
        Initialize config loader.

        Args:
            project_root: Project root directory
            logger: Optional logger instance
        """
        super().__init__(
            project_root=project_root,
            config_class=AutoDevConfig,
            skill_name="orchestrate-auto-dev",
            logger=logger
        )
