## v1.15.1 (2026-02-25)

### 🐛 Bug Fixes

- **python-deps**: Lock file maintenance (#182)



### ⚙️ Miscellaneous Tasks

- **tofu-deps**: Lock file maintenance (#174)



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#184)


## v1.15.0 (2026-02-23)

### 🚀 Features

- **backup**: Render rich archive stats table on Error: Either name or path must be provided output



### 🐛 Bug Fixes

- Remove Chunk Table from Archive Stats Output (#180)



### 💼 Other

- Merge pull request #181 from fullerzz/dev

Output Archive Stats on Successful Backup



### 🚜 Refactor

- Centralize archive name generation



### 🎡 Continuous Integration

- **bump.yml**: Update release workflow to include updated uv.lock file (#179)

- **test.yml**: Bump UV_VERSION env var to 0.10.4


## v1.14.4 (2026-02-21)

### 🐛 Bug Fixes

- **s3**: Add lifecycle rules to logging bucket

- Encrypt inventory report with ss3_s3 (#177)



### 💼 Other

- Merge pull request #178 from fullerzz/dev

S3 Lifecycle Rules + Inventory Report Config



### 📚 Documentation

- Add graphiti memory mcp usage


## v1.14.3 (2026-02-20)

### 🐛 Bug Fixes

- Add s3 lifecycle rule for stale inventory reports (#176)



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#172)


## v1.14.2 (2026-02-14)

### 🐛 Bug Fixes

- **deps**: Lock file maintenance (#164)


## v1.14.1 (2026-02-14)

### 🐛 Bug Fixes

- **s3**: Improve error message for missing permissions when running s3 stats (#173)



### 🎡 Continuous Integration

- **ci-deps**: Update anthropics/claude-code-action digest to c22f7c3 (#171)


## v1.14.0 (2026-02-12)

### 🚀 Features

- S3 metadata transitions (#170)


## v1.13.1 (2026-02-12)

### 🐛 Bug Fixes

- Fallback to default excludes.txt file if repo-specific one isn't present (#169)


## v1.13.0 (2026-02-11)

### 🚀 Features

- **s3**: Add bucket stats command with CloudWatch breakdown (#168)



### ⚙️ Miscellaneous Tasks

- Add precommit hooks with prek

- Remove unreleased section from CHANGELOG

- **renovate**: Group Renovate Dependency Updates and Add Config Validator (#166)

- **deps**: Update python docker tag to v3.14 (#129)



### 🎡 Continuous Integration

- Migrate to git-cliff for changelog generation

- **changelog-preview**: Update existing comment if present

- **ci-deps**: Update ci dependencies (#167)


## v1.12.0 (2026-02-10)

### 🚀 Features

- SQLite DB for Local Storage (#160)



### 💼 Other

- Version 1.11.2 → 1.12.0



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance (#152)



### 🎡 Continuous Integration

- Add CI Workflow for `uv` Lockfile Change Report (#159)

- Add Claude Code GitHub Workflow (#161)

- Add additional inputs to claude-pr-review workflow (#163)


## v1.11.2 (2026-02-06)

### 🐛 Bug Fixes

- S3 Sync Now Uses Correct S3 Bucket (#157)



### 💼 Other

- Version 1.11.1 → 1.11.2



### 📚 Documentation

- Update docs with latest changes



### ⚙️ Miscellaneous Tasks

- Resolve mypy linter errors

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.45.0 (#119)

- **deps**: Update dependency astral-sh/uv to v0.9.27 (#142)


## v1.11.1 (2026-01-25)

### 🐛 Bug Fixes

- Normalize OS Hostname before Validation (#150)



### 💼 Other

- Version 1.11.0 → 1.11.1



### ⚙️ Miscellaneous Tasks

- **ci**: Add python 3.14 to matrix (#149)


## v1.11.0 (2026-01-25)

### 🚀 Features

- **config**: Add 'borgboi config show' command (#147)



### 💼 Other

- Version 1.10.0 → 1.11.0


## v1.10.0 (2026-01-21)

### 🚀 Features

- Refactor Database Schema and Core Architecture (#144)



### 💼 Other

- Version 1.9.1 → 1.10.0



### ⚙️ Miscellaneous Tasks

- **deps**: Update actions and python deps (#140)

- **deps**: Update softprops/action-gh-release digest to a06a81a (#126)

- **deps**: Update actions/cache action to v5 (#138)

- **deps**: Update actions/checkout action to v6 (#139)

- **deps**: Lock file maintenance (#141)



### 🎡 Continuous Integration

- **bump.yml**: Refactor job to use built in GITHUB_TOKEN variable (#145)


## v1.9.1 (2025-11-09)

### 🐛 Bug Fixes

- **s3**: Add s3 lifecycle rule to abort multipart uploads after 2 days (#135)



### 💼 Other

- Version 1.9.0 → 1.9.1


## v1.9.0 (2025-11-07)

### 🚀 Features

- **tf**: Create 2 New DynamoDB Tables (#133)



### 💼 Other

- Merge pull request #120 from fullerzz/renovate/astral-sh-uv-0.x

- Version 1.8.1 → 1.9.0



### ⚙️ Miscellaneous Tasks

- Test and Config Updates (#113)

- **deps**: Lock file maintenance

- **deps**: Update astral-sh/setup-uv digest to 7edac99

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.41.0

- **deps**: Update astral-sh/setup-uv digest to e92bafb

- **deps**: Update dependency astral-sh/uv to v0.8.8

- **deps**: Update dependency astral-sh/uv to v0.8.15 (#123)

- **deps**: Update astral-sh/setup-uv digest to 557e51d (#124)

- **deps**: Update actions/checkout action to v5 (#122)

- **deps**: Lock file maintenance (#114)

- **deps**: Lock file maintenance (#131)


## v1.8.1 (2025-06-28)

### 🐛 Bug Fixes

- **dynamodb**: Specify throughput config for table and GSI



### 💼 Other

- Doc Updates (#110)

* docs: update documentation with offline mode info and more

* chore(uv.lock): updated lockfile

- Version 1.8.0 → 1.8.1



### 🧪 Testing

- Update pytest config to ignore warning from boto3 lib



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance

- **renovate**: Update renovate config with labels and reviewers info

- **deps**: Update astral-sh/setup-uv digest to bd01e18

- **deps**: Update softprops/action-gh-release digest to 72f2c25


## v1.8.0 (2025-06-25)

### 🚀 Features

- **terraform**: Update AWS provider version to v6 (#108)



### 💼 Other

- Version 1.7.0 → 1.8.0



### 🧪 Testing

- Updated tests to cleanup borg security dir



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance

- Update type ignore comment


## v1.7.0 (2025-06-07)

### 🚀 Features

- Implement Offline Mode (#101)



### 💼 Other

- Version 1.6.1 → 1.7.0


## v1.6.1 (2025-05-31)

### 🐛 Bug Fixes

- **tofu**: Enable Intelligent Tiering on S3 Logs Bucket (#100)



### 💼 Other

- Version 1.6.0 → 1.6.1


## v1.6.0 (2025-05-31)

### 🚀 Features

- **tofu**: Enable bucket key encryption for s3 logs bucket



### 💼 Other

- Version 1.5.1 → 1.6.0



### ⚙️ Miscellaneous Tasks

- **deps**: Pin dependencies

- **deps**: Update actions/checkout action to v4


## v1.5.1 (2025-05-31)

### 🐛 Bug Fixes

- **cli**: Update type of --repo-name option from click.Path to str



### 💼 Other

- WIP - basic implementation for list-archives command

- WIP - add archive age to output

- Version 1.5.0 → 1.5.1



### ⚙️ Miscellaneous Tasks

- **deps**: Update astral-sh/setup-uv digest to f0ec1fc

- **deps**: Lock file maintenance

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.40.0

- Implement archive path shortening util

- Add archive id to output

- Update UTC tz ref

- **list-archive-contents**: Add option to output archive contents to file



### 🎡 Continuous Integration

- Add gitleaks github action

- Limit job permissions

- Bump uv version in test workflow to 0.7.9


## v1.5.0 (2025-05-31)

### 🚀 Features

- **s3**: Default to using INTELLIGENT_TIERING for S3 storage class



### 🐛 Bug Fixes

- **restore-repo**: Add --force flag to restore even if repo is detected locally



### 💼 Other

- Version 1.4.0 → 1.5.0



### ⚙️ Miscellaneous Tasks

- **deps**: Update actions/setup-python digest to a26af69


## v1.4.0 (2025-05-10)

### 🚀 Features

- New Command to Restore BorgBoi Repo from S3 (#86)



### 💼 Other

- Version 1.3.0 → 1.4.0



### ⚙️ Miscellaneous Tasks

- **deps**: Update astral-sh/setup-uv action to v6

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.39.0

- **deps**: Update softprops/action-gh-release digest to da05d55

- **deps**: Lock file maintenance


## v1.3.0 (2025-05-04)

### 🚀 Features

- **tf**: Add s3 intelligent tiering config to bucket



### 💼 Other

- Version 1.2.0 → 1.3.0



### ⚙️ Miscellaneous Tasks

- **deps**: Bump Various Dependencies (#74)


## v1.2.0 (2025-03-15)

### 🚀 Features

- Integrated with catppuccin pkg for better color consistency



### 💼 Other

- Version 1.1.0 → 1.2.0



### 🎡 Continuous Integration

- **test.yml**: Fix issue where uv venv used version present in .python-version everytime

- **test.yml**: Recreate .python-version during job execution


## v1.1.0 (2025-03-15)

### 🚀 Features

- **excludes**: Add commands to append line and remove line from excludes file



### 🐛 Bug Fixes

- **validator**: Line number is valid if it equals len of lines as it's 1-indexed



### 💼 Other

- Version 1.0.3 → 1.1.0



### 🚜 Refactor

- **excludes-ops**: Improved docstrings and added validation in validator



### 📚 Documentation

- **wiki**: Updated commands page to include new exclusion commands



### 🧪 Testing

- **orchestrator**: Add tests for getting excludes file and appending new line to it

- **orchestrator**: Add test for removing line from excludes file



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance

- Corrected docstring description of append-excludes command

- Fix typos


## v1.0.3 (2025-03-07)

### 🐛 Bug Fixes

- **delete-repo**: No longer raise FileNotFoundError if exludes list not found on repo deletion



### 💼 Other

- Version 1.0.2 → 1.0.3



### 📚 Documentation

- **README**: Add logo



### 🎡 Continuous Integration

- Bump uv version in workflows to v0.6.5


## v1.0.2 (2025-03-07)

### 🐛 Bug Fixes

- **wiki**: Run docs.yml actions job with lfs checkout enabled



### 💼 Other

- Version 1.0.1 → 1.0.2



### 📚 Documentation

- **wiki**: Add favicon



### 🎨 Styling

- **wiki**: Rm whitespace



### ⚙️ Miscellaneous Tasks

- **deps**: Update astral-sh/setup-uv action to v5

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.38.0

- **deps**: Lock file maintenance

- **deps**: Update softprops/action-gh-release action to v2

- **deps**: Update actions/cache digest to d4323d4

- Add *.DS_Store to .gitignore



### 🎡 Continuous Integration

- **docs.yml**: Update branch trigger


## v1.0.1 (2025-03-05)

### 🐛 Bug Fixes

- **list-repos**: Removed incorrect docstring and added accurate description in new docstring

- **daily-backup**: Fix incorrect docstring description regarding target of archive backup



### 💼 Other

- **cz**: Update commitizen tag_format config

- Version 1.0.0 → 1.0.1



### 📚 Documentation

- **wiki**: Add mkdocs-material dep and generate starter site

- **wiki**: Updated index and created getting started page

- **wiki**: Update 'Getting Started' page and add demo gif

- **wiki**: List commands

- **wiki**: Document borgboi commands



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance

- **wiki**: Fix typo

- **wiki**: Add pymdownx.blocks.caption to markdown extensions



### 🎡 Continuous Integration

- Fix tag name by prefixing with 'v'

- **docs.yml**: Add workflow to publish mkdocs wiki to GH pages


## v1.0.0 (2025-03-01)

### 🚀 Features

- **prune**: Implemented prune command in new module

- **compact**: Implemented compact cmd in new module

- **repo-key**: Add export-repo-key cmd in new module

- **extract**: Add extract cmd in new module

- **delete**: Added delete repo and delete archive commands to new module

- Add ability to disable --log-json from being passed as option to borg

- Updated daily backup to use new borg client and print normal output

- **repo-info**: [BREAKING] Default pretty print --pp flag to true



### 🐛 Bug Fixes

- Converted computed fields with size information to return strings instead of floats

- Iterate over iterable

- Handle repo metadata being None/missing

- Remove rich_utils.confirm_deletion call from borg client

- **delete-archive**: Render cmd output with log_json=False



### 💼 Other

- Add dev dependency vulture to eliminate dead code

- Version 0.12.1 → 1.0.0



### 🚜 Refactor

- **log**: Moved log parsing into validator

- Refactor dynamodb

- Removed original backups.py file

- **log-parsing**: Added new function to take in iterable and yield log model line by line

- Refactor command output rendering and moved most logic into rich_utils

- **list-repos**: Move table output logic for repos into rich_utils



### 📚 Documentation

- Added docsstrings



### 🎨 Styling

- **rich_utils**: Remove extra char



### 🧪 Testing

- Temporarily remove stdout assertion and fixed monkeypatch path

- Try outputting logs

- Output archive creation logs



### ⚙️ Miscellaneous Tasks

- **deps**: Lock file maintenance

- Created new clients module

- Updated new client module to yield json logs and its being read correctly by orchestrator

- Updated type of sizes from float to str

- Including cmd output when raising sp.CalledProcessError

- Run tests with max verbosity

- Print cmd output on error

- Updated monkeypatch target

- Removed monkeypatch

- Check different restore path

- Remove new assertion

- Remove debug options

- WIP testing out ways to render json logs

- WIP improved demo output colors

- Remove demo command

- Pass output and stderr params to error and remove todo comment

- Add FIXME comment to resolve circular import issue in rich_utils

- Update README todos and remove comment



### 🎡 Continuous Integration

- Update commitizen config to create v1 on major version and create release

- **bump**: Update changelog_increment_filename to body.md


## v0.12.1 (2025-02-20)

### 🐛 Bug Fixes

- **orchestrator**: Repo's exclusions file is now removed if the repo is deleted



### 💼 Other

- Version 0.12.0 → 0.12.1



### 🚜 Refactor

- **orchestrator**: Add function to get path of a repo's excludes file



### 🧪 Testing

- Update borg_repo fixture to create repo excludes file by default and clean it up


## v0.12.0 (2025-02-16)

### 🚀 Features

- **list-archives**: Add command to list archive names present in borg repo



### 💼 Other

- Version 0.11.0 → 0.12.0


## v0.11.0 (2025-02-16)

### 🚀 Features

- **delete-archive**: Add support for deleting individual archives from borg repositories

- **delete-archive**: Add CLI command to delete individual archives from within borg repo



### 🐛 Bug Fixes

- **delete-repo**: Repo is now delete from DynamoDB table after successful local removal

- **delete-op**: Deletion confirmation prompt now accepts repo name and archive name as params

- **delete-op**: Run compact command on repo after deletion command

- **delete-repo**: Don't call 'compact' command if entire repo is deleted



### 💼 Other

- Add renovate.json

- **tf**: Updated aws provider to use hashicorp namespace

- **renovate**: Use config:best-practices and enable lock file maintenance

- Version 0.10.0 → 0.11.0



### 🎨 Styling

- **justfile**: Output success message if tests pass



### 🧪 Testing

- Add test file for the Click cli application and added basic tests so far

- **create-borg-repo**: Simplified stdout assertion

- **delete-repo**: Separated output assertion into 2 assertions

- **delete-archive**: Add test for deleting archive



### ⚙️ Miscellaneous Tasks

- **deps**: Pin dependencies

- **deps**: Lock file maintenance



### 🎡 Continuous Integration

- Add rust-just as python dep, upgrade uv to v0.6.0 in CI, and invoke pytest with 'just test' command


## v0.10.0 (2025-02-15)

### 🚀 Features

- Add command to delete borg repo and preview deletion with dry-run



### 💼 Other

- **uv**: Upgrade python deps

- **tests**: Add tmp dirs to .gitignore and add cov target to pytest config

- Version 0.9.0 → 0.10.0



### 🚜 Refactor

- Raise ValueError instead of exit(0)



### 🧪 Testing

- Add pytest-cov to generate test coverage reports


## v0.9.0 (2025-02-09)

### 🚀 Features

- [BREAKING] Add new field 'os_platform' to BorgRepo



### 🐛 Bug Fixes

- [BREAKING] Refactor validation of repo and backup target paths to resolve issue with remote repos



### 💼 Other

- Ease python version constraint to only specify 3.13

- Version 0.8.0 → 0.9.0



### 🎨 Styling

- Update spinner icon for s3 sync



### 🎡 Continuous Integration

- Bump uv version in pipeline to 0.5.29


## v0.8.0 (2025-02-01)

### 🚀 Features

- [BREAKING] Add ability to create exclusion list for each borg repo



### 🐛 Bug Fixes

- **orchestrator**: The borgboi dir will be created if it doesn't exist before attempting to create exlusions file



### 💼 Other

- Version 0.7.0 → 0.8.0



### 🧪 Testing

- Add sample excludes.txt for usage with tests

- Add test for creating exclusions list


## v0.7.0 (2025-01-31)

### 🚀 Features

- **list-repos**: Add deduplicated repo size to output



### 💼 Other

- **uv**: Upgrade python deps

- Version 0.6.1 → 0.7.0



### 🚜 Refactor

- **dynamodb**: Add botocore config to set retry behavior mode to 'standard'



### 🧪 Testing

- Update pytest config to ignore botocore datetime.utcnow deprecationwarning


## v0.6.1 (2025-01-26)

### 💼 Other

- Version 0.6.0 → 0.6.1



### 🚜 Refactor

- **repo-info**: Improved pretty print output for the borgboi repo-info command


## v0.6.0 (2025-01-25)

### 🚀 Features

- **repo-info**: Add pretty print flag to repo info command



### 💼 Other

- Version 0.5.0 → 0.6.0


## v0.5.0 (2025-01-25)

### 🚀 Features

- Implement command to extract borg archive



### 💼 Other

- Version 0.4.0 → 0.5.0



### 🎡 Continuous Integration

- Install borgbackup in ci


## v0.4.0 (2025-01-22)

### 🚀 Features

- Improved repo-info command and added data structure to store output

- Now store repo size metadata in dynamodb table



### 💼 Other

- **tofu**: Add additional platform hash

- Version 0.3.0 → 0.4.0



### 🚜 Refactor

- Moved borg repo info models and cmd execution into backups.py



### 📚 Documentation

- **README**: Update to-dos section of readme


## v0.3.0 (2025-01-18)

### 🚀 Features

- Add new command to view borg repo info



### 💼 Other

- Version 0.2.2 → 0.3.0



### 🚜 Refactor

- Move get repo info logic into orchestrator and added validator module


## v0.2.2 (2025-01-18)

### 💼 Other

- Version 0.2.1 → 0.2.2



### 🚜 Refactor

- Renamed dynamo table item field from name to common_name


## v0.2.1 (2025-01-18)

### 🐛 Bug Fixes

- **s3**: Adds s3 prefix of borg repo name before syncing with s3



### 💼 Other

- Version 0.2.0 → 0.2.1


## v0.2.0 (2025-01-18)

### 🚀 Features

- Add cmd to export repo key in addition to automatically exporting repo key upon repo creation



### 💼 Other

- **pytest**: Add pytest-socket plugin and update pytest config to ignore botocore.auth datetime.utcnow() deprecation warning

- Version 0.1.0 → 0.2.0



### 🧪 Testing

- Add initial test for orchestrator module with more to follow

- **dynamodb**: Add test for update_repo functionality

- **orchestrator**: WIP - writing test for lookup repo but still need to add mocked gsi

- Implemented test for repo lookup in orchestrator



### 🎡 Continuous Integration

- Added workflow to run cz bump with commitizen

- Add workflow to run pytest


## v0.1.0 (2025-01-18)

### 🚀 Features

- Added cli commands for borg create archive, borg prune, and borg compact

- Feat: added command to init repo and added additional metadata to classes

BREAKING CHANGE:

- **list-repos**: Improved appearance of table output



### 🐛 Bug Fixes

- List repos command no longer errors out due to the presence of remote repos in the response



### 💼 Other

- Initial commit

- Added click to build cli

- Sync Local Borg Repo with S3 Bucket (#2)

* feat: added terraform code to create s3 bucket for storing backups

* fix(tf): corrected invalid version constraint used for aws provider

* chore(tf): added lockfile for tf providers

* added todo

* style: added .editorconfig file

* feat(tf): add aws resources to create IAM user and policy for accessing S3 bucket

* fix(tf): updated reference to S3 ARN

- Sync Borg Repo with S3 Bucket (#3)

* feat: last step of daily-backup now syncs local borg repo with s3

* feat(s3): aws cli's s3 sync stdout is written to stdout of borgboi now

* wip: using console.status instead of Live

* wip: console.progress def way to go for now

* wip: console.progress is functional

* wip: creating abstraction for running and logging popen with rich output

* removed s3_sync and added functionality to backups and BorgRepo

* TODO: clean up output

* feat: local borg repo is now synced with s3 bucket after new daily archive is created

* style(cli): removed commented console.rule lines

- **uv**: Upgraded python deps with 'uv sync --upgrade'

- Create and Track Borg Repo Metadata with DynamoDB (#5)

* feat: borgboi now has ability to create new borg repositories and track them with a dynamodb table

* refactor: now saves the name of an ENV VAR containing the borg repo's passphrase instead of hashed value of passphrase

* feat: enhance BorgRepo model with name and backup timestamps; update repo creation and listing functionality

WIP: Planning to query the Dynamo table before each run to retrieve the existing BorgRepo data

* feat: as part of the daily backup the existing metadata is retrieved from dynamo and updated post backup completion

* refactor: orchestrator now responsible for adding new repo to dynamo instead of cli

* chore: upgraded deps and removed bcrypt

* fmt(ruff)

- **pyproject.toml**: Add commitizen config



### 🚜 Refactor

- 'daily-backup' command now creates archive, runs prune, and runs compact

- **list-repos**: Added additional columns with last sync time to table output and moved logic into orchestrator



### 📚 Documentation

- Created initial readme with usage examples and pending todo items

- Updated README



### 🎨 Styling

- Beginning of _print_cmd_parts(...) output now orange



### ⚙️ Miscellaneous Tasks

- Updated .gitignore
