import gzip
import io
import json
import subprocess as sp
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest
from botocore.exceptions import ClientError

from borgboi.clients import s3
from borgboi.config import AWSConfig, Config
from borgboi.core.errors import StorageError


def _make_config(bucket: str) -> Config:
    return Config(aws=AWSConfig(s3_bucket=bucket))


def test_sync_with_s3_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful S3 sync operation."""
    cfg = _make_config("test-bucket")

    # Mock subprocess.Popen
    class MockProc:
        def __init__(self) -> None:
            self.stdout: MockStdout = MockStdout()

        def wait(self) -> Literal[0]:
            return 0

    class MockStdout:
        def __init__(self) -> None:
            self.call_count: int = 0
            self.lines: list[bytes] = [
                b"upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt\n",
                b"upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt\n",
                b"",
            ]

        def readable(self) -> bool:
            self.call_count += 1
            return self.call_count <= 2

        def readline(self) -> bytes:
            if self.call_count <= len(self.lines):
                return self.lines[self.call_count - 1]
            return b""

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    output_lines = list(s3.sync_with_s3("/path/to/repo", "test-repo", cfg=cfg))

    assert len(output_lines) == 2
    assert "upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt" in output_lines[0]
    assert "upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt" in output_lines[1]


def test_sync_with_s3_missing_bucket_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync uses default bucket from config when env var is not set."""
    # Config now provides default value, so no KeyError should be raised
    # The test verifies that the function works with config defaults
    cfg = Config()

    class MockProc:
        def __init__(self) -> None:
            self.stdout: MockStdout = MockStdout()

        def wait(self) -> Literal[0]:
            return 0

    class MockStdout:
        def readable(self) -> Literal[False]:
            return False

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    # This should not raise an error - config provides a default bucket
    output = list(s3.sync_with_s3("/path/to/repo", "test-repo", cfg=cfg))
    assert output is not None  # Just verify it returns something


def test_sync_with_s3_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync handles command failure."""
    cfg = _make_config("test-bucket")

    class MockProc:
        def __init__(self) -> None:
            self.stdout: MockStdout = MockStdout()
            self.returncode: int = 1  # Non-zero exit code

        def wait(self) -> Literal[1]:
            return 1  # Non-zero exit code

    class MockStdout:
        def readable(self) -> Literal[False]:
            return False

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    with pytest.raises(sp.CalledProcessError):
        _ = list(s3.sync_with_s3("/path/to/repo", "test-repo", cfg=cfg))


def test_sync_with_s3_stdout_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync handles None stdout."""
    cfg = _make_config("test-bucket")

    class MockProc:
        def __init__(self) -> None:
            self.stdout: None = None

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    with pytest.raises(ValueError, match="stdout is None"):
        _ = list(s3.sync_with_s3("/path/to/repo", "test-repo", cfg=cfg))


def test_sync_with_s3_runs_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that S3 sync runs cleanly with mocked process."""
    cfg = _make_config("my-backup-bucket")

    class MockProc:
        def __init__(self) -> None:
            self.stdout: MockStdout = MockStdout()

        def wait(self) -> Literal[0]:
            return 0

    class MockStdout:
        def readable(self) -> Literal[False]:
            return False

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    _ = list(s3.sync_with_s3("/home/user/repos/my-repo", "my-repo", cfg=cfg))


class _MockCloudWatchClient:
    def __init__(self, metrics: dict[tuple[str, str], list[dict[str, object]]]) -> None:
        self._metrics = metrics

    def get_metric_statistics(self, **kwargs: object) -> dict[str, object]:
        metric_name = kwargs.get("MetricName")
        dimensions = kwargs.get("Dimensions")
        if not isinstance(metric_name, str) or not isinstance(dimensions, list):
            return {"Datapoints": []}

        storage_type = ""
        for dim in dimensions:
            if isinstance(dim, dict):
                typed_dim = cast(dict[str, object], dim)
            else:
                continue

            if typed_dim.get("Name") == "StorageType":
                value = typed_dim.get("Value")
                if isinstance(value, str):
                    storage_type = value
                break

        datapoints = self._metrics.get((metric_name, storage_type), [])
        return {"Datapoints": datapoints}


class _MockStreamingBody(io.BytesIO):
    def __init__(self, payload: bytes, *, allow_unbounded_read: bool = True) -> None:
        super().__init__(payload)
        self._allow_unbounded_read = allow_unbounded_read

    def read(self, size: int | None = -1, /) -> bytes:
        if size in (-1, None) and not self._allow_unbounded_read:
            raise AssertionError("Inventory payload must be consumed as a stream.")
        return super().read(-1 if size is None else size)


class _MockS3InventoryClient:
    def __init__(
        self,
        *,
        inventory_configurations: list[dict[str, object]] | None = None,
        objects_by_prefix: dict[str, list[dict[str, object]]] | None = None,
        object_payloads: dict[str, bytes] | None = None,
        object_keys_requiring_streaming: set[str] | None = None,
        object_errors: dict[str, Exception] | None = None,
    ) -> None:
        self._inventory_configurations = inventory_configurations or []
        self._objects_by_prefix = objects_by_prefix or {}
        self._object_payloads = object_payloads or {}
        self._object_keys_requiring_streaming = object_keys_requiring_streaming or set()
        self._object_errors = object_errors or {}

    def list_bucket_inventory_configurations(self, **kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "InventoryConfigurationList": self._inventory_configurations,
            "IsTruncated": False,
        }

    def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
        prefix = kwargs.get("Prefix", "")
        if not isinstance(prefix, str):
            prefix = ""
        return {
            "Contents": self._objects_by_prefix.get(prefix, []),
            "IsTruncated": False,
        }

    def get_object(self, **kwargs: object) -> dict[str, object]:
        key = kwargs.get("Key")
        if not isinstance(key, str):
            return {"Body": _MockStreamingBody(b"")}

        object_error = self._object_errors.get(key)
        if object_error is not None:
            raise object_error

        payload = self._object_payloads.get(key)
        if payload is None:
            raise AssertionError(f"Unexpected key requested from mock S3 client: {key}")

        return {
            "Body": _MockStreamingBody(
                payload,
                allow_unbounded_read=key not in self._object_keys_requiring_streaming,
            )
        }


def test_get_bucket_stats_includes_intelligent_tiering_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("BucketSizeBytes", "IntelligentTieringFAStorage"): [{"Timestamp": timestamp, "Average": 6 * 1024**3}],
        ("BucketSizeBytes", "IntelligentTieringIAStorage"): [{"Timestamp": timestamp, "Average": 4 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 12345.0}],
    }
    mock_client = _MockCloudWatchClient(metrics)

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_client)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: _MockS3InventoryClient())

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.bucket_name == cfg.aws.s3_bucket
    assert stats.total_object_count == 12345
    assert stats.total_size_bytes == 20 * 1024**3
    assert stats.metrics_timestamp == timestamp

    composed = {(item.storage_class, item.tier): item.size_bytes for item in stats.storage_breakdown}
    assert composed[("STANDARD", "-")] == 10 * 1024**3
    assert composed[("INTELLIGENT_TIERING", "FA")] == 6 * 1024**3
    assert composed[("INTELLIGENT_TIERING", "IA")] == 4 * 1024**3
    assert stats.intelligent_tiering_forecast is not None
    assert not stats.intelligent_tiering_forecast.available


def test_get_bucket_stats_uses_latest_cloudwatch_datapoint(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")
    older = datetime(2026, 1, 30, tzinfo=UTC)
    latest = datetime(2026, 1, 31, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        (
            "BucketSizeBytes",
            "StandardStorage",
        ): [
            {"Timestamp": older, "Average": 1 * 1024**3},
            {"Timestamp": latest, "Average": 2 * 1024**3},
        ],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": latest, "Average": 2.0}],
    }
    mock_client = _MockCloudWatchClient(metrics)

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_client)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: _MockS3InventoryClient())

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.total_size_bytes == 2 * 1024**3
    assert stats.total_object_count == 2
    assert stats.metrics_timestamp == latest


def test_get_bucket_stats_includes_inventory_based_upcoming_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")
    bucket_name = cfg.aws.s3_bucket
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 2.0}],
    }
    mock_cloudwatch = _MockCloudWatchClient(metrics)

    now = datetime.now(UTC)
    in_window_last_access = (now - timedelta(days=24)).isoformat().replace("+00:00", "Z")
    outside_window_last_access = (now - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    in_window_last_modified = (now - timedelta(days=24)).isoformat().replace("+00:00", "Z")
    outside_window_last_modified = (now - timedelta(days=10)).isoformat().replace("+00:00", "Z")

    manifest_key = f"inventory/{bucket_name}/entire-bucket/2026-02-01T00-00Z/manifest.json"
    data_key = f"inventory/{bucket_name}/entire-bucket/data/part-00000.csv.gz"

    manifest_payload = {
        "fileFormat": "CSV",
        "fileSchema": "Bucket,Key,Size,LastModifiedDate,LastAccessDate,StorageClass,IntelligentTieringAccessTier",
        "creationTimestamp": now.isoformat().replace("+00:00", "Z"),
        "files": [{"key": data_key}],
    }

    csv_rows = "\n".join(
        [
            f"{bucket_name},repo/a,1073741824,{outside_window_last_modified},{in_window_last_access},INTELLIGENT_TIERING,FREQUENT",
            f"{bucket_name},repo/b,2147483648,{in_window_last_modified},{outside_window_last_access},INTELLIGENT_TIERING,FREQUENT",
        ]
    )

    mock_s3 = _MockS3InventoryClient(
        inventory_configurations=[
            {
                "Id": "entire-bucket",
                "IsEnabled": True,
                "OptionalFields": [
                    "Size",
                    "LastModifiedDate",
                    "StorageClass",
                    "IntelligentTieringAccessTier",
                ],
                "Destination": {
                    "S3BucketDestination": {
                        "Bucket": "arn:aws:s3:::test-bucket-logs",
                        "Prefix": "inventory",
                    }
                },
            }
        ],
        objects_by_prefix={
            f"inventory/{bucket_name}/entire-bucket/": [
                {
                    "Key": manifest_key,
                    "LastModified": now,
                }
            ],
        },
        object_payloads={
            manifest_key: json.dumps(manifest_payload).encode("utf-8"),
            data_key: gzip.compress(csv_rows.encode("utf-8")),
        },
    )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_cloudwatch)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: mock_s3)

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.intelligent_tiering_forecast is not None
    assert stats.intelligent_tiering_forecast.available
    assert stats.intelligent_tiering_forecast.inventory_configuration_id == "entire-bucket"
    assert stats.intelligent_tiering_forecast.objects_transitioning_next_week == 1
    assert stats.intelligent_tiering_forecast.size_bytes_transitioning_next_week == 1024**3


def test_get_bucket_stats_inventory_forecast_falls_back_to_last_modified_when_last_access_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_config("test-bucket")
    bucket_name = cfg.aws.s3_bucket
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 1.0}],
    }
    mock_cloudwatch = _MockCloudWatchClient(metrics)

    now = datetime.now(UTC)
    in_window_last_modified = (now - timedelta(days=24)).isoformat().replace("+00:00", "Z")

    manifest_key = f"inventory/{bucket_name}/entire-bucket/2026-02-01T00-00Z/manifest.json"
    data_key = f"inventory/{bucket_name}/entire-bucket/data/part-00000.csv.gz"

    manifest_payload = {
        "fileFormat": "CSV",
        "fileSchema": "Bucket,Key,Size,LastModifiedDate,StorageClass,IntelligentTieringAccessTier",
        "creationTimestamp": now.isoformat().replace("+00:00", "Z"),
        "files": [{"key": data_key}],
    }

    csv_rows = f"{bucket_name},repo/a,1073741824,{in_window_last_modified},INTELLIGENT_TIERING,FREQUENT"

    mock_s3 = _MockS3InventoryClient(
        inventory_configurations=[
            {
                "Id": "entire-bucket",
                "IsEnabled": True,
                "OptionalFields": [
                    "Size",
                    "LastModifiedDate",
                    "StorageClass",
                    "IntelligentTieringAccessTier",
                ],
                "Destination": {
                    "S3BucketDestination": {
                        "Bucket": "arn:aws:s3:::test-bucket-logs",
                        "Prefix": "inventory",
                    }
                },
            }
        ],
        objects_by_prefix={
            f"inventory/{bucket_name}/entire-bucket/": [
                {
                    "Key": manifest_key,
                    "LastModified": now,
                }
            ],
        },
        object_payloads={
            manifest_key: json.dumps(manifest_payload).encode("utf-8"),
            data_key: gzip.compress(csv_rows.encode("utf-8")),
        },
    )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_cloudwatch)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: mock_s3)

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.intelligent_tiering_forecast is not None
    assert stats.intelligent_tiering_forecast.available
    assert stats.intelligent_tiering_forecast.objects_transitioning_next_week == 1
    assert stats.intelligent_tiering_forecast.size_bytes_transitioning_next_week == 1024**3


def test_get_bucket_stats_inventory_forecast_streams_inventory_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")
    bucket_name = cfg.aws.s3_bucket
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 1.0}],
    }
    mock_cloudwatch = _MockCloudWatchClient(metrics)

    now = datetime.now(UTC)
    in_window_last_access = (now - timedelta(days=24)).isoformat().replace("+00:00", "Z")

    manifest_key = f"inventory/{bucket_name}/entire-bucket/2026-02-01T00-00Z/manifest.json"
    data_key = f"inventory/{bucket_name}/entire-bucket/data/part-00000.csv.gz"

    manifest_payload = {
        "fileFormat": "CSV",
        "fileSchema": "Bucket,Key,Size,LastModifiedDate,LastAccessDate,StorageClass,IntelligentTieringAccessTier",
        "creationTimestamp": now.isoformat().replace("+00:00", "Z"),
        "files": [{"key": data_key}],
    }

    csv_rows = (
        f"{bucket_name},repo/a,1073741824,{in_window_last_access},{in_window_last_access},INTELLIGENT_TIERING,FREQUENT"
    )

    mock_s3 = _MockS3InventoryClient(
        inventory_configurations=[
            {
                "Id": "entire-bucket",
                "IsEnabled": True,
                "OptionalFields": [
                    "Size",
                    "LastModifiedDate",
                    "StorageClass",
                    "IntelligentTieringAccessTier",
                ],
                "Destination": {
                    "S3BucketDestination": {
                        "Bucket": "arn:aws:s3:::test-bucket-logs",
                        "Prefix": "inventory",
                    }
                },
            }
        ],
        objects_by_prefix={
            f"inventory/{bucket_name}/entire-bucket/": [
                {
                    "Key": manifest_key,
                    "LastModified": now,
                }
            ],
        },
        object_payloads={
            manifest_key: json.dumps(manifest_payload).encode("utf-8"),
            data_key: gzip.compress(csv_rows.encode("utf-8")),
        },
        object_keys_requiring_streaming={data_key},
    )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_cloudwatch)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: mock_s3)

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.intelligent_tiering_forecast is not None
    assert stats.intelligent_tiering_forecast.available
    assert stats.intelligent_tiering_forecast.objects_transitioning_next_week == 1
    assert stats.intelligent_tiering_forecast.size_bytes_transitioning_next_week == 1024**3


def test_get_bucket_stats_inventory_forecast_kms_access_denied_shows_actionable_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_config("test-bucket")
    bucket_name = cfg.aws.s3_bucket
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 1.0}],
    }
    mock_cloudwatch = _MockCloudWatchClient(metrics)

    now = datetime.now(UTC)
    manifest_key = f"inventory/{bucket_name}/entire-bucket/2026-02-01T00-00Z/manifest.json"

    kms_access_denied = ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": (
                    "User is not authorized to perform: kms:Decrypt on the resource associated with this ciphertext"
                ),
            }
        },
        "GetObject",
    )

    mock_s3 = _MockS3InventoryClient(
        inventory_configurations=[
            {
                "Id": "entire-bucket",
                "IsEnabled": True,
                "OptionalFields": [
                    "Size",
                    "LastModifiedDate",
                    "StorageClass",
                    "IntelligentTieringAccessTier",
                ],
                "Destination": {
                    "S3BucketDestination": {
                        "Bucket": "arn:aws:s3:::test-bucket-logs",
                        "Prefix": "inventory",
                    }
                },
            }
        ],
        objects_by_prefix={
            f"inventory/{bucket_name}/entire-bucket/": [
                {
                    "Key": manifest_key,
                    "LastModified": now,
                }
            ],
        },
        object_errors={
            manifest_key: kms_access_denied,
        },
    )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_cloudwatch)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: mock_s3)

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.intelligent_tiering_forecast is not None
    assert not stats.intelligent_tiering_forecast.available
    assert stats.intelligent_tiering_forecast.unavailable_reason == (
        "Missing KMS permissions for S3 Inventory objects. "
        "Grant kms:Decrypt (and kms:DescribeKey) in the inventory bucket region and allow this principal "
        "in the KMS key policy."
    )


def test_get_bucket_stats_inventory_forecast_access_denied_preserves_denied_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_config("test-bucket")
    bucket_name = cfg.aws.s3_bucket
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)

    metrics: dict[tuple[str, str], list[dict[str, object]]] = {
        ("BucketSizeBytes", "StandardStorage"): [{"Timestamp": timestamp, "Average": 10 * 1024**3}],
        ("NumberOfObjects", "AllStorageTypes"): [{"Timestamp": timestamp, "Average": 1.0}],
    }
    mock_cloudwatch = _MockCloudWatchClient(metrics)

    now = datetime.now(UTC)
    manifest_key = f"inventory/{bucket_name}/entire-bucket/2026-02-01T00-00Z/manifest.json"

    access_denied = ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": (
                    "User is not authorized to perform: kms:DescribeKey on resource "
                    "arn:aws:kms:us-east-1:111122223333:key/example"
                ),
            }
        },
        "GetObject",
    )

    mock_s3 = _MockS3InventoryClient(
        inventory_configurations=[
            {
                "Id": "entire-bucket",
                "IsEnabled": True,
                "OptionalFields": [
                    "Size",
                    "LastModifiedDate",
                    "StorageClass",
                    "IntelligentTieringAccessTier",
                ],
                "Destination": {
                    "S3BucketDestination": {
                        "Bucket": "arn:aws:s3:::test-bucket-logs",
                        "Prefix": "inventory",
                    }
                },
            }
        ],
        objects_by_prefix={
            f"inventory/{bucket_name}/entire-bucket/": [
                {
                    "Key": manifest_key,
                    "LastModified": now,
                }
            ],
        },
        object_errors={
            manifest_key: access_denied,
        },
    )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: mock_cloudwatch)
    monkeypatch.setattr(s3, "_create_s3_client", lambda _cfg: mock_s3)

    stats = s3.get_bucket_stats(cfg=cfg)

    assert stats.intelligent_tiering_forecast is not None
    assert not stats.intelligent_tiering_forecast.available
    assert stats.intelligent_tiering_forecast.unavailable_reason is not None
    assert "Access denied while reading S3 Inventory metadata." in stats.intelligent_tiering_forecast.unavailable_reason
    assert "kms:DescribeKey" in stats.intelligent_tiering_forecast.unavailable_reason


def test_get_bucket_stats_wraps_cloudwatch_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")

    class FailingClient:
        def get_metric_statistics(self, **kwargs: object) -> dict[str, object]:
            _ = kwargs
            raise RuntimeError("cloudwatch unavailable")

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: FailingClient())

    with pytest.raises(StorageError, match="Failed to retrieve S3 bucket stats"):
        _ = s3.get_bucket_stats(cfg=cfg)


def test_get_bucket_stats_wraps_botocore_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _make_config("test-bucket")

    class FailingClient:
        def get_metric_statistics(self, **kwargs: object) -> dict[str, object]:
            _ = kwargs
            raise ClientError(
                {
                    "Error": {
                        "Code": "InternalError",
                        "Message": "cloudwatch unavailable",
                    }
                },
                "GetMetricStatistics",
            )

    monkeypatch.setattr(s3, "_create_cloudwatch_client", lambda _cfg: FailingClient())

    with pytest.raises(StorageError, match="Failed to retrieve S3 bucket stats"):
        _ = s3.get_bucket_stats(cfg=cfg)
