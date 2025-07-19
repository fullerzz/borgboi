"""Common types and messages for the TUI."""

from __future__ import annotations

from enum import Enum

from textual.message import Message

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
