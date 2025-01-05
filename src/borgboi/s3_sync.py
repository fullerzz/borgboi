
from os import environ
import boto3
import subprocess as sp
from borgboi.rich_utils import print_cmd_parts


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

    result = sp.run(cmd_parts, capture_output=True, text=True)

    print(f"{result.stdout=}")
    print(f"{result.stderr=}")
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(
            returncode=result.returncode, cmd=result.args, output=result.stdout
        )