"""CLI interface for orchestrate-prepare Layer 0."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from .runner import PipelineRunner

app = typer.Typer(
    name="orchestrate-prepare",
    help="Layer 0: Story preparation and validation",
    invoke_without_command=True,
)
console = Console()


def get_project_root() -> Path:
    """
    Get the project root directory.

    Handles the case where we're running from inside .claude/skills/orchestrate-prepare
    when called via subprocess delegation from Layer 1.
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


@app.callback(invoke_without_command=True)
def run_pipeline(
    ctx: typer.Context,
    story_id: Optional[str] = typer.Argument(
        None,
        help="Story ID to prepare (creates next story from backlog if not provided)"
    ),
):
    """
    Layer 0: Story preparation and validation.

    Usage:
        /orchestrate-prepare                  # Create next story from backlog
        /orchestrate-prepare 1-2-user-auth    # Prepare specific story
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_root = get_project_root()
    runner = PipelineRunner(project_root)

    console.print(f"\n[bold]Orchestrate Prepare - Layer 0[/bold]")
    console.print(f"Project: {project_root.name}")
    if story_id:
        console.print(f"Story: {story_id}")
    else:
        console.print("Story: (next from backlog)")
    console.print("=" * 50)

    result = runner.run(story_id=story_id)

    if result.success:
        console.print(f"\n[bold green]✓ Story prepared successfully![/bold green]")
        console.print(f"Story ID: {result.story_id}")
        console.print(f"Story file: {result.story_file}")
        raise typer.Exit(0)
    else:
        console.print(f"\n[bold red]✗ Pipeline failed: {result.error}[/bold red]")
        raise typer.Exit(1)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
