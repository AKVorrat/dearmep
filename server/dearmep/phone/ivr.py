import re
from pydantic import UUID4
from random import shuffle
from sqlmodel import Session
from typing import List, Optional

from ..config import Config
from ..convert import blobfile
from ..database import query


def prepare_medialist(session: Session, playlist: List[str], language: str
                      ) -> UUID4:
    """
    Function to create a medialist and get it's id. This medialist_id can be
    given to the ffmpeg concat endpoint in `elks.get_concatenated_media` to
    play the flow to the user in IVR or play responses.
    """

    medialist = blobfile.get_blobs_or_files(
        names=playlist,
        session=session,
        folder=Config.get().telephony.audio_source,
        languages=(language, "en", ""),  # " " string needed
        suffix=".ogg",
    )
    medialist_id = query.store_medialist(
        format="ogg",
        mimetype="audio/ogg",
        items=medialist,
        session=session
    )
    return medialist_id


def _group_filename(group_id: str):
    return "group_" + re.sub(
        r"[^a-zA-Z]", "_",
        re.sub(r"^G:", "", group_id)
    ).lower()


def main_menu(
    *, destination_id: str, scheduled: bool = False,
        group_id: Optional[str] = None) -> List[str]:
    """ IVR main menu, greeting and present choices """
    if not scheduled:
        return ["campaign_greeting", "main_choice_instant_1", destination_id,
                "main_choice_instant_2", "main_choice_arguments"]
    if not group_id:
        raise ValueError("group_id is required when scheduled is True")
    group_filename = _group_filename(group_id)
    return ["campaign_greeting", "main_scheduled_intro",
            "main_choice_scheduled_1", destination_id,
            "main_choice_scheduled_2", group_filename,
            "main_choice_scheduled_3", "main_choice_postpone",
            "main_choice_unsubscribe", "main_choice_arguments"]


def arguments(*, destination_id: str) -> List[str]:
    """ IVR read arguments """
    _arguments = ["argument_1", "argument_2", "argument_3", "argument_4",
                  "argument_5", "argument_6", "argument_7", "argument_8",
                  ]
    shuffle(_arguments)
    return ["arguments_campaign_intro", "arguments_choice_cancel_1",
            destination_id, "arguments_choice_cancel_2", *_arguments,
            "arguments_end"]


def connecting() -> List[str]:
    """ IVR connecting User to MEP """
    return ["connect_connecting"]


def no_input() -> List[str]:
    """ IVR there was no input """
    return ["generic_no_input"]


def try_again_later() -> List[str]:
    """ IVR try again later """
    return ["connect_try_again_later", "generic_goodbye"]


def wrong_input() -> List[str]:
    """ IVR there was wrong input for the current menu """
    return ["generic_invalid_input"]


def silence() -> List[str]:
    """ IVR silence helper function """
    return ["0.1_silence"]


def mep_unavailable_new_suggestion(*, destination_id: str,
                                   group_id: Optional[str] = None,
                                   ) -> List[str]:
    """ IVR MEP is unavailable, we make a new suggestion """
    grp = []
    if group_id:
        grp = ["connect_alternative_2", _group_filename(group_id)]
    return ["connect_unavailable", "connect_alternative_1", destination_id,
            *grp, "connect_alternative_3"]


def mep_unavailable_try_again_later() -> List[str]:
    """ IVR MEP is unavailable we ask to try again later """
    return ["connect_unavailable", "connect_try_again_later",
            "generic_goodbye"]


def we_will_call_again() -> List[str]:
    """ IVR MEP is unavailable we ask to try again later """
    return ["connect_will_retry", "generic_goodbye"]


def postpone_menu(*, today: int,
                  is_postponed: bool,
                  others_scheduled: bool,
                  next_day: Optional[int] = None) -> List[str]:
    """ IVR postpone menu with choices """

    today_weekday = f"weekday_{today}"
    if others_scheduled:
        if not next_day:
            raise ValueError(
                "next_day is required when others_scheduled is True")
        next_weekday = f"weekday_{next_day}"
        call_next_planned_at = ["postpone_choice_other_scheduled_1",
                                next_weekday,
                                "postpone_choice_other_scheduled_2"]
    else:
        call_next_planned_at = ["postpone_choice_next_week"]

    postpone_snooze = [] if is_postponed else ["postpone_choice_snooze"]

    return [*postpone_snooze, *call_next_planned_at,
            "postpone_choice_delete_1", today_weekday,
            "postpone_choice_delete_2"]


def postpone_skipped() -> List[str]:
    """ IVR postpone was skipped """
    return ["postpone_skipped"]


def postpone_snoozed() -> List[str]:
    """ IVR postpone was snoozed """
    return ["postpone_snoozed"]


def delete_menu(*, day: int) -> List[str]:
    """ IVR delete menu """
    return ["delete_has_others", "delete_choice_all", "delete_choice_this_1",
            f"weekday_{day}", "delete_choice_this_2"]


def deleted_all_scheduled_calls() -> List[str]:
    """ IVR response if all scheduled calls were deleted """
    return ["delete_all_deleted", "generic_goodbye"]


def deleted_todays_scheduled_call(*, day: int) -> List[str]:
    """ IVR response if todays scheduled calls were deleted """
    return ["delete_this_deleted_1", f"weekday_{day}", "delete_this_deleted_2",
            "generic_goodbye"]
