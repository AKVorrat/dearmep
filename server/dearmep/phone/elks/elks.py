import logging
from datetime import datetime
from typing import Any, List, Literal, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, \
    Request, status
from fastapi.responses import FileResponse
from pydantic import UUID4, Json
from sqlmodel import Session

from ...config import Config, Language
from ...convert import blobfile, ffmpeg
from ...database import query
from ...database.connection import get_session
from ...database.models import DestinationSelectionLogEvent
from ...models import UserPhone
from ...phone import ivr_audio
from ...phone.ivr_audio import CallType, Flow
from . import ongoing_calls
from .metrics import elks_metrics
from .models import InitialCallElkResponse, InitialElkResponseState, Number
from .utils import choose_from_number, get_numbers

logger = logging.getLogger(__name__)


phone_numbers: List[Number] = []


def start_elks_call(
    user_phone_number: str,
    user_language: Language,
    destination_id: str,
    config: Config,
    session: Session,
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """
    provider_cfg = config.telephony.provider
    elks_url = config.api.base_url + "/phone"
    auth = (
        provider_cfg.username,
        provider_cfg.password,
    )

    user_id = UserPhone(user_phone_number)
    phone_number = choose_from_number(
        user_number_prefix=str(user_id.calling_code),
        user_language=user_language,
        phone_numbers=phone_numbers,
    )

    response = requests.post(
        url="https://api.46elks.com/a1/calls",
        auth=auth,
        data={
            "to": user_phone_number,
            "from": phone_number.number,
            "voice_start": f"{elks_url}/instant_main_menu",
            "whenhangup": f"{elks_url}/hangup",
            "timeout": 13,
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
        user_id=user_id,
        destination_id=destination_id,
        session=session,
    )
    query.log_destination_selection(
        session=session,
        destination=query.get_destination_by_id(session, destination_id),
        event=DestinationSelectionLogEvent.CALLING_USER,
        user_id=user_id,
        call_id=response_data.callid,
    )
    session.commit()

    return response_data.state


def mount_router(app: FastAPI, prefix: str):
    """ Mount the 46elks router to the app """

    # configuration
    config = Config.get()
    telephony_cfg = config.telephony
    provider_cfg = telephony_cfg.provider
    provider = provider_cfg.provider_name
    phone_call_threshhold = telephony_cfg.phone_call_threshhold
    elks_url = config.api.base_url + prefix
    auth = (
        provider_cfg.username,
        provider_cfg.password,
    )
    if not config.telephony.dry_run:
        phone_numbers.extend(get_numbers(
            phone_numbers=phone_numbers,
            auth=auth,
        ))
    medialist = ivr_audio.Medialist(
        folder=config.telephony.audio_source,
        fallback_language="en"
    )

    # helpers
    def verify_origin(request: Request):
        """ Makes sure the request is coming from a 46elks IP """
        client_ip = None if request.client is None else request.client.host
        if client_ip not in provider_cfg.allowed_ips:
            logger.debug(f"refusing {client_ip}, not a 46elks IP")
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "error": "You don't look like an elk.",
                    "client_ip": client_ip,
                },
            )

    def check_no_input(result, why):
        """
        Check if no input by user. Either we are on voice mail OR user did not
        enter a number and timeout has passed in IVR. We got hung up by elks.
        """
        return True if (
            str(result) == "failed"
            and str(why) == "noinput"
        ) else False

    def get_alternative_destination(session):
        """
        get a new suggestion for a MEP to talk to. Make sure that we fetch
        someone not in our calllist """
        new_destination = query.get_random_destination(session)
        if ongoing_calls.destination_is_in_call(
                new_destination.id, session):
            return get_alternative_destination()
        return new_destination

    def instant_connect_to_mep(call, callid, session):

        if not ongoing_calls.destination_is_in_call(
            destination_id=call.destination_id,
            session=session
        ):
            # Mep is available, so we connect the call
            medialist_id = medialist.get(
                flow=Flow.connecting,
                call_type=CallType.instant,
                destination_id=call.destination_id,
                language=call.user_language,
                session=session
            )
            query.log_destination_selection(
                session=session,
                destination=call.destination,
                event=DestinationSelectionLogEvent.CALLING_DESTINATION,
                user_id=call.user_id,
                call_id=call.provider_call_id
            )
            session.commit()
            return {
                "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                "next": f"{elks_url}/instant_connect"
            }

        # MEP is in our list of ongoing calls: we get a new suggestion
        new_destination = get_alternative_destination(session)

        group = [g for g
                 in new_destination.groups
                 if g.type == "parl_group"][0]

        ongoing_calls.remove_call(call, session)
        ongoing_calls.add_call(
            provider=provider,
            provider_call_id=callid,
            user_language=call.user_language,
            user_id=call.user_id,
            destination_id=new_destination.id,
            session=session
        )
        call = ongoing_calls.get_call(callid, provider, session)

        # we ask the user if they want to talk to the new suggested
        # MEP instead
        medialist_id = medialist.get(
            flow=Flow.mep_unavailable,
            call_type=CallType.instant,
            destination_id=call.destination_id,
            language=call.user_language,
            group_id=group.id,
            session=session
        )
        query.log_destination_selection(
            session=session,
            destination=new_destination,
            event=DestinationSelectionLogEvent.IVR_SUGGESTED,
            user_id=call.user_id,
            call_id=call.provider_call_id
        )
        session.commit()

        return {
            "ivr": f"{elks_url}/medialist"
                   f"/{medialist_id}/concat.ogg",
            "next": f"{elks_url}/instant_alternative",
            "timeout": 10,
            "repeat": 2,
        }

    # Router and routes
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
        """
        Initial IVR playback of Insant Call
        User picks up the Phone. We play the main menu.
        """

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)
            medialist_id = medialist.get(
                flow=Flow.main_menu,
                destination_id=call.destination_id,
                call_type=CallType.instant,
                language=call.user_language,
                session=session
            )
            query.log_destination_selection(
                session=session,
                call_id=call.provider_call_id,
                destination=call.destination,
                event=DestinationSelectionLogEvent.IN_MENU,
                user_id=call.user_id
            )
            session.commit()

        return {
            "ivr": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            "next": f"{elks_url}/instant_next",
            "timeout": 5,
            "repeat": 2,
        }

    @router.post("/instant_next")
    def next_route(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """
        Check the entered number from instant_main_menu
         1: connect
         5: arguments
        """

        if check_no_input(result, why):
            return

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)

            if result == "1":
                return instant_connect_to_mep(call, callid, session)

            if result == "5":
                """ user wants to listen to some arguments """

                medialist_id = medialist.get(
                    flow=Flow.arguments,
                    call_type=CallType.instant,
                    destination_id=call.destination_id,
                    language=call.user_language,
                    session=session
                )
                return {
                    "ivr": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                    "next": f"{elks_url}/arguments",
                }

    @router.post("/arguments")
    def ivr_choice_arguments(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """
        Check the entered number after we played arguments to the user
         1: connect
        """
        if check_no_input(result, why):
            return

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)

            if result == "1":
                return instant_connect_to_mep(call, callid, session)

    @router.post("/instant_alternative")
    def instant_alternative(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """
        Check the entered number after we asked the user
        if they want to talk to a newly suggested MEP instead
         1: connect
         2: try again later, quit
        """

        if check_no_input(result, why):
            return

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)

            if result == "1":
                return instant_connect_to_mep(call, callid, session)

        if result == "2":
            with get_session() as session:
                call = ongoing_calls.get_call(callid, provider, session)

                medialist_id = medialist.get(
                    flow=Flow.try_again_later,
                    call_type=CallType.instant,
                    destination_id=call.destination_id,
                    language=call.user_language,
                    session=session
                )
                return {
                    "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                }

    @router.post("/instant_connect")
    def instant_connect(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_nr: str = Form(alias="from"),
        to_nr: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)

            connect_number = ongoing_calls.get_mep_number(call)

            elks_metrics.inc_start(
                destination_number=connect_number,
                our_number=from_nr
            )
            ongoing_calls.connect_call(call, session)
            connect = {
                "connect": connect_number,
                "next": f"{elks_url}/thanks_for_calling",
            }
            if telephony_cfg.test_call:
                connect["connect"] = telephony_cfg.test_call

            query.log_destination_selection(
                session=session,
                destination=call.destination,
                event=DestinationSelectionLogEvent.DESTINATION_CONNECTED,
                user_id=call.user_id,
                call_id=call.provider_call_id
            )
            session.commit()
            return connect

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

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)

            if call.connected_at:
                connected_seconds = (
                    datetime.now() - call.connected_at).total_seconds()
                elks_metrics.observe_connect_time(
                    destination_id=call.destination_id,
                    duration=round(connected_seconds)
                )
                if connected_seconds <= phone_call_threshhold:
                    query.log_destination_selection(
                        session=session,
                        destination=call.destination,
                        event=DestinationSelectionLogEvent.FINISHED_SHORT_CALL,
                        user_id=call.user_id,
                        call_id=call.provider_call_id
                    )
                else:
                    query.log_destination_selection(
                        session=session,
                        destination=call.destination,
                        event=DestinationSelectionLogEvent.FINISHED_CALL,
                        user_id=call.user_id,
                        call_id=call.provider_call_id
                    )
                session.commit()
            else:
                query.log_destination_selection(
                    session=session,
                    destination=call.destination,
                    event=DestinationSelectionLogEvent.CALL_ABORTED,
                    user_id=call.user_id,
                    call_id=call.provider_call_id
                )
                session.commit()
            if cost:
                elks_metrics.observe_cost(
                    destination_id=call.destination_id,
                    cost=cost
                )
            elks_metrics.inc_end(
                destination_number=call.destination_id,
                our_number=from_nr
            )
            ongoing_calls.remove_call(call, session)

            # exit if error
            if not start:
                query.log_destination_selection(
                    session=session,
                    destination=call.destination,
                    event=DestinationSelectionLogEvent.CALLING_USER_FAILED,
                    user_id=call.user_id,
                    call_id=call.provider_call_id
                )
                session.commit()
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
