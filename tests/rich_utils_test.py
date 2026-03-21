import pytest

from borgboi import rich_utils
from borgboi.core import output as output_module


def test_render_cmd_output_lines_reuses_default_output_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[object] = []
    rendered: list[tuple[str, str, list[str], str, str]] = []

    class FakeOutputHandler:
        def __init__(self) -> None:
            created.append(object())

        def render_command(
            self,
            status: str,
            success_msg: str,
            log_stream: list[str],
            *,
            spinner: str = "point",
            ruler_color: str = "#74c7ec",
        ) -> None:
            rendered.append((status, success_msg, list(log_stream), spinner, ruler_color))

    monkeypatch.setattr(output_module, "DefaultOutputHandler", FakeOutputHandler)
    rich_utils._get_default_output_handler.cache_clear()

    rich_utils.render_cmd_output_lines("first", "done", ["line one\n"])
    rich_utils.render_cmd_output_lines("second", "done again", ["line two\n"], spinner="dots", ruler_color="#abcdef")

    assert len(created) == 1
    assert rendered == [
        ("first", "done", ["line one\n"], "point", "#74c7ec"),
        ("second", "done again", ["line two\n"], "dots", "#abcdef"),
    ]

    rich_utils._get_default_output_handler.cache_clear()
