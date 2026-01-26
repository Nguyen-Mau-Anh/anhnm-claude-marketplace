"""CLI interface for orchestrate-integrate Layer 2."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from .runner import PipelineRunner

app = typer.Typer(
    name="orchestrate-integrate",
    help="Layer 2: Complete integration pipeline from story to merged PR",
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


@app.callback(invoke_without_command=True)
def run_pipeline(
    ctx: typer.Context,
    story_input: Optional[str] = typer.Argument(
        None,
        help="Story ID, file path, or story name (auto-detect if not provided)"
    ),
):
    """
    Layer 2: Complete integration pipeline.

    Supports multiple input formats:
      - No input: Auto-detect next story from backlog
      - Story ID (e.g., 1-2-user-auth): Use specific story
      - File path (e.g., docs/stories/1-2-user-auth.md): Use file
      - Partial name (e.g., user-auth): Search for story

    Examples:
        /orchestrate-integrate                           # Auto-detect
        /orchestrate-integrate 1-2-user-auth             # Story ID
        /orchestrate-integrate docs/stories/1-2-*.md     # File path
        /orchestrate-integrate user-auth                 # Partial name
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_root = get_project_root()
    runner = PipelineRunner(project_root)

    console.print(f"\n[bold]Orchestrate Integrate - Layer 2[/bold]")
    console.print(f"Project: {project_root.name}")

    if story_input:
        console.print(f"Input: {story_input}")
    else:
        console.print("Input: (auto-detect)")

    console.print("=" * 70)

    # Run pipeline with story input
    result = runner.run(story_input=story_input)

    if result.success:
        console.print(f"\n[bold green]✓ Pipeline complete![/bold green]")
        console.print(f"Story: {result.story_id}")
        console.print(f"File: {result.story_file}")

        if result.pr_url:
            console.print(f"PR: {result.pr_url}")

            if result.pr_status == "merged":
                console.print(f"[green]✅ PR merged to main[/green]")
            elif result.pr_status == "ready_for_manual_merge":
                console.print(f"[yellow]⏳ PR ready for manual review[/yellow]")
            else:
                console.print(f"[yellow]⏳ PR status: {result.pr_status}[/yellow]")

        console.print(f"\n[dim]Lessons saved: {result.lessons_saved}[/dim]")
        console.print(f"[dim]Errors prevented: {result.errors_prevented}[/dim]")
        console.print(f"[dim]Total time: {result.duration_minutes:.1f} minutes[/dim]")

        raise typer.Exit(0)
    else:
        console.print(f"\n[bold red]✗ Pipeline failed: {result.error}[/bold red]")
        if result.failed_stage:
            console.print(f"[dim]Failed at stage: {result.failed_stage}[/dim]")
        raise typer.Exit(1)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
