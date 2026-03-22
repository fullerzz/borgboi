"""Daily backup screen for the BorgBoi TUI."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ClassVar, override

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ProgressBar, RichLog, Select, Static, Switch

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
    parse_borg_log_line,
)
from borgboi.core.output import _humanize_msgid
from borgboi.lib.utils import format_size_bytes

if TYPE_CHECKING:
    from textual.app import App

    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


class TuiOutputHandler:
    """Output handler that writes to a Textual RichLog widget.

    All write operations go through ``app.call_from_thread`` so this handler
    is safe to use from a ``@work(thread=True)`` worker.
    """

    def __init__(self, app: App[Any], log: RichLog, progress_bar: ProgressBar | None = None) -> None:
        self._app = app
        self._log = log
        self._progress_bar = progress_bar

    def _write(self, text: str | Text) -> None:
        self._app.call_from_thread(self._log.write, text)

    # -- ProgressBar helpers (thread-safe) ------------------------------------

    def _show_progress(self) -> None:
        if self._progress_bar is None:
            return
        self._app.call_from_thread(setattr, self._progress_bar, "display", True)

    def _hide_progress(self) -> None:
        if self._progress_bar is None:
            return
        self._app.call_from_thread(setattr, self._progress_bar, "display", False)

    def _reset_progress(self, *, indeterminate: bool = False) -> None:
        if self._progress_bar is None:
            return
        bar = self._progress_bar

        def _do_reset() -> None:
            bar.update(total=None if indeterminate else 100, progress=0)

        self._app.call_from_thread(_do_reset)

    def _update_progress_bar(self, *, total: int, progress: float) -> None:
        if self._progress_bar is None:
            return
        bar = self._progress_bar

        def _do_update() -> None:
            bar.update(total=total, progress=progress)

        self._app.call_from_thread(_do_update)

    # -- BaseOutputHandler protocol ------------------------------------------

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        """Write a progress update line to the log."""
        if total > 0:
            percent = (current / total) * 100
            msg = f"Progress: {current}/{total} ({percent:.1f}%)"
        else:
            msg = f"Progress: {current}"
        if info:
            msg += f" - {info}"
        self._write(Text(msg, style="cyan"))

    def on_log(self, level: str, message: str, **_kwargs: Any) -> None:
        """Write a log message to the log widget, styled by severity level."""
        style_map = {
            "debug": "dim",
            "info": "",
            "warning": "bold yellow",
            "error": "bold red",
        }
        style = style_map.get(level, "")
        self._write(Text(message, style=style) if style else Text(message))

    def on_file_status(self, status: str, path: str) -> None:
        """Write a file status entry to the log, colour-coded by status character."""
        status_styles = {
            "A": "green",
            "M": "yellow",
            "U": "blue",
            "E": "red",
            "x": "dim",
        }
        style = status_styles.get(status, "")
        text = Text()
        text.append(status, style=style or "")
        text.append(f" {path}")
        self._write(text)

    def on_stdout(self, line: str) -> None:
        """Write a raw stdout line to the log."""
        self._write(line.rstrip())

    def on_stderr(self, line: str) -> None:
        """Parse a stderr line as a structured Borg log event and render it appropriately."""
        cleaned_line = line.rstrip()
        if not cleaned_line:
            return

        try:
            event = parse_borg_log_line(cleaned_line)
        except Exception:
            self._write(Text(cleaned_line, style="dim"))
            return

        if isinstance(event, ArchiveProgress):
            self._render_archive_progress(event)
        elif isinstance(event, ProgressPercent):
            self._render_progress_percent(event)
        elif isinstance(event, ProgressMessage):
            self._render_progress_message(event)
        elif isinstance(event, FileStatus):
            self.on_file_status(event.status, event.path)
        else:
            self._render_log_message(event)

    def on_stats(self, stats: dict[str, Any]) -> None:
        """Write a statistics block to the log."""
        self._write(Text("--- Statistics ---", style="bold #cba6f7"))
        for key, value in stats.items():
            self._write(f"  {key}: {value}")

    # -- Rendering helpers (mirroring DefaultOutputHandler) ------------------

    def _render_archive_progress(self, event: ArchiveProgress) -> None:
        if event.finished:
            self._write(Text("Archive write complete", style="bold green"))
            self._hide_progress()
            return

        details: list[str] = []
        if event.path:
            details.append(event.path)
        if event.nfiles is not None:
            details.append(f"{event.nfiles} files")

        size_parts: list[str] = []
        if event.original_size is not None:
            size_parts.append(f"orig {format_size_bytes(event.original_size)}")
        if event.compressed_size is not None:
            size_parts.append(f"comp {format_size_bytes(event.compressed_size)}")
        if event.deduplicated_size is not None:
            size_parts.append(f"dedup {format_size_bytes(event.deduplicated_size)}")
        if size_parts:
            details.append(" | ".join(size_parts))

        if details:
            text = Text()
            text.append("Backing up ", style="cyan")
            text.append(" | ".join(details))
            self._write(text)

    def _render_progress_message(self, event: ProgressMessage) -> None:
        if event.message:
            self._write(Text(event.message, style="cyan"))
            return
        if event.finished:
            operation = _humanize_msgid(event.msgid)
            text = Text()
            text.append("  ", style="green")
            text.append(f" {operation} complete")
            self._write(text)

    def _render_progress_percent(self, event: ProgressPercent) -> None:
        info_parts: list[str] = []
        if event.message:
            info_parts.append(event.message)
        if event.info:
            info_parts.extend(event.info)

        if event.total and event.total > 0 and not event.finished:
            bar = self._progress_bar
            if bar is not None:
                total = event.total
                progress = float(event.current or 0)

                def _show_and_update() -> None:
                    bar.display = True
                    bar.update(total=total, progress=progress)

                self._app.call_from_thread(_show_and_update)

        self.on_progress(
            current=event.current or 0,
            total=event.total or 0,
            info=" | ".join(info_parts) if info_parts else None,
        )

        if event.finished:
            operation = _humanize_msgid(event.msgid)
            text = Text()
            text.append("  ", style="green")
            text.append(f" {operation} complete")
            self._write(text)
            self._hide_progress()

    def _render_log_message(self, event: LogMessage) -> None:
        message = event.message.strip()
        if not message:
            return
        if event.name == "borg.output.show-rc" and message.startswith("terminating with success status"):
            return
        if event.name == "borg.output.stats" and set(message) == {"-"}:
            return
        self.on_log(event.levelname.lower(), message, logger=event.name, msgid=event.msgid)

    # -- OutputHandler protocol (streaming command rendering) ----------------

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Iterable[str],
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        """Stream a command's stderr output to the log, bracketed by status and success rulers."""
        self._reset_progress(indeterminate=True)
        self._show_progress()
        self._write(Text(f"--- {status} ---", style=f"bold {ruler_color}"))
        for line in log_stream:
            self.on_stderr(line)
        self._write(Text(f"--- {success_msg} ---", style="bold green"))
        self._hide_progress()

    @contextmanager
    def section(self, status: str, success_msg: str) -> Generator[None]:
        """Context manager that writes opening and closing ruler lines around a block of log output."""
        self._reset_progress(indeterminate=True)
        self._show_progress()
        self._write(Text(f"--- {status} ---", style="bold #74c7ec"))
        yield
        self._write(Text(f"--- {success_msg} ---", style="bold green"))
        self._hide_progress()


class DailyBackupScreen(Screen[None]):
    """Screen for running a daily backup on a selected repository."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        orchestrator: Orchestrator,
    ) -> None:
        super().__init__()
        self._orchestrator = orchestrator
        self._repos: list[BorgBoiRepo] = []
        self._backup_running = False

    @property
    def _is_offline(self) -> bool:
        return self._orchestrator.config.offline

    @override
    def compose(self) -> ComposeResult:
        """Build the screen layout with header, repo selector, S3 toggle, action buttons, and log widget."""
        yield Header()
        with Vertical(id="daily-backup-screen"):
            yield Static("Daily Backup", id="daily-backup-title")
            with Horizontal(id="daily-backup-controls"):
                yield Select[str](
                    [],
                    prompt="Select repository",
                    id="daily-backup-select",
                )
                yield Label("Sync to S3", id="daily-backup-s3-label")
                yield Switch(value=not self._is_offline, id="daily-backup-s3-switch", disabled=self._is_offline)
                yield Static("", id="daily-backup-spacer")
                yield Button("Start Backup", id="daily-backup-start", variant="primary", disabled=True)
                yield Button("Clear Log", id="daily-backup-clear", variant="default", disabled=True)
            yield ProgressBar(total=None, show_eta=False, id="daily-backup-progress")
            yield RichLog(id="daily-backup-log", markup=True, max_lines=5000)
        yield Footer()

    def on_mount(self) -> None:
        """Trigger repo loading when the screen is first mounted."""
        self.query_one("#daily-backup-select", Select).loading = True
        self._load_repos()

    @work(thread=True, exclusive=True, group="load-repos")
    def _load_repos(self) -> None:
        try:
            repos = self._orchestrator.list_repos()
            self.app.call_from_thread(self._populate_repos, repos)
        except Exception as e:
            self.app.call_from_thread(self._on_load_error, e)

    def _populate_repos(self, repos: list[BorgBoiRepo]) -> None:
        self._repos = repos
        select = self.query_one("#daily-backup-select", Select)
        select.set_options([(repo.name, repo.name) for repo in repos])
        select.loading = False
        self.query_one("#daily-backup-start", Button).disabled = False

    def _on_load_error(self, error: Exception) -> None:
        select = self.query_one("#daily-backup-select", Select)
        select.loading = False
        select.set_options([])
        self.query_one("#daily-backup-start", Button).disabled = True
        self.notify(str(error), severity="error", title="Failed to load repos")

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.query_one("#daily-backup-select", Select).disabled = not enabled
        switch = self.query_one("#daily-backup-s3-switch", Switch)
        if self._is_offline:
            switch.disabled = True
        else:
            switch.disabled = not enabled
        self.query_one("#daily-backup-start", Button).disabled = not enabled
        if not enabled:
            self.query_one("#daily-backup-clear", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Start Backup and Clear Log button presses."""
        if event.button.id == "daily-backup-clear":
            log = self.query_one("#daily-backup-log", RichLog)
            log.clear()
            self.query_one("#daily-backup-progress", ProgressBar).display = False
            event.button.disabled = True
            return
        if event.button.id != "daily-backup-start":
            return
        if self._backup_running:
            return

        select = self.query_one("#daily-backup-select", Select)
        if select.value is Select.NULL:
            self.notify("Please select a repository first.", severity="warning")
            return

        repo_name = str(select.value)
        repo = next((r for r in self._repos if r.name == repo_name), None)
        if repo is None:
            self.notify(f"Repository '{repo_name}' not found.", severity="error")
            return

        sync_to_s3 = self.query_one("#daily-backup-s3-switch", Switch).value
        log = self.query_one("#daily-backup-log", RichLog)
        log.clear()
        progress_bar = self.query_one("#daily-backup-progress", ProgressBar)

        self._backup_running = True
        self._set_controls_enabled(False)
        self._run_daily_backup(repo, sync_to_s3, log, progress_bar)

    @work(thread=True, exclusive=True)
    def _run_daily_backup(self, repo: BorgBoiRepo, sync_to_s3: bool, log: RichLog, progress_bar: ProgressBar) -> None:
        from borgboi.core.orchestrator import Orchestrator

        output_handler = TuiOutputHandler(self.app, log, progress_bar=progress_bar)

        try:
            orch = self._orchestrator
            orchestrator = Orchestrator(
                borg_client=orch.borg,
                storage=orch.storage,
                s3_client=orch.s3,
                config=orch.config,
                output_handler=output_handler,
            )
            orchestrator.daily_backup(repo, sync_to_s3=sync_to_s3)
        except Exception as e:
            output_handler.on_log("error", f"Error: {e}")
            self.app.call_from_thread(self._on_backup_failed, str(e))
            return
        finally:
            self.app.call_from_thread(setattr, progress_bar, "display", False)

        self.app.call_from_thread(self._on_backup_complete)

    def _on_backup_complete(self) -> None:
        self._backup_running = False
        self._set_controls_enabled(True)
        self.query_one("#daily-backup-clear", Button).disabled = False
        self.notify("Daily backup completed successfully.", severity="information")

    def _on_backup_failed(self, message: str) -> None:
        self._backup_running = False
        self._set_controls_enabled(True)
        self.query_one("#daily-backup-clear", Button).disabled = False
        self.notify(f"Backup failed: {message}", severity="error")

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Prevent the back action while a backup is in progress."""
        return not (action == "back" and self._backup_running)

    def action_back(self) -> None:
        """Pop this screen and return to the previous screen."""
        _ = self.app.pop_screen()
