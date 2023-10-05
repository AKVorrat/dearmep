# mypy: ignore-errors
# Still in dev
from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Optional
from pydantic import Json

from fastapi import FastAPI, APIRouter, Depends, \
    HTTPException, Request, Form, status

import requests

from dearmep.config import Config, Language

from .models import InitialCallElkResponse, InitialElkResponseState, Number
from .ongoing_calls import Call
from . import ongoing_calls
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


def initiate_call(
    user_phone_number: str,
    user_language: Language,
    destination_id: str,
    config: Config
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """
    provider_cfg = config.telephony.provider
    elks_url = config.general.base_url + "/phone"
    auth = (
        provider_cfg.username,
        provider_cfg.password,
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
            "voice_start": f"{elks_url}/voice-start",
            "whenhangup": f"{elks_url}/hangup",
            "timeout": 13
        }
    )

    response.raise_for_status()
    response_data: InitialCallElkResponse = \
        InitialCallElkResponse.parse_obj(response.json())

    if response_data.state == "failed":
        logger.warn(f"Call failed from our number: {phone_number.number}")
        return response_data.state

    ongoing_calls.add_call(
        provider="46elks",
        provider_call_id=response_data.callid,
        user_language=user_language,
        destination_id=destination_id,
    )

    return response_data.state


def mount_router(app: FastAPI, prefix: str):
    """ Mount the 46elks router to the app """

    config = Config.get()
    provider_cfg = config.telephony.provider
    elks_url = config.general.base_url + prefix
    auth = (
        provider_cfg.username,
        provider_cfg.password,
    )
    if not config.telephony.dry_run:
        phone_numbers.extend(get_numbers(
            phone_numbers=phone_numbers,
            auth=auth,
        ))

    def verify_origin(request: Request):
        """ Makes sure the request is coming from a 46elks IP """
        client_ip = None if request.client is None else request.client.host
        # config = config
        whitelisted_ips: Tuple[str, ...] = provider_cfg.allowed_ips
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

        call = ongoing_calls.get_call(callid)

        return {
            "ivr": f"{config.telephony.audio_source}"
                   f"/connect-prompt.{call.user_language}.ogg",
            "next": f"{elks_url}/next",
            "timeout": 1,
            "repeat": 1,
        }

    @router.post("/next")
    def next(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """ Check the users entered number from voice-start """

        if str(result) == "failed" and why == "noinput":
            """
            No input by user. Either we are on
            voice mail OR user did not enter a number
            and time has passed. We hang up.
            """
            return {"hangup": "reject"}

        call = ongoing_calls.get_call(callid)

        if result == "1":
            return elk_connect(call, from_nr)

        if result == "5":

            playback_arguments = {
                "ivr": f"{config.telephony.audio_source}"
                       f"/playback_arguments.{call.user_language}.ogg",
                "next": f"{config.general.base_url}"
                        "/phone/ivr_arguments_playback",
            }

            return playback_arguments

    @router.post("/ivr_arguments_playback")
    def ivr_arguments_playback(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
    ):
        """ Check the users entered number from the arguments playback """

        call = ongoing_calls.get_call(callid)

        if result == "1":
            return elk_connect(call, from_nr)

        return {
            "play": f"{config.telephony.audio_source}/final-tune.ogg",
        }

    @router.post("/hangup")
    def hangup(
        # Arguments always present, also failures
        direction: Literal["incoming", "outgoing"] = Form(),
        created: datetime = Form(),
        from_nr: str = Form(alias="from"),
        callid: str = Form(alias="id"),
        to_nr: str = Form(alias="to"),
        state: str = Form(),
        # Arguments present in some cases, i.e. success
        start: Optional[datetime] = Form(default=None),
        actions: Optional[Json] = Form(default=None),
        cost: Optional[int] = Form(default=None),  # in 100 = 1 cent
        duration: Optional[int] = Form(default=None),  # in sec
        legs: Optional[Json] = Form(default=None)
    ):
        """
        Handles the hangup and cleanup of calls
        Always gets called in the end of calls, no matter their outcome
        Route for hangups
        """
        # If start doesn't exist this is an error message and should
        # be logged. We finish the call in our call tracking table
        if not start:
            logger.critical(f"Call id: {callid} failed. "
                            f"state: {state}, direction: {direction}")

        call = ongoing_calls.get_call(callid)
        if not call:
            logger.critical("call not found")
            return

        if bool(call.connected_at):
            connected_seconds = (
                datetime.now() - call.connected_at).total_seconds()
            elks_metrics.observe_connect_time(
                destination_id=call.destination_id,
                duration=round(connected_seconds)
            )
        if cost:
            elks_metrics.observe_cost(
                destination_id=call.destination_id,
                cost=cost
            )
        elks_metrics.inc_end(
            destination_number=call.destination_id,
            our_number=from_nr
        )
        ongoing_calls.remove_call(callid)

        # exit if error
        if not start:
            return

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
        call: Call,
        from_nr: str
    ):
        """ Dict Response to connect an user with a destination """

        number_MEP = ongoing_calls.get_mep_number(call)

        elks_metrics.inc_start(
            destination_number=number_MEP,
            our_number=from_nr
        )
        ongoing_calls.connect_call(call)
        # DEV
        number_MEP = "+4940428990"  # die Uhrzeit
        connect = {
            "connect": number_MEP,
            "next": f"{elks_url}/goodbye",
        }
        return connect
