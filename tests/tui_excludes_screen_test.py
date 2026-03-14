import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

from textual.widgets import TextArea

from borgboi.config import Config
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.excludes_screen import DefaultExcludesScreen, load_default_excludes_document


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


def test_tui_can_open_and_close_default_excludes_screen(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    excludes_path.parent.mkdir(parents=True, exist_ok=True)
    excludes_path.write_text("*.tmp\n.cache/\n")

    app = BorgBoiApp(
        config=cfg,
        orchestrator=cast(Any, SimpleNamespace(list_repos=Mock(return_value=[]))),
    )

    async def run_test() -> None:
        async with app.run_test() as pilot:
            await pilot.press("e")

            assert isinstance(app.screen, DefaultExcludesScreen)

            viewer = app.screen.query_one("#default-excludes-viewer", TextArea)
            assert viewer.read_only is True
            assert viewer.text == "*.tmp\n.cache/\n"

            await pilot.press("escape")
            assert not isinstance(app.screen, DefaultExcludesScreen)

    asyncio.run(run_test())
