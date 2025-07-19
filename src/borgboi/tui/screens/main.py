"""Main screen for the TUI."""

from __future__ import annotations

import asyncio
from typing import ClassVar, override

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, LoadingIndicator

from borgboi.clients import dynamodb
from borgboi.models import BorgBoiRepo
from borgboi.tui.types import RepoSelected
from borgboi.tui.widgets.repo_list import RepoListWidget


class MainScreen(Screen[None]):
    """Main screen showing repository list."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("h", "home", "Home"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Label("Loading repositories...", id="loading-label"),
            LoadingIndicator(id="loading-indicator"),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        _ = self.load_repositories()

    def action_home(self) -> None:
        """Navigate back to home screen."""
        _ = self.app.pop_screen()

    @work(exclusive=True)
    async def load_repositories(self) -> None:
        """Load repositories in the background."""

        def get_repos() -> list[BorgBoiRepo]:
            # Use dynamodb client directly since orchestrator.list_repos doesn't return data
            return dynamodb.get_all_repos()

        try:
            # Run in thread to avoid blocking
            repos = await asyncio.get_event_loop().run_in_executor(None, get_repos)

            # Update UI with loaded repos
            container = self.query_one("#main-container", Container)
            await container.remove_children()

            if repos:
                await container.mount(
                    Label("BorgBoi Repositories", classes="title"),
                    Label("Press 's' to sort by size, 'd' for date, 'n' for name, 'h' for home", classes="help-text"),
                    RepoListWidget(repos),
                )
                # Focus the DataTable so arrow keys work immediately
                _ = self.query_one(DataTable).focus()
            else:
                await container.mount(
                    Label("No repositories found. Use 'borgboi create-repo' to create one.", classes="warning")
                )
        except Exception as e:
            container = self.query_one("#main-container", Container)
            await container.remove_children()
            await container.mount(Label(f"Error loading repositories: {e!s}", classes="error"))

    @on(RepoSelected)
    def on_repo_selected(self, message: RepoSelected) -> None:
        """Handle repository selection."""
        from borgboi.tui.screens.detail import DetailScreen

        _ = self.app.push_screen(DetailScreen(message.repo))
