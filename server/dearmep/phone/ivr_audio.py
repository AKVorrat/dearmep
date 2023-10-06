from typing import Tuple, Union, Literal, Optional
from dataclasses import dataclass


@dataclass
class Flows:
    """ A class to hold the flows for the IVR """
    def instant(self, flow: Union[
                Literal["main_menu"],
                Literal["connecting"],
                Literal["mep_unavailable"],
                Literal["try_again_later"]
                ],
                destination_id: str,
                group_id: Optional[str] = None
                ) -> Tuple[str, ...]:
        """
        Returns a tuple of strings representing the audio snippet Ids
        to be played for the instant flow.
        Order matters here. The first element is the first to be played.
        """

        if flow == "main_menu":
            return (
                "campaign_greeting",
                "main_choice_instant_1",
                f"destination-{destination_id}",
                "main_choice_instant_2",
                "main_choice_arguments",
            )
        if flow == "connecting":
            return (
                "connect_connecting",
            )
        if flow == "mep_unavailable":
            return (
                "connect_unavailable",
                "connect_alternative_1",
                f"destination-{destination_id}",
                "connect_alternative_2",
                "group",  # TODO Group
                "connect_alternative_3",
            )
        if flow == "try_again_later":
            return (
                "connect_try_again_later",
                "generic_goodbye",
            )

    def __new__(cls):
        raise NotImplementedError(
            "This class cannot be instantiated. "
            "Use the static methods instead"
        )
