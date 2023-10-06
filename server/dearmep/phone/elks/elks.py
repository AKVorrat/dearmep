# mypy: ignore-errors
# Still in dev
from datetime import datetime
import logging
from typing import Tuple, List, Literal, Any, Dict, Optional
from pydantic import Json, UUID4
from pathlib import Path

from fastapi import FastAPI, APIRouter, Depends, \
    HTTPException, Request, Form, status
from fastapi.responses import FileResponse

import requests

from dearmep.config import Config, Language
from dearmep.convert import blobfile, ffmpeg
from dearmep.database.connection import get_session
from dearmep.database import query
from dearmep.phone import ivr_audio

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
    whereami = inspect.currentframe().f_back.f_code.co_name

    if locals:
        schmocals = {k: v for k, v in locals.items() if k not in ("config",)}
        logstr = f"\n\n{line} debug {line}  {whereami}() {header}\n"
        logstr += f"local variables:\n{pprint.pformat(schmocals)}"
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
            "voice_start": f"{elks_url}/instant_main_menu",
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

    @router.post("/instant_main_menu")
    def instant_main_menu(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: Literal["newoutgoing"] = Form(),
    ):
        """ Initial IVR playback of Insant Call """

        call = ongoing_calls.get_call(callid)

        with get_session() as session:
            medialist = blobfile.get_blobs_or_files(
                names=ivr_audio.Flows.instant(
                    flow="main_menu",
                    destination_id=call.destination_id,
                ),
                session=session,
                folder=Path("/home/v/dearmep-infos/ivr_audio"),
                languages=("de", "en", ""),
                suffix=".ogg",
            )
            medialist_id = query.store_medialist(
                format="ogg",
                mimetype="audio/ogg",
                items=medialist,
                session=session
            )

        response = {
            "ivr": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            "next": f"{elks_url}/instant_next",
            "timeout": 5,
            "repeat": 2,
        }
        return response

    @router.post("/instant_next")
    def next_route(
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

            # playback IVR arguments
            playback_arguments = {
                "ivr": f"{config.telephony.audio_source}"
                       f"/playback_arguments.{call.user_language}.ogg",
                "next": f"{elks_url}/instant_next",
            }

            return playback_arguments

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

    @router.post("/thanks_for_calling")
    def thanks_for_calling(
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

    @router.get("/medialist/{medialist_id}/concat.ogg")
    def get_concatenated_media(medialist_id: UUID4):
        """ Get a concatenated media list as a stream for 46 elks IVR """

        with get_session() as session:
            medialist = query.get_medialist_by_id(session, medialist_id)
            items = [
                blobfile.BlobOrFile.from_medialist_item(item, session=session)
                for item in medialist.items
            ]
        with ffmpeg.concat(items, medialist.format, delete=False) as concat:
            return FileResponse(
                concat.name,
                media_type=medialist.mimetype
            )

    app.include_router(router)

    # reused functions to craft responses to 46 elk #
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
            "next": f"{elks_url}/thanks_for_calling",
        }
        return connect
