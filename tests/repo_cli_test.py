import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.cli import repo as repo_module


def test_repo_import_calls_orchestrator_and_prints_success(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SimpleNamespace(path="/repo/imported", name="repo-one")
    orchestrator = SimpleNamespace(import_repo=Mock(return_value=repo))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_import(path="/repo/imported", backup_target="/backup/source", name="repo-one", ctx=cast(Any, ctx))

    orchestrator.import_repo.assert_called_once_with(
        path="/repo/imported",
        backup_target="/backup/source",
        name="repo-one",
        passphrase=None,
    )
    console_print.assert_called_once_with("Imported existing Borg repo at [bold cyan]/repo/imported[/]")


def test_repo_import_routes_errors_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(orchestrator=SimpleNamespace(import_repo=Mock(side_effect=RuntimeError("cannot import"))))

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="cannot import"):
        repo_module.repo_import(
            path="/repo/imported", backup_target="/backup/source", name="repo-one", ctx=cast(Any, ctx)
        )


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

    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

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

    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

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


def test_repo_rsync_runs_rsync_with_mirror_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = SimpleNamespace(name="repo-one", path="/repo/one")
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    proc = SimpleNamespace(wait=Mock(return_value=0))
    subprocess_popen = Mock(return_value=proc)
    console_print = Mock()
    destination = str(tmp_path)

    monkeypatch.setattr(repo_module.shutil, "which", lambda command: "/usr/bin/rsync" if command == "rsync" else None)
    monkeypatch.setattr(repo_module.subprocess, "Popen", subprocess_popen)
    monkeypatch.setattr(repo_module, "_build_rsync_flags", lambda rsync: repo_module._RSYNC_BASE_FLAGS)
    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: True)
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_rsync(name="repo-one", destination=destination, ctx=cast(Any, ctx))

    orchestrator.get_repo.assert_called_once_with(name="repo-one", path=None)
    subprocess_popen.assert_called_once_with(
        [
            "/usr/bin/rsync",
            "--archive",
            "--hard-links",
            "--delete",
            "--partial",
            "/repo/one/",
            destination,
        ]
    )
    assert console_print.call_args_list == [
        (("Source: [bold cyan]/repo/one/[/]",), {}),
        ((f"Destination: [bold cyan]{destination}[/]",), {}),
        (
            ("[bold yellow]Warning:[/] rsync will delete destination files that are not in the source repository.",),
            {},
        ),
        ((f"[bold green]Repository synced to {destination}[/]",), {}),
    ]


def test_repo_rsync_adds_dry_run_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = SimpleNamespace(name="repo-one", path="/repo/one/")
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    proc = SimpleNamespace(wait=Mock(return_value=0))
    subprocess_popen = Mock(return_value=proc)
    console_print = Mock()
    confirm_mock = Mock(side_effect=AssertionError("confirmation should not run"))
    destination = str(tmp_path)

    monkeypatch.setattr(repo_module.shutil, "which", lambda command: "/usr/bin/rsync" if command == "rsync" else None)
    monkeypatch.setattr(repo_module.subprocess, "Popen", subprocess_popen)
    monkeypatch.setattr(repo_module, "_build_rsync_flags", lambda rsync: repo_module._RSYNC_BASE_FLAGS)
    monkeypatch.setattr(repo_module, "confirm_action", confirm_mock)
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_rsync(path="/repo/one/", destination=destination, dry_run=True, ctx=cast(Any, ctx))

    command = subprocess_popen.call_args.args[0]
    confirm_mock.assert_not_called()
    assert "--dry-run" in command
    assert command[-2:] == ["/repo/one/", destination]
    assert console_print.call_args_list == [
        (("Source: [bold cyan]/repo/one/[/]",), {}),
        ((f"Destination: [bold cyan]{destination}[/]",), {}),
        (
            ("[bold yellow]Warning:[/] rsync will delete destination files that are not in the source repository.",),
            {},
        ),
        (("[bold yellow]Dry run completed - no changes made[/]",), {}),
    ]


def test_repo_rsync_aborts_when_confirmation_declined(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = SimpleNamespace(name="repo-one", path="/repo/one")
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    subprocess_popen = Mock()
    console_print = Mock()

    monkeypatch.setattr(repo_module.shutil, "which", lambda command: "/usr/bin/rsync" if command == "rsync" else None)
    monkeypatch.setattr(repo_module.subprocess, "Popen", subprocess_popen)
    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: False)
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_rsync(name="repo-one", destination=str(tmp_path), ctx=cast(Any, ctx))

    subprocess_popen.assert_not_called()
    assert console_print.call_args_list[-1] == (("Aborted.",), {})


def test_build_rsync_flags_skips_unsupported_optional_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[1] == "--help":
            stdout = "--human-readable\n--progress\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        if command[1] == "--info=help":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr(repo_module.subprocess, "run", run)

    assert repo_module._build_rsync_flags("/usr/bin/rsync") == [
        "--archive",
        "--hard-links",
        "--delete",
        "--partial",
        "--human-readable",
        "--progress",
    ]
    assert [command[1] for command in calls] == ["--help", "--info=help"]


def test_build_rsync_flags_prefers_progress2_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--help":
            stdout = "--human-readable\n--numeric-ids\n--delete-delay\n--acls\n--xattrs\n--progress\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        if command[1] == "--info=help":
            return subprocess.CompletedProcess(command, 0, stdout="progress2\n", stderr="")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr(repo_module.subprocess, "run", run)

    assert repo_module._build_rsync_flags("/usr/bin/rsync") == [
        "--archive",
        "--hard-links",
        "--delete",
        "--partial",
        "--human-readable",
        "--numeric-ids",
        "--delete-delay",
        "--acls",
        "--xattrs",
        "--info=progress2",
    ]


def test_run_rsync_command_terminates_process_on_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = SimpleNamespace(
        poll=Mock(return_value=None),
        terminate=Mock(),
        kill=Mock(),
    )
    proc.wait = Mock(side_effect=[KeyboardInterrupt, 0])

    monkeypatch.setattr(repo_module.subprocess, "Popen", Mock(return_value=proc))

    with pytest.raises(KeyboardInterrupt):
        repo_module._run_rsync_command(["rsync", "--archive", "/repo/", "/mnt/repo"])

    proc.terminate.assert_called_once_with()
    proc.kill.assert_not_called()
    assert proc.wait.call_args_list[-1].kwargs == {"timeout": 5}


def test_repo_rsync_routes_missing_rsync_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(orchestrator=SimpleNamespace(get_repo=Mock()))

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module.shutil, "which", lambda command: None)
    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="rsync was not found"):
        repo_module.repo_rsync(name="repo-one", destination="/mnt/backup/repo-one", ctx=cast(Any, ctx))


def test_repo_rsync_routes_rsync_failure_to_print_error_and_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = SimpleNamespace(name="repo-one", path="/repo/one")
    ctx = SimpleNamespace(orchestrator=SimpleNamespace(get_repo=Mock(return_value=repo)))

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module.shutil, "which", lambda command: "/usr/bin/rsync" if command == "rsync" else None)
    monkeypatch.setattr(repo_module, "_build_rsync_flags", lambda rsync: repo_module._RSYNC_BASE_FLAGS)
    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: True)
    monkeypatch.setattr(repo_module.subprocess, "Popen", Mock(return_value=SimpleNamespace(wait=Mock(return_value=23))))
    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="rsync failed with exit code 23"):
        repo_module.repo_rsync(name="repo-one", destination=str(tmp_path), ctx=cast(Any, ctx))


def test_repo_delete_aborts_when_confirmation_declined(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = SimpleNamespace(delete_repo=Mock())
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module, "confirm_action", lambda prompt: False)
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_delete(name="repo-one", ctx=cast(Any, ctx))

    orchestrator.delete_repo.assert_not_called()
    console_print.assert_called_once_with("Aborted.")


def test_repo_delete_skips_confirmation_for_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    confirm_mock = Mock(side_effect=AssertionError("confirmation should not run"))
    orchestrator = SimpleNamespace(delete_repo=Mock())
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr(repo_module, "confirm_action", confirm_mock)
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

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
    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

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


def test_repo_set_quota_calls_orchestrator_and_prints_success(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = SimpleNamespace(update_repo_storage_quota=Mock(return_value="200G"))
    ctx = SimpleNamespace(orchestrator=orchestrator)
    console_print = Mock()

    monkeypatch.setattr("borgboi.cli.repo.console.print", console_print)

    repo_module.repo_set_quota(name="repo-one", quota="200G", ctx=cast(Any, ctx))

    orchestrator.update_repo_storage_quota.assert_called_once_with(
        "200G",
        name="repo-one",
        path=None,
        passphrase=None,
    )
    console_print.assert_called_once_with("[bold green]Repository storage quota updated to 200G[/]")


def test_repo_set_quota_routes_errors_to_print_error_and_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(
        orchestrator=SimpleNamespace(update_repo_storage_quota=Mock(side_effect=RuntimeError("bad quota")))
    )

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(repo_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="bad quota"):
        repo_module.repo_set_quota(name="repo-one", quota="200G", ctx=cast(Any, ctx))
