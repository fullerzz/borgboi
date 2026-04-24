"""Backup operation commands for BorgBoi CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, cast

from cyclopts import App, Parameter

from borgboi.cli.main import ContextArg, confirm_action, print_error_and_exit
from borgboi.core.logging import get_logger
from borgboi.lib.diff import format_diff_change, summarize_diff_changes
from borgboi.rich_utils import console

if TYPE_CHECKING:
    from rich.table import Table

    from borgboi.clients.borg import ArchiveInfo, DiffResult


logger = get_logger(__name__)


def _repo_name(repo: object, fallback: str | None = None) -> str | None:
    return getattr(repo, "name", fallback)


def _repo_path(repo: object, fallback: str | None = None) -> str | None:
    return getattr(repo, "path", fallback)


def _build_archive_stats_tables(repo_path: str, archive_info: ArchiveInfo) -> tuple[Table, Table]:
    """Build Rich tables for Borg archive statistics."""
    from rich.table import Table

    from borgboi.lib import utils

    archive = archive_info.archive
    archive_stats_raw = archive.get("stats", {})
    archive_stats = cast(dict[str, object], archive_stats_raw) if isinstance(archive_stats_raw, dict) else {}

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


def _render_diff_result(result: DiffResult, *, json_output: bool) -> None:
    from borgboi.lib import utils

    if json_output:
        console.out(json.dumps(result.model_dump(mode="json"), indent=2), highlight=False)
        return

    console.rule("[bold]Archive Diff[/]")
    console.print(f"Archive 1: [bold cyan]{result.archive1}[/]")
    console.print(f"Archive 2: [bold cyan]{result.archive2}[/]")

    if not result.entries:
        console.print("No changed paths found.")
        console.rule()
        return

    for entry in result.entries:
        changes = ", ".join(format_diff_change(change) for change in entry.changes)
        console.print(f"[bold]{entry.path}[/]")
        console.print(f"  {changes}")

    summary = summarize_diff_changes(result)
    console.rule("[bold]Summary[/]")
    console.print(f"Changed paths: {len(result.entries)}")
    console.print(f"Added: {summary['added']}")
    console.print(f"Removed: {summary['removed']}")
    console.print(f"Modified: {summary['modified']}")
    console.print(f"Mode changes: {summary['mode']}")
    console.print(f"Bytes added: {utils.format_size_bytes(summary['bytes_added'])}")
    console.print(f"Bytes removed: {utils.format_size_bytes(summary['bytes_removed'])}")
    console.rule()


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
    from borgboi.core.models import BackupOptions

    logger.info("Running backup command", repo_name=name, repo_path=path, no_json=no_json)
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)

        options: BackupOptions | None = None
        if no_json:
            logger.debug(
                "Disabling Borg JSON output for backup command",
                repo_name=_repo_name(repo_info, name),
                repo_path=_repo_path(repo_info, path),
            )
            options = BackupOptions(json_output=False, compression=ctx.config.borg.compression)

        archive_name = ctx.orchestrator.backup(repo_info, passphrase=passphrase, options=options)
        logger.info(
            "Backup command completed",
            repo_name=_repo_name(repo_info, name),
            repo_path=_repo_path(repo_info, path),
            archive_name=archive_name,
        )

        if not no_json:
            try:
                resolved_repo_path = _repo_path(repo_info, path) or ""
                logger.debug(
                    "Rendering archive statistics after backup",
                    repo_name=_repo_name(repo_info, name),
                    repo_path=resolved_repo_path,
                    archive_name=archive_name,
                )
                resolved_passphrase = ctx.orchestrator.resolve_passphrase(repo_info, passphrase)
                archive_info = ctx.orchestrator.borg.archive_info(
                    resolved_repo_path,
                    archive_name,
                    passphrase=resolved_passphrase,
                )
                _render_archive_stats_table(resolved_repo_path, archive_info)
                logger.debug(
                    "Rendered archive statistics after backup",
                    repo_name=_repo_name(repo_info, name),
                    archive_name=archive_name,
                )
            except Exception as stats_error:
                logger.warning(
                    "Failed to render archive statistics after backup",
                    repo_name=_repo_name(repo_info, name),
                    archive_name=archive_name,
                    error=str(stats_error),
                )
                console.print(
                    f"[bold yellow]Warning:[/] Backup succeeded, but stats could not be rendered: {stats_error}"
                )

        console.print("[bold green]Backup completed successfully[/]")
    except Exception as error:
        logger.exception("Backup command failed", error=str(error), repo_name=name, repo_path=path, no_json=no_json)
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
    logger.info("Running daily backup command", repo_name=name, repo_path=path, no_s3_sync=no_s3_sync)
    if not name and not path:
        logger.info("Daily backup command missing repository selector")
        print_error_and_exit("Provide either --name or --path to select a repository.")
    if name and path:
        logger.info("Daily backup command received conflicting repository selectors", repo_name=name, repo_path=path)
        print_error_and_exit("--name and --path are mutually exclusive; provide only one.")

    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        ctx.orchestrator.daily_backup(repo_info, passphrase=passphrase, sync_to_s3=not no_s3_sync)
        logger.info(
            "Daily backup command completed",
            repo_name=_repo_name(repo_info, name),
            repo_path=_repo_path(repo_info, path),
            sync_to_s3=not no_s3_sync,
        )
        console.print("[bold green]Daily backup completed successfully[/]")
    except Exception as error:
        logger.exception(
            "Daily backup command failed", error=str(error), repo_name=name, repo_path=path, no_s3_sync=no_s3_sync
        )
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
    from borgboi.lib import utils
    from borgboi.lib.colors import COLOR_HEX

    logger.info("Running archive list command", repo_name=name, repo_path=path)
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        archives = ctx.orchestrator.list_archives(repo_info, passphrase=passphrase)
        archives.sort(key=lambda archive: archive.name, reverse=True)
        logger.info(
            "Archive list command completed",
            repo_name=_repo_name(repo_info, name),
            repo_path=_repo_path(repo_info, path),
            archive_count=len(archives),
        )

        console.rule(f"[bold]Archives for {_repo_name(repo_info, name)}[/]")
        for archive in archives:
            console.print(
                f"  [bold {COLOR_HEX.sky}]{archive.name}[/]  "
                f"[bold {COLOR_HEX.green}]Age: {utils.calculate_archive_age(archive.name)}[/]  "
                f"[{COLOR_HEX.mauve}]ID: {archive.id}[/]"
            )
        console.rule()
    except Exception as error:
        logger.exception("Archive list command failed", error=str(error), repo_name=name, repo_path=path)
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
    logger.info("Running archive restore command", repo_path=path, archive_name=archive)
    if not confirm_action("Extract archive contents to current directory?"):
        logger.info("Archive restore command aborted by user", repo_path=path, archive_name=archive)
        console.print("Aborted.")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.restore_archive(repo_info, archive, passphrase=passphrase)
        logger.info(
            "Archive restore command completed",
            repo_name=_repo_name(repo_info),
            repo_path=_repo_path(repo_info, path),
            archive_name=archive,
        )
        console.print("[bold green]Archive restored successfully[/]")
    except Exception as error:
        logger.exception("Archive restore command failed", error=str(error), repo_path=path, archive_name=archive)
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
    logger.info("Running archive delete command", repo_path=path, archive_name=archive, dry_run=dry_run)
    if not dry_run and not confirm_action(f"Are you sure you want to delete archive '{archive}'?"):
        logger.info("Archive delete command aborted by user", repo_path=path, archive_name=archive)
        console.print("Aborted.")
        return

    try:
        repo_info = ctx.orchestrator.get_repo(path=path)
        ctx.orchestrator.delete_archive(repo_info, archive, dry_run=dry_run, passphrase=passphrase)
        logger.info(
            "Archive delete command completed",
            repo_name=_repo_name(repo_info),
            repo_path=_repo_path(repo_info, path),
            archive_name=archive,
            dry_run=dry_run,
        )
        if dry_run:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
        else:
            console.print("[bold green]Archive deleted successfully[/]")
    except Exception as error:
        logger.exception(
            "Archive delete command failed",
            error=str(error),
            repo_path=path,
            archive_name=archive,
            dry_run=dry_run,
        )
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
    from borgboi.lib import utils
    from borgboi.lib.colors import COLOR_HEX

    logger.info(
        "Running archive contents command",
        repo_name=name,
        repo_path=path,
        archive_name=archive,
        output=output,
    )
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        contents = borg.list_archive_contents(repo_info.path, archive, passphrase=passphrase)
        logger.debug(
            "Retrieved archive contents",
            repo_name=_repo_name(repo_info, name),
            repo_path=_repo_path(repo_info, path),
            archive_name=archive,
            item_count=len(contents),
        )

        if output == "stdout":
            for item in contents:
                console.print(f"  [{COLOR_HEX.sky}]{utils.shorten_archive_path(item.path)}[/]")
            console.rule()
            logger.info(
                "Archive contents command completed",
                repo_name=_repo_name(repo_info, name),
                repo_path=_repo_path(repo_info, path),
                archive_name=archive,
                output=output,
            )
            return

        output_path = Path(output)
        with output_path.open("w", encoding="utf-8") as file_obj:
            for item in contents:
                file_obj.write(item.path + "\n")
        logger.info(
            "Archive contents written to file",
            repo_name=_repo_name(repo_info, name),
            repo_path=_repo_path(repo_info, path),
            archive_name=archive,
            output_path=str(output_path),
        )
        console.print(f"Archive contents written to [bold cyan]{output_path}[/]")
    except Exception as error:
        logger.exception(
            "Archive contents command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            archive_name=archive,
            output=output,
        )
        print_error_and_exit(str(error), error=error)


@backup.command(name="diff")
def backup_diff(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    archive1: Annotated[str | None, Parameter(name=["--archive1", "-a"], help="Older archive name")] = None,
    archive2: Annotated[str | None, Parameter(name=["--archive2", "-b"], help="Newer archive name")] = None,
    filter_path: Annotated[
        tuple[str, ...],
        Parameter(name="--filter-path", help="Limit diff to one or more archive paths; repeat to provide multiple"),
    ] = (),
    content_only: Annotated[
        bool,
        Parameter(name="--content-only", negative="", help="Compare file contents only"),
    ] = False,
    json_output: Annotated[bool, Parameter(name="--json", negative="", help="Render JSON output")] = False,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """Compare two archives in a repository."""
    from borgboi.core.models import DiffOptions

    logger.info(
        "Running archive diff command",
        repo_name=name,
        repo_path=path,
        archive1=archive1,
        archive2=archive2,
        content_only=content_only,
        json_output=json_output,
        filter_path_count=len(filter_path),
    )
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)

        if (archive1 is None) != (archive2 is None):
            print_error_and_exit(
                "Provide both --archive1 and --archive2, or omit both to compare the two most recent archives."
            )

        archives_validated = False
        if archive1 is None and archive2 is None:
            selected_archive1, selected_archive2 = ctx.orchestrator.get_two_most_recent_archives(
                repo_info,
                passphrase=passphrase,
            )
            archive1 = selected_archive1.name
            archive2 = selected_archive2.name
            archives_validated = True

        assert archive1 is not None
        assert archive2 is not None

        result = ctx.orchestrator.diff_archives(
            repo_info,
            archive1,
            archive2,
            options=DiffOptions(content_only=content_only, paths=list(filter_path)),
            passphrase=passphrase,
            validated=archives_validated,
        )
        _render_diff_result(result, json_output=json_output)
    except Exception as error:
        logger.exception(
            "Archive diff command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            archive1=archive1,
            archive2=archive2,
            content_only=content_only,
            json_output=json_output,
        )
        print_error_and_exit(str(error), error=error)
