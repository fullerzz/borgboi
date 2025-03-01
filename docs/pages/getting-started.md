# Getting Started

!!! tip "Install BorgBackup"
    Before proceeding further, make sure you have **BorgBackup** installed on your system. _It is not bundled with BorgBoi._

    Read installation methods here: [https://borgbackup.readthedocs.io/en/stable/installation.html](https://borgbackup.readthedocs.io/en/stable/installation.html).

## Installation

BorgBoi isn't published to PyPI yet, so it is recommended to install it with [`uv`](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/fullerzz/borgboi
```

Additionally, **BorgBackup** needs to be installed on your system for BorgBoi to work.

Read installation methods here: [https://borgbackup.readthedocs.io/en/stable/installation.html](https://borgbackup.readthedocs.io/en/stable/installation.html).

## Provision AWS Resources

For BorgBoi to function properly, it requires an S3 bucket and DynamoDB table.

Use the IAC present in the, `terraform` directory to provision these resources on AWS.

## Configuring Environment

### AWS Credentials

This section is a work-in-progress as BorgBoi is primarily a personal project, and wasn't designed with shareable AWS resources or configurations in mind.

However, all of the terraform is present, so you should be able to provision the AWS resources yourself.

**Before running BorgBoi, make sure the shell BorgBoi runs in has access to [AWS credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) with sufficient permissions for the DynamoDB table and S3 bucket.**

### BorgBoi Environment Variables

The following environment variables must be set.

| Name | Description |
| ------------ | -------------------------------------|
| `BORG_NEW_PASSPHRASE` | Passphrase to use for securing any new Borg repositories |
| `BORG_PASSPHRASE` | Passphrase to use for accessing any Borg repositories on your system |
| `BORG_S3_BUCKET` | Name of the S3 bucket responsible storing Borg repositories |
| `BORG_DYNAMODB_TABLE` | Name of the DynamoDB table responsible for storing repo metadata |
