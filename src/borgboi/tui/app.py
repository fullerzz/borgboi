"""Main TUI application for borgboi."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType
from textual.types import CSSPathType

from borgboi.tui.screens.detail import DetailScreen
from borgboi.tui.screens.home import HomeScreen
from borgboi.tui.screens.main import MainScreen
from borgboi.tui.widgets.repo_detail import RepoDetailWidget


class BorgBoiApp(App[None]):
    """Main TUI application for borgboi."""

    CSS_PATH: ClassVar[CSSPathType | None] = "borgboi/tui/styles/main.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def on_mount(self) -> None:
        """Called when app starts."""
        self.theme = "catppuccin-mocha"  # pyright: ignore[reportUnannotatedClassAttribute]
        _ = self.push_screen(HomeScreen())

    def action_refresh(self) -> None:
        """Refresh the current screen."""
        # Get the current screen and trigger its refresh
        if isinstance(self.screen, MainScreen):
            _ = self.screen.load_repositories()
        elif isinstance(self.screen, DetailScreen):
            detail_widget = self.screen.query_one(RepoDetailWidget)
            _ = detail_widget.load_archives()


def run_tui() -> None:
    """Run the TUI application."""
    app = BorgBoiApp()
    app.run()


if __name__ == "__main__":
    run_tui()
