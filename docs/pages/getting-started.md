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

## Configuring Environment

### AWS Credentials

**Before running BorgBoi, make sure the shell BorgBoi runs in has access to [AWS credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) with sufficient permissions for the DynamoDB table and S3 bucket.**

### BorgBoi Environment Variables

The following environment variables must be set.

| Name | Description |
| ------------ | -------------------------------------|
| `BORG_NEW_PASSPHRASE` | Passphrase to use for securing any new Borg repositories |
| `BORG_PASSPHRASE` | Passphrase to use for accessing any Borg repositories on your system |
| `BORG_S3_BUCKET` | Name of the S3 bucket responsible storing Borg repositories |
| `BORG_DYNAMODB_TABLE` | Name of the DynamoDB table responsible for storing repo metadata |

## Create a BorgBoi Repo

You can now create a Borg repository with the following BorgBoi command:

```sh
bb create-crepo --repo-path /opt/borg-repos/docs \
    --backup-target ~/Documents
```

![Demo of create-repo command](../gifs/create-repo.gif)
