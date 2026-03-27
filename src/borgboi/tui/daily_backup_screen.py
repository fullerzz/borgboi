"""Daily backup screen for the BorgBoi TUI."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Generator, Iterable
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
from borgboi.tui.daily_backup_progress import (
    DEFAULT_STAGE_DURATION_MS,
    DEFAULT_UNKNOWN_STAGE_DURATION_MS,
    DailyBackupProgressHistory,
    SQLiteDailyBackupProgressHistory,
)

if TYPE_CHECKING:
    from textual.app import App

    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


class TuiOutputHandler:
    """Output handler that writes to a Textual RichLog widget.

    All write operations go through ``app.call_from_thread`` so this handler
    is safe to use from a ``@work(thread=True)`` worker.
    """

    _COMMAND_STEP_IDS: ClassVar[dict[str, str]] = {
        "Creating new archive": "create",
        "Syncing repo with S3 bucket": "sync",
    }
    _LOG_STEP_START_IDS: ClassVar[dict[str, str]] = {
        "Pruning old backups...": "prune",
        "Compacting repository...": "compact",
    }
    _LOG_STEP_COMPLETE_IDS: ClassVar[dict[str, str]] = {
        "Pruning completed": "prune",
        "Compacting completed": "compact",
    }

    def __init__(
        self,
        app: App[Any],
        log: RichLog,
        progress_bar: ProgressBar | None = None,
        *,
        steps: list[str] | None = None,
        progress_history: DailyBackupProgressHistory | None = None,
        repo_name: str | None = None,
        sync_enabled: bool = False,
        now_monotonic: Callable[[], float] | None = None,
        stage_ticker_interval: float = 0.2,
        enable_stage_ticker: bool = True,
    ) -> None:
        self._app = app
        self._log = log
        self._progress_bar = progress_bar
        self._progress_history = progress_history
        self._repo_name = repo_name
        self._sync_enabled = sync_enabled
        self._command_progress_active = False
        self._steps = steps or ["command"]
        self._completed_steps = 0
        self._active_step: str | None = None
        self._active_step_started_at: float | None = None
        self._active_step_reported_progress = 0.0
        self._step_state_lock = threading.Lock()
        self._stage_ticker_interval = stage_ticker_interval
        self._enable_stage_ticker = enable_stage_ticker
        self._now_monotonic = now_monotonic or time.monotonic
        self._stage_ticker_stop: threading.Event | None = None
        self._stage_ticker_thread: threading.Thread | None = None
        self._last_overall_progress = 0.0
        self._step_duration_predictions = self._resolve_step_duration_predictions()
        self._step_ranges = self._build_step_ranges()

    def _write(self, text: str | Text) -> None:
        self._app.call_from_thread(self._log.write, text)

    def close(self) -> None:
        """Release any background resources used for stage progress updates."""
        self._stop_stage_ticker()

    # -- ProgressBar helpers (thread-safe) ------------------------------------

    def _update_progress_bar(self, *, total: int, progress: float) -> None:
        if self._progress_bar is None:
            return
        bar = self._progress_bar

        def _do_update() -> None:
            bar.update(total=total, progress=progress)

        self._app.call_from_thread(_do_update)

    def _update_overall_progress(self, progress: float) -> None:
        clamped_progress = min(max(progress, 0.0), 100.0)
        with self._step_state_lock:
            if clamped_progress <= self._last_overall_progress:
                return
            self._last_overall_progress = clamped_progress
        self._update_progress_bar(total=100, progress=clamped_progress)

    def _resolve_step_duration_predictions(self) -> dict[str, float]:
        predicted_durations: dict[str, float] = {}
        if self._progress_history is not None and self._repo_name is not None:
            try:
                predicted_durations = self._progress_history.get_stage_durations(self._repo_name, self._steps)
            except Exception:
                predicted_durations = {}

        return {
            step_id: max(
                predicted_durations.get(
                    step_id, DEFAULT_STAGE_DURATION_MS.get(step_id, DEFAULT_UNKNOWN_STAGE_DURATION_MS)
                ),
                1.0,
            )
            for step_id in self._steps
        }

    def _build_step_ranges(self) -> dict[str, tuple[float, float]]:
        if not self._steps:
            return {}

        total_duration = sum(self._step_duration_predictions.values()) or float(len(self._steps))
        cumulative_progress = 0.0
        ranges: dict[str, tuple[float, float]] = {}
        for index, step_id in enumerate(self._steps):
            if index == len(self._steps) - 1:
                step_span = max(100.0 - cumulative_progress, 0.0)
            else:
                step_span = (self._step_duration_predictions[step_id] / total_duration) * 100.0
            ranges[step_id] = (cumulative_progress, step_span)
            cumulative_progress += step_span
        return ranges

    def _get_step_range(self, step_id: str) -> tuple[float, float]:
        if step_id in self._step_ranges:
            return self._step_ranges[step_id]

        step_index = self._steps.index(step_id)
        fallback_span = 100.0 / len(self._steps)
        return (step_index * fallback_span, fallback_span)

    def _next_step(self) -> str | None:
        if self._completed_steps >= len(self._steps):
            return None
        return self._steps[self._completed_steps]

    def _start_stage_ticker(self) -> None:
        if not self._enable_stage_ticker:
            return

        self._stop_stage_ticker()
        stop_event = threading.Event()

        def _run() -> None:
            while not stop_event.wait(self._stage_ticker_interval):
                self._advance_active_step_from_timing()

        ticker = threading.Thread(target=_run, name="daily-backup-progress", daemon=True)
        with self._step_state_lock:
            self._stage_ticker_stop = stop_event
            self._stage_ticker_thread = ticker
        ticker.start()

    def _stop_stage_ticker(self) -> None:
        stop_event: threading.Event | None = None
        ticker: threading.Thread | None = None
        with self._step_state_lock:
            stop_event = self._stage_ticker_stop
            ticker = self._stage_ticker_thread
            self._stage_ticker_stop = None
            self._stage_ticker_thread = None

        if stop_event is not None:
            stop_event.set()
        if ticker is not None and ticker.is_alive() and ticker is not threading.current_thread():
            ticker.join(timeout=0.1)

    def _start_step(self, step_id: str | None = None) -> None:
        resolved_step = step_id if step_id in self._steps else self._next_step()
        if resolved_step is None:
            return

        step_index = self._steps.index(resolved_step)
        if step_index < self._completed_steps:
            return

        with self._step_state_lock:
            if self._active_step == resolved_step and self._active_step_started_at is not None:
                return
            self._active_step = resolved_step
            self._active_step_started_at = self._now_monotonic()
            self._active_step_reported_progress = 0.0

        self._start_stage_ticker()
        step_start, _ = self._get_step_range(resolved_step)
        self._update_overall_progress(step_start)

    def _update_step_progress(self, progress_percent: float, *, is_reported: bool = True) -> None:
        if not self._steps:
            return

        if self._active_step is None:
            self._start_step()

        with self._step_state_lock:
            active_step = self._active_step
            if active_step is None:
                return

        step_index = self._steps.index(active_step)
        if step_index < self._completed_steps:
            return

        bounded_percent = min(max(progress_percent, 0.0), 99.0)
        if is_reported:
            with self._step_state_lock:
                self._active_step_reported_progress = max(self._active_step_reported_progress, bounded_percent)
                bounded_percent = self._active_step_reported_progress

        step_start, step_span = self._get_step_range(active_step)
        overall_progress = step_start + (step_span * (bounded_percent / 100.0))
        self._update_overall_progress(overall_progress)

    def _advance_active_step_from_timing(self) -> None:
        with self._step_state_lock:
            active_step = self._active_step
            active_step_started_at = self._active_step_started_at
            reported_progress = self._active_step_reported_progress

        if active_step is None or active_step_started_at is None:
            return

        predicted_duration_ms = self._step_duration_predictions.get(active_step, 1.0)
        elapsed_ms = max((self._now_monotonic() - active_step_started_at) * 1000.0, 0.0)
        estimated_progress = min((elapsed_ms / predicted_duration_ms) * 100.0, 97.0)
        self._update_step_progress(max(estimated_progress, reported_progress), is_reported=False)

    def _complete_step(self, step_id: str | None = None) -> None:
        resolved_step = step_id if step_id in self._steps else self._active_step or self._next_step()
        if resolved_step is None:
            return

        step_index = self._steps.index(resolved_step)
        if step_index < self._completed_steps:
            return

        duration_ms: float | None = None
        with self._step_state_lock:
            if self._active_step == resolved_step and self._active_step_started_at is not None:
                duration_ms = max((self._now_monotonic() - self._active_step_started_at) * 1000.0, 1.0)

        self._stop_stage_ticker()
        step_start, step_span = self._get_step_range(resolved_step)
        overall_progress = step_start + step_span
        self._update_overall_progress(overall_progress)
        self._completed_steps = max(self._completed_steps, step_index + 1)
        if duration_ms is not None and self._progress_history is not None and self._repo_name is not None:
            self._progress_history.record_stage_timing(
                self._repo_name,
                resolved_step,
                duration_ms,
                sync_enabled=self._sync_enabled,
                succeeded=True,
            )

        with self._step_state_lock:
            self._active_step_started_at = None
            self._active_step_reported_progress = 0.0
            self._active_step = None

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
        step_id = self._LOG_STEP_START_IDS.get(message)
        if step_id is not None:
            self._start_step(step_id)

        completed_step_id = self._LOG_STEP_COMPLETE_IDS.get(message)
        if completed_step_id is not None:
            self._complete_step(completed_step_id)

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

        if event.total and event.total > 0:
            step_percent = (float(event.current or 0) / event.total) * 100.0
            self._update_step_progress(step_percent)
        elif not event.finished:
            self._start_step()

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
        self._command_progress_active = True
        self._start_step(self._COMMAND_STEP_IDS.get(status))
        try:
            self._write(Text(f"--- {status} ---", style=f"bold {ruler_color}"))
            for line in log_stream:
                self.on_stderr(line)
            self._complete_step(self._COMMAND_STEP_IDS.get(status))
            self._write(Text(f"--- {success_msg} ---", style="bold green"))
        finally:
            self._command_progress_active = False

    @contextmanager
    def section(self, status: str, success_msg: str) -> Generator[None]:
        """Context manager that writes opening and closing ruler lines around a block of log output."""
        self._command_progress_active = True
        self._start_step()
        self._write(Text(f"--- {status} ---", style="bold #74c7ec"))
        try:
            yield
        finally:
            self._complete_step()
            self._write(Text(f"--- {success_msg} ---", style="bold green"))
            self._command_progress_active = False


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
                yield Button("Start Backup", id="daily-backup-start", variant="primary", disabled=True)
                yield Button("Clear Log", id="daily-backup-clear", variant="default", disabled=True)
                with Vertical(id="daily-backup-progress-wrapper"):
                    yield ProgressBar(total=100, show_eta=False, id="daily-backup-progress")
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
            progress_bar = self.query_one("#daily-backup-progress", ProgressBar)
            progress_bar.update(total=100, progress=0)
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
        progress_bar.update(total=100, progress=0)

        self._backup_running = True
        self._set_controls_enabled(False)
        self._run_daily_backup(repo, sync_to_s3, log, progress_bar)

    @work(thread=True, exclusive=True)
    def _run_daily_backup(self, repo: BorgBoiRepo, sync_to_s3: bool, log: RichLog, progress_bar: ProgressBar) -> None:
        from borgboi.core.orchestrator import Orchestrator

        orch = self._orchestrator
        steps = ["create", "prune", "compact"]
        sync_enabled = sync_to_s3 and not orch.config.offline and orch.s3 is not None
        if sync_enabled:
            steps.append("sync")

        progress_history: SQLiteDailyBackupProgressHistory | None = None
        progress_history_error: str | None = None
        try:
            progress_history = SQLiteDailyBackupProgressHistory()
        except Exception as exc:
            progress_history_error = str(exc)

        output_handler = TuiOutputHandler(
            self.app,
            log,
            progress_bar=progress_bar,
            steps=steps,
            progress_history=progress_history,
            repo_name=repo.name,
            sync_enabled=sync_enabled,
        )
        if progress_history_error is not None:
            output_handler.on_log(
                "warning",
                f"Progress history unavailable; using default stage estimates ({progress_history_error})",
            )

        try:
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
            output_handler.close()
            if progress_history is not None:
                progress_history.close()

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
