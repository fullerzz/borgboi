"""Terminal User Interface for borgboi using Textual."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, override

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.types import CSSPathType
from textual.widgets import Button, DataTable, Footer, Header, Label, ListItem, ListView, LoadingIndicator, Static

from borgboi import orchestrator
from borgboi.clients import borg, dynamodb
from borgboi.clients.borg import RepoArchive
from borgboi.models import BorgBoiRepo


class SortOrder(Enum):
    """Sort order enumeration."""

    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    SIZE_ASC = "size_asc"
    SIZE_DESC = "size_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"


class RepoSelected(Message):
    """Message sent when a repository is selected."""

    def __init__(self, repo: BorgBoiRepo) -> None:
        self.repo: BorgBoiRepo = repo
        super().__init__()


class RepoListWidget(Static):
    """Widget to display the list of repositories."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("s", "sort_by_size", "Sort by Size"),
        Binding("d", "sort_by_date", "Sort by Date"),
        Binding("n", "sort_by_name", "Sort by Name"),
    ]

    def __init__(self, repos: list[BorgBoiRepo]) -> None:
        super().__init__()
        self.repos: list[BorgBoiRepo] = repos
        self.current_sort: SortOrder = SortOrder.NAME_ASC

    def _get_repo_size_for_sort(self, repo: BorgBoiRepo) -> float:
        """Get repository size as float for sorting purposes."""
        if repo.metadata and repo.metadata.cache:
            try:
                return float(repo.metadata.cache.unique_csize_gb)
            except (ValueError, TypeError):
                pass
        return 0.0  # Default to 0 for repos without size info

    def _get_repo_date_for_sort(self, repo: BorgBoiRepo) -> datetime:
        """Get repository last backup date for sorting purposes."""
        if repo.last_backup:
            return repo.last_backup

        # Return a minimum datetime with the same timezone awareness as repo.last_backup
        # Check if we have any repos with timezone-aware dates to determine the pattern
        for r in self.repos:
            if r.last_backup and r.last_backup.tzinfo is not None:
                # Found a timezone-aware datetime, return timezone-aware minimum
                return datetime.min.replace(tzinfo=UTC)

        # All datetimes are timezone-naive, return minimum
        return datetime.min.replace(tzinfo=UTC)

    def _sort_repos(self) -> list[BorgBoiRepo]:
        """Sort repositories based on current sort order."""
        if self.current_sort == SortOrder.NAME_ASC:
            return sorted(self.repos, key=lambda r: r.name.lower())
        elif self.current_sort == SortOrder.NAME_DESC:
            return sorted(self.repos, key=lambda r: r.name.lower(), reverse=True)
        elif self.current_sort == SortOrder.SIZE_ASC:
            return sorted(self.repos, key=self._get_repo_size_for_sort)
        elif self.current_sort == SortOrder.SIZE_DESC:
            return sorted(self.repos, key=self._get_repo_size_for_sort, reverse=True)
        elif self.current_sort == SortOrder.DATE_ASC:
            return sorted(self.repos, key=self._get_repo_date_for_sort)
        elif self.current_sort == SortOrder.DATE_DESC:
            return sorted(self.repos, key=self._get_repo_date_for_sort, reverse=True)
        return self.repos

    def _get_sort_indicator(self, column: str) -> str:
        """Get sort indicator for column header."""
        if column == "name" and self.current_sort in [SortOrder.NAME_ASC, SortOrder.NAME_DESC]:
            return " ↑" if self.current_sort == SortOrder.NAME_ASC else " ↓"
        elif column == "size" and self.current_sort in [SortOrder.SIZE_ASC, SortOrder.SIZE_DESC]:
            return " ↑" if self.current_sort == SortOrder.SIZE_ASC else " ↓"
        elif column == "date" and self.current_sort in [SortOrder.DATE_ASC, SortOrder.DATE_DESC]:
            return " ↑" if self.current_sort == SortOrder.DATE_ASC else " ↓"
        return ""

    def _update_table(self) -> None:
        """Update the table with sorted data."""
        table: DataTable[Any] = self.query_one(DataTable)
        _ = table.clear(columns=True)

        # Add columns with sort indicators
        _ = table.add_columns(
            f"Name{self._get_sort_indicator('name')}",
            "Host",
            f"Size (GB){self._get_sort_indicator('size')}",
            "Location",
            f"Last Archive{self._get_sort_indicator('date')}",
        )

        sorted_repos = self._sort_repos()
        for repo in sorted_repos:
            # Get host machine
            host = repo.hostname

            # Get repo size
            size = "N/A"
            if repo.metadata and repo.metadata.cache:
                size = repo.metadata.cache.unique_csize_gb

            # Get location
            location = repo.metadata.repository.location if repo.metadata else repo.path

            # Get last backup/archive date
            last_backup = repo.last_backup.strftime("%Y-%m-%d %H:%M") if repo.last_backup else "Never"

            _ = table.add_row(repo.name, host, size, location, last_backup, key=repo.name)

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        table: DataTable[Any] = DataTable()
        _ = table.add_columns(
            f"Name{self._get_sort_indicator('name')}",
            "Host",
            f"Size (GB){self._get_sort_indicator('size')}",
            "Location",
            f"Last Archive{self._get_sort_indicator('date')}",
        )

        sorted_repos = self._sort_repos()
        for repo in sorted_repos:
            # Get host machine
            host = repo.hostname

            # Get repo size
            size = "N/A"
            if repo.metadata and repo.metadata.cache:
                size = repo.metadata.cache.unique_csize_gb

            # Get location
            location = repo.metadata.repository.location if repo.metadata else repo.path

            # Get last backup/archive date
            last_backup = repo.last_backup.strftime("%Y-%m-%d %H:%M") if repo.last_backup else "Never"

            _ = table.add_row(repo.name, host, size, location, last_backup, key=repo.name)

        yield table

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        # Focus the DataTable so arrow keys work immediately
        self.query_one(DataTable).focus()

    def action_sort_by_size(self) -> None:
        """Toggle sort by size."""
        if self.current_sort == SortOrder.SIZE_ASC:
            self.current_sort = SortOrder.SIZE_DESC
        else:
            self.current_sort = SortOrder.SIZE_ASC
        self._update_table()
        self.app.notify(f"Sorted by size ({'ascending' if self.current_sort == SortOrder.SIZE_ASC else 'descending'})")

    def action_sort_by_date(self) -> None:
        """Toggle sort by last archive date."""
        if self.current_sort == SortOrder.DATE_ASC:
            self.current_sort = SortOrder.DATE_DESC
        else:
            self.current_sort = SortOrder.DATE_ASC
        self._update_table()
        self.app.notify(f"Sorted by date ({'ascending' if self.current_sort == SortOrder.DATE_ASC else 'descending'})")

    def action_sort_by_name(self) -> None:
        """Toggle sort by name."""
        if self.current_sort == SortOrder.NAME_ASC:
            self.current_sort = SortOrder.NAME_DESC
        else:
            self.current_sort = SortOrder.NAME_ASC
        self._update_table()
        self.app.notify(f"Sorted by name ({'ascending' if self.current_sort == SortOrder.NAME_ASC else 'descending'})")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        if event.row_key and isinstance(event.row_key.value, str):
            repo_name = event.row_key.value
            selected_repo = next((r for r in self.repos if r.name == repo_name), None)
            if selected_repo:
                _ = self.post_message(RepoSelected(selected_repo))


class RepoDetailWidget(Static):
    """Widget to display repository details and archives."""

    DEFAULT_CSS: ClassVar[str] = """
    RepoDetailWidget {
        height: 100%;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._repo: BorgBoiRepo | None = None
        self._archives: list[borg.RepoArchive] = []
        self._loading: bool = False

    @property
    def repo(self) -> BorgBoiRepo | None:
        return self._repo

    @repo.setter
    def repo(self, value: BorgBoiRepo | None) -> None:
        self._repo = value
        if value:
            self.update_repo_display()
            _ = self.load_archives()

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield Label("Repository Details", id="repo-details-header")
            yield Label("", id="repo-name")
            yield Label("", id="repo-location")
            yield Label("", id="repo-encryption")
            yield Label("", id="repo-last-backup")

            yield Label("\nArchives", id="archives-header")
            with ScrollableContainer(id="archives-container"):
                yield DataTable(id="archives-table")

            with Horizontal(id="action-buttons"):
                yield Button("Daily Backup", variant="primary", id="daily-backup-btn")
                yield Button("Refresh", variant="default", id="refresh-btn")
                yield Button("Back", variant="default", id="back-btn")

    def update_repo_display(self) -> None:
        """Update the repository information display."""
        if self._repo:
            self.query_one("#repo-name", Label).update(f"Name: {self._repo.name}")
            location = self._repo.metadata.repository.location if self._repo.metadata else self._repo.path
            self.query_one("#repo-location", Label).update(f"Location: {location}")
            encryption = self._repo.metadata.encryption.mode if self._repo.metadata else "Unknown"
            self.query_one("#repo-encryption", Label).update(f"Encryption: {encryption}")
            last_backup = self._repo.last_backup.strftime("%Y-%m-%d %H:%M") if self._repo.last_backup else "Never"
            self.query_one("#repo-last-backup", Label).update(f"Last Backup: {last_backup}")

    def update_archives_display(self, archives: list[borg.RepoArchive]) -> None:
        """Update the archives table."""
        table: DataTable[Any] = self.query_one("#archives-table", DataTable)
        _ = table.clear(columns=True)

        if archives:
            _ = table.add_columns("Archive", "Created", "Duration", "Size")
            for archive in archives:
                # Handle both dict and object archive formats
                if hasattr(archive, "name"):
                    name = archive.name
                    created = archive.start if hasattr(archive, "start") else "Unknown"
                else:
                    name = archive.name
                    created = archive.start

                _ = table.add_row(
                    name,
                    created,
                    "N/A",  # Duration not available in simple list
                    "N/A",  # Size not available in simple list
                )

    @work(exclusive=True)
    async def load_archives(self) -> None:
        """Load archives for the current repository."""
        if not self._repo:
            return

        self._loading = True

        def get_archives() -> list[RepoArchive]:
            if self._repo is None:
                return []
            # Use borg client directly since orchestrator.list_archives doesn't return data
            return borg.list_archives(self._repo.path)

        try:
            # Run in thread to avoid blocking
            archives = await asyncio.get_event_loop().run_in_executor(None, get_archives)
            self._archives = archives
            self.update_archives_display(archives)
        except Exception as e:
            self.app.notify(f"Failed to load archives: {e!s}", severity="error")
        finally:
            self._loading = False

    @on(Button.Pressed, "#daily-backup-btn")
    def on_daily_backup(self) -> None:
        """Handle daily backup button press."""
        if self._repo:
            _ = self.run_daily_backup()

    @work(exclusive=True, thread=True)
    def run_daily_backup(self) -> None:
        """Run daily backup in a worker thread."""
        if not self._repo:
            return

        try:
            self.app.notify(f"Starting daily backup for {self._repo.name}...")
            orchestrator.perform_daily_backup(self._repo.path, offline=False)
            self.app.notify(f"Daily backup completed for {self._repo.name}!", severity="information")
            # Reload archives after backup
            _ = self.load_archives()
        except Exception as e:
            self.app.notify(f"Backup failed: {e!s}", severity="error")

    @on(Button.Pressed, "#refresh-btn")
    def on_refresh(self) -> None:
        """Handle refresh button press."""
        _ = self.load_archives()

    @on(Button.Pressed, "#back-btn")
    def on_back(self) -> None:
        """Handle back button press."""
        _ = self.app.pop_screen()


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
        self.query_one("#command-list", ListView).focus()

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
        _ = self.app.push_screen(MainScreen())

    @on(ListView.Selected)
    def on_list_view_selected(self, message: ListView.Selected) -> None:
        """Handle ListView selection."""
        if message.item.id == "go-to-repos" or message.item.id == "list-repos":
            self.action_list_repos()
        else:
            self.app.notify(f"Command '{message.item.id}' selected. CLI implementation would be called here.")


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
                self.query_one(DataTable).focus()
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
        _ = self.app.push_screen(DetailScreen(message.repo))


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


class BorgBoiApp(App[None]):
    """Main TUI application for borgboi."""

    CSS_PATH: ClassVar[CSSPathType | None] = "tui.tcss"

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
