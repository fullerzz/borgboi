from os import environ
import boto3
import subprocess as sp
from borgboi.rich_utils import print_cmd_parts, get_console, print_successful_s3_sync

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

    console = get_console()
    proc = sp.Popen(cmd_parts, stdout=sp.PIPE, stderr=sp.PIPE)

    with console.status(
        "[bold green]Syncing with S3 Bucket[/]", spinner="arrow", refresh_per_second=5
    ):
        while proc.stdout.readable():  # type: ignore
            line = proc.stdout.readline()  # type: ignore
            # TODO: Test out changing next line to console.print(...)
            print(line.decode("utf-8"), end="")
            if not line:
                break
    returncode = proc.wait()
    if returncode != 0 and returncode != 1:
        console.print(
            f"[bold red]Error syncing with S3 bucket. Return code: {proc.returncode}[/]"
        )
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd_parts)

    print_successful_s3_sync()
