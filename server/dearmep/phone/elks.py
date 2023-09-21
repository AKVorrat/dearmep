from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Union
from pydantic import BaseModel, Field, Json

from fastapi import APIRouter, Depends, HTTPException, Request, Form, status

import requests

from dearmep.config import Config, Language

# Config

# TODO: find a proper place for those values
from os import environ
CONNECT_TO = environ['DEARMEP_CONNECT_TO']  # phone_nr of mep
BASE_URL = environ['DEARMEP_BASE_URL']  # base url of instance
ROUTER_BASE_URL = f"{BASE_URL}/phone"  # useful in multiple endpoints in here.
AUDIO_SRC = environ['DEARMEP_AUDIO_FILES_SRC']  # absolute url to audio files
# ## #

Config.load()
config = Config.get().telephony

whitelisted_ips: Tuple[str, ...] = config.provider.allowed_ips
auth: Tuple[str, str] = (
    config.provider.username,
    config.provider.password,
)

# Types


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


InitialElkResponseState = Literal["ongoing", "success", "busy", "failed"]
class InitialCallElkResponse(BaseModel):
    id: str
    created: datetime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: str = Field(alias="from")
    to_nr: str = Field(alias="to")


def initiate_call(
    dest_number: str,
    from_number: str,
    user_language: Language,
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """

    response = requests.post(
        url="https://api.46elks.com/a1/calls",
        auth=auth,
        data={
            "to": dest_number,
            "from": from_number,
            "voice_start": f"{ROUTER_BASE_URL}/voice-start",
            "whenhangup": f"{ROUTER_BASE_URL}/hangup",
            "timeout": 13
        }
    )
    # TODO build something to refer in connect call later
    # with MEP nr. and the call id we get back from the
    # response

    response.raise_for_status()
    data = InitialCallElkResponse.parse_obj(response.json())

    if data.state == "failed":
        logger.warn(f"Call failed from our number: {from_number}")

    return data.state

# Routes


router = APIRouter(
    dependencies=[Depends(verify_origin)],
    include_in_schema=False
)


# TODO: deprecated, use lifespan
# https://fastapi.tiangolo.com/advanced/events/
@router.on_event("startup")
async def startup():
    phone_numbers.extend(get_numbers())

from random import choice  # DEV remove


@router.post("/voice-start")
def voice_start(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: Literal["newoutgoing"] = Form(),
):

    # TODO mb as part of the route voice-start/en
    lang = choice(('fr', 'de', 'en', 'sv', 'it', 'es'))

    return {
        "ivr": f"{AUDIO_SRC}/connect-prompt.{lang}.ogg",
        "next": f"{ROUTER_BASE_URL}/next"
    }


@router.post("/next")
def next(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        # TODO check which results happen when no key is pressed f.e. "hold"
        result: int = Form(),
):

    if result == 1:
        return {
            # we want to connect here but I don't want to talk
            # to all my friends during development
            "play": f"{AUDIO_SRC}/success.ogg",
            "next": f"{ROUTER_BASE_URL}/goodbye",
        }
    return {
        "play": f"{AUDIO_SRC}/final-tune.ogg",
    }


@router.post("/goodbye")
def goodbye(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: Any = Form(),
):
    return {
        "play": f"{AUDIO_SRC}/final-tune.ogg",
    }


@router.post("/hangup")
def hangup(
    actions: Json = Form(),
    cost: int = Form(),  # in 100 = 1 cent
    created: datetime = Form(),
    direction: Literal["incoming", "outgoing"] = Form(),
    duration: int = Form(),  # in sec
    from_nr: str = Form(alias="from"),
    callid: str = Form(alias="id"),
    start: datetime = Form(),
    state: str = Form(),
    to_nr: str = Form(alias="to"),
    ):

    actions: List[Union[str, Dict[str, Any]]] = actions
