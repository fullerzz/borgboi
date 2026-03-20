import asyncio
from types import SimpleNamespace
from typing import Any, cast

from textual.widgets import Link, Static, Tabs, TextArea

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.excludes_screen import (
    _EDITING_STATUS,
    DefaultExcludesScreen,
    load_default_excludes_document,
    load_repo_excludes_document,
)


def build_repo(name: str) -> BorgBoiRepo:
    return BorgBoiRepo(
        name=name,
        path=f"/Users/test/{name}",
        hostname="test-host",
        os_platform="Darwin",
        backup_target="local",
        metadata=None,
    )


def test_load_default_excludes_document_reads_shared_file(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n.cache/\n")

    document = load_default_excludes_document(cfg)

    assert document.path == excludes_path
    assert document.exists is True
    assert document.body == "*.tmp\n.cache/\n"
    assert "repo-specific excludes file" in document.status


def test_load_default_excludes_document_returns_missing_state(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)

    document = load_default_excludes_document(cfg)

    assert document.path == cfg.borgboi_dir / cfg.excludes_filename
    assert document.exists is False
    assert document.body == (
        "Create this file to define shared exclude patterns for repositories without a repo-specific excludes file."
    )
    assert document.status == "No shared default excludes file found."


def test_load_repo_excludes_document_returns_fallback_state(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    document = load_repo_excludes_document(cfg, "alpha", index=1)

    assert document.path == cfg.borgboi_dir / f"alpha_{cfg.excludes_filename}"
    assert document.exists is False
    assert document.body == "Create this file to override shared exclude patterns for this repository."
    assert (
        document.status
        == "No repo-specific excludes file found. BorgBoi falls back to the shared default excludes file."
    )


def test_tui_can_open_switch_and_close_excludes_screen(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    repo_excludes_path = cfg.borgboi_dir / f"alpha_{cfg.excludes_filename}"
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n.cache/\n")
    repo_excludes_path.write_text("node_modules/\n.env\n")

    app = BorgBoiApp(
        config=cfg,
        orchestrator=cast(Any, SimpleNamespace(list_repos=lambda: [build_repo("alpha")])),
    )

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")

            assert isinstance(app.screen, DefaultExcludesScreen)

            tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
            help_link = app.screen.query_one("#default-excludes-help-link", Link)
            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
            status = app.screen.query_one("#default-excludes-status", Static)

            assert viewer.read_only is True
            assert help_link.text == "Exclude pattern help (Borg docs)"
            assert help_link.url == "https://borgbackup.readthedocs.io/en/stable/usage/help.html"
            assert tabs.active_tab is not None
            assert tabs.active_tab.id == "default-excludes"
            assert viewer.text == "*.tmp\n.cache/\n"
            assert (
                cast(Any, status).content
                == "Shared excludes apply when a repository has no repo-specific excludes file."
            )

            await pilot.press("right")

            assert tabs.active_tab is not None
            assert tabs.active_tab.id == "repo-1"
            assert viewer.text == "node_modules/\n.env\n"
            assert (
                cast(Any, status).content == "Repo-specific excludes override the shared default for this repository."
            )

            await pilot.press("escape")
            assert not isinstance(app.screen, DefaultExcludesScreen)

    asyncio.run(run_test())


def test_tui_excludes_help_link_activation_opens_docs(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")

    app = _build_excludes_app(cfg)
    opened_urls: list[tuple[str, bool]] = []

    def open_url(url: str, *, new_tab: bool = True) -> None:
        opened_urls.append((url, new_tab))

    monkeypatch.setattr(app, "open_url", open_url)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")

            assert isinstance(app.screen, DefaultExcludesScreen)

            help_link = app.screen.query_one("#default-excludes-help-link", Link)
            help_link.focus()

            await pilot.press("enter")

            assert opened_urls == [("https://borgbackup.readthedocs.io/en/stable/usage/help.html", True)]

    asyncio.run(run_test())


def _build_excludes_app(
    cfg: Config,
    repos: list[BorgBoiRepo] | None = None,
) -> BorgBoiApp:
    """Build a BorgBoiApp wired to the given config and repos."""
    return BorgBoiApp(
        config=cfg,
        orchestrator=cast(
            Any,
            SimpleNamespace(list_repos=lambda: repos or [build_repo("alpha")]),
        ),
    )


def test_tui_edit_save_writes_file_to_disk(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
            assert viewer.read_only is True

            # Enter edit mode
            await pilot.press("ctrl+e")
            assert viewer.read_only is False
            assert app.screen._editing is True

            # Replace content
            viewer.load_text("*.tmp\n.cache/\n")

            # Save
            await pilot.press("ctrl+s")
            assert viewer.read_only is True
            assert app.screen._editing is False

            # Verify file on disk
            assert excludes_path.read_text() == "*.tmp\n.cache/\n"

    asyncio.run(run_test())


def test_tui_edit_cancel_reverts_content(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

            # Enter edit mode and modify
            await pilot.press("ctrl+e")
            viewer.load_text("CHANGED\n")
            assert viewer.text == "CHANGED\n"

            # Cancel with escape
            await pilot.press("escape")
            assert viewer.read_only is True
            assert app.screen._editing is False
            assert viewer.text == "*.tmp\n"

            # File on disk unchanged
            assert excludes_path.read_text() == "*.tmp\n"

    asyncio.run(run_test())


def test_tui_edit_creates_nonexistent_file(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    repo_excludes_path = cfg.borgboi_dir / f"alpha_{cfg.excludes_filename}"
    cfg.borgboi_dir.mkdir(parents=True, exist_ok=True)
    assert not repo_excludes_path.exists()

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            # Switch to repo tab
            tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
            await pilot.press("right")
            assert tabs.active_tab is not None
            assert tabs.active_tab.id == "repo-1"

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

            # Enter edit mode on non-existent file
            await pilot.press("ctrl+e")
            assert viewer.read_only is False
            assert viewer.text == ""  # Cleared for editing

            # Type content and save
            viewer.load_text("node_modules/\n")
            await pilot.press("ctrl+s")

            # File should now exist
            assert repo_excludes_path.exists()
            assert repo_excludes_path.read_text() == "node_modules/\n"

    asyncio.run(run_test())


def test_tui_tab_switch_while_editing_discards_changes(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    repo_excludes_path = cfg.borgboi_dir / f"alpha_{cfg.excludes_filename}"
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")
    repo_excludes_path.write_text("node_modules/\n")

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

            # Enter edit mode on default tab
            await pilot.press("ctrl+e")
            viewer.load_text("UNSAVED\n")

            # Switch tabs programmatically — should discard edits and exit edit mode
            tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
            tabs.active = "repo-1"
            await pilot.pause()
            assert app.screen._editing is False
            assert viewer.read_only is True
            assert viewer.text == "node_modules/\n"

            # Original file unchanged
            assert default_excludes_path.read_text() == "*.tmp\n"

    asyncio.run(run_test())


def test_tui_save_failure_keeps_editing_and_notifies(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)

            # Enter edit mode and modify
            await pilot.press("ctrl+e")
            viewer.load_text("*.tmp\n.cache/\n")

            # Make write_text raise OSError
            def fail_write_text(*args: Any, **kwargs: Any) -> None:
                raise OSError("Permission denied")

            monkeypatch.setattr(type(excludes_path), "write_text", fail_write_text)
            await pilot.press("ctrl+s")

            # Should still be in edit mode
            assert app.screen._editing is True
            assert viewer.read_only is False
            assert viewer.text == "*.tmp\n.cache/\n"

            # File on disk unchanged
            assert excludes_path.read_text() == "*.tmp\n"

    asyncio.run(run_test())


def test_tui_edit_status_shows_editing_indicator(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n")

    app = _build_excludes_app(cfg)

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")
            assert isinstance(app.screen, DefaultExcludesScreen)

            status = app.screen.query_one("#default-excludes-status", Static)
            original_status = cast(Any, status).content

            # Enter edit mode
            await pilot.press("ctrl+e")
            assert _EDITING_STATUS in cast(Any, status).content

            # Exit edit mode
            await pilot.press("escape")
            assert cast(Any, status).content == original_status

    asyncio.run(run_test())
