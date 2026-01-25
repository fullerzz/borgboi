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


def test_config_show_json_format_pretty_print(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test JSON format with pretty-print enabled."""
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--format", "json"])

    assert result.exit_code == 0
    assert "Configuration from:" in result.stdout
    assert printed

    panel = printed[0]
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Syntax)

    syntax = panel.renderable
    # JSON should contain aws key with proper JSON syntax
    assert '"aws"' in syntax.code


def test_config_show_json_format_no_pretty_print(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test JSON format without pretty-print."""
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--format", "json", "--no-pretty-print"])

    assert result.exit_code == 0
    assert "Configuration from:" in result.stdout
    # JSON output should be in stdout
    assert '"aws"' in result.stdout
    assert printed == []


def test_config_show_custom_path(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test loading config from a custom path."""
    import yaml as pyyaml

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    # Create a temporary config file
    config_file = tmp_path / "custom_config.yaml"  # type: ignore[operator]
    config_data = {
        "aws": {"s3_bucket": "custom-bucket"},
        "borg": {"compression": "lz4"},
    }
    config_file.write_text(pyyaml.safe_dump(config_data))

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--path", str(config_file), "--no-pretty-print"])

    assert result.exit_code == 0
    assert f"Configuration from: {config_file}" in result.stdout


def test_config_show_custom_path_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error handling when custom path doesn't exist."""
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "show", "--path", "/nonexistent/config.yaml"])

    assert result.exit_code == 1
    # Check that error message was printed
    assert any("not found" in str(p).lower() for p in printed)
