from datetime import datetime
import logging
from os import environ
from typing import Literal, Tuple, Union

from fastapi import APIRouter, Depends, HTTPException, \
                    Request, status

import requests

### Config
from dearmep.config import Config
Config.load()
config = Config.get().telephony

whitelisted_elk_ips: Tuple[str, ...] = config.provider.allowed_ips
whitelist_ips: Tuple[str, ...] = (
    *whitelisted_elk_ips,
    "127.0.0.1",
    "::1",
)
auth: Tuple[str, str] = (
    config.provider.username,
    config.provider.password,
)

### Types
CallDirection = Literal["incoming", "outgoing"]
CallID = str
Cost = int
DateTime = datetime
Duration = int
FinalState = Literal["success", "failed", "busy"]
PhoneNumber = str


### Helpers

logger = logging.getLogger(__name__)

async def verify_origin(request: Request):
    client_ip = None if request.client is None else request.client.host
    if client_ip not in whitelist_ips:
        logger.debug(f"refusing {client_ip}, not a 46elks IP")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "error": "You don't look like an elk.",
                "client_ip": client_ip,
            },
        )


########## DEV only. keywords to find TODO print eval
def get_function_name():
    import inspect
    frame = inspect.currentframe()
    return frame.f_back.f_code.co_name
##########

### Routes

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

    # TODO catch some errors and report to prometheus TODO
    if response.status_code == 401:
        logger.critical("API access denied for 46elks")
    elif response.status_code != 200:
        logger.warning("an API call was not successfull")
        raise HTTPException(response.status_code, "Phone network is temporarily unavailable. Please try again later")

    return {
        "function": _f,
        "response.status_code": response.status_code,
        "response.text": response.text
    }
