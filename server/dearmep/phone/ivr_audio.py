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
    mep_unavailable = "mep_unavailable"
    try_again_later = "try_again_later"
    arguments = "arguments"


groups = {
    "G:Verts/ALE": "group_verts_ale",
    "G:ECR": "group_ecr",
    "G:PPE": "group_ppe",
    "G:S&D": "group_s_d",
    "G:RE": "group_re",
    "G:NA": "group_na",
    "G:GUE/NGL": "group_gue_ngl",
    "G:ID": "group_id",
}


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

    def get(self, *args, **kwargs):
        return self._medialist_id(*args, **kwargs)

    def _medialist_id(
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

        if group_id:
            group = groups[group_id]

        if call_type == CallType.instant:
            if flow == Flow.main_menu:
                names = (  # type: ignore
                    "campaign_greeting",
                    "main_choice_instant_1",
                    destination_name,
                    "main_choice_instant_2",
                    "main_choice_arguments",
                )
            elif flow == Flow.connecting:
                names = (  # type: ignore
                    "connect_connecting",
                )
            elif flow == Flow.mep_unavailable:
                names = (  # type: ignore
                    "connect_unavailable",
                    "connect_alternative_1",
                    destination_name,
                    "connect_alternative_2",
                    group,
                    "connect_alternative_3",
                )
            elif flow == Flow.try_again_later:
                names = (  # type: ignore
                    "connect_try_again_later",
                    "generic_goodbye",
                )
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
                names = (  # type: ignore
                    "arguments_campaign_intro",
                    "arguments_choice_cancel_1",
                    destination_name,
                    "arguments_choice_cancel_2",
                    "argument_extra",
                    *arguments,
                    "arguments_end",
                )
            else:
                raise ValueError(
                    "Flow name not found. "
                    "Please check the flow name and try again. "
                    f"Allowed names: {list(Flow)}"
                )
        elif call_type == CallType.scheduled:
            raise NotImplementedError(
                "Scheduled calls are not implemented."
            )
        else:
            raise ValueError(
                "call_type not found. Please check the name again. "
                "Allowed names: instant"
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
