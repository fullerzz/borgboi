from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.cli import exclusions as exclusions_module


@pytest.fixture
def exclusions_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(borgboi_dir=tmp_path, excludes_filename="excludes.txt")


@pytest.fixture
def repo_info() -> SimpleNamespace:
    return SimpleNamespace(name="repo-one", path="/repo/one")


def test_exclusions_create_fetches_repo_by_path_and_creates_file(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excludes_path = exclusions_config.borgboi_dir / f"{repo_info.name}_{exclusions_config.excludes_filename}"
    orchestrator = SimpleNamespace(
        get_repo=Mock(return_value=repo_info),
        create_exclusions=Mock(return_value=excludes_path),
    )
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    console_print = Mock()

    monkeypatch.setattr(exclusions_module.console, "print", console_print)

    exclusions_module.exclusions_create(
        path=repo_info.path,
        source="tests/data/excludes.txt",
        ctx=cast(Any, ctx),
    )

    orchestrator.get_repo.assert_called_once_with(path=repo_info.path)
    orchestrator.create_exclusions.assert_called_once_with(repo_info, "tests/data/excludes.txt")
    console_print.assert_called_once_with(f"Exclusions file created at [bold cyan]{excludes_path}[/]")


def test_exclusions_create_routes_errors_to_print_error_and_exit(
    exclusions_config: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = SimpleNamespace(
        orchestrator=SimpleNamespace(get_repo=Mock(side_effect=RuntimeError("repo missing"))),
        config=exclusions_config,
    )

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(exclusions_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="repo missing"):
        exclusions_module.exclusions_create(path="/repo/missing", source="source.txt", ctx=cast(Any, ctx))


def test_exclusions_show_prefers_repo_specific_excludes_file(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo_info))
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    calls: list[str] = []

    def render(path: str, lines_to_highlight: set[int] | None = None) -> None:
        del lines_to_highlight
        calls.append(path)

    monkeypatch.setattr("borgboi.rich_utils.render_excludes_file", render)

    exclusions_module.exclusions_show(name=repo_info.name, ctx=cast(Any, ctx))

    assert calls == [
        (exclusions_config.borgboi_dir / f"{repo_info.name}_{exclusions_config.excludes_filename}").as_posix()
    ]


def test_exclusions_show_falls_back_to_shared_excludes_file(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo_info))
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    calls: list[str] = []
    repo_specific = exclusions_config.borgboi_dir / f"{repo_info.name}_{exclusions_config.excludes_filename}"
    shared = exclusions_config.borgboi_dir / exclusions_config.excludes_filename

    def render(path: str, lines_to_highlight: set[int] | None = None) -> None:
        del lines_to_highlight
        calls.append(path)
        if path == repo_specific.as_posix():
            raise FileNotFoundError(path)

    monkeypatch.setattr("borgboi.rich_utils.render_excludes_file", render)

    exclusions_module.exclusions_show(name=repo_info.name, ctx=cast(Any, ctx))

    assert calls == [repo_specific.as_posix(), shared.as_posix()]


def test_exclusions_show_prints_warning_when_no_excludes_file_exists(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo_info))
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    console_print = Mock()

    monkeypatch.setattr(
        "borgboi.rich_utils.render_excludes_file",
        lambda path, lines_to_highlight=None: (_ for _ in ()).throw(FileNotFoundError(path)),
    )
    monkeypatch.setattr(exclusions_module.console, "print", console_print)

    exclusions_module.exclusions_show(name=repo_info.name, ctx=cast(Any, ctx))

    console_print.assert_called_once_with(f"[bold yellow]No exclusions file found for repository {repo_info.name}[/]")


def test_exclusions_show_routes_unexpected_errors_to_print_error_and_exit(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo_info))
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr("borgboi.rich_utils.render_excludes_file", Mock(side_effect=ValueError("bad render")))
    monkeypatch.setattr(exclusions_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="bad render"):
        exclusions_module.exclusions_show(name=repo_info.name, ctx=cast(Any, ctx))


def test_exclusions_add_calls_add_exclusion_and_highlights_last_line(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excludes_path = exclusions_config.borgboi_dir / f"{repo_info.name}_{exclusions_config.excludes_filename}"
    excludes_path.write_text("*.tmp\n.cache/\n", encoding="utf-8")

    def add_exclusion(_: SimpleNamespace, pattern: str) -> None:
        with excludes_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(pattern + "\n")

    orchestrator = SimpleNamespace(get_repo=Mock(return_value=repo_info), add_exclusion=Mock(side_effect=add_exclusion))
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    render = Mock()

    monkeypatch.setattr("borgboi.rich_utils.render_excludes_file", render)

    exclusions_module.exclusions_add(name=repo_info.name, pattern="logs/", ctx=cast(Any, ctx))

    orchestrator.add_exclusion.assert_called_once_with(repo_info, "logs/")
    render.assert_called_once_with(excludes_path.as_posix(), lines_to_highlight={3})


def test_exclusions_add_routes_errors_to_print_error_and_exit(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(
        get_repo=Mock(return_value=repo_info),
        add_exclusion=Mock(side_effect=RuntimeError("invalid pattern")),
    )
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(exclusions_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="invalid pattern"):
        exclusions_module.exclusions_add(name=repo_info.name, pattern="*", ctx=cast(Any, ctx))


def test_exclusions_remove_calls_remove_exclusion_and_renders_updated_file(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excludes_path = exclusions_config.borgboi_dir / f"{repo_info.name}_{exclusions_config.excludes_filename}"
    excludes_path.write_text("*.tmp\n.cache/\nlogs/\n", encoding="utf-8")

    def remove_exclusion(_: SimpleNamespace, line: int) -> None:
        lines = excludes_path.read_text(encoding="utf-8").splitlines()
        lines.pop(line - 1)
        excludes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    orchestrator = SimpleNamespace(
        get_repo=Mock(return_value=repo_info),
        remove_exclusion=Mock(side_effect=remove_exclusion),
    )
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)
    render = Mock()

    monkeypatch.setattr("borgboi.rich_utils.render_excludes_file", render)

    exclusions_module.exclusions_remove(name=repo_info.name, line=2, ctx=cast(Any, ctx))

    orchestrator.remove_exclusion.assert_called_once_with(repo_info, 2)
    render.assert_called_once_with(excludes_path.as_posix())


def test_exclusions_remove_routes_errors_to_print_error_and_exit(
    exclusions_config: SimpleNamespace,
    repo_info: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = SimpleNamespace(
        get_repo=Mock(return_value=repo_info),
        remove_exclusion=Mock(side_effect=RuntimeError("missing line")),
    )
    ctx = SimpleNamespace(orchestrator=orchestrator, config=exclusions_config)

    def fail(message: str, *, error: Exception | None = None) -> None:
        raise AssertionError((message, error))

    monkeypatch.setattr(exclusions_module, "print_error_and_exit", fail)

    with pytest.raises(AssertionError, match="missing line"):
        exclusions_module.exclusions_remove(name=repo_info.name, line=9, ctx=cast(Any, ctx))
