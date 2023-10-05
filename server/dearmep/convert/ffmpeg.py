from contextlib import ExitStack, contextmanager
import subprocess
from tempfile import NamedTemporaryFile
from typing import IO, Generator, Iterable

from .blobfile import BlobOrFile


def build_concat_list(files: Iterable[str]) -> bytes:
    """Build a "playlist" of files in ffmpeg's "concat" format."""
    return "\n".join((
        "ffconcat version 1.0",
        *(f"file {file}" for file in files)
    )).encode()


@contextmanager
def build_concat_listfile(
    files: Iterable[BlobOrFile],
) -> Generator[IO[bytes], None, None]:
    """Return a temporary file with a "playlist" in ffmpeg "concat" format.

    This is to be used as a context manager; the temporary file will be deleted
    once you leave the context.

    If the input contains Blobs, these will be rendered to temporary files too,
    to allow ffmpeg to access them. These files will also be deleted once you
    leave the context.
    """
    with NamedTemporaryFile("wb", prefix="fflist.", suffix=".txt") as clist:
        with ExitStack() as stack:
            # Write the list of inputs to the concat list file.
            clist.write(build_concat_list(
                str(stack.enter_context(file.get_path()))
                for file in files
            ))
            clist.flush()
            yield clist


@contextmanager
def concat(
    inputs: Iterable[BlobOrFile],
    out_format: str,
    *,
    delete: bool = True,
) -> Generator[IO[bytes], None, None]:
    """Concatenate multiple ffmpeg input files.

    This is to be used as a context manager; the temporary file it returns will
    be deleted once you leave the context. If you set `delete=False`, it will
    _not_ be deleted and you have to take care of this yourself.

    If the input contains Blobs, these will be rendered to temporary files too,
    to allow ffmpeg to access them. They will be deleted once ffmpeg has
    finished concatenating the files.

    This function is only remuxing existing compressed streams into a new
    output file, a process that is really fast. Its disadvantage is that all
    input files need to be of the same format: Not only does the codec need to
    be the same, they also need to use the same parameters (e.g. sample rate,
    audio channels, etc.).
    """
    with NamedTemporaryFile("rb", prefix="ffconcat.", delete=delete) as output:
        with build_concat_listfile(inputs) as clist:
            run((
                "-hide_banner",  # be less verbose
                "-nostdin",  # noninteractive
                "-y",  # allow overwriting output file
                "-safe", "0",  # accept absolute paths
                "-i", clist.name,  # input filename list
                "-c", "copy",  # only copy streams, don't re-encode
                "-f", out_format,  # specify the output format
                output.name,
            ))
        yield output


def run(args, passthru=False, **kwargs) -> subprocess.CompletedProcess:
    """Run an ffmpeg subprocess."""
    completed = subprocess.run(  # type: ignore[call-overload]
        ("ffmpeg", *args),
        **{
            "stdout": None if passthru else subprocess.DEVNULL,
            "stderr": None if passthru else subprocess.DEVNULL,
            **kwargs,
        },
    )
    completed.check_returncode()
    return completed  # type: ignore[no-any-return]
