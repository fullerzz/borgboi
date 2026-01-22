from typing import Any

import pytest
from click.testing import CliRunner
from rich.panel import Panel
from rich.syntax import Syntax

from borgboi import rich_utils
from borgboi.cli import cli


def test_config_show_pretty_print_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert "Configuration from:" in result.stdout
    assert printed

    panel = printed[0]
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Syntax)
    assert "BorgBoi Config" in str(panel.title)

    syntax = panel.renderable
    assert "aws:" in syntax.code


def test_config_show_no_pretty_print(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--no-pretty-print"])

    assert result.exit_code == 0
    assert "Configuration from:" in result.stdout
    assert "aws:" in result.stdout
    assert printed == []
