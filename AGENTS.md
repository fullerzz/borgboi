# Repository Guidelines

## Project Structure & Module Organization
- `src/borgboi/` is the primary Python package. Key areas include `cli/` (CLI commands), `clients/` (AWS/Borg clients), `core/` (domain logic), and `storage/` (persistence/backups).
- `tests/` contains the pytest suite; shared fixtures live in `tests/conftest.py`, and test data is under `tests/data/`.
- `docs/` holds the MkDocs content with configuration in `mkdocs.yml`.
- `terraform/` contains infrastructure definitions (OpenTofu/Terraform).
- `borgopher/` is a separate Go subproject with its own docs and tooling; only touch it when explicitly working on the Go code.

## Build, Test, and Development Commands
Most tasks are exposed via `just` (run `just --list` to see recipes):

```bash
just test         # pytest suite (cleans private/ restore dir)
just test-cov     # coverage report in htmlcov/
just lint         # mypy + ty + ruff + tofu validate + tflint
just fmt          # ruff format + tofu fmt
just ruff         # ruff check --fix + ruff format
just serve-docs   # mkdocs live server
```

To run the CLI locally with dependencies managed by uv:

```bash
uv run borgboi --help
uv run bb daily-backup /path/to/repo
```

## Coding Style & Naming Conventions
- Python 3.12+ with 4-space indentation and a 120-character line length.
- Format and lint with Ruff (`ruff format`, `ruff check --fix`); double quotes are the standard.
- Types are required in most code paths (mypy is configured with `disallow_untyped_defs`).
- Tests use `*_test.py` file names (for example, `tests/config_test.py`).

## Testing Guidelines
- Pytest is the default framework; networking is disabled by default via pytest-socket.
- Coverage is collected automatically (see `pyproject.toml` pytest options). Use `just test-cov` for HTML output in `htmlcov/`.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), optionally with scopes (for example, `feat(config): ...`).
- Keep PRs focused: include a short description, list tests run, and update docs or `CHANGELOG.md` when behavior changes.

## Security & Configuration Tips
- User configuration lives in `~/.borgboi/config.yaml` or `BORGBOI_*` environment variables; never commit secrets or local paths.
- Infrastructure changes in `terraform/` should be validated with `just lint` before review.
