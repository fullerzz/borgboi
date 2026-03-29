"""S3 sync commands for BorgBoi CLI."""

from typing import Annotated

from cyclopts import App, Parameter

from borgboi.cli.main import ContextArg, confirm_action, print_error_and_exit
from borgboi.core.logging import get_logger
from borgboi.rich_utils import console

logger = get_logger(__name__)

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
    logger.info("Running S3 sync command", repo_name=name, repo_path=path, offline=ctx.offline)
    if ctx.offline:
        logger.info("Skipping S3 sync command in offline mode", repo_name=name, repo_path=path)
        console.print("[bold yellow]S3 sync is not available in offline mode[/]")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        ctx.orchestrator.sync_to_s3(repo_info)
        logger.info("S3 sync command completed", repo_name=repo_info.name, repo_path=repo_info.path)
    except Exception as error:
        logger.exception("S3 sync command failed", error=str(error), repo_name=name, repo_path=path)
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
    logger.info(
        "Running S3 restore command", repo_name=name, repo_path=path, dry_run=dry_run, force=force, offline=ctx.offline
    )
    if ctx.offline:
        logger.info("Skipping S3 restore command in offline mode", repo_name=name, repo_path=path)
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

        ctx.orchestrator.restore_from_s3(repo_info, dry_run=dry_run, force=force)
        logger.info(
            "S3 restore command completed",
            repo_name=repo_info.name,
            repo_path=repo_info.path,
            dry_run=dry_run,
            force=force,
        )
    except Exception as error:
        logger.exception(
            "S3 restore command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            dry_run=dry_run,
            force=force,
        )
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
    logger.info("Running S3 delete command", repo_name=name, dry_run=dry_run, offline=ctx.offline)
    if ctx.offline:
        logger.info("Skipping S3 delete command in offline mode", repo_name=name)
        console.print("[bold yellow]S3 delete is not available in offline mode[/]")
        return

    if not confirm_action("Are you sure you want to delete this repository from S3?"):
        logger.info("S3 delete command aborted by user", repo_name=name)
        console.print("Aborted.")
        return

    try:
        ctx.orchestrator.delete_from_s3(name, dry_run=dry_run)
        logger.info("S3 delete command completed", repo_name=name, dry_run=dry_run)
        if dry_run:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
        else:
            console.print("[bold green]Repository deleted from S3 successfully[/]")
    except Exception as error:
        logger.exception("S3 delete command failed", error=str(error), repo_name=name, dry_run=dry_run)
        print_error_and_exit(str(error), error=error)


@s3.command(name="stats")
def s3_stats(*, ctx: ContextArg) -> None:
    """Show S3 bucket storage metrics and class composition."""
    logger.info("Running S3 stats command", offline=ctx.offline)
    if ctx.offline:
        logger.info("Skipping S3 stats command in offline mode")
        console.print("[bold yellow]S3 stats are not available in offline mode[/]")
        return

    try:
        from borgboi import rich_utils
        from borgboi.clients import s3 as s3_client

        stats = s3_client.get_bucket_stats(cfg=ctx.config)
        logger.info(
            "S3 stats command completed",
            bucket_name=stats.bucket_name,
            total_size_bytes=stats.total_size_bytes,
            total_object_count=stats.total_object_count,
        )
        rich_utils.output_s3_bucket_stats(stats)
    except Exception as error:
        logger.exception("S3 stats command failed", error=str(error))
        print_error_and_exit(str(error), error=error)
