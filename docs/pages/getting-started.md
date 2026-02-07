# Getting Started

!!! tip "Install BorgBackup"
    Before proceeding further, make sure you have **BorgBackup** installed on your system. _It is not bundled with BorgBoi currently._

    Read installation methods here: [https://borgbackup.readthedocs.io/en/stable/installation.html](https://borgbackup.readthedocs.io/en/stable/installation.html).

## Installation

BorgBoi isn't published to PyPI yet, so it is recommended to install it from the GitHub repo with [`uv`](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/fullerzz/borgboi
```

Additionally, **BorgBackup** needs to be installed on your system for BorgBoi to work.

Read installation methods here: [https://borgbackup.readthedocs.io/en/stable/installation.html](https://borgbackup.readthedocs.io/en/stable/installation.html).

## Provision AWS Resources

For BorgBoi to function properly in online mode, it requires an S3 bucket and DynamoDB table.

Use the [IAC present in the `terraform` directory](https://github.com/fullerzz/borgboi/tree/main/terraform) to provision these resources on AWS with Terraform or OpenTofu.

!!! note "Offline Mode Available"
    If you prefer not to use AWS services, BorgBoi also supports offline mode. See the [Offline Mode](#offline-mode) section below.

## Configuration

BorgBoi uses a configuration file located at `~/.borgboi/config.yaml`. You can view the current configuration with:

```sh
bb config show
```

For a complete reference of every field, environment variable, and allowed value, see [User Configuration](user-configuration.md).

### Configuration File

Create or edit `~/.borgboi/config.yaml`:

```yaml
aws:
  s3_bucket: my-borgboi-bucket
  dynamodb_repos_table: bb-repos
  region: us-west-1

borg:
  compression: zstd,6
  storage_quota: 100G
  retention:
    keep_daily: 7
    keep_weekly: 4
    keep_monthly: 6
    keep_yearly: 0

offline: false
```

### Environment Variables

Configuration can be overridden using environment variables with the `BORGBOI_` prefix:

| Environment Variable | Config Path | Description |
| -------------------- | ----------- | ----------- |
| `BORGBOI_OFFLINE` | `offline` | Enable offline mode |
| `BORGBOI_DEBUG` | `debug` | Enable debug output |
| `BORGBOI_AWS__S3_BUCKET` | `aws.s3_bucket` | S3 bucket for backup storage |
| `BORGBOI_AWS__DYNAMODB_REPOS_TABLE` | `aws.dynamodb_repos_table` | DynamoDB table for repo metadata |
| `BORGBOI_AWS__REGION` | `aws.region` | AWS region |
| `BORGBOI_BORG__BORG_PASSPHRASE` | `borg.borg_passphrase` | Default passphrase for existing repos |
| `BORGBOI_BORG__BORG_NEW_PASSPHRASE` | `borg.borg_new_passphrase` | Passphrase for new repos |

!!! info "Passphrase Handling"
    BorgBoi uses a hierarchical passphrase resolution:

    1. **Command-line `--passphrase` option** (highest priority)
    2. **Stored passphrase file** (`~/.borgboi/passphrases/{repo-name}.key`)
    3. **Environment variable** (`BORGBOI_BORG__BORG_PASSPHRASE`)
    4. **Config file** (`borg.borg_passphrase`)

    For new repositories, BorgBoi can auto-generate passphrases and store them securely.

### AWS Credentials

**Before running BorgBoi in online mode, make sure the shell BorgBoi runs in has access to [AWS credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) with sufficient permissions for the DynamoDB table and S3 bucket.**

## Offline Mode

BorgBoi supports offline mode for users who prefer not to use AWS services or want to use BorgBoi without cloud dependencies.

### Enabling Offline Mode

You can enable offline mode in three ways:

1. **Configuration File**: Set `offline: true` in `~/.borgboi/config.yaml`
2. **Environment Variable**: Set `BORGBOI_OFFLINE=1` in your environment
3. **Command Flag**: Add `--offline` to any BorgBoi command

### How Offline Mode Works

In offline mode:

- Repository metadata is stored locally in `~/.borgboi/.borgboi_metadata/` instead of DynamoDB
- No S3 synchronization occurs during backups
- All Borg operations work normally (create, backup, extract, etc.)
- AWS credentials are not required

### Offline Mode Limitations

- Repository restoration from S3 is not available
- Repository metadata is not shared across systems
- No cloud backup of repository metadata
- The `repo list` command is not yet implemented in offline mode

## Create a BorgBoi Repo

You can now create a Borg repository with the following BorgBoi command:

```sh
bb repo create --path /opt/borg-repos/docs \
    --backup-target ~/Documents \
    --name my-docs-backup
```

Or using the legacy command syntax:

```sh
bb create-repo --repo-path /opt/borg-repos/docs \
    --backup-target ~/Documents
```

![Demo of create-repo command](../gifs/create-repo.gif)

## Perform a Daily Backup

Run a daily backup with automatic pruning and compaction:

```sh
bb backup daily --path /opt/borg-repos/docs
```

This command creates a new archive, prunes old archives based on retention policy, compacts the repository, and syncs to S3 (unless `--no-s3-sync` is specified or running in offline mode).

## List Your Repositories

View all managed repositories:

```sh
bb repo list
```

## View Repository Info

Get detailed information about a repository:

```sh
bb repo info --name my-docs-backup
```

## List Archives

View all archives in a repository:

```sh
bb backup list --name my-docs-backup
```
