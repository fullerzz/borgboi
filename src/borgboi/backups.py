from pathlib import Path
from pydantic import BaseModel, SecretStr
from pydantic.types import DirectoryPath
from datetime import UTC, datetime
from borgboi import rich_utils
import subprocess as sp


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


class BorgRepo(BaseModel):
    path: DirectoryPath
    passphrase: SecretStr

    def create_archive(self, dir_to_backup: Path) -> None:
        title = _create_archive_title()
        cmd_parts = [
            "borg",
            "create",
            "--progress",
            "--filter",
            "AME",
            "--stats",
            "--show-rc",
            "--compression=zstd,1",
            "--exclude-caches",
            "--exclude",
            "'home/*/.cache/*'",
            f"{self.path.as_posix()}::{title}",
            dir_to_backup.as_posix(),
        ]
        rich_utils.print_cmd_parts(cmd_parts)
        console = rich_utils.get_console()

        proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)

        with console.status("[bold blue]Creating new archive[/]", spinner="pong"):
            while proc.stdout.readable():  # type: ignore
                line = proc.stdout.readline()  # type: ignore
                print(line.decode("utf-8"), end="")
                if not line:
                    break

        # stdout no longer readable so wait for return code
        returncode = proc.wait()
        if returncode != 0 and returncode != 1:
            console.print(
                f"[bold red]Error creating archive. Return code: {proc.returncode}[/]"
            )
            raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd_parts)

        # result = sp.run(cmd_parts, capture_output=True, text=True)
        # print_create_archive_output(stdout=result.stdout, stderr=result.stderr)

        # if result.returncode != 0 and result.returncode != 1:
        #     raise sp.CalledProcessError(
        #         returncode=result.returncode, cmd=result.args, output=result.stdout
        #     )

    def prune(
        self, keep_daily: int = 7, keep_weekly: int = 3, keep_monthly: int = 2
    ) -> None:
        cmd_parts = [
            "borg",
            "prune",
            "--list",
            f"--keep-daily={keep_daily}",
            f"--keep-weekly={keep_weekly}",
            f"--keep-monthly={keep_monthly}",
            self.path.as_posix(),
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Pruning old backups[/]",
            success_message="Pruning completed successfully",
            error_message="Error pruning backups",
            spinner="pong",
        )

    def compact(self) -> None:
        cmd_parts = [
            "borg",
            "compact",
            "--progress",
            self.path.as_posix(),
        ]
        rich_utils.print_cmd_parts(cmd_parts)

        result = sp.run(cmd_parts, capture_output=True, text=True)
        rich_utils.print_create_archive_output(
            stdout=result.stdout, stderr=result.stderr
        )

        if result.returncode != 0 and result.returncode != 1:
            raise sp.CalledProcessError(
                returncode=result.returncode, cmd=result.args, output=result.stdout
            )
