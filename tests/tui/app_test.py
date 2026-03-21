from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from textual.widgets import DataTable

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.config_panel import ConfigPanel
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen

from .conftest import build_repo


async def test_app_composes_with_data_table_and_config_panel(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test():
        tui_app.query_one("#repos-table", DataTable)
        tui_app.query_one("#config-panel", ConfigPanel)


async def test_app_loads_and_populates_repos_table(tui_config: Config) -> None:
    repos = [build_repo("alpha"), build_repo("beta")]
    orchestrator = cast(Any, SimpleNamespace(list_repos=lambda: repos))
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#repos-table", DataTable)
        assert table.row_count == 2


async def test_action_toggle_config_shows_and_hides_panel(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        panel = tui_app.query_one("#config-panel", ConfigPanel)
        initial_display = panel.display

        await pilot.press("c")
        assert panel.display is not initial_display

        await pilot.press("c")
        assert panel.display is initial_display


async def test_action_toggle_config_ignored_on_non_main_screen(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        panel = tui_app.query_one("#config-panel", ConfigPanel)
        display_before = panel.display

        await pilot.press("e")  # push excludes screen
        assert isinstance(tui_app.screen, DefaultExcludesScreen)

        await pilot.press("c")  # should be ignored
        assert panel.display == display_before


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
