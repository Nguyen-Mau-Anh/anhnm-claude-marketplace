"""CLI interface for orchestrate-dev Layer 1."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from .runner import PipelineRunner

app = typer.Typer(
    name="orchestrate-dev",
    help="Layer 1: Story development with quality checks",
    invoke_without_command=True,
)
console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path.cwd()


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

    project_root = get_project_root()
    runner = PipelineRunner(project_root)

    console.print(f"\n[bold]Orchestrate Dev - Layer 1[/bold]")
    console.print(f"Project: {project_root.name}")
    if story_id:
        console.print(f"Story: {story_id}")
    else:
        console.print("Story: (next from backlog)")
    console.print("=" * 50)

    result = runner.run(story_id=story_id)

    if result.success:
        console.print(f"\n[bold green]Pipeline completed successfully![/bold green]")
        raise typer.Exit(0)
    else:
        console.print(f"\n[bold red]Pipeline failed: {result.error}[/bold red]")
        raise typer.Exit(1)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
