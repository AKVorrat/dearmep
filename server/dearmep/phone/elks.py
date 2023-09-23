from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Union
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


# Routes


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

    # current_call: OngoingCall = ongoing_calls.get_call(callid)

    if result == 1:

        current_call: OngoingCallRead = ongoing_calls.get_call(callid)
        number_MEP = current_call.contact.contact
        # we want to connect here but I don't want to talk
        # to parlamentarians during development
        # connection_response = {
        #     "connect": current_call.contact.contact,
        #     "next": f"{config.general.base_url}/phone/goodbye",
        # }
        elks_metrics.inc_start(
            destination_number=number_MEP,
            our_number=from_nr
        )
        development_response = {
            "play": f"{config.telephony.audio_source}/success.ogg",
            "next": f"{config.general.base_url}/phone/goodbye",
        }
        return development_response

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
    # current_call: OngoingCall = ongoing_calls.get_call(callid)

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
    # TODO access LEGS which apparently gets sent sometimes
):

    actions: List[Union[str, Dict[str, Any]]] = _actions

    # PREP testing
    # log all the things, including OngoingCall instance
    # calculate duration w testing_connect_time value and now
    # compare to legs and duration

    # was sometimes called before call ended. even before phone was picked up..
    # might also be remnants of earlier calls where elk was not able to
    # successfully call /hangup because app crashed in dev or breakpoint() hit.
    try:
        current_call: OngoingCallRead = ongoing_calls.get_call(callid)
        # TODO change dearmep.database.models.Contact.destination_id
        # away from Optional[str] to str
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
        logger.critical(50 * "*")
        logger.debug("hangup prematurely called by elks?")
        logger.debug(f"They tried to send data for call {callid}")
        logger.debug(f" Ongoing Calls: {ongoing_calls}")
        logger.debug("Their request")
        logger.debug(
            actions,
            cost,
            created,
            direction,
            duration,
            from_nr,
            callid,
            start,
            state,
            to_nr)
        logger.critical(50 * "*")
        return

    ongoing_calls.remove(callid)
    if len(ongoing_calls) != 0:
        logger.critical(50 * "*")
        logger.debug("Current calls NOT empty:")
        logger.debug(ongoing_calls)
        logger.critical(50 * "*")
