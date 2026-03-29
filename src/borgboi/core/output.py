"""Output handling for BorgBoi operations.

This module provides abstractions for handling output from Borg commands,
allowing for flexible output processing (console, logging, silent, etc.).
"""

from collections.abc import Generator, Iterable
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any, Protocol

from pydantic import ValidationError

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
    parse_borg_log_line,
)
from borgboi.core.logging import get_logger
from borgboi.lib.utils import format_size_bytes

_PROGRESS_MSGID_LABELS: dict[str, str] = {
    "cache.begin_transaction": "Cache initialization",
    "cache.commit": "Cache commit",
}

logger = get_logger(__name__)


def _humanize_msgid(msgid: str | None) -> str:
    if msgid is None:
        return "Operation"
    if msgid in _PROGRESS_MSGID_LABELS:
        return _PROGRESS_MSGID_LABELS[msgid]
    return msgid.replace(".", " ").replace("_", " ").title()


class BaseOutputHandler(Protocol):
    """Compatibility protocol for Borg operation output handlers.

    Implementations can direct output to console, logs, files, or discard it entirely.
    This captures the pre-streaming handler contract so existing custom handlers that
    only implement the `on_*` hooks can still be injected into orchestrators and
    Borg clients.
    """

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        """Handle progress updates.

        Args:
            current: Current progress value
            total: Total progress value (0 if indeterminate)
            info: Optional additional information about the progress
        """
        ...

    def on_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Handle log messages.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            kwargs: Additional log context
        """
        ...

    def on_file_status(self, status: str, path: str) -> None:
        """Handle file status updates during backup/restore.

        Args:
            status: File status code (A=added, M=modified, E=error, etc.)
            path: File path
        """
        ...

    def on_stdout(self, line: str) -> None:
        """Handle a line of stdout output.

        Args:
            line: Output line
        """
        ...

    def on_stderr(self, line: str) -> None:
        """Handle a line of stderr output.

        Args:
            line: Error output line
        """
        ...

    def on_stats(self, stats: dict[str, Any]) -> None:
        """Handle statistics output from Borg.

        Args:
            stats: Statistics dictionary from Borg
        """
        ...


class SectionOutputHandler(BaseOutputHandler, Protocol):
    """Optional protocol for handlers that support section wrappers."""

    def section(self, status: str, success_msg: str) -> AbstractContextManager[None]:
        """Context manager wrapping a logical operation section.

        Implementations may render visual decorations (rulers, spinners) around
        the yielded block.  Non-interactive handlers should yield without side-effects.

        Args:
            status: Description of the operation shown while it runs
            success_msg: Message displayed when the operation completes
        """
        ...


class OutputHandler(BaseOutputHandler, Protocol):
    """Extended output handler protocol with streaming command rendering.

    Newer interactive handlers should implement this richer streaming hook.
    Callers that need to support legacy handlers should use
    `render_command_with_fallback()`.
    """

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Iterable[str],
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        """Render a streaming command operation.

        Args:
            status: Description of the operation shown while it runs
            success_msg: Message displayed when the operation completes
            log_stream: Iterable stream of command output lines
            spinner: Rich spinner style for interactive handlers
            ruler_color: Rich rule color for interactive handlers
        """
        ...


def render_command_with_fallback(
    output: BaseOutputHandler,
    status: str,
    success_msg: str,
    log_stream: Iterable[str],
    *,
    spinner: str = "point",
    ruler_color: str = "#74c7ec",
) -> None:
    """Render a command stream while supporting legacy output handlers.

    If the handler implements `render_command()`, use it. Otherwise fall back to
    the older `section()` plus `on_stderr()` streaming behavior when available,
    or plain `on_stderr()` streaming for handlers that only implement `on_*`
    methods.
    """
    render_command = getattr(output, "render_command", None)
    if callable(render_command):
        logger.debug(
            "Rendering command with output handler render_command",
            output_handler=type(output).__name__,
            status=status,
            success_msg=success_msg,
            spinner=spinner,
        )
        render_command(
            status,
            success_msg,
            log_stream,
            spinner=spinner,
            ruler_color=ruler_color,
        )
        return

    section = getattr(output, "section", None)
    logger.debug(
        "Rendering command with legacy output fallback",
        output_handler=type(output).__name__,
        status=status,
        success_msg=success_msg,
        supports_section=callable(section),
    )
    section_context = section(status, success_msg) if callable(section) else nullcontext()
    with section_context:  # pyright: ignore[reportGeneralTypeIssues]
        for line in log_stream:
            output.on_stderr(line)


class DefaultOutputHandler:
    """Default output handler that prints to Rich console."""

    def __init__(self) -> None:
        # Lazy import to avoid circular dependency
        from borgboi.rich_utils import console

        self._console = console

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        """Print progress to console."""
        if total > 0:
            percent = (current / total) * 100
            msg = f"Progress: {current}/{total} ({percent:.1f}%)"
        else:
            msg = f"Progress: {current}"
        if info:
            msg += f" - {info}"
        self._console.print(msg, end="\r")

    def on_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Print log message to console with appropriate styling."""
        style_map = {
            "debug": "dim",
            "info": "",
            "warning": "bold yellow",
            "error": "bold red",
        }
        style = style_map.get(level, "")
        if style:
            self._console.print(f"[{style}]{message}[/]")
        else:
            self._console.print(message)

    def on_file_status(self, status: str, path: str) -> None:
        """Print file status to console."""
        status_styles = {
            "A": "green",  # Added
            "M": "yellow",  # Modified
            "U": "blue",  # Unchanged
            "E": "red",  # Error
            "x": "dim",  # Excluded
        }
        style = status_styles.get(status, "")
        if style:
            self._console.print(f"[{style}]{status}[/] {path}")
        else:
            self._console.print(f"{status} {path}")

    def on_stdout(self, line: str) -> None:
        """Print stdout line to console."""
        self._console.print(line.rstrip())

    def on_stderr(self, line: str) -> None:
        """Render stderr output, decoding Borg JSON log events when possible."""
        cleaned_line = line.rstrip()
        if not cleaned_line:
            return

        try:
            event = parse_borg_log_line(cleaned_line)
        except ValidationError:
            self._console.print(f"[dim]{cleaned_line}[/]")
            return

        if isinstance(event, ArchiveProgress):
            self._render_archive_progress(event)
            return

        if isinstance(event, ProgressPercent):
            self._render_progress_percent(event)
            return

        if isinstance(event, ProgressMessage):
            self._render_progress_message(event)
            return

        if isinstance(event, FileStatus):
            self.on_file_status(event.status, event.path)
            return

        self._render_log_message(event)

    def _render_archive_progress(self, archive_progress: ArchiveProgress) -> None:
        if archive_progress.finished:
            self._console.print("[bold green]Archive write complete[/]")
            return

        details: list[str] = []
        if archive_progress.path:
            details.append(archive_progress.path)
        if archive_progress.nfiles is not None:
            details.append(f"{archive_progress.nfiles} files")

        size_parts: list[str] = []
        if archive_progress.original_size is not None:
            size_parts.append(f"orig {format_size_bytes(archive_progress.original_size)}")
        if archive_progress.compressed_size is not None:
            size_parts.append(f"comp {format_size_bytes(archive_progress.compressed_size)}")
        if archive_progress.deduplicated_size is not None:
            size_parts.append(f"dedup {format_size_bytes(archive_progress.deduplicated_size)}")
        if size_parts:
            details.append(" | ".join(size_parts))

        if details:
            self._console.print(f"[cyan]Backing up[/] {' | '.join(details)}")

    def _render_progress_message(self, progress_message: ProgressMessage) -> None:
        if progress_message.message:
            self._console.print(f"[cyan]{progress_message.message}[/]")
            return

        if progress_message.finished:
            operation = _humanize_msgid(progress_message.msgid)
            self._console.print(f"[green]✓[/] {operation} complete")

    def _render_progress_percent(self, progress_percent: ProgressPercent) -> None:
        info_parts: list[str] = []
        if progress_percent.message:
            info_parts.append(progress_percent.message)
        if progress_percent.info:
            info_parts.extend(progress_percent.info)

        self.on_progress(
            current=progress_percent.current or 0,
            total=progress_percent.total or 0,
            info=" | ".join(info_parts) if info_parts else None,
        )

        if progress_percent.finished:
            operation = _humanize_msgid(progress_percent.msgid)
            self._console.print(f"[green]✓[/] {operation} complete")

    def _render_log_message(self, log_message: LogMessage) -> None:
        message = log_message.message.strip()
        if not message:
            return

        if log_message.name == "borg.output.show-rc" and message.startswith("terminating with success status"):
            return

        if log_message.name == "borg.output.stats" and set(message) == {"-"}:
            return

        self.on_log(log_message.levelname.lower(), message, logger=log_message.name, msgid=log_message.msgid)

    def on_stats(self, stats: dict[str, Any]) -> None:
        """Print statistics to console."""
        from borgboi.lib.colors import COLOR_HEX

        self._console.rule(f"[{COLOR_HEX.mauve}]Statistics[/]")
        for key, value in stats.items():
            self._console.print(f"  {key}: {value}")

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Iterable[str],
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        """Render a streaming command with Rich status and parsed Borg output."""
        from borgboi.lib.colors import COLOR_HEX
        from borgboi.rich_utils import TEXT_COLOR

        logger.debug(
            "Rendering streaming command in default output handler",
            status=status,
            success_msg=success_msg,
            spinner=spinner,
            ruler_color=ruler_color,
        )
        self._console.rule(f"[bold {TEXT_COLOR}]{status}[/]", style=ruler_color)
        with self._console.status(status=f"[bold {COLOR_HEX.blue}]{status}[/]", spinner=spinner):
            for line in log_stream:
                self.on_stderr(line)
        self._console.rule(f":heavy_check_mark: [bold {TEXT_COLOR}]{success_msg}[/]", style=ruler_color)
        self._console.print("")
        logger.debug("Completed streaming command in default output handler", status=status, success_msg=success_msg)

    @contextmanager
    def section(self, status: str, success_msg: str) -> Generator[None]:
        """Render a Rich ruler + spinner around the yielded block."""
        from borgboi.lib.colors import COLOR_HEX
        from borgboi.rich_utils import TEXT_COLOR

        ruler_color = "#74c7ec"
        self._console.rule(f"[bold {TEXT_COLOR}]{status}[/]", style=ruler_color)
        with self._console.status(status=f"[bold {COLOR_HEX.blue}]{status}[/]", spinner="point"):
            yield
        self._console.rule(f":heavy_check_mark: [bold {TEXT_COLOR}]{success_msg}[/]", style=ruler_color)
        self._console.print("")


class SilentOutputHandler:
    """Output handler that discards all output. Useful for testing."""

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        """Discard progress updates."""

    def on_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Discard log messages."""

    def on_file_status(self, status: str, path: str) -> None:
        """Discard file status updates."""

    def on_stdout(self, line: str) -> None:
        """Discard stdout output."""

    def on_stderr(self, line: str) -> None:
        """Discard stderr output."""

    def on_stats(self, stats: dict[str, Any]) -> None:
        """Discard statistics."""

    @contextmanager
    def section(self, status: str, success_msg: str) -> Generator[None]:
        """No-op section wrapper."""
        yield

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Iterable[str],
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        """Consume command output without rendering it."""
        _ = status, success_msg, spinner, ruler_color
        for _line in log_stream:
            pass


class CollectingOutputHandler:
    """Output handler that collects all output for later inspection.

    Useful for testing and programmatic access to command output.
    """

    def __init__(self) -> None:
        self.progress_updates: list[tuple[int, int, str | None]] = []
        self.log_messages: list[tuple[str, str, dict[str, Any]]] = []
        self.file_statuses: list[tuple[str, str]] = []
        self.stdout_lines: list[str] = []
        self.stderr_lines: list[str] = []
        self.stats: list[dict[str, Any]] = []

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        """Collect progress updates."""
        self.progress_updates.append((current, total, info))

    def on_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Collect log messages."""
        self.log_messages.append((level, message, kwargs))

    def on_file_status(self, status: str, path: str) -> None:
        """Collect file status updates."""
        self.file_statuses.append((status, path))

    def on_stdout(self, line: str) -> None:
        """Collect stdout output."""
        self.stdout_lines.append(line)

    def on_stderr(self, line: str) -> None:
        """Collect stderr output."""
        self.stderr_lines.append(line)

    def on_stats(self, stats: dict[str, Any]) -> None:
        """Collect statistics."""
        self.stats.append(stats)

    @contextmanager
    def section(self, status: str, success_msg: str) -> Generator[None]:
        """No-op section wrapper."""
        yield

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Iterable[str],
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        """Collect command output lines through the stderr channel."""
        _ = status, success_msg, spinner, ruler_color
        for line in log_stream:
            self.on_stderr(line)

    def clear(self) -> None:
        """Clear all collected output."""
        self.progress_updates.clear()
        self.log_messages.clear()
        self.file_statuses.clear()
        self.stdout_lines.clear()
        self.stderr_lines.clear()
        self.stats.clear()
