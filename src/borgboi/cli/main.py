"""Main CLI app for BorgBoi."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from importlib.metadata import version as get_version
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn

import cyclopts
from cyclopts import App, CycloptsError, Parameter, ResultAction
from rich.console import Console
from rich.prompt import Confirm
from rich.traceback import install

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator

import uuid_utils as uuid
from structlog.contextvars import bind_contextvars, clear_contextvars

from borgboi.config import Config, get_config
from borgboi.core.logging import configure_logging, get_logger
from borgboi.core.telemetry import (
    TelemetrySession,
    bind_trace_contextvars,
    configure_telemetry,
    force_flush_telemetry,
    get_current_trace_id,
    get_tracer,
    set_span_attributes,
    telemetry_is_active,
)
from borgboi.rich_utils import console

install(suppress=[cyclopts])


class BorgBoiContext:
    """Shared context object for CLI commands."""

    def __init__(self, offline: bool = False, debug: bool = False) -> None:
        self.offline = offline
        self.debug = debug
        self.trace_id = uuid.uuid7().hex
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
MetaTokens = Annotated[str, Parameter(show=False, allow_leading_hyphen=True)]  # pyright: ignore[reportCallIssue]
_REDACTED = "[REDACTED]"
_SENSITIVE_FLAGS = {"--passphrase"}
_TRACER = get_tracer(__name__)


def _redact_sensitive_tokens(tokens: Iterable[str]) -> list[str]:
    redacted_tokens: list[str] = []
    redact_next = False

    for token in tokens:
        if redact_next:
            redacted_tokens.append(_REDACTED)
            redact_next = False
            continue

        option, separator, _value = token.partition("=")
        if option in _SENSITIVE_FLAGS:
            if separator:
                redacted_tokens.append(f"{option}={_REDACTED}")
            else:
                redacted_tokens.append(token)
                redact_next = True
            continue

        redacted_tokens.append(token)

    return redacted_tokens


def print_error_and_exit(message: str, *, error: Exception | None = None) -> NoReturn:
    console.print(f"[bold red]Error:[/] {message}")
    raise SystemExit(1) from error


def confirm_action(prompt: str) -> bool:
    return Confirm.ask(prompt, console=console, default=False)


def _resolve_trace_endpoint(config: Config) -> str | None:
    return (
        config.telemetry.trace_endpoint
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )


def _format_trace_suffix(config: Config, flush_ok: bool) -> str:
    endpoint = _resolve_trace_endpoint(config)
    destination = endpoint or "the configured OTLP endpoint"
    verb = "sent to" if flush_ok else "queued for"
    return f" [dim](Traces {verb} {destination})[/dim]"


def _print_exit_summary(
    ctx: BorgBoiContext,
    config: Config,
    telemetry: TelemetrySession,
    otel_trace_id: str | None,
    flush_ok: bool,
) -> None:
    active_trace_id = otel_trace_id or ctx.trace_id
    trace_suffix = _format_trace_suffix(config, flush_ok) if telemetry.enabled else ""
    if config.logging.enabled:
        console.print(f"Logs for this execution have trace_id {active_trace_id}{trace_suffix}")
    elif telemetry.enabled:
        console.print(f"Trace for this execution has trace_id {active_trace_id}{trace_suffix}")


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
) -> object:
    ctx = BorgBoiContext(offline=offline, debug=debug)
    clear_contextvars()
    config = ctx.config
    safe_tokens = _redact_sensitive_tokens(tokens)
    telemetry = configure_telemetry(config)
    logging_enabled = configure_logging(config) is not None
    otel_trace_id: str | None = None

    try:
        command, bound, ignored = app.parse_args(tokens)
        additional_kwargs: dict[str, object] = {}

        for parameter_name, annotation in ignored.items():
            if annotation is BorgBoiContext:
                additional_kwargs[parameter_name] = ctx

        command_name = getattr(command, "__name__", command.__class__.__name__)
        logger = get_logger(__name__) if logging_enabled or telemetry.enabled else None

        if telemetry.enabled:
            span_name = f"cli.{command_name.removeprefix('_').replace('_', '-')}"
            with _TRACER.start_as_current_span(span_name) as span:
                set_span_attributes(
                    span,
                    {
                        "borgboi.command.name": command_name,
                        "borgboi.command.tokens": safe_tokens,
                        "borgboi.mode.offline": config.offline,
                        "borgboi.mode.debug": config.debug,
                    },
                )
                bind_trace_contextvars()
                otel_trace_id = get_current_trace_id()

                if logger is not None:
                    logger.info(
                        "Running CLI command",
                        command=command_name,
                        tokens=safe_tokens,
                        offline=config.offline,
                        debug=config.debug,
                    )

                return command(*bound.args, **bound.kwargs, **additional_kwargs)

        bind_contextvars(trace_id=ctx.trace_id)
        if logger is not None:
            logger.info(
                "Running CLI command",
                command=command_name,
                tokens=safe_tokens,
                offline=config.offline,
                debug=config.debug,
            )

        return command(*bound.args, **bound.kwargs, **additional_kwargs)
    except SystemExit:
        raise
    except Exception:
        get_logger(__name__).exception("CLI command failed", tokens=safe_tokens)
        raise
    finally:
        flush_ok = force_flush_telemetry() if telemetry.enabled or telemetry_is_active() else True
        _print_exit_summary(ctx, config, telemetry, otel_trace_id, flush_ok)
        clear_contextvars()


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
    if ctx.config.telemetry.enabled and ctx.config.telemetry.capture_tui:
        with _TRACER.start_as_current_span("tui.session") as span:
            set_span_attributes(
                span,
                {
                    "borgboi.mode.offline": ctx.config.offline,
                    "borgboi.ui.theme": ctx.config.ui.theme,
                },
            )
            bind_trace_contextvars()
            tui_app.run()
            return

    tui_app.run()


def cli(
    tokens: Iterable[str] | str | None = None,
    *,
    console: Console | None = None,
    error_console: Console | None = None,
    print_error: bool | None = None,
    exit_on_error: bool | None = None,
    help_on_error: bool | None = None,
    verbose: bool | None = None,
    end_of_options_delimiter: str | None = None,
    backend: Literal["asyncio", "trio"] | None = None,
    result_action: ResultAction | None = None,
    error_formatter: Callable[[CycloptsError], object] | None = None,
) -> object:
    """Invoke the BorgBoi CLI."""
    return app.meta(
        tokens,
        console=console,
        error_console=error_console,
        print_error=print_error,
        exit_on_error=exit_on_error,
        help_on_error=help_on_error,
        verbose=verbose,
        end_of_options_delimiter=end_of_options_delimiter,
        backend=backend,
        result_action=result_action,
        error_formatter=error_formatter,
    )


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
