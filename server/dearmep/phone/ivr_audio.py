from typing import Literal, Optional
from pydantic import UUID4
from pathlib import Path
from sqlmodel import Session

from dearmep.models import Language
from dearmep.database import query
from dearmep.convert import blobfile

Flow = Literal[
    "main_menu",
    "connecting",
    "mep_unavailable",
    "try_again_later"
]


class Medialist:
    """
    Instantiate this class with the folder where the audio files are stored
    and the fallback language.
    """
    def __init__(
            self,
            folder: Path,
            fallback_language: Language,
    ):
        self.folder = folder
        self.fallback_language = fallback_language

    def get(self, *args, **kwargs):
        return self._medialist_id(*args, **kwargs)

    def _medialist_id(
        self,
        flow: Flow,
        destination_id: str,
        call_type: Literal["instant", "scheduled"],
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

        if call_type == "instant":
            if flow == "main_menu":
                names = (  # type: ignore
                    "campaign_greeting",
                    "main_choice_instant_1",
                    destination_name,
                    "main_choice_instant_2",
                    "main_choice_arguments",
                )
            elif flow == "connecting":
                names = (  # type: ignore
                    "connect_connecting",
                )
            elif flow == "mep_unavailable":
                names = (  # type: ignore
                    "connect_unavailable",
                    "connect_alternative_1",
                    destination_name,
                    "connect_alternative_2",
                    "group",  # TODO Group
                    "connect_alternative_3",
                )
            elif flow == "try_again_later":
                names = (  # type: ignore
                    "connect_try_again_later",
                    "generic_goodbye",
                )

        try:
            assert names
        except UnboundLocalError:
            raise ValueError(
                "Flow name not found. "
                "Please check the flow name and try again. "
                f"Allowed names: {Flow.__args__}"  # type: ignore
            )

        # with get_session() as session:
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
