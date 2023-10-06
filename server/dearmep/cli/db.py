from __future__ import annotations
from argparse import _SubParsersAction, ArgumentParser
from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from . import Context
from ..config import APP_NAME, Config
from ..database import create_db, query
from ..database.connection import get_session
from ..database.models import Blob


def cmd_init(ctx: Context):
    Config.load()
    create_db()


def cmd_store_blob(ctx: Context):
    Config.load()
    name = ctx.args.name or ctx.args.file.name
    mime = ctx.args.mime or guess_type(ctx.args.file, strict=False)[0]
    if not mime:
        raise ValueError("could not guess MIME type")
    blob = Blob(
        type=ctx.args.type,
        mime_type=mime,
        name=name,
        description=ctx.args.description,
        data=ctx.args.file.read_bytes(),
    )
    with get_session() as session:
        if ctx.args.overwrite:
            try:
                oldblob = query.get_blob_by_name(session, name)
                session.delete(oldblob)
                session.flush()
            except query.NotFound:
                pass
        session.add(blob)
        try:
            session.commit()
        except IntegrityError:
            raise Exception(f"blob named {name} already exists") from None
        print(blob.id)


def add_parser(subparsers: _SubParsersAction, help_if_no_subcommand, **kwargs):
    parser: ArgumentParser = subparsers.add_parser(
        "db",
        help="manage the database",
        description=f"Manage the {APP_NAME} database and its contents.",
    )
    subsub = parser.add_subparsers(metavar="COMMAND")

    init = subsub.add_parser(
        "init",
        help="initialize the database from scratch",
        description="Create a new, empty database.",
    )
    init.set_defaults(func=cmd_init)

    store_blob = subsub.add_parser(
        "store-blob",
        help="store a blob (i.e., file asset) in the database",
        description="Store a static file in the database.",
    )
    store_blob.add_argument(
        "--type", required=True,
        help="the type (category) of the blob, e.g. `logo`, `name_audio` etc.",
    )
    store_blob.add_argument(
        "--mime", metavar="MIMETYPE",
        help="the MIME type of the blob (default: guess from extension)",
    )
    store_blob.add_argument(
        "--name", metavar="NAME",
        help="the file name to use when storing (default: keep original)",
    )
    store_blob.add_argument(
        "--description", metavar="TEXT",
        help="a helpful description to add to the blob",
    )
    store_blob.add_argument(
        "--overwrite", action="store_true",
        help="if there already is a blob with that name, overwrite it",
    )
    store_blob.add_argument(
        "file", metavar="FILE", type=Path,
        help="name of the local file to read and store",
    )
    store_blob.set_defaults(func=cmd_store_blob)

    help_if_no_subcommand(parser)
