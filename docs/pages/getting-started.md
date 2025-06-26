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

For BorgBoi to function properly, it requires an S3 bucket and DynamoDB table.

Use the [IAC present in the `terraform` directory](https://github.com/fullerzz/borgboi/tree/main/terraform) to provision these resources on AWS with Terraform or OpenTofu.

!!! note "Offline Mode Available"
    If you prefer not to use AWS services, BorgBoi also supports offline mode. See the [Offline Mode](#offline-mode) section below.

## Configuring Environment

### AWS Credentials

**Before running BorgBoi, make sure the shell BorgBoi runs in has access to [AWS credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) with sufficient permissions for the DynamoDB table and S3 bucket.**

### BorgBoi Environment Variables

The following environment variables can be set:

| Name | Description | Required |
| ------------ | -------------------------------------|----------|
| `BORG_NEW_PASSPHRASE` | Passphrase to use for securing any new Borg repositories | Yes |
| `BORG_PASSPHRASE` | Passphrase to use for accessing any Borg repositories on your system | Yes |
| `BORG_S3_BUCKET` | Name of the S3 bucket responsible storing Borg repositories | Online mode only |
| `BORG_DYNAMODB_TABLE` | Name of the DynamoDB table responsible for storing repo metadata | Online mode only |
| `BORGBOI_OFFLINE` | Set to enable offline mode (no AWS services required) | No |

## Offline Mode

BorgBoi supports offline mode for users who prefer not to use AWS services or want to use BorgBoi without cloud dependencies.

### Enabling Offline Mode

You can enable offline mode in two ways:

1. **Environment Variable**: Set `BORGBOI_OFFLINE=1` in your environment
2. **Command Flag**: Add `--offline` to any BorgBoi command

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
- The `list-repos` command is not yet implemented in offline mode

## Create a BorgBoi Repo

You can now create a Borg repository with the following BorgBoi command:

```sh
bb create-repo --repo-path /opt/borg-repos/docs \
    --backup-target ~/Documents
```

![Demo of create-repo command](../gifs/create-repo.gif)
