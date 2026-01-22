"""Story Completion Validator

Validates that a story file meets all completion requirements before
marking it as "Ready for Review".

CRITICAL: This prevents incomplete stories from being marked as complete.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class ValidationIssue:
    """A single validation issue found in the story."""
    severity: str  # ERROR, WARNING
    section: str
    line_num: int
    message: str
    context: str = ""


@dataclass
class ValidationResult:
    """Result of story validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    stats: Dict[str, int]


class StoryValidator:
    """Validates story files for completion readiness."""

    def __init__(self, story_file: Path):
        self.story_file = Path(story_file)
        self.content = ""
        self.lines = []

    def validate(self) -> ValidationResult:
        """Run all validation checks."""
        issues = []
        stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "total_acs": 0,
            "completed_acs": 0,
            "unchecked_tasks": 0,
            "unchecked_acs": 0,
            "not_done_markers": 0
        }

        # Read file
        try:
            self.content = self.story_file.read_text()
            self.lines = self.content.split('\n')
        except Exception as e:
            issues.append(ValidationIssue(
                severity="ERROR",
                section="File",
                line_num=0,
                message=f"Cannot read story file: {e}"
            ))
            return ValidationResult(is_valid=False, issues=issues, stats=stats)

        # Run validations
        self._check_required_sections(issues)
        self._check_tasks_completion(issues, stats)
        self._check_acceptance_criteria(issues, stats)
        self._check_not_done_markers(issues, stats)
        self._check_file_list(issues)

        # Determine overall validity
        error_count = sum(1 for i in issues if i.severity == "ERROR")
        is_valid = error_count == 0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            stats=stats
        )

    def _check_required_sections(self, issues: List[ValidationIssue]):
        """Check that required sections exist."""
        required_sections = [
            "## Description",
            "## Tasks",
            "## Acceptance Criteria",
            "## Status"
        ]

        for section in required_sections:
            if section not in self.content:
                issues.append(ValidationIssue(
                    severity="ERROR",
                    section="Structure",
                    line_num=0,
                    message=f"Missing required section: {section}"
                ))

    def _check_tasks_completion(self, issues: List[ValidationIssue], stats: Dict[str, int]):
        """Check that all tasks are marked complete."""
        in_tasks_section = False
        in_review_followups = False

        for line_num, line in enumerate(self.lines, start=1):
            # Track section boundaries
            if line.startswith("## Tasks"):
                in_tasks_section = True
                continue
            elif line.startswith("### Review Follow-ups"):
                in_review_followups = True
                continue
            elif line.startswith("##") and not line.startswith("## Tasks"):
                in_tasks_section = False
                in_review_followups = False
                continue

            # Check for task items
            if in_tasks_section:
                # Checked task: - [x]
                if re.match(r'^-\s+\[x\]', line, re.IGNORECASE):
                    stats["total_tasks"] += 1
                    stats["completed_tasks"] += 1
                # Unchecked task: - [ ]
                elif re.match(r'^-\s+\[\s*\]', line):
                    stats["total_tasks"] += 1
                    stats["unchecked_tasks"] += 1

                    # Extract task description
                    task_desc = re.sub(r'^-\s+\[\s*\]\s*', '', line).strip()

                    # Skip LOW priority review items (optional)
                    if in_review_followups and "[LOW]" in line:
                        continue

                    issues.append(ValidationIssue(
                        severity="ERROR",
                        section="Tasks",
                        line_num=line_num,
                        message=f"Incomplete task: {task_desc[:80]}",
                        context=line.strip()
                    ))

    def _check_acceptance_criteria(self, issues: List[ValidationIssue], stats: Dict[str, int]):
        """Check that all acceptance criteria are satisfied."""
        in_ac_section = False

        for line_num, line in enumerate(self.lines, start=1):
            # Track section boundaries
            if line.startswith("## Acceptance Criteria"):
                in_ac_section = True
                continue
            elif line.startswith("##") and not line.startswith("## Acceptance Criteria"):
                in_ac_section = False
                continue

            # Check for AC items
            if in_ac_section:
                # Checked AC: - [x]
                if re.match(r'^-\s+\[x\]', line, re.IGNORECASE):
                    stats["total_acs"] += 1
                    stats["completed_acs"] += 1
                # Unchecked AC: - [ ]
                elif re.match(r'^-\s+\[\s*\]', line):
                    stats["total_acs"] += 1
                    stats["unchecked_acs"] += 1

                    # Extract AC description
                    ac_desc = re.sub(r'^-\s+\[\s*\]\s*', '', line).strip()

                    issues.append(ValidationIssue(
                        severity="ERROR",
                        section="Acceptance Criteria",
                        line_num=line_num,
                        message=f"Unsatisfied AC: {ac_desc[:80]}",
                        context=line.strip()
                    ))

    def _check_not_done_markers(self, issues: List[ValidationIssue], stats: Dict[str, int]):
        """Check for NOT DONE markers indicating incomplete work."""
        in_ac_section = False

        for line_num, line in enumerate(self.lines, start=1):
            if line.startswith("## Acceptance Criteria"):
                in_ac_section = True
                continue
            elif line.startswith("##"):
                in_ac_section = False
                continue

            # Look for NOT DONE markers
            if "NOT DONE" in line or "❌" in line:
                stats["not_done_markers"] += 1

                # Get context
                context = line.strip()
                if len(context) > 100:
                    context = context[:100] + "..."

                issues.append(ValidationIssue(
                    severity="ERROR",
                    section="Acceptance Criteria" if in_ac_section else "Unknown",
                    line_num=line_num,
                    message="Found NOT DONE marker indicating incomplete work",
                    context=context
                ))

    def _check_file_list(self, issues: List[ValidationIssue]):
        """Check that File List section exists and is not empty."""
        if "## File List" not in self.content:
            issues.append(ValidationIssue(
                severity="WARNING",
                section="File List",
                line_num=0,
                message="Missing File List section"
            ))
            return

        # Extract File List section
        in_file_list = False
        has_files = False

        for line in self.lines:
            if line.startswith("## File List"):
                in_file_list = True
                continue
            elif line.startswith("##"):
                in_file_list = False
                continue

            if in_file_list and line.strip() and not line.strip().startswith("#"):
                has_files = True
                break

        if not has_files:
            issues.append(ValidationIssue(
                severity="WARNING",
                section="File List",
                line_num=0,
                message="File List section is empty - no files documented"
            ))


def print_validation_report(result: ValidationResult, story_file: Path):
    """Print validation results in a readable format."""
    print("\n" + "=" * 70)
    print(f"STORY VALIDATION REPORT: {story_file.name}")
    print("=" * 70)

    # Print statistics
    print("\n📊 STATISTICS:")
    print(f"  Tasks: {result.stats['completed_tasks']}/{result.stats['total_tasks']} complete")
    print(f"  Acceptance Criteria: {result.stats['completed_acs']}/{result.stats['total_acs']} satisfied")
    print(f"  Unchecked Tasks: {result.stats['unchecked_tasks']}")
    print(f"  Unchecked ACs: {result.stats['unchecked_acs']}")
    print(f"  NOT DONE markers: {result.stats['not_done_markers']}")

    # Print issues
    if result.issues:
        print(f"\n❌ VALIDATION ISSUES FOUND: {len(result.issues)}")

        errors = [i for i in result.issues if i.severity == "ERROR"]
        warnings = [i for i in result.issues if i.severity == "WARNING"]

        if errors:
            print(f"\n🔴 ERRORS ({len(errors)}):")
            for issue in errors:
                print(f"  Line {issue.line_num} [{issue.section}]: {issue.message}")
                if issue.context:
                    print(f"    → {issue.context}")

        if warnings:
            print(f"\n🟡 WARNINGS ({len(warnings)}):")
            for issue in warnings:
                print(f"  Line {issue.line_num} [{issue.section}]: {issue.message}")
                if issue.context:
                    print(f"    → {issue.context}")
    else:
        print("\n✅ NO ISSUES FOUND")

    # Print overall result
    print("\n" + "=" * 70)
    if result.is_valid:
        print("✅ VALIDATION PASSED - Story is ready for review")
    else:
        print("❌ VALIDATION FAILED - Story is NOT ready for review")
        print("\nThe story CANNOT be marked as 'Ready for Review' until all")
        print("tasks are complete and all acceptance criteria are satisfied.")
    print("=" * 70 + "\n")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 story_validator.py <story_file>")
        sys.exit(1)

    story_file = Path(sys.argv[1])

    if not story_file.exists():
        print(f"ERROR: Story file not found: {story_file}")
        sys.exit(1)

    validator = StoryValidator(story_file)
    result = validator.validate()

    print_validation_report(result, story_file)

    # Exit with error code if validation failed
    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
