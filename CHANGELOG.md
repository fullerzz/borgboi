## v1.11.0 (2026-01-25)

### Feat

- **config**: add 'borgboi config show' command (#147)

## v1.10.0 (2026-01-21)

### Feat

- Refactor Database Schema and Core Architecture (#144)

## v1.9.1 (2025-11-09)

### Fix

- **s3**: add s3 lifecycle rule to abort multipart uploads after 2 days (#135)

## v1.9.0 (2025-11-07)

### Feat

- **tf**: Create 2 New DynamoDB Tables (#133)

## v1.8.1 (2025-06-28)

### Fix

- **dynamodb**: specify throughput config for table and GSI

## v1.8.0 (2025-06-25)

### Feat

- **terraform**: update AWS provider version to v6 (#108)

## v1.7.0 (2025-06-07)

### Feat

- Implement Offline Mode (#101)

## v1.6.1 (2025-05-31)

### Fix

- **tofu**: Enable Intelligent Tiering on S3 Logs Bucket (#100)

## v1.6.0 (2025-05-31)

### Feat

- **tofu**: enable bucket key encryption for s3 logs bucket

## v1.5.1 (2025-05-31)

### Fix

- **cli**: update type of --repo-name option from click.Path to str

## v1.5.0 (2025-05-31)

### Feat

- **s3**: default to using INTELLIGENT_TIERING for S3 storage class

### Fix

- **restore-repo**: add --force flag to restore even if repo is detected locally

## v1.4.0 (2025-05-10)

### Feat

- New Command to Restore BorgBoi Repo from S3 (#86)

## v1.3.0 (2025-05-04)

### Feat

- **tf**: add s3 intelligent tiering config to bucket

## v1.2.0 (2025-03-15)

### Feat

- integrated with catppuccin pkg for better color consistency

## v1.1.0 (2025-03-15)

### Feat

- **excludes**: add commands to append line and remove line from excludes file

### Fix

- **validator**: line number is valid if it equals len of lines as it's 1-indexed

### Refactor

- **excludes-ops**: improved docstrings and added validation in validator

## v1.0.3 (2025-03-07)

### Fix

- **delete-repo**: no longer raise FileNotFoundError if exludes list not found on repo deletion

## v1.0.2 (2025-03-07)

### Fix

- **wiki**: run docs.yml actions job with lfs checkout enabled

## v1.0.1 (2025-03-05)

### Fix

- **daily-backup**: fix incorrect docstring description regarding target of archive backup
- **list-repos**: removed incorrect docstring and added accurate description in new docstring

## v1.0.0 (2025-03-01)

### BREAKING CHANGE

- --pp Pretty print flag now defaults to True

### Feat

- **repo-info**: default pretty print --pp flag to true
- updated daily backup to use new borg client and print normal output
- add ability to disable --log-json from being passed as option to borg
- **delete**: added delete repo and delete archive commands to new module
- **extract**: add extract cmd in new module
- **repo-key**: add export-repo-key cmd in new module
- **compact**: implemented compact cmd in new module
- **prune**: implemented prune command in new module

### Fix

- **delete-archive**: render cmd output with log_json=False
- remove rich_utils.confirm_deletion call from borg client
- handle repo metadata being None/missing
- iterate over iterable
- converted computed fields with size information to return strings instead of floats

### Refactor

- **list-repos**: move table output logic for repos into rich_utils
- refactor command output rendering and moved most logic into rich_utils
- **log-parsing**: added new function to take in iterable and yield log model line by line
- removed original backups.py file
- refactor dynamodb
- **log**: moved log parsing into validator

## v0.12.1 (2025-02-20)

### Fix

- **orchestrator**: repo's exclusions file is now removed if the repo is deleted

### Refactor

- **orchestrator**: add function to get path of a repo's excludes file

## v0.12.0 (2025-02-16)

### Feat

- **list-archives**: add command to list archive names present in borg repo

## v0.11.0 (2025-02-16)

### Feat

- **delete-archive**: add CLI command to delete individual archives from within borg repo
- **delete-archive**: add support for deleting individual archives from borg repositories

### Fix

- **delete-repo**: don't call 'compact' command if entire repo is deleted
- **delete-op**: run compact command on repo after deletion command
- **delete-op**: deletion confirmation prompt now accepts repo name and archive name as params
- **delete-repo**: Repo is now delete from DynamoDB table after successful local removal

## v0.10.0 (2025-02-15)

### Feat

- add command to delete borg repo and preview deletion with dry-run

### Refactor

- raise ValueError instead of exit(0)

## v0.9.0 (2025-02-09)

### BREAKING CHANGE

- Updated type of both path and backup_target fields in BorgRepo from Path to str
- The new field os_platform needs to be manually inserted into each item that already exists in the DynamoDB table.

### Feat

- add new field 'os_platform' to BorgRepo

### Fix

- refactor validation of repo and backup target paths to resolve issue with remote repos

## v0.8.0 (2025-02-01)

### BREAKING CHANGE

- An exclusion file must exist before a daily backup or archive can be created. There is a new borgboi command to create this exclusions list. After it's created, it will be persisted. Closes #21

### Feat

- add ability to create exclusion list for each borg repo

### Fix

- **orchestrator**: the borgboi dir will be created if it doesn't exist before attempting to create exlusions file

## v0.7.0 (2025-01-31)

### Feat

- **list-repos**: add deduplicated repo size to output

### Refactor

- **dynamodb**: add botocore config to set retry behavior mode to 'standard'

## v0.6.1 (2025-01-26)

### Refactor

- **repo-info**: improved pretty print output for the borgboi repo-info command

## v0.6.0 (2025-01-25)

### Feat

- **repo-info**: add pretty print flag to repo info command

## v0.5.0 (2025-01-25)

### Feat

- implement command to extract borg archive

## v0.4.0 (2025-01-22)

### Feat

- now store repo size metadata in dynamodb table
- improved repo-info command and added data structure to store output

### Refactor

- moved borg repo info models and cmd execution into backups.py

## v0.3.0 (2025-01-18)

### Feat

- add new command to view borg repo info

### Refactor

- move get repo info logic into orchestrator and added validator module

## v0.2.2 (2025-01-18)

### Refactor

- renamed dynamo table item field from name to common_name

## v0.2.1 (2025-01-18)

### Fix

- **s3**: adds s3 prefix of borg repo name before syncing with s3

## v0.2.0 (2025-01-18)

### Feat

- add cmd to export repo key in addition to automatically exporting repo key upon repo creation

## v0.1.0 (2025-01-17)

### Feat

- **list-repos**: improved appearance of table output
- added command to init repo and added additional metadata to classes
- added cli commands for borg create archive, borg prune, and borg compact

### Fix

- list repos command no longer errors out due to the presence of remote repos in the response

### Refactor

- **list-repos**: added additional columns with last sync time to table output and moved logic into orchestrator
- 'daily-backup' command now creates archive, runs prune, and runs compact
