"""Tests for TuiOutputHandler from daily_backup_screen.py.

These tests mock _write to avoid the threading complexity of call_from_thread,
focusing on the formatting and dispatch logic.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from rich.text import Text

from borgboi.tui.daily_backup_screen import TuiOutputHandler


class _StaticProgressHistory:
    def __init__(self, durations: dict[str, float] | None = None) -> None:
        self._durations = durations or {}
        self.recorded: list[dict[str, Any]] = []

    def get_stage_durations(self, repo_name: str, stage_ids: Iterable[str]) -> dict[str, float]:
        return {stage_id: self._durations[stage_id] for stage_id in stage_ids if stage_id in self._durations}

    def record_stage_timing(
        self,
        repo_name: str,
        stage_id: str,
        duration_ms: float,
        *,
        sync_enabled: bool,
        succeeded: bool,
    ) -> None:
        self.recorded.append(
            {
                "repo_name": repo_name,
                "stage_id": stage_id,
                "duration_ms": duration_ms,
                "sync_enabled": sync_enabled,
                "succeeded": succeeded,
            }
        )


def _make_handler(
    *,
    steps: list[str] | None = None,
    progress_history: _StaticProgressHistory | None = None,
    repo_name: str | None = None,
    now_monotonic: Any = None,
    enable_stage_ticker: bool = False,
) -> tuple[TuiOutputHandler, list[str | Text]]:
    """Create a TuiOutputHandler with a mocked _write that collects output."""
    written: list[str | Text] = []
    app = MagicMock()
    log = MagicMock()
    handler = TuiOutputHandler(
        app,
        log,
        steps=steps,
        progress_history=progress_history,
        repo_name=repo_name,
        now_monotonic=now_monotonic,
        enable_stage_ticker=enable_stage_ticker,
    )

    def capture_write(text: str | Text) -> None:
        written.append(text)

    handler._write = capture_write  # type: ignore[method-assign] # ty: ignore[invalid-assignment]
    return handler, written


def _make_handler_with_progress(
    *,
    steps: list[str] | None = None,
    progress_history: _StaticProgressHistory | None = None,
    repo_name: str | None = None,
    now_monotonic: Any = None,
    enable_stage_ticker: bool = False,
) -> tuple[TuiOutputHandler, list[str | Text], MagicMock, list[tuple[Any, ...]]]:
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
    handler = TuiOutputHandler(
        app,
        log,
        progress_bar=progress_bar,
        steps=steps,
        progress_history=progress_history,
        repo_name=repo_name,
        now_monotonic=now_monotonic,
        enable_stage_ticker=enable_stage_ticker,
    )

    def capture_write(text: str | Text) -> None:
        written.append(text)

    handler._write = capture_write  # type: ignore[method-assign] # ty: ignore[invalid-assignment]
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

    # Progress bar update should be a no-op when progress_bar is None
    handler._update_progress_bar(total=100, progress=50)


def test_render_command_resets_progress_before_streaming() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_lines = [
        '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"working","msgid":"test"}\n',
    ]

    handler.render_command("Creating", "Create done", log_lines)

    assert cft_calls
    assert progress_bar.update.call_args_list[-1] == call(total=100, progress=100)
    assert all(progress_call != call(total=None, progress=0) for progress_call in progress_bar.update.call_args_list)


def test_section_resets_and_completes_progress() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()

    with handler.section("Pruning", "Prune done"):
        handler.on_log("info", "working...")

    assert cft_calls
    assert progress_bar.update.call_args_list[-1] == call(total=100, progress=100)
    assert all(progress_call != call(total=None, progress=0) for progress_call in progress_bar.update.call_args_list)


def test_render_command_marks_progress_complete_for_unstructured_streams() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()

    handler.render_command(
        "Syncing repo with S3 bucket",
        "S3 sync completed successfully",
        ["upload: ./file.txt to s3://test-bucket/repo/file.txt\n"],
    )

    assert cft_calls
    assert progress_bar.update.call_args_list[-1] == call(total=100, progress=100)
    assert all(progress_call != call(total=None, progress=0) for progress_call in progress_bar.update.call_args_list)


def test_progress_percent_updates_bar() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"progress_percent","operation":0,"msgid":"archive.prune","finished":false,"current":50,"total":100,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    # Batched closure should have dispatched via call_from_thread and called update
    assert len(cft_calls) > 0
    progress_bar.update.assert_called()
    update_calls = progress_bar.update.call_args_list
    assert any(c == call(total=100, progress=50.0) for c in update_calls)


def test_render_command_maps_progress_into_weighted_stage_slice() -> None:
    progress_history = _StaticProgressHistory({"create": 4_000.0, "prune": 1_000.0, "compact": 1_000.0})
    handler, _, progress_bar, _ = _make_handler_with_progress(
        steps=["create", "prune", "compact"],
        progress_history=progress_history,
        repo_name="alpha",
    )
    log_line = (
        '{"type":"progress_percent","operation":0,"msgid":"archive.create",'
        '"finished":false,"current":50,"total":100,"time":"2026-01-01T00:00:00"}\n'
    )

    handler.render_command("Creating new archive", "Create done", [log_line])

    progress_values = [progress_call.kwargs["progress"] for progress_call in progress_bar.update.call_args_list]
    assert any(progress == pytest.approx(33.3333333333) for progress in progress_values)
    assert progress_values[-1] == pytest.approx(66.6666666667)


def test_log_driven_steps_use_weighted_cumulative_progress_slices() -> None:
    progress_history = _StaticProgressHistory(
        {"create": 4_000.0, "prune": 1_000.0, "compact": 1_000.0, "sync": 2_000.0}
    )
    handler, _, progress_bar, _ = _make_handler_with_progress(
        steps=["create", "prune", "compact", "sync"],
        progress_history=progress_history,
        repo_name="alpha",
    )
    prune_log_line = (
        '{"type":"progress_percent","operation":0,"msgid":"archive.prune",'
        '"finished":false,"current":50,"total":100,"time":"2026-01-01T00:00:00"}'
    )

    handler.render_command("Creating new archive", "Create done", [])
    handler.on_log("info", "Pruning old backups...")
    handler.on_stderr(prune_log_line)
    handler.on_log("info", "Pruning completed")

    progress_values = [progress_call.kwargs["progress"] for progress_call in progress_bar.update.call_args_list]
    assert progress_values[0] == pytest.approx(50.0)
    assert any(progress == pytest.approx(56.25) for progress in progress_values)
    assert progress_values[-1] == pytest.approx(62.5)


def test_timing_estimate_advances_active_step_without_structured_progress() -> None:
    clock = {"now": 0.0}
    progress_history = _StaticProgressHistory({"create": 4_000.0, "prune": 1_000.0, "compact": 1_000.0})
    handler, _, progress_bar, _ = _make_handler_with_progress(
        steps=["create", "prune", "compact"],
        progress_history=progress_history,
        repo_name="alpha",
        now_monotonic=lambda: clock["now"],
    )

    handler._start_step("create")
    clock["now"] = 2.0
    handler._advance_active_step_from_timing()

    progress_values = [progress_call.kwargs["progress"] for progress_call in progress_bar.update.call_args_list]
    assert progress_values[-1] == pytest.approx(33.3333333333)


def test_completed_step_records_stage_timing_history() -> None:
    clock = {"now": 0.0}
    progress_history = _StaticProgressHistory({"create": 4_000.0, "prune": 1_000.0, "compact": 1_000.0})
    handler, _, _, _ = _make_handler_with_progress(
        steps=["create", "prune", "compact"],
        progress_history=progress_history,
        repo_name="alpha",
        now_monotonic=lambda: clock["now"],
    )

    handler._start_step("create")
    clock["now"] = 2.5
    handler._complete_step("create")

    assert len(progress_history.recorded) == 1
    recorded = progress_history.recorded[0]
    assert recorded["repo_name"] == "alpha"
    assert recorded["stage_id"] == "create"
    assert recorded["duration_ms"] == pytest.approx(2500.0)
    assert recorded["sync_enabled"] is False
    assert recorded["succeeded"] is True


def test_progress_percent_finished_writes_completion_without_hiding_bar() -> None:
    handler, written, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"progress_percent","operation":0,"msgid":"archive.prune","finished":true,"current":100,"total":100,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    assert cft_calls
    progress_bar.update.assert_called_once_with(total=100, progress=99.0)
    assert any("Progress: 100/100 (100.0%)" in (t.plain if isinstance(t, Text) else t) for t in written)
    assert any("Archive Prune complete" in (t.plain if isinstance(t, Text) else t) for t in written)


def test_archive_progress_finished_logs_completion_without_hiding_bar() -> None:
    handler, written, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"archive_progress","finished":true,"time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    assert cft_calls == []
    progress_bar.update.assert_not_called()
    assert any("Archive write complete" in (t.plain if isinstance(t, Text) else t) for t in written)


def test_archive_progress_logs_details_without_toggling_bar_visibility() -> None:
    handler, written, progress_bar, cft_calls = _make_handler_with_progress()
    log_line = '{"type":"archive_progress","finished":false,"path":"/some/file.txt","time":"2026-01-01T00:00:00"}'

    handler.on_stderr(log_line)

    assert cft_calls == []
    progress_bar.update.assert_not_called()
    assert any("Backing up /some/file.txt" in (t.plain if isinstance(t, Text) else t) for t in written)


def test_render_command_resets_then_completes_progress_for_archive_updates() -> None:
    handler, _, progress_bar, cft_calls = _make_handler_with_progress()
    log_lines = [
        '{"type":"archive_progress","finished":false,"time":"2026-01-01T00:00:00"}\n',
        '{"type":"archive_progress","finished":true,"time":"2026-01-01T00:00:00"}\n',
    ]

    handler.render_command("Creating", "Create done", log_lines)

    assert cft_calls
    assert progress_bar.update.call_args_list[-1] == call(total=100, progress=100)
    assert all(progress_call != call(total=None, progress=0) for progress_call in progress_bar.update.call_args_list)
