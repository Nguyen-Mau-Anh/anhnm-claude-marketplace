"""CLI interface for orchestrate-auto-dev."""

import sys
from pathlib import Path


def main():
    """Main entry point for orchestrate-auto-dev."""

    # Get project root (4 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent.parent

    # Parse arguments
    story_id = None
    if len(sys.argv) > 1:
        story_id = sys.argv[1]

    print(f"[orchestrate-auto-dev] Starting automated development orchestrator")
    print(f"[orchestrate-auto-dev] Project root: {project_root}")

    if story_id:
        print(f"[orchestrate-auto-dev] Story ID: {story_id}")
    else:
        print(f"[orchestrate-auto-dev] No story ID provided")
        print(f"Usage: orchestrate-auto-dev <story_id>")
        sys.exit(1)

    # Import and run pipeline
    from .runner import AutoDevRunner

    runner = AutoDevRunner(project_root)
    result = runner.run(story_id)

    if result.success:
        print(f"\n[orchestrate-auto-dev] ✅ SUCCESS")
        print(f"Story: {result.story_id}")
        print(f"Story file: {result.story_file}")
        sys.exit(0)
    else:
        print(f"\n[orchestrate-auto-dev] ❌ FAILED")
        print(f"Error: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
