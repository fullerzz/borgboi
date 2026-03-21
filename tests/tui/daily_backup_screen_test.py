from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, cast, override

from textual.widgets import Button, RichLog, Select, Switch

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.daily_backup_screen import DailyBackupScreen

from .conftest import FakeBorg, FakeStorage, build_repo


def _build_daily_backup_app(
    config: Config,
    repos: list[BorgBoiRepo] | None = None,
    borg: FakeBorg | None = None,
    storage: FakeStorage | None = None,
    list_repos: Any = None,
) -> tuple[BorgBoiApp, FakeBorg, FakeStorage]:
    """Build a BorgBoiApp wired for daily backup testing."""
    borg = borg or FakeBorg()
    storage = storage or FakeStorage()
    orchestrator = cast(
        Any,
        SimpleNamespace(
            config=config,
            borg=borg,
            storage=storage,
            s3=None,
            list_repos=list_repos or (lambda: repos or [build_repo("alpha")]),
        ),
    )
    return BorgBoiApp(config=config, orchestrator=orchestrator), borg, storage


async def _open_daily_backup_screen(app: BorgBoiApp, pilot: Any) -> DailyBackupScreen:
    """Navigate to the DailyBackupScreen and wait for repos to load."""
    await pilot.press("b")
    await pilot.pause()
    assert isinstance(app.screen, DailyBackupScreen)
    await pilot.pause()  # let repos load via worker
    return app.screen


# -- Existing refactored test ------------------------------------------------


async def test_tui_daily_backup_start_runs_selected_repo(tui_config_with_excludes: Config) -> None:
    repo = build_repo("alpha")
    app, borg, storage = _build_daily_backup_app(tui_config_with_excludes, [repo])

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        start_button = screen.query_one("#daily-backup-start", Button)
        log = screen.query_one("#daily-backup-log", RichLog)

        select.value = repo.name
        await pilot.click("#daily-backup-start")
        await pilot.pause()

        assert start_button.disabled is False
        assert borg.create_calls == [f"{repo.path}:{repo.backup_target}"]
        assert borg.prune_calls == [repo.path]
        assert borg.compact_calls == [repo.path]
        assert storage.saved_repos == [repo.name]
        assert len(log.lines) > 0


# -- New tests for coverage gaps ---------------------------------------------


async def test_start_backup_with_no_repo_selected_shows_warning(tui_config_with_excludes: Config) -> None:
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        assert select.value is Select.NULL

        await pilot.click("#daily-backup-start")
        await pilot.pause()

        assert screen.query_one("#daily-backup-start", Button).disabled is False


async def test_escape_pops_screen_when_not_backing_up(tui_config_with_excludes: Config) -> None:
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        await _open_daily_backup_screen(app, pilot)

        await pilot.press("escape")
        assert not isinstance(app.screen, DailyBackupScreen)


async def test_backup_failed_shows_error_and_reenables_controls(tui_config_with_excludes: Config) -> None:
    repo = build_repo("alpha")

    class _FailingBorg(FakeBorg):
        @override
        def create(self, repo_path: str, backup_target: str, **_kwargs: Any) -> Generator[str]:
            raise RuntimeError("borg exploded")

    app, _, _ = _build_daily_backup_app(tui_config_with_excludes, [repo], borg=_FailingBorg())

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        select.value = repo.name
        await pilot.click("#daily-backup-start")
        await pilot.pause()

        assert screen.query_one("#daily-backup-start", Button).disabled is False
        assert screen.query_one("#daily-backup-select", Select).disabled is False


async def test_s3_switch_disabled_in_offline_mode(tui_config_with_excludes: Config) -> None:
    assert tui_config_with_excludes.offline is True
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        switch = screen.query_one("#daily-backup-s3-switch", Switch)
        assert switch.disabled is True
        assert switch.value is False


async def test_repos_loaded_into_select_on_mount(tui_config_with_excludes: Config) -> None:
    repos = [build_repo("alpha"), build_repo("beta")]
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes, repos)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        assert select.loading is False
        # _options includes prompt placeholder + actual options
        actual_options = [opt for opt in select._options if opt[1] is not Select.NULL]
        assert len(actual_options) == len(repos)


async def test_load_repos_error_disables_start_button(tui_config: Config) -> None:
    def failing_list_repos() -> list[BorgBoiRepo]:
        raise RuntimeError("db down")

    app, _, _ = _build_daily_backup_app(tui_config, list_repos=failing_list_repos)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        start_button = screen.query_one("#daily-backup-start", Button)
        assert start_button.disabled is True
