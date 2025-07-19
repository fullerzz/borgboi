"""Repository detail widget for the TUI."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any, ClassVar, override

from textual import on, work
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, DataTable, Label, Static

from borgboi import orchestrator
from borgboi.clients import borg
from borgboi.clients.borg import RepoArchive
from borgboi.models import BorgBoiRepo


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
    def compose(self) -> Generator[Label | DataTable[Any] | Button]:
        """Create child widgets."""
        with Vertical():
            yield Label("Repository Details", id="repo-details-header")
            yield Label("", id="repo-name")
            yield Label("", id="repo-location")
            yield Label("", id="repo-encryption")
            yield Label("", id="repo-last-backup")

            yield Label("\\nArchives", id="archives-header")
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
