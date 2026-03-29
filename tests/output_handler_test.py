from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest

from borgboi.core.output import CollectingOutputHandler, DefaultOutputHandler


def _capture_prints(
    monkeypatch: pytest.MonkeyPatch, handler: DefaultOutputHandler
) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    printed: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.append((args, kwargs))

    monkeypatch.setattr(handler._console, "print", fake_print)
    return printed


def test_on_stderr_renders_log_message_text_not_raw_json(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    printed = _capture_prints(monkeypatch, handler)

    handler.on_stderr(
        '{"type": "log_message", "time": 1771889251.639816, "levelname": "INFO", "name": "borg.output", '
        '"message": "Initializing cache transaction: Reading config"}\n'
    )

    assert len(printed) == 1
    rendered = str(printed[0][0][0])
    assert "Initializing cache transaction: Reading config" in rendered
    assert '{"type"' not in rendered


def test_on_stderr_renders_file_status(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    printed = _capture_prints(monkeypatch, handler)

    handler.on_stderr('{"type": "file_status", "status": "A", "path": "/tmp/example.txt"}\n')

    assert len(printed) == 1
    assert printed[0][0][0] == "[green]A[/] /tmp/example.txt"


def test_on_stderr_renders_progress_message_and_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    printed = _capture_prints(monkeypatch, handler)

    handler.on_stderr(
        '{"type": "progress_message", "operation": 1, "msgid": "cache.begin_transaction", "finished": false, '
        '"message": "Initializing cache transaction: Reading chunks", "time": 1771889251.6399653}\n'
    )
    handler.on_stderr(
        '{"type": "progress_message", "operation": 1, "msgid": "cache.begin_transaction", "finished": true, '
        '"time": 1771889251.640237}\n'
    )

    assert len(printed) == 2
    assert printed[0][0][0] == "[cyan]Initializing cache transaction: Reading chunks[/]"
    assert printed[1][0][0] == "[green]✓[/] Cache initialization complete"


def test_on_stderr_falls_back_for_non_json_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    printed = _capture_prints(monkeypatch, handler)

    handler.on_stderr("plain stderr line\n")

    assert len(printed) == 1
    assert printed[0][0][0] == "[dim]plain stderr line[/]"


def test_on_stderr_suppresses_stats_separator_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    printed = _capture_prints(monkeypatch, handler)

    handler.on_stderr(
        '{"type": "log_message", "time": 1771889252.0842347, "message": "----------------", '
        '"levelname": "INFO", "name": "borg.output.stats"}\n'
    )

    assert printed == []


def test_render_command_streams_lines_through_on_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = DefaultOutputHandler()
    events: list[tuple[str, Any]] = []

    def fake_rule(*args: Any, **kwargs: Any) -> None:
        events.append(("rule", args[0]))

    @contextmanager
    def fake_status(*args: Any, **kwargs: Any) -> Generator[None]:
        events.append(("status_enter", kwargs["status"]))
        try:
            yield
        finally:
            events.append(("status_exit", kwargs["spinner"]))

    def fake_stderr(line: str) -> None:
        events.append(("stderr", line))

    monkeypatch.setattr(handler._console, "rule", fake_rule)
    monkeypatch.setattr(handler._console, "status", fake_status)
    monkeypatch.setattr(
        handler._console, "print", lambda *args, **kwargs: events.append(("print", args[0] if args else ""))
    )
    monkeypatch.setattr(handler, "on_stderr", fake_stderr)

    handler.render_command(
        "Creating new archive",
        "Archive created successfully",
        ["first line\n", "second line\n"],
        spinner="dots",
        ruler_color="#abcdef",
    )

    assert events == [
        ("rule", "[bold #cdd6f4]Creating new archive[/]"),
        ("status_enter", "[bold #89b4fa]Creating new archive[/]"),
        ("stderr", "first line\n"),
        ("stderr", "second line\n"),
        ("status_exit", "dots"),
        ("rule", ":heavy_check_mark: [bold #cdd6f4]Archive created successfully[/]"),
        ("print", ""),
    ]


def test_collecting_output_handler_render_command_collects_stderr_lines() -> None:
    handler = CollectingOutputHandler()

    handler.render_command("status", "success", ["one\n", "two\n"])

    assert handler.stderr_lines == ["one\n", "two\n"]
