"""Knowledge base manager for lessons learned.

Captures errors and fixes during pipeline execution, then injects
relevant lessons into future runs to prevent repeating mistakes.
"""

import yaml
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from .logger import Logger

logger = Logger("knowledge_base")


# Error type patterns for classification
ERROR_PATTERNS = {
    "unused_import": r"unused import|imported but unused",
    "missing_import": r"ModuleNotFoundError|ImportError|No module named",
    "circular_import": r"circular import",
    "type_mismatch": r"Type .* is not assignable|Incompatible types",
    "missing_type": r"Missing type annotation|Implicit Any",
    "optional_type": r"None.*not assignable|possibly undefined",
    "missing_await": r"coroutine.*was never awaited",
    "async_syntax": r"async.*invalid syntax",
    "assertion_failed": r"AssertionError|assert .* failed",
    "test_timeout": r"TimeoutError|Test timed out",
    "trailing_whitespace": r"trailing whitespace",
    "line_too_long": r"line too long",
    "unused_variable": r"unused variable|assigned but never used",
    "syntax_error": r"SyntaxError",
    "name_error": r"NameError",
    "attribute_error": r"AttributeError",
}


@dataclass
class Lesson:
    """A single lesson learned from error + fix."""
    id: str
    date: str
    story_id: Optional[str]
    stage: str
    error_type: str
    error_pattern: str
    error_message: str
    context: Dict
    fix: Dict
    success: bool
    times_encountered: int = 1
    times_prevented: int = 0


class KnowledgeBase:
    """Manage lessons learned knowledge base."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.kb_file = self.project_root / "state" / "knowledge-base.yaml"

        # Try to create directory, but don't fail if we can't
        try:
            self.kb_file.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            print(f"WARNING: Could not create knowledge base directory: {e}")
            # Continue anyway - save() will handle errors later

    def load(self) -> Dict:
        """Load knowledge base from YAML file."""
        logger.debug(f"Loading knowledge base from {self.kb_file}")

        if not self.kb_file.exists():
            logger.info("Knowledge base file not found, creating new")
            return {
                "metadata": {
                    "version": "1.0.0",
                    "total_lessons": 0,
                    "created": datetime.now().isoformat()
                },
                "lessons": {}
            }

        try:
            with open(self.kb_file) as f:
                data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    logger.warning("Invalid knowledge base format, returning empty")
                    return {
                        "metadata": {"version": "1.0.0", "total_lessons": 0},
                        "lessons": {}
                    }
                total_lessons = data.get("metadata", {}).get("total_lessons", 0)
                logger.info(f"Loaded knowledge base with {total_lessons} lessons")
                return data
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            logger.debug(f"KB file: {self.kb_file}")
            logger.warning("Returning empty knowledge base")
            return {
                "metadata": {"version": "1.0.0", "total_lessons": 0},
                "lessons": {}
            }

    def _make_serializable(self, obj):
        """
        Recursively convert objects to YAML-serializable types.

        Converts Path, datetime, and other non-serializable objects to strings.
        """
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Convert custom objects to dict
            return str(obj)
        else:
            # Primitive types (str, int, float, bool, None)
            return obj

    def save(self, data: Dict) -> None:
        """Save knowledge base to YAML file."""
        total_lessons = len(data.get("lessons", {}))
        logger.debug(f"Saving knowledge base with {total_lessons} lessons to {self.kb_file}")

        try:
            # Ensure directory exists
            self.kb_file.parent.mkdir(parents=True, exist_ok=True)

            # Update metadata
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            data["metadata"]["total_lessons"] = total_lessons

            # Ensure data is serializable (convert Path and other objects to strings)
            serializable_data = self._make_serializable(data)

            # Write to temp file first (atomic write)
            temp_file = self.kb_file.with_suffix('.yaml.tmp')
            with open(temp_file, "w") as f:
                yaml.dump(serializable_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            # Rename temp file to actual file (atomic operation)
            temp_file.replace(self.kb_file)
            logger.info(f"Saved knowledge base: {total_lessons} lessons")

        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")
            logger.debug(f"KB file: {self.kb_file}, Error type: {type(e).__name__}")
            # Don't crash - just log the error and continue

    def add_lesson(
        self,
        stage: str,
        error_type: str,
        error_pattern: str,
        error_message: str,
        context: Dict,
        fix: Dict,
        success: bool,
        story_id: Optional[str] = None,
    ) -> str:
        """
        Add new lesson to knowledge base with enhanced context.

        Args:
            stage: Pipeline stage where error occurred
            error_type: Type of error (from ERROR_PATTERNS)
            error_pattern: Pattern to match future errors
            error_message: Full error message
            context: Context information (files, environment, etc.)
            fix: Fix information (description, commands, prevention tips)
            success: Whether the fix was successful
            story_id: Optional story identifier

        Returns:
            lesson_id: Unique identifier for the lesson

        Behavior:
            - If similar lesson exists, increment times_encountered
            - If new lesson, create with sequential ID
            - Auto-extracts module name and import statement for import errors
        """
        kb = self.load()

        # Enhance context for import errors
        if error_type == "missing_import":
            module_name = extract_module_name(error_message)
            import_stmt = extract_import_statement(error_message)

            if module_name:
                context.setdefault("module_name", module_name)
            if import_stmt:
                context.setdefault("import_statement", import_stmt)

            # Add dependency files info
            dep_files = get_dependency_files(self.project_root)
            if dep_files:
                fix.setdefault("related_files", dep_files)

        # Check if similar lesson exists
        similar = self._find_similar_lesson(kb, error_pattern)
        if similar:
            # Increment encounter count
            encounters = kb["lessons"][similar].get("times_encountered", 1) + 1
            kb["lessons"][similar]["times_encountered"] = encounters
            kb["lessons"][similar]["last_encountered"] = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"Updated existing lesson {similar} (encounter #{encounters})")
            self.save(kb)
            return similar

        # Generate new lesson ID
        lesson_count = len([k for k in kb["lessons"] if k.startswith(f"{stage}-{error_type}")])
        lesson_id = f"{stage}-{error_type}-{lesson_count + 1:03d}"

        logger.info(f"Adding new lesson {lesson_id} for {stage}/{error_type}")
        logger.debug(f"Error pattern: {error_pattern[:100]}...")

        # Create lesson
        lesson = Lesson(
            id=lesson_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            story_id=story_id,
            stage=stage,
            error_type=error_type,
            error_pattern=error_pattern,
            error_message=error_message[:500],  # Truncate long messages
            context=context,
            fix=fix,
            success=success,
        )

        # Add to knowledge base
        kb["lessons"][lesson_id] = asdict(lesson)
        kb["lessons"][lesson_id]["last_encountered"] = lesson.date
        self.save(kb)

        return lesson_id

    def get_lessons_for_stage(self, stage: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get successful lessons for a stage.

        Args:
            stage: Stage name to get lessons for
            limit: Max lessons to return (None = all lessons, 0 = all lessons)

        Returns lessons sorted by:
        1. times_encountered (descending)
        2. times_prevented (descending)
        """
        logger.debug(f"Getting lessons for stage: {stage}")
        kb = self.load()

        # Filter by stage and success (with defensive checks)
        stage_lessons = []
        for lesson_id, lesson in kb.get("lessons", {}).items():
            # Skip invalid lessons
            if not isinstance(lesson, dict):
                continue

            # Check if lesson matches stage and is successful
            if lesson.get("stage") == stage and lesson.get("success", True):
                stage_lessons.append(lesson)

        # Sort by encounter count and prevention count
        stage_lessons.sort(
            key=lambda x: (x.get("times_encountered", 1), x.get("times_prevented", 0)),
            reverse=True
        )

        # Return all lessons if limit is None or 0
        result_count = len(stage_lessons) if (limit is None or limit == 0) else min(limit, len(stage_lessons))
        logger.info(f"Retrieved {result_count} lessons for stage {stage}")

        if limit is None or limit == 0:
            return stage_lessons

        return stage_lessons[:limit]

    def format_for_prompt(self, lessons: List[Dict], max_lessons: int = 5) -> str:
        """
        Format lessons for injection into prompts with actionable information.

        Returns formatted text with lesson details, commands, and prevention tips.
        """
        if not lessons:
            return ""

        lessons = lessons[:max_lessons]

        output = "\n" + "=" * 70 + "\n"
        output += "🧠 KNOWLEDGE BASE: LESSONS LEARNED (Avoid These Known Issues)\n"
        output += "=" * 70 + "\n\n"

        for i, lesson in enumerate(lessons, 1):
            times = lesson.get('times_encountered', 1)
            prevented = lesson.get('times_prevented', 0)

            output += f"Lesson #{i}: {lesson['id']}\n"
            output += f"  📊 Frequency: Seen {times}x"
            if prevented > 0:
                output += f", Prevented {prevented}x"
            output += "\n"
            output += f"  ⚠️  Error: {lesson['error_pattern']}\n"
            output += f"  💡 Fix: {lesson['fix'].get('description', 'See lesson details')}\n"

            # Add commands if available
            if 'commands' in lesson['fix'] and lesson['fix']['commands']:
                output += f"  🔧 Commands to run:\n"
                for cmd in lesson['fix']['commands']:
                    output += f"      $ {cmd}\n"

            # Add prevention tips
            if 'prevention_tips' in lesson['fix'] and lesson['fix']['prevention_tips']:
                output += f"  🛡️  How to prevent:\n"
                for tip in lesson['fix']['prevention_tips']:
                    output += f"      • {tip}\n"

            # Include code examples if available
            if 'code_before' in lesson['fix'] and 'code_after' in lesson['fix']:
                output += f"  📝 Code example:\n"
                output += f"      Before: {lesson['fix']['code_before']}\n"
                output += f"      After:  {lesson['fix']['code_after']}\n"

            # Add related files if available
            if 'related_files' in lesson['fix'] and lesson['fix']['related_files']:
                output += f"  📄 Check these files: {', '.join(lesson['fix']['related_files'])}\n"

            output += "\n"

        output += "=" * 70 + "\n"
        output += "⚡ IMPORTANT: Review these lessons before implementing to avoid repeating mistakes.\n"
        output += "=" * 70 + "\n"
        return output

    def track_prevention(self, stage: str, lessons_shown: List[str]) -> None:
        """
        Track when lessons prevent errors.

        Call this when a stage passes on first try after showing lessons.
        """
        kb = self.load()

        for lesson_id in lessons_shown:
            if lesson_id in kb.get("lessons", {}):
                lesson = kb["lessons"][lesson_id]
                if isinstance(lesson, dict):
                    lesson["times_prevented"] = lesson.get("times_prevented", 0) + 1

        self.save(kb)

    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        kb = self.load()

        lessons = kb.get("lessons", {})
        total_lessons = len(lessons)
        total_encounters = sum(
            l.get("times_encountered", 1) for l in lessons.values() if isinstance(l, dict)
        )
        total_prevented = sum(
            l.get("times_prevented", 0) for l in lessons.values() if isinstance(l, dict)
        )

        # By stage
        by_stage = {}
        for lesson in lessons.values():
            if not isinstance(lesson, dict):
                continue

            stage = lesson.get("stage")
            if not stage:
                continue

            if stage not in by_stage:
                by_stage[stage] = {"lessons": 0, "encounters": 0, "prevented": 0}
            by_stage[stage]["lessons"] += 1
            by_stage[stage]["encounters"] += lesson.get("times_encountered", 1)
            by_stage[stage]["prevented"] += lesson.get("times_prevented", 0)

        # By error type
        by_error_type = {}
        for lesson in kb["lessons"].values():
            error_type = lesson["error_type"]
            if error_type not in by_error_type:
                by_error_type[error_type] = {"lessons": 0, "encounters": 0}
            by_error_type[error_type]["lessons"] += 1
            by_error_type[error_type]["encounters"] += lesson.get("times_encountered", 1)

        return {
            "total_lessons": total_lessons,
            "total_encounters": total_encounters,
            "total_prevented": total_prevented,
            "by_stage": by_stage,
            "by_error_type": by_error_type
        }

    def export_markdown(self, group_by: str = "stage") -> str:
        """
        Export lessons as markdown.

        Args:
            group_by: "stage", "error_type", "date", or "all"
        """
        kb = self.load()

        md = "# Lessons Learned - Knowledge Base\n\n"
        md += f"**Total Lessons:** {kb['metadata']['total_lessons']}\n"
        md += f"**Last Updated:** {kb['metadata'].get('last_updated', 'N/A')}\n\n"
        md += "---\n\n"

        if group_by == "stage":
            # Group by stage
            stages = {}
            for lesson_id, lesson in kb["lessons"].items():
                stage = lesson["stage"]
                if stage not in stages:
                    stages[stage] = []
                stages[stage].append((lesson_id, lesson))

            for stage, lessons in sorted(stages.items()):
                md += f"## Stage: {stage.title()} ({len(lessons)} lessons)\n\n"
                for lesson_id, lesson in lessons:
                    md += f"### {lesson_id}\n\n"
                    md += f"**Error:** {lesson['error_pattern']}\n\n"
                    md += f"**Fix:** {lesson['fix'].get('description', 'N/A')}\n\n"
                    md += f"**Frequency:** {lesson.get('times_encountered', 1)} times encountered, "
                    md += f"{lesson.get('times_prevented', 0)} times prevented\n\n"
                    md += "---\n\n"

        return md

    def _find_similar_lesson(self, kb: Dict, error_pattern: str) -> Optional[str]:
        """Find similar existing lesson to avoid duplicates."""
        for lesson_id, lesson in kb.get("lessons", {}).items():
            if isinstance(lesson, dict) and lesson.get("error_pattern") == error_pattern:
                return lesson_id
        return None


def classify_error(error_message: str) -> str:
    """
    Classify error type based on message pattern.

    Returns:
        error_type: One of the predefined error types or "unknown"
    """
    for error_type, pattern in ERROR_PATTERNS.items():
        if re.search(pattern, error_message, re.IGNORECASE):
            return error_type
    return "unknown"


def extract_error_pattern(error_message: str) -> str:
    """
    Extract distinctive pattern from error message.

    Removes file paths, line numbers, and other noise to get core pattern.
    """
    # Remove file paths and line numbers
    pattern = re.sub(r'File ".*", line \d+', '', error_message)
    pattern = re.sub(r'\.py:\d+:', '', pattern)
    pattern = re.sub(r'line \d+', '', pattern)

    # Remove absolute paths
    pattern = re.sub(r'/[^\s]+/', '', pattern)

    # Take first meaningful line
    lines = [l.strip() for l in pattern.split('\n') if l.strip()]
    if lines:
        return lines[0][:200]  # Limit length

    return error_message[:200]


def extract_module_name(error_message: str) -> Optional[str]:
    """
    Extract module name from import error.

    Args:
        error_message: Error message containing import failure

    Returns:
        Module name if found, None otherwise
    """
    patterns = [
        r"No module named ['\"]([^'\"]+)['\"]",
        r"ModuleNotFoundError: ([^\s]+)",
        r"ImportError: cannot import name ['\"]([^'\"]+)['\"]",
        r"cannot import name ['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message)
        if match:
            return match.group(1)
    return None


def extract_import_statement(error_message: str) -> Optional[str]:
    """
    Extract the actual import statement from error message or traceback.

    Args:
        error_message: Error message/traceback containing import statement

    Returns:
        Import statement if found, None otherwise
    """
    patterns = [
        r"(from [\w.]+ import [\w, ]+)",
        r"(import [\w., ]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message)
        if match:
            return match.group(1)
    return None


def get_dependency_files(project_root: Path) -> List[str]:
    """
    Get list of dependency management files present in project.

    Args:
        project_root: Root directory of the project

    Returns:
        List of dependency file names that exist
    """
    potential_files = [
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Pipfile",
        "poetry.lock",
        "package.json",
    ]

    existing_files = []
    for filename in potential_files:
        filepath = project_root / filename
        if filepath.exists():
            existing_files.append(filename)

    return existing_files
