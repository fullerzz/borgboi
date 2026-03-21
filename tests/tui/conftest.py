from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from borgboi.config import Config
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
        yield '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"create","msgid":"archive.create"}\n'

    def prune(self, repo_path: str, **_kwargs: Any) -> Generator[str]:
        self.prune_calls.append(repo_path)
        yield '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"prune","msgid":"archive.prune"}\n'

    def compact(self, repo_path: str, **_kwargs: Any) -> Generator[str]:
        self.compact_calls.append(repo_path)
        yield '{"type":"log_message","name":"borg.output.info","levelname":"INFO","message":"compact","msgid":"archive.compact"}\n'

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
def fake_orchestrator(default_repos: list[BorgBoiRepo]) -> Any:
    """Minimal orchestrator stub that returns default_repos from list_repos."""
    return cast(Any, SimpleNamespace(list_repos=lambda: default_repos))


@pytest.fixture
def tui_app(tui_config: Config, fake_orchestrator: Any) -> BorgBoiApp:
    """Build a BorgBoiApp wired to the given config and fake orchestrator."""
    return BorgBoiApp(config=tui_config, orchestrator=fake_orchestrator)
