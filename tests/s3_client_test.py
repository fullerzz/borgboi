from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from borgboi.clients import s3_client as s3_client_module
from borgboi.core.errors import StorageError
from borgboi.storage.models import S3RepoStats


class _FakeStream:
    def __init__(self, lines: list[bytes] | None = None, read_data: bytes = b"") -> None:
        self._lines = list(lines or [])
        self._read_data = read_data

    def readable(self) -> bool:
        return True

    def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        return b""

    def read(self) -> bytes:
        return self._read_data

    def close(self) -> None:
        pass


class _FakeProcess:
    def __init__(self, stdout: _FakeStream | None, stderr: _FakeStream | None, returncode: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self._returncode = returncode

    def wait(self) -> int:
        return self._returncode


@pytest.fixture
def client() -> s3_client_module.S3Client:
    return s3_client_module.S3Client(bucket="test-bucket", aws_cli_path="aws")


def test_sync_to_bucket_builds_expected_command(
    monkeypatch: pytest.MonkeyPatch, client: s3_client_module.S3Client
) -> None:
    local_path = Path("repo-dir")
    recorded: list[tuple[list[str], str]] = []

    def fake_run(cmd: list[str], error_msg: str) -> Any:
        recorded.append((cmd, error_msg))
        return iter(["uploaded"])

    monkeypatch.setattr(client, "_run_streaming_command", fake_run)

    output = list(client.sync_to_bucket(local_path, "repo-one"))

    assert output == ["uploaded"]
    assert recorded == [
        (
            ["aws", "s3", "sync", "repo-dir", "s3://test-bucket/repo-one", "--storage-class", "INTELLIGENT_TIERING"],
            "Failed to sync repo-one to S3",
        )
    ]


def test_sync_from_bucket_builds_expected_dry_run_command(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    local_path = Path("restore-dir")
    recorded: list[tuple[list[str], str]] = []

    def fake_run(cmd: list[str], error_msg: str) -> Any:
        recorded.append((cmd, error_msg))
        return iter(["downloaded"])

    monkeypatch.setattr(client, "_run_streaming_command", fake_run)

    output = list(client.sync_from_bucket(local_path, "repo-one", dry_run=True))

    assert output == ["downloaded"]
    assert recorded == [
        (
            ["aws", "s3", "--dryrun", "sync", "s3://test-bucket/repo-one", "restore-dir"],
            "Failed to restore repo-one from S3",
        )
    ]


def test_delete_from_bucket_builds_expected_dry_run_command(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    recorded: list[tuple[list[str], str]] = []

    def fake_run(cmd: list[str], error_msg: str) -> Any:
        recorded.append((cmd, error_msg))
        return iter(["deleted"])

    monkeypatch.setattr(client, "_run_streaming_command", fake_run)

    output = list(client.delete_from_bucket("repo-one", dry_run=True))

    assert output == ["deleted"]
    assert recorded == [
        (
            ["aws", "s3", "rm", "s3://test-bucket/repo-one", "--recursive", "--dryrun"],
            "Failed to delete repo-one from S3",
        )
    ]


def test_run_streaming_command_yields_output_lines(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    process = _FakeProcess(
        stdout=_FakeStream([b"first\n", b"second\n"]),
        stderr=_FakeStream(),
        returncode=0,
    )

    monkeypatch.setattr(s3_client_module.sp, "Popen", lambda *args, **kwargs: process)

    lines = list(client._run_streaming_command(["aws", "s3", "sync"]))

    assert lines == ["first", "second"]


def test_run_streaming_command_raises_when_stdout_missing(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    monkeypatch.setattr(
        s3_client_module.sp,
        "Popen",
        lambda *args, **kwargs: _FakeProcess(stdout=None, stderr=_FakeStream(), returncode=0),
    )

    with pytest.raises(StorageError, match="stdout is None"):
        list(client._run_streaming_command(["aws", "s3", "sync"]))


def test_run_streaming_command_raises_storage_error_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    process = _FakeProcess(
        stdout=_FakeStream(),
        stderr=_FakeStream(read_data=b"permission denied"),
        returncode=2,
    )

    monkeypatch.setattr(s3_client_module.sp, "Popen", lambda *args, **kwargs: process)

    with pytest.raises(StorageError, match="permission denied") as exc_info:
        list(client._run_streaming_command(["aws", "s3", "sync"], error_msg="sync failed"))

    assert exc_info.value.operation == "s3_sync"


def test_get_stats_parses_output_and_uses_latest_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    payload = json.dumps(
        [
            {"Size": 10, "LastModified": "2024-01-01T00:00:00Z"},
            {"Size": 20, "LastModified": "2024-02-02T12:00:00Z"},
        ]
    )
    result = SimpleNamespace(stdout=payload)

    monkeypatch.setattr(s3_client_module.sp, "run", lambda *args, **kwargs: result)

    stats = client.get_stats("repo-one")

    assert stats.total_size_bytes == 30
    assert stats.object_count == 2
    assert stats.last_modified == datetime(2024, 2, 2, 12, 0, tzinfo=UTC)
    assert isinstance(stats.cached_at, datetime)


def test_get_stats_returns_empty_stats_for_blank_output(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    monkeypatch.setattr(s3_client_module.sp, "run", lambda *args, **kwargs: SimpleNamespace(stdout="  "))

    stats = client.get_stats("repo-one")

    assert stats.total_size_bytes == 0
    assert stats.object_count == 0
    assert stats.last_modified is None


def test_get_stats_wraps_json_errors(monkeypatch: pytest.MonkeyPatch, client: s3_client_module.S3Client) -> None:
    monkeypatch.setattr(s3_client_module.sp, "run", lambda *args, **kwargs: SimpleNamespace(stdout="not-json"))

    with pytest.raises(StorageError, match="Failed to parse S3 stats response"):
        client.get_stats("repo-one")


def test_exists_checks_summary_output(monkeypatch: pytest.MonkeyPatch, client: s3_client_module.S3Client) -> None:
    monkeypatch.setattr(
        s3_client_module.sp,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="Total Objects: 3"),
    )

    assert client.exists("repo-one") is True


def test_exists_returns_false_on_errors(monkeypatch: pytest.MonkeyPatch, client: s3_client_module.S3Client) -> None:
    monkeypatch.setattr(
        s3_client_module.sp,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("aws failed")),
    )

    assert client.exists("repo-one") is False


def test_list_repos_parses_prefixes_and_ignores_other_lines(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    output = "PRE repo-one/\nPRE repo-two/\n2024-01-01 00:00:00 12 some-file.txt\n"
    monkeypatch.setattr(s3_client_module.sp, "run", lambda *args, **kwargs: SimpleNamespace(stdout=output))

    repos = client.list_repos()

    assert repos == ["repo-one", "repo-two"]


def test_list_repos_returns_empty_on_called_process_error(
    monkeypatch: pytest.MonkeyPatch,
    client: s3_client_module.S3Client,
) -> None:
    error = s3_client_module.sp.CalledProcessError(1, ["aws"], stderr="boom")
    monkeypatch.setattr(s3_client_module.sp, "run", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    assert client.list_repos() == []


def test_mock_s3_client_handles_dry_run_delete_and_missing_restore() -> None:
    client = s3_client_module.MockS3Client()
    client.add_repo("repo-one", S3RepoStats(total_size_bytes=2048, object_count=2))

    restore_output = list(client.sync_from_bucket("restore-dir", "repo-one", dry_run=True))
    delete_output = list(client.delete_from_bucket("repo-one", dry_run=True))

    assert restore_output == ["(dryrun) download: s3://mock-bucket/repo-one/ to restore-dir"]
    assert delete_output == ["(dryrun) delete: s3://mock-bucket/repo-one/"]
    assert client.exists("repo-one") is True

    with pytest.raises(StorageError, match="not found in S3"):
        list(client.sync_from_bucket("restore-dir", "missing-repo"))
