import subprocess as sp
from functools import cached_property

from pydantic import BaseModel, Field, computed_field
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

GIBIBYTES_IN_GIGABYTE = 0.93132257461548

console = Console(record=True)


class Stats(BaseModel):
    total_chunks: int
    total_csize: int = Field(description="Compressed size")
    total_size: int = Field(description="Original size")
    total_unique_chunks: int
    unique_csize: int = Field(description="Deduplicated size")
    unique_size: int


class RepoCache(BaseModel):
    path: str
    stats: Stats

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_size_gb(self) -> float:
        """Original size in gigabytes."""
        return self.stats.total_size / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_csize_gb(self) -> float:
        """Compressed size in gigabytes."""
        return self.stats.total_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def unique_csize_gb(self) -> float:
        """Deduplicated size in gigabytes."""
        return self.stats.unique_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE


class Encryption(BaseModel):
    mode: str


class Repository(BaseModel):
    id: str
    last_modified: str
    location: str


class RepoInfo(BaseModel):
    cache: RepoCache
    encryption: Encryption
    repository: Repository
    security_dir: str


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


def run_and_output_repo_info(cmd_parts: list[str]) -> None:
    """
    Run a subprocess.Popen command and logs the output to the console.
    This output is wrapped by a rich console.status context manager to
    display a spinner while the command is running.

    Args:
        cmd_parts (list[str]): command inputs to pass to subprocess.Popen

    Raises:
        sp.CalledProcessError: Error raised if command exit code isn't 0 or 1
    """
    _print_cmd_parts(cmd_parts)
    result = sp.run(cmd_parts, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        console.print(f":x: [bold red]{result.stderr} - Return code: {result.returncode}[/]")
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd_parts)
    foo = RepoInfo.model_validate_json(result.stdout)
    console.print(foo)
    panels: list[Panel] = []
    panels.append(Panel(f"{foo.cache.total_size_gb:.2f} GB", title="Total Size", expand=False))
    panels.append(Panel(f"{foo.cache.total_csize_gb:.2f} GB", title="Compressed Size", expand=False))
    panels.append(Panel(f"{foo.cache.unique_csize_gb:.2f} GB", title="Deduplicated Size", expand=False))
    columns = Columns(panels)
    console.print(columns)


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
