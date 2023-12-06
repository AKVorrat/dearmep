from logging import getLogger
from typing import Union

from .abstract import AbstractPhoneService
from ..database.connection import Session
from ..database.models import DestinationID
from ..models import CallState, CallType, DestinationInCallResponse, \
    Language, PhoneNumber, SMSSenderName, UserInCallResponse


_logger = getLogger(__name__)


class DeveloperPhoneService(AbstractPhoneService):
    """
    A phone service implementation that can be used while
    developing/debugging an application. This implementation is always
    in dry run mode and logs the simulated actions with the default
    Python logging framework at the INFO level.
    """

    def send_sms(
        self,
        *,
        recipient: PhoneNumber,
        content: str,
        sender: SMSSenderName,
    ) -> None:
        """
        Show a [SMS] log file message
        """
        _logger.info(f"[SMS] {recipient}: {content}")

    def establish_call(
        self,
        *,
        user_phone: PhoneNumber,
        type_of_call: CallType,
        destination_id: DestinationID,
        language: Language,
        session: Session,
    ) -> Union[CallState, DestinationInCallResponse, UserInCallResponse]:
        _logger.info(f"[CALL] {user_phone} <-> {destination_id} simulated")
        return CallState.CALLING_USER
