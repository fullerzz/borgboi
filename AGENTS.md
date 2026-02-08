# AGENTS.md

Guidance for autonomous coding agents working in this repository.
Apply these rules to keep changes aligned with the current architecture, tooling, and quality gates.

## Mission

1. Make minimal, focused changes that preserve existing behavior unless the task says otherwise.
2. Prefer extending existing abstractions over introducing new parallel patterns.
3. Keep code typed, testable, and lint-clean.
4. Do not modify the Go subproject `borgopher/` unless explicitly requested.

## Repository Map

- `src/borgboi/cli/`: Click CLI groups, command wiring, legacy command adapters.
- `src/borgboi/core/`: orchestrator, domain models, output abstraction, custom error hierarchy.
- `src/borgboi/clients/`: Borg and AWS client adapters.
- `src/borgboi/storage/`: storage interface + DynamoDB/SQLite implementations.
- `src/borgboi/config.py`: Pydantic settings, YAML loading, env override behavior.
- `tests/`: pytest suites and shared fixtures (`tests/conftest.py`).
- `docs/` + `mkdocs.yml`: docs site.
- `terraform/`: OpenTofu/Terraform config and infra checks.

## Search Guidance

- Use `ast-grep` for searching and matching source code patterns (AST-aware queries).
- Use `ripgrep` (`rg`) for other text search (docs, configs, logs, and general regex/literal grep).

## Build / Lint / Test Commands

Preferred entry points:

```bash
just --list
just test
just test-cov
just lint
just ruff
just fmt
just serve-docs
```

Direct commands (faster for focused loops):

```bash
uv run pytest -vv --capture=tee-sys --diff-symbols
uv run pytest --cov=src/borgboi --cov-report=term --cov-report=html
uv run ruff check --fix .
uv run ruff format .
uv run dmypy check src/borgboi
uv run ty check
```

Infra commands:

```bash
cd terraform && tofu validate
cd terraform && tofu fmt -recursive
tflint --recursive --color
```

## Running a Single Test (Important)

Use `uv run pytest ...` directly for targeted tests.

```bash
# single file
uv run pytest tests/config_test.py -vv --capture=tee-sys --diff-symbols

# single test function
uv run pytest tests/config_test.py::test_get_config -vv --capture=tee-sys --diff-symbols

# keyword filtering
uv run pytest -k "config and not cli" -vv --capture=tee-sys --diff-symbols
```

Helpful focused options:

```bash
uv run pytest -x tests/orchestrator_test.py   # stop on first failure
uv run pytest --lf                             # rerun last failures
uv run pytest -l tests/s3_test.py             # show local vars in tracebacks
```

Notes: `pyproject.toml` adds default pytest opts (coverage + socket restrictions),
network is blocked by default (`--disable-socket`), and `just test` removes `private/` after completion.

## Code Style Guidelines

### Formatting and Imports

- 4-space indentation, 120-char line length.
- Prefer double quotes.
- Keep imports sorted and grouped (Ruff import rules).
- Remove unused imports/variables and dead code.
- Run `uv run ruff check --fix .` and `uv run ruff format .` after edits.

### Types

- Add annotations for all new functions/methods.
- Keep signatures mypy-clean under strict settings (`disallow_untyped_defs = true`).
- Prefer modern syntax: `X | None`, `list[str]`, `dict[str, Any]`.
- Use Protocol/ABC when extending pluggable interfaces.
- Use `typing.override` when overriding inherited methods (existing pattern).

### Naming and Structure

- Modules/functions/vars: `snake_case`.
- Classes/exceptions: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Follow the local style of the file you edit; avoid broad refactors unless requested.
- Keep business logic in `core/` and adapters in `clients/`/`storage/`.

### Error Handling

- Prefer domain exceptions in `src/borgboi/core/errors.py`.
- Use `ValidationError` for invalid user/input/state.
- Use `StorageError` for persistence/backend failures.
- Use `BorgError` for Borg command failures.
- Use `ConfigurationError` for config issues.
- Provide actionable messages with operation context.
- Avoid broad `except Exception` unless there is explicit fallback behavior, and preserve cause context.

### Output, Logging, and IO

- Route user-facing output through output handlers in `src/borgboi/core/output.py`.
- Avoid `print()` in production code (Ruff `T20` rule is enabled).
- Prefer `pathlib.Path` for filesystem operations.
- Use `yaml.safe_load` / `yaml.safe_dump` for YAML.

### Config and Environment

- `BORGBOI_*` env vars override config values.
- Nested config env keys use `__` (double underscore).
- Respect home resolution behavior (`BORGBOI_HOME`, `SUDO_USER`, then `Path.home()`).

## Testing Conventions

- Use pytest fixtures and parametrization; reuse `tests/conftest.py` fixtures.
- Keep tests deterministic and offline-friendly.
- Use `moto` for AWS interactions; do not use real AWS in tests.
- Add regression tests for bug fixes.
- Prefer colocated tests by feature area rather than large generic test files.

## Commit and PR Expectations

- Use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Keep PRs focused; include verification commands and update docs when behavior changes.

## Safety and Secrets

- Never commit secrets, tokens, credentials, or machine-local private paths.
- Treat `~/.borgboi/config.yaml` as user-local runtime state, not repo state.
- Be cautious with deletion/destructive backup flows; preserve dry-run support.

## Cursor / Copilot Rules Status

No extra editor-agent instruction files were found when this file was updated:

- `.cursorrules`: not present
- `.cursor/rules/`: not present
- `.github/copilot-instructions.md`: not present

If these files are added later, merge their rules into this document and treat them as higher-priority repository guidance.
