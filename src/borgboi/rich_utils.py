import subprocess as sp

from rich.console import Console
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


def output_repo_info(
    *,
    name: str,
    total_size_gb: float,
    total_csize_gb: float,
    unique_csize_gb: float,
    encryption_mode: str,
    repo_id: str,
    repo_location: str,
    last_modified: str,
) -> None:
    """
    Pretty print Borg repository information.
    """
    table = Table(title=f"Borg Repo Info - {repo_id}", show_header=False, show_lines=True, row_styles=["dim", ""])
    table.add_column()
    table.add_column()
    table.add_row("[bold blue]Name[/]", f"[cyan]{name}[/]")
    table.add_section()
    table.add_row("[bold blue]Total Size (GB)", f"[cyan]{total_size_gb:.2f}")
    table.add_row("[bold blue]Total Compressed Size (GB)", f"[cyan]{total_csize_gb:.2f}")
    table.add_row("[bold blue]Unique Compressed Size (GB)", f"[cyan]{unique_csize_gb:.2f}")
    table.add_section()
    table.add_row("[bold blue]Encryption", f"[cyan]{encryption_mode}")
    table.add_row("[bold blue]Last Modified", f"[cyan]{last_modified}")
    table.add_row("[bold blue]Repo Location", f"[cyan]{repo_location}")
    console.print(table, new_line_start=True)
