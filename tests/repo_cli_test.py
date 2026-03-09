from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.cli import repo as repo_module


def test_repo_list_renders_repos_table(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SimpleNamespace(name="repo-one")
    orchestrator = SimpleNamespace(list_repos=Mock(return_value=[repo]))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    render = Mock()

    monkeypatch.setattr("borgboi.rich_utils.output_repos_table", render)

    repo_module.repo_list(ctx=cast(Any, ctx))

    render.assert_called_once_with([repo])


def test_repo_list_routes_errors_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(orchestrator=SimpleNamespace(list_repos=Mock(side_effect=RuntimeError("boom"))))

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="boom"):
        repo_module.repo_list(ctx=cast(Any, ctx))


def test_repo_info_raw_prints_raw_repo_data(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_info = {"archives": 3}
    repo = SimpleNamespace(name="repo-one", path="/repo/one", metadata=None)
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo), get_repo_info=Mock(return_value=raw_info))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module.console, "print", console_print)

    repo_module.repo_info(name="repo-one", raw=True, ctx=cast(Any, ctx))

    console_print.assert_called_once_with(raw_info)
    orchestrator.get_repo_info.assert_called_once_with(repo, passphrase=None)


def test_repo_info_with_metadata_renders_formatted_repo_info(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = SimpleNamespace(
        cache=SimpleNamespace(total_size_gb="5.0", total_csize_gb="2.5", unique_csize_gb="1.0"),
        encryption=SimpleNamespace(mode="repokey"),
        repository=SimpleNamespace(id="repo-id", location="/repo/one", last_modified="2026-01-01T00:00:00"),
    )
    repo = SimpleNamespace(name="repo-one", path="/repo/one", metadata=metadata)
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo), get_repo_info=Mock(return_value=object()))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    render = Mock()

    monkeypatch.setattr("borgboi.rich_utils.output_repo_info", render)

    repo_module.repo_info(name="repo-one", ctx=cast(Any, ctx))

    render.assert_called_once_with(
        name="repo-one",
        total_size_gb="5.0",
        total_csize_gb="2.5",
        unique_csize_gb="1.0",
        encryption_mode="repokey",
        repo_id="repo-id",
        repo_location="/repo/one",
        last_modified="2026-01-01T00:00:00",
    )


def test_repo_info_without_metadata_prints_basic_name_and_path(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SimpleNamespace(name="repo-one", path="/repo/one", metadata=None)
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo), get_repo_info=Mock(return_value=object()))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module.console, "print", console_print)

    repo_module.repo_info(name="repo-one", ctx=cast(Any, ctx))

    assert console_print.call_args_list == [
        (("Repository: [bold cyan]repo-one[/]",), {}),
        (("Path: /repo/one",), {}),
    ]


def test_repo_info_routes_errors_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(orchestrator=SimpleNamespace(get_repo=Mock(side_effect=RuntimeError("broken"))))

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="broken"):
        repo_module.repo_info(name="repo-one", ctx=cast(Any, ctx))


def test_repo_delete_aborts_when_confirmation_declined(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = SimpleNamespace(delete_repo=Mock())
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: False)
    monkeypatch.setattr(repo_module.console, "print", console_print)

    repo_module.repo_delete(name="repo-one", ctx=cast(Any, ctx))

    orchestrator.delete_repo.assert_not_called()
    console_print.assert_called_once_with("Aborted.")


def test_repo_delete_skips_confirmation_for_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    confirm_mock = Mock(side_effect=AssertionError("confirmation should not run"))
    orchestrator = SimpleNamespace(delete_repo=Mock())
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module, "confirm_action", confirm_mock)
    monkeypatch.setattr(repo_module.console, "print", console_print)

    repo_module.repo_delete(name="repo-one", dry_run=True, ctx=cast(Any, ctx))

    confirm_mock.assert_not_called()
    orchestrator.delete_repo.assert_called_once_with(
        name="repo-one",
        path=None,
        dry_run=True,
        delete_from_s3=False,
        passphrase=None,
    )
    console_print.assert_called_once_with("[bold yellow]Dry run completed - no changes made[/]")


def test_repo_delete_prints_success_message_after_real_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    test_passphrase = "secret"  # noqa: S105
    orchestrator = SimpleNamespace(delete_repo=Mock())
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: True)
    monkeypatch.setattr(repo_module.console, "print", console_print)

    repo_module.repo_delete(name="repo-one", delete_from_s3=True, passphrase=test_passphrase, ctx=cast(Any, ctx))

    orchestrator.delete_repo.assert_called_once_with(
        name="repo-one",
        path=None,
        dry_run=False,
        delete_from_s3=True,
        passphrase=test_passphrase,
    )
    console_print.assert_called_once_with("[bold green]Repository deleted successfully[/]")


def test_repo_delete_routes_errors_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = SimpleNamespace(delete_repo=Mock(side_effect=RuntimeError("cannot delete")))
    ctx = SimpleNamespace(orchestrator=orchestrator)

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: True)
    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="cannot delete"):
        repo_module.repo_delete(name="repo-one", ctx=cast(Any, ctx))
