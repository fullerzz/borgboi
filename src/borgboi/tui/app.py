"""BorgBoi TUI application."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Footer, Header

from borgboi.lib.utils import format_last_backup, format_repo_size

if TYPE_CHECKING:
    from borgboi.config import Config
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


class BorgBoiApp(App[None]):
    TITLE = "BorgBoi"  # type: ignore[mutable-override]  # ty: ignore[unused-ignore-comment]
    CSS_PATH = "borgboi.tcss"  # type: ignore[mutable-override]  # ty: ignore[unused-ignore-comment]

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(
        self,
        config: Config | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._orchestrator = orchestrator

    @property
    def orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            from borgboi.core.orchestrator import Orchestrator

            self._orchestrator = Orchestrator(config=self._config)
        return self._orchestrator

    @override
    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="repos-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#repos-table", DataTable)
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
        table = self.query_one("#repos-table", DataTable)
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
        table = self.query_one("#repos-table", DataTable)
        table.loading = False
        self.notify(str(error), severity="error", title="Failed to load repos")

    def action_refresh(self) -> None:
        table = self.query_one("#repos-table", DataTable)
        table.loading = True
        self._load_repos()
