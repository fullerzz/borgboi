import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from borgboi.cli.backup import _build_archive_stats_tables
from borgboi.clients.borg import ArchiveInfo
from borgboi.core.models import BackupOptions

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
    assert summary_labels == [
        "Repository",
        "Archive name",
        "Archive fingerprint",
        "Time (start)",
        "Time (end)",
        "Duration",
        "Number of files",
    ]
    assert summary_values == [
        "/mnt/raid1/borg-backup-repos/samba-ser8",
        "2026-02-22_00:02:27",
        "b7fe3d5228c11fde30c5f36126f2fc3555b95f154f1f1c7e4802dd4e94795e88",
        "Sat, 2026-02-21 17:02:27",
        "Sat, 2026-02-21 17:02:27",
        "0.06 seconds",
        "64",
    ]

    scope_cells = list(size_table.columns[0].cells)
    original_cells = list(size_table.columns[1].cells)
    compressed_cells = list(size_table.columns[2].cells)
    deduplicated_cells = list(size_table.columns[3].cells)
    assert scope_cells == ["This archive", "All archives"]
    assert original_cells == ["5.00 GB", "28.00 GB"]
    assert compressed_cells == ["4.00 GB", "26.00 GB"]
    assert deduplicated_cells == ["0 B", "5.00 GB"]


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
            _ = config
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
            raise AssertionError("resolve_passphrase should not be called when --no-json is used")

    monkeypatch.setattr(cli_main, "Orchestrator", _FakeOrchestrator)
    monkeypatch.setattr("borgboi.cli.backup._render_archive_stats_table", lambda *args: render_calls.append(args))

    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["backup", "run", "--path", str(tmp_path), "--no-json"])

    assert result.exit_code == 0
    assert len(captured_options) == 1

    options = captured_options[0]
    assert isinstance(options, BackupOptions)
    assert options.json_output is False
    assert render_calls == []
