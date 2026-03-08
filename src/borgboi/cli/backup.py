"""Backup operation commands for BorgBoi CLI."""

from typing import Annotated

from cyclopts import App, Parameter
from rich.table import Table

from borgboi.cli.main import ContextArg, confirm_action, print_error_and_exit
from borgboi.clients.borg import ArchiveInfo
from borgboi.core.models import BackupOptions
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


backup = App(
    name="backup",
    help="Backup operation commands.\n\nCreate, inspect, restore, and delete Borg archives.",
)


@backup.command(name="run")
def backup_run(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    no_json: Annotated[
        bool,
        Parameter(name="--no-json", negative="", help="Disable JSON logging; stream Borg's native output"),
    ] = False,
    ctx: ContextArg,
) -> None:
    """Create a new backup archive."""
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)

        options: BackupOptions | None = None
        if no_json:
            options = BackupOptions(json_output=False, compression=ctx.config.borg.compression)

        archive_name = ctx.orchestrator.backup(repo_info, passphrase=passphrase, options=options)

        if not no_json:
            try:
                resolved_passphrase = ctx.orchestrator.resolve_passphrase(repo_info, passphrase)
                archive_info = ctx.orchestrator.borg.archive_info(
                    repo_info.path,
                    archive_name,
                    passphrase=resolved_passphrase,
                )
                _render_archive_stats_table(repo_info.path, archive_info)
            except Exception as stats_error:
                console.print(
                    f"[bold yellow]Warning:[/] Backup succeeded, but stats could not be rendered: {stats_error}"
                )

        console.print("[bold green]Backup completed successfully[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@backup.command(name="daily")
def backup_daily(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    no_s3_sync: Annotated[bool, Parameter(name="--no-s3-sync", negative="", help="Skip S3 sync after backup")] = False,
    ctx: ContextArg,
) -> None:
    """Perform daily backup with prune and compact."""
    if not name and not path:
        print_error_and_exit("Provide either --name or --path to select a repository.")
    if name and path:
        print_error_and_exit("--name and --path are mutually exclusive; provide only one.")

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        ctx.orchestrator.daily_backup(repo_info, passphrase=passphrase, sync_to_s3=not no_s3_sync)
        console.print("[bold green]Daily backup completed successfully[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@backup.command(name="list")
def backup_list(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """List archives in a repository."""
    from borgboi.lib.colors import COLOR_HEX

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        archives = ctx.orchestrator.list_archives(repo_info, passphrase=passphrase)
        archives.sort(key=lambda archive: archive.name, reverse=True)

        console.rule(f"[bold]Archives for {repo_info.name}[/]")
        for archive in archives:
            console.print(
                f"  [bold {COLOR_HEX.sky}]{archive.name}[/]  "
                f"[bold {COLOR_HEX.green}]Age: {utils.calculate_archive_age(archive.name)}[/]  "
                f"[{COLOR_HEX.mauve}]ID: {archive.id}[/]"
            )
        console.rule()
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@backup.command(name="restore")
def backup_restore(
    *,
    path: Annotated[str, Parameter(name=["--path", "-p"], help="Repository path")],
    archive: Annotated[str, Parameter(name=["--archive", "-a"], help="Archive name to restore")],
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """Restore an archive to the current directory."""
    if not confirm_action("Extract archive contents to current directory?"):
        console.print("Aborted.")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.restore_archive(repo_info, archive, passphrase=passphrase)
        console.print("[bold green]Archive restored successfully[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@backup.command(name="delete")
def backup_delete(
    *,
    path: Annotated[str, Parameter(name=["--path", "-p"], help="Repository path")],
    archive: Annotated[str, Parameter(name=["--archive", "-a"], help="Archive name to delete")],
    dry_run: Annotated[
        bool, Parameter(name="--dry-run", negative="", help="Simulate deletion without making changes")
    ] = False,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """Delete an archive from a repository."""
    if not dry_run and not confirm_action(f"Are you sure you want to delete archive '{archive}'?"):
        console.print("Aborted.")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.delete_archive(repo_info, archive, dry_run=dry_run, passphrase=passphrase)
        if dry_run:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
        else:
            console.print("[bold green]Archive deleted successfully[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)


@backup.command(name="contents")
def backup_contents(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    archive: Annotated[str, Parameter(name=["--archive", "-a"], help="Archive name")],
    output: Annotated[str, Parameter(name=["--output", "-o"], help="Output file path or 'stdout'")] = "stdout",
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """List contents of an archive."""
    from pathlib import Path

    from borgboi.clients import borg
    from borgboi.lib.colors import COLOR_HEX

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        contents = borg.list_archive_contents(repo_info.path, archive, passphrase=passphrase)

        if output == "stdout":
            for item in contents:
                console.print(f"  [{COLOR_HEX.sky}]{utils.shorten_archive_path(item.path)}[/]")
            console.rule()
            return

        output_path = Path(output)
        with output_path.open("w") as file_obj:
            for item in contents:
                file_obj.write(item.path + "\n")
        console.print(f"Archive contents written to [bold cyan]{output_path}[/]")
    except Exception as error:
        print_error_and_exit(str(error), error=error)
