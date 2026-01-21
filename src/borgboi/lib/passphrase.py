"""Passphrase management for BorgBoi.

This module provides secure passphrase generation, storage, and resolution
following the borgopher (Go) implementation pattern.

Security features:
- 256-bit entropy (32 random bytes)
- File-based storage with 0o600 permissions
- Directory isolation with 0o700 permissions
- Cryptographically secure random generation
- Permission validation on load
"""

import os
import secrets
import stat
from pathlib import Path

from borgboi.config import config
from borgboi.rich_utils import console


def generate_secure_passphrase() -> str:
    """Generate a cryptographically secure passphrase.

    Uses 32 random bytes (256-bit entropy) encoded in URL-safe base64.
    This matches the borgopher implementation for consistency.

    Returns:
        str: A URL-safe base64-encoded passphrase (43 characters)
    """
    return secrets.token_urlsafe(32)


def get_passphrase_file_path(repo_name: str) -> Path:
    """Get the path to a repository's passphrase file.

    Args:
        repo_name: Name of the repository

    Returns:
        Path: Path to ~/.borgboi/passphrases/{repo-name}.key
    """
    return config.passphrases_dir / f"{repo_name}.key"


def save_passphrase_to_file(repo_name: str, passphrase: str) -> Path:
    """Save a passphrase to a secure file.

    Creates the passphrases directory with 0o700 permissions if it doesn't exist,
    then saves the passphrase to a file with 0o600 permissions (owner read/write only).

    Args:
        repo_name: Name of the repository
        passphrase: Passphrase to save

    Returns:
        Path: Path to the created passphrase file

    Raises:
        OSError: If directory or file creation fails
    """
    # Ensure passphrases directory exists with secure permissions
    passphrases_dir = config.passphrases_dir
    passphrases_dir.mkdir(parents=True, exist_ok=True)
    passphrases_dir.chmod(0o700)  # drwx------ (owner only)

    # Write passphrase to file
    passphrase_file = get_passphrase_file_path(repo_name)
    passphrase_file.write_text(passphrase, encoding="utf-8")

    # Set restrictive permissions immediately after creation
    passphrase_file.chmod(0o600)  # -rw------- (owner read/write only)

    return passphrase_file


def load_passphrase_from_file(repo_name: str) -> str | None:
    """Load a passphrase from its file.

    Validates file permissions and warns if they are not 0o600.

    Args:
        repo_name: Name of the repository

    Returns:
        str | None: The passphrase, or None if file doesn't exist
    """
    passphrase_file = get_passphrase_file_path(repo_name)

    if not passphrase_file.exists():
        return None

    # Check file permissions and warn if insecure
    file_stat = passphrase_file.stat()
    file_mode = stat.S_IMODE(file_stat.st_mode)

    if file_mode != 0o600:
        console.print(f"[bold yellow]Warning: Passphrase file has insecure permissions: {oct(file_mode)}[/]")
        console.print(f"[bold yellow]Expected 0o600 (owner read/write only) for {passphrase_file}[/]")
        console.print(f"[bold yellow]Run: chmod 600 {passphrase_file}[/]")

    return passphrase_file.read_text(encoding="utf-8").strip()


def resolve_passphrase(
    repo_name: str,
    cli_passphrase: str | None = None,
    db_passphrase: str | None = None,
    allow_env_fallback: bool = True,
    env_var_name: str = "BORG_PASSPHRASE",
) -> str | None:
    """Resolve passphrase from multiple sources with priority order.

    Resolution priority:
    1. CLI parameter (temporary override, doesn't update file)
    2. Passphrase file (~/.borgboi/passphrases/{repo-name}.key)
    3. Database passphrase (legacy storage, for unmigrated repos)
    4. Environment variable (only if allow_env_fallback=True)
    5. Config file (borg.borg_passphrase or borg.borg_new_passphrase)

    Args:
        repo_name: Name of the repository
        cli_passphrase: Passphrase from CLI parameter (highest priority)
        db_passphrase: Passphrase from database (legacy storage for unmigrated repos)
        allow_env_fallback: Whether to fall back to environment variable
        env_var_name: Environment variable to check (BORG_PASSPHRASE or BORG_NEW_PASSPHRASE)

    Returns:
        str | None: Resolved passphrase, or None if not found
    """
    # Priority 1: CLI parameter (temporary override)
    if cli_passphrase is not None:
        return cli_passphrase

    # Priority 2: Passphrase file
    file_passphrase = load_passphrase_from_file(repo_name)
    if file_passphrase is not None:
        return file_passphrase

    # Priority 3: Database passphrase (legacy storage for unmigrated repos)
    if db_passphrase is not None:
        return db_passphrase

    # Priority 4: Environment variable (only if allowed)
    if allow_env_fallback:
        env_passphrase = os.getenv(env_var_name)
        if env_passphrase is not None:
            return env_passphrase

    # Priority 5: Config file
    if env_var_name == "BORG_NEW_PASSPHRASE":
        return config.borg.borg_new_passphrase
    else:
        return config.borg.borg_passphrase


def migrate_repo_passphrase(repo_name: str, old_passphrase: str) -> Path:
    """Migrate a repository's passphrase from database to file storage.

    Creates the passphrase file and validates it can be read back correctly.

    Args:
        repo_name: Name of the repository
        old_passphrase: The passphrase currently stored in the database

    Returns:
        Path: Path to the created passphrase file

    Raises:
        ValueError: If passphrase verification fails after saving
        OSError: If file creation fails
    """
    # Save passphrase to file
    passphrase_file = save_passphrase_to_file(repo_name, old_passphrase)

    # Verify passphrase can be read back
    loaded_passphrase = load_passphrase_from_file(repo_name)
    if loaded_passphrase != old_passphrase:
        # Clean up on failure
        passphrase_file.unlink(missing_ok=True)
        raise ValueError(f"Passphrase verification failed for repository '{repo_name}'. Migration aborted.")

    return passphrase_file
