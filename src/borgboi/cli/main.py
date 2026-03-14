"""Main CLI app for BorgBoi."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import version as get_version
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import cyclopts
from cyclopts import App, Parameter
from rich.prompt import Confirm
from rich.traceback import install

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator

from borgboi.config import Config, get_config
from borgboi.rich_utils import console

install(suppress=[cyclopts])


class BorgBoiContext:
    """Shared context object for CLI commands."""

    def __init__(self, offline: bool = False, debug: bool = False) -> None:
        self.offline = offline
        self.debug = debug
        self._orchestrator: Orchestrator | None = None
        self._config: Config | None = None

    @property
    def orchestrator(self) -> Orchestrator:
        from borgboi.core.orchestrator import Orchestrator

        if self._orchestrator is None:
            self._orchestrator = Orchestrator(config=self.config)
        return self._orchestrator

    @property
    def config(self) -> Config:
        if self._config is None:
            base_config = get_config()
            self._config = base_config.model_copy(
                update={
                    "offline": self.offline or base_config.offline,
                    "debug": self.debug or base_config.debug,
                }
            )
        return self._config


ContextArg = Annotated[BorgBoiContext, Parameter(parse=False)]
MetaTokens = Annotated[str, Parameter(show=False, allow_leading_hyphen=True)]


def print_error_and_exit(message: str, *, error: Exception | None = None) -> NoReturn:
    console.print(f"[bold red]Error:[/] {message}")
    raise SystemExit(1) from error


def confirm_action(prompt: str) -> bool:
    return Confirm.ask(prompt, console=console, default=False)


_VERSION = get_version("borgboi")

app = App(
    name="borgboi",
    help=(
        "BorgBoi - Borg backup automation with AWS integration.\n\n"
        "Use subcommands to manage repositories and backups: repo, backup, s3, exclusions, config."
    ),
    version=_VERSION,
)
app.register_install_completion_command()  # NOTE: This modifies the user's shell rc file


@app.meta.default
def _launcher(
    *tokens: MetaTokens,
    offline: Annotated[
        bool,
        Parameter(name="--offline", env_var="BORGBOI_OFFLINE", negative="", help="Run in offline mode (no AWS)"),
    ] = False,
    debug: Annotated[
        bool,
        Parameter(name="--debug", env_var="BORGBOI_DEBUG", negative="", help="Enable debug output"),
    ] = False,
) -> Any:
    ctx = BorgBoiContext(offline=offline, debug=debug)
    command, bound, ignored = app.parse_args(tokens)
    additional_kwargs: dict[str, Any] = {}

    for parameter_name, annotation in ignored.items():
        if annotation is BorgBoiContext:
            additional_kwargs[parameter_name] = ctx

    return command(*bound.args, **bound.kwargs, **additional_kwargs)


@app.command(name="version")
def version() -> None:
    """Display the installed borgboi version."""
    console.print(f"borgboi {_VERSION}", highlight=False)


app.command("borgboi.cli.repo:repo")
app.command("borgboi.cli.backup:backup")
app.command("borgboi.cli.s3:s3")
app.command("borgboi.cli.exclusions:exclusions")
app.command("borgboi.cli.config:config")


@app.command(name="tui")
def tui(*, ctx: ContextArg) -> None:
    """Launch the interactive TUI."""
    from borgboi.tui import BorgBoiApp

    tui_app = BorgBoiApp(config=ctx.config)
    tui_app.run()


def cli(tokens: Iterable[str] | str | None = None, **kwargs: Any) -> Any:
    """Invoke the BorgBoi CLI."""
    return app.meta(tokens, **kwargs)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
