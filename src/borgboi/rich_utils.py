from functools import lru_cache
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns


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


def print_successful_s3_sync() -> None:
    console = get_console()
    console.print(
        Panel(
            "[bold green]Successfully synced with S3 bucket[/]",
            title="S3 Sync Complete",
            expand=False,
        )
    )
