"""Default excludes viewer screen for the BorgBoi TUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TextArea

if TYPE_CHECKING:
    from borgboi.config import Config


@dataclass(frozen=True, slots=True)
class DefaultExcludesDocument:
    """Renderable shared excludes file state for the TUI."""

    path: Path | None
    status: str
    body: str
    exists: bool


def load_default_excludes_document(config: Config | None) -> DefaultExcludesDocument:
    """Load the shared default excludes file for display."""
    if config is None:
        return DefaultExcludesDocument(
            path=None,
            status="No configuration loaded.",
            body="BorgBoi could not resolve the shared excludes file path.",
            exists=False,
        )

    excludes_path = config.borgboi_dir / config.excludes_filename

    if not excludes_path.exists():
        return DefaultExcludesDocument(
            path=excludes_path,
            status="No shared default excludes file found.",
            body=(
                "Create this file to define shared exclude patterns for repositories "
                "without a repo-specific excludes file."
            ),
            exists=False,
        )

    content = excludes_path.read_text()
    if not content:
        return DefaultExcludesDocument(
            path=excludes_path,
            status="Shared default excludes file is empty.",
            body="",
            exists=True,
        )

    return DefaultExcludesDocument(
        path=excludes_path,
        status="Shared excludes apply when a repository has no repo-specific excludes file.",
        body=content,
        exists=True,
    )


class DefaultExcludesScreen(Screen[None]):
    """Screen for viewing the shared default excludes file."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("e", "app.pop_screen", "Back"),
    ]

    def __init__(self, config: Config | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._document = load_default_excludes_document(config)

    @override
    def compose(self) -> ComposeResult:
        document = self._document
        viewer = TextArea(document.body, id="default-excludes-viewer")
        viewer.read_only = True

        yield Header()
        with Vertical(id="default-excludes-screen"):
            yield Static(
                "[bold #cba6f7]Default excludes.txt[/]",
                id="default-excludes-title",
                markup=True,
            )
            yield Static(document.status, id="default-excludes-status")
            yield Static(self._path_label(document), id="default-excludes-path")
            yield viewer
        yield Footer()

    def _path_label(self, document: DefaultExcludesDocument) -> str:
        """Build a display label for the shared excludes path."""
        if document.path is None:
            return "Path unavailable"
        return f"Path: {document.path}"
