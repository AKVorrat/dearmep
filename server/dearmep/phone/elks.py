from datetime import datetime
import logging
from typing import Tuple, List, Literal
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Request, status

import requests

from dearmep.config import Config, Language

# Config

# Dev#
from os import environ
CONNECT_TO = environ['DEARMEP_CONNECT_TO']
BASE_URL = environ['DEARMEP_BASE_URL']
BASE_URL += "/phone"
voice_start_url = f"{BASE_URL}/voice-start"
when_hangup_url = f"{BASE_URL}/hangup"
# ## #

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
DateTime = datetime
PhoneNumber = str
InitialElkResponseState = Literal["ongoing", "success", "busy", "failed"]


class Number(BaseModel):
    category: Literal["fixed", "mobile", "voip"]
    country: str
    expires: datetime
    number: str
    capabilities: List[str]
    cost: int
    active: Literal["yes", "no"]
    allocated: datetime
    id: str


# will be loaded in function `startup`
phone_numbers: List[Number] = []

# Helpers


logger = logging.getLogger(__name__)


def get_numbers() -> List[Number]:
    """
    Fetches all available numbers of an account at 46elks.
    """

    response = requests.get(
        url="https://api.46elks.com/a1/numbers",
        auth=auth
    )
    if response.status_code != 200:
        raise Exception(
            "Could not fetch numbers from 46elks. "
            f"Their http status: {response.status_code}")

    numbers: List[Number] = [
        Number.parse_obj(number) for number in response.json().get('data')
    ]
    logger.info(
        "Currently available 46elks phone numbers: "
        f"{[number.number for number in numbers]}",
    )

    return numbers


def verify_origin(request: Request):
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


class InitialCallElkResponse(BaseModel):
    id: str
    created: DateTime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: PhoneNumber = Field(alias="from")
    to_nr: PhoneNumber = Field(alias="to")


def initiate_call(
    dest_number: PhoneNumber,
    from_number: PhoneNumber,
    user_language: Language
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """

    response = requests.post(
        url="https://api.46elks.com/a1/calls",
        auth=auth,
        data={
            "to": dest_number,
            "from": from_number,
            "voice_start": voice_start_url,
            "whenhangup": when_hangup_url,
            "timeout": 13
        }
    )

    response.raise_for_status()
    data = InitialCallElkResponse.parse_obj(response.json())

    if data.state == "failed":
        logger.warn(f"Call failed from our number: {from_number}")

    return data.state

# Routes


router = APIRouter(
    dependencies=[Depends(verify_origin)]
)


# TODO: deprecated, use lifespan
# https://fastapi.tiangolo.com/advanced/events/
@router.on_event("startup")
async def startup():
    phone_numbers.extend(get_numbers())


# DEVELOP
from typing import Any, Dict,Union
from fastapi import Form
@router.post("/voice-start")
def voice_starttest(request: Union[List,Dict,Any]=None):
    next_url = f"{BASE_URL}/next"

    return {
      "connect": CONNECT_TO,
      "next": next_url
    }


from urllib.parse import parse_qs
@router.post("/next")
def hangup(request: Union[List,Dict,Any,bytes]=None):
    readable = parse_qs(request.decode())
    print(' ~~~ NEXT:',readable)
@router.post("/hangup")
def hangup(request: Union[List,Dict,Any,bytes]=None):
    readable = parse_qs(request.decode())
    print(' ~~~ ON_HANGUP:',readable)
