"""BorgBoi TUI application."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar, override

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Sparkline, Static

from borgboi.lib.utils import format_last_backup, format_repo_size
from borgboi.storage.db import get_db_path
from borgboi.tui.config_screen import ConfigScreen
from borgboi.tui.daily_backup_progress import SQLiteDailyBackupProgressHistory
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from textual.screen import Screen

    from borgboi.config import Config
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo

SPARKLINE_DAYS = 14


class BorgBoiApp(App[None]):
    TITLE = "BorgBoi"  # type: ignore[mutable-override]
    CSS_PATH = "borgboi.tcss"  # type: ignore[mutable-override]

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "show_config", "Config"),
        Binding("e", "show_default_excludes", "Excludes"),
        Binding("b", "daily_backup", "Backup"),
    ]

    def __init__(
        self,
        config: Config | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._orchestrator = orchestrator
        self._main_screen: Screen[object] | None = None
        self._repos: list[BorgBoiRepo] = []
        self._repos_table: DataTable[str] | None = None

    @property
    def orchestrator(self) -> Orchestrator:
        """Return the shared orchestrator, constructing it lazily if not provided at init."""
        if self._orchestrator is None:
            from borgboi.core.orchestrator import Orchestrator

            self._orchestrator = Orchestrator(config=self._config)
        return self._orchestrator

    @override
    def compose(self) -> ComposeResult:
        """Build the main screen layout with header, repos table, sparkline, and footer."""
        yield Header()
        with Vertical(id="repos-section"):
            yield DataTable(id="repos-table")
        with Vertical(id="sparkline-section"):
            yield Sparkline(
                [0.0] * SPARKLINE_DAYS,
                summary_function=max,
                id="archive-sparkline",
            )
            with Horizontal(id="sparkline-x-labels"):
                for index in range(SPARKLINE_DAYS):
                    yield Static("", classes="sparkline-x-label", id=f"sparkline-x-label-{index}")
        yield Footer()

    def on_mount(self) -> None:
        """Initialise the repos table columns and trigger the initial data load."""
        self._main_screen = self.screen

        # Mode indicator in header subtitle
        if self._config is not None:
            self.sub_title = "Offline" if self._config.offline else "Online"

        # Titled borders for dashboard sections
        repos_section = self.query_one("#repos-section", Vertical)
        repos_section.border_title = "Repositories"

        sparkline_section = self.query_one("#sparkline-section", Vertical)
        sparkline_section.border_title = "Archive Activity"
        sparkline_section.border_subtitle = "Last 2 Weeks"

        # Simplified repo table
        self._repos_table = table = self.query_one("#repos-table", DataTable)
        table.add_columns("Name", "Hostname", "Last Archive", "Size")
        table.loading = True
        self._load_repos()
        self._load_sparkline_data()

    @work(thread=True, exclusive=True)
    def _load_repos(self) -> None:
        try:
            repos = self.orchestrator.list_repos()
            self.call_from_thread(self._populate_table, repos)
        except Exception as e:
            self.call_from_thread(self._on_load_error, e)

    def _populate_table(self, repos: list[BorgBoiRepo]) -> None:
        self._repos = repos
        table = self._repos_table
        if table is None:
            return
        table.clear()
        for repo in repos:
            table.add_row(
                repo.name,
                repo.hostname,
                format_last_backup(repo.last_backup),
                format_repo_size(repo.metadata),
            )
        table.loading = False

    def _on_load_error(self, error: Exception) -> None:
        table = self._repos_table
        if table is None:
            return
        table.loading = False
        self.notify(str(error), severity="error", title="Failed to load repos")

    @work(thread=True, exclusive=True, group="sparkline")
    def _load_sparkline_data(self) -> None:
        try:
            with SQLiteDailyBackupProgressHistory(
                db_path=get_db_path(self._config.borgboi_dir if self._config else None)
            ) as history:
                data = history.get_daily_archive_counts(SPARKLINE_DAYS)
            # Build x-labels from the same "today" snapshot used by the query
            today = datetime.now(UTC).date()
            labels = [(today - timedelta(days=SPARKLINE_DAYS - 1 - i)).strftime("%m/%d") for i in range(SPARKLINE_DAYS)]
            self.call_from_thread(self._update_sparkline, data, labels)
        except Exception:
            logger.debug("Failed to load sparkline data", exc_info=True)

    def _update_sparkline(self, data: list[float], labels: list[str]) -> None:
        self.query_one("#archive-sparkline", Sparkline).data = data
        for index, label in enumerate(labels):
            self.query_one(f"#sparkline-x-label-{index}", Static).update(label)

    def action_show_config(self) -> None:
        """Push the configuration viewer screen."""
        if self.screen is not self._main_screen:
            return
        _ = self.push_screen(ConfigScreen(config=self._config))

    def action_refresh(self) -> None:
        """Reload the repos table and sparkline from storage."""
        if self.screen is not self._main_screen:
            return
        if self._repos_table is None:
            return
        self._repos_table.loading = True
        self._load_repos()
        self._load_sparkline_data()

    def action_show_default_excludes(self) -> None:
        """Push the excludes viewer screen."""
        if self.screen is not self._main_screen:
            return
        _ = self.push_screen(DefaultExcludesScreen(config=self._config, repos=self._repos))

    def action_daily_backup(self) -> None:
        """Push the daily backup screen."""
        if self.screen is not self._main_screen:
            return
        _ = self.push_screen(DailyBackupScreen(orchestrator=self.orchestrator))
