"""S3 sync commands for BorgBoi CLI."""

from typing import Annotated

from cyclopts import App, Parameter

from borgboi.cli.main import ContextArg, confirm_action, print_error_and_exit
from borgboi.rich_utils import console

s3 = App(
    name="s3",
    help="S3 synchronization commands.\n\nSync repositories to AWS S3 and inspect bucket stats.",
)


@s3.command(name="sync")
def s3_sync(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    ctx: ContextArg,
) -> None:
    """Sync a repository to S3."""
    if ctx.offline:
        console.print("[bold yellow]S3 sync is not available in offline mode[/]")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)

        from borgboi import rich_utils
        from borgboi.clients import s3 as s3_client
        from borgboi.lib.colors import COLOR_HEX

        rich_utils.render_cmd_output_lines(
            "Syncing repo with S3 bucket",
            "S3 sync completed successfully",
            s3_client.sync_with_s3(repo_info.path, repo_info.name, cfg=ctx.config),
            spinner="arrow",
            ruler_color=COLOR_HEX.green,
        )
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@s3.command(name="restore")
def s3_restore(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    dry_run: Annotated[
        bool,
        Parameter(name="--dry-run", negative="", help="Simulate restoration without making changes"),
    ] = False,
    force: Annotated[
        bool,
        Parameter(name="--force", negative="", help="Force restore even if repository exists locally"),
    ] = False,
    ctx: ContextArg,
) -> None:
    """Restore a repository from S3."""
    if ctx.offline:
        console.print("[bold yellow]S3 restore is not available in offline mode[/]")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)

        if repo_info.metadata and repo_info.metadata.cache:
            console.print(
                f"Repository found: [bold cyan]{repo_info.path} - Total size: {repo_info.metadata.cache.total_size_gb} GB[/]"
            )
        else:
            console.print(f"Repository found: [bold cyan]{repo_info.path}[/]")

        from borgboi import orchestrator as old_orchestrator

        old_orchestrator.restore_repo(repo_info, dry_run, force, ctx.offline)
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@s3.command(name="delete")
def s3_delete(
    *,
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    dry_run: Annotated[
        bool, Parameter(name="--dry-run", negative="", help="Simulate deletion without making changes")
    ] = False,
    ctx: ContextArg,
) -> None:
    """Delete a repository from S3."""
    _ = name, dry_run

    if ctx.offline:
        console.print("[bold yellow]S3 delete is not available in offline mode[/]")
        return

    if not confirm_action("Are you sure you want to delete this repository from S3?"):
        console.print("Aborted.")
        return

    console.print("[bold yellow]S3 delete not yet implemented in new CLI[/]")


@s3.command(name="stats")
def s3_stats(*, ctx: ContextArg) -> None:
    """Show S3 bucket storage metrics and class composition."""
    if ctx.offline:
        console.print("[bold yellow]S3 stats are not available in offline mode[/]")
        return

    try:
        from borgboi import rich_utils
        from borgboi.clients import s3 as s3_client

        stats = s3_client.get_bucket_stats(cfg=ctx.config)
        rich_utils.output_s3_bucket_stats(stats)
    except Exception as error:
        print_error_and_exit(str(error), error=error)
