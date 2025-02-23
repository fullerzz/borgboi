import subprocess as sp

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(record=True)


def print_cmd_parts(cmd_parts: list[str]) -> None:
    cmd = Text.assemble(("Preparing to execute: ", "orange3"), (" ".join(cmd_parts), "bold blue"))
    console.print(cmd)


def run_and_log_sp_popen(
    cmd_parts: list[str],
    status_message: str,
    success_message: str,
    error_message: str,
    spinner: str = "arrow",
    use_stderr: bool = False,
) -> None:
    """
    Run a subprocess.Popen command and logs the output to the console.
    This output is wrapped by a rich console.status context manager to
    display a spinner while the command is running.

    Args:
        cmd_parts (list[str]): command inputs to pass to subprocess.Popen
        status_message (str): status message to display continuously while command runs
        success_message (str): message to be display upon successful completion of command
        error_message (str): message to display upon command failure
        spinner (str, optional): name of spinner animation to use. Defaults to "arrow". See 'python -m rich.spinner' for options.
        use_stderr (bool, optional): Log stderr instead of stdout to console. Defaults to False.

    Raises:
        sp.CalledProcessError: Error raised if command exit code isn't 0 or 1
    """
    print_cmd_parts(cmd_parts)
    proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    status = status_message

    # Borg logs to stderr so that's a use-case where use_stderr would be True
    out_stream = proc.stdout if not use_stderr else proc.stderr

    with console.status(status, spinner=spinner):
        while out_stream.readable():  # type: ignore
            line = out_stream.readline()  # type: ignore
            print(line.decode("utf-8"), end="")  # noqa: T201
            if not line:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
                break

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0 and returncode != 1:
        console.print(f":x: [bold red]{error_message} - Return code: {proc.returncode}[/]")
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd_parts)
    console.print(f":heavy_check_mark: [bold green]{success_message}[/]")


def output_obj(obj: object) -> None:
    console.print(obj)


def output_init_instructions(repo_path: str) -> None:
    """
    Print instructions for initializing a new Borg repository.
    """
    console.print("To initialize the Borg repository, run the following command:")
    console.print(f"[bold blue]borg init --progress --encryption=repokey --storage-quota=100G {repo_path}[/]")


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
