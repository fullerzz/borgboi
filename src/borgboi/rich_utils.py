from functools import lru_cache
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
import subprocess as sp


@lru_cache(maxsize=1)
def get_console() -> Console:
    return Console(record=True)


def print_cmd_parts(cmd_parts: list[str]) -> None:
    console = get_console()
    console.print(
        Panel(f"[bold blue]{" ".join(cmd_parts)}[/]", title="Command to be Executed")
    )


def print_create_archive_output(stdout: str, stderr: str) -> None:
    console = get_console()
    columns = Columns(
        [
            Panel(stdout, title="Standard Output", expand=False),
            Panel(stderr, title="Standard Error", expand=False),
        ],
        expand=True,
        equal=True,
    )
    console.print(columns)


def run_and_log_sp_popen(
    cmd_parts: list[str],
    status_message: str,
    success_message: str,
    error_message: str,
    spinner: str = "arrow",
    use_stderr: bool = False,
) -> None:
    console = get_console()
    print_cmd_parts(cmd_parts)
    proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)

    # Borg logs to stderr so that's a use-case where this would be used
    out_stream = proc.stdout if not use_stderr else proc.stderr
    with console.status(status_message, spinner=spinner):
        while out_stream.readable():  # type: ignore
            line = out_stream.readline()  # type: ignore
            print(line.decode("utf-8"), end="")
            if not line:
                break

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0 and returncode != 1:
        console.print(
            f":x: [bold red]{error_message} - Return code: {proc.returncode}[/]"
        )
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd_parts)
    console.print(f":heavy_check_mark: [bold green]{success_message}[/]")
