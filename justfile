test:
    uv run pytest

lint: mypy tflint tofu-validate
    uv run ruff check --fix .

fmt:
    uv run ruff format .
    cd terraform && tofu fmt -recursive

ruff:
    uv run ruff check --fix .
    uv run ruff format .

start-dmypy:
    -uv run dmypy start

mypy: start-dmypy
    uv run dmypy check src/borgboi

tofu-validate:
    cd terraform && tofu validate

tflint:
    cd terraform && tflint --init
    tflint --recursive --color