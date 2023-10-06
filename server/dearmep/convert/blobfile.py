from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator, List, Optional, Sequence, Tuple, Union

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

    def __str__(self) -> str:
        if isinstance(self._obj, Path):
            return str(self._obj)
        if isinstance(self._obj, Blob):
            return f"Blob obj {self._obj.id}"
        if isinstance(self._obj, int):
            return f"Blob ref {self._obj}"
        raise NotImplementedError()

    def __repr__(self) -> str:
        if isinstance(self._obj, Blob):
            return (
                f"BlobOrFile(Blob(id={self._obj.id}, name={self._obj.name}))")
        return f"BlobOrFile({repr(self._obj)})"

    @classmethod
    def from_medialist_item(
        cls,
        item: MediaListItem,
        *,
        session: Optional[Session],
    ) -> BlobOrFile:
        if isinstance(item, str):
            return cls(Path(item))
        if isinstance(item, int):
            return cls(item, session=session)
        raise NotImplementedError()

    def as_medialist_item(self) -> MediaListItem:
        if isinstance(self._obj, Path):
            return str(self._obj)
        if isinstance(self._obj, Blob):
            if self._obj.id is None:
                raise ValueError("wrapped blob does not have an ID")
            return int(self._obj.id)
        if isinstance(self._obj, int):
            return self._obj
        raise NotImplementedError()

    @contextmanager
    def get_path(
        self,
        *,
        session: Optional[Session] = None,
    ) -> Generator[Path, None, None]:
        """Get a `Path` instance to the data represented by this object.

        If this object wraps a `Path` instance, this will be returned. Else, if
        it contains a Blob, the Blob is extracted from the database into a
        temporary file, and the `Path` to that temporary file is returned.

        Note that the result of this method is designed to be used as a context
        manager. The existence of the returned `Path` is only guaranteed for as
        long as the context is open. Once you leave the context, the temporary
        file (if this object contains a Blob) is deleted.
        """
        from ..database import query

        if isinstance(self._obj, Path):
            yield self._obj
            return

        if isinstance(self._obj, int):
            session = session or self._session
            if not session:
                raise ValueError(
                    "cannot resolve blob ID without database session")
            blob = query.get_blob_by_id(session, self._obj)
        elif isinstance(self._obj, Blob):
            blob = self._obj
        else:
            raise NotImplementedError()

        with NamedTemporaryFile("wb+", prefix=f"blob.{blob.id}.") as fobj:
            fobj.write(blob.data)
            fobj.flush()
            fobj.seek(0)
            yield Path(fobj.name)


def get_blobs_or_files(
    names: Sequence[str],
    *,
    session: Session,
    folder: Path,
    languages: Sequence[str] = (),
    suffix: str = "",
) -> List[BlobOrFile]:
    """Get BlobOrFile list by looking up names in database & filesystem.

    `names` is a sequence of file stems (without specifying a language suffix
    or filetype extension). Provide the extension separately via `suffix`, and
    include the leading dot. `language` is a sequence of language suffixes to
    try. You can leave this empty if you don't want to use language suffixes.

    The function will generate file names in the format `{stem}.{lang}{suffix}`
    for each of the name stems & languages. If a blob with that name exists in
    the database, it will be added to the output list. Else, if a file with
    that name exists in `folder`, it will be added to the output list.

    For each stem, only one output item will be added to the list, even if
    multiple language suffixes might match. In other words, the languages work
    as a preference list, first match wins. This means that the output list
    will always be as long as the input sequence.

    If a stem doesn't have a match at all (neither a Blob nor a file with any
    of the languages), a `KeyError` is raised.
    """
    from ..database import query

    def names_with_languages(
        name: str, languages: Sequence[str], suffix: str
    ) -> Tuple[str, ...]:
        if not languages:  # no multi-language matching
            return (f"{name}{suffix}",)
        return tuple(
            f"{name}{'.' if len(lang) else ''}{lang}{suffix}"
            for lang in languages
        )

    # Build list of names to retrieve, to reduce the number of DB queries.
    allnames = {
        stem: names_with_languages(stem, languages, suffix)
        for stem in names
    }
    flat = [name for expanded in allnames.values() for name in expanded]

    # Query the database for all possible names.
    blobs = query.get_blobs_by_names(session, flat)

    # Collect the actual result.
    res: List[BlobOrFile] = []
    for name in names:
        for candidate in names_with_languages(name, languages, suffix):
            if candidate in blobs:
                res.append(BlobOrFile(blobs[candidate]))
                break
            if (path := folder / candidate).exists():
                res.append(BlobOrFile(path))
                break
        else:
            raise KeyError(name)
    return res
