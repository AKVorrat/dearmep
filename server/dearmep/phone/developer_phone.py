from logging import getLogger

from .abstract import AbstractPhoneService
from ..models import PhoneNumber

_logger = getLogger(__name__)


class DeveloperPhoneService(AbstractPhoneService):
    """
    A phone service implementation that can be used while
    developing/debugging an application. This implementation is always
    in dry run mode and logs the simulated actions with the default
    Python logging framework at the INFO level.
    """

    def send_sms(self, recipient: PhoneNumber, content: str) -> None:
        """
        Show a [SMS] log file message
        """
        _logger.info(f"[SMS] {recipient}: {content}")

    def establish_call(self, caller: PhoneNumber, callee: PhoneNumber) -> None:
        _logger.info(f"[CALL] {caller} <-> {callee} simulated")
