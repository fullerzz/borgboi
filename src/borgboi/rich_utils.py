from collections.abc import Generator, Iterable
from datetime import UTC
from typing import TYPE_CHECKING

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
    parse_borg_log_stream,
)
from borgboi.lib.colors import COLOR_HEX, PYGMENTS_STYLES
from borgboi.models import BorgBoiRepo

TEXT_COLOR = COLOR_HEX.text
console = Console(record=True)

if TYPE_CHECKING:
    from borgboi.clients.s3 import S3BucketStats


def save_console_output() -> None:
    """
    Save the console output to an HTML file.
    """
    console.save_html("borgboi_output.html")


def _build_size_panel(total_size_gb: str, total_csize_gb: str, unique_csize_gb: str) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column()
    table.add_column(justify="right")
    table.add_row("[bold blue]Total Size", f"[cyan]{total_size_gb} GB")
    table.add_row("[bold blue]Compressed Size", f"[cyan]{total_csize_gb} GB")
    table.add_row("[bold blue]Deduplicated Size", f"[cyan]{unique_csize_gb} GB")
    return Panel(table, title="Disk Usage 💾", border_style="blue", expand=False)


def _build_metadata_panel(encryption_mode: str, repo_id: str, repo_location: str, last_modified: str) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column()
    table.add_column()
    table.add_row("[bold green]Encryption", f"[orange3]{encryption_mode}")
    table.add_row("[bold green]Location", f"[orange3]{repo_location}")
    table.add_row("[bold green]Last Modified", f"[orange3]{last_modified}")
    return Panel(table, title="Metadata 📝", border_style="green", expand=False)


def output_repo_info(
    *,
    name: str,
    total_size_gb: str,
    total_csize_gb: str,
    unique_csize_gb: str,
    encryption_mode: str,
    repo_id: str,
    repo_location: str,
    last_modified: str,
) -> None:
    """
    Pretty print Borg repository information.
    """
    console.rule("[bold]Borg Repo Info", style=COLOR_HEX.blue)
    console.print(f"[bold {COLOR_HEX.mauve}]Repo Name:[/] {name}")
    size_panel = _build_size_panel(total_size_gb, total_csize_gb, unique_csize_gb)
    metadata_panel = _build_metadata_panel(encryption_mode, repo_id, repo_location, last_modified)
    columns = Columns([size_panel, metadata_panel])
    console.print(columns)
    console.rule(f"[bold {COLOR_HEX.mauve}]Repo ID:[/] [{COLOR_HEX.mauve}]{repo_id}[/]", style=COLOR_HEX.blue)


def output_repos_table(repos: list[BorgBoiRepo]) -> None:
    table = Table(title="BorgBoi Repositories", show_lines=True)
    table.add_column("Name")
    table.add_column("Local Path 📁")
    table.add_column("Hostname 🖥")
    table.add_column("Last Archive 📆")
    table.add_column("Size 💾", justify="right")
    table.add_column("Backup Target 🎯")

    for repo in repos:
        name = f"[bold {COLOR_HEX.sky}]{repo.name}[/]"
        local_path = f"[bold {COLOR_HEX.blue}]{repo.path}[/]"
        env_var_name = f"[bold green]{repo.hostname}[/]"
        backup_target = f"[bold {COLOR_HEX.mauve}]{repo.backup_target}[/]"
        if repo.last_backup:
            archive_date = f"[bold {COLOR_HEX.yellow}]{repo.last_backup.strftime('%a %b %d, %Y')}[/]"
        else:
            archive_date = f"[italic {COLOR_HEX.red}]Never[/]"

        if repo.metadata is None:
            size = f"🤷[italic {COLOR_HEX.red}]Unknown[/]"
        elif repo.metadata.cache.unique_csize_gb != 0.0:
            size = f"[{COLOR_HEX.peach}]{repo.metadata.cache.unique_csize_gb} GB[/]"
        else:
            size = f"🤷[italic {COLOR_HEX.red}]Unknown[/]"

        table.add_row(name, local_path, env_var_name, archive_date, size, backup_target)
    console.print(table)


def confirm_deletion(repo_name: str, archive_name: str = "") -> None:
    """
    Prompts the user to confirm deletion of a Borg repository or archive.

    Args:
        repo_name (str): name of the repository to be deleted
        archive_name (str, optional): name of the archive to be deleted. Defaults to "".

    Raises:
        ValueError: If the user does not confirm deletion.

    Returns:
        None: Indicates the confirmation process is complete.
    """
    confirmation_key = repo_name
    if archive_name:
        confirmation_key = f"{repo_name}::{archive_name}"
    resp = console.input(f"[{COLOR_HEX.red}]Type [bold]{confirmation_key}[/] to confirm deletion: ")
    if resp.lower() == confirmation_key.lower():
        return None
    console.print("Deletion aborted.")
    raise ValueError("Deletion aborted.")


def parse_logs(
    log_stream: Iterable[str],
) -> Generator[ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus]:
    """
    Parse the logs from the borg client

    Args:
        log_stream (Iterable[str]): logs from the borg client

    Yields:
        Generator[ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus]: validated log message
    """
    yield from parse_borg_log_stream(log_stream)


def render_cmd_output_lines(
    status: str, success_msg: str, log_stream: Iterable[str], spinner: str = "point", ruler_color: str = "#74c7ec"
) -> None:
    """
    Render the output of a command to the console.

    Args:
        cmd (str): The command that was executed.
        log_stream (Iterable[str]): The output of the command.

    Returns:
        None
    """
    console.rule(f"[bold {TEXT_COLOR}]{status}[/]", style=ruler_color)

    with console.status(status=f"[bold {COLOR_HEX.blue}]{status}[/]", spinner=spinner):
        for log in log_stream:
            print(log, end="")  # noqa: T201

    console.rule(f":heavy_check_mark: [bold {TEXT_COLOR}]{success_msg}[/]", style=ruler_color)
    console.print("")


def render_excludes_file(excludes_file_path: str, lines_to_highlight: set[int] | None = None) -> None:
    """
    Render the contents of the excludes file to the console.

    Args:
        excludes_file_path (str): Path to the excludes file.
        lines_to_highlight (set[int], optional): Set of line numbers to highlight. Defaults to None.

    Returns:
        None
    """
    syntax = Syntax.from_path(
        excludes_file_path,
        line_numbers=True,
        theme=PYGMENTS_STYLES["catppuccin-mocha"],  # type: ignore[arg-type]
        padding=1,
        highlight_lines=lines_to_highlight,
    )
    panel = Panel(syntax, title="Excludes File", expand=False)
    console.print(panel)


def output_s3_bucket_stats(stats: "S3BucketStats") -> None:
    """Render S3 bucket metrics with Rich panel/table output."""
    timestamp = (
        stats.metrics_timestamp.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        if stats.metrics_timestamp
        else "Unavailable"
    )

    summary_table = Table.grid(padding=(0, 1))
    summary_table.add_column(style=f"bold {COLOR_HEX.blue}")
    summary_table.add_column(style=f"{COLOR_HEX.text}")
    summary_table.add_row("Bucket", stats.bucket_name)
    summary_table.add_row("Total Size", f"{stats.total_size_bytes / (1024**3):.2f} GB")
    summary_table.add_row("Total Objects", f"{stats.total_object_count:,}")
    summary_table.add_row("CloudWatch Timestamp", timestamp)
    summary_table.add_row("Metric Source", "AWS/S3 daily storage metrics")

    forecast = stats.intelligent_tiering_forecast
    if forecast is None:
        summary_table.add_row("Upcoming IT FA->IA (7d)", "Unavailable")
    elif not forecast.available:
        summary_table.add_row("Upcoming IT FA->IA (7d)", "Unavailable")
        if forecast.unavailable_reason:
            summary_table.add_row("Forecast Details", forecast.unavailable_reason)
    else:
        summary_table.add_row(
            "Upcoming IT FA->IA (7d)",
            (
                f"{forecast.objects_transitioning_next_week:,} objects / "
                f"{forecast.size_bytes_transitioning_next_week / (1024**3):.2f} GB"
            ),
        )
        inventory_generated_at = (
            forecast.inventory_generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            if forecast.inventory_generated_at
            else "Unavailable"
        )
        summary_table.add_row("Inventory Timestamp", inventory_generated_at)
        if forecast.inventory_configuration_id:
            summary_table.add_row("Inventory Config", forecast.inventory_configuration_id)
        if forecast.estimation_method:
            summary_table.add_row("Forecast Method", forecast.estimation_method)

    panel = Panel(summary_table, title="S3 Bucket Stats", border_style=COLOR_HEX.blue, expand=False)
    console.print(panel)

    composition_table = Table(title="Storage Class Composition", show_lines=True)
    composition_table.add_column("Storage Class", style=f"bold {COLOR_HEX.sky}")
    composition_table.add_column("Tier", style=f"{COLOR_HEX.green}")
    composition_table.add_column("Size (GB)", justify="right", style=f"{COLOR_HEX.peach}")
    composition_table.add_column("% of Bucket", justify="right", style=f"{COLOR_HEX.yellow}")

    total_size = stats.total_size_bytes
    if not stats.storage_breakdown:
        composition_table.add_row("No data", "-", "0.00", "0.00%")
    else:
        for item in stats.storage_breakdown:
            size_gb = item.size_bytes / (1024**3)
            pct_of_bucket = (item.size_bytes / total_size * 100) if total_size > 0 else 0.0
            composition_table.add_row(
                item.storage_class,
                item.tier,
                f"{size_gb:.2f}",
                f"{pct_of_bucket:.2f}%",
            )

    console.print(composition_table)
