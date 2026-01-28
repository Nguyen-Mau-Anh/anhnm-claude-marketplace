"""Generic configuration loader with inheritance pattern.

Base classes and utilities for loading YAML configurations.
"""

import os
import re
import time
import yaml
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, TypeVar, Generic
from pydantic import BaseModel, Field, ValidationError


class RetryConfig(BaseModel):
    """Retry configuration for a stage."""
    max: int = 2
    fix_prompt: Optional[str] = None
    fix_agent: Optional[str] = None


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage."""
    order: float = 0  # Supports fractional ordering (e.g., 3.5)
    enabled: bool = True
    execution: str = "spawn"  # "spawn", "direct", "spawn_per_task", or "delegate"
    type: str = "bmad_workflow"  # "bmad_workflow" or "bash"
    workflow: Optional[str] = None
    command: Optional[str] = None
    delegate_to: Optional[str] = None
    condition: Optional[str] = None
    timeout: int = 300
    task_timeout: Optional[int] = None  # Per-task timeout for spawn_per_task execution
    on_failure: str = "abort"  # "abort", "fix_and_retry", "continue"
    retry: Optional[RetryConfig] = None
    blocking: bool = True
    description: Optional[str] = None
    prompt: Optional[str] = None
    task_prompt: Optional[str] = None  # Prompt template for single task execution
    story_prompt: Optional[str] = None  # Prompt template for all-at-once execution


class KnowledgeBaseConfig(BaseModel):
    """Configuration for knowledge base / lessons learned system."""
    enabled: bool = True
    max_lessons_per_stage: Optional[int] = None  # None = all lessons
    min_encounter_count: int = 1
    stage_overrides: Optional[Dict[str, Dict[str, int]]] = Field(default_factory=dict)


class TaskDecompositionConfig(BaseModel):
    """Configuration for task decomposition / task-by-task execution."""
    enabled: bool = True
    mode: str = "per_task"  # "per_task" or "single"


# Type variable for generic config
ConfigType = TypeVar('ConfigType', bound=BaseModel)


class BaseConfig(BaseModel):
    """Base configuration model for all orchestrators."""
    name: str
    version: str = "1.0.0"
    description: str = ""
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

    stages: Dict[str, StageConfig] = Field(default_factory=dict)
    output: List[str] = Field(default_factory=list)
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    task_decomposition: TaskDecompositionConfig = Field(default_factory=TaskDecompositionConfig)


class ConfigLoader(Generic[ConfigType]):
    """
    Generic configuration loader with inheritance pattern.

    Features:
    - Automatic fallback to default config on errors
    - Config caching for performance
    - Stage validation
    - Environment variable expansion
    - Atomic file writes

    Usage:
        class MyConfig(BaseConfig):
            custom_field: str = "default"

        loader = ConfigLoader(project_root, MyConfig, "my-skill")
        config = loader.load()
    """

    def __init__(
        self,
        project_root: Path,
        config_class: type[ConfigType],
        skill_name: str,
        default_config_path: Optional[Path] = None,
        logger: Optional[Any] = None,
    ):
        """
        Initialize config loader.

        Args:
            project_root: Project root directory
            config_class: Pydantic config model class
            skill_name: Name of the skill (e.g., "orchestrate-dev")
            default_config_path: Optional path to default config file
            logger: Optional logger instance (uses print if None)
        """
        self.project_root = Path(project_root)
        self.config_class = config_class
        self.skill_name = skill_name
        self.logger = logger

        # Config caching
        self._cached_config: Optional[ConfigType] = None
        self._cache_timestamp: float = 0

        # Default config in skill directory
        if default_config_path:
            self.default_config = default_config_path
        else:
            # Auto-detect from caller's location
            self.default_config = Path(__file__).parent.parent / "default.config.yaml"

        # Project config in docs folder
        self.project_config = self.project_root / "docs" / f"{skill_name}.config.yaml"

    def _log(self, message: str, level: str = "info") -> None:
        """Log message using logger or print as fallback."""
        if self.logger:
            if level == "error":
                self.logger.error(message)
            elif level == "warn":
                self.logger.warn(message)
            else:
                self.logger.info(message)
        else:
            prefix = "[Config]" if level == "info" else f"[Config:{level.upper()}]"
            print(f"{prefix} {message}")

    def expand_env_vars(self, value: str) -> str:
        """
        Expand environment variables in config values.

        Supports both ${VAR} and $VAR formats.

        Args:
            value: String possibly containing environment variables

        Returns:
            String with environment variables expanded
        """
        if not isinstance(value, str):
            return value

        # Replace ${VAR} format
        def replace_env_braces(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        # Replace $VAR format (uppercase letters, numbers, underscores)
        def replace_env_simple(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        value = re.sub(r'\$\{([^}]+)\}', replace_env_braces, value)
        value = re.sub(r'\$([A-Z_][A-Z0-9_]*)', replace_env_simple, value)

        return value

    def expand_dict_env_vars(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively expand environment variables in dictionary values."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.expand_env_vars(value)
            elif isinstance(value, dict):
                result[key] = self.expand_dict_env_vars(value)
            elif isinstance(value, list):
                result[key] = [
                    self.expand_env_vars(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def validate_stages(self, stages: Dict[str, StageConfig]) -> List[str]:
        """
        Validate stage configurations and return warnings.

        Args:
            stages: Dictionary of stage configurations

        Returns:
            List of warning messages (empty if all valid)
        """
        warnings = []

        # Check for duplicate orders
        orders = {}
        for name, stage in stages.items():
            if stage.order in orders:
                warnings.append(
                    f"Duplicate order {stage.order}: '{name}' and '{orders[stage.order]}'"
                )
            orders[stage.order] = name

        # Validate execution types
        valid_executions = {"spawn", "direct", "delegate"}
        for name, stage in stages.items():
            if stage.execution not in valid_executions:
                warnings.append(
                    f"Stage '{name}' has invalid execution type: '{stage.execution}' "
                    f"(valid: {', '.join(valid_executions)})"
                )

            # Validate required fields per execution type
            if stage.execution == "spawn":
                if not stage.prompt and not stage.workflow:
                    warnings.append(
                        f"Stage '{name}' (spawn) missing prompt or workflow"
                    )
            elif stage.execution == "direct":
                if not stage.command:
                    warnings.append(
                        f"Stage '{name}' (direct) missing command"
                    )
            elif stage.execution == "delegate":
                if not stage.delegate_to:
                    warnings.append(
                        f"Stage '{name}' (delegate) missing delegate_to"
                    )

        return warnings

    def load(self, use_cache: bool = True) -> ConfigType:
        """
        Load configuration with caching and robust error handling.

        Args:
            use_cache: If True, return cached config if available and not modified

        Returns:
            Loaded and validated configuration (never fails, returns default on errors)
        """
        # Check cache if enabled
        if use_cache and self._cached_config:
            try:
                # Check if file was modified since cache
                if self.project_config.exists():
                    mtime = self.project_config.stat().st_mtime
                    if mtime <= self._cache_timestamp:
                        self._log("Using cached config")
                        return self._cached_config
            except Exception as e:
                self._log(f"Cache check failed: {e}", "warn")
                # Continue to reload

        # Ensure docs folder exists
        try:
            self.project_config.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log(f"Could not create docs folder: {e}", "warn")

        # Copy default if project config doesn't exist
        if not self.project_config.exists():
            if self.default_config.exists():
                try:
                    shutil.copy(self.default_config, self.project_config)
                    self._log(f"Created {self.project_config}")
                    self._log("Customize this file for your project")
                except Exception as e:
                    self._log(f"Could not copy default config: {e}", "warn")
                    self._log("Using default config in memory", "warn")
                    # Return default instance as fallback
                    return self._create_default_config()
            else:
                self._log(f"Default config not found: {self.default_config}", "warn")
                self._log("Using minimal default config", "warn")
                # Return default instance as fallback
                return self._create_default_config()

        self._log(f"Loading config from {self.project_config}")

        try:
            # Load YAML with error handling
            with open(self.project_config, "r") as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                self._log("Config file is empty or invalid, using defaults", "warn")
                return self._create_default_config()

            # Expand environment variables
            data = self.expand_dict_env_vars(data)

            # Let Pydantic handle nested model parsing automatically
            # Don't pre-parse stages or knowledge_base - Pydantic will do it

            # Create and validate config instance
            try:
                config = self.config_class(**data)
            except ValidationError as e:
                self._log(f"Config validation failed: {e}", "error")
                self._log("Using default config", "warn")
                return self._create_default_config()

            # Validate stages and log warnings
            warnings = self.validate_stages(config.stages)
            for warning in warnings:
                self._log(warning, "warn")

            # Cache the config
            if use_cache:
                self._cached_config = config
                self._cache_timestamp = time.time()

            return config

        except yaml.YAMLError as e:
            self._log(f"YAML parsing error: {e}", "error")
            self._log("Using default config", "warn")
            return self._create_default_config()

        except FileNotFoundError:
            self._log(f"Config file disappeared: {self.project_config}", "warn")
            self._log("Using default config", "warn")
            return self._create_default_config()

        except Exception as e:
            self._log(f"Unexpected error loading config: {e}", "error")
            self._log("Using default config", "warn")
            return self._create_default_config()

    def _create_default_config(self) -> ConfigType:
        """
        Create default config instance as fallback.

        Returns:
            Default configuration instance
        """
        try:
            return self.config_class(name=self.skill_name)
        except Exception as e:
            self._log(f"Could not create default config: {e}", "error")
            # Last resort: create with minimal data
            try:
                return self.config_class(
                    name=self.skill_name,
                    version="1.0.0",
                    description=f"Default config for {self.skill_name}",
                )
            except Exception:
                # If even that fails, we have a bigger problem
                raise RuntimeError(
                    f"Cannot create default config for {self.skill_name}. "
                    f"Check your config class definition."
                )

    def clear_cache(self) -> None:
        """Clear cached configuration to force reload on next load() call."""
        self._cached_config = None
        self._cache_timestamp = 0
        self._log("Config cache cleared")

    def reload(self) -> ConfigType:
        """
        Force reload configuration from disk, bypassing cache.

        Returns:
            Freshly loaded configuration
        """
        self.clear_cache()
        return self.load(use_cache=False)

    def is_cached(self) -> bool:
        """
        Check if configuration is currently cached.

        Returns:
            True if cached config exists
        """
        return self._cached_config is not None

    def get_cache_age(self) -> Optional[float]:
        """
        Get age of cached config in seconds.

        Returns:
            Seconds since config was cached, or None if not cached
        """
        if not self._cached_config:
            return None
        return time.time() - self._cache_timestamp

    def find_story_file(
        self,
        story_id: str,
        config: BaseConfig,
        **extra_vars
    ) -> Optional[Path]:
        """
        Find story file in configured locations with flexible variable expansion.

        Supports both ${var} and {var} formats for all variables.

        Args:
            story_id: Story identifier
            config: Configuration with story_locations
            **extra_vars: Additional variables for template expansion

        Returns:
            Path to story file or None if not found
        """
        template_vars = {"story_id": story_id, **extra_vars}

        for location_template in config.story_locations:
            # Expand all template variables
            location = location_template
            for key, value in template_vars.items():
                # Support both ${var} and {var} formats
                location = location.replace(f"${{{key}}}", str(value))
                location = location.replace(f"{{{key}}}", str(value))

            # Expand environment variables
            location = self.expand_env_vars(location)

            path = self.project_root / location
            if path.exists():
                self._log(f"Found story file: {path}")
                return path

        self._log(f"Story file not found for {story_id}", "warn")
        self._log(f"Searched locations: {config.story_locations}", "warn")
        return None

    def save(self, config: ConfigType) -> None:
        """
        Save configuration to project config file with atomic write.

        Args:
            config: Configuration to save

        Raises:
            IOError: If save fails (safe - doesn't break pipeline)
        """
        try:
            # Ensure directory exists
            self.project_config.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict (mode='json' handles nested Pydantic models)
            config_dict = config.model_dump(mode='json')

            # Write to temp file first (atomic write pattern)
            temp_file = self.project_config.with_suffix('.yaml.tmp')

            with open(temp_file, "w") as f:
                yaml.dump(
                    config_dict,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True
                )

            # Atomic rename (replaces existing file)
            temp_file.replace(self.project_config)

            self._log(f"Saved to {self.project_config}")

            # Invalidate cache
            self._cached_config = None
            self._cache_timestamp = 0

        except Exception as e:
            self._log(f"Failed to save config: {e}", "error")
            # Clean up temp file if it exists
            try:
                temp_file = self.project_config.with_suffix('.yaml.tmp')
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
            # Don't raise - just log the error
            self._log("Config changes were not persisted", "warn")


def load_yaml(file_path: Path, fallback_to_empty: bool = True) -> Dict[str, Any]:
    """
    Load YAML file with error handling and optional fallback.

    Args:
        file_path: Path to YAML file
        fallback_to_empty: If True, return empty dict on error instead of raising

    Returns:
        Parsed YAML data (or empty dict if fallback enabled)

    Raises:
        FileNotFoundError: If file not found and fallback disabled
        ValueError: If YAML invalid and fallback disabled
        IOError: If other error and fallback disabled
    """
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError as e:
        if fallback_to_empty:
            print(f"[Config] File not found: {file_path}, using empty config")
            return {}
        raise FileNotFoundError(f"Config file not found: {file_path}") from e
    except yaml.YAMLError as e:
        if fallback_to_empty:
            print(f"[Config] Invalid YAML in {file_path}: {e}, using empty config")
            return {}
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e
    except Exception as e:
        if fallback_to_empty:
            print(f"[Config] Failed to load {file_path}: {e}, using empty config")
            return {}
        raise IOError(f"Failed to load config from {file_path}: {e}") from e


def save_yaml(file_path: Path, data: Dict[str, Any], atomic: bool = True) -> None:
    """
    Save data to YAML file with atomic write option.

    Args:
        file_path: Path to YAML file
        data: Data to save
        atomic: If True, use atomic write (write to temp file, then rename)

    Raises:
        IOError: If save fails
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            # Atomic write: write to temp file then rename
            temp_file = file_path.with_suffix('.yaml.tmp')

            with open(temp_file, "w") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True
                )

            # Atomic rename
            temp_file.replace(file_path)
        else:
            # Direct write
            with open(file_path, "w") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True
                )

    except Exception as e:
        # Clean up temp file if atomic write failed
        if atomic:
            try:
                temp_file = file_path.with_suffix('.yaml.tmp')
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
        raise IOError(f"Failed to save config to {file_path}: {e}") from e


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two configuration dictionaries with deep recursive merging.

    Override values take precedence over base values.
    Nested dictionaries are merged recursively.
    Lists and other types are replaced (not merged).

    Args:
        base: Base configuration
        override: Override configuration

    Returns:
        Merged configuration (new dict, does not modify inputs)

    Examples:
        >>> base = {"a": 1, "b": {"x": 1, "y": 2}}
        >>> override = {"b": {"y": 3, "z": 4}, "c": 5}
        >>> merge_configs(base, override)
        {'a': 1, 'b': {'x': 1, 'y': 3, 'z': 4}, 'c': 5}
    """
    # Deep copy to avoid modifying inputs
    result = {}

    # Start with all base keys
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = value.copy()
        else:
            result[key] = value

    # Merge override keys
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive merge for nested dicts
            result[key] = merge_configs(result[key], value)
        else:
            # Override value (handles new keys, non-dict values, and type changes)
            result[key] = value

    return result
