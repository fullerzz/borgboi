from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARCHIVE_NAME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def create_archive_name() -> str:
    """Create an archive name using Borg's timestamp format."""
    return datetime.now(UTC).strftime(ARCHIVE_NAME_FORMAT)


def shorten_archive_path(archive_path: str) -> str:
    """
    Shorten the archive path for display purposes.

    Args:
        archive_path (str): The full path of the archive.

    Returns:
        str: The shortened archive path.
    """
    home_dir = Path.home().as_posix()[1:]  # Get home directory without leading slash
    if archive_path.startswith(home_dir):
        archive_path = archive_path.replace(home_dir, "~", 1)
    parts = archive_path.split("/")
    if len(parts) > 3:
        return "/".join([*parts[:4], "...", *parts[-2:]])
    return archive_path


def calculate_archive_age(archive_time: str) -> str:
    """
    Calculate the age of a Borg archive based on its creation time.

    Args:
        archive_time (str): The creation time of the archive in "YYYY-MM-DD_HH:MM:SS" format (UTC).

    Returns:
        str: A human-readable string representing the age of the archive (i.e. "2d 3h 15m").
    """
    # Parse the custom format string and make it timezone-aware (UTC)
    archive_datetime = datetime.strptime(archive_time, "%Y-%m-%d_%H:%M:%S").replace(tzinfo=UTC)
    now = datetime.now(tz=UTC)
    age = now - archive_datetime
    days = age.days
    hours, remainder = divmod(age.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def coerce_int(value: Any) -> int | None:
    """Convert an unknown value to int when possible."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def format_size_bytes(size_bytes: int | None) -> str:
    """Format bytes using Borg-like human readable units."""
    if size_bytes is None:
        return "Unknown"
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(size_bytes)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1

    if unit == 0:
        return f"{int(value)} {units[unit]}"
    return f"{value:.2f} {units[unit]}"


def format_iso_timestamp(value: Any) -> str:
    """Format timestamps from Borg JSON payloads."""
    if not isinstance(value, str) or not value.strip():
        return "Unknown"

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    return parsed.strftime("%a, %Y-%m-%d %H:%M:%S")


def format_duration_seconds(seconds: Any) -> str:
    """Format a duration value in seconds for display."""
    if not isinstance(seconds, (int, float)):
        return "Unknown"
    if seconds < 60:
        return f"{seconds:.2f} seconds"

    total_seconds = int(seconds)
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    return f"{remaining_minutes}m {remaining_seconds}s"
