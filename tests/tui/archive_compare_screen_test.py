from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.style import Style
from textual.widgets import DirectoryTree, Input, Select, Static, Switch

from borgboi.clients.borg import DiffResult, RepoArchive, RepoInfo
from borgboi.config import Config
from borgboi.core.models import Repository
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.features.archive_compare import (
    ArchiveCompareScreen,
    CompareDirectoryTree,
    build_compare_path_states,
    build_compare_tree_highlights,
    build_compare_tree_modified_paths,
    build_compare_tree_parent_indicators,
)
from borgboi.tui.features.repo_detail import RepoInfoScreen


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
    monkeypatch.setattr(
        "borgboi.tui.features.repo_detail.workspace.socket.gethostname", lambda: repo_detail_repo.hostname
    )
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


def test_build_compare_tree_highlights_assigns_side_specific_file_and_directory_colors(
    archive_compare_result: DiffResult,
) -> None:
    states = build_compare_path_states(archive_compare_result)

    older_highlights, newer_highlights = build_compare_tree_highlights(states)

    assert older_highlights[Path("removed.txt")] == "red"
    assert Path("added.txt") not in older_highlights
    assert Path("docs/file.txt") not in older_highlights
    assert Path("docs/mode.txt") not in older_highlights
    assert Path("docs") not in older_highlights
    assert Path("only-older") not in older_highlights

    assert newer_highlights[Path("added.txt")] == "green"
    assert Path("removed.txt") not in newer_highlights
    assert Path("docs/file.txt") not in newer_highlights
    assert Path("docs/mode.txt") not in newer_highlights
    assert Path("docs") not in newer_highlights


def test_build_compare_tree_modified_paths_marks_direct_modified_files_and_directories() -> None:
    result = DiffResult.model_validate(
        {
            "archive1": "older",
            "archive2": "newer",
            "entries": [
                {"path": "docs/file.txt", "changes": [{"type": "modified", "added": 2, "removed": 1}]},
                {
                    "path": "docs/mode.txt",
                    "changes": [{"type": "mode", "old_mode": "-rw-r--r--", "new_mode": "-rwxr-xr-x"}],
                },
                {"path": "direct-dir", "changes": [{"type": "modified", "added": 1, "removed": 0}]},
                {"path": "added-dir", "changes": [{"type": "added", "size": 1}]},
            ],
        }
    )

    older_modified, newer_modified = build_compare_tree_modified_paths(build_compare_path_states(result))

    assert Path("docs/file.txt") in older_modified
    assert Path("docs/file.txt") in newer_modified
    assert Path("docs/mode.txt") in older_modified
    assert Path("docs/mode.txt") in newer_modified
    assert Path("direct-dir") in older_modified
    assert Path("direct-dir") in newer_modified
    assert Path("added-dir") not in older_modified
    assert Path("added-dir") not in newer_modified


def test_build_compare_tree_parent_indicators_marks_ancestor_only_directories() -> None:
    result = DiffResult.model_validate(
        {
            "archive1": "older",
            "archive2": "newer",
            "entries": [
                {"path": "docs/subdir/removed.txt", "changes": [{"type": "removed", "size": 1}]},
                {"path": "docs/subdir/updated.txt", "changes": [{"type": "modified", "added": 2, "removed": 1}]},
                {"path": "direct-dir", "changes": [{"type": "removed", "size": 1}]},
            ],
        }
    )

    older_indicators, newer_indicators = build_compare_tree_parent_indicators(build_compare_path_states(result))

    assert Path("docs") in older_indicators
    assert Path("docs/subdir") in older_indicators
    assert Path("docs") in newer_indicators
    assert Path("docs/subdir") in newer_indicators
    assert Path("direct-dir") not in older_indicators
    assert Path("direct-dir") not in newer_indicators


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


async def test_archive_compare_screen_assigns_row_highlights_to_tree_nodes(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", CompareDirectoryTree)

        older_removed = await older_tree.find_node_by_relative_path(Path("removed.txt"))
        older_only_directory = await older_tree.find_node_by_relative_path(Path("only-older"))
        assert older_only_directory is not None
        older_only_directory.expand()
        await pilot.pause()
        older_only_file = await older_tree.find_node_by_relative_path(Path("only-older/file.txt"))
        newer_added = await newer_tree.find_node_by_relative_path(Path("added.txt"))
        older_docs = await older_tree.find_node_by_relative_path(Path("docs"))
        newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))

        assert older_docs is not None
        older_docs.expand()
        await pilot.pause()
        older_modified_file = await older_tree.find_node_by_relative_path(Path("docs/file.txt"))
        newer_modified_file = await newer_tree.find_node_by_relative_path(Path("docs/file.txt"))

        assert older_removed is not None
        assert older_only_file is not None
        assert newer_added is not None
        assert older_docs is not None
        assert newer_docs is not None
        assert older_modified_file is not None
        assert newer_modified_file is not None

        assert older_tree._highlight_for_node(older_removed) == "red"
        assert older_tree._highlight_for_node(older_only_directory) is None
        assert older_tree._highlight_for_node(older_only_file) == "red"
        assert newer_tree._highlight_for_node(newer_added) == "green"
        assert older_tree._highlight_for_node(older_docs) is None
        assert older_tree._highlight_for_node(older_modified_file) is None
        assert newer_tree._highlight_for_node(newer_modified_file) is None

        older_docs_label = older_tree.render_label(older_docs, Style(), Style())
        older_only_directory_label = older_tree.render_label(older_only_directory, Style(), Style())
        older_modified_file_label = older_tree.render_label(older_modified_file, Style(), Style())
        newer_modified_file_label = newer_tree.render_label(newer_modified_file, Style(), Style())
        assert "(modified)" in older_docs_label.plain
        assert "(modified)" in older_only_directory_label.plain
        assert "(modified)" in older_modified_file_label.plain
        assert "(modified)" in newer_modified_file_label.plain

        red_bg = CompareDirectoryTree.ROW_HIGHLIGHT_STYLES["red"].bgcolor
        green_bg = CompareDirectoryTree.ROW_HIGHLIGHT_STYLES["green"].bgcolor
        assert red_bg is not None
        assert green_bg is not None

        older_removed_strip = older_tree.render_line(older_removed.line)
        older_only_directory_strip = older_tree.render_line(older_only_directory.line)
        older_modified_file_strip = older_tree.render_line(older_modified_file.line)
        newer_added_strip = newer_tree.render_line(newer_added.line)
        newer_modified_file_strip = newer_tree.render_line(newer_modified_file.line)

        assert any(style is not None and style.bgcolor == red_bg for _, style, _ in older_removed_strip)
        assert all(style is None or style.bgcolor != red_bg for _, style, _ in older_only_directory_strip)
        assert any(style is not None and style.bgcolor == green_bg for _, style, _ in newer_added_strip)
        assert all(style is None or style.bgcolor != green_bg for _, style, _ in older_modified_file_strip)
        assert all(style is None or style.bgcolor != green_bg for _, style, _ in newer_modified_file_strip)


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
            if newer_docs is not None and newer_docs.is_expanded and screen.expanded_paths == frozenset({"docs"}):
                break

        assert older_docs.is_expanded is True
        assert newer_docs is not None
        assert newer_docs.is_expanded is True
        assert screen.expanded_paths == frozenset({"docs"})


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
            if newer_docs is not None and newer_docs.is_collapsed and screen.expanded_paths == frozenset():
                break

        assert older_docs.is_collapsed is True
        assert newer_docs is not None
        assert newer_docs.is_collapsed is True
        assert screen.expanded_paths == frozenset()


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
        assert screen.expanded_paths == frozenset({"only-older"})


async def test_archive_compare_screen_resets_expansion_state_on_new_compare(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        older_tree = screen.query_one("#archive-compare-older-tree", CompareDirectoryTree)
        newer_tree = screen.query_one("#archive-compare-newer-tree", CompareDirectoryTree)
        older_docs = await older_tree.find_node_by_relative_path(Path("docs"))
        newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))

        assert older_docs is not None
        older_docs.expand()

        for _ in range(40):
            await pilot.pause(0.05)
            newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))
            if newer_docs is not None and newer_docs.is_expanded and screen.expanded_paths == frozenset({"docs"}):
                break

        assert screen.expanded_paths == frozenset({"docs"})

        screen.action_run_compare()

        for _ in range(60):
            await pilot.pause(0.05)
            older_docs = await older_tree.find_node_by_relative_path(Path("docs"))
            newer_docs = await newer_tree.find_node_by_relative_path(Path("docs"))
            if (
                screen.expanded_paths == frozenset()
                and older_docs is not None
                and newer_docs is not None
                and older_docs.is_collapsed
                and newer_docs.is_collapsed
            ):
                break

        assert screen.expanded_paths == frozenset()
        assert older_docs is not None
        assert newer_docs is not None
        assert older_docs.is_collapsed is True
        assert newer_docs.is_collapsed is True


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


async def test_archive_compare_screen_clears_selected_file_when_directory_selected(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen._show_selected_path(screen._newer_root / "docs" / "file.txt")
        await pilot.pause()
        assert screen.selected_path == Path("docs/file.txt")

        screen._show_selected_path(screen._newer_root / "docs")
        await pilot.pause()

        assert screen.selected_path is None


async def test_archive_compare_screen_clears_selected_file_when_filters_hide_it(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen._show_selected_path(screen._newer_root / "docs" / "file.txt")
        await pilot.pause()
        assert screen.selected_path == Path("docs/file.txt")

        search_input = screen.query_one("#archive-compare-search-input", Input)
        search_input.value = "removed"
        await pilot.pause()

        assert screen.selected_path is None


async def test_archive_compare_screen_cleans_up_tempdir_on_dismiss(archive_compare_app: BorgBoiApp) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)
        temp_root = screen._compare_temp_root

        assert temp_root.exists() is True

        await pilot.press("escape")
        await pilot.pause()

        assert temp_root.exists() is False


async def test_archive_compare_screen_kind_filter_prunes_overlays_and_summary(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen.action_toggle_kind("added")
        screen.action_toggle_kind("modified")
        screen.action_toggle_kind("mode")
        await pilot.pause()

        assert set(screen._path_states) == {Path("removed.txt"), Path("only-older/file.txt")}
        assert Path("added.txt") not in screen._path_states
        assert Path("docs/file.txt") not in screen._path_states
        summary = screen.query_one("#archive-compare-summary", Static)
        assert "Changed paths:[/] 2" in str(cast(Any, summary).content)


async def test_archive_compare_screen_search_filter_matches_paths_case_insensitively(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        search_input = screen.query_one("#archive-compare-search-input", Input)
        search_input.value = "DOCS"
        await pilot.pause()

        assert set(screen._path_states) == {Path("docs/file.txt"), Path("docs/mode.txt")}

        screen.action_clear_filters()
        await pilot.pause()

        assert screen._path_states.keys() == screen._raw_path_states.keys()
        assert search_input.value == ""


async def test_archive_compare_screen_next_prev_change_cycles_and_selects(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen.action_next_change()
        await pilot.pause()
        assert screen.selected_path == screen._ordered_change_paths[0]

        screen.action_next_change()
        await pilot.pause()
        assert screen.selected_path == screen._ordered_change_paths[1]

        screen.action_prev_change()
        await pilot.pause()
        assert screen.selected_path == screen._ordered_change_paths[0]

        screen.action_prev_change()
        await pilot.pause()
        assert screen.selected_path == screen._ordered_change_paths[-1]


async def test_archive_compare_screen_re_derives_cursor_after_filter_reorders_list(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen.action_next_change()
        await pilot.pause()
        screen.action_next_change()
        await pilot.pause()
        screen.action_next_change()
        await pilot.pause()
        assert screen.selected_path == Path("docs/file.txt")
        assert screen._change_cursor == 2

        screen.action_toggle_kind("removed")
        await pilot.pause()

        assert screen.selected_path == Path("docs/file.txt")
        assert screen._change_cursor == 1


async def test_archive_compare_screen_opens_content_diff_modal_for_selected_path(
    archive_compare_app: BorgBoiApp,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        screen.selected_path = Path("docs/file.txt")
        screen.action_open_content_diff()
        await pilot.pause()

        from borgboi.tui.features.archive_compare import ContentDiffScreen

        assert isinstance(archive_compare_app.screen, ContentDiffScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(archive_compare_app.screen, ArchiveCompareScreen)


async def test_content_diff_modal_ignores_worker_result_after_dismissal(
    archive_compare_app: BorgBoiApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extract_started = threading.Event()
    allow_extract = threading.Event()

    def _slow_extract(*_args: Any, archive_name: str, **_kwargs: Any) -> SimpleNamespace:
        extract_started.set()
        allow_extract.wait(timeout=5)
        payload = b"before\n" if archive_name == "2026-03-27_22:00:00" else b"after\n"
        return SimpleNamespace(payload=payload, truncated=False)

    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)
        monkeypatch.setattr(
            screen._orchestrator,
            "extract_archived_file_capped",
            lambda repo, archive_name, file_path, *, max_bytes: _slow_extract(
                repo,
                archive_name=archive_name,
                file_path=file_path,
                max_bytes=max_bytes,
            ),
            raising=False,
        )

        screen.selected_path = Path("docs/file.txt")
        screen.action_open_content_diff()

        from borgboi.tui.features.archive_compare import ContentDiffScreen

        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(archive_compare_app.screen, ContentDiffScreen) and extract_started.is_set():
                break

        assert isinstance(archive_compare_app.screen, ContentDiffScreen)
        assert extract_started.is_set() is True

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(archive_compare_app.screen, ArchiveCompareScreen)

        allow_extract.set()
        for _ in range(60):
            await pilot.pause(0.05)

        assert isinstance(archive_compare_app.screen, ArchiveCompareScreen)


async def test_archive_compare_screen_clears_previous_diff_after_compare_failure(
    archive_compare_app: BorgBoiApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with archive_compare_app.run_test() as pilot:
        screen = await _open_archive_compare_screen(archive_compare_app, pilot)

        assert screen._path_states
        assert (screen._older_root / "removed.txt").exists() is True

        def _raise_diff_failure(*_args: Any, **_kwargs: Any) -> DiffResult:
            raise RuntimeError("compare boom")

        monkeypatch.setattr(screen._orchestrator, "diff_archives", _raise_diff_failure)
        screen.action_run_compare()

        for _ in range(60):
            await pilot.pause(0.05)
            if not screen._path_states:
                break

        summary = screen.query_one("#archive-compare-summary", Static)
        older_heading = screen.query_one("#archive-compare-older-heading", Static)
        newer_heading = screen.query_one("#archive-compare-newer-heading", Static)

        assert screen._path_states == {}
        assert (screen._older_root / "removed.txt").exists() is False
        assert (screen._newer_root / "added.txt").exists() is False
        assert "Archive comparison failed" in str(cast(Any, summary).content)
        assert "2026-03-27_22:00:00" in str(cast(Any, older_heading).content)
        assert "2026-03-28_22:00:00" in str(cast(Any, newer_heading).content)
