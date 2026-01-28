"""Input validation and schema checking.

Provides validation functions for common orchestrator inputs.
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from .logger import Logger

logger = Logger("validators")


def validate_story_id(story_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate story ID format.

    Expected formats:
    - epic-story: "1-2-feature-name"
    - simple: "story-123"
    - jira-style: "PROJ-123"

    Args:
        story_id: Story identifier to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not story_id:
        logger.warning("Story ID validation failed: empty")
        return False, "Story ID cannot be empty"

    if len(story_id) > 100:
        logger.warning(f"Story ID validation failed: too long ({len(story_id)} chars)")
        return False, "Story ID too long (max 100 characters)"

    # Allow alphanumeric, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', story_id):
        logger.warning(f"Story ID validation failed: invalid characters in '{story_id}'")
        return False, "Story ID can only contain letters, numbers, hyphens, and underscores"

    # Check for common patterns
    valid_patterns = [
        r'^\d+-\d+-.+$',  # Epic-story: 1-2-feature
        r'^[A-Z]+-\d+$',  # JIRA: PROJ-123
        r'^story-\d+$',   # Simple: story-123
        r'^[a-z0-9-_]+$', # General kebab-case
    ]

    if not any(re.match(pattern, story_id) for pattern in valid_patterns):
        logger.warning(f"Story ID validation failed: '{story_id}' doesn't match expected formats")
        return False, f"Story ID '{story_id}' doesn't match expected formats"

    logger.debug(f"Story ID validation passed: {story_id}")
    return True, None


def validate_file_exists(
    file_path: Path,
    must_be_file: bool = True,
    must_be_readable: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Validate file existence and permissions.

    Args:
        file_path: Path to validate
        must_be_file: Must be a file (not directory)
        must_be_readable: Must have read permissions

    Returns:
        Tuple of (is_valid, error_message)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.warning(f"File validation failed: {file_path} does not exist")
        return False, f"Path does not exist: {file_path}"

    if must_be_file and not file_path.is_file():
        logger.warning(f"File validation failed: {file_path} is not a file")
        return False, f"Path is not a file: {file_path}"

    if must_be_readable:
        try:
            with open(file_path, 'r') as f:
                f.read(1)
        except PermissionError:
            logger.warning(f"File validation failed: {file_path} is not readable")
            return False, f"File is not readable: {file_path}"
        except Exception as e:
            logger.warning(f"File validation failed: cannot read {file_path}: {e}")
            return False, f"Cannot read file: {e}"

    logger.debug(f"File validation passed: {file_path.name}")
    return True, None


def validate_directory_exists(
    directory: Path,
    must_be_writable: bool = False
) -> tuple[bool, Optional[str]]:
    """
    Validate directory existence and permissions.

    Args:
        directory: Path to validate
        must_be_writable: Must have write permissions

    Returns:
        Tuple of (is_valid, error_message)
    """
    directory = Path(directory)

    if not directory.exists():
        logger.warning(f"Directory validation failed: {directory} does not exist")
        return False, f"Directory does not exist: {directory}"

    if not directory.is_dir():
        logger.warning(f"Directory validation failed: {directory} is not a directory")
        return False, f"Path is not a directory: {directory}"

    if must_be_writable:
        test_file = directory / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            logger.warning(f"Directory validation failed: {directory} is not writable")
            return False, f"Directory is not writable: {directory}"
        except Exception as e:
            logger.warning(f"Directory validation failed: cannot write to {directory}: {e}")
            return False, f"Cannot write to directory: {e}"

    logger.debug(f"Directory validation passed: {directory}")
    return True, None


def validate_config(config: Dict[str, Any], required_keys: List[str]) -> tuple[bool, Optional[str]]:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary
        required_keys: List of required keys

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(config, dict):
        logger.warning("Config validation failed: not a dictionary")
        return False, "Config must be a dictionary"

    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        logger.warning(f"Config validation failed: missing keys {missing_keys}")
        return False, f"Missing required config keys: {', '.join(missing_keys)}"

    logger.debug(f"Config validation passed: {len(required_keys)} required keys present")
    return True, None


def validate_stage_config(stage: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate stage configuration.

    Args:
        stage: Stage configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ['order', 'enabled', 'execution']
    valid, error = validate_config(stage, required_keys)

    if not valid:
        return False, error

    # Validate execution type
    valid_executions = ['spawn', 'direct', 'delegate']
    if stage['execution'] not in valid_executions:
        logger.warning(f"Stage validation failed: invalid execution type '{stage['execution']}'")
        return False, f"Invalid execution type: {stage['execution']}. Must be one of {valid_executions}"

    # Validate order is numeric
    try:
        float(stage['order'])
    except (ValueError, TypeError):
        logger.warning(f"Stage validation failed: order not numeric ({stage['order']})")
        return False, f"Stage order must be numeric, got: {stage['order']}"

    # Validate timeout if present
    if 'timeout' in stage:
        try:
            timeout = int(stage['timeout'])
            if timeout <= 0:
                logger.warning("Stage validation failed: timeout must be positive")
                return False, "Timeout must be positive"
        except (ValueError, TypeError):
            logger.warning(f"Stage validation failed: timeout not an integer ({stage['timeout']})")
            return False, f"Timeout must be an integer, got: {stage['timeout']}"

    logger.debug("Stage config validation passed")
    return True, None


def validate_timeout(timeout: int, min_seconds: int = 1, max_seconds: int = 7200) -> tuple[bool, Optional[str]]:
    """
    Validate timeout value.

    Args:
        timeout: Timeout in seconds
        min_seconds: Minimum allowed timeout
        max_seconds: Maximum allowed timeout

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        timeout = int(timeout)
    except (ValueError, TypeError):
        logger.warning(f"Timeout validation failed: not an integer ({type(timeout).__name__})")
        return False, f"Timeout must be an integer, got: {type(timeout).__name__}"

    if timeout < min_seconds:
        logger.warning(f"Timeout validation failed: too short ({timeout}s < {min_seconds}s)")
        return False, f"Timeout too short: {timeout}s (minimum: {min_seconds}s)"

    if timeout > max_seconds:
        logger.warning(f"Timeout validation failed: too long ({timeout}s > {max_seconds}s)")
        return False, f"Timeout too long: {timeout}s (maximum: {max_seconds}s)"

    logger.debug(f"Timeout validation passed: {timeout}s")
    return True, None


def validate_prompt(prompt: str, max_length: int = 50000) -> tuple[bool, Optional[str]]:
    """
    Validate prompt text.

    Args:
        prompt: Prompt text
        max_length: Maximum prompt length

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not prompt:
        logger.warning("Prompt validation failed: empty")
        return False, "Prompt cannot be empty"

    if not isinstance(prompt, str):
        logger.warning(f"Prompt validation failed: not a string ({type(prompt).__name__})")
        return False, f"Prompt must be string, got: {type(prompt).__name__}"

    if len(prompt) > max_length:
        logger.warning(f"Prompt validation failed: too long ({len(prompt)} > {max_length} chars)")
        return False, f"Prompt too long: {len(prompt)} characters (max: {max_length})"

    logger.debug(f"Prompt validation passed: {len(prompt)} characters")
    return True, None


# Convenience function for validation with exception
def validate_or_raise(is_valid: bool, error_message: Optional[str], exception_class=ValueError) -> None:
    """
    Raise exception if validation failed.

    Args:
        is_valid: Validation result
        error_message: Error message
        exception_class: Exception to raise

    Raises:
        exception_class if not valid
    """
    if not is_valid:
        raise exception_class(error_message)
