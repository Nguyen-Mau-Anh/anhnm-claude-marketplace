"""Configuration loader for orchestrate-dev-test."""

import yaml
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Retry configuration for a stage."""
    max: int = 3
    fix_prompt: Optional[str] = None


class TrackConfig(BaseModel):
    """Configuration for a parallel track."""
    delegate_to: str
    timeout: int = 7200


class StageConfig(BaseModel):
    """Configuration for a single stage."""
    order: float = 0
    enabled: bool = True
    execution: str = "spawn"  # "spawn", "direct", "delegate", "parallel"
    timeout: int = 600
    on_failure: str = "abort"
    retry: Optional[RetryConfig] = None
    command: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    tracks: Optional[Dict[str, TrackConfig]] = None


class StoryTypesConfig(BaseModel):
    """Story type filtering configuration."""
    skip: List[str] = Field(default_factory=lambda: [
        "environment-setup",
        "documentation",
        "config-change",
        "dependency-update",
    ])
    require: List[str] = Field(default_factory=lambda: [
        "feature",
        "bugfix",
        "refactor",
        "api-change",
    ])


class DeploymentConfig(BaseModel):
    """Deployment settings."""
    enabled: bool = True
    health_check_timeout: int = 60
    methods: Optional[Dict[str, List[str]]] = None


class TestExecutionConfig(BaseModel):
    """Test execution settings."""
    smoke: Optional[Dict] = None
    critical_sqa: Optional[Dict] = None
    max_fix_attempts: int = 3


class OutputConfig(BaseModel):
    """Output directory settings."""
    status_dir: str = "state/l2"
    test_env_dir: str = "state/test-env"
    tdm_dir: str = "docs/test-design/matrices"


class DevTestConfig(BaseModel):
    """Layer 2 configuration model."""
    name: str = "orchestrate-dev-test"
    version: str = "1.0.0"
    description: str = "Layer 2: Development + parallel test design + test execution"
    layer: int = 2
    wraps: str = "orchestrate-dev"

    autonomy_instructions: str = """AUTONOMOUS MODE - NO QUESTIONS.
Skip all menus, confirmations, and user prompts.
Execute the task completely and output results only.
Do not ask follow-up questions."""

    story_locations: List[str] = Field(default_factory=lambda: [
        "state/stories/${story_id}.md",
        "docs/stories/${story_id}.md",
        "docs/sprint-artifacts/${story_id}.md",
    ])

    story_types: StoryTypesConfig = Field(default_factory=StoryTypesConfig)
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    test_execution: TestExecutionConfig = Field(default_factory=TestExecutionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    stages: Dict[str, StageConfig] = Field(default_factory=dict)


class ConfigLoader:
    """Load configuration with inheritance pattern."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.skill_dir = Path(__file__).parent.parent
        self.default_config = self.skill_dir / "default.config.yaml"
        self.project_config = self.project_root / "docs" / "orchestrate-dev-test.config.yaml"

    def load(self) -> DevTestConfig:
        """Load configuration, creating project config if needed."""
        self.project_config.parent.mkdir(parents=True, exist_ok=True)

        if not self.project_config.exists():
            if self.default_config.exists():
                shutil.copy(self.default_config, self.project_config)
                print(f"[Config] Created {self.project_config}")
                print("[Config] Customize this file for your project")
            else:
                raise FileNotFoundError(f"Default config not found: {self.default_config}")

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
                    if "tracks" in stage_data and isinstance(stage_data["tracks"], dict):
                        parsed_tracks = {}
                        for track_name, track_data in stage_data["tracks"].items():
                            if isinstance(track_data, dict):
                                parsed_tracks[track_name] = TrackConfig(**track_data)
                        stage_data["tracks"] = parsed_tracks
                    stages[name] = StageConfig(**stage_data)

        # Parse nested configs
        story_types = StoryTypesConfig()
        if "story_types" in data and isinstance(data["story_types"], dict):
            story_types = StoryTypesConfig(**data["story_types"])

        deployment = DeploymentConfig()
        if "deployment" in data and isinstance(data["deployment"], dict):
            deployment = DeploymentConfig(**data["deployment"])

        test_execution = TestExecutionConfig()
        if "test_execution" in data and isinstance(data["test_execution"], dict):
            test_execution = TestExecutionConfig(**data["test_execution"])

        output = OutputConfig()
        if "output" in data and isinstance(data["output"], dict):
            output = OutputConfig(**data["output"])

        return DevTestConfig(
            name=data.get("name", "orchestrate-dev-test"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            layer=data.get("layer", 2),
            wraps=data.get("wraps", "orchestrate-dev"),
            autonomy_instructions=data.get("autonomy_instructions", DevTestConfig.model_fields["autonomy_instructions"].default),
            story_locations=data.get("story_locations", []),
            story_types=story_types,
            deployment=deployment,
            test_execution=test_execution,
            output=output,
            stages=stages,
        )

    def find_story_file(self, story_id: str, config: DevTestConfig) -> Optional[Path]:
        """Find story file in configured locations."""
        for location_template in config.story_locations:
            location = location_template.replace("${story_id}", story_id)
            path = self.project_root / location
            if path.exists():
                return path
        return None
