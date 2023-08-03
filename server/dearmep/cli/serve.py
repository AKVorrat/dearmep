from __future__ import annotations
from argparse import _SubParsersAction, ArgumentParser
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from . import Context
from ..config import APP_NAME, CMD_NAME, ENV_PREFIX, included_file


DEFAULT_PORT = 8000
LOG_LEVELS = ("critical", "error", "warning", "info", "debug")
DEFAULT_LOG_LEVEL = "info"


def serve(ctx: Context):
    uvicorn.run(
        "dearmep.main:create_app",
        factory=True,
        port=ctx.args.port,
        reload=ctx.args.reload,
        reload_excludes=["node_modules"],  # TODO: doesn't seem to be working
        log_config=ctx.args.log_config,
        log_level=ctx.args.log_level,
        proxy_headers=True,  # Parse headers from a reverse proxy.
    )


def add_parser(subparsers: _SubParsersAction, **kwargs):
    parser: ArgumentParser = subparsers.add_parser(
        "serve",
        help="run an HTTP server",
        description=f"Start a Uvicorn instance and run {APP_NAME} inside of "
        "it. Remember that you need to provide the path to your campaign's "
        f"configuration via the {ENV_PREFIX}CONFIG environment variable.",
        epilog=f"If you would like to start {APP_NAME} via a separate ASGI "
        "server, its factory function is `dearmep.main:create_app`.",
    )
    parser.set_defaults(func=serve)

    parser.add_argument(
        "--port", "-p",
        type=int, default=DEFAULT_PORT,
        help=f"TCP port number to use (default: {DEFAULT_PORT})",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="automatically restart the application when a source file "
        "changes (only useful during development)",
    )

    parser.add_argument(
        "--log-config",
        metavar="PATH",
        default=str(included_file("logging.yaml")),
        help="path to a YAML logging config file to use (defaults to the "
        f"built-in one you can inspect via `{CMD_NAME} dump log-config`)",
    )

    parser.add_argument(
        "--log-level", "-l",
        metavar="LEVEL",
        choices=LOG_LEVELS, default=DEFAULT_LOG_LEVEL,
        help="only display messages at or above this level (default: "
        f"{DEFAULT_LOG_LEVEL}; choices: {', '.join(LOG_LEVELS)})",
    )