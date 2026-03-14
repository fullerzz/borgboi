"""Excludes viewer screen for the BorgBoi TUI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, Tab, Tabs, TextArea

if TYPE_CHECKING:
    from borgboi.config import Config
    from borgboi.models import BorgBoiRepo


@dataclass(frozen=True, slots=True)
class ExcludesDocument:
    """Renderable excludes file state for the TUI."""

    tab_id: str
    tab_label: str
    path: Path | None
    status: str
    body: str
    exists: bool


def _read_excludes_body(path: Path) -> str:
    """Read excludes file content for display."""
    return path.read_text()


def load_default_excludes_document(config: Config | None) -> ExcludesDocument:
    """Load the shared default excludes file for display."""
    if config is None:
        return ExcludesDocument(
            tab_id="default-excludes",
            tab_label="Default",
            path=None,
            status="No configuration loaded.",
            body="BorgBoi could not resolve the shared excludes file path.",
            exists=False,
        )

    excludes_path = config.borgboi_dir / config.excludes_filename

    if not excludes_path.exists():
        return ExcludesDocument(
            tab_id="default-excludes",
            tab_label="Default",
            path=excludes_path,
            status="No shared default excludes file found.",
            body=(
                "Create this file to define shared exclude patterns for repositories "
                "without a repo-specific excludes file."
            ),
            exists=False,
        )

    content = _read_excludes_body(excludes_path)
    if not content:
        return ExcludesDocument(
            tab_id="default-excludes",
            tab_label="Default",
            path=excludes_path,
            status="Shared default excludes file is empty.",
            body="",
            exists=True,
        )

    return ExcludesDocument(
        tab_id="default-excludes",
        tab_label="Default",
        path=excludes_path,
        status="Shared excludes apply when a repository has no repo-specific excludes file.",
        body=content,
        exists=True,
    )


def load_repo_excludes_document(config: Config | None, repo_name: str, index: int) -> ExcludesDocument:
    """Load a repository-specific excludes file for display."""
    if config is None:
        return ExcludesDocument(
            tab_id=f"repo-{index}",
            tab_label=repo_name,
            path=None,
            status="No configuration loaded.",
            body="BorgBoi could not resolve the repo-specific excludes file path.",
            exists=False,
        )

    excludes_path = config.borgboi_dir / f"{repo_name}_{config.excludes_filename}"
    default_exists = (config.borgboi_dir / config.excludes_filename).exists()

    if not excludes_path.exists():
        fallback_status = (
            "No repo-specific excludes file found. BorgBoi falls back to the shared default excludes file."
            if default_exists
            else "No repo-specific excludes file found, and no shared default excludes file is available."
        )
        return ExcludesDocument(
            tab_id=f"repo-{index}",
            tab_label=repo_name,
            path=excludes_path,
            status=fallback_status,
            body="Create this file to override shared exclude patterns for this repository.",
            exists=False,
        )

    content = _read_excludes_body(excludes_path)
    if not content:
        return ExcludesDocument(
            tab_id=f"repo-{index}",
            tab_label=repo_name,
            path=excludes_path,
            status="Repo-specific excludes file is empty and overrides the shared default for this repository.",
            body="",
            exists=True,
        )

    return ExcludesDocument(
        tab_id=f"repo-{index}",
        tab_label=repo_name,
        path=excludes_path,
        status="Repo-specific excludes override the shared default for this repository.",
        body=content,
        exists=True,
    )


def load_excludes_documents(config: Config | None, repos: Sequence[BorgBoiRepo]) -> list[ExcludesDocument]:
    """Build the excludes documents shown in the viewer tabs."""
    documents = [load_default_excludes_document(config)]
    for index, repo in enumerate(repos, start=1):
        documents.append(load_repo_excludes_document(config, repo.name, index=index))
    return documents


class DefaultExcludesScreen(Screen[None]):
    """Screen for viewing shared and repo-specific excludes files."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("e", "app.pop_screen", "Back"),
    ]

    def __init__(
        self,
        config: Config | None = None,
        repos: Sequence[BorgBoiRepo] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._documents = load_excludes_documents(config, repos or [])
        self._documents_by_tab_id = {document.tab_id: document for document in self._documents}

    @override
    def compose(self) -> ComposeResult:
        document = self._documents[0]
        viewer = TextArea(document.body, id="default-excludes-viewer")
        viewer.read_only = True

        yield Header()
        with Vertical(id="default-excludes-screen"):
            yield Static(
                "[bold #cba6f7]Excludes files[/]",
                id="default-excludes-title",
                markup=True,
            )
            yield Tabs(
                *(Tab(document.tab_label, id=document.tab_id) for document in self._documents),
                id="default-excludes-tabs",
            )
            yield Static(document.status, id="default-excludes-status")
            yield Static(self._path_label(document), id="default-excludes-path")
            yield viewer
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#default-excludes-tabs", Tabs).focus()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Update the viewer when a tab becomes active."""
        if event.tab is None or event.tab.id is None:
            return

        document = self._documents_by_tab_id[event.tab.id]
        self._show_document(document)

    def _show_document(self, document: ExcludesDocument) -> None:
        """Render an excludes document in the viewer area."""
        self.query_one("#default-excludes-status", Static).update(document.status)
        self.query_one("#default-excludes-path", Static).update(self._path_label(document))
        self.query_one("#default-excludes-viewer", TextArea).load_text(document.body)

    def _path_label(self, document: ExcludesDocument) -> str:
        """Build a display label for an excludes path."""
        if document.path is None:
            return "Path unavailable"
        return f"Path: {document.path}"
