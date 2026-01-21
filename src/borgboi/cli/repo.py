"""Repository management commands for BorgBoi CLI."""

import click

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.rich_utils import console


@click.group()
def repo() -> None:
    """Repository management commands.

    Create, list, view, and delete Borg repositories.
    """


@repo.command("create")
@click.option("--path", "-p", required=True, type=click.Path(exists=False), help="Path to create repository")
@click.option("--backup-target", "-b", required=True, type=click.Path(exists=True), help="Directory to back up")
@click.option("--name", "-n", required=True, help="Repository name")
@click.option("--passphrase", type=str, default=None, help="Passphrase (auto-generated if not provided)")
@pass_context
def repo_create(ctx: BorgBoiContext, path: str, backup_target: str, name: str, passphrase: str | None) -> None:
    """Create a new Borg repository."""
    try:
        repo = ctx.orchestrator.create_repo(path=path, backup_target=backup_target, name=name, passphrase=passphrase)
        console.print(f"Created new Borg repo at [bold cyan]{repo.path}[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@repo.command("list")
@pass_context
def repo_list(ctx: BorgBoiContext) -> None:
    """List all BorgBoi repositories."""
    from borgboi import rich_utils

    try:
        repos = ctx.orchestrator.list_repos()
        rich_utils.output_repos_table(repos)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@repo.command("info")
@click.option("--path", "-p", type=click.Path(exists=False), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@click.option("--raw", is_flag=True, help="Show raw Borg output instead of formatted")
@pass_context
def repo_info(ctx: BorgBoiContext, path: str | None, name: str | None, passphrase: str | None, raw: bool) -> None:
    """Show repository information."""
    from borgboi import rich_utils

    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)
        repo_info_data = ctx.orchestrator.get_repo_info(repo, passphrase=passphrase)

        if raw:
            console.print(repo_info_data)
        else:
            if repo.metadata:
                rich_utils.output_repo_info(
                    name=repo.name,
                    total_size_gb=repo.metadata.cache.total_size_gb,
                    total_csize_gb=repo.metadata.cache.total_csize_gb,
                    unique_csize_gb=repo.metadata.cache.unique_csize_gb,
                    encryption_mode=repo.metadata.encryption.mode,
                    repo_id=repo.metadata.repository.id,
                    repo_location=repo.metadata.repository.location,
                    last_modified=repo.metadata.repository.last_modified,
                )
            else:
                console.print(f"Repository: [bold cyan]{repo.name}[/]")
                console.print(f"Path: {repo.path}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@repo.command("delete")
@click.option("--path", "-p", type=click.Path(exists=False), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--dry-run", is_flag=True, help="Simulate deletion without making changes")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@click.option("--delete-from-s3", is_flag=True, help="Also delete from S3")
@pass_context
def repo_delete(
    ctx: BorgBoiContext,
    path: str | None,
    name: str | None,
    dry_run: bool,
    passphrase: str | None,
    delete_from_s3: bool,
) -> None:
    """Delete a Borg repository."""
    if not dry_run and not click.confirm("Are you sure you want to delete this repository?"):
        console.print("Aborted.")
        return

    try:
        ctx.orchestrator.delete_repo(
            name=name, path=path, dry_run=dry_run, delete_from_s3=delete_from_s3, passphrase=passphrase
        )
        if not dry_run:
            console.print("[bold green]Repository deleted successfully[/]")
        else:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e
