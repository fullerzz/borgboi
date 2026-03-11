"""Exclusions management commands for BorgBoi CLI."""

from typing import Annotated

from cyclopts import App, Parameter

from borgboi.cli.main import ContextArg, print_error_and_exit
from borgboi.rich_utils import console

exclusions = App(
    name="exclusions",
    help="Exclusions management commands.\n\nCreate, inspect, add, and remove exclusion patterns.",
)


@exclusions.command(name="create")
def exclusions_create(
    *,
    path: Annotated[str, Parameter(name=["--path", "-p"], help="Repository path")],
    source: Annotated[str, Parameter(name=["--source", "-s"], help="Source file with exclusion patterns")],
    ctx: ContextArg,
) -> None:
    """Create an exclusions file for a repository."""
    try:
        repo_info = ctx.orchestrator.get_repo(path=path)
        excludes_path = ctx.orchestrator.create_exclusions(repo_info, source)
        console.print(f"Exclusions file created at [bold cyan]{excludes_path}[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@exclusions.command(name="show")
def exclusions_show(
    *,
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    ctx: ContextArg,
) -> None:
    """Show exclusion patterns for a repository."""
    from borgboi import rich_utils

    try:
        repo_info = ctx.orchestrator.get_repo(name=name)
        candidates = [
            ctx.config.borgboi_dir / f"{repo_info.name}_{ctx.config.excludes_filename}",
            ctx.config.borgboi_dir / ctx.config.excludes_filename,
        ]

        for candidate in candidates:
            try:
                rich_utils.render_excludes_file(candidate.as_posix())
                return
            except FileNotFoundError:
                continue

        console.print(f"[bold yellow]No exclusions file found for repository {name}[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@exclusions.command(name="add")
def exclusions_add(
    *,
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    pattern: Annotated[str, Parameter(name=["--pattern", "-x"], help="Exclusion pattern to add")],
    ctx: ContextArg,
) -> None:
    """Add an exclusion pattern to a repository."""
    from borgboi import rich_utils

    try:
        repo_info = ctx.orchestrator.get_repo(name=name)
        ctx.orchestrator.add_exclusion(repo_info, pattern)

        excludes_path = ctx.config.borgboi_dir / f"{repo_info.name}_{ctx.config.excludes_filename}"
        with excludes_path.open("r") as file_obj:
            line_count = sum(1 for _ in file_obj)
        rich_utils.render_excludes_file(excludes_path.as_posix(), lines_to_highlight={line_count})
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@exclusions.command(name="remove")
def exclusions_remove(
    *,
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    line: Annotated[int, Parameter(name=["--line", "-l"], help="Line number to remove (1-based)")],
    ctx: ContextArg,
) -> None:
    """Remove an exclusion pattern by line number."""
    from borgboi import rich_utils

    try:
        repo_info = ctx.orchestrator.get_repo(name=name)
        ctx.orchestrator.remove_exclusion(repo_info, line)

        excludes_path = ctx.config.borgboi_dir / f"{repo_info.name}_{ctx.config.excludes_filename}"
        rich_utils.render_excludes_file(excludes_path.as_posix())
    except Exception as error:
        print_error_and_exit(str(error), error=error)
