from typing import Any

import pytest

from borgboi.core.output import DefaultOutputHandler


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
