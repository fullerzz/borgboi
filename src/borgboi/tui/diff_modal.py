"""Content-level diff modal for a single file across two archives."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any, ClassVar, override

from rich.markup import escape
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, RichLog, Static

from borgboi.core.logging import get_logger
from borgboi.lib.utils import format_size_bytes

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo

logger = get_logger(__name__)

MAX_CONTENT_DIFF_BYTES = 2 * 1024 * 1024
BINARY_SNIFF_BYTES = 8192
DIFF_CONTEXT_LINES = 3


class ContentDiffScreen(ModalScreen[None]):
    """Modal that renders a unified diff of one file across two archives."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(
        self,
        repo: BorgBoiRepo,
        orchestrator: Orchestrator,
        *,
        older_archive: str,
        newer_archive: str,
        older_exists: bool,
        newer_exists: bool,
        file_path: str,
        **kwargs: Any,
    ) -> None:
        self._repo = repo
        self._orchestrator = orchestrator
        self._older_archive = older_archive
        self._newer_archive = newer_archive
        self._older_exists = older_exists
        self._newer_exists = newer_exists
        self._file_path = file_path
        super().__init__(**kwargs)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="content-diff-modal"):
            yield Static(
                f"[bold #f5e0dc]Content diff[/] — {escape(self._file_path)}",
                id="content-diff-title",
                markup=True,
            )
            yield Label(
                f"[#89b4fa]{escape(self._older_archive)}[/] -> [#89b4fa]{escape(self._newer_archive)}[/]",
                id="content-diff-subtitle",
                markup=True,
            )
            yield Static("Loading file contents...", id="content-diff-status", markup=True)
            yield RichLog(id="content-diff-log", markup=False, highlight=False, wrap=False)
        yield Footer()

    def on_mount(self) -> None:
        self._load_contents()

    def action_close(self) -> None:
        _ = self.dismiss(None)

    @work(thread=True, exclusive=True, group="content-diff")
    def _load_contents(self) -> None:
        try:
            older_content = (
                self._orchestrator.extract_archived_file_capped(
                    self._repo,
                    self._older_archive,
                    self._file_path,
                    max_bytes=MAX_CONTENT_DIFF_BYTES,
                )
                if self._older_exists
                else None
            )
            newer_content = (
                self._orchestrator.extract_archived_file_capped(
                    self._repo,
                    self._newer_archive,
                    self._file_path,
                    max_bytes=MAX_CONTENT_DIFF_BYTES,
                )
                if self._newer_exists
                else None
            )
        except Exception as exc:
            logger.exception(
                "Failed to extract file contents for diff",
                repo_name=self._repo.name,
                file_path=self._file_path,
                error=str(exc),
            )
            self.app.call_from_thread(self._render_error, exc)
            return

        self.app.call_from_thread(
            self._render_contents,
            older_content.payload if older_content is not None else b"",
            newer_content.payload if newer_content is not None else b"",
            older_content.truncated if older_content is not None else False,
            newer_content.truncated if newer_content is not None else False,
        )

    def _render_error(self, error: Exception) -> None:
        self.query_one("#content-diff-status", Static).update(
            f"[#f38ba8]Failed to load file contents:[/] {escape(str(error))}"
        )

    def _render_contents(
        self,
        older_bytes: bytes,
        newer_bytes: bytes,
        older_truncated: bool,
        newer_truncated: bool,
    ) -> None:
        log = self.query_one("#content-diff-log", RichLog)
        status = self.query_one("#content-diff-status", Static)

        for side, truncated, payload in (
            ("older", older_truncated, older_bytes),
            ("newer", newer_truncated, newer_bytes),
        ):
            if truncated:
                status.update(
                    f"[#f9e2af]Skipped:[/] {side} copy exceeds "
                    f"{escape(format_size_bytes(MAX_CONTENT_DIFF_BYTES))}. No diff rendered."
                )
                return
            if _looks_binary(payload):
                status.update(
                    f"[#f9e2af]Skipped:[/] {side} copy looks binary (null bytes detected). No text diff rendered."
                )
                return

        older_lines = _decode_lines(older_bytes)
        newer_lines = _decode_lines(newer_bytes)
        diff_lines = list(
            difflib.unified_diff(
                older_lines,
                newer_lines,
                fromfile=f"{self._older_archive}:{self._file_path}",
                tofile=f"{self._newer_archive}:{self._file_path}",
                n=DIFF_CONTEXT_LINES,
                lineterm="",
            )
        )

        if not diff_lines:
            status.update(
                f"[#a6e3a1]No textual differences[/] ({escape(format_size_bytes(len(older_bytes)))} older, "
                f"{escape(format_size_bytes(len(newer_bytes)))} newer)."
            )
            return

        status.update(
            f"[#a6e3a1]Rendered[/] {len(diff_lines)} diff line(s) "
            f"({escape(format_size_bytes(len(older_bytes)))} -> {escape(format_size_bytes(len(newer_bytes)))})."
        )
        log.clear()
        for raw_line in diff_lines:
            log.write(_style_diff_line(raw_line))


def _looks_binary(payload: bytes) -> bool:
    if not payload:
        return False
    head = payload[:BINARY_SNIFF_BYTES]
    return b"\x00" in head


def _decode_lines(payload: bytes) -> list[str]:
    if not payload:
        return []
    text = payload.decode("utf-8", errors="replace")
    return text.splitlines()


def _style_diff_line(line: str) -> Text:
    if line.startswith("+++") or line.startswith("---"):
        return Text(line, style="bold #cba6f7")
    if line.startswith("@@"):
        return Text(line, style="bold #89b4fa")
    if line.startswith("+"):
        return Text(line, style="#a6e3a1")
    if line.startswith("-"):
        return Text(line, style="#f38ba8")
    return Text(line, style="#cdd6f4")
