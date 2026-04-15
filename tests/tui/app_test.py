from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from textual.widgets import DataTable, Static

from borgboi.config import Config, TelemetryConfig
from borgboi.models import BorgBoiRepo
from borgboi.storage.db import get_db_path
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.config_screen import ConfigScreen
from borgboi.tui.daily_backup_screen import DailyBackupScreen
from borgboi.tui.excludes_screen import DefaultExcludesScreen
from borgboi.tui.repo_info_screen import RepoInfoScreen

from .conftest import FakeTracer, build_repo, make_orchestrator


async def test_app_composes_with_data_table_and_sections(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test():
        tui_app.query_one("#repos-table", DataTable)
        tui_app.query_one("#repos-section")
        tui_app.query_one("#sparkline-section")


async def test_app_loads_and_populates_repos_table(tui_config: Config) -> None:
    repos = [build_repo("alpha"), build_repo("beta")]
    orchestrator = make_orchestrator(list_repos=lambda: repos)
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        # Wait for repos to load via worker
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if table.row_count == 2:
                break
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
    orchestrator = make_orchestrator(config=tui_config, list_repos=lambda: [build_repo("alpha")])
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, DailyBackupScreen)


async def test_action_show_repo_info_pushes_screen(tui_config: Config, repo_with_live_metadata: BorgBoiRepo) -> None:
    orchestrator = make_orchestrator(
        config=tui_config,
        list_repos=lambda: [repo_with_live_metadata],
        get_repo_info=lambda _repo: repo_with_live_metadata.metadata,
        list_archives=lambda _repo: [],
    )
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        # Wait for repos to load and table to be populated
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if table.row_count > 0:
                break
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, RepoInfoScreen)


async def test_repo_table_row_selected_opens_repo_info_screen(
    tui_config: Config, repo_with_live_metadata: BorgBoiRepo
) -> None:
    orchestrator = make_orchestrator(
        config=tui_config,
        list_repos=lambda: [repo_with_live_metadata],
        get_repo_info=lambda _repo: repo_with_live_metadata.metadata,
        list_archives=lambda _repo: [],
    )
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        # Wait for repos to load and table to be populated
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if table.row_count > 0:
                break
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, RepoInfoScreen)


async def test_returning_from_successful_backup_refreshes_dashboard(
    tui_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    orchestrator = make_orchestrator(config=tui_config, list_repos=lambda: [build_repo("alpha")])
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    repo_refreshes = 0
    sparkline_refreshes = 0

    def fake_load_repos() -> None:
        nonlocal repo_refreshes
        repo_refreshes += 1

    def fake_load_sparkline_data() -> None:
        nonlocal sparkline_refreshes
        sparkline_refreshes += 1

    monkeypatch.setattr(app, "_load_repos", fake_load_repos)
    monkeypatch.setattr(app, "_load_sparkline_data", fake_load_sparkline_data)

    async with app.run_test() as pilot:
        await pilot.pause()
        initial_repo_refreshes = repo_refreshes
        initial_sparkline_refreshes = sparkline_refreshes

        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, DailyBackupScreen)

        app.screen._on_backup_complete()
        await pilot.press("escape")
        await pilot.pause()

        assert repo_refreshes == initial_repo_refreshes + 1
        assert sparkline_refreshes == initial_sparkline_refreshes + 1


async def test_action_daily_backup_ignored_on_non_main_screen(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        await pilot.press("e")  # push excludes screen
        assert isinstance(tui_app.screen, DefaultExcludesScreen)

        await pilot.press("b")  # should be ignored
        assert isinstance(tui_app.screen, DefaultExcludesScreen)


async def test_action_show_repo_info_ignored_on_non_main_screen(
    tui_config: Config, repo_with_live_metadata: BorgBoiRepo
) -> None:
    orchestrator = make_orchestrator(
        config=tui_config,
        list_repos=lambda: [repo_with_live_metadata],
        get_repo_info=lambda _repo: repo_with_live_metadata.metadata,
        list_archives=lambda _repo: [],
    )
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        await pilot.press("i")
        assert isinstance(app.screen, DefaultExcludesScreen)


async def test_action_refresh_reloads_repos(tui_config: Config) -> None:
    call_count = 0

    def counting_list_repos() -> list[BorgBoiRepo]:
        nonlocal call_count
        call_count += 1
        return [build_repo("alpha")]

    orchestrator = make_orchestrator(list_repos=counting_list_repos)
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        # Wait for initial load
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if not table.loading:
                break
        initial_count = call_count

        await pilot.press("r")
        # Wait for refresh to increase call count
        for _ in range(50):
            await pilot.pause(0.05)
            if call_count > initial_count:
                break
        assert call_count > initial_count


async def test_app_loads_sparkline_history_from_configured_db(
    tui_config: Config,
    monkeypatch: pytest.MonkeyPatch,
    patch_sparkline_history: Callable[..., None],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    captured_db_paths: list[object] = []
    alternate_home = tmp_path_factory.mktemp("alt-home")

    orchestrator = make_orchestrator(list_repos=lambda: [build_repo("alpha")])
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)
    monkeypatch.setenv("BORGBOI_HOME", alternate_home.as_posix())
    patch_sparkline_history([0.0] * 14, captured_db_paths)

    today = datetime.now(UTC).date()
    expected_labels = [(today - timedelta(days=13 - index)).strftime("%m/%d") for index in range(14)]

    async with app.run_test() as pilot:
        # Wait for sparkline labels to be populated
        for _ in range(50):
            await pilot.pause(0.05)
            label = app.query_one("#sparkline-x-label-0", Static)
            if label.content:
                break
        actual_labels = [app.query_one(f"#sparkline-x-label-{index}", Static).content for index in range(14)]
        assert actual_labels == expected_labels

    assert captured_db_paths == [get_db_path(tui_config.borgboi_dir)]


async def test_load_repos_error_shows_notification(tui_config: Config) -> None:
    def failing_list_repos() -> list[BorgBoiRepo]:
        raise RuntimeError("db down")

    orchestrator = make_orchestrator(list_repos=failing_list_repos)
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        # Wait for loading to complete (even with error)
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if not table.loading:
                break
        assert table.loading is False
        assert table.row_count == 0


async def test_app_captures_expected_tui_spans(
    fake_tui_tracer: FakeTracer,
    patch_sparkline_history: Callable[..., None],
    tui_config: Config,
) -> None:
    tui_config.telemetry.enabled = True
    orchestrator = make_orchestrator(list_repos=lambda: [build_repo("alpha")])
    app = BorgBoiApp(config=tui_config, orchestrator=orchestrator)
    patch_sparkline_history([1.0] * 14)

    async with app.run_test() as pilot:
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            label = app.query_one("#sparkline-x-label-0", Static)
            if not table.loading and label.content:
                break

    assert fake_tui_tracer.started_spans[0] == "tui.app.mount"
    assert set(fake_tui_tracer.started_spans[1:]) == {"tui.load_repos", "tui.load_sparkline"}


async def test_app_skips_tui_spans_when_capture_disabled(
    fake_tui_tracer: FakeTracer,
    monkeypatch: pytest.MonkeyPatch,
    patch_sparkline_history: Callable[..., None],
    tmp_path: Any,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())

    config = Config(offline=True, telemetry=TelemetryConfig(capture_tui=False))
    config.borgboi_dir.mkdir(parents=True, exist_ok=True)

    orchestrator = make_orchestrator(list_repos=lambda: [build_repo("alpha")])
    app = BorgBoiApp(config=config, orchestrator=orchestrator)
    patch_sparkline_history([1.0] * 14)

    async with app.run_test() as pilot:
        table = app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            label = app.query_one("#sparkline-x-label-0", Static)
            if not table.loading and label.content:
                break

    assert fake_tui_tracer.started_spans == []
