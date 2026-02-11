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
    if not datapoints:
        return 0, None

    latest = max(datapoints, key=lambda item: item["Timestamp"])
    average_value = float(latest.get("Average", 0.0))
    rounded_value = round(average_value)
    return max(rounded_value, 0), latest["Timestamp"]


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

        return S3BucketStats(
            bucket_name=bucket_name,
            total_size_bytes=total_size_bytes,
            total_object_count=total_object_count,
            storage_breakdown=breakdown,
            metrics_timestamp=latest_timestamp,
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
