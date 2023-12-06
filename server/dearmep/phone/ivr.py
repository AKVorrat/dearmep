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


def main_menu(*, destination_id: str) -> List[str]:
    """ IVR main menu, greeting and present choices """
    return ["campaign_greeting", "main_choice_instant_1", destination_id,
            "main_choice_instant_2", "main_choice_arguments"]


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
