"""Repository list widget for the TUI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, override

from textual import on
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Static

from borgboi.models import BorgBoiRepo
from borgboi.tui.types import RepoSelected, SortOrder


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
    def compose(self):
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
        _ = self.query_one(DataTable).focus()

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
