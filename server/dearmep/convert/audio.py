from mimetypes import guess_type
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from . import ffmpeg
from ..database.models import Blob


AUDIO_FORMAT = "ogg"  # ffmpeg -f
AUDIO_EXTENSION = "ogg"  # file extension
AUDIO_SAMPLERATE = 44100
IMPORT_OPTS = (
    "-filter:a",
    ", ".join((
        # normalize loudness
        # "loudnorm",
        # remove silence
        "silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-50dB",
    )),
    # loudnorm upsamples to 192k, bring it back down again
    "-ar", str(AUDIO_SAMPLERATE),
    "-ac", "1",  # mix down to mono -- beware of phase cancellation though
)


def audio2blob(
    type: str,
    path: Path,
    *,
    description: Optional[str] = None,
    convert: bool = False,
) -> Blob:
    if convert:
        with NamedTemporaryFile(
            "rb", prefix="audioconv.", suffix=f".{AUDIO_EXTENSION}",
        ) as temp:
            name = f"{path.stem}.{AUDIO_EXTENSION}"
            convert_file(path, Path(temp.name))
            data = temp.read()
            mimetype = guess_type(temp.name, strict=False)[0]
    else:
        name = path.name
        data = path.read_bytes()
        mimetype = guess_type(path, strict=False)[0]
    return Blob(
        type=type,
        mime_type=mimetype,
        name=name,
        description=description,
        data=data,
    )


def convert_file(
    input: Path,
    output: Path,
):
    ffmpeg.run((
        "-i", str(input),
        *IMPORT_OPTS,
        str(output),
    ))
