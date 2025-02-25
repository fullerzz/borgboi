import subprocess as sp
from collections.abc import Generator, Iterable

from pydantic import ValidationError
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
)

console = Console(record=True)


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
    console.rule("[bold]Borg Repo Info", style="blue")
    console.print(f"[bold magenta]Repo Name:[/] {name}")
    size_panel = _build_size_panel(total_size_gb, total_csize_gb, unique_csize_gb)
    metadata_panel = _build_metadata_panel(encryption_mode, repo_id, repo_location, last_modified)
    columns = Columns([size_panel, metadata_panel])
    console.print(columns)
    console.rule(f"[bold magenta]Repo ID:[/] [magenta]{repo_id}[/]", style="blue")


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
    resp = console.input(f"[red]Type [bold]{confirmation_key}[/] to confirm deletion: ")
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
    log_msg: ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus
    for log in log_stream:
        try:
            log_msg = ArchiveProgress.model_validate_json(log)
        except ValidationError:
            try:
                log_msg = ProgressPercent.model_validate_json(log)
            except ValidationError:
                try:
                    log_msg = ProgressMessage.model_validate_json(log)
                except ValidationError:
                    log_msg = LogMessage.model_validate_json(log)
        yield log_msg


def _build_archive_progress_string(
    msg: ArchiveProgress,
    original_size: int | None,
    compressed_size: int | None,
    deduplicated_size: int | None,
    nfiles: int | None,
) -> str:
    val = ""
    if msg.original_size:
        val += f"Original Size: {msg.original_size} bytes"
    elif original_size:
        val += f"Original Size: {original_size} bytes"
    if msg.compressed_size:
        val += f" Compressed Size: {msg.compressed_size} bytes"
    elif compressed_size:
        val += f" Compressed Size: {compressed_size} bytes"
    if msg.deduplicated_size:
        val += f" Deduplicated Size: {msg.deduplicated_size} bytes"
    elif deduplicated_size:
        val += f" Deduplicated Size: {deduplicated_size} bytes"
    if msg.nfiles:
        val += f" Number of files: {msg.nfiles}"
    elif nfiles:
        val += f" Number of files: {nfiles}"
    if msg.path:
        val += f" Path: {msg.path}"
    val += f" Finished: {msg.finished}"
    return val


def render_cmd_output(cmd: str, log_stream: Iterable[str]) -> None:
    nfiles: int | None = None
    original_size: int | None = None
    compressed_size: int | None = None
    deduplicated_size: int | None = None
    status = cmd
    with console.status(status, spinner="arrow"):
        for log in parse_logs(log_stream):
            if isinstance(log, ArchiveProgress):
                nfiles = log.nfiles if log.nfiles else nfiles
                original_size = log.original_size if log.original_size else original_size
                compressed_size = log.compressed_size if log.compressed_size else compressed_size
                deduplicated_size = log.deduplicated_size if log.deduplicated_size else deduplicated_size
                msg = _build_archive_progress_string(log, original_size, compressed_size, deduplicated_size, nfiles)
                console.print(f"[bold blue]{msg}")
                console.print_json(log.model_dump_json(exclude_none=True))
            elif isinstance(log, ProgressMessage):
                console.print_json(log.model_dump_json(exclude_none=True))
            elif isinstance(log, ProgressPercent):
                console.print_json(log.model_dump_json(exclude_none=True))
            elif isinstance(log, LogMessage):
                console.print_json(log.model_dump_json(exclude_none=True))
            elif isinstance(log, FileStatus):
                console.print_json(log.model_dump_json(exclude_none=True))
