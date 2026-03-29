import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import borgboi.cli as cli_package
import borgboi.config as config_module
import borgboi.core.logging as logging_module
from tests.cli_helpers import invoke_cli

cli_main = importlib.import_module("borgboi.cli.main")


def _read_active_log_entries() -> list[dict[str, object]]:
    log_file = logging_module._LoggingState.active_log_file
    assert log_file is not None
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


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

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

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


def test_cli_logging_redacts_passphrase_tokens(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    config_module.get_config.cache_clear()
    repo_path = tmp_path / "repo"
    backup_target = tmp_path / "backup-target"

    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_path),
            "--backup-target",
            str(backup_target),
            "--name",
            "test-repo",
            "--passphrase",
            "super-secret",
        ],
    )

    assert exit_code == 0

    logs_dir = config_module.resolve_home_dir() / ".borgboi" / "logs"
    log_file = next(logs_dir.glob("borgboi_*.log"))
    log_entries = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    command_entry = next(entry for entry in log_entries if entry["event"] == "Running CLI command")

    assert command_entry["tokens"][-2:] == ["--passphrase", "[REDACTED]"]
    assert "super-secret" not in log_file.read_text()


def test_repo_create_logs_structured_cli_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"

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

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setenv("BORGBOI_HOME", str(home_dir))
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    config_module.get_config.cache_clear()

    repo_path = tmp_path / "repo"
    backup_target = tmp_path / "backup-target"
    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_path),
            "--backup-target",
            str(backup_target),
            "--name",
            "test-repo",
        ],
    )

    assert exit_code == 0

    log_entries = _read_active_log_entries()
    assert any(
        entry["event"] == "Running repository create command"
        and entry["logger"] == "borgboi.cli.repo"
        and entry["repo_name"] == "test-repo"
        and entry["repo_path"] == str(repo_path)
        and entry["backup_target"] == str(backup_target)
        for entry in log_entries
    )
    assert any(
        entry["event"] == "Repository create command completed"
        and entry["logger"] == "borgboi.cli.repo"
        and entry["repo_name"] == "test-repo"
        and entry["repo_path"] == str(repo_path)
        for entry in log_entries
    )


def test_s3_stats_logs_offline_skip_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"

    monkeypatch.setenv("BORGBOI_HOME", str(home_dir))
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    config_module.get_config.cache_clear()

    exit_code = invoke_cli(cli_main.cli, ["--offline", "s3", "stats"])

    assert exit_code == 0

    log_entries = _read_active_log_entries()
    assert any(
        entry["event"] == "Skipping S3 stats command in offline mode"
        and entry["logger"] == "borgboi.cli.s3"
        and entry["level"] == "info"
        for entry in log_entries
    )
