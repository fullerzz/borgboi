from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.widgets import Link, Static, Tabs, TextArea

from borgboi.config import Config
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.excludes_screen import (
    _EDITING_STATUS,
    _EXCLUDES_HELP_URL,
    DefaultExcludesScreen,
    load_default_excludes_document,
    load_repo_excludes_document,
)

from .conftest import build_repo


def _build_excludes_app(cfg: Config) -> BorgBoiApp:
    """Build a BorgBoiApp wired to the given config."""
    return BorgBoiApp(
        config=cfg,
        orchestrator=cast(
            Any,
            SimpleNamespace(list_repos=lambda: [build_repo("alpha")]),
        ),
    )


# -- Pure unit tests (no async, no pilot) ------------------------------------


def test_load_default_excludes_document_reads_shared_file(tui_config_with_excludes: Config) -> None:
    excludes_path = tui_config_with_excludes.borgboi_dir / tui_config_with_excludes.excludes_filename

    document = load_default_excludes_document(tui_config_with_excludes)

    assert document.path == excludes_path
    assert document.exists is True
    assert document.body == "*.tmp\n"
    assert "repo-specific excludes file" in document.status


def test_load_default_excludes_document_returns_missing_state(tui_config: Config) -> None:
    document = load_default_excludes_document(tui_config)

    assert document.path == tui_config.borgboi_dir / tui_config.excludes_filename
    assert document.exists is False
    assert document.body == (
        "Create this file to define shared exclude patterns for repositories without a repo-specific excludes file."
    )
    assert document.status == "No shared default excludes file found."


def test_load_repo_excludes_document_returns_fallback_state(tui_config_with_excludes: Config) -> None:
    document = load_repo_excludes_document(tui_config_with_excludes, "alpha", index=1)

    assert document.path == tui_config_with_excludes.borgboi_dir / f"alpha_{tui_config_with_excludes.excludes_filename}"
    assert document.exists is False
    assert document.body == "Create this file to override shared exclude patterns for this repository."
    assert (
        document.status
        == "No repo-specific excludes file found. BorgBoi falls back to the shared default excludes file."
    )


# -- Async pilot tests -------------------------------------------------------


async def test_tui_can_open_switch_and_close_excludes_screen(tui_config: Config) -> None:
    default_excludes_path = tui_config.borgboi_dir / tui_config.excludes_filename
    repo_excludes_path = tui_config.borgboi_dir / f"alpha_{tui_config.excludes_filename}"
    default_excludes_path.write_text("*.tmp\n.cache/\n")
    repo_excludes_path.write_text("node_modules/\n.env\n")

    app = _build_excludes_app(tui_config)

    async with app.run_test() as pilot:
        await pilot.press("e")

        assert isinstance(app.screen, DefaultExcludesScreen)

        tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
        help_link = app.screen.query_one("#default-excludes-help-link", Link)
        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
        status = app.screen.query_one("#default-excludes-status", Static)

        assert viewer.read_only is True
        assert help_link.text == "Exclude pattern help (Borg docs)"
        assert help_link.url == _EXCLUDES_HELP_URL
        assert tabs.active_tab is not None
        assert tabs.active_tab.id == "default-excludes"
        assert viewer.text == "*.tmp\n.cache/\n"
        assert (
            cast(Any, status).content == "Shared excludes apply when a repository has no repo-specific excludes file."
        )

        await pilot.press("right")

        assert tabs.active_tab is not None
        assert tabs.active_tab.id == "repo-1"
        assert viewer.text == "node_modules/\n.env\n"
        assert cast(Any, status).content == "Repo-specific excludes override the shared default for this repository."

        await pilot.press("escape")
        assert not isinstance(app.screen, DefaultExcludesScreen)


async def test_tui_excludes_help_link_activation_opens_docs(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
) -> None:
    app = _build_excludes_app(tui_config_with_excludes)
    opened_urls: list[tuple[str, bool]] = []

    def open_url(url: str, *, new_tab: bool = True) -> None:
        opened_urls.append((url, new_tab))

    monkeypatch.setattr(app, "open_url", open_url)

    async with app.run_test() as pilot:
        await pilot.press("e")

        assert isinstance(app.screen, DefaultExcludesScreen)

        help_link = app.screen.query_one("#default-excludes-help-link", Link)
        help_link.focus()

        await pilot.press("enter")

        assert opened_urls == [(_EXCLUDES_HELP_URL, True)]


async def test_tui_edit_save_writes_file_to_disk(tui_config_with_excludes: Config) -> None:
    excludes_path = tui_config_with_excludes.borgboi_dir / tui_config_with_excludes.excludes_filename
    app = _build_excludes_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
        assert viewer.read_only is True

        await pilot.press("ctrl+e")
        assert viewer.read_only is False
        assert viewer.has_class("-editing")

        viewer.load_text("*.tmp\n.cache/\n")

        await pilot.press("ctrl+s")
        assert viewer.read_only is True

        assert excludes_path.read_text() == "*.tmp\n.cache/\n"


async def test_tui_edit_cancel_reverts_content(tui_config_with_excludes: Config) -> None:
    excludes_path = tui_config_with_excludes.borgboi_dir / tui_config_with_excludes.excludes_filename
    app = _build_excludes_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

        await pilot.press("ctrl+e")
        viewer.load_text("CHANGED\n")
        assert viewer.text == "CHANGED\n"

        await pilot.press("escape")
        assert viewer.read_only is True
        assert viewer.text == "*.tmp\n"

        assert excludes_path.read_text() == "*.tmp\n"


async def test_tui_edit_creates_nonexistent_file(tui_config: Config) -> None:
    repo_excludes_path = tui_config.borgboi_dir / f"alpha_{tui_config.excludes_filename}"
    assert not repo_excludes_path.exists()

    app = _build_excludes_app(tui_config)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
        await pilot.press("right")
        assert tabs.active_tab is not None
        assert tabs.active_tab.id == "repo-1"

        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

        await pilot.press("ctrl+e")
        assert viewer.read_only is False
        assert viewer.text == ""

        viewer.load_text("node_modules/\n")
        await pilot.press("ctrl+s")

        assert repo_excludes_path.exists()
        assert repo_excludes_path.read_text() == "node_modules/\n"


async def test_tui_tab_switch_while_editing_discards_changes(tui_config: Config) -> None:
    default_excludes_path = tui_config.borgboi_dir / tui_config.excludes_filename
    repo_excludes_path = tui_config.borgboi_dir / f"alpha_{tui_config.excludes_filename}"
    default_excludes_path.write_text("*.tmp\n")
    repo_excludes_path.write_text("node_modules/\n")

    app = _build_excludes_app(tui_config)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

        await pilot.press("ctrl+e")
        viewer.load_text("UNSAVED\n")

        # Should discard edits and exit edit mode
        tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
        tabs.active = "repo-1"
        await pilot.pause()
        assert viewer.read_only is True
        assert viewer.text == "node_modules/\n"

        assert default_excludes_path.read_text() == "*.tmp\n"


async def test_tui_save_failure_keeps_editing_and_notifies(
    monkeypatch: pytest.MonkeyPatch,
    tui_config_with_excludes: Config,
) -> None:
    excludes_path = tui_config_with_excludes.borgboi_dir / tui_config_with_excludes.excludes_filename
    app = _build_excludes_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

        await pilot.press("ctrl+e")
        viewer.load_text("*.tmp\n.cache/\n")

        def fail_write_text(*args: Any, **kwargs: Any) -> None:
            raise OSError("Permission denied")

        monkeypatch.setattr(type(excludes_path), "write_text", fail_write_text)
        await pilot.press("ctrl+s")

        assert viewer.read_only is False
        assert viewer.text == "*.tmp\n.cache/\n"

        assert excludes_path.read_text() == "*.tmp\n"


async def test_tui_edit_status_shows_editing_indicator(tui_config_with_excludes: Config) -> None:
    app = _build_excludes_app(tui_config_with_excludes)

    async with app.run_test() as pilot:
        await pilot.press("e")
        assert isinstance(app.screen, DefaultExcludesScreen)

        status = app.screen.query_one("#default-excludes-status", Static)
        original_status = cast(Any, status).content

        await pilot.press("ctrl+e")
        assert _EDITING_STATUS in cast(Any, status).content

        await pilot.press("escape")
        assert cast(Any, status).content == original_status
