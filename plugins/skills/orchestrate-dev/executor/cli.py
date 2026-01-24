"""CLI interface for orchestrate-dev Layer 1."""

import typer
import signal
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console

from .runner import PipelineRunner

# Global runner instance for cleanup
_runner_instance = None

app = typer.Typer(
    name="orchestrate-dev",
    help="Layer 1: Story development with quality checks",
    invoke_without_command=True,
)
console = Console()


def get_project_root() -> Path:
    """
    Get the project root directory.

    Handles the case where we're running from inside .claude/skills/orchestrate-dev
    when called via subprocess delegation from Layer 2.
    """
    cwd = Path.cwd()

    # Check if we're inside .claude/skills/ directory
    # If so, go up to find the actual project root
    parts = cwd.parts
    if '.claude' in parts and 'skills' in parts:
        # Find the index of .claude
        claude_idx = parts.index('.claude')
        # Project root is the parent of .claude
        project_root = Path(*parts[:claude_idx])
        return project_root

    # Otherwise, cwd is the project root
    return cwd


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
def run_pipeline(
    ctx: typer.Context,
    story_id: Optional[str] = typer.Argument(
        None,
        help="Story ID to develop (runs next story from backlog if not provided)"
    ),
):
    """
    Layer 1: Story development with quality checks.

    Usage:
        /orchestrate-dev                  # Run next story from backlog
        /orchestrate-dev 1-2-user-auth    # Run specific story
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    global _runner_instance

    # Register signal handlers for cleanup
    signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_and_exit)  # Termination

    project_root = get_project_root()
    runner = PipelineRunner(project_root)
    _runner_instance = runner  # Store for cleanup

    console.print(f"\n[bold]Orchestrate Dev - Layer 1[/bold]")
    console.print(f"Project: {project_root.name}")
    if story_id:
        console.print(f"Story: {story_id}")
    else:
        console.print("Story: (next from backlog)")
    console.print("=" * 50)

    try:
        result = runner.run(story_id=story_id)

        # Explicit cleanup before exit
        cleanup_and_exit()

        if result.success:
            console.print(f"\n[bold green]Pipeline completed successfully![/bold green]")
            raise typer.Exit(0)
        else:
            console.print(f"\n[bold red]Pipeline failed: {result.error}[/bold red]")
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
