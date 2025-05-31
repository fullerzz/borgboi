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
