"""BorgBoi TUI application."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header

from borgboi.lib.utils import format_last_backup, format_repo_size
from borgboi.tui.config_panel import ConfigPanel
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen

if TYPE_CHECKING:
    from textual.screen import Screen

    from borgboi.config import Config
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


class BorgBoiApp(App[None]):
    TITLE = "BorgBoi"  # type: ignore[mutable-override]  # ty: ignore[unused-ignore-comment]
    CSS_PATH = "borgboi.tcss"  # type: ignore[mutable-override]  # ty: ignore[unused-ignore-comment]

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "toggle_config", "Config"),
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
        """Build the main screen layout with header, repos table, config panel, and footer."""
        yield Header()
        with Horizontal(id="main-content"):
            yield DataTable(id="repos-table")
            yield ConfigPanel(config=self._config)
        yield Footer()

    def on_mount(self) -> None:
        """Initialise the repos table columns and trigger the initial data load."""
        self._main_screen = self.screen
        self._repos_table = table = self.query_one("#repos-table", DataTable)
        table.add_columns(
            "Name",
            "Local Path",
            "Hostname",
            "Last Archive",
            "Size",
            "Backup Target",
        )
        table.loading = True
        self._load_repos()

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
                repo.path,
                repo.hostname,
                format_last_backup(repo.last_backup),
                format_repo_size(repo.metadata),
                repo.backup_target,
            )
        table.loading = False

    def _on_load_error(self, error: Exception) -> None:
        table = self._repos_table
        if table is None:
            return
        table.loading = False
        self.notify(str(error), severity="error", title="Failed to load repos")

    def action_toggle_config(self) -> None:
        """Toggle visibility of the config panel sidebar."""
        if self.screen is not self._main_screen:
            return
        panel = self.query_one("#config-panel", ConfigPanel)
        panel.display = not panel.display

    def action_refresh(self) -> None:
        """Reload the repos table from storage."""
        if self.screen is not self._main_screen:
            return
        if self._repos_table is None:
            return
        self._repos_table.loading = True
        self._load_repos()

    def action_show_default_excludes(self) -> None:
        """Push the excludes viewer screen."""
        _ = self.push_screen(DefaultExcludesScreen(config=self._config, repos=self._repos))

    def action_daily_backup(self) -> None:
        """Push the daily backup screen."""
        if self.screen is not self._main_screen:
            return
        _ = self.push_screen(DailyBackupScreen(orchestrator=self.orchestrator))
