"""Home screen for the TUI."""

from __future__ import annotations

from typing import ClassVar, override

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView


class HomeScreen(Screen[None]):
    """Home screen with command list."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "select_command", "Select"),
        Binding("l", "list_repos", "List Repos"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with Container(id="home-container"):
            yield Label("BorgBoi - Terminal User Interface", classes="title")
            yield Label("Select a command to execute:", classes="subtitle")

            with ScrollableContainer(id="commands-container"):
                yield ListView(
                    ListItem(Label("📦 create-repo - Create a new Borg repository"), id="create-repo"),
                    ListItem(Label("📝 list-repos - List all BorgBoi repositories"), id="list-repos"),
                    ListItem(Label("📅 daily-backup - Perform daily backup operation"), id="daily-backup"),
                    ListItem(Label("📋 list-archives - List archives in a repository"), id="list-archives"),
                    ListItem(
                        Label("📄 list-archive-contents - List contents of an archive"), id="list-archive-contents"
                    ),
                    ListItem(Label("🔍 get-repo - Get repository by name or path"), id="get-repo"),
                    ListItem(Label("🔑 export-repo-key - Extract repository key"), id="export-repo-key"),
                    ListItem(Label("ℹ️ repo-info - Show repository information"), id="repo-info"),
                    ListItem(Label("📤 extract-archive - Extract archive to current directory"), id="extract-archive"),
                    ListItem(Label("🗑️ delete-archive - Delete an archive"), id="delete-archive"),
                    ListItem(Label("🗂️ delete-repo - Delete a repository"), id="delete-repo"),
                    ListItem(Label("➕ append-excludes - Add exclusion pattern"), id="append-excludes"),
                    ListItem(Label("✏️ modify-excludes - Modify exclusion patterns"), id="modify-excludes"),
                    ListItem(Label("🔄 restore-repo - Restore repository from S3"), id="restore-repo"),
                    ListItem(Label("➡️ Go to Repository List"), id="go-to-repos"),
                    id="command-list",
                )

            with Container(id="help-container"):
                yield Label(
                    "Use arrow keys to navigate, Enter to select, 'l' for quick repo list access", classes="help-text"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Focus the command list so arrow keys work immediately
        _ = self.query_one("#command-list", ListView).focus()

    def action_select_command(self) -> None:
        """Handle command selection."""
        list_view = self.query_one("#command-list", ListView)
        if list_view.highlighted_child:
            command_id = list_view.highlighted_child.id
            if command_id == "go-to-repos" or command_id == "list-repos":
                self.action_list_repos()
            else:
                self.app.notify(f"Command '{command_id}' selected. CLI implementation would be called here.")

    def action_list_repos(self) -> None:
        """Navigate to repository list screen."""
        from borgboi.tui.screens.main import MainScreen

        _ = self.app.push_screen(MainScreen())

    @on(ListView.Selected)
    def on_list_view_selected(self, message: ListView.Selected) -> None:
        """Handle ListView selection."""
        if message.item.id == "go-to-repos" or message.item.id == "list-repos":
            self.action_list_repos()
        else:
            self.app.notify(f"Command '{message.item.id}' selected. CLI implementation would be called here.")
