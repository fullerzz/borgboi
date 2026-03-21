import asyncio
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.widgets import Button, RichLog, Select

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.daily_backup_screen import DailyBackupScreen


def _build_repo(name: str) -> BorgBoiRepo:
    return BorgBoiRepo(
        name=name,
        path=f"/Users/test/{name}",
        hostname="test-host",
        os_platform="Darwin",
        backup_target="local",
        metadata=None,
    )


class _FakeBorg:
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


class _FakeStorage:
    def __init__(self) -> None:
        self.saved_repos: list[str] = []

    def save(self, repo: BorgBoiRepo) -> None:
        self.saved_repos.append(repo.name)


def test_tui_daily_backup_start_runs_selected_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    config = Config(offline=True)
    config.borgboi_dir.mkdir(parents=True, exist_ok=True)
    (config.borgboi_dir / config.excludes_filename).write_text("*.tmp\n", encoding="utf-8")
    repo = _build_repo("alpha")
    borg = _FakeBorg()
    storage = _FakeStorage()
    orchestrator = cast(
        Any,
        SimpleNamespace(
            config=config,
            borg=borg,
            storage=storage,
            s3=None,
            list_repos=lambda: [repo],
        ),
    )
    app = BorgBoiApp(config=config, orchestrator=orchestrator)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("b")
            await pilot.pause(0.2)

            assert isinstance(app.screen, DailyBackupScreen)
            screen = app.screen
            screen._populate_repos([repo])
            assert screen._backup_running is False

            select = screen.query_one("#daily-backup-select", Select)
            start_button = screen.query_one("#daily-backup-start", Button)
            log = screen.query_one("#daily-backup-log", RichLog)

            select.value = repo.name
            screen.on_button_pressed(Button.Pressed(start_button))
            await pilot.pause(0.5)

            assert screen._backup_running is False
            assert start_button.disabled is False
            assert borg.create_calls == [f"{repo.path}:{repo.backup_target}"]
            assert borg.prune_calls == [repo.path]
            assert borg.compact_calls == [repo.path]
            assert storage.saved_repos == [repo.name]
            assert len(log.lines) > 0

    asyncio.run(run_test())
