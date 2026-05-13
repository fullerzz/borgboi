"""Repository management commands for BorgBoi CLI."""

import shutil
import subprocess
from typing import Annotated

from cyclopts import App, Parameter

from borgboi.cli.main import ContextArg, confirm_action, print_error_and_exit
from borgboi.core.logging import get_logger
from borgboi.rich_utils import console

logger = get_logger(__name__)

_RSYNC_BASE_FLAGS = [
    "--archive",
    "--hard-links",
    "--delete",
    "--partial",
]
_RSYNC_OPTIONAL_FLAGS = [
    "--human-readable",
    "--numeric-ids",
    "--delete-delay",
    "--acls",
    "--xattrs",
]
repo = App(
    name="repo",
    help="Repository management commands.\n\nCreate, inspect, list, and delete Borg repositories.",
)


def _rsync_option_text(rsync: str, option: str) -> str:
    result = subprocess.run(  # noqa: S603
        [rsync, option],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""

    return f"{result.stdout}\n{result.stderr}"


def _build_rsync_flags(rsync: str) -> list[str]:
    flags = [*_RSYNC_BASE_FLAGS]
    help_text = _rsync_option_text(rsync, "--help")
    flags.extend(flag for flag in _RSYNC_OPTIONAL_FLAGS if flag in help_text)

    info_help = _rsync_option_text(rsync, "--info=help")
    if "progress2" in info_help:
        flags.append("--info=progress2")
    elif "--progress" in help_text:
        flags.append("--progress")

    return flags


def _terminate_rsync(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _run_rsync_command(command: list[str]) -> None:
    proc = subprocess.Popen(command)  # noqa: S603
    try:
        returncode = proc.wait()
    except BaseException:
        _terminate_rsync(proc)
        raise

    if returncode != 0:
        raise subprocess.CalledProcessError(returncode=returncode, cmd=command)


@repo.command(name="create")
def repo_create(
    *,
    path: Annotated[str, Parameter(name=["--path", "-p"], help="Path to create repository")],
    backup_target: Annotated[str, Parameter(name=["--backup-target", "-b"], help="Directory to back up")],
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    passphrase: Annotated[
        str | None,
        Parameter(name="--passphrase", help="Passphrase (auto-generated if not provided)"),
    ] = None,
    ctx: ContextArg,
) -> None:
    """Create a new Borg repository."""
    logger.info("Running repository create command", repo_name=name, repo_path=path, backup_target=backup_target)
    try:
        repo_info = ctx.orchestrator.create_repo(
            path=path,
            backup_target=backup_target,
            name=name,
            passphrase=passphrase,
        )
        logger.info("Repository create command completed", repo_name=repo_info.name, repo_path=repo_info.path)
        console.print(f"Created new Borg repo at [bold cyan]{repo_info.path}[/]")
    except Exception as error:
        logger.exception(
            "Repository create command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            backup_target=backup_target,
        )
        print_error_and_exit(str(error), error=error)


@repo.command(name="import")
def repo_import(
    *,
    path: Annotated[str, Parameter(name=["--path", "-p"], help="Path to existing repository")],
    backup_target: Annotated[str, Parameter(name=["--backup-target", "-b"], help="Directory to back up")],
    name: Annotated[str, Parameter(name=["--name", "-n"], help="Repository name")],
    passphrase: Annotated[
        str | None,
        Parameter(name="--passphrase", help="Passphrase override for encrypted repositories"),
    ] = None,
    ctx: ContextArg,
) -> None:
    """Import an existing Borg repository into BorgBoi."""
    logger.info("Running repository import command", repo_name=name, repo_path=path, backup_target=backup_target)
    try:
        repo_info = ctx.orchestrator.import_repo(
            path=path,
            backup_target=backup_target,
            name=name,
            passphrase=passphrase,
        )
        logger.info("Repository import command completed", repo_name=repo_info.name, repo_path=repo_info.path)
        console.print(f"Imported existing Borg repo at [bold cyan]{repo_info.path}[/]")
    except Exception as error:
        logger.exception(
            "Repository import command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            backup_target=backup_target,
        )
        print_error_and_exit(str(error), error=error)


@repo.command(name="list")
def repo_list(*, ctx: ContextArg) -> None:
    """List all BorgBoi repositories."""
    from borgboi import rich_utils

    logger.info("Running repository list command")
    try:
        repos = ctx.orchestrator.list_repos()
        logger.info("Repository list command completed", repo_count=len(repos))
        rich_utils.output_repos_table(repos)
    except Exception as error:
        logger.exception("Repository list command failed", error=str(error))
        print_error_and_exit(str(error), error=error)


@repo.command(name="info")
def repo_info(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    raw: Annotated[
        bool, Parameter(name="--raw", negative="", help="Show raw Borg output instead of formatted")
    ] = False,
    ctx: ContextArg,
) -> None:
    """Show repository information."""
    from borgboi import rich_utils

    logger.info("Running repository info command", repo_name=name, repo_path=path, raw=raw)
    try:
        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        repo_data = ctx.orchestrator.get_repo_info(repo_info, passphrase=passphrase)

        if raw:
            logger.debug("Printing raw repository info", repo_name=repo_info.name, repo_path=repo_info.path)
            console.print(repo_data)
            return

        if repo_info.metadata:
            logger.debug("Rendering formatted repository metadata", repo_name=repo_info.name, repo_path=repo_info.path)
            rich_utils.output_repo_info(
                name=repo_info.name,
                total_size_gb=repo_info.metadata.cache.total_size_gb,
                total_csize_gb=repo_info.metadata.cache.total_csize_gb,
                unique_csize_gb=repo_info.metadata.cache.unique_csize_gb,
                encryption_mode=repo_info.metadata.encryption.mode,
                repo_id=repo_info.metadata.repository.id,
                repo_location=repo_info.metadata.repository.location,
                last_modified=repo_info.metadata.repository.last_modified,
            )
            return

        logger.debug(
            "Printing basic repository information without metadata", repo_name=repo_info.name, repo_path=repo_info.path
        )
        console.print(f"Repository: [bold cyan]{repo_info.name}[/]")
        console.print(f"Path: {repo_info.path}")
    except Exception as error:
        logger.exception("Repository info command failed", error=str(error), repo_name=name, repo_path=path, raw=raw)
        print_error_and_exit(str(error), error=error)


@repo.command(name="rsync")
def repo_rsync(
    *,
    destination: Annotated[str, Parameter(name=["--destination", "-d"], help="Mounted NFS/SMB destination path")],
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    dry_run: Annotated[
        bool, Parameter(name="--dry-run", negative="", help="Show rsync actions without copying data")
    ] = False,
    ctx: ContextArg,
) -> None:
    """Copy a local Borg repository to mounted NFS/SMB storage with rsync."""
    logger.info(
        "Running repository rsync command", repo_name=name, repo_path=path, destination=destination, dry_run=dry_run
    )
    try:
        rsync = shutil.which("rsync")
        if rsync is None:
            msg = "rsync was not found on PATH. Install rsync before using 'borgboi repo rsync'."
            raise RuntimeError(msg)

        repo_info = ctx.orchestrator.get_repo(name=name, path=path)
        source = f"{repo_info.path.rstrip('/')}/"
        console.print(f"Source: [bold cyan]{source}[/]")
        console.print(f"Destination: [bold cyan]{destination}[/]")
        console.print(
            "[bold yellow]Warning:[/] rsync will delete destination files that are not in the source repository."
        )
        if not dry_run and not confirm_action("Continue with repository rsync?"):
            logger.info(
                "Repository rsync command aborted by user",
                repo_name=repo_info.name,
                repo_path=repo_info.path,
                destination=destination,
            )
            console.print("Aborted.")
            return

        dry_run_flag = ["--dry-run"] if dry_run else []
        command = [
            rsync,
            *_build_rsync_flags(rsync),
            *dry_run_flag,
            source,
            destination,
        ]
        logger.info(
            "Starting repository rsync",
            repo_name=repo_info.name,
            repo_path=repo_info.path,
            destination=destination,
            dry_run=dry_run,
        )
        _run_rsync_command(command)
        logger.info(
            "Repository rsync command completed",
            repo_name=repo_info.name,
            repo_path=repo_info.path,
            destination=destination,
            dry_run=dry_run,
        )
        if dry_run:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
        else:
            console.print(f"[bold green]Repository synced to {destination}[/]")
    except subprocess.CalledProcessError as error:
        logger.exception(
            "Repository rsync command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            destination=destination,
            dry_run=dry_run,
        )
        print_error_and_exit(f"rsync failed with exit code {error.returncode}", error=error)
    except Exception as error:
        logger.exception(
            "Repository rsync command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            destination=destination,
            dry_run=dry_run,
        )
        print_error_and_exit(str(error), error=error)


@repo.command(name="delete")
def repo_delete(
    *,
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    dry_run: Annotated[
        bool, Parameter(name="--dry-run", negative="", help="Simulate deletion without making changes")
    ] = False,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    delete_from_s3: Annotated[
        bool,
        Parameter(name="--delete-from-s3", negative="", help="Also delete from S3"),
    ] = False,
    ctx: ContextArg,
) -> None:
    """Delete a Borg repository."""
    logger.info(
        "Running repository delete command",
        repo_name=name,
        repo_path=path,
        dry_run=dry_run,
        delete_from_s3=delete_from_s3,
    )
    if not dry_run and not confirm_action("Are you sure you want to delete this repository?"):
        logger.info("Repository delete command aborted by user", repo_name=name, repo_path=path)
        console.print("Aborted.")
        return

    try:
        ctx.orchestrator.delete_repo(
            name=name,
            path=path,
            dry_run=dry_run,
            delete_from_s3=delete_from_s3,
            passphrase=passphrase,
        )
        logger.info(
            "Repository delete command completed",
            repo_name=name,
            repo_path=path,
            dry_run=dry_run,
            delete_from_s3=delete_from_s3,
        )
        if dry_run:
            console.print("[bold yellow]Dry run completed - no changes made[/]")
        else:
            console.print("[bold green]Repository deleted successfully[/]")
    except Exception as error:
        logger.exception(
            "Repository delete command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            dry_run=dry_run,
            delete_from_s3=delete_from_s3,
        )
        print_error_and_exit(str(error), error=error)


@repo.command(name="set-quota")
def repo_set_quota(
    *,
    quota: Annotated[str, Parameter(name=["--quota", "-q"], help="New repository storage quota")],
    path: Annotated[str | None, Parameter(name=["--path", "-p"], help="Repository path")] = None,
    name: Annotated[str | None, Parameter(name=["--name", "-n"], help="Repository name")] = None,
    passphrase: Annotated[str | None, Parameter(name="--passphrase", help="Passphrase override")] = None,
    ctx: ContextArg,
) -> None:
    """Update a repository storage quota."""
    logger.info("Running repository set-quota command", repo_name=name, repo_path=path, quota=quota)
    try:
        updated_quota = ctx.orchestrator.update_repo_storage_quota(
            quota,
            name=name,
            path=path,
            passphrase=passphrase,
        )
        logger.info(
            "Repository set-quota command completed",
            repo_name=name,
            repo_path=path,
            quota=updated_quota,
        )
        console.print(f"[bold green]Repository storage quota updated to {updated_quota}[/]")
    except Exception as error:
        logger.exception(
            "Repository set-quota command failed",
            error=str(error),
            repo_name=name,
            repo_path=path,
            quota=quota,
        )
        print_error_and_exit(str(error), error=error)
