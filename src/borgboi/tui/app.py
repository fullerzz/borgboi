"""BorgBoi TUI application."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar, override

from opentelemetry import trace
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Sparkline, Static

from borgboi.core.logging import get_logger
from borgboi.core.telemetry import set_span_attributes
from borgboi.lib.utils import format_last_backup, format_repo_size
from borgboi.storage.db import get_db_path
from borgboi.tui.config_screen import ConfigScreen
from borgboi.tui.daily_backup_progress import SQLiteDailyBackupProgressHistory
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen
from borgboi.tui.repo_info_screen import RepoInfoScreen
from borgboi.tui.telemetry import capture_span

logger = get_logger(__name__)

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
        Binding("enter", "show_repo_info", "Repo Info"),
        Binding("i", "show_repo_info", "Repo Info"),
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

    @capture_span("tui.app.mount")
    def on_mount(self) -> None:
        """Initialise the repos table columns and trigger the initial data load."""
        set_span_attributes(
            trace.get_current_span(),
            {
                "borgboi.mode.offline": self._config.offline if self._config else None,
                "borgboi.ui.theme": self._config.ui.theme if self._config else None,
            },
        )
        logger.info("TUI app mounted", offline=self._config.offline if self._config else None)
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
        table.cursor_type = "row"
        table.add_columns("Name", "Hostname", "Last Archive", "Size")
        table.loading = True
        self._load_repos()
        self._load_sparkline_data()

    @work(thread=True, exclusive=True)
    @capture_span("tui.load_repos")
    def _load_repos(self) -> None:
        logger.debug("Loading repositories for TUI dashboard")
        try:
            repos = self.orchestrator.list_repos()
            set_span_attributes(trace.get_current_span(), {"borgboi.repo.count": len(repos)})
            logger.info("Repositories loaded", count=len(repos))
            self.call_from_thread(self._populate_table, repos)
        except Exception as e:
            logger.exception("Failed to load repositories", error=str(e))
            self.call_from_thread(self._on_load_error, e)

    def _populate_table(self, repos: list[BorgBoiRepo]) -> None:
        self._repos = repos
        table = self._repos_table
        if table is None:
            logger.warning("Repos table not available for population")
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
        logger.debug("Repository table populated", row_count=len(repos))

    def _on_load_error(self, error: Exception) -> None:
        table = self._repos_table
        if table is None:
            return
        table.loading = False
        self.notify(str(error), severity="error", title="Failed to load repos")
        logger.error("Repository loading error notification shown", error=str(error))

    def _selected_repo(self) -> BorgBoiRepo | None:
        """Return the currently highlighted repository in the dashboard table."""
        table = self._repos_table
        if table is None or table.row_count == 0 or not self._repos:
            return None

        row_index = table.cursor_row
        if not table.is_valid_row_index(row_index):
            return None
        if row_index >= len(self._repos):
            return None
        return self._repos[row_index]

    @work(thread=True, exclusive=True, group="sparkline")
    @capture_span("tui.load_sparkline")
    def _load_sparkline_data(self) -> None:
        logger.debug("Loading sparkline data")
        try:
            today = datetime.now(UTC).date()
            with SQLiteDailyBackupProgressHistory(
                db_path=get_db_path(self._config.borgboi_dir if self._config else None)
            ) as history:
                data = history.get_daily_archive_counts(SPARKLINE_DAYS)
            labels = [(today - timedelta(days=SPARKLINE_DAYS - 1 - i)).strftime("%m/%d") for i in range(SPARKLINE_DAYS)]
            set_span_attributes(trace.get_current_span(), {"borgboi.sparkline.points": len(data)})
            logger.debug("Sparkline data loaded", data_points=len(data))
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
        logger.debug("Opening config screen")
        _ = self.push_screen(ConfigScreen(config=self._config))

    def action_refresh(self) -> None:
        """Reload the repos table and sparkline from storage."""
        if self.screen is not self._main_screen:
            return
        logger.info("Refreshing dashboard")
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        """Reload the dashboard data shown on the main screen."""
        if self._repos_table is None:
            return
        self._repos_table.loading = True
        self._load_repos()
        self._load_sparkline_data()

    def action_show_default_excludes(self) -> None:
        """Push the excludes viewer screen."""
        if self.screen is not self._main_screen:
            return
        logger.debug("Opening excludes screen", repo_count=len(self._repos))
        _ = self.push_screen(DefaultExcludesScreen(config=self._config, repos=self._repos))

    def action_show_repo_info(self) -> None:
        """Push the selected repository detail screen."""
        if self.screen is not self._main_screen:
            return

        repo = self._selected_repo()
        if repo is None:
            self.notify("No repository selected", severity="warning", title="Repo Info")
            logger.warning("Repo info requested with no selected repository")
            return

        logger.debug("Opening repo info screen", repo_name=repo.name, repo_path=repo.path)
        _ = self.push_screen(RepoInfoScreen(repo=repo, config=self._config, orchestrator=self.orchestrator))

    def action_daily_backup(self) -> None:
        """Push the daily backup screen."""
        if self.screen is not self._main_screen:
            return
        logger.info("Opening daily backup screen")
        _ = self.push_screen(
            DailyBackupScreen(
                orchestrator=self.orchestrator,
                on_back_after_success=self._refresh_dashboard,
            )
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open repo details when the dashboard table row is activated."""
        if event.data_table.id != "repos-table":
            return
        self.action_show_repo_info()
