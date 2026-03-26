from __future__ import annotations

import time
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, cast, override

from textual.widgets import Button, ProgressBar, RichLog, Select, Switch

from borgboi.clients.s3_client import MockS3Client
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
    s3: Any = None,
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
            s3=s3,
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


# -- ProgressBar tests -------------------------------------------------------


async def test_progress_bar_visible_initially(tui_config_with_excludes: Config) -> None:
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        assert progress_bar.display is True
        assert progress_bar.total == 100
        assert progress_bar.progress == 0


async def test_progress_bar_remains_visible_after_backup_completes(tui_config_with_excludes: Config) -> None:
    repo = build_repo("alpha")
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes, [repo])

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        select.value = repo.name
        await pilot.click("#daily-backup-start")
        await pilot.pause()

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        assert progress_bar.display is True


async def test_progress_bar_remains_visible_after_backup_fails(tui_config_with_excludes: Config) -> None:
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

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        assert progress_bar.display is True


async def test_clear_log_resets_progress_bar_state(tui_config_with_excludes: Config) -> None:
    app, _, _ = _build_daily_backup_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        progress_bar.update(total=None, progress=42)
        progress_bar.display = True

        clear_button = screen.query_one("#daily-backup-clear", Button)
        clear_button.disabled = False

        screen.on_button_pressed(Button.Pressed(clear_button))

        assert progress_bar.total == 100
        assert progress_bar.progress == 0
        assert progress_bar.display is True
        assert clear_button.disabled is True


async def test_progress_bar_stays_visible_until_streaming_create_finishes(tui_config_with_excludes: Config) -> None:
    repo = build_repo("alpha")

    class _StreamingBorg(FakeBorg):
        @override
        def create(self, repo_path: str, backup_target: str, **_kwargs: Any) -> Generator[str]:
            self.create_calls.append(f"{repo_path}:{backup_target}")
            yield (
                '{"type":"archive_progress","finished":false,"path":"/some/file.txt","time":"2026-01-01T00:00:00"}\n'
            )
            yield '{"type":"archive_progress","finished":true,"time":"2026-01-01T00:00:00"}\n'
            time.sleep(0.5)
            yield (
                '{"type":"log_message","name":"borg.output.stats","levelname":"INFO",'
                '"message":"Repository: /repo","time":"2026-01-01T00:00:00"}\n'
            )

    app, _, _ = _build_daily_backup_app(tui_config_with_excludes, [repo], borg=_StreamingBorg())

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        select.value = repo.name
        await pilot.click("#daily-backup-start")
        await pilot.pause(0.2)

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        assert progress_bar.display is True

        await pilot.pause(0.5)
        assert progress_bar.display is True


async def test_progress_bar_marks_complete_after_s3_sync(monkeypatch: Any, tmp_path: Any) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    config = Config(offline=False)
    config.borgboi_dir.mkdir(parents=True, exist_ok=True)
    (config.borgboi_dir / config.excludes_filename).write_text("*.tmp\n")

    repo = build_repo("alpha")

    fake_s3 = MockS3Client()
    app, _, _ = _build_daily_backup_app(config, [repo], s3=fake_s3)

    async with app.run_test() as pilot:
        screen = await _open_daily_backup_screen(app, pilot)

        select = screen.query_one("#daily-backup-select", Select)
        select.value = repo.name
        await pilot.click("#daily-backup-start")
        await pilot.pause()

        progress_bar = screen.query_one("#daily-backup-progress", ProgressBar)
        assert progress_bar.display is True
        assert progress_bar.total == 100
        assert progress_bar.progress == 100
        assert fake_s3.sync_calls == [(repo.safe_path, repo.name)]
