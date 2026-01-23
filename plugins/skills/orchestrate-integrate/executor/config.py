"""Configuration loader for orchestrate-integrate Layer 2."""

import yaml
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Retry configuration for a stage."""
    max: int = 2
    fix_prompt: Optional[str] = None
    fix_agent: Optional[str] = None


class StageConfig(BaseModel):
    """Configuration for a single stage."""
    order: float = 0
    enabled: bool = True
    execution: str = "spawn"  # "spawn" or "direct"
    type: str = "bmad_workflow"
    workflow: Optional[str] = None
    command: Optional[str] = None
    condition: Optional[str] = None
    timeout: int = 300
    on_failure: str = "abort"
    retry: Optional[RetryConfig] = None
    blocking: bool = True
    description: Optional[str] = None
    prompt: Optional[str] = None


class KnowledgeBaseConfig(BaseModel):
    """Configuration for knowledge base system."""
    enabled: bool = True
    max_lessons_per_stage: Optional[int] = None
    min_encounter_count: int = 1
    stage_overrides: Optional[Dict[str, Dict[str, int]]] = Field(default_factory=dict)


class TaskDecompositionConfig(BaseModel):
    """Configuration for task decomposition."""
    enabled: bool = True
    threshold: int = 6


class PRSettingsConfig(BaseModel):
    """PR settings for Layer 2."""
    auto_merge: bool = False
    merge_method: str = "squash"  # "squash", "merge", "rebase"
    delete_branch_after_merge: bool = True
    require_reviews: int = 0
    wait_for_checks: bool = True
    title_template: str = "feat: {story_title}"
    description_template: str = "## Story\n{story_id}: {story_title}\n\n{changes_summary}"


class GitSettingsConfig(BaseModel):
    """Git settings for Layer 2."""
    branch_prefix: str = "feat/"
    base_branch: str = "main"
    commit_message_template: str = "{commit_type}: {story_title}\n\nStory: {story_id}\n\n{changes_summary}"


class IntegrateConfig(BaseModel):
    """Layer 2 configuration model (extends Layer 1)."""
    name: str = "orchestrate-integrate"
    version: str = "1.0.0"
    description: str = "Complete integration pipeline"
    layer: int = 2

    autonomy_instructions: str = """AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions."""

    story_locations: List[str] = Field(default_factory=lambda: [
        "state/stories/${story_id}.md",
        "docs/stories/${story_id}.md",
        "docs/sprint-artifacts/${story_id}.md",
    ])

    stages: Dict[str, StageConfig] = Field(default_factory=dict)

    output: List[str] = Field(default_factory=lambda: [
        "story_id", "story_file", "files_changed",
        "lint_result", "typecheck_result", "test_results",
        "review_findings", "commit_hash", "branch_name",
        "pr_number", "pr_url", "pr_status", "merge_status", "status"
    ])

    # From Layer 1
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    task_decomposition: TaskDecompositionConfig = Field(default_factory=TaskDecompositionConfig)

    # Layer 2 specific
    pr_settings: PRSettingsConfig = Field(default_factory=PRSettingsConfig)
    git_settings: GitSettingsConfig = Field(default_factory=GitSettingsConfig)


class ConfigLoader:
    """
    Load Layer 2 configuration.

    1. Check for project config in docs/
    2. If not exists, copy default from skill folder
    3. Load and return config
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.skill_dir = Path(__file__).parent.parent
        self.default_config = self.skill_dir / "default.config.yaml"
        self.project_config = self.project_root / "docs" / "orchestrate-integrate.config.yaml"

    def load(self) -> IntegrateConfig:
        """Load configuration, creating project config if needed."""
        # Ensure docs folder exists
        self.project_config.parent.mkdir(parents=True, exist_ok=True)

        # Copy default if project config doesn't exist
        if not self.project_config.exists():
            if self.default_config.exists():
                shutil.copy(self.default_config, self.project_config)
                print(f"[Config] Created {self.project_config}")
                print("[Config] Customize this file for your project")
            else:
                raise FileNotFoundError(f"Default config not found: {self.default_config}")

        # Load project config
        print(f"[Config] Using {self.project_config}")

        with open(self.project_config, "r") as f:
            data = yaml.safe_load(f)

        # Parse stages
        stages = {}
        if "stages" in data:
            for name, stage_data in data["stages"].items():
                if isinstance(stage_data, dict):
                    if "retry" in stage_data and isinstance(stage_data["retry"], dict):
                        stage_data["retry"] = RetryConfig(**stage_data["retry"])
                    stages[name] = StageConfig(**stage_data)

        # Parse knowledge_base config
        kb_config = KnowledgeBaseConfig()
        if "knowledge_base" in data and isinstance(data["knowledge_base"], dict):
            kb_config = KnowledgeBaseConfig(**data["knowledge_base"])

        # Parse task_decomposition config
        td_config = TaskDecompositionConfig()
        if "task_decomposition" in data and isinstance(data["task_decomposition"], dict):
            td_config = TaskDecompositionConfig(**data["task_decomposition"])

        # Parse PR settings
        pr_config = PRSettingsConfig()
        if "pr_settings" in data and isinstance(data["pr_settings"], dict):
            pr_config = PRSettingsConfig(**data["pr_settings"])

        # Parse Git settings
        git_config = GitSettingsConfig()
        if "git_settings" in data and isinstance(data["git_settings"], dict):
            git_config = GitSettingsConfig(**data["git_settings"])

        return IntegrateConfig(
            name=data.get("name", "orchestrate-integrate"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            layer=data.get("layer", 2),
            autonomy_instructions=data.get("autonomy_instructions", IntegrateConfig.model_fields["autonomy_instructions"].default),
            story_locations=data.get("story_locations", []),
            stages=stages,
            output=data.get("output", []),
            knowledge_base=kb_config,
            task_decomposition=td_config,
            pr_settings=pr_config,
            git_settings=git_config,
        )

    def find_story_file(self, story_id: str, config: IntegrateConfig) -> Optional[Path]:
        """Find story file in configured locations."""
        for location_template in config.story_locations:
            location = location_template.replace("${story_id}", story_id)
            path = self.project_root / location
            if path.exists():
                return path
        return None
