from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union

from ..database.connection import Session
from ..database.models import Blob, BlobID
from ..models import MediaListItem


class BlobOrFile:
    """Represents either a Blob in the database or a real file.

    Designed to provide methods to access Blobs as (temporary) files, so that
    they can be used in conjunction with other files, for example in command
    line tools.
    """
    def __init__(
        self,
        blob_or_file: Union[Blob, BlobID, Path],
        *,
        session: Optional[Session] = None,
    ):
        self._session = session
        self._obj = blob_or_file

    @classmethod
    def from_medialist_item(cls, item) -> BlobOrFile:
        if isinstance(item, str):
            return cls(Path(item))
        # TODO
        raise NotImplementedError()

    def as_medialist_item(self) -> MediaListItem:
        if isinstance(self._obj, Path):
            return str(self._obj)
        # TODO
        raise NotImplementedError()

    @contextmanager
    def get_path(self) -> Generator[Path, None, None]:
        """Get a `Path` instance to the data represented by this object.

        If this object wraps a `Path` instance, this will be returned. Else, if
        it contains a Blob, the Blob is extracted from the database into a
        temporary file, and the `Path` to that temporary file is returned.

        Note that the result of this method is designed to be used as a context
        manager. The existence of the returned `Path` is only guaranteed for as
        long as the context is open. Once you leave the context, the temporary
        file (if this object contains a Blob) is deleted.
        """
        if isinstance(self._obj, Path):
            yield self._obj
            return
        # TODO: Provide the blob contents as a temporary file.
        raise NotImplementedError()
