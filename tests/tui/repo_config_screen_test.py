from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from textual.widgets import Button, Input, Label, Static

from borgboi.config import Config
from borgboi.core.models import Repository, RetentionPolicy
from borgboi.tui.app import BorgBoiApp
from borgboi.tui.repo_config_screen import RepoConfigResult, RepoConfigScreen


def _build_host_app(config: Config, repo: Repository, **orchestrator_overrides: Any) -> BorgBoiApp:
    orchestrator = SimpleNamespace(
        config=config,
        list_repos=lambda: [repo],
        **orchestrator_overrides,
    )
    return BorgBoiApp(config=config, orchestrator=cast(Any, orchestrator))


async def test_repo_config_screen_allows_retention_editing_for_remote_repo(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
) -> None:
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: "other-host")
    app = _build_host_app(tui_config_with_excludes, repo_detail_repo)

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes)
        )
        await pilot.pause()

        assert isinstance(app.screen, RepoConfigScreen)

        quota_input = app.screen.query_one("#repo-config-quota-input", Input)
        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        status = app.screen.query_one("#repo-config-status", Label)
        current = app.screen.query_one("#repo-config-current", Static)

        assert quota_input.disabled is True
        assert daily_input.disabled is False
        assert "Retention can be edited here" in str(cast(Any, status).content)
        assert "Current Quota" in str(cast(Any, current).content)
        assert "Unknown" in str(cast(Any, current).content)
        assert "Unavailable" in str(cast(Any, current).content)


async def test_repo_config_screen_disables_quota_after_load_failure(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)
    app = _build_host_app(
        tui_config_with_excludes,
        repo_detail_repo,
        get_repo_storage_quota=lambda _repo: (_ for _ in ()).throw(RuntimeError("quota unavailable")),
    )

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes)
        )
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoConfigScreen)

        quota_input = app.screen.query_one("#repo-config-quota-input", Input)
        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        current = app.screen.query_one("#repo-config-current", Static)
        assert quota_input.disabled is True
        assert daily_input.disabled is False
        assert "Unavailable" in str(cast(Any, current).content)


async def test_repo_config_screen_can_clear_repo_specific_quota(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    assert repo_detail_repo.retention_policy is not None
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    results: list[RepoConfigResult | None] = []
    seen_storage_quotas: list[str | None] = []

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        seen_storage_quotas.append(kwargs.get("storage_quota"))
        return None, repo_detail_repo.retention_policy

    app = _build_host_app(
        tui_config_with_excludes,
        repo_detail_repo,
        get_repo_storage_quota=lambda _repo: "100G",
        update_repo_config=update_repo_config,
    )

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes),
            callback=results.append,
        )
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoConfigScreen)

        quota_input = app.screen.query_one("#repo-config-quota-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)

        import asyncio

        for _ in range(20):
            if quota_input.value == "100G":
                break
            await asyncio.sleep(0.1)

        quota_input.value = ""
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if results:
                break
            await asyncio.sleep(0.1)

        assert seen_storage_quotas == [""]
        assert results == [
            RepoConfigResult(
                quota=None,
                retention_policy=repo_detail_repo.retention_policy,
                quota_load_failed=False,
                quota_load_error=None,
            )
        ]


async def test_repo_config_screen_preserves_loaded_quota_for_retention_only_save(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    assert repo_detail_repo.retention_policy is not None
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    results: list[RepoConfigResult | None] = []
    seen_storage_quotas: list[str | None] = []

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        seen_storage_quotas.append(kwargs.get("storage_quota"))
        return None, kwargs["retention_policy"]

    app = _build_host_app(
        tui_config_with_excludes,
        repo_detail_repo,
        get_repo_storage_quota=lambda _repo: "100G",
        update_repo_config=update_repo_config,
    )

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes),
            callback=results.append,
        )
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoConfigScreen)

        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)

        import asyncio

        for _ in range(20):
            if app.screen.query_one("#repo-config-quota-input", Input).value == "100G":
                break
            await asyncio.sleep(0.1)

        daily_input.value = "30"
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if results:
                break
            await asyncio.sleep(0.1)

        assert seen_storage_quotas == [None]
        assert results == [
            RepoConfigResult(
                quota="100G",
                retention_policy=RetentionPolicy(keep_daily=30, keep_weekly=8, keep_monthly=12, keep_yearly=2),
                quota_load_failed=False,
                quota_load_error=None,
            )
        ]


async def test_repo_config_screen_preserves_inherited_retention_on_quota_only_save(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    repo_detail_repo.retention_policy = None
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    results: list[RepoConfigResult | None] = []
    seen_retention_policies: list[RetentionPolicy | None] = []
    seen_clear_flags: list[bool] = []

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        seen_retention_policies.append(kwargs.get("retention_policy"))
        seen_clear_flags.append(kwargs.get("clear_retention_policy", False))
        return "250G", None

    app = _build_host_app(
        tui_config_with_excludes,
        repo_detail_repo,
        get_repo_storage_quota=lambda _repo: "100G",
        update_repo_config=update_repo_config,
    )

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes),
            callback=results.append,
        )
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoConfigScreen)

        quota_input = app.screen.query_one("#repo-config-quota-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)

        import asyncio

        for _ in range(20):
            if quota_input.value == "100G":
                break
            await asyncio.sleep(0.1)

        quota_input.value = "250G"
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if results:
                break
            await asyncio.sleep(0.1)

        assert seen_retention_policies == [None]
        assert seen_clear_flags == [False]
        assert results == [
            RepoConfigResult(
                quota="250G",
                retention_policy=None,
                quota_load_failed=False,
                quota_load_error=None,
            )
        ]


async def test_repo_config_screen_clears_override_when_form_matches_defaults(
    monkeypatch: Any,
    tui_config_with_excludes: Config,
    repo_detail_repo: Repository,
    tmp_path: Any,
) -> None:
    repo_detail_repo.path = tmp_path.as_posix()
    repo_detail_repo.retention_policy = RetentionPolicy(keep_daily=30, keep_weekly=8, keep_monthly=12, keep_yearly=2)
    monkeypatch.setattr("borgboi.tui.repo_workspace.socket.gethostname", lambda: repo_detail_repo.hostname)

    results: list[RepoConfigResult | None] = []
    seen_retention_policies: list[RetentionPolicy | None] = []
    seen_clear_flags: list[bool] = []

    def update_repo_config(**kwargs: Any) -> tuple[str | None, RetentionPolicy | None]:
        seen_retention_policies.append(kwargs.get("retention_policy"))
        seen_clear_flags.append(kwargs.get("clear_retention_policy", False))
        return None, None

    app = _build_host_app(
        tui_config_with_excludes,
        repo_detail_repo,
        get_repo_storage_quota=lambda _repo: "100G",
        update_repo_config=update_repo_config,
    )

    async with app.run_test() as pilot:
        await app.push_screen(
            RepoConfigScreen(repo=repo_detail_repo, orchestrator=app.orchestrator, config=tui_config_with_excludes),
            callback=results.append,
        )
        await pilot.pause(0.2)

        assert isinstance(app.screen, RepoConfigScreen)

        import asyncio

        daily_input = app.screen.query_one("#repo-config-daily-input", Input)
        weekly_input = app.screen.query_one("#repo-config-weekly-input", Input)
        monthly_input = app.screen.query_one("#repo-config-monthly-input", Input)
        yearly_input = app.screen.query_one("#repo-config-yearly-input", Input)
        save_button = app.screen.query_one("#repo-config-save-btn", Button)

        for _ in range(20):
            if daily_input.value == "30":
                break
            await asyncio.sleep(0.1)

        daily_input.value = str(tui_config_with_excludes.borg.retention.keep_daily)
        weekly_input.value = str(tui_config_with_excludes.borg.retention.keep_weekly)
        monthly_input.value = str(tui_config_with_excludes.borg.retention.keep_monthly)
        yearly_input.value = str(tui_config_with_excludes.borg.retention.keep_yearly)
        app.screen.on_button_pressed(Button.Pressed(save_button))

        for _ in range(20):
            if results:
                break
            await asyncio.sleep(0.1)

        assert seen_retention_policies == [None]
        assert seen_clear_flags == [True]
        assert results == [
            RepoConfigResult(
                quota="100G",
                retention_policy=None,
                quota_load_failed=False,
                quota_load_error=None,
            )
        ]
