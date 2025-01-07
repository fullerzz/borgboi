from os import environ
import sys
import boto3
import subprocess as sp
from borgboi.rich_utils import print_cmd_parts, get_console
from rich.live import Live
from rich.text import Text

from borgboi.backups import BorgRepo


class S3Client:
    def __init__(self, bucket_name: str) -> None:
        self.bucket_name = bucket_name
        self.s3 = boto3.client("s3")

    def list_objects(self, prefix: str) -> None:
        pass


def sync_repo(repo: BorgRepo) -> None:
    # s3_client = S3Client(bucket_name=environ["BORG_S3_BUCKET"])
    sync_source = repo.path.as_posix()
    s3_destination_uri = f"s3://{environ["BORG_S3_BUCKET"]}/home"
    cmd_parts = [
        "aws",
        "s3",
        "sync",
        sync_source,
        s3_destination_uri,
    ]
    print_cmd_parts(cmd_parts)

    # result = sp.run(cmd_parts, capture_output=True, text=True)

    # proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)
    # while proc.stdout.readable():  # type: ignore
    #     line = proc.stdout.readline()  # type: ignore
    #     print(line.decode("utf-8"), end="")
    console = get_console()
    with console.status(
        "[bold green]Syncing with S3 Bucket[/]", spinner="arrow", refresh_per_second=5
    ):
        # result = sp.run(cmd_parts, stdout=sys.stdout, stderr=sys.stderr)
        proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)
        while proc.stdout.readable():  # type: ignore
            line = proc.stdout.readline()  # type: ignore
            print(line.decode("utf-8"), end="")

            if not line:
                break

    # with Live(
    #     Text("Syncing with S3 Bucket...\n", style="bold green"),
    #     console=get_console(),
    #     refresh_per_second=2,
    #     transient=True,
    #     redirect_stdout=False,
    #     redirect_stderr=False,
    # ):
    #     result = sp.run(cmd_parts, stdout=sys.stdout, stderr=sys.stderr)

    # if result.returncode != 0 and result.returncode != 1:
    #     raise sp.CalledProcessError(
    #         returncode=result.returncode, cmd=result.args, output=result.stdout
    #     )
