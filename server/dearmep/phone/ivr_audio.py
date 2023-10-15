import re
from enum import Enum
from pathlib import Path
from random import shuffle
from typing import Optional

from pydantic import UUID4
from sqlmodel import Session

from ..convert import blobfile
from ..database import query


class CallType(Enum):
    instant = "instant"
    scheduled = "scheduled"


class Flow(Enum):
    main_menu = "main_menu"
    connecting = "connecting"
    new_suggestion = "new_suggestion"
    mep_unavailable = "mep_unavailable"
    try_again_later = "try_again_later"
    arguments = "arguments"


class Medialist:
    """
    Instantiate this class with the folder where the audio files are stored
    and the fallback language.
    """
    def __init__(
            self,
            folder: Path,
            fallback_language: str,
    ):
        self.folder = folder
        self.fallback_language = fallback_language

    def group_filename(self, group_id: str):
        return "group_" + re.sub(
            r"[^a-zA-Z]", "_",
            re.sub(r"^G:", "", group_id)
        ).lower()

    def get(
        self,
        flow: Flow,
        destination_id: str,
        call_type: CallType,
        session: Session,
        language: str,
        group_id: Optional[str] = None,
    ) -> UUID4:
        """
        Function to wrap the creation of the medialist. Returns the
        medialist_id for the given flow. This medialist_id can be given to the
        ffmpeg concat endpoint in `elks.get_concatenated_media` to play the
        flow to the user in IVR or play responses.
        """
        destination_name = destination_id  # for readability
        languages = (language, self.fallback_language, "")  # "" string needed

        if call_type == CallType.instant:
            if flow == Flow.main_menu:
                names = [
                    "campaign_greeting",
                    "main_choice_instant_1",
                    destination_name,
                    "main_choice_instant_2",
                    "main_choice_arguments",
                ]
            elif flow == Flow.connecting:
                names = [
                    "connect_connecting",
                ]
            elif flow == Flow.new_suggestion:
                names = [
                    "connect_unavailable",
                    "connect_alternative_1",
                    destination_name,
                ]
                if group_id:
                    names.extend(
                        [
                            "connect_alternative_2",
                            self.group_filename(group_id)
                        ]
                    )
                names.extend(["connect_alternative_3"])
            elif flow == Flow.mep_unavailable:
                names = [
                    "connect_unavailable",
                    "connect_try_again_later",
                    "generic_goodbye",
                ]
            elif flow == Flow.try_again_later:
                names = [
                    "connect_try_again_later",
                    "generic_goodbye",
                ]
            elif flow == Flow.arguments:
                arguments = [
                    "argument_1",
                    "argument_2",
                    "argument_3",
                    "argument_4",
                    "argument_5",
                    "argument_6",
                    "argument_7",
                    "argument_8"]
                shuffle(arguments)
                names = [
                    "arguments_campaign_intro",
                    "arguments_choice_cancel_1",
                    destination_name,
                    "arguments_choice_cancel_2",
                    "argument_extra",
                    *arguments,
                    "arguments_end",
                ]
            else:
                raise ValueError(
                    "Flow name not found. "
                    "Please check the flow name and try again. "
                    f"Allowed flow: {list(Flow)}"
                )
        elif call_type == CallType.scheduled:
            raise NotImplementedError(
                "Scheduled calls are not implemented."
            )
        else:
            raise ValueError(
                "call_type not found. Please check the name again. "
                "Allowed call_type: instant"
            )

        medialist = blobfile.get_blobs_or_files(
            names=names,
            session=session,
            folder=self.folder,
            languages=languages,
            suffix=".ogg",
        )
        medialist_id = query.store_medialist(
            format="ogg",
            mimetype="audio/ogg",
            items=medialist,
            session=session
        )
        return medialist_id
