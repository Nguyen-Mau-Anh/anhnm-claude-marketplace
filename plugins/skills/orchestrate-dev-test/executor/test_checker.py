"""Test requirement checker for orchestrate-dev-test.

Determines whether a story requires test design/execution based on story type.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from .config import DevTestConfig


def extract_story_type(story_file: Path) -> Optional[str]:
    """
    Extract story type from story file content.

    Looks for patterns like:
    - type: feature
    - story_type: bugfix
    - ## Type: refactor
    """
    try:
        content = story_file.read_text()

        # Try YAML frontmatter pattern
        type_match = re.search(r'^type:\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
        if type_match:
            return type_match.group(1).lower()

        # Try story_type pattern
        type_match = re.search(r'^story_type:\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
        if type_match:
            return type_match.group(1).lower()

        # Try markdown heading pattern
        type_match = re.search(r'^##\s*Type:\s*(\w+)', content, re.MULTILINE | re.IGNORECASE)
        if type_match:
            return type_match.group(1).lower()

        # Try inferring from story title or content
        content_lower = content.lower()

        if 'documentation' in content_lower or 'docs' in content_lower:
            return 'documentation'
        if 'config' in content_lower or 'configuration' in content_lower:
            return 'config-change'
        if 'dependency' in content_lower or 'upgrade' in content_lower:
            return 'dependency-update'
        if 'bugfix' in content_lower or 'bug fix' in content_lower or 'fix:' in content_lower:
            return 'bugfix'
        if 'refactor' in content_lower:
            return 'refactor'

        # Default to feature if we can't determine
        return 'feature'

    except Exception as e:
        print(f"[test_checker] Warning: Could not read story file: {e}")
        return None


def should_skip_tests(story_file: Path, config: DevTestConfig) -> Tuple[bool, str]:
    """
    Determine if tests should be skipped for this story.

    Args:
        story_file: Path to the story file
        config: DevTestConfig with story type rules

    Returns:
        Tuple of (should_skip, reason)
    """
    story_type = extract_story_type(story_file)

    if not story_type:
        # If we can't determine type, run tests to be safe
        return False, "Could not determine story type, running tests by default"

    # Check if type is in skip list
    if story_type in config.story_types.skip:
        return True, f"Story type '{story_type}' is in skip list"

    # Check if type requires tests
    if story_type in config.story_types.require:
        return False, f"Story type '{story_type}' requires tests"

    # Default: don't skip (run tests)
    return False, f"Story type '{story_type}' not explicitly configured, running tests by default"


def check_test_requirement(
    story_id: str,
    story_file: Path,
    config: DevTestConfig
) -> Tuple[bool, str, str]:
    """
    Check if tests are required for this story.

    Args:
        story_id: Story identifier
        story_file: Path to story file
        config: DevTestConfig

    Returns:
        Tuple of (tests_required, story_type, reason)
    """
    story_type = extract_story_type(story_file) or "unknown"
    should_skip, reason = should_skip_tests(story_file, config)

    return (not should_skip, story_type, reason)
