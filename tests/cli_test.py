import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import borgboi.cli as cli_package
from tests.cli_helpers import invoke_cli

cli_main = importlib.import_module("borgboi.cli.main")


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["--help"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "repo" in captured.out
    assert "backup" in captured.out
    assert "config" in captured.out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["version"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.startswith("borgboi ")


def test_lazy_commands_are_importable() -> None:
    for name in ("repo", "backup", "s3", "exclusions", "config"):
        assert cli_main.app[name] is not None


def test_package_exports_root_app() -> None:
    assert cli_package.app is cli_main.app
    assert cli_package.cli is cli_main.cli


def test_repo_create(
    monkeypatch: pytest.MonkeyPatch,
    repo_storage_dir: Path,
    backup_target_dir: Path,
) -> None:
    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def create_repo(
            self,
            *,
            path: str,
            backup_target: str,
            name: str,
            passphrase: str | None = None,
        ) -> object:
            _ = backup_target, passphrase
            return SimpleNamespace(path=path, name=name)

    monkeypatch.setattr(cli_main, "Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_storage_dir),
            "--backup-target",
            str(backup_target_dir),
            "--name",
            "test-repo",
        ],
    )

    assert exit_code == 0


def test_root_offline_flag_is_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["--offline", "s3", "stats"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "offline mode" in captured.out.lower()
