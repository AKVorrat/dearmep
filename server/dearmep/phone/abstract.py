from abc import ABCMeta

from ..config import Config
from ..models import PhoneNumber


class AbstractPhoneService(metaclass=ABCMeta):
    def send_sms(self, recipient: PhoneNumber, content: str) -> None:
        """
        Send a SMS to a phone with a given number.
        """
        pass

    def establish_call(self, caller: PhoneNumber, callee: PhoneNumber) -> None:
        """
        Establish a call between our user and a destination.
        """
        pass


def get_phone_service() -> AbstractPhoneService:
    if Config.get().telephony.dry_run:
        from .developer_phone import DeveloperPhoneService
        return DeveloperPhoneService()
    else:
        raise NotImplementedError("Live phone operations not implemented yet")
