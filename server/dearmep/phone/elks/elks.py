import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union

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
from ...database.models import Destination, DestinationSelectionLogEvent
from ...models import CallType, CallState, DestinationInCallResponse, \
    UserPhone, UserInCallResponse
from .. import ivr
from . import ongoing_calls
from .metrics import elks_metrics
from .models import InitialCallElkResponse, Number
from .utils import choose_from_number, get_numbers

_logger = logging.getLogger(__name__)


phone_numbers: List[Number] = []
timeout = 9  # seconds
establish_call_timeout = 45  # seconds
menu_duration_timeout = 7  # minutes
repeat = 2


def send_sms(
    *,
    user_phone_number: str,
    from_title: str,
    message: str,
):
    provider_cfg = Config.get().telephony.provider
    auth = (
        provider_cfg.username,
        provider_cfg.password,
    )
    response = requests.post(
        url="https://api.46elks.com/a1/sms",
        auth=auth,
        data={
            "from": from_title,
            "to": user_phone_number,
            "message": message,
        }
    )
    if not response.ok:
        _logger.critical(
            f"46elks request to send sms failed: {response.status_code}")
        response.raise_for_status()

    try:
        response_data = response.json()
        elks_metrics.observe_sms_cost(
            cost=response_data["cost"],
            parts=response_data["parts"],
            recipient=user_phone_number,
        )
    except Exception:
        _logger.exception("observing SMS cost failed")


def start_elks_call(
    user_phone_number: str,
    user_language: Language,
    type_of_call: CallType,
    destination_id: str,
    session: Session,
) -> Union[CallState, DestinationInCallResponse, UserInCallResponse]:
    """ Initiate a Phone call via 46elks """
    config = Config.get()
    provider_cfg = config.telephony.provider
    elks_url = config.api.base_url + "/phone"
    auth = (
        provider_cfg.username,
        provider_cfg.password,
    )

    if ongoing_calls.destination_is_in_call(destination_id, session):
        return DestinationInCallResponse()

    user_id = UserPhone(user_phone_number)
    if ongoing_calls.user_is_in_call(user_id, session):
        return UserInCallResponse()

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
            "voice_start": f"{elks_url}/main_menu",
            "whenhangup": f"{elks_url}/hangup",
            "timeout": establish_call_timeout,
        }
    )

    if not response.ok:
        _logger.critical(
            f"46elks request to start call failed: {response.status_code}")
        return CallState.CALLING_USER_FAILED

    response_data: InitialCallElkResponse = \
        InitialCallElkResponse.parse_obj(response.json())

    if response_data.state == "failed":
        _logger.warn(f"Call failed from our number: {phone_number.number}")
        return CallState.CALLING_USER_FAILED

    ongoing_calls.add_call(
        provider=provider_cfg.provider_name,
        provider_call_id=response_data.callid,
        user_language=user_language,
        user_id=user_id,
        destination_id=destination_id,
        session=session,
        started_at=datetime.now(),
        type=type_of_call,
    )
    query.log_destination_selection(
        session=session,
        destination=query.get_destination_by_id(session, destination_id),
        event=DestinationSelectionLogEvent.CALLING_USER,
        user_id=user_id,
        call_id=response_data.callid,
    )
    session.commit()

    return CallState.CALLING_USER


def mount_router(app: FastAPI, prefix: str):
    """ Mount the 46elks router to the app """

    # configuration and instantiation at mount time
    config = Config.get()
    telephony_cfg = config.telephony
    provider_cfg = telephony_cfg.provider
    provider = provider_cfg.provider_name
    successful_call_duration = telephony_cfg.successful_call_duration
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

    # helpers
    def verify_origin(request: Request):
        """ Makes sure the request is coming from a 46elks IP """
        client_ip = None if request.client is None else request.client.host
        if client_ip not in provider_cfg.allowed_ips:
            _logger.debug(f"refusing {client_ip}, not a 46elks IP")
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "error": "You don't look like an elk.",
                    "client_ip": client_ip,
                },
            )

    def get_group_id(destination: Destination) -> Optional[str]:
        """
        Get the group id of the destinations 'parl_group'.
        If the destination has no parl_group, we return None.
        """
        parl_group = [g for g in destination.groups
                      if g.type == "parl_group"]
        if not parl_group:
            _logger.warning(f"Destination {destination.id} has no parl_group")
            return None
        return parl_group[0].id

    def sanity_check(result, why, call, session) -> Optional[dict]:
        """
        Checks if no input by user.
            Either we are on voice mail OR user did not enter a number and
            timeout and repeat have passed in IVR. We hang up.
        Checks also if the user is missusing our menu by checking the time they
            spend there not exceeding a limit.
        We craft the response here as it is needed to check this in every
            route.
        """
        if str(result) == "failed" and str(why) == "noinput":
            playlist = ivr.no_input()
            medialist_id = ivr.prepare_medialist(session, playlist,
                                                 call.user_language)
            return {
                "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            }
        duration_of_call = datetime.now() - call.started_at
        if duration_of_call >= timedelta(minutes=menu_duration_timeout):
            playlist = ivr.try_again_later()
            medialist_id = ivr.prepare_medialist(session, playlist,
                                                 call.user_language)
            elks_metrics.inc_menu_limit()
            return {
                "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            }
        return None

    def prepare_response(
            valid_input: List[int] = [],
            invalid_next: str = "",
            language: str = "en",
            timeout: int = timeout,
            repeat: int = repeat,
            no_timeout: bool = False,
            no_repeat: bool = False,
            session: Optional[Session] = None,
    ) -> dict:
        """
        Prepare response with default timeout and repeat and valid input
        numbers for the next ivr call. if valid_input is not given, we assume
        the user can enter any number. You can override default timeout and
        repeat values by passing them as arguments. You can deactivate
        including them with no_timeout and no_repeat. IF valid_input is given
        your call to this function MUST include an active session and
        invalid_next for the route which should be called.
        """
        response: Dict[str, Any] = {"timeout": timeout, "repeat": repeat}

        if valid_input:
            if not session or not invalid_next:
                raise ValueError(
                    "You need to pass a session and invalid_next "
                    "if you want to use valid_input"
                )
            playlist = ivr.wrong_input()
            medialist_id = ivr.prepare_medialist(session, playlist, language)
            wrong_input_response = {
                str(number): {
                    "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                    "next": invalid_next,
                }
                for number in range(10)
                if number not in valid_input
            }
            response.update(wrong_input_response)
        if no_timeout:
            response.pop("timeout")
        if no_repeat:
            response.pop("repeat")

        return response

    def forward_to(local_route: str, session: Session) -> dict:
        medialist_id = ivr.prepare_medialist(session, ivr.silence(), "")
        return {
            "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            "next": f"{elks_url}/{local_route}",
        }

    # Router and routes
    router = APIRouter(
        dependencies=[Depends(verify_origin)],
        include_in_schema=False,
        prefix=prefix
    )

    @router.post("/main_menu")
    def main_menu(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_number: str = Form(alias="from"),
        to_number: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """
        Playback the Instant intro in IVR
        [1]: connect
        [5]: arguments
        """

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)
            if (response := sanity_check(
                    result, why, call, session)):
                return response

            if call.type == CallType.INSTANT:
                valid_input = [1, 5]
                if result == "1":
                    return forward_to("connect", session)
                if result == "5":
                    return forward_to("arguments", session)

            response = prepare_response(
                valid_input=valid_input,
                invalid_next=f"{elks_url}/main_menu",
                language=call.user_language,
                session=session)

            playlist = ivr.main_menu(destination_id=call.destination_id)
            medialist_id = ivr.prepare_medialist(session, playlist,
                                                 call.user_language)

            query.log_destination_selection(
                session=session,
                call_id=call.provider_call_id,
                destination=call.destination,
                event=DestinationSelectionLogEvent.IN_MENU,
                user_id=call.user_id
            )
            session.commit()

        response.update({
            "ivr": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
            "next": f"{elks_url}/main_menu",
        })
        return response

    @router.post("/connect")
    def connect(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_number: str = Form(alias="from"),
        to_number: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        """
        User wants to get connected to MEP
        If MEP is available, we connect them.
        If MEP is in call already, we find a new one and suggest it to the
        user. If we fail finding one, we ask the user to try again later.
        We handle the user input here for this second path.
        [1]: connect to new MEP
        [2]: try again later, quit
        """
        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)
            if (response := sanity_check(
                    result, why, call, session)):
                return response

            # we get keypress [1] if a new suggestion is accepted
            if result == "1":
                playlist = ivr.connecting()
                medialist_id = ivr.prepare_medialist(session, playlist,
                                                     call.user_language)
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
                    "next": f"{elks_url}/finalize_connect"
                }
            # we get keypress [2] if the user wants to rather quit now
            if result == "2":
                playlist = ivr.try_again_later()
                medialist_id = ivr.prepare_medialist(session, playlist,
                                                     call.user_language)
                return {
                    "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                }

            if not ongoing_calls.destination_is_in_call(
                destination_id=call.destination_id,
                session=session
            ):
                # Mep is available, so we connect the call
                playlist = ivr.connecting()
                medialist_id = ivr.prepare_medialist(session, playlist,
                                                     call.user_language)
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
                    "next": f"{elks_url}/finalize_connect"
                }

            # MEP is in our list of ongoing calls: we get a new suggestion
            # we don't need to log the event here, as it is logged in the
            # get_random_destination function
            try:
                new_destination = query.get_recommended_destination(
                    session=session,
                    country=call.destination.country,
                    call_id=call.provider_call_id,
                    event=DestinationSelectionLogEvent.IVR_SUGGESTED,
                    user_id=call.user_id,
                )
            except query.NotFound:
                # no other MEPs available, we tell the user to try again later
                playlist = ivr.mep_unavailable_try_again_later()
                medialist_id = ivr.prepare_medialist(session, playlist,
                                                     call.user_language)
                session.commit()
                return {
                    "play": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                    "next": f"{elks_url}/hangup",
                }

            # we ask the user if they want to talk to the new suggested MEP
            # instead
            ongoing_calls.remove_call(call, session)

            ongoing_calls.add_call(
                provider=provider,
                provider_call_id=callid,
                user_language=call.user_language,
                user_id=call.user_id,
                destination_id=new_destination.id,
                type=call.type,
                started_at=call.started_at,
                session=session,
            )
            call = ongoing_calls.get_call(callid, provider, session)

            playlist = ivr.mep_unavailable_new_suggestion(
                destination_id=call.destination_id,
                group_id=get_group_id(new_destination),
            )
            medialist_id = ivr.prepare_medialist(session, playlist,
                                                 call.user_language)
            session.commit()

            response = prepare_response(
                valid_input=[1, 2],
                invalid_next=f"{elks_url}/connect",
                language=call.user_language,
                session=session)
            response.update({
                "ivr": f"{elks_url}/medialist"
                       f"/{medialist_id}/concat.ogg",
                "next": f"{elks_url}/connect",
            })
            return response

    @router.post("/arguments")
    def arguments(
            callid: str = Form(),
            from_number: str = Form(alias="from"),
            to_number: str = Form(alias="to"),
            result: str = Form(),
            why: Optional[str] = Form(default=None),
    ):
        """
        Playback the arguments in IVR
         [1]: connect
        """

        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)
            if (response := sanity_check(
                    result, why, call, session)):
                return response

            if result == "1":
                return forward_to("connect", session)

            playlist = ivr.arguments(destination_id=call.destination_id)
            medialist_id = ivr.prepare_medialist(session, playlist,
                                                 call.user_language)

            response = prepare_response(
                valid_input=[1],
                invalid_next=f"{elks_url}/arguments",
                language=call.user_language,
                session=session)
            response.update({
                "ivr": f"{elks_url}/medialist/{medialist_id}/concat.ogg",
                "next": f"{elks_url}/arguments",
            })
            return response

    @router.post("/finalize_connect")
    def finalize_connect(
        callid: str = Form(),
        direction: Literal["incoming", "outgoing"] = Form(),
        from_number: str = Form(alias="from"),
        to_number: str = Form(alias="to"),
        result: str = Form(),
        why: Optional[str] = Form(default=None),
    ):
        with get_session() as session:
            call = ongoing_calls.get_call(callid, provider, session)
            if (response := sanity_check(
                    result, why, call, session)):
                return response

            connect_number = ongoing_calls.get_mep_number(call)

            elks_metrics.inc_start(
                destination_number=connect_number,
                our_number=from_number
            )
            ongoing_calls.connect_call(call, session)
            connect = {
                "connect": connect_number,
            }
            if telephony_cfg.always_connect_to:
                connect["connect"] = telephony_cfg.always_connect_to

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
        from_number: str = Form(alias="from"),
        callid: str = Form(alias="id"),
        to_number: str = Form(alias="to"),
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
        Always gets called in the end of calls, no matter their outcome.
        Route for hangups
        """
        # If start doesn't exist this is an error message and should
        # be logged. We finish the call in our call tracking table
        if not start:
            _logger.critical(f"Call id: {callid} failed. "
                             f"state: {state}, direction: {direction}")

        with get_session() as session:
            try:
                call = ongoing_calls.get_call(callid, provider, session)
            except ongoing_calls.CallError:
                _logger.warning(
                    f"Call id: {callid} not found in ongoing calls. "
                    "This means we didn't get to write the call to our db "
                    "after initialisation."
                )
                return

            if call.connected_at:
                connected_seconds = (
                    datetime.now() - call.connected_at).total_seconds()
                elks_metrics.observe_connect_time(
                    destination_id=call.destination_id,
                    duration=round(connected_seconds)
                )
                if connected_seconds <= successful_call_duration:
                    event = DestinationSelectionLogEvent.FINISHED_SHORT_CALL
                else:
                    event = DestinationSelectionLogEvent.FINISHED_CALL
                query.log_destination_selection(
                    session=session,
                    destination=call.destination,
                    event=event,
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
                our_number=from_number
            )
            ongoing_calls.remove_call(call, session)

            # error
            if not start:
                query.log_destination_selection(
                    session=session,
                    destination=call.destination,
                    event=DestinationSelectionLogEvent.CALLING_USER_FAILED,
                    user_id=call.user_id,
                    call_id=call.provider_call_id
                )
                session.commit()

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
