"""CLI interface for orchestrate-test-design."""

import typer
import signal
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console

from .runner import TestDesignRunner

# Global runner instance for cleanup
_runner_instance = None

app = typer.Typer(
    name="orchestrate-test-design",
    help="Test Design Track: TDM creation, test case generation, validation",
    invoke_without_command=True,
)
console = Console()


def get_project_root() -> Path:
    """
    Get the project root directory by walking up the tree.

    Looks for indicators of project root:
    - .git directory
    - .claude directory
    - package.json (Node projects)
    - pyproject.toml (Python projects)

    This ensures we always find the true project root, regardless of
    where the command is run from (e.g., packages/backend/).
    """
    current = Path.cwd().resolve()

    # Walk up the directory tree
    while True:
        # Check for project root indicators
        if (current / '.git').exists():
            return current
        if (current / '.claude').exists():
            return current
        if (current / 'package.json').exists():
            # Check if there's a parent with .git (in case of monorepo)
            parent = current.parent
            if parent != current and (parent / '.git').exists():
                return parent
            return current
        if (current / 'pyproject.toml').exists():
            # Check if there's a parent with .git (in case of monorepo)
            parent = current.parent
            if parent != current and (parent / '.git').exists():
                return parent
            return current

        # Move up one level
        parent = current.parent
        if parent == current:
            # Reached filesystem root, use cwd as fallback
            return Path.cwd().resolve()

        current = parent


def cleanup_and_exit(signum=None, frame=None):
    """Cleanup handler for signals and exit."""
    global _runner_instance

    if signum is not None:
        console.print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _runner_instance and hasattr(_runner_instance, 'spawner'):
        try:
            _runner_instance.spawner._cleanup_all_processes()
        except Exception as e:
            console.print(f"[red]Cleanup error: {e}[/red]")

    if signum is not None:
        sys.exit(1 if signum == signal.SIGINT else 0)


@app.callback(invoke_without_command=True)
def run_test_design(
    ctx: typer.Context,
    story_id: str = typer.Argument(
        ...,
        help="Story ID to create test design for"
    ),
):
    """
    Test Design Track: Create TDM and generate test cases.

    Usage:
        /orchestrate-test-design 1-2-user-auth
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    global _runner_instance

    # Register signal handlers for cleanup
    signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_and_exit)  # Termination

    project_root = get_project_root()
    runner = TestDesignRunner(project_root)
    _runner_instance = runner  # Store for cleanup

    console.print(f"\n[bold]Orchestrate Test Design[/bold]")
    console.print(f"Project: {project_root.name}")
    console.print(f"Story: {story_id}")
    console.print("=" * 50)

    try:
        result = runner.run(story_id=story_id)

        # Explicit cleanup before exit
        cleanup_and_exit()

        if result.success:
            console.print(f"\n[bold green]Test design completed successfully![/bold green]")
            console.print(f"TDM: {result.tdm_file}")
            raise typer.Exit(0)
        else:
            console.print(f"\n[bold red]Test design failed: {result.error}[/bold red]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print(f"\n[yellow]Interrupted by user, cleaning up...[/yellow]")
        cleanup_and_exit()
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]Unexpected error: {e}[/bold red]")
        cleanup_and_exit()
        raise


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
