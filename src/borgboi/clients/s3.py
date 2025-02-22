import subprocess as sp
from collections.abc import Generator
from os import environ


def sync_with_s3(repo_path: str, repo_name: str) -> Generator[str]:
    """
    Sync a Borg repository with an S3 bucket while yielding the output line by line.

    Args:
        repo_path (str): posix path to the Borg repository
        repo_name (str): name of the Borg repository

    Raises:
        sp.CalledProcessError: If the command returns a non-zero exit code

    Yields:
        Generator[str]: stdout of S3 sync command line by line
    """
    sync_source = repo_path
    s3_destination_uri = f"s3://{environ['BORG_S3_BUCKET']}/{repo_name}"
    cmd = [
        "aws",
        "s3",
        "sync",
        sync_source,
        s3_destination_uri,
    ]

    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    out_stream = proc.stdout

    while out_stream.readable():  # type: ignore
        line = out_stream.readline()  # type: ignore
        yield line.decode("utf-8")
        if not line:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            break

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0:
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd)
