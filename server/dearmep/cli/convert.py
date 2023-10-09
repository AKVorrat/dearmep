from __future__ import annotations
from argparse import _SubParsersAction, ArgumentParser
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from . import Context
from ..config import APP_NAME, CMD_NAME
from ..convert import ActionIfExists, audio, dump
from ..convert.audio import AUDIO_EXTENSION, AUDIO_FORMAT, AUDIO_SAMPLERATE
from ..convert.europarl import media, rollcallvote
from ..convert.parltrack import mep
from ..convert.tabular import CSVStreamTabular, Tabular
from ..http_client import DEFAULT_MASS_DOWNLOAD_JOBS
from ..progress import FlexiBytesReader


MEP_PORTRAIT_FILE_PATTERN = "{id}.jpg"
MEP_NAME_AUDIO_FILE_PATTERN = "{id}.mp3"


_logger = logging.getLogger(__name__)


def tabular_class(ctx: Context):
    """Return the correct Tabular subclass depending on the output format."""
    format = ctx.args.output_format
    if format == "csv":
        return CSVStreamTabular
    else:
        return Tabular


def convert_audio(ctx: Context):
    args = ctx.args
    for input in args.input:
        out_path = Path(input).with_suffix(f".{AUDIO_EXTENSION}")

        if out_path.exists():
            if args.existing == ActionIfExists.SKIP.value:
                continue
            if args.existing == ActionIfExists.FAIL.value:
                raise FileExistsError(out_path)
            if out_path.resolve() == input.resolve():
                raise ValueError(
                    "input & output refer to the same file, cannot overwrite")

        audio.convert_file(
            input,
            out_path,
        )
        print(out_path)


def parltrack_meps(ctx: Context):
    with ctx.task_factory() as tf:
        for output in dump.dump_iter_json(mep.convert_meps(
            ctx.args.input,
            tf,
            include_inactive=ctx.args.include_inactive,
            lz_compressed=ctx.args.lz,
        )):
            print(output)


def europarl_portraits(ctx: Context):
    ctx.setup_logging()
    ids = set(ctx.args.ID)
    with ctx.task_factory() as tf:
        task = tf.create_task("downloading portraits", total=len(ids))
        media.download_portraits(
            ids,
            filename_pattern=ctx.args.filename_template,
            jobs=ctx.args.jobs,
            skip_existing=ctx.args.existing == "skip",
            overwrite=ctx.args.existing == "overwrite",
            not_found=ctx.args.not_found,
            task=task,
        )
    _logger.warning(
        "The European Parliament requests attribution for using these photos. "
        "Please see <https://www.europarl.europa.eu/legal-notice/> for more."
    )


def europarl_name_audio(ctx: Context):
    ctx.setup_logging()
    ids = set(ctx.args.ID)
    with ctx.task_factory() as tf:
        task = tf.create_task("downloading name audio", total=len(ids))
        media.download_name_audio(
            ids,
            filename_pattern=ctx.args.filename_template,
            jobs=ctx.args.jobs,
            skip_existing=ctx.args.existing == "skip",
            overwrite=ctx.args.existing == "overwrite",
            not_found=ctx.args.not_found,
            task=task,
        )
    _logger.warning(
        "The European Parliament requests attribution for using these files. "
        "Please see <https://www.europarl.europa.eu/legal-notice/> for more."
    )


def rollcallvote_topics(ctx: Context):
    with ctx.task_factory() as tf:
        table = rollcallvote.list_topics(
            ctx.args.input,
            tf,
            tabular_class(ctx),
        )
    table.print_to_console(ctx.console)


def rollcallvote_votes(ctx: Context):
    with ctx.task_factory() as tf:
        table = rollcallvote.list_votes(
            ctx.args.input,
            tf,
            tabular_class(ctx),
            ctx.args.topic,
        )
    table.print_to_console(ctx.console)


def add_parser(subparsers: _SubParsersAction, help_if_no_subcommand, **kwargs):
    def rcv_template(parser: ArgumentParser, func: Callable):
        FlexiBytesReader.add_as_argument(parser)
        parser.add_argument(
            "-f", "--output-format",
            metavar="FORMAT", choices=("csv", "table"),
            default="table",
            help="output data format",
        )
        parser.set_defaults(func=func, raw_stdout=True)

    def ep_download_template(
        parser: ArgumentParser,
        func: Callable,
        *,
        default_pattern: str,
        can_save_notfound: bool,
    ):
        parser.add_argument(
            "-f", "--filename-template", metavar="TEMPLATE",
            default=default_pattern,
            help="Python .format() string template to determine target "
            "filename, {id} will be replaced by the MEP's ID (default: "
            f"{default_pattern})",
        )
        parser.add_argument(
            "-j", "--jobs", metavar="N",
            default=DEFAULT_MASS_DOWNLOAD_JOBS, type=int,
            help="the number of parallel download jobs to run (default: "
            f"{DEFAULT_MASS_DOWNLOAD_JOBS})",
        )
        choices = (media.STOP, media.IGNORE, media.SAVE) \
            if can_save_notfound else (media.STOP, media.IGNORE)
        help = [
            "what to do if there is no media for the given ID: 'stop' the "
            "whole download process (default)",
            "'ignore' this ID",
        ]
        if can_save_notfound:
            help.append(
                "'save' the placeholder that will be returned by the EuroParl "
                "server under the destination filename")
        parser.add_argument(
            "-n", "--not-found", metavar="ACTION",
            choices=choices,
            default=media.STOP,
            help=", or ".join((", ".join(help[:-1]), help[-1])),
        )
        parser.add_argument(
            "-e", "--existing", metavar="ACTION",
            choices=("stop", "skip", "overwrite"), default="stop",
            help="what to do if the target file already exists: 'stop' the "
            "whole download process (default), 'skip' downloading this file "
            "(keeping the existing file as is), or 'overwrite' (download "
            "again)",
        )
        parser.add_argument(
            "ID",
            help="the numerical MEP ID to download the media for",
            nargs="+", type=int,
        )
        parser.set_defaults(func=func)

    parser: ArgumentParser = subparsers.add_parser(
        "convert",
        help="convert data formats into others",
        description="Convert several data formats into others.",
    )
    subsub = parser.add_subparsers(metavar="CONVERTER")

    mep_portraits = subsub.add_parser(
        "europarl.portraits",
        help="portrait images of Members of the European Parliament",
        description="Download portrait images of Members of the European "
        "Parliament from the Parliament's server.",
    )
    ep_download_template(
        mep_portraits,
        europarl_portraits,
        default_pattern=MEP_PORTRAIT_FILE_PATTERN,
        can_save_notfound=True,
    )

    mep_name_audio = subsub.add_parser(
        "europarl.name-audio",
        help="name audio files of Members of the European Parliament",
        description="Download audio files containing the name of Members of "
        "the European Parliament from the Parliament's server.",
    )
    ep_download_template(
        mep_name_audio,
        europarl_name_audio,
        default_pattern=MEP_NAME_AUDIO_FILE_PATTERN,
        can_save_notfound=False,
    )

    rcv = subsub.add_parser(
        "europarl.rollcallvote",
        help="European Parliament Roll Call Vote",
    )
    rcv_sub = rcv.add_subparsers(metavar="RCV_ACTION")

    rcv_topics = rcv_sub.add_parser(
        "topics",
        help="list all voting topics in the input file",
    )
    rcv_template(rcv_topics, rollcallvote_topics)

    rcv_votes = rcv_sub.add_parser(
        "votes",
        help="list all votes for/against a given topic",
    )
    rcv_votes.add_argument(
        "--topic", "-t",
        help="ID of the topic to return the votes for",
        required=True,
    )
    rcv_template(rcv_votes, rollcallvote_votes)

    help_if_no_subcommand(rcv)

    meps = subsub.add_parser(
        "parltrack.meps",
        help="Parltrack MEP list",
        description="Convert one of Parltrack's \"MEPs\" dumps (see "
        f"<https://parltrack.org/dumps>) into {APP_NAME} Destination JSON "
        f"that can then be imported (e.g. using `{CMD_NAME} import "
        "destinations`) as the list of Destinations to contact.",
    )
    FlexiBytesReader.add_as_argument(meps)
    meps_lz = meps.add_mutually_exclusive_group()
    meps_lz.add_argument(
        "--lz", action="store_true",
        help="assume the input to be lz compressed, just as you would "
        "download it from the Parltrack website (default)",
    )
    meps_lz.add_argument(
        "--no-lz", dest="lz", action="store_false",
        help="assume the input to be uncompressed JSON",
    )
    meps.add_argument(
        "--include-inactive", action="store_true",
        help='include MEPs that are marked in the input as being "inactive"',
    )
    meps.set_defaults(func=parltrack_meps, raw_stdout=True, lz=True)

    audio = subsub.add_parser(
        "audio",
        help="audio files",
        description="Convert an audio file into the format recommended by "
        f"{APP_NAME}: {AUDIO_SAMPLERATE} Hz {AUDIO_FORMAT}, mono.",
    )
    audio.add_argument(
        "input", metavar="INPUT_FILE", type=Path, nargs="+",
        help="name of the input file(s)",
    )
    audio.add_argument(
        "-e", "--existing", default="fail",
        choices=tuple(action.value for action in ActionIfExists),
        help="what to do if an output file already exists: 'skip' the "
        "conversion and do nothing, 'overwrite' it, or 'fail' and exit with "
        "an error code",
    )
    audio.set_defaults(func=convert_audio)

    help_if_no_subcommand(parser)
