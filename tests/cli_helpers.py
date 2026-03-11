from collections.abc import Sequence
from typing import Any


def invoke_cli(command: Any, args: Sequence[str]) -> int:
    try:
        command(list(args), result_action="return_value")
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 1
    return 0
