from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from textual.widgets import Collapsible, Static

from borgboi.tui.app import BorgBoiApp
from borgboi.tui.screens import ConfigScreen
from borgboi.tui.widgets.config_panel import ConfigPanel, _aws_profile_display, _render_section

# -- Pure unit tests ----------------------------------------------------------


def test_render_section_escapes_plain_text_values() -> None:
    rendered = _render_section({"Repo Path": "/var/backups/[test]", "S3 Bucket": "bucket[name]"})

    assert "/var/backups/\\[test]" in rendered
    assert "bucket\\[name]" in rendered


def test_render_section_still_formats_booleans_as_colored_markup() -> None:
    rendered = _render_section({"Offline": True, "Debug": False})

    assert "[#a6e3a1]True[/]" in rendered
    assert "[#f38ba8]False[/]" in rendered


def test_aws_profile_display_uses_provider_chain_when_profile_unset() -> None:
    assert _aws_profile_display(None) == "provider chain"
    assert _aws_profile_display("sandbox") == "sandbox"


# -- Mounted widget tests ----------------------------------------------------


async def test_config_panel_renders_all_sections(tui_app: BorgBoiApp) -> None:
    async with tui_app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(tui_app.screen, ConfigScreen)
        panel = tui_app.screen.query_one("#config-panel", ConfigPanel)
        collapsibles = panel.query(Collapsible)
        # 5 sections: General, AWS, Borg, Retention, UI
        assert len(collapsibles) == 5


async def test_config_panel_no_config_shows_fallback() -> None:
    orchestrator = cast(Any, SimpleNamespace(list_repos=lambda: []))
    app = BorgBoiApp(config=None, orchestrator=orchestrator)

    async with app.run_test() as pilot:
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)
        panel = app.screen.query_one("#config-panel", ConfigPanel)
        statics = panel.query(Static)
        texts = [cast(Any, s).content for s in statics]
        assert any("No configuration loaded" in t for t in texts)
