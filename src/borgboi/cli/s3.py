"""S3 sync commands for BorgBoi CLI."""

import click

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.rich_utils import console


@click.group()
def s3() -> None:
    """S3 synchronization commands.

    Sync repositories with AWS S3 for cloud backup.
    """


@s3.command("sync")
@click.option("--path", "-p", type=click.Path(exists=True), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@pass_context
def s3_sync(ctx: BorgBoiContext, path: str | None, name: str | None) -> None:
    """Sync a repository to S3."""
    if ctx.offline:
        console.print("[bold yellow]S3 sync is not available in offline mode[/]")
        return

    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)

        # Use the old s3 module for now
        from borgboi import rich_utils
        from borgboi.clients import s3
        from borgboi.lib.colors import COLOR_HEX

        rich_utils.render_cmd_output_lines(
            "Syncing repo with S3 bucket",
            "S3 sync completed successfully",
            s3.sync_with_s3(repo.path, repo.name, cfg=ctx.config),
            spinner="arrow",
            ruler_color=COLOR_HEX.green,
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@s3.command("restore")
@click.option("--path", "-p", type=click.Path(exists=False), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--dry-run", is_flag=True, help="Simulate restoration without making changes")
@click.option("--force", is_flag=True, help="Force restore even if repository exists locally")
@pass_context
def s3_restore(ctx: BorgBoiContext, path: str | None, name: str | None, dry_run: bool, force: bool) -> None:
    """Restore a repository from S3."""
    if ctx.offline:
        console.print("[bold yellow]S3 restore is not available in offline mode[/]")
        return

    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)

        if repo.metadata and repo.metadata.cache:
            console.print(
                f"Repository found: [bold cyan]{repo.path} - Total size: {repo.metadata.cache.total_size_gb} GB[/]"
            )
        else:
            console.print(f"Repository found: [bold cyan]{repo.path}[/]")

        # Use old orchestrator for now
        from borgboi import orchestrator as old_orch

        old_orch.restore_repo(repo, dry_run, force, ctx.offline)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@s3.command("delete")
@click.option("--name", "-n", required=True, type=str, help="Repository name")
@click.option("--dry-run", is_flag=True, help="Simulate deletion without making changes")
@click.confirmation_option(prompt="Are you sure you want to delete this repository from S3?")
@pass_context
def s3_delete(ctx: BorgBoiContext, name: str, dry_run: bool) -> None:
    """Delete a repository from S3."""
    _ = name, dry_run  # Will be used when S3 client is implemented

    if ctx.offline:
        console.print("[bold yellow]S3 delete is not available in offline mode[/]")
        return

    console.print("[bold yellow]S3 delete not yet implemented in new CLI[/]")
    # Will be implemented when S3 client class is complete
