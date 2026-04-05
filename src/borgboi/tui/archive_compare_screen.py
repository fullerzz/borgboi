"""Archive comparison screen for the BorgBoi TUI."""

from __future__ import annotations

import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, ClassVar, Literal, override

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Footer, Header, Label, Select, Static, Switch, Tree
from textual.widgets.directory_tree import DirEntry
from textual.widgets.tree import TreeNode

from borgboi.clients.borg import DiffChange, DiffResult, RepoArchive
from borgboi.core.logging import get_logger
from borgboi.core.models import DiffOptions
from borgboi.lib.diff import format_diff_change, summarize_diff_changes
from borgboi.lib.utils import format_iso_timestamp, format_size_bytes

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


@dataclass(frozen=True)
class ComparePathState:
    """Comparison metadata for a single changed archive path."""

    relative_path: Path
    older_exists: bool
    newer_exists: bool
    changes: tuple[DiffChange, ...]


def build_compare_path_states(result: DiffResult) -> dict[Path, ComparePathState]:
    """Build a lookup of changed paths and which side each path exists on."""
    states: dict[Path, ComparePathState] = {}
    for entry in result.entries:
        older_exists, newer_exists = _resolve_path_presence(entry.changes)
        states[entry.path] = ComparePathState(
            relative_path=entry.path,
            older_exists=older_exists,
            newer_exists=newer_exists,
            changes=tuple(entry.changes),
        )
    return states


def _resolve_path_presence(changes: list[DiffChange]) -> tuple[bool, bool]:
    """Infer whether a changed path exists in the older and newer archive."""
    change_types = {change.type for change in changes}
    if change_types == {"added"}:
        return False, True
    if change_types == {"removed"}:
        return True, False
    return True, True


def _archive_sort_key(archive: RepoArchive) -> tuple[str, str]:
    """Sort archives newest-first using the timestamp when available."""
    return (archive.time or archive.start or "", archive.name)


class CompareDirectoryTree(DirectoryTree):
    """Directory tree that reports directory expand/collapse changes to the screen."""

    def __init__(
        self,
        path: str | Path,
        *,
        on_directory_expanded: Callable[[CompareDirectoryTree, Path], Awaitable[None]] | None = None,
        on_directory_collapsed: Callable[[CompareDirectoryTree, Path], Awaitable[None]] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        self._on_directory_expanded = on_directory_expanded
        self._on_directory_collapsed = on_directory_collapsed
        super().__init__(path, name=name, id=id, classes=classes, disabled=disabled)

    @override
    async def _on_tree_node_expanded(self, event: Tree.NodeExpanded[DirEntry]) -> None:
        """Emit a screen-friendly message after Textual finishes loading a directory."""
        await super()._on_tree_node_expanded(event)
        dir_entry = event.node.data
        if dir_entry is None or not event.node.allow_expand:
            return
        if self._on_directory_expanded is not None:
            await self._on_directory_expanded(self, dir_entry.path)

    async def _on_tree_node_collapsed(self, event: Tree.NodeCollapsed[DirEntry]) -> None:
        """Emit a screen-friendly message after a directory node is collapsed."""
        dir_entry = event.node.data
        if dir_entry is None or not event.node.allow_expand:
            return
        if self._on_directory_collapsed is not None:
            await self._on_directory_collapsed(self, dir_entry.path)

    async def ensure_node_loaded(self, node: TreeNode[DirEntry]) -> None:
        """Ensure a directory node's children are loaded into memory."""
        if not node.allow_expand or node.data is None or node.data.loaded:
            return
        await self._add_to_load_queue(node)

    async def find_node_by_relative_path(self, relative_path: Path) -> TreeNode[DirEntry] | None:
        """Locate a node by relative path, loading ancestor directories as needed."""
        current_node = self.root
        if not relative_path.parts:
            return current_node

        for part in relative_path.parts:
            await self.ensure_node_loaded(current_node)
            child_node: TreeNode[DirEntry] | None = next(
                (child for child in current_node.children if child.data is not None and child.data.path.name == part),
                None,
            )
            if child_node is None:
                return None
            current_node = child_node

        return current_node


class ArchiveCompareScreen(Screen[None]):
    """Screen for visually comparing two archives from the same repository."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
        Binding("r", "run_compare", "Compare"),
    ]

    def __init__(
        self,
        repo: BorgBoiRepo,
        orchestrator: Orchestrator,
        *,
        initial_older_archive: str | None = None,
        initial_newer_archive: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._repo = repo
        self._orchestrator = orchestrator
        self._initial_older_archive = initial_older_archive
        self._initial_newer_archive = initial_newer_archive
        self._archives: list[RepoArchive] = []
        self._archive_index: dict[str, RepoArchive] = {}
        self._path_states: dict[Path, ComparePathState] = {}
        self._compare_result = DiffResult(archive1="", archive2="", entries=[])
        self._tempdir = TemporaryDirectory(prefix="borgboi-archive-compare-")
        self._compare_temp_root = Path(self._tempdir.name)
        self._older_root = self._compare_temp_root / "older"
        self._newer_root = self._compare_temp_root / "newer"
        self._older_root_resolved = self._older_root.resolve()
        self._newer_root_resolved = self._newer_root.resolve()
        self._mirrored_tree_operations: set[tuple[str, str, str]] = set()
        self._older_root.mkdir(parents=True, exist_ok=True)
        self._newer_root.mkdir(parents=True, exist_ok=True)
        super().__init__(**kwargs)

    @override
    def compose(self) -> ComposeResult:
        """Build the archive comparison layout."""
        yield Header()
        with Vertical(id="archive-compare-screen"):
            yield Static(f"Archive Compare: {self._repo.name}", id="archive-compare-title")
            yield Label("Loading archive choices...", id="archive-compare-status")
            with Horizontal(id="archive-compare-body"):
                with Vertical(classes="archive-compare-pane"):
                    yield Select[str]([], prompt="Older archive", id="archive-compare-older-select", disabled=True)
                    yield Static("Older archive", id="archive-compare-older-heading", markup=True)
                    yield CompareDirectoryTree(
                        self._older_root,
                        id="archive-compare-older-tree",
                        on_directory_expanded=self._mirror_directory_expansion,
                        on_directory_collapsed=self._mirror_directory_collapse,
                    )
                with Vertical(id="archive-compare-details", classes="archive-compare-pane"):
                    with Horizontal(id="archive-compare-center-controls"):
                        yield Label("Content only", id="archive-compare-content-only-label")
                        yield Switch(value=False, id="archive-compare-content-only-switch")
                        yield Button("Compare", id="archive-compare-run-btn", variant="primary", disabled=True)
                    yield Static("Loading comparison summary...", id="archive-compare-summary", markup=True)
                    yield Static("No path selected.", id="archive-compare-selection", markup=True)
                with Vertical(classes="archive-compare-pane"):
                    yield Select[str]([], prompt="Newer archive", id="archive-compare-newer-select", disabled=True)
                    yield Static("Newer archive", id="archive-compare-newer-heading", markup=True)
                    yield CompareDirectoryTree(
                        self._newer_root,
                        id="archive-compare-newer-tree",
                        on_directory_expanded=self._mirror_directory_expansion,
                        on_directory_collapsed=self._mirror_directory_collapse,
                    )
        yield Footer()

    def on_mount(self) -> None:
        """Prepare the trees and start loading archive choices."""
        self._older_tree = self.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        self._newer_tree = self.query_one("#archive-compare-newer-tree", CompareDirectoryTree)
        for tree in (self._older_tree, self._newer_tree):
            tree.show_root = False
            tree.root.expand()

        self.query_one("#archive-compare-older-select", Select).loading = True
        self.query_one("#archive-compare-newer-select", Select).loading = True
        self._load_archive_choices()

    def on_unmount(self) -> None:
        """Clean up any temporary mirror directories created for comparison."""
        self._cleanup_tempdir()

    def action_back(self) -> None:
        """Return to the previous screen."""
        _ = self.app.pop_screen()

    def action_run_compare(self) -> None:
        """Run the comparison for the selected archive pair."""
        self._start_compare()

    @work(thread=True, exclusive=True, group="archive-choices")
    def _load_archive_choices(self) -> None:
        """Load archive options and determine the default compare pair."""
        try:
            archives = sorted(self._orchestrator.list_archives(self._repo), key=_archive_sort_key, reverse=True)
            older_archive = self._initial_older_archive
            newer_archive = self._initial_newer_archive
            if older_archive is None or newer_archive is None:
                older, newer = self._orchestrator.get_two_most_recent_archives(self._repo)
                older_archive = older.name
                newer_archive = newer.name
        except Exception as exc:
            logger.exception("Failed to load archive choices", repo_name=self._repo.name, error=str(exc))
            self.app.call_from_thread(self._on_archive_choices_error, exc)
            return

        assert older_archive is not None
        assert newer_archive is not None
        self.app.call_from_thread(self._apply_archive_choices, archives, older_archive, newer_archive)

    def _apply_archive_choices(self, archives: list[RepoArchive], older_archive: str, newer_archive: str) -> None:
        """Populate the archive selectors and kick off the initial compare."""
        self._archives = archives
        self._archive_index = {archive.name: archive for archive in archives}

        older_select = self.query_one("#archive-compare-older-select", Select)
        newer_select = self.query_one("#archive-compare-newer-select", Select)

        options = [(archive.name, archive.name) for archive in archives]
        older_select.set_options(options)
        newer_select.set_options(options)
        older_select.loading = False
        newer_select.loading = False
        older_select.disabled = False
        newer_select.disabled = False
        self.query_one("#archive-compare-run-btn", Button).disabled = False

        older_select.value = older_archive
        newer_select.value = newer_archive
        self.query_one("#archive-compare-status", Label).update("Archive choices loaded. Running initial comparison...")
        self._start_compare()

    def _on_archive_choices_error(self, error: Exception) -> None:
        """Handle archive-choice loading failures."""
        self.query_one("#archive-compare-older-select", Select).loading = False
        self.query_one("#archive-compare-newer-select", Select).loading = False
        self.query_one("#archive-compare-status", Label).update(f"Failed to load archive choices: {error}")
        self.query_one("#archive-compare-summary", Static).update(
            f"[#f38ba8]Archive comparison unavailable:[/] {escape(str(error))}"
        )
        self.notify(str(error), severity="error", title="Archive Compare")

    def _start_compare(self) -> None:
        """Validate the selected archive pair and start a background compare."""
        older_select = self.query_one("#archive-compare-older-select", Select)
        newer_select = self.query_one("#archive-compare-newer-select", Select)

        if older_select.value is Select.BLANK or newer_select.value is Select.BLANK:
            return

        older_archive = str(older_select.value)
        newer_archive = str(newer_select.value)
        if older_archive == newer_archive:
            self.notify("Select two different archives to compare.", severity="warning", title="Archive Compare")
            return

        self._set_compare_controls_enabled(False)
        self.query_one("#archive-compare-status", Label).update(f"Comparing {older_archive} -> {newer_archive}...")
        self.query_one("#archive-compare-selection", Static).update("No path selected.")
        self._compare_archives(
            older_archive, newer_archive, self.query_one("#archive-compare-content-only-switch", Switch).value
        )

    @work(thread=True, exclusive=True, group="archive-compare")
    def _compare_archives(self, older_archive: str, newer_archive: str, content_only: bool) -> None:
        """Run the archive diff and materialize the temporary mirror trees."""
        try:
            result = self._orchestrator.diff_archives(
                self._repo,
                older_archive,
                newer_archive,
                options=DiffOptions(content_only=content_only),
            )
            path_states = build_compare_path_states(result)
            self._reset_compare_roots()
            self._materialize_compare_root(
                self._older_root,
                [state.relative_path for state in path_states.values() if state.older_exists],
            )
            self._materialize_compare_root(
                self._newer_root,
                [state.relative_path for state in path_states.values() if state.newer_exists],
            )
        except Exception as exc:
            logger.exception(
                "Failed to compare archives",
                repo_name=self._repo.name,
                older_archive=older_archive,
                newer_archive=newer_archive,
                error=str(exc),
            )
            self.app.call_from_thread(self._on_compare_error, exc)
            return

        self.app.call_from_thread(self._apply_compare_result, result, path_states, content_only)

    def _reset_compare_roots(self) -> None:
        """Clear any previous synthetic compare tree contents."""
        for root in (self._older_root, self._newer_root):
            shutil.rmtree(root, ignore_errors=True)
            root.mkdir(parents=True, exist_ok=True)

    def _materialize_compare_root(self, root: Path, paths: list[Path]) -> None:
        """Write a lightweight filesystem mirror for a set of changed paths."""
        normalized_paths = {path for path in paths if path.parts}
        parent_directories = {parent for path in normalized_paths for parent in path.parents if parent.parts}

        for directory in sorted(parent_directories, key=lambda item: (len(item.parts), item.as_posix())):
            (root / directory).mkdir(parents=True, exist_ok=True)

        for relative_path in sorted(normalized_paths, key=lambda item: item.as_posix()):
            target = root / relative_path
            if relative_path in parent_directories:
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)

    def _apply_compare_result(
        self, result: DiffResult, path_states: dict[Path, ComparePathState], content_only: bool
    ) -> None:
        """Render the compare result after the background worker finishes."""
        self._compare_result = result
        self._path_states = path_states
        self._set_compare_controls_enabled(True)
        self.query_one("#archive-compare-status", Label).update(
            self._render_status_line(result.archive1, result.archive2, content_only)
        )
        self.query_one("#archive-compare-summary", Static).update(self._render_summary(result))
        self.query_one("#archive-compare-selection", Static).update(
            "No changed paths to inspect." if not path_states else "No path selected."
        )
        self.query_one("#archive-compare-older-heading", Static).update(self._render_archive_heading(result.archive1))
        self.query_one("#archive-compare-newer-heading", Static).update(self._render_archive_heading(result.archive2))
        self._mirrored_tree_operations.clear()

        _ = self._older_tree.reload()
        _ = self._newer_tree.reload()

    def _on_compare_error(self, error: Exception) -> None:
        """Handle archive compare failures."""
        self._set_compare_controls_enabled(True)
        self.query_one("#archive-compare-status", Label).update(f"Archive comparison failed: {error}")
        self.query_one("#archive-compare-summary", Static).update(
            f"[#f38ba8]Archive comparison failed:[/] {escape(str(error))}"
        )
        self.query_one("#archive-compare-selection", Static).update("No path selected.")
        self.notify(str(error), severity="error", title="Archive Compare")

    def _set_compare_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable compare controls while background work is running."""
        self.query_one("#archive-compare-older-select", Select).disabled = not enabled
        self.query_one("#archive-compare-newer-select", Select).disabled = not enabled
        self.query_one("#archive-compare-content-only-switch", Switch).disabled = not enabled
        self.query_one("#archive-compare-run-btn", Button).disabled = not enabled

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle compare button presses."""
        if event.button.id != "archive-compare-run-btn":
            return
        self._start_compare()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Update the detail panel when a file is selected in either tree."""
        self._show_selected_path(event.path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Update the detail panel when a directory is selected in either tree."""
        self._show_selected_path(event.path)

    async def _mirror_directory_expansion(self, source_tree: CompareDirectoryTree, expanded_path: Path) -> None:
        """Mirror user-driven directory expansions into the opposite archive tree."""
        await self._sync_directory_state(source_tree, expanded_path, operation="expand")

    async def _mirror_directory_collapse(self, source_tree: CompareDirectoryTree, collapsed_path: Path) -> None:
        """Mirror user-driven directory collapses into the opposite archive tree."""
        await self._sync_directory_state(source_tree, collapsed_path, operation="collapse")

    async def _sync_directory_state(
        self, source_tree: CompareDirectoryTree, directory_path: Path, *, operation: Literal["expand", "collapse"]
    ) -> None:
        """Synchronize a directory expand/collapse operation into the opposite tree."""
        relative_path = self._relative_compare_path(directory_path)
        if relative_path is None or not relative_path.parts:
            return

        message_key = (operation, source_tree.id or "", relative_path.as_posix())
        if message_key in self._mirrored_tree_operations:
            self._mirrored_tree_operations.remove(message_key)
            return

        peer_tree = self._get_peer_tree(source_tree)
        if peer_tree is None:
            return

        matching_node = await peer_tree.find_node_by_relative_path(relative_path)
        if matching_node is None or not matching_node.allow_expand:
            return

        if operation == "expand":
            if matching_node.is_expanded:
                return
            self._mirrored_tree_operations.add((operation, peer_tree.id or "", relative_path.as_posix()))
            matching_node.expand()
            await peer_tree.ensure_node_loaded(matching_node)
            return

        if operation == "collapse":
            if matching_node.is_collapsed:
                return
            self._mirrored_tree_operations.add((operation, peer_tree.id or "", relative_path.as_posix()))
            matching_node.collapse()

    def _show_selected_path(self, selected_path: Path) -> None:
        """Render details for the selected compare path or directory."""
        relative_path = self._relative_compare_path(selected_path)
        if relative_path is None:
            return

        state = self._path_states.get(relative_path)
        if state is not None:
            changes = ", ".join(format_diff_change(change) for change in state.changes)
            self.query_one("#archive-compare-selection", Static).update(
                "\n".join(
                    [
                        f"[bold #f5e0dc]{escape(relative_path.as_posix())}[/]",
                        f"[#89b4fa]Older:[/] {'Present' if state.older_exists else 'Missing'}",
                        f"[#89b4fa]Newer:[/] {'Present' if state.newer_exists else 'Missing'}",
                        f"[#89b4fa]Changes:[/] {escape(changes)}",
                    ]
                )
            )
            return

        descendant_count = sum(
            1 for path in self._path_states if relative_path == path or relative_path in path.parents
        )
        self.query_one("#archive-compare-selection", Static).update(
            "\n".join(
                [
                    f"[bold #f5e0dc]{escape(relative_path.as_posix())}[/]",
                    f"[#89b4fa]Changed descendants:[/] {descendant_count}",
                ]
            )
        )

    def _relative_compare_path(self, absolute_path: Path) -> Path | None:
        """Convert an absolute selected path into a relative compare path."""
        resolved_path = absolute_path.resolve()
        for root in (self._older_root_resolved, self._newer_root_resolved):
            try:
                return resolved_path.relative_to(root)
            except ValueError:
                continue
        return None

    def _get_peer_tree(self, source_tree: CompareDirectoryTree) -> CompareDirectoryTree | None:
        """Return the opposite compare tree for a given source tree."""
        if source_tree is self._older_tree:
            return self._newer_tree
        if source_tree is self._newer_tree:
            return self._older_tree
        return None

    def _render_archive_heading(self, archive_name: str) -> str:
        """Render a heading for one side of the compare view."""
        archive = self._archive_index.get(archive_name)
        if archive is None:
            return escape(archive_name)
        return "\n".join(
            [
                f"[bold #f5e0dc]{escape(archive.name)}[/]",
                f"[#89b4fa]{escape(format_iso_timestamp(archive.time or archive.start))}[/]",
            ]
        )

    def _render_status_line(self, older_archive: str, newer_archive: str, content_only: bool) -> str:
        """Render the current compare status line."""
        content_label = "content-only" if content_only else "content + metadata"
        return f"Comparing {older_archive} -> {newer_archive} ({content_label})."

    def _render_summary(self, result: DiffResult) -> str:
        """Render summary metrics for the current compare result."""
        summary = summarize_diff_changes(result)
        return "\n".join(
            [
                f"[bold #f5e0dc]{escape(result.archive1)}[/] [#89b4fa]->[/] [bold #f5e0dc]{escape(result.archive2)}[/]",
                f"[#89b4fa]Changed paths:[/] {len(result.entries)}",
                f"[#89b4fa]Added:[/] {summary['added']}  [#89b4fa]Removed:[/] {summary['removed']}",
                f"[#89b4fa]Modified:[/] {summary['modified']}  [#89b4fa]Mode changes:[/] {summary['mode']}",
                (
                    f"[#89b4fa]Bytes added:[/] {escape(format_size_bytes(summary['bytes_added']))}  "
                    f"[#89b4fa]Bytes removed:[/] {escape(format_size_bytes(summary['bytes_removed']))}"
                ),
            ]
        )

    def _cleanup_tempdir(self) -> None:
        """Release the synthetic compare tree directory."""
        self._tempdir.cleanup()
