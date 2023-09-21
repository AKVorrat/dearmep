from dearmep.config import Language
from dearmep.database.models import Contact
from pydantic import BaseModel
from typing import Literal
from .models import InitialElkResponseState
from datetime import datetime


class OngoingCall(BaseModel):
    provider: str = "46elks"
    callid: str
    created: datetime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: str
    to_nr: str
    language: Language
    contact: Contact
    # mepid: str


class OngoingCalls:
    # PUT IN OWN FILE

    def __init__(self):
        self.calls = []

    def get_call(self, callid: str) -> OngoingCall:
        """ Get an ongoing call by id """
        try:
            return [x for x in self.calls if x.callid == callid][0]
        except IndexError:
            raise IndexError(f"Could not find ongoing call with id: {callid}")

    def destination_is_on_call(self, destination_id: str) -> bool:
        """ Check if Destination is on a call we control here """
        _calls = [
            x for x in self.calls if x.contact.destination_id == destination_id
        ]
        if len(_calls) > 0:
            return True
        return False

    def append(self, call: OngoingCall):
        """ Append an ongoing call """
        self.calls.append(call)

    def remove(self, callid: str):
        """ Remove an ongoing call """
        self.calls = [x for x in self.calls if x.callid != callid]

    def all(self):
        """ Get all ongoing calls """
        return self.calls

    def __len__(self):
        return len(self.calls)

    def __repr__(self):
        return str(f"<OngoingCalls Instance with {len(self.calls)} Calls>")

    def __str__(self):
        return self.calls
