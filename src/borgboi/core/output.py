"""Output handling for BorgBoi operations.

This module provides abstractions for handling output from Borg commands,
allowing for flexible output processing (console, logging, silent, etc.).
"""

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
from borgboi.lib.utils import format_size_bytes

_PROGRESS_MSGID_LABELS: dict[str, str] = {
    "cache.begin_transaction": "Cache initialization",
    "cache.commit": "Cache commit",
}


def _humanize_msgid(msgid: str | None) -> str:
    if msgid is None:
        return "Operation"
    if msgid in _PROGRESS_MSGID_LABELS:
        return _PROGRESS_MSGID_LABELS[msgid]
    return msgid.replace(".", " ").replace("_", " ").title()


class OutputHandler(Protocol):
    """Protocol for handling output from Borg operations.

    Implementations can direct output to console, logs, files, or discard it entirely.
    This enables flexible output handling across different contexts (CLI, tests, etc.).
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

    def clear(self) -> None:
        """Clear all collected output."""
        self.progress_updates.clear()
        self.log_messages.clear()
        self.file_statuses.clear()
        self.stdout_lines.clear()
        self.stderr_lines.clear()
        self.stats.clear()
