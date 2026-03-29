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
from textual.widgets import Footer, Header, Link, Static, Tab, Tabs, TextArea

from borgboi.core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.config import Config
    from borgboi.models import BorgBoiRepo

_EDITING_STATUS = "(editing)"
_EXCLUDES_HELP_URL = "https://borgbackup.readthedocs.io/en/stable/usage/help.html"


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
    try:
        content = path.read_text()
        logger.debug("Read excludes file", path=str(path), content_length=len(content))
        return content
    except Exception as exc:
        logger.warning("Failed to read excludes file", path=str(path), error=str(exc))
        raise


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
    """Screen for viewing and editing shared and repo-specific excludes files."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel_or_back", "Back"),
        Binding("e", "back", "Back"),
        Binding("ctrl+e", "toggle_edit", "Edit", priority=True),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    def __init__(
        self,
        config: Config | None = None,
        repos: Sequence[BorgBoiRepo] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._repos: Sequence[BorgBoiRepo] = repos or []
        self._documents = load_excludes_documents(config, self._repos)
        self._documents_by_tab_id = {document.tab_id: document for document in self._documents}
        self._editing = False
        logger.debug(
            "DefaultExcludesScreen initialized", document_count=len(self._documents), repo_count=len(self._repos)
        )

    @property
    def _active_document(self) -> ExcludesDocument | None:
        """Return the document for the currently active tab."""
        tabs = self.query_one("#default-excludes-tabs", Tabs)
        tab = tabs.active_tab
        if tab is None or tab.id is None:
            return None
        return self._documents_by_tab_id.get(tab.id)

    @override
    def compose(self) -> ComposeResult:
        """Build the screen layout with tabs for each excludes document, a viewer, and help link."""
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
            yield Link("Exclude pattern help (Borg docs)", url=_EXCLUDES_HELP_URL, id="default-excludes-help-link")
            yield viewer
        yield Footer()

    def on_mount(self) -> None:
        """Focus the tab bar when the screen is first mounted."""
        logger.debug("DefaultExcludesScreen mounted")
        self.query_one("#default-excludes-tabs", Tabs).focus()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Update the viewer when a tab becomes active."""
        if event.tab is None or event.tab.id is None:
            logger.debug("Tab activation event with no tab")
            return

        if self._editing:
            logger.debug("Cancelling edit mode on tab switch")
            self._reset_edit_state()

        document = self._documents_by_tab_id[event.tab.id]
        logger.debug("Tab activated", tab_id=event.tab.id, document_exists=document.exists)
        self._show_document(document)

    def action_toggle_edit(self) -> None:
        """Toggle between read-only and edit mode."""
        if self._editing:
            logger.debug("Exiting edit mode via toggle")
            self._cancel_edit()
        else:
            logger.debug("Entering edit mode via toggle")
            self._enter_edit_mode()

    def action_save(self) -> None:
        """Save the current TextArea content to disk."""
        if not self._editing:
            return

        document = self._active_document
        if document is None or document.path is None:
            self.notify("Cannot save: no file path available", severity="error")
            logger.error("Save attempted with no active document or path")
            return

        content = self.query_one("#default-excludes-viewer", TextArea).text

        try:
            document.path.parent.mkdir(parents=True, exist_ok=True)
            document.path.write_text(content)
            logger.info("Excludes file saved", path=str(document.path), content_length=len(content))
        except OSError as exc:
            logger.error("Failed to save excludes file", path=str(document.path), error=str(exc))
            self.notify(f"Save failed: {exc}", severity="error")
            return

        self._reload_documents()
        self._reset_edit_state()

        reloaded = self._active_document
        if reloaded is not None:
            self._show_document(reloaded)

        self.notify(f"Saved {document.path.name}", severity="information")

    def action_back(self) -> None:
        """Go back to the main screen (only available when not editing)."""
        logger.debug("Closing excludes screen")
        _ = self.app.pop_screen()

    def action_cancel_or_back(self) -> None:
        """Cancel editing or go back to the main screen."""
        if self._editing:
            logger.debug("Cancelling edit and returning to main screen")
            self._cancel_edit()
        else:
            logger.debug("Closing excludes screen via cancel/back")
            _ = self.app.pop_screen()

    def _cancel_edit(self) -> None:
        """Exit edit mode and restore the current document."""
        logger.debug("Cancelling edit mode")
        self._reset_edit_state()
        document = self._active_document
        if document is not None:
            self._show_document(document)

    def _enter_edit_mode(self) -> None:
        """Switch to edit mode for the active document."""
        document = self._active_document
        if document is None or document.path is None:
            self.notify("Cannot edit: no file path available", severity="error")
            logger.warning("Edit mode requested but no active document or path available")
            return

        viewer = self.query_one("#default-excludes-viewer", TextArea)
        self._editing = True

        if not document.exists:
            viewer.load_text("")
            logger.debug("Creating new excludes file in edit mode", path=str(document.path))

        viewer.read_only = False
        viewer.add_class("-editing")
        viewer.focus()

        self.query_one("#default-excludes-status", Static).update(f"{document.status} {_EDITING_STATUS}")
        self.refresh_bindings()
        logger.debug("Entered edit mode", path=str(document.path))

    def _reset_edit_state(self) -> None:
        """Reset editing flags and viewer styling without modifying TextArea content."""
        viewer = self.query_one("#default-excludes-viewer", TextArea)
        viewer.read_only = True
        viewer.remove_class("-editing")

        self._editing = False

        self.query_one("#default-excludes-tabs", Tabs).focus()
        self.refresh_bindings()
        logger.debug("Edit state reset")

    def _show_document(self, document: ExcludesDocument) -> None:
        """Render an excludes document in the viewer area."""
        self.query_one("#default-excludes-status", Static).update(document.status)
        self.query_one("#default-excludes-path", Static).update(self._path_label(document))
        self.query_one("#default-excludes-viewer", TextArea).load_text(document.body)
        logger.debug("Document shown", tab_id=document.tab_id, exists=document.exists)

    def _reload_documents(self) -> None:
        """Reload all documents from disk."""
        logger.debug("Reloading excludes documents from disk")
        self._documents = load_excludes_documents(self._config, self._repos)
        self._documents_by_tab_id = {document.tab_id: document for document in self._documents}
        logger.debug("Documents reloaded", count=len(self._documents))

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Control binding visibility based on editing state."""
        if action == "save":
            return self._editing
        if action == "back":
            return not self._editing
        return True

    def _path_label(self, document: ExcludesDocument) -> str:
        """Build a display label for an excludes path."""
        if document.path is None:
            return "Path unavailable"
        return f"Path: {document.path}"
