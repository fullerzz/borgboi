## v1.26.0 (2026-04-04)

### 🚀 Features

- **backup**: Add `backup diff` command to compare archives (#235) ([70a1e11](https://github.com/fullerzz/borgboi/commit/70a1e11edc3a1f769c3262c7041957707a78644f))


## v1.25.1 (2026-04-02)

### 🐛 Bug Fixes

- **tui**: Wire up backup shortcut on repo info screen (#234) ([f7555ef](https://github.com/fullerzz/borgboi/commit/f7555efc8069d55714e7eb46276e5450d3102983))



### 🧪 Testing

- Enable `pytest-xdist` for default test runs (#233) ([5621ffd](https://github.com/fullerzz/borgboi/commit/5621ffd4d05a2c2ed2f6f9869b6848069d404f32))



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#216) ([b3f5452](https://github.com/fullerzz/borgboi/commit/b3f5452b4a1c373f651153ba9a9c97ad36eeafa1))


## v1.25.0 (2026-04-01)

### 🚀 Features

- **tui**: Add Repo Info Screen to TUI (#232) ([de102e1](https://github.com/fullerzz/borgboi/commit/de102e1333823d5c359d4e04a4428fdc8599ca7b))



### ⚙️ Miscellaneous Tasks

- **deps**: Require Minimum Release Age of 24 hours (#229) ([0da9acb](https://github.com/fullerzz/borgboi/commit/0da9acbb1c08c03744cb20f3e6ff9736afcf574c))

- **renovate**: Add additional presets and enable osv vulnerability PRs (#230) ([cd53fb0](https://github.com/fullerzz/borgboi/commit/cd53fb06291947c1653e9c7d0b22e5e5eaf86c5e))


## v1.24.0 (2026-03-29)

### 🚀 Features

- Add per-repo storage quota updates (#227) ([c33b783](https://github.com/fullerzz/borgboi/commit/c33b783fca7ed03f7e9cb657dea7dbc17dc604b3))


## v1.23.0 (2026-03-29)

### 🚀 Features

- Instrument BorgBoi with App Logging (#224) ([c022f50](https://github.com/fullerzz/borgboi/commit/c022f5021050d7c51baa4d03fd107484a3373ff8))


## v1.22.1 (2026-03-29)

### 🐛 Bug Fixes

- **tui**: Refresh Dashboard after Successful Backup (#222) ([f3e96fa](https://github.com/fullerzz/borgboi/commit/f3e96faa944973d18c987ccc297b114cfa8b7b58))



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (major) (#217) ([60b21cd](https://github.com/fullerzz/borgboi/commit/60b21cdd42d04d6eee1b5955ef74764b5ad01c4f))


## v1.22.0 (2026-03-29)

### 🚀 Features

- **tui**: Add daily backup screen to TUI to allow creating daily backups ([ef1996c](https://github.com/fullerzz/borgboi/commit/ef1996cb8a8521a352c9155eb5634502ce1670a7))

- Add Progress Bar to TUI Screen for Daily Backups (#219) ([110b3d9](https://github.com/fullerzz/borgboi/commit/110b3d99bcbf9ddc152dd6fa68ff68a08a224740))



### 🐛 Bug Fixes

- **tui**: Align archive sparkline labels ([0cd44b7](https://github.com/fullerzz/borgboi/commit/0cd44b745984e2d90090998ff9b48a4069538756))

- Clean up lint typing compatibility ([29b479c](https://github.com/fullerzz/borgboi/commit/29b479c1047a53e1260ae7cbaf4a85fb3af96bd9))



### 💼 Other

- Add Progress Bar to Daily Backup TUI Screen (#220) ([b562097](https://github.com/fullerzz/borgboi/commit/b56209727a37e4151eaf3aa52a1fbfaa365d53e6))



### 🚜 Refactor

- **tui**: Redesign home screen as focused dashboard ([f84ff75](https://github.com/fullerzz/borgboi/commit/f84ff755c3e4a8a2a7357cafd22a0b2eb0ac3c21))



### 📚 Documentation

- Update docs with info on recent TUI changes ([0115795](https://github.com/fullerzz/borgboi/commit/01157951e25374668fa6fe44e80a8b307a019387))



### 🎨 Styling

- **tui**: Right align 'start backup' button in daily backup tui screen ([85335a4](https://github.com/fullerzz/borgboi/commit/85335a498473efc4ec8f55756760d32330d69921))

- **tui**: Add Clear Log button to daily backup screen ([09eef49](https://github.com/fullerzz/borgboi/commit/09eef498063a68bd1b4412a02a7e0032c4378bba))



### 🧪 Testing

- **tui**: Refactor tui tests into new tests/tui submodule ([a020a5d](https://github.com/fullerzz/borgboi/commit/a020a5d1b36eb3d01c37c960233bd2379bcadcd3))



### ⚙️ Miscellaneous Tasks

- Update .gitignore ([631c025](https://github.com/fullerzz/borgboi/commit/631c02569ce820d791b44a232bf5e5caf9b275c7))

- Mypy cleanup ([3dc2109](https://github.com/fullerzz/borgboi/commit/3dc210918aa0fa0f2200179ae413d08707a8f000))

- **justfile**: Add recipe 'dev-tui' to run tui with textual dev mode enabled ([e141952](https://github.com/fullerzz/borgboi/commit/e141952b9f5b7b787dfdfed01a77b3aef48c3b53))

- **tui**: Add docstrings ([36ec732](https://github.com/fullerzz/borgboi/commit/36ec7329b7cac62c92227e7210371c02e3190798))


## v1.21.1 (2026-03-27)

### 🐛 Bug Fixes

- **python-deps**: Lock file maintenance (#214) ([c55857c](https://github.com/fullerzz/borgboi/commit/c55857c2fbf8c3937c2d75796b055e46e4d5dd04))



### ⚙️ Miscellaneous Tasks

- **deps**: Update tflint plugin terraform-linters/tflint-ruleset-aws to v0.46.0 (#200) ([7a3ca46](https://github.com/fullerzz/borgboi/commit/7a3ca46f56d0632bb34e1cfb7f583b4bb7b10c28))

- **deps**: Update terraform aws to v6.37.0 (#215) ([f413970](https://github.com/fullerzz/borgboi/commit/f413970442c3aaa29530db7c02602b7a46ca2bce))



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#210) ([87489c9](https://github.com/fullerzz/borgboi/commit/87489c93e8d748013d029a4e20d8bd465803737f))


## v1.21.0 (2026-03-24)

### 🚀 Features

- Implement S3 sync and delete workflows in the orchestrator (#213) ([1a1137d](https://github.com/fullerzz/borgboi/commit/1a1137dec810efb3914321c69f18143ba0bc9a02))


## v1.20.0 (2026-03-20)

### 🚀 Features

- Add initial Textual TUI scaffold ([a4e2201](https://github.com/fullerzz/borgboi/commit/a4e2201ab2b0c9ac54bf1007ac92a06cceacff31))

- Add TUI config sidebar ([743d332](https://github.com/fullerzz/borgboi/commit/743d332c556ff632178831aaec1bb82c131de3ad))

- Add TUI default excludes viewer ([dca4c69](https://github.com/fullerzz/borgboi/commit/dca4c69c8a3b5ebd6ada6ad3493a71b1446c3348))

- Add tabbed TUI excludes viewer ([47725cf](https://github.com/fullerzz/borgboi/commit/47725cfabfb45d95640514132575f037b9f88caf))



### 🐛 Bug Fixes

- Handle OSError in TUI excludes save to prevent crash ([07bbc33](https://github.com/fullerzz/borgboi/commit/07bbc3397d880b78bbd8f602f46cd3128497d410))

- Add clickable link to borg help docs in excludes TUI screen ([f53aea9](https://github.com/fullerzz/borgboi/commit/f53aea9801bf0b1936668fcd09047d55b5910568))

- Store DataTable reference to prevent crash when excludes screen is open during repo load ([6d7f942](https://github.com/fullerzz/borgboi/commit/6d7f942f6388686c8c71e7c9057d94f7373af508))

- Always display repo size when metadata is available ([4c7fd55](https://github.com/fullerzz/borgboi/commit/4c7fd553a27be9dbccf042a3eee24ec5a0bdaac8))



### 💼 Other

- Merge pull request #211 from fullerzz/textual-tui

Introduce TUI Command ([00860d4](https://github.com/fullerzz/borgboi/commit/00860d4fc3e9b76c4b3c4e1312e11f1edceaa388))

- Merge pull request #212 from fullerzz/dev

TUI Command, Renovate Config, and Doc Updates ([b38490f](https://github.com/fullerzz/borgboi/commit/b38490fad291fa8ee7e974f195c213f5cfa75e1e))



### 📚 Documentation

- Update docs with tui info ([24b2f43](https://github.com/fullerzz/borgboi/commit/24b2f438ed4ae393b4752597c33a80dad443fb55))



### ⚙️ Miscellaneous Tasks

- **renovate**: Fix duplicate renovate PRs for opentofu providers ([c89cab9](https://github.com/fullerzz/borgboi/commit/c89cab9d26eee0212d1dcd56c6ab5f0de1c6939f))

- Clean up unused var ([3d34965](https://github.com/fullerzz/borgboi/commit/3d34965327cd5f46588b0e6a313f9fe09be7c284))

- **git-cliff**: Update changelog config to include commit ids ([853f61f](https://github.com/fullerzz/borgboi/commit/853f61fd7b122b9332b89839f620afc4d536f138))


## v1.19.0 (2026-03-17)

### 🚀 Features

- Implement repo import command to import existing borg repositories (#208)



### 🐛 Bug Fixes

- **python-deps**: Lock file maintenance (#203)

- Preserve passphrase files on import failure



### 💼 Other

- Merge pull request #209 from fullerzz/dev

New Repo Import Command, Doc Updates, and Dependency Updates



### 📚 Documentation

- Correct command output in docs

- Add info on shell completion



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#205)

- Add permissions config to workflow


## v1.18.0 (2026-03-11)

### 🚀 Features

- Migrate to cyclopts



### 🐛 Bug Fixes

- Add support for shell completion with cyclopts

- Wire default s3 client for restore workflows



### 💼 Other

- Merge pull request #204 from fullerzz/cyclopts

feat: Migrate to Cyclopts



### 🚜 Refactor

- Polish cyclopts CLI surface

- **cli**: Improve lazy loading, reduce duplication, and fix minor issues



### 📚 Documentation

- Refresh CLI docs for Cyclopts migration



### ⚡ Performance

- **cli**: Implement lazy loading for cyclopts command registration



### 🧪 Testing

- Expand validator and CLI coverage

- Cover storage backends and s3 client

- Add orchestrator and migration coverage


## v1.17.3 (2026-03-07)

### 🐛 Bug Fixes

- Reuse rich output handler for command rendering

- Preserve legacy output handler fallback



### 💼 Other

- Merge pull request #201 from fullerzz/dev

Refresh README and Improve Output Streaming for Archive Creation



### 🚜 Refactor

- Unify borg backup output streaming



### 📚 Documentation

- Migrate to Zensical for Project Documentation (#197)

- **README.md**: Refresh readme



### ⚙️ Miscellaneous Tasks

- **deps**: Update terraform aws to v6.35.1 (#199)

- Resolve mypy violations in test file



### 🎡 Continuous Integration

- **ci-deps**: Pin dependencies (#196)

- **ci-deps**: Update ci dependencies (#198)


## v1.17.2 (2026-03-04)

### 🐛 Bug Fixes

- Support `bb version` command

- **python-deps**: Lock file maintenance (#193)



### 💼 Other

- Merge pull request #195 from fullerzz/dev

Dependency Upgrades + Support `bb version` Command



### ⚙️ Miscellaneous Tasks

- **deps**: Update terraform aws to ~> 6.0 (#191)



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#190)


## v1.17.1 (2026-02-28)

### 🐛 Bug Fixes

- **output**: Render borg JSON logs as readable rich messages (#189)



### 🎡 Continuous Integration

- **ci-deps**: Update ci dependencies (#186)

- **claude-code-review**: Specify model as claude-opus-4-6


## v1.17.0 (2026-02-25)

### 🚀 Features

- **backup**: Allow daily backups by repository name



### 🐛 Bug Fixes

- **backup**: Reject conflicting or missing --name/--path in daily command



### 💼 Other

- Merge pull request #188 from fullerzz/dev

Support Passing Repo Name for Daily Backup + Inline Snapshot Test Config



### 📚 Documentation

- Remove duplicate s3 stats section from commands docs



### 🧪 Testing

- Add inline-snapshot testing


## v1.16.0 (2026-02-25)

### 🚀 Features

- **backup**: Add `--no-json` Flag for Native Borg Output (#185)


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
