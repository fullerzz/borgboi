import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from textual.widgets import Static, Tabs, TextArea

from borgboi.config import Config
from borgboi.models import BorgBoiRepo
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.excludes_screen import (
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
        orchestrator=cast(Any, SimpleNamespace(list_repos=Mock(return_value=[build_repo("alpha")]))),
    )

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")

            assert isinstance(app.screen, DefaultExcludesScreen)

            tabs = app.screen.query_one("#default-excludes-tabs", Tabs)
            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
            status = app.screen.query_one("#default-excludes-status", Static)

            assert viewer.read_only is True
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
