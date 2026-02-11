from datetime import UTC, datetime
from typing import Any

import pytest
from click.testing import CliRunner
from rich.panel import Panel
from rich.table import Table

from borgboi import rich_utils
from borgboi.cli import cli
from borgboi.clients import s3 as s3_client


def test_s3_stats_renders_panel_and_table(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = s3_client.S3BucketStats(
        bucket_name="test-bucket",
        total_size_bytes=10 * 1024**3,
        total_object_count=42,
        storage_breakdown=[
            s3_client.S3StorageClassBreakdown(storage_class="INTELLIGENT_TIERING", tier="FA", size_bytes=6 * 1024**3),
            s3_client.S3StorageClassBreakdown(storage_class="INTELLIGENT_TIERING", tier="IA", size_bytes=4 * 1024**3),
        ],
        metrics_timestamp=datetime(2026, 2, 1, tzinfo=UTC),
    )

    monkeypatch.setattr(s3_client, "get_bucket_stats", lambda cfg=None: stats)

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["s3", "stats"])

    assert result.exit_code == 0
    assert any(isinstance(item, Panel) for item in printed)
    assert any(isinstance(item, Table) for item in printed)


def test_s3_stats_unavailable_in_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called() -> None:
        raise AssertionError("get_bucket_stats should not be called in offline mode")

    monkeypatch.setattr(s3_client, "get_bucket_stats", lambda cfg=None: fail_if_called())

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["--offline", "s3", "stats"])

    assert result.exit_code == 0
    assert any("offline mode" in str(item).lower() for item in printed)


def test_s3_stats_returns_error_when_stats_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_failure() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(s3_client, "get_bucket_stats", lambda cfg=None: raise_failure())

    printed: list[Any] = []

    def fake_print(*args: Any, **kwargs: Any) -> None:
        _ = kwargs
        printed.extend(args)

    monkeypatch.setattr(rich_utils.console, "print", fake_print)

    runner = CliRunner()
    result = runner.invoke(cli, ["s3", "stats"])

    assert result.exit_code == 1
    output_text = " ".join(str(item).lower() for item in printed)
    assert "error" in output_text
    assert "boom" in output_text
