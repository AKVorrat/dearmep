import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette_exporter import PrometheusMiddleware, handle_metrics
from starlette_exporter.optional_metrics import request_body_size, \
    response_body_size

from . import __version__, markdown_files, static_files
from .api import v1 as api_v1
from .phone import elks as phone
from .config import APP_NAME, Config


_logger = logging.getLogger(__name__)


def require_operation_id(app: FastAPI):
    """
    Require all routes in the app to have the OpenAPI `operationId` field set.

    This allows e.g. auto-generated clients to use nice method names.
    """
    for route in app.routes:
        if isinstance(route, APIRoute) \
            and route.include_in_schema \
            and not route.operation_id:
            _logger.error(
                f'API function "{route.name}" ({", ".join(route.methods)} '
                f"{route.path}) does not have operation_id set"
            )


def create_app(config_dict: Optional[dict] = None) -> FastAPI:
    if config_dict is None:
        Config.load()
    else:
        Config.load_dict(config_dict)

    app = FastAPI(
        title=APP_NAME,
        version=__version__,
    )

    app.include_router(api_v1.router, prefix="/api/v1")
    app.include_router(phone.router, prefix="/phone")
    static_files.mount_if_configured(app, "/static")
    markdown_files.mount_if_configured(app, "/pages")

    app.add_middleware(
        PrometheusMiddleware,
        app_name=APP_NAME,
        group_paths=True,
        optional_metrics=[request_body_size, response_body_size],
    )
    app.add_route("/metrics", handle_metrics)

    require_operation_id(app)

    return app
