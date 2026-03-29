from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.widgets import DataTable, DirectoryTree, Static, TabbedContent, TextArea

from borgboi.clients.borg import RepoArchive, RepoInfo
from borgboi.config import Config
from borgboi.core.models import Repository
from borgboi.tui.app import BorgBoiApp
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
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
) -> None:
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
        summary = repo_info_app.screen.query_one("#repo-info-summary", Static)
        quota = repo_info_app.screen.query_one("#repo-info-config", Static)
        command_output = repo_info_app.screen.query_one("#repo-info-command-output", Static)
        excludes_viewer = repo_info_app.screen.query_one("#repo-info-excludes-viewer", TextArea)
        archives_status = repo_info_app.screen.query_one("#repo-info-archives-status", Static)
        archives_table = repo_info_app.screen.query_one("#repo-info-archives-table", DataTable)

        assert tabs.active == "repo-info-overview-tab"
        assert "Backup Target" in str(cast(Any, summary).content)
        assert "Retention Source" in str(cast(Any, quota).content)
        assert "Repo-specific" in str(cast(Any, quota).content)
        assert "Deduplicated Size" in str(cast(Any, command_output).content)
        assert "Repo ID" in str(cast(Any, command_output).content)
        assert excludes_viewer.text == "node_modules/\n.env\n"
        assert str(cast(Any, archives_status).content) == "2 archives found."
        assert archives_table.row_count == 2
        assert archives_table.get_row_at(0)[0] == "2026-03-28_22:00:00"


async def test_repo_info_screen_handles_unreadable_excludes_file(
    tui_config_with_excludes: Config,
    repo_info_app: BorgBoiApp,
) -> None:
    repo_specific_path = tui_config_with_excludes.borgboi_dir / f"alpha_{tui_config_with_excludes.excludes_filename}"
    repo_specific_path.write_bytes(b"\xff\xfe")

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        excludes_status = repo_info_app.screen.query_one("#repo-info-excludes-status", Static)
        excludes_viewer = repo_info_app.screen.query_one("#repo-info-excludes-viewer", TextArea)
        command_output = repo_info_app.screen.query_one("#repo-info-command-output", Static)

        assert "could not be read" in str(cast(Any, excludes_status).content)
        assert excludes_viewer.text == ""
        assert "Deduplicated Size" in str(cast(Any, command_output).content)


async def test_repo_info_screen_handles_live_load_errors(repo_info_error_app: BorgBoiApp) -> None:
    async with repo_info_error_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_error_app.screen, RepoInfoScreen)

        loading = repo_info_error_app.screen.query_one("#repo-info-loading", Static)
        command_output = repo_info_error_app.screen.query_one("#repo-info-command-output", Static)
        archives_status = repo_info_error_app.screen.query_one("#repo-info-archives-status", Static)
        archives_table = repo_info_error_app.screen.query_one("#repo-info-archives-table", DataTable)

        assert str(cast(Any, loading).content) == "Failed to load live repository data."
        assert "borg unavailable" in str(cast(Any, command_output).content)
        assert str(cast(Any, archives_status).content) == "Archive list unavailable."
        assert archives_table.row_count == 0


async def test_repo_info_screen_shows_workspace_tree_for_local_repo(
    monkeypatch: pytest.MonkeyPatch,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
    tmp_path: Any,
) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_info_screen.socket.gethostname", lambda: repo_detail_repo.hostname)

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
    monkeypatch.setattr("borgboi.tui.repo_info_screen.socket.gethostname", lambda: "other-host")

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        workspace_status = repo_info_app.screen.query_one("#repo-info-workspace-status", Static)
        workspace_unavailable = repo_info_app.screen.query_one("#repo-info-workspace-unavailable", Static)

        assert "Workspace tree unavailable" in str(cast(Any, workspace_status).content)
        assert "only available for repositories on this machine" in str(cast(Any, workspace_unavailable).content)
        assert len(repo_info_app.screen.query("#repo-info-workspace-tree")) == 0


async def test_repo_info_screen_reports_missing_local_workspace_path(
    monkeypatch: pytest.MonkeyPatch,
    repo_detail_repo: Repository,
    repo_info_app: BorgBoiApp,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = (tmp_path / "missing-repo").as_posix()
    monkeypatch.setattr("borgboi.tui.repo_info_screen.socket.gethostname", lambda: repo_detail_repo.hostname)

    async with repo_info_app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(repo_info_app.screen, RepoInfoScreen)

        workspace_unavailable = repo_info_app.screen.query_one("#repo-info-workspace-unavailable", Static)

        assert "Repository path is not available on this machine" in str(cast(Any, workspace_unavailable).content)
        assert len(repo_info_app.screen.query("#repo-info-workspace-tree")) == 0
