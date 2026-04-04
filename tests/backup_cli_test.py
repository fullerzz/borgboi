import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from inline_snapshot import snapshot

from borgboi.cli.backup import (
    _build_archive_stats_tables,
    _format_diff_change,
    _render_diff_result,
    _summarize_diff_changes,
)
from borgboi.clients.borg import ArchiveInfo, DiffResult
from borgboi.core.models import BackupOptions, DiffOptions
from tests.cli_helpers import invoke_cli

cli_main = importlib.import_module("borgboi.cli.main")


def test_build_archive_stats_tables_includes_archive_and_cache_metrics() -> None:
    archive_info = ArchiveInfo.model_validate(
        {
            "archives": [
                {
                    "name": "2026-02-22_00:02:27",
                    "id": "b7fe3d5228c11fde30c5f36126f2fc3555b95f154f1f1c7e4802dd4e94795e88",
                    "start": "2026-02-21T17:02:27.123456+00:00",
                    "end": "2026-02-21T17:02:27.183456+00:00",
                    "duration": 0.06,
                    "stats": {
                        "original_size": 5 * 1024**3,
                        "compressed_size": 4 * 1024**3,
                        "deduplicated_size": 0,
                        "nfiles": 64,
                    },
                },
            ],
            "cache": {
                "path": "/mnt/raid1/borg-backup-repos/samba-ser8",
                "stats": {
                    "total_chunks": 10931,
                    "total_csize": 26 * 1024**3,
                    "total_size": 28 * 1024**3,
                    "total_unique_chunks": 1914,
                    "unique_csize": 5 * 1024**3,
                    "unique_size": 5 * 1024**3,
                },
            },
            "encryption": {"mode": "repokey"},
            "repository": {
                "id": "repo-id",
                "last_modified": "2026-02-21T17:02:27.190000+00:00",
                "location": "/mnt/raid1/borg-backup-repos/samba-ser8",
            },
        }
    )

    summary_table, size_table = _build_archive_stats_tables(
        "/mnt/raid1/borg-backup-repos/samba-ser8",
        archive_info,
    )

    summary_labels = list(summary_table.columns[0].cells)
    summary_values = list(summary_table.columns[1].cells)
    assert summary_labels == snapshot(
        [
            "Repository",
            "Archive name",
            "Archive fingerprint",
            "Time (start)",
            "Time (end)",
            "Duration",
            "Number of files",
        ]
    )
    assert summary_values == snapshot(
        [
            "/mnt/raid1/borg-backup-repos/samba-ser8",
            "2026-02-22_00:02:27",
            "b7fe3d5228c11fde30c5f36126f2fc3555b95f154f1f1c7e4802dd4e94795e88",
            "Sat, 2026-02-21 17:02:27",
            "Sat, 2026-02-21 17:02:27",
            "0.06 seconds",
            "64",
        ]
    )

    scope_cells = list(size_table.columns[0].cells)
    original_cells = list(size_table.columns[1].cells)
    compressed_cells = list(size_table.columns[2].cells)
    deduplicated_cells = list(size_table.columns[3].cells)
    assert scope_cells == snapshot(["This archive", "All archives"])
    assert original_cells == snapshot(["5.00 GB", "28.00 GB"])
    assert compressed_cells == snapshot(["4.00 GB", "26.00 GB"])
    assert deduplicated_cells == snapshot(["0 B", "5.00 GB"])


def test_backup_options_default_includes_log_json() -> None:
    args = BackupOptions().to_borg_args()
    assert "--log-json" in args


def test_backup_options_no_json_excludes_log_json() -> None:
    args = BackupOptions(json_output=False).to_borg_args()
    assert "--log-json" not in args
    assert "--stats" in args
    assert "--progress" in args
    assert "--list" in args


def test_backup_run_no_json_passes_options_and_skips_stats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_options: list[BackupOptions | None] = []
    render_calls: list[tuple[object, ...]] = []

    class _FakeBorgClient:
        def archive_info(self, repo_path: str, archive_name: str, passphrase: str | None = None) -> None:
            _ = (repo_path, archive_name, passphrase)
            raise AssertionError("archive_info should not be called when --no-json is used")

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config
            self.borg = _FakeBorgClient()

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = name
            return SimpleNamespace(path=path)

        def backup(
            self,
            repo: object,
            passphrase: str | None = None,
            options: BackupOptions | None = None,
        ) -> str:
            _ = (repo, passphrase)
            captured_options.append(options)
            return "archive-2026-02-23"

        def resolve_passphrase(self, repo: object, passphrase: str | None = None) -> str:
            _ = (repo, passphrase)
            return "fake-passphrase"

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setattr("borgboi.cli.backup._render_archive_stats_table", lambda *args: render_calls.append(args))

    exit_code = invoke_cli(cli_main.cli, ["backup", "run", "--path", str(tmp_path), "--no-json"])

    assert exit_code == 0
    assert len(captured_options) == 1

    options = captured_options[0]
    assert isinstance(options, BackupOptions)
    assert options.json_output is False
    assert render_calls == []


def test_backup_run_default_fetches_stats_and_renders_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_options: list[BackupOptions | None] = []
    archive_info_calls: list[tuple[str, str, str | None]] = []
    render_calls: list[tuple[object, ...]] = []
    archive_info_result = object()

    class _FakeBorgClient:
        def archive_info(self, repo_path: str, archive_name: str, passphrase: str | None = None) -> object:
            archive_info_calls.append((repo_path, archive_name, passphrase))
            return archive_info_result

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config
            self.borg = _FakeBorgClient()

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = name
            return SimpleNamespace(path=path)

        def backup(
            self,
            repo: object,
            passphrase: str | None = None,
            options: BackupOptions | None = None,
        ) -> str:
            _ = (repo, passphrase)
            captured_options.append(options)
            return "archive-2026-02-23"

        def resolve_passphrase(self, repo: object, passphrase: str | None = None) -> str:
            _ = (repo, passphrase)
            return "resolved-passphrase"

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setattr("borgboi.cli.backup._render_archive_stats_table", lambda *args: render_calls.append(args))

    exit_code = invoke_cli(cli_main.cli, ["backup", "run", "--path", str(tmp_path)])

    assert exit_code == 0
    assert captured_options == [None]
    assert archive_info_calls == [(str(tmp_path), "archive-2026-02-23", "resolved-passphrase")]
    assert render_calls == [(str(tmp_path), archive_info_result)]


def test_backup_daily_accepts_repo_name(monkeypatch: pytest.MonkeyPatch) -> None:
    get_repo_calls: list[tuple[str | None, str | None]] = []
    daily_backup_calls: list[tuple[object, str | None, bool]] = []
    fake_repo = SimpleNamespace(name="daily-repo", path="/fake/repo")

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            get_repo_calls.append((name, path))
            return fake_repo

        def daily_backup(self, repo: object, passphrase: str | None = None, sync_to_s3: bool = True) -> None:
            daily_backup_calls.append((repo, passphrase, sync_to_s3))

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(cli_main.cli, ["backup", "daily", "--name", "daily-repo"])

    assert exit_code == 0
    assert get_repo_calls == [("daily-repo", None)]
    assert daily_backup_calls == [(fake_repo, None, True)]


def test_backup_daily_name_respects_no_s3_sync_and_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    daily_backup_calls: list[tuple[object, str | None, bool]] = []
    fake_repo = SimpleNamespace(name="daily-repo", path="/fake/repo")

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = (name, path)
            return fake_repo

        def daily_backup(self, repo: object, passphrase: str | None = None, sync_to_s3: bool = True) -> None:
            daily_backup_calls.append((repo, passphrase, sync_to_s3))

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(
        cli_main.cli,
        ["backup", "daily", "--name", "daily-repo", "--passphrase", "cli-passphrase", "--no-s3-sync"],
    )

    assert exit_code == 0
    assert daily_backup_calls == [(fake_repo, "cli-passphrase", False)]


def test_backup_daily_rejects_neither_name_nor_path(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["backup", "daily"])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "Provide either --name or --path" in captured.out


def test_backup_daily_rejects_both_name_and_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(
        cli_main.cli,
        ["backup", "daily", "--name", "my-repo", "--path", str(tmp_path)],
    )
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "mutually exclusive" in captured.out


def test_summarize_diff_changes_counts_entries_by_type() -> None:
    result = DiffResult.model_validate(
        {
            "archive1": "archive-old",
            "archive2": "archive-new",
            "entries": [
                {"path": "added.txt", "changes": [{"type": "added", "size": 42}]},
                {"path": "removed.txt", "changes": [{"type": "removed", "size": 11}]},
                {
                    "path": "modified.txt",
                    "changes": [{"type": "modified", "added": 12, "removed": 4}],
                },
                {
                    "path": "mode.txt",
                    "changes": [{"type": "mode", "old_mode": "-rw-r--r--", "new_mode": "-rwxr-xr-x"}],
                },
            ],
        }
    )

    assert _summarize_diff_changes(result) == {
        "added": 1,
        "removed": 1,
        "modified": 1,
        "mode": 1,
        "bytes_added": 54,
        "bytes_removed": 15,
    }


def test_format_diff_change_includes_metadata_values() -> None:
    result = DiffResult.model_validate(
        {
            "archive1": "archive-old",
            "archive2": "archive-new",
            "entries": [
                {
                    "path": "docs/file.txt",
                    "changes": [
                        {
                            "type": "mtime",
                            "old": "2026-04-03T10:00:00",
                            "new": "2026-04-03T11:00:00",
                        }
                    ],
                }
            ],
        }
    )

    assert _format_diff_change(result.entries[0].changes[0]) == "mtime 2026-04-03T10:00:00 -> 2026-04-03T11:00:00"


def test_render_diff_result_json_outputs_raw_json(capsys: pytest.CaptureFixture[str]) -> None:
    result = DiffResult.model_validate(
        {
            "archive1": "archive-old",
            "archive2": "archive-new",
            "entries": [
                {
                    "path": "/home/user/[vendor]/" + ("a" * 120),
                    "changes": [{"type": "modified", "added": 8, "removed": 2}],
                }
            ],
        }
    )

    _render_diff_result(result, json_output=True)
    captured = capsys.readouterr()

    assert captured.out == json.dumps(result.model_dump(mode="json"), indent=2) + "\n"


def test_backup_diff_defaults_to_two_most_recent_archives(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    get_two_most_recent_calls: list[tuple[object, str | None]] = []
    diff_calls: list[tuple[object, str, str, DiffOptions, str | None]] = []
    fake_repo = SimpleNamespace(name="demo-repo", path="/fake/repo")
    fake_result = DiffResult.model_validate({"archive1": "archive-1", "archive2": "archive-2", "entries": []})

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = (name, path)
            return fake_repo

        def get_two_most_recent_archives(self, repo: object, passphrase: str | None = None) -> tuple[object, object]:
            get_two_most_recent_calls.append((repo, passphrase))
            return (SimpleNamespace(name="archive-1"), SimpleNamespace(name="archive-2"))

        def diff_archives(
            self,
            repo: object,
            archive1: str,
            archive2: str,
            options: DiffOptions | None = None,
            passphrase: str | None = None,
            *,
            validated: bool = False,
        ) -> DiffResult:
            assert options is not None
            diff_calls.append((repo, archive1, archive2, options, passphrase))
            return fake_result

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(cli_main.cli, ["backup", "diff", "--name", "demo-repo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert get_two_most_recent_calls == [(fake_repo, None)]
    assert len(diff_calls) == 1
    assert diff_calls[0][1:3] == ("archive-1", "archive-2")
    assert diff_calls[0][3].content_only is False
    assert diff_calls[0][3].paths == []
    assert "No changed paths found." in captured.out


def test_backup_diff_passes_explicit_archives_and_filters(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    diff_calls: list[tuple[object, str, str, DiffOptions, str | None]] = []
    fake_repo = SimpleNamespace(name="demo-repo", path="/fake/repo")
    fake_result = DiffResult.model_validate(
        {
            "archive1": "archive-a",
            "archive2": "archive-b",
            "entries": [{"path": "docs/file.txt", "changes": [{"type": "modified", "added": 8, "removed": 2}]}],
        }
    )

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = (name, path)
            return fake_repo

        def diff_archives(
            self,
            repo: object,
            archive1: str,
            archive2: str,
            options: DiffOptions | None = None,
            passphrase: str | None = None,
            *,
            validated: bool = False,
        ) -> DiffResult:
            assert options is not None
            diff_calls.append((repo, archive1, archive2, options, passphrase))
            return fake_result

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(
        cli_main.cli,
        [
            "backup",
            "diff",
            "--name",
            "demo-repo",
            "--archive1",
            "archive-a",
            "--archive2",
            "archive-b",
            "--filter-path",
            "docs",
            "--filter-path",
            "src/app.py",
            "--content-only",
            "--passphrase",
            "secret",
        ],
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(diff_calls) == 1
    assert diff_calls[0][1:3] == ("archive-a", "archive-b")
    assert diff_calls[0][3].content_only is True
    assert diff_calls[0][3].paths == ["docs", "src/app.py"]
    assert diff_calls[0][4] == "secret"
    assert "docs/file.txt" in captured.out


def test_backup_diff_requires_both_explicit_archives(capsys: pytest.CaptureFixture[str]) -> None:
    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def get_repo(self, name: str | None = None, path: str | None = None) -> object:
            _ = (name, path)
            return SimpleNamespace(name="demo-repo", path="/fake/repo")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(cli_main.cli, ["backup", "diff", "--name", "demo-repo", "--archive1", "archive-a"])
    try:
        captured = capsys.readouterr()

        assert exit_code != 0
        assert "Provide both --archive1 and --archive2" in captured.out
    finally:
        monkeypatch.undo()


def test_backup_restore_aborts_cleanly_when_confirmation_is_declined(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("borgboi.cli.backup.confirm_action", lambda prompt: False)

    exit_code = invoke_cli(
        cli_main.cli,
        ["backup", "restore", "--path", str(tmp_path), "--archive", "archive-2026-02-23"],
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Aborted." in captured.out
