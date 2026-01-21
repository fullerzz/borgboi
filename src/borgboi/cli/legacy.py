"""Legacy command aliases for backward compatibility.

This module provides deprecated aliases for the original CLI commands,
allowing users to continue using the old command names.
"""

import click

from borgboi.config import config
from borgboi.rich_utils import console


def register_legacy_commands(cli: click.Group) -> None:  # noqa: C901
    """Register legacy commands on the main CLI group.

    Args:
        cli: The main CLI group to register commands on
    """

    # Create repo (legacy: create-repo)
    @cli.command("create-repo")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
    @click.option("--backup-target", "-b", required=True, type=click.Path(exists=True), prompt=True)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def create_repo(repo_path: str, backup_target: str, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] Create a new Borg repository. Use 'repo create' instead."""
        from borgboi import orchestrator

        name = click.prompt("Enter a name for this repository")
        repo = orchestrator.create_borg_repo(
            path=repo_path, backup_path=backup_target, name=name, offline=offline, passphrase=passphrase
        )
        console.print(f"Created new Borg repo at [bold cyan]{repo.path}[/]")

    # Create exclusions (legacy: create-exclusions)
    @cli.command("create-exclusions")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
    @click.option("--exclusions-source", "-x", required=True, type=click.Path(exists=True, dir_okay=False))
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def create_exclusions(repo_path: str, exclusions_source: str, offline: bool) -> None:
        """[DEPRECATED] Create exclusions list. Use 'exclusions create' instead."""
        from borgboi import orchestrator

        repo = orchestrator.lookup_repo(repo_path, None, offline)
        orchestrator.create_excludes_list(repo.name, exclusions_source)

    # List repos (legacy: list-repos)
    @cli.command("list-repos")
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def list_repos(offline: bool) -> None:
        """[DEPRECATED] List all repositories. Use 'repo list' instead."""
        from borgboi import orchestrator

        orchestrator.list_repos(offline)

    # List archives (legacy: list-archives)
    @cli.command("list-archives")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def list_archives(repo_path: str | None, repo_name: str | None, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] List archives. Use 'backup list' instead."""
        from borgboi import orchestrator

        orchestrator.list_archives(repo_path, repo_name, offline, passphrase=passphrase)

    # List archive contents (legacy: list-archive-contents)
    @cli.command("list-archive-contents")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--archive-name", "-a", required=True, type=str)
    @click.option("--output", "-o", required=False, type=str, default="stdout")
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def list_archive_contents(
        repo_path: str | None,
        repo_name: str | None,
        archive_name: str,
        output: str,
        passphrase: str | None,
        offline: bool,
    ) -> None:
        """[DEPRECATED] List archive contents. Use 'backup contents' instead."""
        from borgboi import orchestrator

        orchestrator.list_archive_contents(repo_path, repo_name, archive_name, output, offline, passphrase=passphrase)

    # Get repo (legacy: get-repo)
    @cli.command("get-repo")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def get_repo(repo_path: str | None, repo_name: str | None, offline: bool) -> None:
        """[DEPRECATED] Get repository info. Use 'repo info' instead."""
        from borgboi import orchestrator

        repo = orchestrator.lookup_repo(repo_path, repo_name, offline)
        console.print(f"Repository found: [bold cyan]{repo.path}[/]")
        console.print(repo)

    # Daily backup (legacy: daily-backup)
    @cli.command("daily-backup")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def daily_backup(repo_path: str, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] Perform daily backup. Use 'backup daily' instead."""
        from borgboi import orchestrator

        orchestrator.perform_daily_backup(repo_path, offline, passphrase=passphrase)

    # Export repo key (legacy: export-repo-key)
    @cli.command("export-repo-key")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def export_repo_key(repo_path: str, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] Export repository key."""
        from borgboi import orchestrator

        key_path = orchestrator.extract_repo_key(repo_path, offline, passphrase=passphrase)
        console.print(f"Exported repo key to: [bold cyan]{key_path}[/]")

    # Repo info (legacy: repo-info)
    @cli.command("repo-info")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--pp", is_flag=True, show_default=True, default=True)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def repo_info(
        repo_path: str | None, repo_name: str | None, pp: bool, passphrase: str | None, offline: bool
    ) -> None:
        """[DEPRECATED] Show repository info. Use 'repo info' instead."""
        from borgboi import orchestrator

        orchestrator.get_repo_info(repo_path, repo_name, pp, offline, passphrase=passphrase)

    # Extract archive (legacy: extract-archive)
    @cli.command("extract-archive")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
    @click.option("--archive-name", "-a", required=True, prompt=True)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def extract_archive(repo_path: str, archive_name: str, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] Extract archive. Use 'backup restore' instead."""
        from borgboi import orchestrator

        click.confirm("Confirm extraction to current directory", abort=True)
        orchestrator.restore_archive(repo_path, archive_name, offline, passphrase=passphrase)

    # Delete archive (legacy: delete-archive)
    @cli.command("delete-archive")
    @click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
    @click.option("--archive-name", "-a", required=True, prompt=True)
    @click.option("--dry-run", is_flag=True, default=False)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def delete_archive(repo_path: str, archive_name: str, dry_run: bool, passphrase: str | None, offline: bool) -> None:
        """[DEPRECATED] Delete archive. Use 'backup delete' instead."""
        from borgboi import orchestrator

        orchestrator.delete_archive(repo_path, archive_name, dry_run, offline, passphrase=passphrase)

    # Delete repo (legacy: delete-repo)
    @cli.command("delete-repo")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--dry-run", is_flag=True, default=False)
    @click.option("--passphrase", "-p", type=str, default=None)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def delete_repo(
        repo_path: str | None, repo_name: str | None, dry_run: bool, passphrase: str | None, offline: bool
    ) -> None:
        """[DEPRECATED] Delete repository. Use 'repo delete' instead."""
        from borgboi import orchestrator

        orchestrator.delete_borg_repo(repo_path, repo_name, dry_run, offline, passphrase=passphrase)

    # Append excludes (legacy: append-excludes)
    @cli.command("append-excludes")
    @click.option("--repo-name", "-n", required=True, type=str)
    @click.option("--exclusion-pattern", "-x", required=True, type=str)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def append_excludes(repo_name: str, exclusion_pattern: str, offline: bool) -> None:
        """[DEPRECATED] Add exclusion pattern. Use 'exclusions add' instead."""
        from borgboi import orchestrator

        try:
            excludes_file = orchestrator.get_excludes_file(repo_name, offline)
            orchestrator.append_to_excludes_file(excludes_file, exclusion_pattern)
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    # Modify excludes (legacy: modify-excludes)
    @cli.command("modify-excludes")
    @click.option("--repo-name", "-n", required=True, type=str)
    @click.option("--delete-line-num", "-D", required=True, type=int)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def modify_excludes(repo_name: str, delete_line_num: int, offline: bool) -> None:
        """[DEPRECATED] Remove exclusion pattern. Use 'exclusions remove' instead."""
        from borgboi import orchestrator

        try:
            excludes_file = orchestrator.get_excludes_file(repo_name, offline)
            orchestrator.remove_from_excludes_file(excludes_file, delete_line_num)
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    # Restore repo (legacy: restore-repo)
    @cli.command("restore-repo")
    @click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
    @click.option("--repo-name", "-n", required=False, type=str)
    @click.option("--dry-run", is_flag=True, default=False)
    @click.option("--force", is_flag=True, default=False)
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def restore_repo(repo_path: str | None, repo_name: str | None, dry_run: bool, force: bool, offline: bool) -> None:
        """[DEPRECATED] Restore from S3. Use 's3 restore' instead."""
        from borgboi import orchestrator

        repo = orchestrator.lookup_repo(repo_path, repo_name, offline)
        if repo.metadata and repo.metadata.cache:
            console.print(
                f"Repository found: [bold cyan]{repo.path} - Total size: {repo.metadata.cache.total_size_gb} GB[/]"
            )
        else:
            console.print(f"Repository found: [bold cyan]{repo.path}[/]")
        orchestrator.restore_repo(repo, dry_run, force, offline)

    # Migrate passphrases (legacy: migrate-passphrases)
    @cli.command("migrate-passphrases")
    @click.option("--repo-name", "-n", type=str, help="Specific repo to migrate")
    @click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
    def migrate_passphrases(repo_name: str | None, offline: bool) -> None:
        """Migrate passphrases from database to file storage."""
        from borgboi import orchestrator

        if repo_name:
            try:
                repo = orchestrator.lookup_repo(None, repo_name, offline)
                orchestrator.migrate_repo_passphrase_to_file(repo, offline)
            except Exception as e:
                console.print(f"[bold red]Failed to migrate {repo_name}: {e}[/]")
        else:
            try:
                repos = orchestrator.list_repos_data(offline)
                migrated = 0
                already_migrated = 0
                failed = 0
                skipped = 0

                console.print("\n[bold]Starting passphrase migration...[/]\n")

                for repo in repos:
                    try:
                        if repo.passphrase_migrated:
                            console.print(f"[dim]  {repo.name} (already migrated)[/]")
                            already_migrated += 1
                            continue
                        if repo.passphrase is None:
                            console.print(f"[yellow]  {repo.name} (no passphrase)[/]")
                            skipped += 1
                            continue
                        orchestrator.migrate_repo_passphrase_to_file(repo, offline)
                        migrated += 1
                    except Exception as e:
                        console.print(f"[bold red]  Failed: {repo.name}: {e}[/]")
                        failed += 1

                console.print("\n[bold]Migration Summary:[/]")
                console.print(f"  [green]Migrated:[/] {migrated}")
                console.print(f"  [dim]Already migrated:[/] {already_migrated}")
                console.print(f"  [yellow]Skipped:[/] {skipped}")
                if failed > 0:
                    console.print(f"  [red]Failed:[/] {failed}")
            except Exception as e:
                console.print(f"[bold red]Migration failed: {e}[/]")
