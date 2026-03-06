# BorgBoi 👦🏼

BorgBoi is a CLI wrapper around [BorgBackup](https://borgbackup.readthedocs.io/en/stable/index.html) for managing repositories, running recurring backups, and optionally syncing Borg repositories to AWS S3.

It layers a grouped CLI, YAML-based configuration, local metadata storage, and AWS integration on top of Borg so routine backup workflows are easier to run and inspect.

<img src="docs/images/borgboi_logo.svg" alt="BorgBoi logo" width="400" />

## What It Does

- Creates and manages Borg repositories from a single CLI.
- Runs daily backup workflows that create archives, prune old data, and compact repositories.
- Syncs repositories to S3 and restores them when cloud mode is enabled.
- Supports offline mode with local SQLite-backed metadata storage and no AWS dependency.
- Stores repository passphrases in per-repo files under `~/.borgboi/passphrases/`.
- Exposes both grouped subcommands and legacy flat command aliases for backward compatibility.

## Prerequisites

- Python 3.12 or newer
- [BorgBackup](https://borgbackup.readthedocs.io/en/stable/installation.html) installed and available in `PATH`
- AWS credentials with access to your S3 bucket and DynamoDB tables if you want online mode

> [!IMPORTANT]
> BorgBoi wraps BorgBackup, but does not install Borg itself. Install BorgBackup separately before running repository or backup commands.

## Installation

BorgBoi is not currently published to PyPI. The recommended install path is with [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/fullerzz/borgboi
```

The installed CLI is available as either `bb` or `borgboi`.

## Quick Start

Inspect the effective configuration:

```bash
bb config show
```

Create a repository:

```bash
bb repo create \
	--path /opt/borg-repos/docs \
	--backup-target ~/Documents \
	--name my-docs-backup
```

Create an exclusions file before running backups:

```bash
bb exclusions create \
	--path /opt/borg-repos/docs \
	--source ~/borgboi-excludes.txt
```

Run the daily backup workflow:

```bash
bb backup daily --name my-docs-backup
```

Inspect repositories and archives:

```bash
bb repo list
bb backup list --name my-docs-backup
bb repo info --name my-docs-backup
```

## Cloud And Offline Modes

In its default online mode, BorgBoi uses AWS services for metadata and repository synchronization:

- DynamoDB stores repository metadata.
- S3 stores synced Borg repository data.
- AWS credentials are required for S3 and DynamoDB operations.

Offline mode disables AWS usage and keeps metadata locally in SQLite while preserving the local Borg workflow.

> [!NOTE]
> Offline mode skips AWS-backed features like S3 sync and restore. Use online mode when you want cloud replication, and offline mode when you want the local Borg workflow without AWS dependencies.

Enable offline mode with any of these options:

- Set `offline: true` in `~/.borgboi/config.yaml`
- Export `BORGBOI_OFFLINE=1`
- Pass `--offline` to a BorgBoi command

Example:

```bash
export BORGBOI_OFFLINE=1
bb repo create --path /opt/borg-repos/docs --backup-target ~/Documents --name my-docs-backup
bb backup daily --name my-docs-backup
```

## Configuration

BorgBoi loads configuration from `~/.borgboi/config.yaml` and environment variables prefixed with `BORGBOI_`.

- Nested configuration values use double underscores, such as `BORGBOI_AWS__S3_BUCKET`.
- `BORGBOI_HOME` changes the base home directory used to resolve `.borgboi` paths.
- When running under `sudo`, `SUDO_USER` is used to resolve the original user's home directory when possible.

Use `bb config show --format tree` to inspect the merged effective configuration.

## Command Groups

The primary CLI is organized into grouped subcommands:

- `repo` for repository lifecycle operations
- `backup` for archive creation, listing, restore, and deletion
- `s3` for sync, restore, and bucket stats
- `exclusions` for managing backup exclusion files
- `config` for displaying effective configuration

Legacy flat commands such as `create-repo` and `daily-backup` are still available as compatibility aliases.

## Documentation

Primary documentation is published at [fullerzz.github.io/borgboi](https://fullerzz.github.io/borgboi/).

- [Docs Home](https://fullerzz.github.io/borgboi/)
- [Getting Started](https://fullerzz.github.io/borgboi/pages/getting-started/)
- [Commands Reference](https://fullerzz.github.io/borgboi/pages/commands/)
- [User Configuration](https://fullerzz.github.io/borgboi/pages/user-configuration/)
- [SQLite Database](https://fullerzz.github.io/borgboi/pages/sqlite-database/)

## Development

For local development:

```bash
uv sync
just test
just lint
just serve-docs
```
