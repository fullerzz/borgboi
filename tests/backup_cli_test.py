from borgboi.cli.backup import _build_archive_stats_tables
from borgboi.clients.borg import ArchiveInfo


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
