from datetime import datetime
import logging
from os import environ
from typing import Literal, Tuple, Union

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, \
                    Request, status

from ..models import PhoneNumber


logger = logging.getLogger(__name__)


CallDirection = Literal["incoming", "outgoing"]
CallID = str
Cost = int
DateTime = datetime
Duration = int
FinalState = Literal["success", "failed", "busy"]


# This list is from <https://46elks.com/docs/verify-callback-origin>.
elks_ips: Tuple[str, ...] = (
    "176.10.154.199", "85.24.146.132", "185.39.146.243",
    "2001:9b0:2:902::199",
)


def include_router(
    parent: Union[APIRouter, FastAPI],
    base_url: str,
    prefix: str = "/callback/46elks",
    allow_localhost: bool = False,
) -> APIRouter:
    # TODO: This is just for initial experimentation. Will be removed.
    connect_to = environ["CONNECT_TO"]
    logger.warn("will connect everyone to %s", connect_to)

    base_url = base_url.rstrip("/")

    logger.info(
        "setting up 46elks callback routes at %s%s, %sallowing localhost",
        base_url, prefix, "" if allow_localhost else "dis"
    )

    router = APIRouter()

    allowed_ips = elks_ips
    if allow_localhost:
        allowed_ips += ("::1", "127.0.0.1")

    async def verify_origin(request: Request):
        client_ip = None if request.client is None else request.client.host
        if client_ip not in allowed_ips:
            logger.debug(f"refusing {client_ip}, not a 46elks IP")
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "error": "You don't look like an elk.",
                    "client_ip": client_ip,
                },
            )

    # See <https://46elks.com/docs/receive-call>.
    @router.post("/voice-start")
    async def voice_start(
        callid: CallID = Form(),
        direction: CallDirection = Form(),
        from_nr: PhoneNumber = Form(alias="from"),
        to_nr: PhoneNumber = Form(alias="to"),
    ):
        logger.info(
            "voice_start of %s call %s",
            direction, callid,
        )
        prompt_path = "/audio/experiments/46elks/connect-prompt.de.mp3"
        return {
            "ivr": f"{base_url}{prompt_path}",
            "whenhangup": f"{base_url}{prefix}/voice-end",
            "next": f"{base_url}{prefix}/next"
        }

    # See <https://46elks.com/docs/call-actions>.
    @router.post(
        "/voice-end",  # aka "whenhangup"
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def voice_end(
        callid: CallID = Form(alias="id"),
        created: DateTime = Form(),
        start: DateTime = Form(),  # TODO: is this optional?
        direction: CallDirection = Form(),
        from_nr: PhoneNumber = Form(alias="from"),
        to_nr: PhoneNumber = Form(alias="to"),
        state: FinalState = Form(),
        cost: Cost = Form(),
        duration: Duration = Form(),
    ):
        logger.info(
            "%s call %s (created %s, started %s) ends (%s), %ds, cost %d",
            direction, callid, created, start, state, duration, cost,
        )

    @router.post(
        "/next",
    )
    async def next():
        return {
            "connect": connect_to,
            "next": f"{base_url}{prefix}/connect",
        }

    parent.include_router(
        router,
        dependencies=[Depends(verify_origin)],
        prefix=prefix,
    )
    return router
