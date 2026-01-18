"""Output handling for BorgBoi operations.

This module provides abstractions for handling output from Borg commands,
allowing for flexible output processing (console, logging, silent, etc.).
"""

from typing import Any, Protocol


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
        """Print stderr line to console."""
        self._console.print(f"[dim]{line.rstrip()}[/]")

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
