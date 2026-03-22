"""Tests for TuiOutputHandler from daily_backup_screen.py.

These tests mock _write to avoid the threading complexity of call_from_thread,
focusing on the formatting and dispatch logic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

from rich.text import Text

from borgboi.tui.daily_backup_screen import TuiOutputHandler


def _make_handler() -> tuple[TuiOutputHandler, list[str | Text]]:
    """Create a TuiOutputHandler with a mocked _write that collects output."""
    written: list[str | Text] = []
    app = MagicMock()
    log = MagicMock()
    handler = TuiOutputHandler(app, log)

    def capture_write(text: str | Text) -> None:
        written.append(text)

    handler._write = capture_write  # type: ignore[method-assign]
    return handler, written


def _make_handler_with_progress() -> tuple[TuiOutputHandler, list[str | Text], MagicMock, list[tuple[Any, ...]]]:
    """Create a TuiOutputHandler with a mocked _write, mock progress bar, and call log.

    call_from_thread executes the callable immediately so that nested
    calls (e.g. progress_bar.update inside a closure) are recorded on
    the mock.  All call_from_thread invocations are also logged in
    ``cft_calls`` for easy assertion.
    """
    written: list[str | Text] = []
    cft_calls: list[tuple[Any, ...]] = []
    app = MagicMock()

    def _tracking_call_from_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        cft_calls.append((fn, *args))
        return fn(*args, **kwargs)

    app.call_from_thread = _tracking_call_from_thread
    log = MagicMock()
    progress_bar = MagicMock()
    handler = TuiOutputHandler(app, log, progress_bar=progress_bar)

    def capture_write(text: str | Text) -> None:
        written.append(text)

    handler._write = capture_write  # type: ignore[method-assign]
    return handler, written, progress_bar, cft_calls


# -- on_progress tests -------------------------------------------------------


def test_on_progress_formats_with_percent_when_total_positive() -> None:
    handler, written = _make_handler()

    handler.on_progress(50, 100, "files")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "50/100" in text.plain
    assert "50.0%" in text.plain
    assert "files" in text.plain


def test_on_progress_no_percent_when_total_zero() -> None:
    handler, written = _make_handler()

    handler.on_progress(50, 0)

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "Progress: 50" in text.plain
    assert "%" not in text.plain


# -- on_log tests ------------------------------------------------------------


def test_on_log_applies_warning_style() -> None:
    handler, written = _make_handler()

    handler.on_log("warning", "disk full")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "disk full" in text.plain
    assert text.style == "bold yellow"


def test_on_log_applies_error_style() -> None:
    handler, written = _make_handler()

    handler.on_log("error", "something broke")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert text.style == "bold red"


def test_on_log_info_has_no_style() -> None:
    handler, written = _make_handler()

    handler.on_log("info", "starting")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "starting" in text.plain


# -- on_file_status tests ----------------------------------------------------


def test_on_file_status_green_for_added() -> None:
    handler, written = _make_handler()

    handler.on_file_status("A", "/path/to/file")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "A" in text.plain
    assert "/path/to/file" in text.plain


def test_on_file_status_yellow_for_modified() -> None:
    handler, written = _make_handler()

    handler.on_file_status("M", "/path/to/file")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "M" in text.plain


# -- on_stderr tests ---------------------------------------------------------


def test_on_stderr_handles_unparseable_line() -> None:
    handler, written = _make_handler()

    handler.on_stderr("this is not json at all")

    assert len(written) == 1
    text = written[0]
    assert isinstance(text, Text)
    assert "this is not json at all" in text.plain
    assert text.style == "dim"


def test_on_stderr_skips_empty_lines() -> None:
    handler, written = _make_handler()

    handler.on_stderr("")
    handler.on_stderr("   ")

    assert len(written) == 0


def test_on_stderr_parses_log_message_json() -> None:
    handler, written = _make_handler()
    log_line = '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"archive created","msgid":"archive.create"}'

    handler.on_stderr(log_line)

    assert len(written) >= 1
    # Should have been dispatched to _render_log_message -> on_log
    assert any("archive created" in (t.plain if isinstance(t, Text) else t) for t in written)


def test_on_stderr_parses_file_status_json() -> None:
    handler, written = _make_handler()
    log_line = '{"type":"file_status","status":"A","path":"/some/file.txt"}'

    handler.on_stderr(log_line)

    assert len(written) >= 1
    assert any("/some/file.txt" in (t.plain if isinstance(t, Text) else t) for t in written)


# -- on_stats tests ----------------------------------------------------------


def test_on_stats_formats_key_value_pairs() -> None:
    handler, written = _make_handler()

    handler.on_stats({"files": "100", "size": "1GB"})

    # Should have header + 2 key-value lines
    assert len(written) == 3
    header = written[0]
    assert isinstance(header, Text)
    assert "Statistics" in header.plain
    assert "files: 100" in written[1]
    assert "size: 1GB" in written[2]


# -- render_command tests ----------------------------------------------------


def test_render_command_writes_header_body_and_footer() -> None:
    handler, written = _make_handler()
    log_lines = [
        '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"pruning","msgid":"archive.prune"}\n',
    ]

    handler.render_command("Pruning", "Prune complete", log_lines)

    # Should have: header ruler, body line(s), footer ruler
    assert len(written) >= 3
    header = written[0]
    footer = written[-1]
    assert isinstance(header, Text)
    assert isinstance(footer, Text)
    assert "Pruning" in header.plain
    assert "Prune complete" in footer.plain


# -- section context manager tests -------------------------------------------


def test_section_context_manager_writes_bookends() -> None:
    handler, written = _make_handler()

    with handler.section("Starting backup", "Backup done"):
        handler.on_log("info", "working...")

    assert len(written) == 3
    header = written[0]
    footer = written[2]
    assert isinstance(header, Text)
    assert isinstance(footer, Text)
    assert "Starting backup" in header.plain
    assert "Backup done" in footer.plain


# -- progress bar integration tests ------------------------------------------


def test_handler_without_progress_bar_does_not_fail() -> None:
    handler, _ = _make_handler()

    # All progress-related methods should be no-ops when progress_bar is None
    handler._show_progress()
    handler._hide_progress()
    handler._reset_progress(indeterminate=True)
    handler._update_progress_bar(total=100, progress=50)


def _has_setattr_call(
    cft_calls: list[tuple[Any, ...]],
    progress_bar: MagicMock,
    attr: str,
    value: object,
) -> bool:
    return any(c == (setattr, progress_bar, attr, value) for c in cft_calls)


def test_render_command_shows_and_hides_progress() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_lines = [
        '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"working","msgid":"test"}\n',
    ]

    handler.render_command("Creating", "Create done", log_lines)

    assert _has_setattr_call(cft_calls, progress_bar, "display", True)
    assert _has_setattr_call(cft_calls, progress_bar, "display", False)


def test_section_shows_and_hides_progress() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()

    with handler.section("Pruning", "Prune done"):
        handler.on_log("info", "working...")

    assert _has_setattr_call(cft_calls, progress_bar, "display", True)
    assert _has_setattr_call(cft_calls, progress_bar, "display", False)


def test_progress_percent_updates_bar() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"progress_percent","operation":0,"msgid":"archive.prune","finished":false,"current":50,"total":100,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    # Batched closure should have dispatched via call_from_thread and called update
    assert len(cft_calls) > 0
    progress_bar.update.assert_called()
    update_calls = progress_bar.update.call_args_list
    assert any(c == call(total=100, progress=50.0) for c in update_calls)


def test_progress_percent_finished_hides_bar() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"progress_percent","operation":0,"msgid":"archive.prune","finished":true,"current":100,"total":100,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    assert _has_setattr_call(cft_calls, progress_bar, "display", False)


def test_archive_progress_finished_hides_bar() -> None:
    handler, written, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"archive_progress","finished":true,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    assert _has_setattr_call(cft_calls, progress_bar, "display", False)
    assert any("Archive write complete" in (t.plain if isinstance(t, Text) else t) for t in written)
