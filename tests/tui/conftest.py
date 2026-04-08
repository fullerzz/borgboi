from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from borgboi.clients.borg import RepoArchive, RepoInfo
from borgboi.config import Config
from borgboi.core.models import RepoMetadata, Repository, RetentionPolicy
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp


def build_repo(name: str = "alpha", path: str | None = None) -> BorgBoiRepo:
    """Build a minimal BorgBoiRepo for TUI testing."""
    return BorgBoiRepo(
        name=name,
        path=path or f"/Users/test/{name}",
        hostname="test-host",
        os_platform="Darwin",
        backup_target="local",
        metadata=None,
    )


class FakeBorg:
    """Fake Borg client that records calls without executing real Borg commands."""

    def __init__(self) -> None:
        self.create_calls: list[str] = []
        self.prune_calls: list[str] = []
        self.compact_calls: list[str] = []

    def create(self, repo_path: str, backup_target: str, **_kwargs: Any) -> Generator[str]:
        self.create_calls.append(f"{repo_path}:{backup_target}")
        yield (
            '{"type":"log_message","name":"borg.output.info","levelname":"INFO",'
            '"message":"create","msgid":"archive.create","time":"2026-01-01T00:00:00"}\n'
        )

    def prune(self, repo_path: str, **_kwargs: Any) -> Generator[str]:
        self.prune_calls.append(repo_path)
        yield (
            '{"type":"log_message","name":"borg.output.info","levelname":"INFO",'
            '"message":"prune","msgid":"archive.prune","time":"2026-01-01T00:00:00"}\n'
        )

    def compact(self, repo_path: str, **_kwargs: Any) -> Generator[str]:
        self.compact_calls.append(repo_path)
        yield (
            '{"type":"log_message","name":"borg.output.info","levelname":"INFO",'
            '"message":"compact","msgid":"archive.compact","time":"2026-01-01T00:00:00"}\n'
        )

    def info(self, repo_path: str, **_kwargs: Any) -> dict[str, str]:
        return {"repository": repo_path}


class FakeStorage:
    """Fake storage that records save calls."""

    def __init__(self) -> None:
        self.saved_repos: list[str] = []

    def save(self, repo: BorgBoiRepo) -> None:
        self.saved_repos.append(repo.name)


@pytest.fixture
def tui_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Config:
    """Create an offline Config rooted in tmp_path with borgboi_dir created."""
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    config = Config(offline=True)
    config.borgboi_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def tui_config_with_excludes(tui_config: Config) -> Config:
    """tui_config with the shared excludes file pre-created."""
    excludes_path = tui_config.borgboi_dir / tui_config.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")
    return tui_config


@pytest.fixture
def default_repos() -> list[BorgBoiRepo]:
    """Default list of one repo for TUI tests."""
    return [build_repo("alpha")]


@pytest.fixture
def live_repo_info() -> RepoInfo:
    """Shared Borg repo metadata payload for TUI tests."""
    return RepoInfo.model_validate(
        {
            "cache": {
                "path": "/Users/test/.cache/borg/alpha",
                "stats": {
                    "total_chunks": 42,
                    "total_csize": 3221225472,
                    "total_size": 5368709120,
                    "total_unique_chunks": 21,
                    "unique_csize": 2147483648,
                    "unique_size": 3221225472,
                },
            },
            "encryption": {"mode": "repokey"},
            "repository": {
                "id": "repo-id-1234567890",
                "last_modified": "2026-03-29T10:00:00+00:00",
                "location": "/Users/test/alpha",
            },
            "security_dir": "/Users/test/.config/borg/security/repo-id-1234567890",
            "archives": [
                {
                    "archive": "2026-03-28_22:00:00",
                    "id": "archive-a",
                    "name": "2026-03-28_22:00:00",
                    "start": "",
                    "time": "2026-03-28T22:00:00+00:00",
                },
                {
                    "archive": "2026-03-27_22:00:00",
                    "id": "archive-b",
                    "name": "2026-03-27_22:00:00",
                    "start": "",
                    "time": "2026-03-27T22:00:00+00:00",
                },
            ],
        }
    )


@pytest.fixture
def repo_archives() -> list[RepoArchive]:
    """Shared archive list for repo-detail TUI tests."""
    return [
        RepoArchive.model_validate(
            {
                "archive": "2026-03-28_22:00:00",
                "id": "archive-a-1234567890",
                "name": "2026-03-28_22:00:00",
                "start": "2026-03-28T22:00:00+00:00",
                "time": "2026-03-28T22:00:00+00:00",
            }
        ),
        RepoArchive.model_validate(
            {
                "archive": "2026-03-27_22:00:00",
                "id": "archive-b-1234567890",
                "name": "2026-03-27_22:00:00",
                "start": "2026-03-27T22:00:00+00:00",
                "time": "2026-03-27T22:00:00+00:00",
            }
        ),
    ]


@pytest.fixture
def repo_with_live_metadata(live_repo_info: RepoInfo) -> BorgBoiRepo:
    """Legacy repo model populated with live metadata for dashboard tests."""
    repo = build_repo("alpha")
    repo.metadata = live_repo_info
    return repo


@pytest.fixture
def repo_detail_repo(live_repo_info: RepoInfo) -> Repository:
    """Rich repository model populated with metadata and retention for detail tests."""
    return Repository(
        name="alpha",
        path="/Users/test/alpha",
        backup_target="/Users/test/Documents",
        hostname="test-host",
        os_platform="Darwin",
        last_backup=datetime(2026, 3, 28, 22, 0, tzinfo=UTC),
        metadata=RepoMetadata.model_validate(live_repo_info.model_dump()),
        retention_policy=RetentionPolicy(keep_daily=14, keep_weekly=8, keep_monthly=12, keep_yearly=2),
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        last_s3_sync=datetime(2026, 3, 29, 9, 0, tzinfo=UTC),
    )


@pytest.fixture
def fake_orchestrator(default_repos: list[BorgBoiRepo]) -> Any:
    """Minimal orchestrator stub that returns default_repos from list_repos."""
    return cast(Any, SimpleNamespace(list_repos=lambda: default_repos))


@pytest.fixture
def tui_app(tui_config: Config, fake_orchestrator: Any) -> BorgBoiApp:
    """Build a BorgBoiApp wired to the given config and fake orchestrator."""
    return BorgBoiApp(config=tui_config, orchestrator=fake_orchestrator)
