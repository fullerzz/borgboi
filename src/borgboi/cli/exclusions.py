"""Exclusions management commands for BorgBoi CLI."""

import click

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.rich_utils import console


@click.group()
def exclusions() -> None:
    """Exclusions management commands.

    Manage backup exclusion patterns for repositories.
    """


@exclusions.command("create")
@click.option("--path", "-p", required=True, type=click.Path(exists=True), help="Repository path")
@click.option(
    "--source",
    "-s",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Source file with exclusion patterns",
)
@pass_context
def exclusions_create(ctx: BorgBoiContext, path: str, source: str) -> None:
    """Create an exclusions file for a repository."""
    try:
        repo = ctx.orchestrator.get_repo(path=path)
        excludes_path = ctx.orchestrator.create_exclusions(repo, source)
        console.print(f"Exclusions file created at [bold cyan]{excludes_path}[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@exclusions.command("show")
@click.option("--name", "-n", required=True, type=str, help="Repository name")
@pass_context
def exclusions_show(ctx: BorgBoiContext, name: str) -> None:
    """Show exclusion patterns for a repository."""
    from borgboi import rich_utils

    try:
        repo = ctx.orchestrator.get_repo(name=name)

        # Get excludes file path
        excludes_path = ctx.config.borgboi_dir / f"{repo.name}_{ctx.config.excludes_filename}"
        if not excludes_path.exists():
            console.print(f"[bold yellow]No exclusions file found for repository {name}[/]")
            return

        rich_utils.render_excludes_file(excludes_path.as_posix())
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@exclusions.command("add")
@click.option("--name", "-n", required=True, type=str, help="Repository name")
@click.option("--pattern", "-x", required=True, type=str, help="Exclusion pattern to add")
@pass_context
def exclusions_add(ctx: BorgBoiContext, name: str, pattern: str) -> None:
    """Add an exclusion pattern to a repository."""
    from borgboi import rich_utils

    try:
        repo = ctx.orchestrator.get_repo(name=name)
        ctx.orchestrator.add_exclusion(repo, pattern)

        # Show the updated file with the new pattern highlighted
        excludes_path = ctx.config.borgboi_dir / f"{repo.name}_{ctx.config.excludes_filename}"
        with excludes_path.open("r") as f:
            line_count = sum(1 for _ in f)
        rich_utils.render_excludes_file(excludes_path.as_posix(), lines_to_highlight={line_count})
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@exclusions.command("remove")
@click.option("--name", "-n", required=True, type=str, help="Repository name")
@click.option("--line", "-l", required=True, type=int, help="Line number to remove (1-based)")
@pass_context
def exclusions_remove(ctx: BorgBoiContext, name: str, line: int) -> None:
    """Remove an exclusion pattern by line number."""
    from borgboi import rich_utils

    try:
        repo = ctx.orchestrator.get_repo(name=name)
        ctx.orchestrator.remove_exclusion(repo, line)

        # Show the updated file
        excludes_path = ctx.config.borgboi_dir / f"{repo.name}_{ctx.config.excludes_filename}"
        rich_utils.render_excludes_file(excludes_path.as_posix())
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e
