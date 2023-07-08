from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from ..database.models import Blob


class ImageLoadException(Exception):
    pass


def image2blob(
    type: str,
    path: Path,
    *,
    description: Optional[str] = None,
) -> Blob:
    data = path.read_bytes()
    data_stream = BytesIO(data)
    image = Image.open(data_stream)
    if image.format is None:
        raise ImageLoadException(f"could not determine image format of {path}")
    mimetype = Image.MIME[image.format]
    return Blob(
        type=type,
        mime_type=mimetype,
        name=path.name,
        description=description,
        data=data,
    )