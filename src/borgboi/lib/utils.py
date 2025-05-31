from datetime import UTC
from pathlib import Path


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
        return "/".join(parts[:4] + ["..."] + parts[-2:])
    return archive_path


def calculate_archive_age(archive_time: str) -> str:
    """
    Calculate the age of a Borg archive based on its creation time.

    Args:
        archive_time (str): The creation time of the archive in "YYYY-MM-DD_HH:MM:SS" format (UTC).

    Returns:
        str: A human-readable string representing the age of the archive (i.e. "2d 3h 15m").
    """
    from datetime import datetime, timezone

    # Parse the custom format string and make it timezone-aware (UTC)
    archive_datetime = datetime.strptime(archive_time, "%Y-%m-%d_%H:%M:%S").replace(tzinfo=timezone.utc)
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
