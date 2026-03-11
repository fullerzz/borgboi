import json
from typing import Any

import pytest
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

from borgboi import rich_utils
from borgboi.cli import cli
from borgboi.config import CONFIG_ENV_VAR_MAP
from tests.cli_helpers import invoke_cli


def _clear_borgboi_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all BORGBOI_* environment variables to ensure clean test state."""
    for env_var in CONFIG_ENV_VAR_MAP.values():
        monkeypatch.delenv(env_var, raising=False)


def test_config_show_pretty_print_panel(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_borgboi_env_vars(monkeypatch)

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed

    panel = printed[0]
    assert isinstance(panel, Panel)
    # Without env overrides, we get Syntax highlighting
    assert isinstance(panel.renderable, Syntax)
    assert "BorgBoi Config" in str(panel.title)

    syntax = panel.renderable
    assert "aws:" in syntax.code


def test_config_show_no_pretty_print(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _clear_borgboi_env_vars(monkeypatch)
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert "aws:" in captured.out
    assert printed == []


def test_config_show_json_format_pretty_print(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test JSON format with pretty-print enabled."""
    _clear_borgboi_env_vars(monkeypatch)

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed

    panel = printed[0]
    assert isinstance(panel, Panel)
    # Without env overrides, we get Syntax highlighting
    assert isinstance(panel.renderable, Syntax)

    syntax = panel.renderable
    # JSON should contain aws key with proper JSON syntax
    assert '"aws"' in syntax.code


def test_config_show_json_format_pretty_print_with_env_override(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test JSON format with env overrides uses syntax panel and includes override mapping."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed

    panel = printed[0]
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Syntax)

    syntax = panel.renderable
    assert '"_env_overrides"' in syntax.code
    assert '"aws.s3_bucket"' in syntax.code
    assert '"BORGBOI_AWS__S3_BUCKET"' in syntax.code


def test_config_show_json_format_no_pretty_print(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test JSON format without pretty-print."""
    _clear_borgboi_env_vars(monkeypatch)
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--format", "json", "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert '"aws"' in captured.out
    assert printed == []


def test_config_show_json_format_no_pretty_print_with_env_override(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test JSON format without pretty-print includes env overrides mapping."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--format", "json", "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed == []

    json_start = captured.out.find("{")
    assert json_start != -1
    parsed = json.loads(captured.out[json_start:])
    assert "_env_overrides" in parsed
    assert parsed["_env_overrides"]["aws.s3_bucket"] == "BORGBOI_AWS__S3_BUCKET"
    assert "# Values from environment variables:" not in captured.out


def test_config_show_custom_path(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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

    exit_code = invoke_cli(cli, ["config", "show", "--path", str(config_file), "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Configuration from: {config_file}" in captured.out


def test_config_show_custom_path_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error handling when custom path doesn't exist."""
    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--path", "/nonexistent/config.yaml"])

    assert exit_code == 1
    assert any("not found" in str(p).lower() for p in printed)


def test_config_show_with_env_override_uses_tree(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that when env vars override config, Tree format is used instead of Syntax."""
    _clear_borgboi_env_vars(monkeypatch)
    # Set an env var to trigger tree format
    monkeypatch.setenv("BORGBOI_OFFLINE", "true")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed

    # With env overrides, we get Tree format
    panel = printed[0]
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Tree)


def test_config_show_env_override_legend_displayed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the yellow values legend is displayed when env overrides exist."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show"])

    assert exit_code == 0
    assert any("Yellow values" in str(p) for p in printed)


def test_config_show_no_pretty_print_with_env_override(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that plain text output includes env override comments when env vars are set."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert "aws:" in captured.out
    assert "# Values from environment variables:" in captured.out
    assert "aws.s3_bucket <- BORGBOI_AWS__S3_BUCKET" in captured.out
    assert printed == []


def test_config_show_tree_format(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test explicit tree format output."""
    _clear_borgboi_env_vars(monkeypatch)

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--format", "tree"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration from:" in captured.out
    assert printed

    # Tree format always uses Tree renderable
    panel = printed[0]
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Tree)


def test_config_show_multiple_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test display with multiple env var overrides."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_OFFLINE", "true")
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")
    monkeypatch.setenv("BORGBOI_BORG__COMPRESSION", "lz4")

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    exit_code = invoke_cli(cli, ["config", "show", "--no-pretty-print"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "offline <- BORGBOI_OFFLINE" in captured.out
    assert "aws.s3_bucket <- BORGBOI_AWS__S3_BUCKET" in captured.out
    assert "borg.compression <- BORGBOI_BORG__COMPRESSION" in captured.out
