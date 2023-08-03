from __future__ import annotations
from argparse import _SubParsersAction, ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import Context
from ..config import APP_NAME, CMD_NAME, Config
from ..convert import dump
from ..database import importing as db_importing
from ..database.connection import get_session
from ..progress import FlexiBytesReader


def import_destinations(ctx: Context):
    Config.load()
    input: FlexiBytesReader = ctx.args.input

    with get_session() as session:
        importer = db_importing.Importer(
            portrait_template=getattr(ctx.args, "portrait_template", None),
            fallback_portrait=getattr(ctx.args, "fallback_portrait", None),
            logo_template=getattr(ctx.args, "logo_template", None),
        )
        with ctx.task_factory() as tf:
            with tf.create_task("reading and converting JSON") as task:
                input.set_task(task)
                with input as input_stream:
                    importer.import_dump(
                        session,
                        dump.read_dump_json(input_stream),
                    )
        session.commit()


def add_parser(subparsers: _SubParsersAction, help_if_no_subcommand, **kwargs):
    parser: ArgumentParser = subparsers.add_parser(
        "import",
        help=f"import data into the {APP_NAME} database",
        description=f"Import data into the {APP_NAME} database.",
    )
    subsub = parser.add_subparsers(metavar="WHAT")

    destinations = subsub.add_parser(
        "destinations",
        help="import people to contact (e.g. members of parliament)",
        description=f"Read a {APP_NAME} Destination JSON stream (e.g. "
        f"generated by a converter like `{CMD_NAME} convert parltrack.meps`) "
        "into the database.",
    )
    FlexiBytesReader.add_as_argument(destinations)
    destinations.add_argument(
        "-p", "--portrait-template", metavar="TEMPLATE",
        help="template string to construct the path to the portrait image of "
        "the Destination, e.g. `portraits/{filename}`; available placeholders "
        "are {filename} (the name as given in the `portrait` field in the "
        "Destination object in the stream) and {id} (the Destination's ID as "
        "given in the JSON",
    )
    destinations.add_argument(
        "-P", "--fallback-portrait", metavar="FILE",
        type=Path,
        help="path to a file that will be used if the portrait specified in "
        "the dump cannot be found",
    )
    destinations.add_argument(
        "-l", "--logo-template", metavar="TEMPLATE",
        help="template string to construct the path to the logo image of "
        "Destination groups, e.g. `logos/{filename}`; available placeholders "
        "are {filename} (the name as given in the `logo` field in the Group "
        "object in the stream), {id} (the Group's ID as given in the JSON), "
        "{short_name} and {long_name} (as given in the JSON)",
    )
    destinations.set_defaults(func=import_destinations, raw_stdout=True)

    help_if_no_subcommand(parser)