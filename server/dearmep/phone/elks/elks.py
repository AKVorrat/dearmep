# mypy: ignore-errors
# Still in dev
from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Union, Optional
from pydantic import Json

from fastapi import FastAPI, APIRouter, Depends, \
    HTTPException, Request, Form, status

import requests

from dearmep.config import Config, Language

from .models import InitialCallElkResponse, InitialElkResponseState, Number
from .ongoing_calls import OngoingCalls, OngoingCall, OngoingCallRead, Contact
from .utils import get_numbers, choose_from_number
from .metrics import elks_metrics


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


phone_numbers: List[Number] = []
ongoing_calls = OngoingCalls()


def initiate_call(
    user_phone_number: str,
    user_language: Language,
    contact: Contact,
    config: Config

) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """
    auth: Tuple[str, str] = (
        config.telephony.provider.username,
        config.telephony.provider.password,
    )

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

    ongoing_call: OngoingCall = OngoingCall.parse_obj({
        **response_data.dict(),
        "language": user_language,
        "contact": contact
    })
    ongoing_calls.append(ongoing_call)

    return ongoing_call.state


def mount_router(app: FastAPI, prefix: str):
    """ Mount the 46elks router to the app """

    config = Config.get()
    auth = (
        config.telephony.provider.username,
        config.telephony.provider.password
    )
    phone_numbers.extend(get_numbers(
        phone_numbers=phone_numbers,
        auth=auth,
    ))

    def verify_origin(request: Request):
        """ Makes sure the request is coming from a 46elks IP """
        client_ip = None if request.client is None else request.client.host
        # config = config
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

    router = APIRouter(
        dependencies=[Depends(verify_origin)],
        include_in_schema=False,
        prefix=prefix
    )

    @router.post("/voice-start")
    def voice_start(
            callid: str = Form(),
            direction: Literal["incoming", "outgoing"] = Form(),
            from_nr: str = Form(alias="from"),
            to_nr: str = Form(alias="to"),
            result: Literal["newoutgoing"] = Form(),
    ):
        """ Begin playback of an IVR to user """

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
        """ Check the users entered number from voice-start """

        current_call: OngoingCallRead = ongoing_calls.get_call(callid)

        if result == 1:
            return elk_connect(current_call, from_nr)

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
        """ Check the users entered number from the arguments playback """

        current_call: OngoingCallRead = ongoing_calls.get_call(callid)

        if result == 1:
            return elk_connect(current_call, from_nr)

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
        """
        Handles the hangup and cleanup of calls
        Always gets called in the end of calls, no matter their outcome
        Route for hangups
        """

        actions: List[Union[str, Dict[str, Any]]] = _actions

        current_call: OngoingCallRead = ongoing_calls.get_call(callid)
        ongoing_calls.remove(callid)

        if bool(current_call.connected):
            connected_seconds = (
                datetime.now() - current_call.connected).total_seconds()
            elks_metrics.observe_connect_time(
                destination_id=current_call.contact.destination_id,
                duration=round(connected_seconds)
            )
        elks_metrics.observe_cost(
            destination_id=current_call.contact.destination_id,
            cost=cost
        )
        elks_metrics.inc_end(
            destination_number=current_call.contact.contact,
            our_number=from_nr
        )

        if len(ongoing_calls) != 0:
            for _ in range(200):
                logger.critical(50 * "*")
                logger.critical(
                    "this should never happen in dev, "
                    "list of calls is not empty"
                )

        # catch weird json
        if [x for x in actions if type(x) is not str and x.get("hangup") == "badsource"]:  # noqa: E501

            logger.warning("we sent unproper json elk did not understand")
            debug(locals(), header="badsource, unproper json")

            return
        debug(locals())

    @router.post("/goodbye")
    def goodbye(
            callid: str = Form(),
            direction: Literal["incoming", "outgoing"] = Form(),
            from_nr: str = Form(alias="from"),
            to_nr: str = Form(alias="to"),
            result: Any = Form(),
    ):
        """ route probably unused in the release, useful for debugging """

        return {
            "play": f"{config.telephony.audio_source}/final-tune.ogg",
        }

    app.include_router(router)

    # reused functions to craft responses to 46 elk
    def elk_connect(
        current_call: OngoingCallRead,
        from_nr: str
    ):
        """ Dict Response to connect an user with a destination """

        number_MEP = current_call.contact.contact

        elks_metrics.inc_start(
            destination_number=number_MEP,
            our_number=from_nr
        )
        current_call.connected = datetime.now()
        connect = {
            "connect": "+4940428990",
            "next": f"{config.general.base_url}/phone/goodbye",
        }
        return connect
