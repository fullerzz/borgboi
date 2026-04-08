from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, DirectoryTree, Input, Label, Static, TabbedContent, TabPane, TextArea

from borgboi.clients.borg import RepoArchive, RepoInfo
from borgboi.config import Config
from borgboi.core.models import Repository, RetentionPolicy
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.archive_compare_screen import ArchiveCompareScreen
from borgboi.tui.repo_config_screen import RepoConfigScreen
from borgboi.tui.repo_info_screen import RepoInfoScreen, load_repo_excludes_state


@pytest.fixture
def repo_info_app(
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
) -> BorgBoiApp:
    return BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_repo_storage_quota=lambda _repo: "100G",
                update_repo_storage_quota=lambda quota, **_: quota.upper(),
                update_repo_config=lambda **kwargs: (
                    None if kwargs.get("storage_quota") == "" else kwargs.get("storage_quota", "100G"),
                    kwargs.get("retention_policy", repo_detail_repo.retention_policy),
                ),
            ),
        ),
    )


@pytest.fixture
def repo_info_error_app(tui_config: Config, repo_detail_repo: Repository) -> BorgBoiApp:
    return BorgBoiApp(
        config=tui_config,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: (_ for _ in ()).throw(RuntimeError("borg unavailable")),
                list_archives=lambda _repo: [],
                get_repo_storage_quota=lambda _repo: (_ for _ in ()).throw(RuntimeError("borg unavailable")),
            ),
        ),
    )


def test_load_repo_excludes_state_prefers_repo_specific_file(tui_config_with_excludes: Config) -> None:
    repo_specific_path = tui_config_with_excludes.borgboi_dir / f"alpha_{tui_config_with_excludes.excludes_filename}"
    repo_specific_path.write_text("node_modules/\n", encoding="utf-8")

    state = load_repo_excludes_state(tui_config_with_excludes, "alpha")

    assert state.source_label == "Repo-specific"
    assert state.path == repo_specific_path
    assert state.body == "node_modules/\n"
    assert "override" in state.status


def test_load_repo_excludes_state_falls_back_to_shared_default(tui_config_with_excludes: Config) -> None:
    state = load_repo_excludes_state(tui_config_with_excludes, "alpha")

    assert state.source_label == "Shared default"
    assert state.path == tui_config_with_excludes.borgboi_dir / tui_config_with_excludes.excludes_filename
    assert state.body == "*.tmp\n"
    assert "currently in use" in state.status


def test_load_repo_excludes_state_handles_invalid_utf8_repo_specific_file(tui_config_with_excludes: Config) -> None:
    repo_specific_path = tui_config_with_excludes.borgboi_dir / f"alpha_{tui_config_with_excludes.excludes_filename}"
    repo_specific_path.write_bytes(b"\xff\xfe")

    state = load_repo_excludes_state(tui_config_with_excludes, "alpha")

    assert state.source_label == "Repo-specific"
    assert state.path == repo_specific_path
    assert state.body == ""
    assert "could not be read" in state.status


async def test_repo_info_screen_renders_requested_sections(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    repo_specific_path = (
        tui_config_with_excludes.borgboi_dir / f"{repo_detail_repo.name}_{tui_config_with_excludes.excludes_filename}"
    )
    repo_specific_path.write_text("node_modules/\n.env\n", encoding="utf-8")

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        tabs = repo_info_app.screen.query_one("#repo-info-tabs", TabbedContent)
        settings_tab = repo_info_app.screen.query_one("#repo-info-settings-tab", TabPane)
        summary = repo_info_app.screen.query_one("#repo-info-summary", Static)
        quota = repo_info_app.screen.query_one("#repo-info-config", Static)
        command_output = repo_info_app.screen.query_one("#repo-info-command-output", Static)
        excludes_viewer = repo_info_app.screen.query_one("#repo-info-excludes-viewer", TextArea)
        archives_status = repo_info_app.screen.query_one("#repo-info-archives-status", Static)
        archives_table = repo_info_app.screen.query_one("#repo-info-archives-table", DataTable)

        # Wait for worker threads to complete loading live data
        import asyncio

        # Poll for up to 2 seconds waiting for both live workers to load
        for _ in range(20):
            command_output_content = str(cast(Any, command_output).content)
            quota_content = str(cast(Any, quota).content)
            if (
                "Deduplicated Size" in command_output_content
                and "Quota Source" in quota_content
                and "Repository" in quota_content
            ):
                break
            await asyncio.sleep(0.1)

        assert tabs.active == "repo-info-overview-tab"
        assert settings_tab.id == "repo-info-settings-tab"
        assert "Backup Target" in str(cast(Any, summary).content)
        assert "Retention Source" in str(cast(Any, quota).content)
        assert "100G" in str(cast(Any, quota).content)
        assert "Quota Source" in str(cast(Any, quota).content)
        assert "Repository" in str(cast(Any, quota).content)
        assert "Repo-specific" in str(cast(Any, quota).content)
        assert "Deduplicated Size" in str(cast(Any, command_output).content)
        assert "Repo ID" in str(cast(Any, command_output).content)
        assert excludes_viewer.text == "node_modules/\n.env\n"
        assert str(cast(Any, archives_status).content) == "2 archives found."
        assert archives_table.row_count == 2
        assert archives_table.get_row_at(0)[0] == "2026-03-28_22:00:00"


async def test_repo_info_screen_uses_scrollable_overview_body(repo_info_app: BorgBoiApp) -> None:
    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        overview_body = repo_info_app.screen.query_one("#repo-info-overview-body", VerticalScroll)

        assert overview_body.can_focus is True


async def test_repo_info_screen_handles_unreadable_excludes_file(
    tui_config_with_excludes: Config,
    repo_info_app: BorgBoiApp,
) -> None:
    repo_specific_path = tui_config_with_excludes.borgboi_dir / f"alpha_{tui_config_with_excludes.excludes_filename}"
    repo_specific_path.write_bytes(b"\xff\xfe")

    async with repo_info_app.run_test() as pilot:
        # Wait for main screen repos to load
        table = repo_info_app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if table.row_count > 0:
                break
        await pilot.press("i")

        # Wait for RepoInfoScreen to be active
        for _ in range(50):
            await pilot.pause(0.05)
            if isinstance(repo_info_app.screen, RepoInfoScreen):
                break

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        excludes_status = repo_info_app.screen.query_one("#repo-info-excludes-status", Static)
        excludes_viewer = repo_info_app.screen.query_one("#repo-info-excludes-viewer", TextArea)
        command_output = repo_info_app.screen.query_one("#repo-info-command-output", Static)

        # Wait for worker results
        import asyncio

        for _ in range(50):
            if "could not be read" in str(cast(Any, excludes_status).content) and "Deduplicated Size" in str(
                cast(Any, command_output).content
            ):
                break
            await asyncio.sleep(0.05)

        assert "could not be read" in str(cast(Any, excludes_status).content)
        assert excludes_viewer.text == ""
        assert "Deduplicated Size" in str(cast(Any, command_output).content)


async def test_repo_info_screen_handles_live_load_errors(repo_info_error_app: BorgBoiApp) -> None:
    async with repo_info_error_app.run_test() as pilot:
        # Wait for main screen repos to load
        table = repo_info_error_app.query_one("#repos-table", DataTable)
        for _ in range(50):
            await pilot.pause(0.05)
            if table.row_count > 0:
                break
        await pilot.press("i")

        # Wait for RepoInfoScreen to be active
        for _ in range(50):
            await pilot.pause(0.05)
            if isinstance(repo_info_error_app.screen, RepoInfoScreen):
                break

        assert isinstance(repo_info_error_app.screen, RepoInfoScreen)

        loading = repo_info_error_app.screen.query_one("#repo-info-loading", Static)
        command_output = repo_info_error_app.screen.query_one("#repo-info-command-output", Static)
        archives_status = repo_info_error_app.screen.query_one("#repo-info-archives-status", Static)
        archives_table = repo_info_error_app.screen.query_one("#repo-info-archives-table", DataTable)

        # Wait for worker error results
        import asyncio

        for _ in range(50):
            if (
                "Failed to load live repository data." in str(cast(Any, loading).content)
                and "borg unavailable" in str(cast(Any, command_output).content)
                and "Archive list unavailable." in str(cast(Any, archives_status).content)
            ):
                break
            await asyncio.sleep(0.05)

        assert str(cast(Any, loading).content) == "Failed to load live repository data."
        assert "borg unavailable" in str(cast(Any, command_output).content)
        assert str(cast(Any, archives_status).content) == "Archive list unavailable."
        assert archives_table.row_count == 0


async def test_repo_info_screen_clears_stale_quota_after_refresh_failure(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    quota_calls = 0

    def get_repo_storage_quota(_repo: Repository) -> str:
        nonlocal quota_calls
        quota_calls += 1
        if quota_calls == 1:
            return "100G"
        raise RuntimeError("quota reload failed")

    app = BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_repo_storage_quota=get_repo_storage_quota,
                update_repo_storage_quota=lambda quota, **_: quota.upper(),
                update_repo_config=lambda **kwargs: (
                    None if kwargs.get("storage_quota") == "" else kwargs.get("storage_quota", "100G"),
                    kwargs.get("retention_policy", repo_detail_repo.retention_policy),
                ),
            ),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(app.screen, RepoInfoScreen)

        quota = app.screen.query_one("#repo-info-config", Static)
        config_status = app.screen.query_one("#repo-info-config-status", Label)

        import asyncio

        for _ in range(20):
            quota_content = str(cast(Any, quota).content)
            if "Quota Source" in quota_content and "Repository" in quota_content:
                break
            await asyncio.sleep(0.1)

        assert "100G" in str(cast(Any, quota).content)
        assert "Repository" in str(cast(Any, quota).content)

        await pilot.press("r")

        for _ in range(20):
            quota_content = str(cast(Any, quota).content)
            config_status_content = str(cast(Any, config_status).content)
            if "Unavailable" in quota_content and "quota reload failed" in config_status_content:
                break
            await asyncio.sleep(0.1)

        assert "100G" not in str(cast(Any, quota).content)
        assert "Unavailable" in str(cast(Any, quota).content)
        assert "Unknown" in str(cast(Any, quota).content)
        assert "quota reload failed" in str(cast(Any, config_status).content)


async def test_repo_info_screen_shows_workspace_tree_for_local_repo(
    monkeypatch: pytest.MonkeyPatch,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
    tmp_path: Any,
) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        workspace_status = repo_info_app.screen.query_one("#repo-info-workspace-status", Static)
        workspace_path = repo_info_app.screen.query_one("#repo-info-workspace-path", Static)
        workspace_tree = repo_info_app.screen.query_one("#repo-info-workspace-tree", DirectoryTree)

        assert "Browsing local repository workspace" in str(cast(Any, workspace_status).content)
        assert tmp_path.as_posix() in str(cast(Any, workspace_path).content)
        assert workspace_tree.path == tmp_path
        assert len(repo_info_app.screen.query("#repo-info-workspace-unavailable")) == 0


async def test_repo_info_screen_hides_workspace_tree_for_remote_repo(
    monkeypatch: pytest.MonkeyPatch,
    repo_info_app: BorgBoiApp,
) -> None:
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: "other-host")

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        workspace_status = repo_info_app.screen.query_one("#repo-info-workspace-status", Static)
        workspace_unavailable = repo_info_app.screen.query_one("#repo-info-workspace-unavailable", Static)
        config_status = repo_info_app.screen.query_one("#repo-info-config-status", Label)
        quota_summary = repo_info_app.screen.query_one("#repo-info-config", Static)
        storage_card = repo_info_app.screen.query_one("#repo-info-storage-card", Static)
        edit_button = repo_info_app.screen.query_one("#repo-info-edit-config-btn", Button)
        compare_button = repo_info_app.screen.query_one("#repo-info-compare-archives-btn", Button)

        assert "Workspace tree unavailable" in str(cast(Any, workspace_status).content)
        assert "only available for repositories on this machine" in str(cast(Any, workspace_unavailable).content)
        assert "Press e or use Edit settings to update retention" in str(cast(Any, config_status).content)
        assert "Max Storage Quota" in str(cast(Any, quota_summary).content)
        assert "Unknown" in str(cast(Any, quota_summary).content)
        assert "Unavailable" in str(cast(Any, quota_summary).content)
        assert "Quota Unknown" in str(cast(Any, storage_card).content)
        assert edit_button.disabled is False
        assert compare_button.disabled is True
        assert len(repo_info_app.screen.query("#repo-info-workspace-tree")) == 0


async def test_repo_info_screen_opens_archive_compare_screen(
    monkeypatch: pytest.MonkeyPatch,
    repo_info_app: BorgBoiApp,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        await pilot.press("d")
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(repo_info_app.screen, ArchiveCompareScreen):
                break

        assert isinstance(repo_info_app.screen, ArchiveCompareScreen)


async def test_repo_info_screen_shortcut_opens_archives_tab_and_focuses_table(repo_info_app: BorgBoiApp) -> None:
    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        tabs = repo_info_app.screen.query_one("#repo-info-tabs", TabbedContent)
        archives_table = repo_info_app.screen.query_one("#repo-info-archives-table", DataTable)

        await pilot.press("a")
        await pilot.pause()

        assert tabs.active == "repo-info-archives-tab"
        assert repo_info_app.focused is archives_table


async def test_repo_info_screen_opens_repo_config_screen(
    monkeypatch: pytest.MonkeyPatch,
    repo_info_app: BorgBoiApp,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoConfigScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)


async def test_repo_info_screen_preserves_loaded_quota_after_retention_only_save(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    seen_storage_quotas: list[str | None] = []

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        seen_storage_quotas.append(kwargs.get("storage_quota"))
        return None, kwargs["retention_policy"]

    app = BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_repo_storage_quota=lambda _repo: "100G",
                update_repo_config=update_repo_config,
            ),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoInfoScreen)

        quota_summary = app.screen.query_one("#repo-info-config", Static)

        import asyncio

        for _ in range(20):
            if "Repository" in str(cast(Any, quota_summary).content):
                break
            await asyncio.sleep(0.1)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, RepoConfigScreen)

        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)
        daily_input.value = "30"
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if isinstance(app.screen, RepoInfoScreen) and "30" in str(cast(Any, quota_summary).content):
                break
            await asyncio.sleep(0.1)

        assert seen_storage_quotas == [None]
        assert isinstance(app.screen, RepoInfoScreen)
        assert "Repository" in str(cast(Any, quota_summary).content)
        assert "100G" in str(cast(Any, quota_summary).content)
        assert "30" in str(cast(Any, quota_summary).content)


async def test_repo_info_screen_preserves_default_retention_source_after_quota_only_save(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    repo_detail_repo.retention_policy = None
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        return "250G", None

    app = BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_repo_storage_quota=lambda _repo: "100G",
                update_repo_config=update_repo_config,
            ),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoInfoScreen)

        quota_summary = app.screen.query_one("#repo-info-config", Static)

        import asyncio

        for _ in range(20):
            if "Retention Source" in str(cast(Any, quota_summary).content):
                break
            await asyncio.sleep(0.1)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, RepoConfigScreen)

        quota_input = app.screen.query_one("#repo-config-quota-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)
        quota_input.value = "250G"
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if isinstance(app.screen, RepoInfoScreen) and "250G" in str(cast(Any, quota_summary).content):
                break
            await asyncio.sleep(0.1)

        assert isinstance(app.screen, RepoInfoScreen)
        assert app.screen._repo.retention_policy is None
        assert "250G" in str(cast(Any, quota_summary).content)
        assert "Default" in str(cast(Any, quota_summary).content)


async def test_repo_info_screen_shows_default_retention_source_after_clearing_override(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    repo_detail_repo.retention_policy = RetentionPolicy(keep_daily=30, keep_weekly=8, keep_monthly=12, keep_yearly=2)
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        return None, None

    app = BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_repo_storage_quota=lambda _repo: "100G",
                update_repo_config=update_repo_config,
            ),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoInfoScreen)

        quota_summary = app.screen.query_one("#repo-info-config", Static)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, RepoConfigScreen)

        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)
        daily_input.value = str(tui_config_with_excludes.borg.retention.keep_daily)
        app.screen.on_button_pressed(Button.Pressed(save_button))

        import asyncio

        for _ in range(20):
            if isinstance(app.screen, RepoInfoScreen) and "Default" in str(cast(Any, quota_summary).content):
                break
            await asyncio.sleep(0.1)

        assert isinstance(app.screen, RepoInfoScreen)
        assert app.screen._repo.retention_policy is None
        assert "Default" in str(cast(Any, quota_summary).content)


async def test_repo_info_screen_reports_missing_local_workspace_path(
    monkeypatch: pytest.MonkeyPatch,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = (tmp_path / "missing-repo").as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        workspace_unavailable = repo_info_app.screen.query_one("#repo-info-workspace-unavailable", Static)

        assert "Repository path is not available on this machine" in str(cast(Any, workspace_unavailable).content)
        assert len(repo_info_app.screen.query("#repo-info-workspace-tree")) == 0
