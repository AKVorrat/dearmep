# SPDX-FileCopyrightText: © 2023 Tim Weber
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from argparse import ArgumentParser, _SubParsersAction

    from . import Context
from ..config import APP_NAME, CMD_NAME, Config
from ..convert import dump
from ..database import importing as db_importing
from ..database.connection import get_session
from ..database.models import SwayabilityImport
from ..progress import FlexiBytesReader, FlexiStrReader


_logger = logging.getLogger(__name__)


def import_destinations(ctx: Context) -> None:
    Config.load()
    input: FlexiBytesReader = ctx.args.input

    with get_session() as session:
        importer = db_importing.Importer(
            portrait_template=ctx.args.portrait_template,
            fallback_portrait=ctx.args.fallback_portrait,
            logo_template=ctx.args.logo_template,
            name_audio_template=ctx.args.name_audio_template,
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


def import_swayability(ctx: Context) -> None:
    Config.load()
    input: FlexiStrReader = ctx.args.input

    with get_session() as session:
        with ctx.task_factory() as tf:
            with tf.create_task("reading and importing CSV") as task:
                input.set_task(task)
                with input as input_stream:
                    csvr = csv.DictReader(input_stream)
                    ignored = db_importing.import_swayability(session, map(
                        SwayabilityImport.parse_obj, csvr
                    ), ignore_unknown=ctx.args.ignore_unknown)
                session.commit()
    if ignored:
        _logger.warning(
            "Ignored the following IDs which were not found in the database: "
            f"{', '.join(ignored)}")


def add_parser(subparsers: _SubParsersAction, help_if_no_subcommand) -> None:
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
        "given in the JSON)",
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
    destinations.add_argument(
        "-a", "--name-audio-template", metavar="TEMPLATE",
        help="template string to construct the path to the spoken version of "
        "the Destination's name, e.g. `names/{filename}`; available "
        "placeholders are {filename} (the name as given in the `name_audio` "
        "field in the Destination object in the stream) and {id} (the "
        "Destination's ID as given in the JSON)",
    )
    destinations.set_defaults(func=import_destinations, raw_stdout=True)

    swayability = subsub.add_parser(
        "swayability",
        help="import data to calculate the priority of Destinations",
        description="Read a CSV file which provides Swayability data for "
        "Destinations. The CSV file is required to have an `id` column that "
        "references the Destination's ID. A `endorsement` column can be used "
        "to set the Base Endorsement value for the destination.",
    )
    FlexiStrReader.add_as_argument(swayability)
    swayability.add_argument(
        "--ignore-unknown", action="store_true",
        help="If the CSV contains IDs which are not found in the database, "
        "ignore these. If this option is not set, unknown IDs will instead "
        "cause the import to abort.",
    )
    swayability.set_defaults(func=import_swayability)

    help_if_no_subcommand(parser)
