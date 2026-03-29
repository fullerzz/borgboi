from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from textual.widgets import DataTable, Static

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.storage.db import get_db_path
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.config_screen import ConfigScreen
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen

from .conftest import build_repo


async def test_app_composes_with_data_table_and_sections(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test():
        tui_app.query_one("#repos-table", DataTable)
        tui_app.query_one("#repos-section")
        tui_app.query_one("#sparkline-section")


async def test_app_loads_and_populates_repos_table(tui_config: Config) -> None:
    repos = [build_repo("alpha"), build_repo("beta")]
    orchestrator = cast(Any, SimpleNamespace(list_repos=lambda: repos))
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#repos-table", DataTable)
        assert table.row_count == 2


async def test_action_show_config_pushes_screen(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(tui_app.screen, ConfigScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(tui_app.screen, ConfigScreen)


async def test_action_show_config_ignored_on_non_main_screen(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        await pilot.press("e")  # push excludes screen
        assert isinstance(tui_app.screen, DefaultExcludesScreen)

        await pilot.press("c")  # should be ignored
        assert isinstance(tui_app.screen, DefaultExcludesScreen)


async def test_action_daily_backup_pushes_screen(tui_config: Config) -> None:
    orchestrator = cast(
        Any,
        SimpleNamespace(
            config=tui_config,
            borg=None,
            storage=None,
            s3=None,
            list_repos=lambda: [build_repo("alpha")],
        ),
    )
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, DailyBackupScreen)


async def test_action_daily_backup_ignored_on_non_main_screen(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        await pilot.press("e")  # push excludes screen
        assert isinstance(tui_app.screen, DefaultExcludesScreen)

        await pilot.press("b")  # should be ignored
        assert isinstance(tui_app.screen, DefaultExcludesScreen)


async def test_action_refresh_reloads_repos(tui_config: Config) -> None:
    call_count = 0

    def counting_list_repos() -> list[BorgBoiRepo]:
        nonlocal call_count
        call_count += 1
        return [build_repo("alpha")]

    orchestrator = cast(Any, SimpleNamespace(list_repos=counting_list_repos))
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.pause()  # initial load
        initial_count = call_count

        await pilot.press("r")
        await pilot.pause()
        assert call_count > initial_count


async def test_app_loads_sparkline_history_from_configured_db(
    tui_config: Config, monkeypatch: Any, tmp_path_factory: Any
) -> None:
    captured_db_paths: list[object] = []
    alternate_home = tmp_path_factory.mktemp("alt-home")

    class FakeHistory:
        def __init__(self, db_path: object = None, engine: object = None) -> None:
            del engine
            captured_db_paths.append(db_path)

        def __enter__(self) -> FakeHistory:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def get_daily_archive_counts(self, days: int) -> list[float]:
            return [0.0] * days

    orchestrator = cast(Any, SimpleNamespace(list_repos=lambda: [build_repo("alpha")]))
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)
    monkeypatch.setenv("BORGBOI_HOME", alternate_home.as_posix())
    monkeypatch.setattr("borgboi.tui.app.SQLiteDailyBackupProgressHistory", FakeHistory)

    today = datetime.now(UTC).date()
    expected_labels = [(today - timedelta(days=13 - index)).strftime("%m/%d") for index in range(14)]

    async with app.run_test() as pilot:
        await pilot.pause()
        actual_labels = [app.query_one(f"#sparkline-x-label-{index}", Static).content for index in range(14)]
        assert actual_labels == expected_labels

    assert captured_db_paths == [get_db_path(tui_config.borgboi_dir)]


async def test_load_repos_error_shows_notification(tui_config: Config) -> None:
    def failing_list_repos() -> list[BorgBoiRepo]:
        raise RuntimeError("db down")

    orchestrator = cast(Any, SimpleNamespace(list_repos=failing_list_repos))
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#repos-table", DataTable)
        assert table.loading is False
        assert table.row_count == 0
