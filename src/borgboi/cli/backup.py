"""Backup operation commands for BorgBoi CLI."""

import click
from rich.table import Table

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.clients.borg import ArchiveInfo
from borgboi.lib import utils
from borgboi.rich_utils import console


def _build_archive_stats_tables(repo_path: str, archive_info: ArchiveInfo) -> tuple[Table, Table]:
    """Build Rich tables for Borg archive statistics."""
    archive = archive_info.archive
    archive_stats_raw = archive.get("stats", {})
    archive_stats = archive_stats_raw if isinstance(archive_stats_raw, dict) else {}

    this_original_size = utils.format_size_bytes(utils.coerce_int(archive_stats.get("original_size")))
    this_compressed_size = utils.format_size_bytes(utils.coerce_int(archive_stats.get("compressed_size")))
    this_deduplicated_size = utils.format_size_bytes(utils.coerce_int(archive_stats.get("deduplicated_size")))

    cache_stats = archive_info.cache.stats
    all_original_size = utils.format_size_bytes(cache_stats.total_size)
    all_compressed_size = utils.format_size_bytes(cache_stats.total_csize)
    all_deduplicated_size = utils.format_size_bytes(cache_stats.unique_csize)

    number_of_files = utils.coerce_int(archive_stats.get("nfiles"))
    summary_table = Table(title="Archive Summary", show_header=False)
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value")
    summary_table.add_row("Repository", repo_path)
    summary_table.add_row("Archive name", str(archive.get("name", "Unknown")))
    summary_table.add_row("Archive fingerprint", str(archive.get("id", "Unknown")))
    summary_table.add_row("Time (start)", utils.format_iso_timestamp(archive.get("start")))
    summary_table.add_row("Time (end)", utils.format_iso_timestamp(archive.get("end")))
    summary_table.add_row("Duration", utils.format_duration_seconds(archive.get("duration")))
    summary_table.add_row("Number of files", str(number_of_files) if number_of_files is not None else "Unknown")

    size_table = Table(title="Size Statistics")
    size_table.add_column("Scope", style="bold cyan")
    size_table.add_column("Original size", justify="right")
    size_table.add_column("Compressed size", justify="right")
    size_table.add_column("Deduplicated size", justify="right")
    size_table.add_row("This archive", this_original_size, this_compressed_size, this_deduplicated_size)
    size_table.add_row("All archives", all_original_size, all_compressed_size, all_deduplicated_size)

    return summary_table, size_table


def _render_archive_stats_table(repo_path: str, archive_info: ArchiveInfo) -> None:
    """Render Borg archive statistics in Rich tables."""
    summary_table, size_table = _build_archive_stats_tables(repo_path, archive_info)

    console.print(summary_table)
    console.print(size_table)


@click.group()
def backup() -> None:
    """Backup operation commands.

    Create, list, restore, and delete backups.
    """


@backup.command("run")
@click.option("--path", "-p", type=click.Path(exists=True), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@pass_context
def backup_run(ctx: BorgBoiContext, path: str | None, name: str | None, passphrase: str | None) -> None:
    """Create a new backup archive."""
    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)
        archive_name = ctx.orchestrator.backup(repo, passphrase=passphrase)

        try:
            resolved_passphrase = ctx.orchestrator.resolve_passphrase(repo, passphrase)
            archive_info = ctx.orchestrator.borg.archive_info(
                repo.path,
                archive_name,
                passphrase=resolved_passphrase,
            )
            _render_archive_stats_table(repo.path, archive_info)
        except Exception as stats_error:
            console.print(f"[bold yellow]Warning:[/] Backup succeeded, but stats could not be rendered: {stats_error}")

        console.print("[bold green]Backup completed successfully[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@backup.command("daily")
@click.option("--path", "-p", required=True, type=click.Path(exists=True), help="Repository path")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@click.option("--no-s3-sync", is_flag=True, help="Skip S3 sync after backup")
@pass_context
def backup_daily(ctx: BorgBoiContext, path: str, passphrase: str | None, no_s3_sync: bool) -> None:
    """Perform daily backup with prune and compact."""
    try:
        repo = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.daily_backup(repo, passphrase=passphrase, sync_to_s3=not no_s3_sync)
        console.print("[bold green]Daily backup completed successfully[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@backup.command("list")
@click.option("--path", "-p", type=click.Path(exists=False), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@pass_context
def backup_list(ctx: BorgBoiContext, path: str | None, name: str | None, passphrase: str | None) -> None:
    """List archives in a repository."""
    from borgboi.lib.colors import COLOR_HEX

    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)
        archives = ctx.orchestrator.list_archives(repo, passphrase=passphrase)
        archives.sort(key=lambda x: x.name, reverse=True)

        console.rule(f"[bold]Archives for {repo.name}[/]")
        for archive in archives:
            console.print(
                f"  [bold {COLOR_HEX.sky}]{archive.name}[/]  "
                f"[bold {COLOR_HEX.green}]Age: {utils.calculate_archive_age(archive.name)}[/]  "
                f"[{COLOR_HEX.mauve}]ID: {archive.id}[/]"
            )
        console.rule()
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@backup.command("restore")
@click.option("--path", "-p", required=True, type=click.Path(exists=True), help="Repository path")
@click.option("--archive", "-a", required=True, help="Archive name to restore")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@click.confirmation_option(prompt="Extract archive contents to current directory?")
@pass_context
def backup_restore(ctx: BorgBoiContext, path: str, archive: str, passphrase: str | None) -> None:
    """Restore an archive to the current directory."""
    try:
        repo = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.restore_archive(repo, archive, passphrase=passphrase)
        console.print("[bold green]Archive restored successfully[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@backup.command("delete")
@click.option("--path", "-p", required=True, type=click.Path(exists=True), help="Repository path")
@click.option("--archive", "-a", required=True, help="Archive name to delete")
@click.option("--dry-run", is_flag=True, help="Simulate deletion without making changes")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@pass_context
def backup_delete(ctx: BorgBoiContext, path: str, archive: str, dry_run: bool, passphrase: str | None) -> None:
    """Delete an archive from a repository."""
    if not dry_run and not click.confirm(f"Are you sure you want to delete archive '{archive}'?"):
        console.print("Aborted.")
        return

    try:
        repo = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.delete_archive(repo, archive, dry_run=dry_run, passphrase=passphrase)
        if not dry_run:
            console.print("[bold green]Archive deleted successfully[/]")
        else:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e


@backup.command("contents")
@click.option("--path", "-p", type=click.Path(exists=False), help="Repository path")
@click.option("--name", "-n", type=str, help="Repository name")
@click.option("--archive", "-a", required=True, help="Archive name")
@click.option("--output", "-o", type=str, default="stdout", help="Output file path or 'stdout'")
@click.option("--passphrase", type=str, default=None, help="Passphrase override")
@pass_context
def backup_contents(
    ctx: BorgBoiContext, path: str | None, name: str | None, archive: str, output: str, passphrase: str | None
) -> None:
    """List contents of an archive."""
    from pathlib import Path

    from borgboi.lib.colors import COLOR_HEX

    try:
        repo = ctx.orchestrator.get_repo(name=name, path=path)

        from borgboi.clients import borg

        contents = borg.list_archive_contents(repo.path, archive, passphrase=passphrase)

        if output == "stdout":
            for item in contents:
                console.print(f"  [{COLOR_HEX.sky}]{utils.shorten_archive_path(item.path)}[/]")
            console.rule()
        else:
            output_path = Path(output)
            with output_path.open("w") as f:
                for item in contents:
                    f.write(item.path + "\n")
            console.print(f"Archive contents written to [bold cyan]{output_path}[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e
