"""Detail screen for the TUI."""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header

from borgboi.models import BorgBoiRepo
from borgboi.tui.widgets.repo_detail import RepoDetailWidget


class DetailScreen(Screen[None]):
    """Detail screen for a specific repository."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("h", "home", "Home"),
    ]

    def __init__(self, repo: BorgBoiRepo) -> None:
        super().__init__()
        self.repo: BorgBoiRepo = repo

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(RepoDetailWidget(), id="detail-container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        detail_widget = self.query_one(RepoDetailWidget)
        detail_widget.repo = self.repo

    def action_home(self) -> None:
        """Navigate back to home screen."""
        _ = self.app.pop_screen()
        _ = self.app.pop_screen()  # Pop twice to get back to home
