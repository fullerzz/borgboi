from contextlib import contextmanager
from pathlib import Path
from platform import system
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.config import Config
from borgboi.core.errors import ValidationError
from borgboi.core.orchestrator import Orchestrator
from borgboi.core.output import CollectingOutputHandler
from borgboi.models import BorgBoiRepo


def _build_repo(name: str = "test-repo") -> BorgBoiRepo:
    return BorgBoiRepo(
        path="/repo/test-repo",
        backup_target="/backup/source",
        name=name,
        hostname="localhost",
        os_platform="Darwin" if system() == "Darwin" else "Linux",
        metadata=None,
        passphrase_migrated=True,
    )


class RecordingOutputHandler(CollectingOutputHandler):
    def __init__(self) -> None:
        super().__init__()
        self.render_calls: list[dict[str, Any]] = []

    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Any,
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        self.render_calls.append(
            {
                "status": status,
                "success_msg": success_msg,
                "spinner": spinner,
                "ruler_color": ruler_color,
                "log_stream": log_stream,
            }
        )
        super().render_command(
            status,
            success_msg,
            log_stream,
            spinner=spinner,
            ruler_color=ruler_color,
        )


class LegacyOutputHandler:
    def __init__(self) -> None:
        self.log_messages: list[tuple[str, str, dict[str, Any]]] = []
        self.stderr_lines: list[str] = []

    def on_progress(self, current: int, total: int, info: str | None = None) -> None:
        _ = current, total, info

    def on_log(self, level: str, message: str, **kwargs: Any) -> None:
        self.log_messages.append((level, message, kwargs))

    def on_file_status(self, status: str, path: str) -> None:
        _ = status, path

    def on_stdout(self, line: str) -> None:
        _ = line

    def on_stderr(self, line: str) -> None:
        self.stderr_lines.append(line)

    def on_stats(self, stats: dict[str, Any]) -> None:
        _ = stats

    @contextmanager
    def section(self, status: str, success_msg: str):
        _ = status, success_msg
        yield


def test_backup_uses_default_shared_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    orchestrator.backup(repo)

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    assert not repo_specific_excludes_path.exists()
    borg_client.create.assert_called_once()
    assert borg_client.create.call_args.kwargs["exclude_file"] == default_excludes_path.as_posix()


def test_backup_prefers_repo_specific_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    repo_specific_excludes_path.write_text("*.iso\n")

    orchestrator.backup(repo)

    borg_client.create.assert_called_once()
    assert borg_client.create.call_args.kwargs["exclude_file"] == repo_specific_excludes_path.as_posix()
    assert borg_client.create.call_args.kwargs["exclude_file"] != default_excludes_path.as_posix()


def test_backup_returns_created_archive_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    expected_archive_name = "2026-02-22_00:02:27"
    monkeypatch.setattr("borgboi.core.orchestrator.create_archive_name", lambda: expected_archive_name)

    created_archive_name = orchestrator.backup(repo)

    assert created_archive_name == expected_archive_name
    assert borg_client.create.call_args.kwargs["archive_name"] == expected_archive_name


def test_backup_renders_borg_create_stream_via_output_handler(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = iter(["archive line\n", "archive line 2\n"])
    output_handler = RecordingOutputHandler()

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
        output_handler=output_handler,
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    archive_name = orchestrator.backup(repo)

    assert archive_name
    assert len(output_handler.render_calls) == 1
    render_call = output_handler.render_calls[0]
    assert render_call["status"] == "Creating new archive"
    assert render_call["success_msg"] == "Archive created successfully"
    assert render_call["spinner"] == "point"
    assert render_call["ruler_color"] == "#74c7ec"
    assert output_handler.stderr_lines == ["archive line\n", "archive line 2\n"]
    assert output_handler.log_messages == [
        ("info", "Archive created successfully", {"archive_name": archive_name, "repo": repo.name})
    ]


def test_backup_falls_back_for_legacy_output_handlers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = iter(["archive line\n", "archive line 2\n"])
    output_handler = LegacyOutputHandler()

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
        output_handler=cast(Any, output_handler),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    archive_name = orchestrator.backup(repo)

    assert archive_name
    assert output_handler.stderr_lines == ["archive line\n", "archive line 2\n"]
    assert output_handler.log_messages == [
        ("info", "Archive created successfully", {"archive_name": archive_name, "repo": repo.name})
    ]


def test_backup_raises_when_no_excludes_files_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    with pytest.raises(ValidationError, match="Exclude list must be created before performing a backup"):
        orchestrator.backup(repo)

    borg_client.create.assert_not_called()


def test_get_exclusions_uses_default_shared_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, Mock()),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n.cache/\n")

    assert orchestrator.get_exclusions(repo) == ["*.tmp", ".cache/"]


def test_get_exclusions_prefers_repo_specific_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, Mock()),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    repo_specific_excludes_path.write_text("*.iso\n")

    assert orchestrator.get_exclusions(repo) == ["*.iso"]
