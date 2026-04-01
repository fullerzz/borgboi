test_restore_dir := 'private/'

# list recipes
default:
    @just --list

# run pytest test suite
test:
    uv run pytest -vv --capture=tee-sys --diff-symbols
    rm -rf {{ test_restore_dir }}
    @echo {{ BOLD + GREEN }}'✔️ All tests passed!'{{ NORMAL }}

# run pytest test suite with coverage
test-cov:
    uv run pytest --cov=src/borgboi --cov-report=html
    rm -rf {{ test_restore_dir }}
    -open htmlcov/index.html

# run all linters
lint: mypy ty tflint tofu-validate
    uv run ruff check --fix .

# run ruff and tofu formatters
fmt:
    uv run ruff format .
    cd terraform && tofu fmt -recursive

# run ruff linter and formatter
ruff:
    uv run ruff check --fix .
    uv run ruff format .

_start-dmypy:
    -uv run dmypy start

# run mypy type checker
mypy: _start-dmypy
    uv run dmypy check src/ tests/ scripts/

# run ty type checker
ty:
    uv run ty check

# run tofu validate
tofu-validate:
    cd terraform && tofu init -backend=false
    cd terraform && tofu validate

# run tflint
tflint:
    cd terraform && tflint --init
    tflint --recursive --color

# run zensical local server
serve-docs:
    uv run zensical serve

# generate unreleased changelog with git-cliff
changelog-unreleased:
    uv run git-cliff --unreleased -c cliff.toml --github-repo fullerzz/borgboi -o PREVIEW_CHANGELOG.md
    @echo "Unreleased changelog written to PREVIEW_CHANGELOG.md"

# validate renovate config
validate-renovate:
    bunx --yes --package renovate -- renovate-config-validator

# interactively review and approve snapshot changes
snapshot-review *args:
    uv run pytest -n0 --inline-snapshot=review {{ args }}

# fill empty snapshot() placeholders with recorded values
snapshot-create *args:
    uv run pytest -n0 --inline-snapshot=create {{ args }}

# create missing snapshots and update changed values
snapshot-fix *args:
    uv run pytest -n0 --inline-snapshot=create,fix {{ args }}

# trim unused snapshot data (prefer full-suite runs)
snapshot-trim *args:
    uv run pytest -n0 --inline-snapshot=trim {{ args }}

# update snapshot repr formatting without value changes
snapshot-update *args:
    uv run pytest -n0 --inline-snapshot=update {{ args }}

# run the TUI in dev mode to enable connecting to textual console debugger
dev-tui:
    uv run textual run --dev src/borgboi/cli/main.py tui
