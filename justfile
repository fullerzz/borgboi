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
    uv run dmypy check src/borgboi

# run ty type checker
ty:
    uv run ty check

# run tofu validate
tofu-validate:
    cd terraform && tofu validate

# run tflint
tflint:
    cd terraform && tflint --init
    tflint --recursive --color

# run mkdocs local server
serve-docs:
    uv run mkdocs serve

# generate unreleased changelog with git-cliff
changelog-unreleased:
    uv run git-cliff --unreleased -c cliff.toml --github-repo fullerzz/borgboi -o PREVIEW_CHANGELOG.md
    @echo "Unreleased changelog written to PREVIEW_CHANGELOG.md"

# validate renovate config
validate-renovate:
    bunx --yes --package renovate -- renovate-config-validator
