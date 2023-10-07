from typing import Tuple, Literal, Optional
from pydantic import UUID4
from pathlib import Path

from dearmep.database.connection import get_session
from dearmep.database import query
from dearmep.convert import blobfile

Flow = Literal[
    "main_menu",
    "connecting",
    "mep_unavailable",
    "try_again_later"
]


def medialist_id(
    flow: Flow,
    destination_id: str,
    call_type: Literal["instant", "scheduled"],
    group_id: Optional[str] = None,
    languages: Tuple[str, ...] = ("de", "en", ""),
    folder: Path = Path("/home/v/dearmep-infos/ivr_audio"),
) -> UUID4:
    """
    Function to wrap the creation of the medialist.
    Returns the medialist_id for the given flow. This medialist_id can be given
    to the ffmpeg concat endpoint in `elks.get_concatenated_media` to play the
    flow to the user in IVR or play responses.
    """

    if call_type == "instant":
        if flow == "main_menu":
            names = (  # type: ignore
                "campaign_greeting",
                "main_choice_instant_1",
                f"destination-{destination_id}",
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
                f"destination-{destination_id}",
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

    with get_session() as session:
        medialist = blobfile.get_blobs_or_files(
            names=names,
            session=session,
            folder=folder,
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
