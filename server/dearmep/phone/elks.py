from datetime import datetime
import logging
from typing import Literal, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status

import requests

from dearmep.config import Config

# Config

Config.load()
config = Config.get().telephony

whitelisted_ips: Tuple[str, ...] = config.provider.allowed_ips
auth: Tuple[str, str] = (
    config.provider.username,
    config.provider.password,
)

# Types
CallDirection = Literal["incoming", "outgoing"]
CallID = str
Cost = int
DateTime = datetime
Duration = int
FinalState = Literal["success", "failed", "busy"]
PhoneNumber = str


# Helpers

logger = logging.getLogger(__name__)


async def verify_origin(request: Request):
    client_ip = None if request.client is None else request.client.host
    if client_ip not in whitelisted_ips:
        logger.debug(f"refusing {client_ip}, not a 46elks IP")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "error": "You don't look like an elk.",
                "client_ip": client_ip,
            },
        )


# DEV only. keywords to find TODO print eval
def get_function_name():
    import inspect
    frame = inspect.currentframe()
    return frame.f_back.f_code.co_name


# Routes

router = APIRouter(
    dependencies=[Depends(verify_origin)]
)


@router.get("/call")
def explorative_calls():
    _f = get_function_name()

    response = requests.get(
        url="https://api.46elks.com/a1/numbers",
        auth=auth,
        data={}
    )
    response.raise_for_status()

    return {
        "function": _f,
        "response.status_code": response.status_code,
        "response.text": response.text
    }
