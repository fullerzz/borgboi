from collections.abc import Generator, Iterable

from pydantic import ValidationError
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
)
from borgboi.models import BorgBoiRepo

TEXT_COLOR = "#74c7ec"
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


def output_repos_table(repos: list[BorgBoiRepo]) -> None:
    table = Table(title="BorgBoi Repositories", show_lines=True)
    table.add_column("Name")
    table.add_column("Local Path 📁")
    table.add_column("Hostname 🖥")
    table.add_column("Last Archive 📆")
    table.add_column("Size 💾", justify="right")
    table.add_column("Backup Target 🎯")

    for repo in repos:
        name = f"[bold cyan]{repo.name}[/]"
        local_path = f"[bold blue]{repo.path}[/]"
        env_var_name = f"[bold green]{repo.hostname}[/]"
        backup_target = f"[bold magenta]{repo.backup_target}[/]"
        if repo.last_backup:
            archive_date = f"[bold yellow]{repo.last_backup.strftime('%a %b %d, %Y')}[/]"
        else:
            archive_date = "[italic red]Never[/]"

        if repo.metadata is None:
            size = "🤷[italic red]Unknown[/]"
        elif repo.metadata.cache.unique_csize_gb != 0.0:
            size = f"[dark_orange]{repo.metadata.cache.unique_csize_gb} GB[/]"
        else:
            size = "🤷[italic red]Unknown[/]"

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

    with console.status(status=f"[bold blue]{status}[/]", spinner=spinner):
        for log in log_stream:
            print(log, end="")  # noqa: T201

    console.rule(f":heavy_check_mark: [bold {TEXT_COLOR}]{success_msg}[/]", style=ruler_color)
    console.print("")
