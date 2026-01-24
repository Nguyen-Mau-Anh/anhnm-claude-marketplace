"""Task decomposition for large stories.

Parses story files and breaks them into individual tasks for execution.
Each task is executed by a separate agent in fresh context.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Task:
    """Represents a single task from a story."""
    index: int  # Task number (1-based)
    content: str  # Full task text including subtasks
    is_complete: bool  # Whether task is already checked [x]
    subtasks: List[str]  # List of subtask text


def parse_story_tasks(story_file: Path) -> List[Task]:
    """
    Parse story file and extract all tasks.

    Returns:
        List of Task objects, preserving order from story file.
    """
    if not story_file.exists():
        return []

    content = story_file.read_text()
    tasks = []

    # Find Tasks section (supports both "## Tasks" and "## Tasks / Subtasks")
    tasks_match = re.search(r'^##\s*Tasks\s*(/\s*Subtasks)?', content, re.MULTILINE)
    if not tasks_match:
        return []

    # Extract content after Tasks header until next ## section or end
    tasks_start = tasks_match.end()
    next_section = re.search(r'^##\s+', content[tasks_start:], re.MULTILINE)
    tasks_end = next_section.start() + tasks_start if next_section else len(content)
    tasks_content = content[tasks_start:tasks_end]

    # Parse tasks: - [ ] or - [x] at start of line
    task_pattern = r'^- \[([ x])\] (.+?)(?=^- \[|^##|\Z)'
    task_matches = re.finditer(task_pattern, tasks_content, re.MULTILINE | re.DOTALL)

    for i, match in enumerate(task_matches, 1):
        is_complete = match.group(1) == 'x'
        task_text = match.group(2).strip()

        # Extract subtasks (indented - [ ] or - [x])
        subtasks = []
        subtask_pattern = r'^\s+- \[([ x])\] (.+?)$'
        for subtask_match in re.finditer(subtask_pattern, task_text, re.MULTILINE):
            subtasks.append(subtask_match.group(2).strip())

        tasks.append(Task(
            index=i,
            content=task_text,
            is_complete=is_complete,
            subtasks=subtasks
        ))

    return tasks


def should_decompose(tasks: List[Task]) -> bool:
    """
    Determine if story should be decomposed into task-by-task execution.

    Args:
        tasks: List of parsed tasks

    Returns:
        True if story has any incomplete tasks, False otherwise
    """
    # Always decompose if there are any incomplete tasks
    incomplete_tasks = [t for t in tasks if not t.is_complete]

    # Return True if any incomplete tasks exist
    return len(incomplete_tasks) > 0


def get_incomplete_tasks(tasks: List[Task]) -> List[Task]:
    """Get only tasks that are not yet complete."""
    return [t for t in tasks if not t.is_complete]


def format_task_for_agent(task: Task, story_id: str, story_file: str) -> str:
    """
    Format a single task for agent execution.

    Returns a focused prompt for the agent to implement just this task.
    """
    task_text = task.content.split('\n')[0]  # First line only for display

    return f"""You are implementing TASK #{task.index} from story {story_id}.

Story file: {story_file}

TASK TO IMPLEMENT:
{task.content}

INSTRUCTIONS:
1. Read the story file to understand full context
2. Implement THIS TASK ONLY following TDD:
   - Write tests first (red)
   - Implement code to pass tests (green)
   - Refactor if needed
3. Run tests to verify this task works
4. Update the story file:
   - Mark task #{task.index} as [x] when complete
   - Update File List with changed files
   - Add to Change Log

DO NOT implement other tasks. Focus only on task #{task.index}.

Output:
- Summary of what was implemented
- Files changed
- Test results for this task
"""


def create_task_chunks(tasks: List[Task], chunk_size: int = 4) -> List[List[Task]]:
    """
    Group tasks into chunks for sequential execution.

    Useful if you want to process 3-4 tasks per agent instead of 1 task per agent.

    Args:
        tasks: List of tasks to chunk
        chunk_size: Number of tasks per chunk (default: 4)

    Returns:
        List of task chunks
    """
    chunks = []
    for i in range(0, len(tasks), chunk_size):
        chunks.append(tasks[i:i+chunk_size])
    return chunks


def format_tasks_summary(tasks: List[Task]) -> str:
    """Create a summary of tasks for logging."""
    total = len(tasks)
    complete = len([t for t in tasks if t.is_complete])
    incomplete = total - complete

    return f"{total} tasks total ({complete} complete, {incomplete} remaining)"
