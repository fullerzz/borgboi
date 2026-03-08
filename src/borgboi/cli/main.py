"""Main CLI app for BorgBoi."""

from collections.abc import Iterable
from importlib.metadata import version as get_version
from typing import Annotated, Any, NoReturn

import cyclopts
from cyclopts import App, Parameter
from rich.prompt import Confirm
from rich.traceback import install

from borgboi.config import Config, get_config
from borgboi.core.orchestrator import Orchestrator
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
        if self._orchestrator is None:
            self._orchestrator = Orchestrator(config=self.config)
        return self._orchestrator

    @property
    def config(self) -> Config:
        if self._config is None:
            base_config = get_config()
            self._config = Config(
                aws=base_config.aws,
                borg=base_config.borg,
                ui=base_config.ui,
                offline=self.offline or base_config.offline,
                debug=self.debug or base_config.debug,
            )
        return self._config


ContextArg = Annotated[BorgBoiContext, Parameter(parse=False)]
MetaTokens = Annotated[str, Parameter(show=False, allow_leading_hyphen=True)]


def print_error_and_exit(message: str, *, error: Exception | None = None) -> NoReturn:
    console.print(f"[bold red]Error:[/] {message}")
    raise SystemExit(1) from error


def confirm_action(prompt: str) -> bool:
    return Confirm.ask(prompt, console=console, default=False)


app = App(
    name="borgboi",
    help=(
        "BorgBoi - Borg backup automation with AWS integration.\n\n"
        "Use subcommands to manage repositories and backups: repo, backup, s3, exclusions, config."
    ),
    version=get_version("borgboi"),
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
    console.print(f"borgboi {get_version('borgboi')}", highlight=False)


def _register_commands() -> None:
    from borgboi.cli.backup import backup
    from borgboi.cli.config import config
    from borgboi.cli.exclusions import exclusions
    from borgboi.cli.repo import repo
    from borgboi.cli.s3 import s3

    app.command(repo)
    app.command(backup)
    app.command(s3)
    app.command(exclusions)
    app.command(config)


_register_commands()


def cli(tokens: Iterable[str] | str | None = None, **kwargs: Any) -> Any:
    """Invoke the BorgBoi CLI."""
    return app.meta(tokens, **kwargs)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
