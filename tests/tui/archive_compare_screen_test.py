from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.widgets import DirectoryTree, Select, Static, Switch

from borgboi.clients.borg import DiffResult, RepoArchive, RepoInfo
from borgboi.config import Config
from borgboi.core.models import Repository
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.archive_compare_screen import ArchiveCompareScreen, CompareDirectoryTree, build_compare_path_states
from borgboi.tui.repo_info_screen import RepoInfoScreen


@pytest.fixture
def archive_compare_result() -> DiffResult:
    return DiffResult.model_validate(
        {
            "archive1": "2026-03-27_22:00:00",
            "archive2": "2026-03-28_22:00:00",
            "entries": [
                {"path": "added.txt", "changes": [{"type": "added", "size": 42}]},
                {"path": "removed.txt", "changes": [{"type": "removed", "size": 11}]},
                {"path": "only-older/file.txt", "changes": [{"type": "removed", "size": 7}]},
                {"path": "docs/file.txt", "changes": [{"type": "modified", "added": 12, "removed": 4}]},
                {
                    "path": "docs/mode.txt",
                    "changes": [{"type": "mode", "old_mode": "-rw-r--r--", "new_mode": "-rwxr-xr-x"}],
                },
            ],
        }
    )


@pytest.fixture
def archive_compare_app(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    live_repo_info: RepoInfo,
    repo_archives: list[RepoArchive],
    archive_compare_result: DiffResult,
) -> BorgBoiApp:
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)
    repo_detail_repo.path = tui_config_with_excludes.borgboi_dir.as_posix()

    return BorgBoiApp(
        config=tui_config_with_excludes,
        orchestrator=cast(
            Any,
            SimpleNamespace(
                config=tui_config_with_excludes,
                list_repos=lambda: [repo_detail_repo],
                get_repo_info=lambda _repo: live_repo_info,
                list_archives=lambda _repo: repo_archives,
                get_two_most_recent_archives=lambda _repo: (repo_archives[1], repo_archives[0]),
                diff_archives=lambda _repo, archive1, archive2, options=None, **_: archive_compare_result,
                get_repo_storage_quota=lambda _repo: "100G",
                update_repo_storage_quota=lambda quota, **_: quota.upper(),
                update_repo_config=lambda **kwargs: (
                    None if kwargs.get("storage_quota") == "" else kwargs.get("storage_quota", "100G"),
                    kwargs.get("retention_policy", repo_detail_repo.retention_policy),
                ),
            ),
        ),
    )


def test_build_compare_path_states_assigns_archive_side_presence(archive_compare_result: DiffResult) -> None:
    states = build_compare_path_states(archive_compare_result)

    assert states[cast(Any, next(path for path in states if path.as_posix() == "added.txt"))].older_exists is False
    assert states[cast(Any, next(path for path in states if path.as_posix() == "added.txt"))].newer_exists is True
    assert states[cast(Any, next(path for path in states if path.as_posix() == "removed.txt"))].older_exists is True
    assert states[cast(Any, next(path for path in states if path.as_posix() == "removed.txt"))].newer_exists is False
    assert states[cast(Any, next(path for path in states if path.as_posix() == "docs/file.txt"))].older_exists is True
    assert states[cast(Any, next(path for path in states if path.as_posix() == "docs/file.txt"))].newer_exists is True


async def _open_archive_compare_screen(app: BorgBoiApp, pilot: Any) -> ArchiveCompareScreen:
    await pilot.pause()
    await pilot.press("i")
    await pilot.pause()
    assert isinstance(app.screen, RepoInfoScreen)
    await pilot.press("d")

    for _ in range(60):
        await pilot.pause(0.05)
        if isinstance(app.screen, ArchiveCompareScreen) and app.screen._path_states:
            break

    assert isinstance(app.screen, ArchiveCompareScreen)
    return app.screen


async def test_archive_compare_screen_builds_changed_path_trees(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", DirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", DirectoryTree)
        summary = screen.query_one("#archive-compare-summary", Static)
        older_select = screen.query_one("#archive-compare-older-select", Select)
        newer_select = screen.query_one("#archive-compare-newer-select", Select)
        content_only = screen.query_one("#archive-compare-content-only-switch", Switch)

        assert screen._compare_temp_root.exists() is True
        assert older_tree.path == screen._older_root
        assert newer_tree.path == screen._newer_root
        assert older_select.value == "2026-03-27_22:00:00"
        assert newer_select.value == "2026-03-28_22:00:00"
        assert content_only.value is False

        assert (screen._older_root / "removed.txt").exists() is True
        assert (screen._newer_root / "removed.txt").exists() is False
        assert (screen._older_root / "added.txt").exists() is False
        assert (screen._newer_root / "added.txt").exists() is True
        assert (screen._older_root / "docs" / "file.txt").exists() is True
        assert (screen._newer_root / "docs" / "file.txt").exists() is True
        assert "Changed paths" in str(cast(Any, summary).content)
        assert "2026-03-27_22:00:00" in str(cast(Any, summary).content)
        assert "2026-03-28_22:00:00" in str(cast(Any, summary).content)


async def test_archive_compare_screen_mirrors_directory_expansion_when_path_exists(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", CompareDirectoryTree)
        older_docs = await older_tree.find_node_by_relative_path(Path("docs"))
        newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))

        assert older_docs is not None
        assert newer_docs is not None
        assert older_docs.is_collapsed is True
        assert newer_docs.is_collapsed is True

        older_docs.expand()

        for _ in range(40):
            await pilot.pause(0.05)
            newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))
            if newer_docs is not None and newer_docs.is_expanded:
                break

        assert older_docs.is_expanded is True
        assert newer_docs is not None
        assert newer_docs.is_expanded is True


async def test_archive_compare_screen_mirrors_directory_collapse_when_path_exists(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", CompareDirectoryTree)
        older_docs = await older_tree.find_node_by_relative_path(Path("docs"))
        newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))

        assert older_docs is not None
        assert newer_docs is not None

        older_docs.expand()

        for _ in range(40):
            await pilot.pause(0.05)
            newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))
            if newer_docs is not None and newer_docs.is_expanded:
                break

        assert newer_docs is not None
        assert older_docs.is_expanded is True
        assert newer_docs.is_expanded is True

        older_docs.collapse()

        for _ in range(40):
            await pilot.pause(0.05)
            newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))
            if newer_docs is not None and newer_docs.is_collapsed:
                break

        assert older_docs.is_collapsed is True
        assert newer_docs is not None
        assert newer_docs.is_collapsed is True


async def test_archive_compare_screen_ignores_missing_matching_directory(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", CompareDirectoryTree)
        older_only = await older_tree.find_node_by_relative_path(Path("only-older"))

        assert older_only is not None
        assert older_only.allow_expand is True
        assert await newer_tree.find_node_by_relative_path(Path("only-older")) is None

        older_only.expand()

        for _ in range(10):
            await pilot.pause(0.05)

        assert older_only.is_expanded is True
        assert await newer_tree.find_node_by_relative_path(Path("only-older")) is None


async def test_archive_compare_screen_updates_selected_path_details(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen._show_selected_path(screen._newer_root / "docs" / "file.txt")
        await pilot.pause()

        selection = screen.query_one("#archive-compare-selection", Static)
        assert "docs/file.txt" in str(cast(Any, selection).content)
        assert "modified" in str(cast(Any, selection).content)
        assert "Older" in str(cast(Any, selection).content)
        assert "Newer" in str(cast(Any, selection).content)


async def test_archive_compare_screen_cleans_up_tempdir_on_dismiss(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)
        temp_root = screen._compare_temp_root

        assert temp_root.exists() is True

        await pilot.press("escape")
        await pilot.pause()

        assert temp_root.exists() is False
