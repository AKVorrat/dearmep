# mypy: ignore-errors
# Still in dev
from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Union, Optional
from pydantic import Json

from fastapi import APIRouter, Depends, HTTPException, Request, Form, status

import requests

from dearmep.config import Config, Language

from .models import InitialCallElkResponse, InitialElkResponseState, Number
from .ongoing_calls import OngoingCalls, OngoingCall, OngoingCallRead, Contact
from .utils import get_numbers, choose_from_number
from .metrics import elks_metrics


def get_config() -> Config:
    config = Config.get()
    return config


# will be loaded in function `startup`
phone_numbers: List[Number] = []

# Instatiate Object to keep track of ongoing calls
ongoing_calls = OngoingCalls()

# Helpers


logger = logging.getLogger(__name__)


def debug(locals: Optional[Dict[str, Any]] = None, header: str = "") -> None:
    import inspect
    import pprint
    line = 20 * "*"
    space = 20 * " "
    whereami = inspect.currentframe().f_back.f_code.co_name

    if locals:
        logstr = f"\n\n{line} debug {line}  {whereami}() {header}\n"
        logstr += f"local variables:\n{pprint.pformat(locals)}"
        logstr += f"\n{line}{line}{line}\n"
    else:
        logstr = f"\n\n{line} call {line}  {whereami}()\n"

    logger.debug(logstr)


def verify_origin(request: Request):
    """ Makes sure the request is coming from a 46elks IP """
    client_ip = None if request.client is None else request.client.host
    config = get_config()
    whitelisted_ips: Tuple[str, ...] = config.telephony.provider.allowed_ips
    if client_ip not in whitelisted_ips:
        logger.debug(f"refusing {client_ip}, not a 46elks IP")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "error": "You don't look like an elk.",
                "client_ip": client_ip,
            },
        )


def initiate_call(
    user_phone_number: str,
    user_language: Language,
    contact: Contact
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """
    config = get_config()
    auth: Tuple[str, str] = (
        config.telephony.provider.username,
        config.telephony.provider.password,
    )

    # make a choice for our phone number
    phone_number = choose_from_number(
        phone_numbers=phone_numbers,
        language=user_language
    )

    response = requests.post(
        url="https://api.46elks.com/a1/calls",
        auth=auth,
        data={
            "to": user_phone_number,
            "from": phone_number.number,
            "voice_start": f"{config.general.base_url}/phone/voice-start",
            "whenhangup": f"{config.general.base_url}/phone/hangup",
            "timeout": 13
        }
    )

    response.raise_for_status()
    response_data: InitialCallElkResponse = \
        InitialCallElkResponse.parse_obj(response.json())

    if response_data.state == "failed":
        logger.warn(f"Call failed from our number: {phone_number.number}")
        return response_data.state

    # add to ongoing calls
    _ongoing_call = response_data.dict()
    _ongoing_call.update({
        "language": user_language,
        "contact": contact
    })
    ongoing_call: OngoingCall = OngoingCall.parse_obj(
        _ongoing_call
    )
    ongoing_calls.append(ongoing_call)

    return ongoing_call.state


router = APIRouter(
    dependencies=[Depends(verify_origin)],
    include_in_schema=False
)


# TODO: deprecated, use lifespan
# https://fastapi.tiangolo.com/advanced/events/
@router.on_event("startup")
async def startup():
    config = get_config()
    auth: Tuple[str, str] = (
        config.telephony.provider.username,
        config.telephony.provider.password,
    )
    phone_numbers.extend(get_numbers(
        phone_numbers=phone_numbers,
        auth=auth,
    ))


@router.post("/voice-start")
def voice_start(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: Literal["newoutgoing"] = Form(),
):

    config: Config = get_config()
    current_call: OngoingCallRead = ongoing_calls.get_call(callid)

    return {
        "ivr": f"{config.telephony.audio_source}"
               f"/connect-prompt.{current_call.language}.ogg",
        "next": f"{config.general.base_url}/phone/next"
    }


@router.post("/next")
def next(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: int = Form(),
):

    config: Config = get_config()

    current_call: OngoingCallRead = ongoing_calls.get_call(callid)
    if result == 1:

        number_MEP = current_call.contact.contact

        elks_metrics.inc_start(
            destination_number=number_MEP,
            our_number=from_nr
        )
        current_call.connected = True
        connect = {
            "connect": "+4940428990",
            "next": f"{config.general.base_url}/phone/goodbye",
        }
        return connect

    if result == 5:

        playback_arguments = {
            "ivr": f"{config.telephony.audio_source}"
                   f"/playback_arguments.{current_call.language}.ogg",
            "next": f"{config.general.base_url}/phone/ivr_arguments_playback",
        }

        return playback_arguments


@router.post("/ivr_arguments_playback")
def ivr_arguments_playback(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: int = Form(),
):
    config: Config = get_config()

    if result == 1:
        connect = {
            "connect": "+4940428990",
            "next": f"{config.general.base_url}/phone/goodbye",
        }
        return connect

    return {
        "play": f"{config.telephony.audio_source}/final-tune.ogg",
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
    config: Config = get_config()

    return {
        "play": f"{config.telephony.audio_source}/final-tune.ogg",
    }


@router.post("/hangup")
def hangup(
    _actions: Json = Form(alias="actions"),
    cost: int = Form(),  # in 100 = 1 cent
    created: datetime = Form(),
    direction: Literal["incoming", "outgoing"] = Form(),
    duration: int = Form(),  # in sec
    from_nr: str = Form(alias="from"),
    callid: str = Form(alias="id"),
    start: datetime = Form(),
    state: str = Form(),
    to_nr: str = Form(alias="to"),
    legs: Optional[Json] = Form(default=None)
):

    actions: List[Union[str, Dict[str, Any]]] = _actions

    if actions == [{"hangup": "badsource",
                    "reason": "The data received was not proper JSON"}]:
        debug(locals(), header="badsource, unproper json")

    try:
        current_call: OngoingCallRead = ongoing_calls.get_call(callid)
        elks_metrics.observe_connect_time(
            destination_id=current_call.contact.destination_id,
            duration=duration
        )
        elks_metrics.observe_cost(
            destination_id=current_call.contact.destination_id,
            cost=cost
        )
        elks_metrics.inc_end(
            destination_number=current_call.contact.contact,
            our_number=from_nr
        )
    except IndexError:
        debug(locals(), header="premature? IndexError")
        return

    ongoing_calls.remove(callid)
    if len(ongoing_calls) != 0:
        for _ in range(200):
            logger.critical(50 * "*")
            logger.critical(
                "this should never happen in dev, list of calls is not empty"
            )

    debug(locals())
