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
        self.kb_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict:
        """Load knowledge base from YAML file."""
        if not self.kb_file.exists():
            return {
                "metadata": {
                    "version": "1.0.0",
                    "total_lessons": 0,
                    "created": datetime.now().isoformat()
                },
                "lessons": {}
            }

        with open(self.kb_file) as f:
            return yaml.safe_load(f) or {
                "metadata": {"version": "1.0.0", "total_lessons": 0},
                "lessons": {}
            }

    def save(self, data: Dict) -> None:
        """Save knowledge base to YAML file."""
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        data["metadata"]["total_lessons"] = len(data.get("lessons", {}))

        with open(self.kb_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

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
        Add new lesson to knowledge base.

        Returns:
            lesson_id: Unique identifier for the lesson

        Behavior:
            - If similar lesson exists, increment times_encountered
            - If new lesson, create with sequential ID
        """
        kb = self.load()

        # Check if similar lesson exists
        similar = self._find_similar_lesson(kb, error_pattern)
        if similar:
            # Increment encounter count
            kb["lessons"][similar]["times_encountered"] += 1
            kb["lessons"][similar]["last_encountered"] = datetime.now().strftime("%Y-%m-%d")
            self.save(kb)
            return similar

        # Generate new lesson ID
        lesson_count = len([k for k in kb["lessons"] if k.startswith(f"{stage}-{error_type}")])
        lesson_id = f"{stage}-{error_type}-{lesson_count + 1:03d}"

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
        kb = self.load()

        # Filter by stage and success
        stage_lessons = [
            lesson for lesson_id, lesson in kb["lessons"].items()
            if lesson["stage"] == stage and lesson.get("success", True)
        ]

        # Sort by encounter count and prevention count
        stage_lessons.sort(
            key=lambda x: (x.get("times_encountered", 1), x.get("times_prevented", 0)),
            reverse=True
        )

        # Return all lessons if limit is None or 0
        if limit is None or limit == 0:
            return stage_lessons

        return stage_lessons[:limit]

    def format_for_prompt(self, lessons: List[Dict], max_lessons: int = 5) -> str:
        """
        Format lessons for injection into prompts.

        Returns formatted text with lesson details for LLM consumption.
        """
        if not lessons:
            return ""

        lessons = lessons[:max_lessons]

        output = "\nKNOWN ISSUES TO AVOID (from previous runs):\n"
        output += "━" * 60 + "\n"

        for i, lesson in enumerate(lessons, 1):
            times = lesson.get('times_encountered', 1)
            output += f"Lesson #{i} ({lesson['id']}) [Seen {times} time{'s' if times > 1 else ''}]:\n"
            output += f"  ⚠ Error Pattern: {lesson['error_pattern']}\n"
            output += f"  💡 Fix: {lesson['fix'].get('description', 'See lesson details')}\n"

            # Include code examples if available
            if 'code_before' in lesson['fix'] and 'code_after' in lesson['fix']:
                output += f"\n  Before: {lesson['fix']['code_before']}\n"
                output += f"  After:  {lesson['fix']['code_after']}\n"

            output += "\n"

        output += "━" * 60 + "\n"
        return output

    def track_prevention(self, stage: str, lessons_shown: List[str]) -> None:
        """
        Track when lessons prevent errors.

        Call this when a stage passes on first try after showing lessons.
        """
        kb = self.load()

        for lesson_id in lessons_shown:
            if lesson_id in kb["lessons"]:
                kb["lessons"][lesson_id]["times_prevented"] = \
                    kb["lessons"][lesson_id].get("times_prevented", 0) + 1

        self.save(kb)

    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        kb = self.load()

        total_lessons = len(kb["lessons"])
        total_encounters = sum(l.get("times_encountered", 1) for l in kb["lessons"].values())
        total_prevented = sum(l.get("times_prevented", 0) for l in kb["lessons"].values())

        # By stage
        by_stage = {}
        for lesson in kb["lessons"].values():
            stage = lesson["stage"]
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
        for lesson_id, lesson in kb["lessons"].items():
            if lesson["error_pattern"] == error_pattern:
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
