# BorgBoi Docs

??? info "BorgBackup - The engine behind BorgBoi"
    This project wouldn't be possible without the underlying technology that is **BorgBackup** or Borg for short.
    >BorgBackup (short: Borg) is a deduplicating backup program. Optionally, it supports compression and authenticated encryption.
    >The main goal of Borg is to provide an efficient and secure way to backup data. The data deduplication technique used makes Borg suitable for daily backups since only changes are stored. The authenticated encryption technique makes it suitable for backups to not fully trusted targets.
    
    Their full documentation is available here: [https://borgbackup.readthedocs.io](https://borgbackup.readthedocs.io/en/stable/index.html).

## What is BorgBoi?

BorgBoi is a thin wrapper around the BorgBackup tool that I will refer to as Borg from here on out.

It contains the following features:

* Daily backup command that **creates** a new archive, **prunes** stale archives, and **compacts** the Borg repository to free up space
* Metadata about your Borg repositories is stored in DynamoDB
* Borg repositories are synced with S3 to enable cloud backups and archive restoration from other systems
## Installation

BorgBoi isn't published to PyPI yet, so it is recommended to install it with [`uv`](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/fullerzz/borgboi
```

Additionally, **BorgBackup** needs to be installed on your system for BorgBoi to work.

Read installation methods here: [https://borgbackup.readthedocs.io/en/stable/installation.html](https://borgbackup.readthedocs.io/en/stable/installation.html).

## GitHub Repo

[https://github.com/fullerzz/borgboi](https://github.com/fullerzz/borgboi)

![BorgBoi Logo](images/borgboi_logo.svg){ loading=lazy }
