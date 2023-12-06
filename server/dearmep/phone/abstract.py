from abc import ABC, abstractmethod
from typing import Union

from ..config import Config
from ..database.connection import Session
from ..database.models import DestinationID
from ..models import CallState, CallType, DestinationInCallResponse, \
    Language, PhoneNumber, SMSSenderName, UserInCallResponse


class AbstractPhoneService(ABC):
    @abstractmethod
    def send_sms(
        self,
        *,
        recipient: PhoneNumber,
        content: str,
        sender: SMSSenderName,
    ) -> None:
        """
        Send a SMS to a phone with a given number.
        """
        pass

    @abstractmethod
    def establish_call(
        self,
        *,
        user_phone: PhoneNumber,
        destination_id: DestinationID,
        type_of_call: CallType,
        language: Language,
        session: Session,
    ) -> Union[CallState, DestinationInCallResponse, UserInCallResponse]:
        """
        Establish a call between our user and a destination.
        """
        pass


def get_phone_service() -> AbstractPhoneService:
    if Config.get().telephony.dry_run:
        from .developer_phone import DeveloperPhoneService
        return DeveloperPhoneService()
    else:
        from .elks_phone import ElksPhoneService
        return ElksPhoneService()
