import csv
import gzip
import io
import json
import subprocess as sp
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from borgboi.config import Config, get_config
from borgboi.core.errors import StorageError

_CLOUDWATCH_PERIOD_SECONDS = 86400
_INTELLIGENT_TIERING_TRANSITION_DAYS = 30
_INTELLIGENT_TIERING_FORECAST_WINDOW_DAYS = 7
_INVENTORY_REQUIRED_FIELDS = {
    "Size",
    "StorageClass",
    "IntelligentTieringAccessTier",
}
_INVENTORY_ACCESS_TIME_FIELDS = ("LastAccessDate", "LastModifiedDate")


@dataclass(frozen=True)
class S3StorageClassBreakdown:
    """A single storage class/tier composition entry for a bucket."""

    storage_class: str
    tier: str
    size_bytes: int


@dataclass(frozen=True)
class S3BucketStats:
    """Bucket-wide storage statistics from CloudWatch S3 daily metrics."""

    bucket_name: str
    total_size_bytes: int
    total_object_count: int
    storage_breakdown: list[S3StorageClassBreakdown]
    metrics_timestamp: datetime | None = None
    intelligent_tiering_forecast: "S3IntelligentTieringForecast | None" = None


@dataclass(frozen=True)
class S3IntelligentTieringForecast:
    """Inventory-based FA->IA transition forecast metadata for S3 Intelligent-Tiering."""

    window_start: datetime
    window_end: datetime
    available: bool
    objects_transitioning_next_week: int = 0
    size_bytes_transitioning_next_week: int = 0
    inventory_generated_at: datetime | None = None
    inventory_configuration_id: str | None = None
    estimation_method: str | None = None
    unavailable_reason: str | None = None


_STORAGE_TYPE_BREAKDOWN: dict[str, tuple[str, str]] = {
    "StandardStorage": ("STANDARD", "-"),
    "StandardIAStorage": ("STANDARD_IA", "-"),
    "OneZoneIAStorage": ("ONEZONE_IA", "-"),
    "ReducedRedundancyStorage": ("REDUCED_REDUNDANCY", "-"),
    "GlacierStorage": ("GLACIER", "-"),
    "GlacierInstantRetrievalStorage": ("GLACIER_IR", "-"),
    "DeepArchiveStorage": ("DEEP_ARCHIVE", "-"),
    "ExpressOneZoneStorage": ("EXPRESS_ONEZONE", "-"),
    "IntelligentTieringFAStorage": ("INTELLIGENT_TIERING", "FA"),
    "IntelligentTieringIAStorage": ("INTELLIGENT_TIERING", "IA"),
    "IntelligentTieringAIAStorage": ("INTELLIGENT_TIERING", "AIA"),
    "IntelligentTieringAAStorage": ("INTELLIGENT_TIERING", "AA"),
    "IntelligentTieringDAAStorage": ("INTELLIGENT_TIERING", "DAA"),
}


def _create_cloudwatch_client(cfg: Config) -> Any:
    """Create a CloudWatch client using configured AWS region/profile."""
    session = boto3.session.Session(profile_name=cfg.aws.profile) if cfg.aws.profile else boto3.session.Session()
    return session.client(
        "cloudwatch",
        region_name=cfg.aws.region,
        config=BotoConfig(retries={"mode": "standard"}),
    )


def _create_s3_client(cfg: Config) -> Any:
    """Create an S3 client using configured AWS region/profile."""
    session = boto3.session.Session(profile_name=cfg.aws.profile) if cfg.aws.profile else boto3.session.Session()
    return session.client(
        "s3",
        region_name=cfg.aws.region,
        config=BotoConfig(retries={"mode": "standard"}),
    )


def _get_latest_metric_average(
    cloudwatch_client: Any,
    *,
    bucket_name: str,
    metric_name: str,
    storage_type: str,
) -> tuple[int, datetime | None]:
    """Return latest CloudWatch average value for a bucket/storage dimension."""
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(days=3)
    response = cloudwatch_client.get_metric_statistics(
        Namespace="AWS/S3",
        MetricName=metric_name,
        Dimensions=[
            {"Name": "BucketName", "Value": bucket_name},
            {"Name": "StorageType", "Value": storage_type},
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=_CLOUDWATCH_PERIOD_SECONDS,
        Statistics=["Average"],
    )

    datapoints = response.get("Datapoints", [])
    if not isinstance(datapoints, list) or not datapoints:
        return 0, None

    typed_datapoints = [
        item for item in datapoints if isinstance(item, dict) and isinstance(item.get("Timestamp"), datetime)
    ]
    if not typed_datapoints:
        return 0, None

    latest = max(typed_datapoints, key=lambda item: item["Timestamp"])
    average_value = float(latest.get("Average", 0.0))
    rounded_value = round(average_value)
    return max(rounded_value, 0), latest["Timestamp"]


def _unavailable_intelligent_tiering_forecast(
    *, reason: str, now: datetime, window_end: datetime
) -> S3IntelligentTieringForecast:
    return S3IntelligentTieringForecast(
        window_start=now,
        window_end=window_end,
        available=False,
        unavailable_reason=reason,
    )


def _format_inventory_forecast_unavailable_reason(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        response = exc.response
        error_details = response.get("Error", {}) if isinstance(response, dict) else {}
        code = str(error_details.get("Code", ""))
        message = str(error_details.get("Message", ""))
        error_summary = f"{code}: {message}" if code and message else message or code or str(exc)

        if code in {"AccessDenied", "AccessDeniedException"} and "kms:Decrypt" in message:
            return (
                "Missing KMS permissions for S3 Inventory objects. "
                "Grant kms:Decrypt (and kms:DescribeKey) in the inventory bucket region and allow this principal "
                "in the KMS key policy."
            )

        if code in {"AccessDenied", "AccessDeniedException"}:
            return (
                "Access denied while reading S3 Inventory metadata. "
                "Ensure this principal can list/get inventory objects and decrypt them when SSE-KMS is enabled. "
                f"AWS error details: {error_summary}"
            )

    return f"Failed to load S3 Inventory metadata: {exc}"


def _parse_inventory_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.isdigit():
        timestamp = int(cleaned)
        if timestamp > 9999999999:
            return datetime.fromtimestamp(timestamp / 1000, tz=UTC)
        return datetime.fromtimestamp(timestamp, tz=UTC)

    normalized = cleaned.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_inventory_int(value: str | None) -> int | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None


def _is_eligible_inventory_configuration(configuration: dict[str, Any]) -> bool:
    if not configuration.get("IsEnabled"):
        return False

    optional_fields = configuration.get("OptionalFields", [])
    if not isinstance(optional_fields, list):
        return False

    optional_field_set = set(optional_fields)
    return _INVENTORY_REQUIRED_FIELDS.issubset(optional_field_set) and any(
        field in optional_field_set for field in _INVENTORY_ACCESS_TIME_FIELDS
    )


def _extract_inventory_configuration(s3_client: Any, bucket_name: str) -> dict[str, Any] | None:
    continuation_token: str | None = None
    matching: list[dict[str, Any]] = []

    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket_name}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3_client.list_bucket_inventory_configurations(**kwargs)
        configurations = response.get("InventoryConfigurationList", [])

        if isinstance(configurations, list):
            matching.extend(
                configuration
                for configuration in configurations
                if isinstance(configuration, dict) and _is_eligible_inventory_configuration(configuration)
            )

        if not response.get("IsTruncated"):
            break

        next_token = response.get("NextContinuationToken")
        if not isinstance(next_token, str) or not next_token:
            break
        continuation_token = next_token

    if not matching:
        return None

    matching.sort(key=lambda item: str(item.get("Id", "")))
    return matching[0]


def _extract_bucket_name_from_arn(bucket_arn_or_name: str) -> str:
    prefix = "arn:aws:s3:::"
    if bucket_arn_or_name.startswith(prefix):
        return bucket_arn_or_name.removeprefix(prefix)
    return bucket_arn_or_name


def _list_objects_for_prefix(s3_client: Any, *, bucket_name: str, prefix: str) -> list[dict[str, Any]]:
    continuation_token: str | None = None
    objects: list[dict[str, Any]] = []

    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket_name, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3_client.list_objects_v2(**kwargs)
        contents = response.get("Contents", [])
        if isinstance(contents, list):
            objects.extend(item for item in contents if isinstance(item, dict))

        if not response.get("IsTruncated"):
            break

        next_token = response.get("NextContinuationToken")
        if not isinstance(next_token, str) or not next_token:
            break

        continuation_token = next_token

    return objects


def _get_inventory_manifest(
    s3_client: Any,
    *,
    destination_bucket: str,
    destination_prefix: str,
    source_bucket: str,
    inventory_configuration_id: str,
) -> tuple[dict[str, Any], datetime | None] | None:
    prefix_parts = []
    if destination_prefix:
        prefix_parts.append(destination_prefix.rstrip("/"))
    prefix_parts.extend([source_bucket, inventory_configuration_id])
    manifest_prefix = "/".join(prefix_parts) + "/"

    objects = _list_objects_for_prefix(s3_client, bucket_name=destination_bucket, prefix=manifest_prefix)
    manifest_candidates = [
        item for item in objects if isinstance(item.get("Key"), str) and str(item["Key"]).endswith("/manifest.json")
    ]
    if not manifest_candidates:
        return None

    def _manifest_last_modified(item: dict[str, Any]) -> datetime:
        last_modified = item.get("LastModified")
        if isinstance(last_modified, datetime):
            return last_modified
        return datetime.min.replace(tzinfo=UTC)

    latest_manifest = max(manifest_candidates, key=_manifest_last_modified)

    manifest_key = latest_manifest.get("Key")
    if not isinstance(manifest_key, str):
        return None

    manifest_response = s3_client.get_object(Bucket=destination_bucket, Key=manifest_key)
    manifest_body = manifest_response.get("Body")
    if manifest_body is None:
        return None

    manifest_bytes = manifest_body.read()
    if not isinstance(manifest_bytes, bytes):
        return None

    manifest_json = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest_json, dict):
        return None

    last_modified = latest_manifest.get("LastModified")
    manifest_timestamp = last_modified if isinstance(last_modified, datetime) else None
    return manifest_json, manifest_timestamp


def _iter_inventory_rows(
    s3_client: Any,
    *,
    destination_bucket: str,
    object_key: str,
    schema_columns: list[str],
) -> Generator[dict[str, str]]:
    response = s3_client.get_object(Bucket=destination_bucket, Key=object_key)
    body = response.get("Body")
    if body is None:
        return

    binary_stream: Any = gzip.GzipFile(fileobj=body, mode="rb") if object_key.endswith(".gz") else body

    try:
        with io.TextIOWrapper(binary_stream, encoding="utf-8", newline="") as text_stream:
            reader = csv.reader(text_stream)

            for row in reader:
                if len(row) < len(schema_columns):
                    continue

                if row[: len(schema_columns)] == schema_columns:
                    continue

                mapped = {schema_columns[idx]: row[idx] for idx in range(len(schema_columns))}
                yield mapped
    finally:
        close = getattr(binary_stream, "close", None)
        if callable(close):
            close()


def _extract_inventory_destination_details(configuration: dict[str, Any]) -> tuple[str, str] | None:
    destination = configuration.get("Destination")
    if not isinstance(destination, dict):
        return None

    destination_bucket_config = destination.get("S3BucketDestination")
    if not isinstance(destination_bucket_config, dict):
        return None

    destination_bucket_arn_or_name = destination_bucket_config.get("Bucket")
    if not isinstance(destination_bucket_arn_or_name, str) or not destination_bucket_arn_or_name:
        return None

    destination_bucket_name = _extract_bucket_name_from_arn(destination_bucket_arn_or_name)
    destination_prefix = destination_bucket_config.get("Prefix", "")
    if not isinstance(destination_prefix, str):
        destination_prefix = ""

    return destination_bucket_name, destination_prefix


def _extract_inventory_file_keys(manifest: dict[str, Any]) -> list[str]:
    files = manifest.get("files")
    if not isinstance(files, list):
        return []

    keys: list[str] = []
    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue
        object_key = file_entry.get("key")
        if isinstance(object_key, str) and object_key:
            keys.append(object_key)

    return keys


def _extract_inventory_schema_columns(manifest: dict[str, Any]) -> list[str] | None:
    file_format = manifest.get("fileFormat")
    if file_format != "CSV":
        return None

    file_schema = manifest.get("fileSchema")
    if not isinstance(file_schema, str) or not file_schema.strip():
        return None

    schema_columns = [column.strip() for column in file_schema.split(",") if column.strip()]
    schema_column_set = set(schema_columns)
    if not _INVENTORY_REQUIRED_FIELDS.issubset(schema_column_set):
        return None

    if not any(field in schema_column_set for field in _INVENTORY_ACCESS_TIME_FIELDS):
        return None

    return schema_columns


def _project_intelligent_tiering_transitions(
    s3_client: Any,
    *,
    destination_bucket_name: str,
    data_file_keys: list[str],
    schema_columns: list[str],
    now: datetime,
    window_end: datetime,
) -> tuple[int, int]:
    projected_objects = 0
    projected_size_bytes = 0

    for object_key in data_file_keys:
        for row in _iter_inventory_rows(
            s3_client,
            destination_bucket=destination_bucket_name,
            object_key=object_key,
            schema_columns=schema_columns,
        ):
            storage_class = row.get("StorageClass")
            access_tier = row.get("IntelligentTieringAccessTier")
            if storage_class != "INTELLIGENT_TIERING" or access_tier != "FREQUENT":
                continue

            size_bytes = _parse_inventory_int(row.get("Size"))
            last_accessed_or_modified = _parse_inventory_timestamp(row.get("LastAccessDate"))
            if last_accessed_or_modified is None:
                last_accessed_or_modified = _parse_inventory_timestamp(row.get("LastModifiedDate"))

            if size_bytes is None or last_accessed_or_modified is None:
                continue

            projected_transition_at = last_accessed_or_modified + timedelta(days=_INTELLIGENT_TIERING_TRANSITION_DAYS)
            if now <= projected_transition_at <= window_end:
                projected_objects += 1
                projected_size_bytes += max(size_bytes, 0)

    return projected_objects, projected_size_bytes


def _build_intelligent_tiering_forecast(s3_client: Any, *, bucket_name: str) -> S3IntelligentTieringForecast:
    now = datetime.now(UTC)
    window_end = now + timedelta(days=_INTELLIGENT_TIERING_FORECAST_WINDOW_DAYS)

    try:
        configuration = _extract_inventory_configuration(s3_client, bucket_name)
        if configuration is None:
            return _unavailable_intelligent_tiering_forecast(
                reason=(
                    "No enabled S3 Inventory configuration includes required optional fields "
                    "(Size, StorageClass, IntelligentTieringAccessTier, and LastAccessDate or LastModifiedDate)."
                ),
                now=now,
                window_end=window_end,
            )

        configuration_id = configuration.get("Id")
        if not isinstance(configuration_id, str) or not configuration_id:
            return _unavailable_intelligent_tiering_forecast(
                reason="Enabled S3 Inventory configuration has no usable ID.",
                now=now,
                window_end=window_end,
            )

        destination_details = _extract_inventory_destination_details(configuration)
        if destination_details is None:
            return _unavailable_intelligent_tiering_forecast(
                reason="Enabled S3 Inventory configuration is missing destination metadata.",
                now=now,
                window_end=window_end,
            )
        destination_bucket_name, destination_prefix = destination_details

        manifest_entry = _get_inventory_manifest(
            s3_client,
            destination_bucket=destination_bucket_name,
            destination_prefix=destination_prefix,
            source_bucket=bucket_name,
            inventory_configuration_id=configuration_id,
        )
        if manifest_entry is None:
            return _unavailable_intelligent_tiering_forecast(
                reason=(
                    "No delivered inventory manifest found yet. The first S3 Inventory report can take up to 48 hours "
                    "after configuration."
                ),
                now=now,
                window_end=window_end,
            )

        manifest, manifest_last_modified = manifest_entry
        schema_columns = _extract_inventory_schema_columns(manifest)
        if schema_columns is None:
            return _unavailable_intelligent_tiering_forecast(
                reason="Inventory format/schema is missing required columns for transition estimation.",
                now=now,
                window_end=window_end,
            )

        data_file_keys = _extract_inventory_file_keys(manifest)
        if not data_file_keys:
            return _unavailable_intelligent_tiering_forecast(
                reason="Inventory manifest contains no data files.",
                now=now,
                window_end=window_end,
            )

        projected_objects, projected_size_bytes = _project_intelligent_tiering_transitions(
            s3_client,
            destination_bucket_name=destination_bucket_name,
            data_file_keys=data_file_keys,
            schema_columns=schema_columns,
            now=now,
            window_end=window_end,
        )

        inventory_generated_at = _parse_inventory_timestamp(str(manifest.get("creationTimestamp", "")))
        if inventory_generated_at is None:
            inventory_generated_at = manifest_last_modified

        return S3IntelligentTieringForecast(
            window_start=now,
            window_end=window_end,
            available=True,
            objects_transitioning_next_week=projected_objects,
            size_bytes_transitioning_next_week=projected_size_bytes,
            inventory_generated_at=inventory_generated_at,
            inventory_configuration_id=configuration_id,
            estimation_method=(
                "S3 Inventory heuristic: LastAccessDate + 30 days without access "
                "(fallback to LastModifiedDate when LastAccessDate is unavailable)."
            ),
        )
    except (ClientError, BotoCoreError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _unavailable_intelligent_tiering_forecast(
            reason=_format_inventory_forecast_unavailable_reason(exc),
            now=now,
            window_end=window_end,
        )


def get_bucket_stats(cfg: Config | None = None) -> S3BucketStats:
    """Get bucket-wide storage composition and object counts from CloudWatch."""
    config = cfg or get_config()
    bucket_name = config.aws.s3_bucket

    try:
        cloudwatch_client = _create_cloudwatch_client(config)

        aggregated_size: dict[tuple[str, str], int] = {}
        metric_timestamps: list[datetime] = []

        for storage_type, (storage_class, tier) in _STORAGE_TYPE_BREAKDOWN.items():
            size_bytes, timestamp = _get_latest_metric_average(
                cloudwatch_client,
                bucket_name=bucket_name,
                metric_name="BucketSizeBytes",
                storage_type=storage_type,
            )
            if timestamp is not None:
                metric_timestamps.append(timestamp)
            if size_bytes <= 0:
                continue

            # Keep this additive in case AWS introduces multiple storage-type metrics
            # that map to the same logical storage class/tier pair.
            key = (storage_class, tier)
            aggregated_size[key] = aggregated_size.get(key, 0) + size_bytes

        total_object_count, object_timestamp = _get_latest_metric_average(
            cloudwatch_client,
            bucket_name=bucket_name,
            metric_name="NumberOfObjects",
            storage_type="AllStorageTypes",
        )
        if object_timestamp is not None:
            metric_timestamps.append(object_timestamp)

        breakdown = [
            S3StorageClassBreakdown(storage_class=storage_class, tier=tier, size_bytes=size_bytes)
            for (storage_class, tier), size_bytes in aggregated_size.items()
        ]
        breakdown.sort(key=lambda item: item.size_bytes, reverse=True)

        total_size_bytes = sum(item.size_bytes for item in breakdown)
        latest_timestamp = max(metric_timestamps) if metric_timestamps else None
        try:
            s3_client = _create_s3_client(config)
            intelligent_tiering_forecast = _build_intelligent_tiering_forecast(s3_client, bucket_name=bucket_name)
        except (ClientError, BotoCoreError) as exc:
            now = datetime.now(UTC)
            intelligent_tiering_forecast = _unavailable_intelligent_tiering_forecast(
                reason=f"Failed to initialize S3 client for inventory forecast: {exc}",
                now=now,
                window_end=now + timedelta(days=_INTELLIGENT_TIERING_FORECAST_WINDOW_DAYS),
            )

        return S3BucketStats(
            bucket_name=bucket_name,
            total_size_bytes=total_size_bytes,
            total_object_count=total_object_count,
            storage_breakdown=breakdown,
            metrics_timestamp=latest_timestamp,
            intelligent_tiering_forecast=intelligent_tiering_forecast,
        )
    except (ClientError, BotoCoreError) as exc:
        raise StorageError(
            f"Failed to retrieve S3 bucket stats for bucket '{bucket_name}': {exc}",
            operation="s3_stats",
            cause=exc,
        ) from exc
    except Exception as exc:
        raise StorageError(
            f"Failed to retrieve S3 bucket stats for bucket '{bucket_name}': {exc}",
            operation="s3_stats",
            cause=exc,
        ) from exc


def sync_with_s3(repo_path: str, repo_name: str, cfg: Config | None = None) -> Generator[str]:
    """
    Sync a Borg repository with an S3 bucket while yielding the output line by line.

    Args:
        repo_path (str): posix path to the Borg repository
        repo_name (str): name of the Borg repository
        cfg (Config | None): borgboi configuration (defaults to global config)

    Raises:
        sp.CalledProcessError: If the command returns a non-zero exit code

    Yields:
        Generator[str]: stdout of S3 sync command line by line
    """
    sync_source = repo_path
    cfg = cfg or get_config()
    s3_destination_uri = f"s3://{cfg.aws.s3_bucket}/{repo_name}"
    cmd = [
        "aws",
        "s3",
        "sync",
        sync_source,
        s3_destination_uri,
        "--storage-class",
        "INTELLIGENT_TIERING",
    ]

    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    out_stream = proc.stdout

    if not out_stream:
        raise ValueError("stdout is None")

    while out_stream.readable():
        line = out_stream.readline()
        if not line:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            break
        yield line.decode("utf-8")

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0:
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd)


def restore_from_s3(repo_path: str, repo_name: str, dry_run: bool, cfg: Config | None = None) -> Generator[str]:
    """
    Restore a Borg repository from an S3 bucket while yielding the output line by line.

    Args:
        repo_path (str): posix path to the Borg repository
        repo_name (str): name of the Borg repository
        dry_run (bool): whether to simulate the restore without making changes
        cfg (Config | None): borgboi configuration (defaults to global config)

    Raises:
        sp.CalledProcessError: If the command returns a non-zero exit code

    Yields:
        Generator[str]: stdout of S3 sync command line by line
    """
    cfg = cfg or get_config()
    sync_source = f"s3://{cfg.aws.s3_bucket}/{repo_name}"
    s3_destination_uri = repo_path
    if dry_run:
        cmd = [
            "aws",
            "s3",
            "--dryrun",
            "sync",
            sync_source,
            s3_destination_uri,
        ]
    else:
        cmd = [
            "aws",
            "s3",
            "sync",
            sync_source,
            s3_destination_uri,
        ]

    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    out_stream = proc.stdout

    if not out_stream:
        raise ValueError("stdout is None")

    while out_stream.readable():
        line = out_stream.readline()
        if not line:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            break
        yield line.decode("utf-8")

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0:
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd)
