"""Configuration loader for orchestrate-test-design."""

import yaml
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Retry configuration for a stage."""
    max: int = 3
    fix_prompt: Optional[str] = None


class StageConfig(BaseModel):
    """Configuration for a single stage."""
    order: float = 0
    enabled: bool = True
    execution: str = "spawn"
    timeout: int = 600
    on_failure: str = "abort"  # "abort", "fix_and_retry", "continue"
    retry: Optional[RetryConfig] = None
    description: Optional[str] = None
    prompt: Optional[str] = None


class ValidationConfig(BaseModel):
    """Validation settings."""
    max_attempts: int = 3
    min_smoke_tests: int = 5
    min_critical_tests: int = 10
    require_error_cases: bool = True
    require_security_tests: bool = True
    require_boundary_tests: bool = True


class OutputConfig(BaseModel):
    """Output directory settings."""
    tdm_dir: str = "docs/test-design/matrices"
    status_dir: str = "state/test-design"
    validation_dir: str = "state/test-design/validation"


class TestDesignConfig(BaseModel):
    """Test Design configuration model."""
    name: str = "orchestrate-test-design"
    version: str = "1.0.0"
    description: str = "Test design track"
    layer: int = 0

    autonomy_instructions: str = """AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions."""

    story_locations: List[str] = Field(default_factory=lambda: [
        "state/stories/${story_id}.md",
        "docs/stories/${story_id}.md",
        "docs/sprint-artifacts/${story_id}.md",
    ])

    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    techniques: List[str] = Field(default_factory=lambda: ["EP", "BVA", "DT", "ST", "EG", "UC"])
    output: OutputConfig = Field(default_factory=OutputConfig)
    stages: Dict[str, StageConfig] = Field(default_factory=dict)


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
        self.project_config = self.project_root / "docs" / "orchestrate-test-design.config.yaml"

    def load(self) -> TestDesignConfig:
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

        # Parse validation config
        validation = ValidationConfig()
        if "validation" in data and isinstance(data["validation"], dict):
            validation = ValidationConfig(**data["validation"])

        # Parse output config
        output = OutputConfig()
        if "output" in data and isinstance(data["output"], dict):
            output = OutputConfig(**data["output"])

        return TestDesignConfig(
            name=data.get("name", "orchestrate-test-design"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            layer=data.get("layer", 0),
            autonomy_instructions=data.get("autonomy_instructions", TestDesignConfig.model_fields["autonomy_instructions"].default),
            story_locations=data.get("story_locations", []),
            validation=validation,
            techniques=data.get("techniques", ["EP", "BVA", "DT", "ST", "EG", "UC"]),
            output=output,
            stages=stages,
        )

    def find_story_file(self, story_id: str, config: TestDesignConfig) -> Optional[Path]:
        """Find story file in configured locations."""
        for location_template in config.story_locations:
            location = location_template.replace("${story_id}", story_id)
            path = self.project_root / location
            if path.exists():
                return path
        return None
