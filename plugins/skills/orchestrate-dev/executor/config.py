"""Configuration loader with inheritance pattern."""

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
    order: float = 0  # Supports fractional ordering (e.g., 3.5 for between 3 and 4)
    enabled: bool = True
    execution: str = "spawn"  # "spawn", "direct", or "delegate"
    type: str = "bmad_workflow"  # "bmad_workflow" or "bash"
    workflow: Optional[str] = None
    command: Optional[str] = None
    delegate_to: Optional[str] = None  # For execution="delegate": skill to call (e.g., "/orchestrate-prepare")
    condition: Optional[str] = None
    timeout: int = 300
    on_failure: str = "abort"  # "abort", "fix_and_retry", "continue"
    retry: Optional[RetryConfig] = None
    blocking: bool = True
    description: Optional[str] = None
    # Prompt template for spawn stages - supports {story_id}, {story_file}, {errors}, {files_changed}
    prompt: Optional[str] = None


class KnowledgeBaseConfig(BaseModel):
    """Configuration for knowledge base / lessons learned system."""
    enabled: bool = True
    max_lessons_per_stage: Optional[int] = None  # None = all lessons
    min_encounter_count: int = 1
    stage_overrides: Optional[Dict[str, Dict[str, int]]] = Field(default_factory=dict)


class DevConfig(BaseModel):
    """Layer 1 configuration model."""
    name: str = "orchestrate-dev"
    version: str = "1.0.0"
    description: str = "Story development with quality checks"
    layer: int = 1

    # Autonomy instructions injected into all prompts via {autonomy}
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
        "review_findings", "status"
    ])

    # Knowledge base configuration
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)


class ConfigLoader:
    """
    Load configuration with inheritance pattern.

    1. Check for project config in docs/
    2. If not exists, copy default from skill folder
    3. Load and return config
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.skill_dir = Path(__file__).parent.parent
        self.default_config = self.skill_dir / "default.config.yaml"
        self.project_config = self.project_root / "docs" / "orchestrate-dev.config.yaml"

    def load(self) -> DevConfig:
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

        # Parse stages into StageConfig objects
        stages = {}
        if "stages" in data:
            for name, stage_data in data["stages"].items():
                if isinstance(stage_data, dict):
                    # Handle retry as nested object
                    if "retry" in stage_data and isinstance(stage_data["retry"], dict):
                        stage_data["retry"] = RetryConfig(**stage_data["retry"])
                    stages[name] = StageConfig(**stage_data)

        # Parse knowledge_base config
        kb_config = KnowledgeBaseConfig()
        if "knowledge_base" in data and isinstance(data["knowledge_base"], dict):
            kb_config = KnowledgeBaseConfig(**data["knowledge_base"])

        return DevConfig(
            name=data.get("name", "orchestrate-dev"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            layer=data.get("layer", 1),
            autonomy_instructions=data.get("autonomy_instructions", DevConfig.model_fields["autonomy_instructions"].default),
            story_locations=data.get("story_locations", []),
            stages=stages,
            output=data.get("output", []),
            knowledge_base=kb_config,
        )

    def find_story_file(self, story_id: str, config: DevConfig) -> Optional[Path]:
        """Find story file in configured locations."""
        for location_template in config.story_locations:
            location = location_template.replace("${story_id}", story_id)
            path = self.project_root / location
            if path.exists():
                return path
        return None
