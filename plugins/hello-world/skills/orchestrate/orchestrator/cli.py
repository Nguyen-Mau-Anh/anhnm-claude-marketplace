"""CLI interface for the AI Development Orchestrator."""

import typer
import subprocess
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn

from .storage.sprint_storage import SprintStorage
from .adapters.claude_spawner import ClaudeSpawner, TaskType
from .models.story import StoryStatus

app = typer.Typer(
    name="orchestrator",
    help="AI Development Orchestration System - BMAD Parallelizer",
)
console = Console()

# Global state for live dashboard
_current_story: Optional[str] = None
_current_phase: Optional[str] = None
_story_results: dict = {}  # story_id -> {phase: status}


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path.cwd()


def _build_dashboard(storage: SprintStorage, actionable: list[str]) -> Table:
    """Build the live dashboard table."""
    global _current_story, _current_phase, _story_results

    table = Table(title=f"🚀 Orchestrator Dashboard - {datetime.now().strftime('%H:%M:%S')}")
    table.add_column("Story", style="cyan", width=25)
    table.add_column("Dev", justify="center", width=12)
    table.add_column("Test", justify="center", width=12)
    table.add_column("Review", justify="center", width=12)
    table.add_column("Status", justify="center", width=15)

    for story_id in actionable:
        results = _story_results.get(story_id, {})

        # Determine phase statuses
        dev_status = results.get("dev", "⏳ pending")
        test_status = results.get("test", "⏳ pending")
        review_status = results.get("review", "⏳ pending")

        # Highlight current story/phase
        if story_id == _current_story:
            if _current_phase == "dev":
                dev_status = "[yellow]⚡ running[/yellow]"
            elif _current_phase == "test":
                test_status = "[yellow]⚡ running[/yellow]"
            elif _current_phase == "review":
                review_status = "[yellow]⚡ running[/yellow]"

        # Overall status
        if results.get("final") == "done":
            overall = "[green]✅ Done[/green]"
        elif results.get("final") == "failed":
            overall = "[red]❌ Failed[/red]"
        elif story_id == _current_story:
            overall = "[yellow]🔄 Processing[/yellow]"
        else:
            overall = "[dim]⏳ Queued[/dim]"

        table.add_row(story_id, dev_status, test_status, review_status, overall)

    return table


def _update_story_result(story_id: str, phase: str, success: bool, duration: float = 0):
    """Update story result for dashboard."""
    global _story_results
    if story_id not in _story_results:
        _story_results[story_id] = {}

    if success:
        _story_results[story_id][phase] = f"[green]✓ {duration:.0f}s[/green]"
    else:
        _story_results[story_id][phase] = "[red]✗ failed[/red]"


@app.command()
def status():
    """Show current orchestration status."""
    project_root = get_project_root()
    storage = SprintStorage(project_root)

    sprint_status = storage.load()

    if not sprint_status:
        console.print("[yellow]No sprint-status.yaml found. Auto-initializing...[/yellow]")
        sprint_status = storage.auto_initialize()

        if not sprint_status:
            console.print("[red]No story files found to initialize from.[/red]")
            console.print("Create story files in docs/stories/ or state/stories/ first.")
            return

        console.print(f"[green]Created sprint-status.yaml with {len(sprint_status.development_status)} items[/green]\n")

    # Display progress
    progress = storage.get_progress()

    console.print(Panel.fit(
        f"[bold]{sprint_status.project}[/bold]\n"
        f"Tracking: {sprint_status.tracking_system}",
        title="Project",
    ))

    # Progress bar
    pct = progress["percent_complete"]
    done = progress["done"]
    total = progress["total"]

    console.print(f"\n[bold]Progress:[/bold] {done}/{total} stories ({pct:.1f}%)")

    # Story status table
    table = Table(title="Story Status")
    table.add_column("Story ID", style="cyan")
    table.add_column("Status", style="green")

    for story_id, status in sprint_status.development_status.items():
        if story_id.startswith("epic-") or story_id.endswith("-retrospective"):
            continue
        table.add_row(story_id, status)

    console.print(table)

    # Actionable stories
    actionable = storage.get_actionable_stories()
    if actionable:
        console.print(f"\n[bold]Ready to work on:[/bold] {', '.join(actionable)}")


@app.command()
def start(
    workers: int = typer.Option(1, "--workers", "-w", help="Number of concurrent workers (1 for prototype)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without executing"),
    new_terminal: bool = typer.Option(False, "--new-terminal", "-t", help="Open in new terminal window"),
    dashboard: bool = typer.Option(True, "--dashboard/--no-dashboard", help="Show live dashboard"),
):
    """
    Start the orchestration process.

    This is the main entry point that kicks off autonomous development.
    """
    global _current_story, _current_phase, _story_results

    # Open in new terminal if requested
    if new_terminal:
        project_root = get_project_root()
        cmd = f"cd {project_root} && python3 -m orchestrator start"
        if dry_run:
            cmd += " --dry-run"

        # macOS: open new Terminal window
        script = f'''
        tell application "Terminal"
            activate
            do script "{cmd}"
        end tell
        '''
        subprocess.run(["osascript", "-e", script])
        console.print("[green]Opened orchestrator in new terminal window[/green]")
        return

    project_root = get_project_root()
    storage = SprintStorage(project_root)
    spawner = ClaudeSpawner(project_root)

    sprint_status = storage.load()

    if not sprint_status:
        console.print("[yellow]No sprint-status.yaml found. Auto-initializing...[/yellow]")
        sprint_status = storage.auto_initialize()

        if not sprint_status:
            console.print("[red]No story files found to initialize from.[/red]")
            console.print("Create story files in docs/stories/ or state/stories/ first.")
            raise typer.Exit(1)

        console.print(f"[green]Created sprint-status.yaml with {len(sprint_status.development_status)} items[/green]\n")

    # Get actionable stories
    actionable = storage.get_actionable_stories()

    if not actionable:
        console.print("[green]No stories ready for development.[/green]")
        console.print("All stories are either done or blocked.")
        return

    console.print(Panel.fit(
        f"[bold]Starting Orchestration[/bold]\n\n"
        f"Project: {sprint_status.project}\n"
        f"Workers: {workers}\n"
        f"Stories ready: {len(actionable)}",
        title="🚀 Orchestrator",
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN - Not executing[/yellow]")
        for story_id in actionable:
            console.print(f"  Would process: {story_id}")
        return

    # Reset dashboard state
    _story_results = {}
    _current_story = None
    _current_phase = None

    # Run with live dashboard
    if dashboard:
        with Live(_build_dashboard(storage, actionable), refresh_per_second=1, console=console) as live:
            for story_id in actionable:
                _process_story_with_dashboard(story_id, storage, spawner, live, actionable)
    else:
        # Simple mode without dashboard
        console.print("\n[bold]Starting execution loop...[/bold]\n")
        for story_id in actionable:
            _process_story(story_id, storage, spawner)


def _process_story_with_dashboard(
    story_id: str,
    storage: SprintStorage,
    spawner: ClaudeSpawner,
    live: Live,
    actionable: list[str]
):
    """Process a story with live dashboard updates."""
    global _current_story, _current_phase, _story_results

    _current_story = story_id

    # Phase 1: Develop
    _current_phase = "dev"
    live.update(_build_dashboard(storage, actionable))
    storage.update_story_status(story_id, StoryStatus.IN_PROGRESS)

    result = spawner.spawn_sync(
        TaskType.DEVELOP_STORY,
        story_id=story_id,
        story_path=f"docs/stories/{story_id}.md",
    )
    _update_story_result(story_id, "dev", result.success, result.duration_seconds)
    live.update(_build_dashboard(storage, actionable))

    if not result.success:
        storage.update_story_status(story_id, StoryStatus.NEEDS_FIX)
        _story_results[story_id]["final"] = "failed"
        live.update(_build_dashboard(storage, actionable))
        return

    # Phase 2: Test
    _current_phase = "test"
    live.update(_build_dashboard(storage, actionable))
    storage.update_story_status(story_id, StoryStatus.TESTING)

    result = spawner.spawn_sync(
        TaskType.TEST_STORY,
        story_id=story_id,
    )
    _update_story_result(story_id, "test", result.success, result.duration_seconds)
    live.update(_build_dashboard(storage, actionable))

    if not result.success:
        storage.update_story_status(story_id, StoryStatus.NEEDS_FIX)
        _story_results[story_id]["final"] = "failed"
        live.update(_build_dashboard(storage, actionable))
        return

    # Phase 3: Code Review
    _current_phase = "review"
    live.update(_build_dashboard(storage, actionable))

    result = spawner.spawn_sync(
        TaskType.REVIEW_CODE,
        story_id=story_id,
    )
    _update_story_result(story_id, "review", result.success, result.duration_seconds)

    # Mark complete
    storage.update_story_status(story_id, StoryStatus.REVIEW)
    _story_results[story_id]["final"] = "done"
    _current_story = None
    _current_phase = None
    live.update(_build_dashboard(storage, actionable))


def _process_story(story_id: str, storage: SprintStorage, spawner: ClaudeSpawner):
    """Process a single story through the development pipeline (no dashboard)."""

    console.print(f"\n[bold cyan]Processing: {story_id}[/bold cyan]")

    # Phase 1: Develop
    console.print("  [dim]Phase 1: Development[/dim]")
    storage.update_story_status(story_id, StoryStatus.IN_PROGRESS)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Invoking dev agent...", total=None)

        result = spawner.spawn_sync(
            TaskType.DEVELOP_STORY,
            story_id=story_id,
            story_path=f"docs/stories/{story_id}.md",
        )

        progress.remove_task(task)

    if not result.success:
        console.print(f"  [red]Development failed: {result.error}[/red]")
        storage.update_story_status(story_id, StoryStatus.NEEDS_FIX)
        return

    console.print(f"  [green]Development complete ({result.duration_seconds:.1f}s)[/green]")

    # Phase 2: Test
    console.print("  [dim]Phase 2: Testing[/dim]")
    storage.update_story_status(story_id, StoryStatus.TESTING)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Invoking TEA agent...", total=None)

        result = spawner.spawn_sync(
            TaskType.TEST_STORY,
            story_id=story_id,
        )

        progress.remove_task(task)

    if not result.success:
        console.print(f"  [red]Testing failed: {result.error}[/red]")
        storage.update_story_status(story_id, StoryStatus.NEEDS_FIX)
        return

    console.print(f"  [green]Testing complete ({result.duration_seconds:.1f}s)[/green]")

    # Phase 3: Code Review
    console.print("  [dim]Phase 3: Code Review[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running code review...", total=None)

        result = spawner.spawn_sync(
            TaskType.REVIEW_CODE,
            story_id=story_id,
        )

        progress.remove_task(task)

    if not result.success:
        console.print(f"  [yellow]Review had issues: {result.error}[/yellow]")
        # Don't fail on review - just note it

    console.print(f"  [green]Review complete ({result.duration_seconds:.1f}s)[/green]")

    # Mark ready for user review
    storage.update_story_status(story_id, StoryStatus.REVIEW)
    console.print(f"  [bold green]✓ {story_id} ready for review[/bold green]")


@app.command()
def review(
    story_id: Optional[str] = typer.Argument(None, help="Story ID to review"),
):
    """Review completed stories."""
    project_root = get_project_root()
    storage = SprintStorage(project_root)

    sprint_status = storage.load()
    if not sprint_status:
        sprint_status = storage.auto_initialize()
        if not sprint_status:
            console.print("[red]No sprint status found and no stories to initialize from.[/red]")
            raise typer.Exit(1)

    # Get stories in review state
    review_stories = sprint_status.get_stories_by_status(StoryStatus.REVIEW)

    if not review_stories:
        console.print("[green]No stories pending review.[/green]")
        return

    if story_id:
        if story_id not in review_stories:
            console.print(f"[yellow]{story_id} is not in review state.[/yellow]")
            return
        _show_review(story_id)
    else:
        console.print(f"\n[bold]Stories pending review ({len(review_stories)}):[/bold]")
        for sid in review_stories:
            console.print(f"  • {sid}")
        console.print("\nUse: orchestrator review <story-id>")


def _show_review(story_id: str):
    """Show review details for a story."""
    console.print(Panel.fit(
        f"[bold]Review: {story_id}[/bold]\n\n"
        "Use these commands:\n"
        f"  orchestrator approve {story_id}\n"
        f"  orchestrator bug {story_id} \"description\"",
        title="📋 Story Review",
    ))


@app.command()
def approve(
    story_ids: list[str] = typer.Argument(..., help="Story IDs to approve"),
):
    """Approve one or more stories."""
    project_root = get_project_root()
    storage = SprintStorage(project_root)

    for story_id in story_ids:
        storage.update_story_status(story_id, StoryStatus.DONE)
        console.print(f"[green]✓ Approved {story_id}[/green]")


@app.command()
def bug(
    story_id: str = typer.Argument(..., help="Story ID with the bug"),
    description: str = typer.Argument(..., help="Bug description"),
    critical: bool = typer.Option(False, "--critical", "-c", help="Mark as critical"),
):
    """Report a bug on a story."""
    project_root = get_project_root()
    storage = SprintStorage(project_root)
    spawner = ClaudeSpawner(project_root)

    storage.update_story_status(story_id, StoryStatus.NEEDS_FIX)

    console.print(f"[yellow]Bug reported on {story_id}[/yellow]")
    console.print(f"  Description: {description}")

    if critical:
        console.print("  [red]CRITICAL - blocking other work[/red]")

    # Optionally trigger fix immediately
    fix_now = typer.confirm("Attempt to fix now?")
    if fix_now:
        console.print("\n[dim]Invoking dev agent to fix...[/dim]")

        result = spawner.spawn_sync(
            TaskType.FIX_BUG,
            story_id=story_id,
            bug_description=description,
        )

        if result.success:
            console.print(f"[green]Fix applied ({result.duration_seconds:.1f}s)[/green]")
            storage.update_story_status(story_id, StoryStatus.REVIEW)
        else:
            console.print(f"[red]Fix failed: {result.error}[/red]")


@app.command()
def init(
    docs_path: str = typer.Argument("./docs", help="Path to planning documents"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-initialization even if sprint-status.yaml exists"),
):
    """Initialize orchestration from planning documents."""
    project_root = get_project_root()
    storage = SprintStorage(project_root)

    # Check if already initialized
    existing = storage.find_status_file()
    if existing and not force:
        console.print(f"[yellow]Sprint status already exists at {existing}[/yellow]")
        console.print("Use --force to re-initialize.")
        return

    console.print(f"[dim]Scanning for stories in {docs_path}...[/dim]")

    # Try auto-initialization
    sprint_status = storage.auto_initialize()

    if sprint_status:
        console.print(f"\n[green]✓ Initialized sprint-status.yaml[/green]")
        console.print(f"  Project: {sprint_status.project}")
        console.print(f"  Stories found: {len(sprint_status.development_status)}")

        # Show what was discovered
        table = Table(title="Discovered Stories")
        table.add_column("ID", style="cyan")
        table.add_column("Status", style="green")

        for story_id, status in sorted(sprint_status.development_status.items()):
            table.add_row(story_id, status)

        console.print(table)
        console.print("\n[bold]Run 'orchestrator start' to begin development[/bold]")
    else:
        console.print("[yellow]No story files found to initialize from.[/yellow]")
        console.print("\nTo create stories, either:")
        console.print("  1. Create markdown files in docs/stories/ or state/stories/")
        console.print("  2. Run BMAD workflow: /bmad:bmm:workflows:create-epics-stories")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
