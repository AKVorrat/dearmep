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
    callid: str = Field(alias="id")
    created: datetime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: str = Field(alias="from")
    to_nr: str = Field(alias="to")


class OngoingCall(BaseModel):
    callid: str
    created: datetime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: str
    to_nr: str
    language: Language
    # mepid: str


ongoing_calls: List[OngoingCall] = []

def get_ongoing_call(callid: str) -> OngoingCall:

    try:
        return [x for x in ongoing_calls if x.callid == callid][0]
    except IndexError:
        raise IndexError(f"Could not find ongoing call with id: {callid}")


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

    response.raise_for_status()
    response_data: InitialCallElkResponse = InitialCallElkResponse.parse_obj(response.json())

    if response_data.state == "failed":
        logger.warn(f"Call failed from our number: {from_number}")
        return response_data.state

    _ongoing_call = response_data.dict()
    _ongoing_call.update({
        "language": user_language
    })
    ongoing_call: OngoingCall = OngoingCall.parse_obj(
        _ongoing_call
    )
    ongoing_calls.append(ongoing_call)

    logger.info( 20 * "*" + "initiate_call")

    return ongoing_call.state


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

    current_call: OngoingCall = get_ongoing_call(callid)

    return {
        "ivr": f"{AUDIO_SRC}/connect-prompt.{current_call.language}.ogg",
        "next": f"{ROUTER_BASE_URL}/next"
    }


@router.post("/next")
def next(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: int = Form(),
):

    current_call: OngoingCall = get_ongoing_call(callid)

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


# route probably unused in the release, useful for debugging
@router.post("/goodbye")
def goodbye(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: Any = Form(),
):
    current_call: OngoingCall = get_ongoing_call(callid)

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

    # was sometimes called before call ended. even before phone was picked up..
    # might also be remnants of earlier calls where elk was not able to successfully
    # call /hangup because app crashed in dev or breakpoint() hit.
    try:
        current_call: OngoingCall = get_ongoing_call(callid)
    except IndexError:
        logger.critical(50*"*")
        logger.debug("hangup prematurely called by elks?")
        logger.debug(f"They tried to send data for call {callid}")
        logger.debug(f" Ongoing Calls: {ongoing_calls}")
        logger.debug("Their request")
        logger.debug(actions, cost, created, direction, duration, from_nr, callid, start, state, to_nr)
        logger.critical(50*"*")
        return

    ongoing_calls.remove(current_call)
    if len(ongoing_calls) != 0:
        logger.critical(50*"*")
        logger.debug("Current calls NOT empty:")
        logger.debug(ongoing_calls)
        logger.critical(50*"*")
