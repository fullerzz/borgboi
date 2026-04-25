"""Daily backup screen for the BorgBoi TUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, override

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ProgressBar, RichLog, Select, Static, Switch

from borgboi.core.logging import get_logger
from borgboi.tui.features.daily_backup.output import TuiOutputHandler
from borgboi.tui.features.daily_backup.progress import SQLiteDailyBackupProgressHistory

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


class DailyBackupScreen(Screen[None]):
    """Screen for running a daily backup on a selected repository."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        orchestrator: Orchestrator,
        on_back_after_success: Callable[[], None] | None = None,
        selected_repo_name: str | None = None,
    ) -> None:
        super().__init__()
        self._orchestrator = orchestrator
        self._on_back_after_success = on_back_after_success
        self._selected_repo_name = selected_repo_name
        self._repos: list[BorgBoiRepo] = []
        self._backup_running = False
        self._backup_completed = False
        logger.debug("DailyBackupScreen initialized", offline=orchestrator.config.offline)

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
        logger.debug("DailyBackupScreen mounted, loading repositories")
        self.query_one("#daily-backup-select", Select).loading = True
        self._load_repos()

    @work(thread=True, exclusive=True, group="load-repos")
    def _load_repos(self) -> None:
        logger.debug("Loading repositories in background thread")
        try:
            repos = self._orchestrator.list_repos()
            logger.info("Repositories loaded for backup screen", count=len(repos))
            self.app.call_from_thread(self._populate_repos, repos)
        except Exception as e:
            logger.exception("Failed to load repositories", error=str(e))
            self.app.call_from_thread(self._on_load_error, e)

    def _populate_repos(self, repos: list[BorgBoiRepo]) -> None:
        self._repos = repos
        select = self.query_one("#daily-backup-select", Select)
        select.set_options([(repo.name, repo.name) for repo in repos])
        if self._selected_repo_name and any(r.name == self._selected_repo_name for r in repos):
            select.value = self._selected_repo_name
        select.loading = False
        self.query_one("#daily-backup-start", Button).disabled = False
        logger.debug("Repository selector populated", options=len(repos))

    def _on_load_error(self, error: Exception) -> None:
        select = self.query_one("#daily-backup-select", Select)
        select.loading = False
        select.set_options([])
        self.query_one("#daily-backup-start", Button).disabled = True
        self.notify(str(error), severity="error", title="Failed to load repos")
        logger.error("Repository loading error in backup screen", error=str(error))

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
            logger.debug("Log cleared")
            return
        if event.button.id != "daily-backup-start":
            return
        if self._backup_running:
            logger.warning("Backup already running, ignoring start request")
            return

        select = self.query_one("#daily-backup-select", Select)
        if select.value is Select.NULL:
            self.notify("Please select a repository first.", severity="warning")
            return

        repo_name = str(select.value)
        repo = next((r for r in self._repos if r.name == repo_name), None)
        if repo is None:
            self.notify(f"Repository '{repo_name}' not found.", severity="error")
            logger.error("Selected repository not found", repo_name=repo_name)
            return

        sync_to_s3 = self.query_one("#daily-backup-s3-switch", Switch).value
        log = self.query_one("#daily-backup-log", RichLog)
        log.clear()
        progress_bar = self.query_one("#daily-backup-progress", ProgressBar)
        progress_bar.update(total=100, progress=0)

        self._backup_running = True
        self._set_controls_enabled(False)
        logger.info("Starting daily backup", repo=repo_name, sync_to_s3=sync_to_s3)
        self._run_daily_backup(repo, sync_to_s3, log, progress_bar)

    @work(thread=True, exclusive=True)
    def _run_daily_backup(self, repo: BorgBoiRepo, sync_to_s3: bool, log: RichLog, progress_bar: ProgressBar) -> None:
        from borgboi.core.orchestrator import Orchestrator

        orch = self._orchestrator
        steps = ["create", "prune", "compact"]
        sync_enabled = sync_to_s3 and not orch.config.offline and orch.s3 is not None
        if sync_enabled:
            steps.append("sync")

        logger.debug("Preparing backup run", repo=repo.name, steps=steps, sync_enabled=sync_enabled)

        progress_history: SQLiteDailyBackupProgressHistory | None = None
        progress_history_error: str | None = None
        try:
            progress_history = SQLiteDailyBackupProgressHistory()
            logger.debug("Progress history initialized")
        except Exception as exc:
            progress_history_error = str(exc)
            logger.warning("Failed to initialize progress history", error=str(exc))

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
            logger.info("Executing daily backup", repo=repo.name, sync_to_s3=sync_to_s3)
            orchestrator = Orchestrator(
                borg_client=orch.borg,
                storage=orch.storage,
                s3_client=orch.s3,
                config=orch.config,
                output_handler=output_handler,
            )
            orchestrator.daily_backup(repo, sync_to_s3=sync_to_s3)
            logger.info("Daily backup completed successfully", repo=repo.name)
        except Exception as e:
            logger.exception("Daily backup failed", repo=repo.name, error=str(e))
            output_handler.on_log("error", f"Error: {e}")
            self.app.call_from_thread(self._on_backup_failed, str(e))
            return
        finally:
            output_handler.close()
            if progress_history is not None:
                progress_history.close()

        self.app.call_from_thread(self._on_backup_complete)

    def _on_backup_complete(self) -> None:
        self._backup_completed = True
        self._backup_running = False
        self._set_controls_enabled(True)
        self.query_one("#daily-backup-clear", Button).disabled = False
        self.notify("Daily backup completed successfully.", severity="information")
        logger.info("Backup completion UI updated")

    def _on_backup_failed(self, message: str) -> None:
        self._backup_running = False
        self._set_controls_enabled(True)
        self.query_one("#daily-backup-clear", Button).disabled = False
        self.notify(f"Backup failed: {message}", severity="error")
        logger.error("Backup failure UI updated", error_message=message)

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Prevent the back action while a backup is in progress."""
        return not (action == "back" and self._backup_running)

    def action_back(self) -> None:
        """Pop this screen and return to the previous screen."""
        logger.debug("Closing daily backup screen", backup_completed=self._backup_completed)
        _ = self.app.pop_screen()
        if self._backup_completed and self._on_back_after_success is not None:
            self._on_back_after_success()
