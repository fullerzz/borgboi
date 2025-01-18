import subprocess as sp

from rich.console import Console
from rich.text import Text

console = Console(record=True)


def _print_cmd_parts(cmd_parts: list[str]) -> None:
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
    _print_cmd_parts(cmd_parts)
    proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    status = status_message

    # Borg logs to stderr so that's a use-case where use_stderr would be True
    out_stream = proc.stdout if not use_stderr else proc.stderr

    with console.status(status, spinner=spinner):
        while out_stream.readable():  # type: ignore
            line = out_stream.readline()  # type: ignore
            print(line.decode("utf-8"), end="")  # noqa: T201
            if not line:
                break

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0 and returncode != 1:
        console.print(f":x: [bold red]{error_message} - Return code: {proc.returncode}[/]")
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd_parts)
    console.print(f":heavy_check_mark: [bold green]{success_message}[/]")


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
