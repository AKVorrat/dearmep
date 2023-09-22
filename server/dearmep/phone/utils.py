import requests
import logging

from typing import List, Tuple
from random import choice

from .models import Number

from ..config import Language

logger = logging.getLogger(__name__)


def choose_from_number(
        phone_numbers: List[Number],
        language: Language
) -> Number:
    """
    Returns a phonenumber, preferably from the given language.
    In case a local country number does not exist,
    returns any international number.
    """

    lang_numbers = [nr for nr in phone_numbers if nr.country == language]

    if len(lang_numbers) == 0:
        return choice(phone_numbers)

    return choice(lang_numbers)


def get_numbers(
        phone_numbers: List[Number],
        auth: Tuple[str, str]
) -> List[Number]:
    """
    Fetches all available numbers of an account at 46elks.
    """

    response = requests.get(
        url="https://api.46elks.com/a1/numbers",
        auth=auth
    )
    if response.status_code != 200:
        raise Exception(
            "Could not fetch numbers from 46elks. "
            f"Their http status: {response.status_code}")

    phone_numbers.extend(
        [Number.parse_obj(number) for number in response.json().get("data")]
    )
    logger.info(
        "Currently available 46elks phone numbers: "
        f"{[number.number for number in phone_numbers]}",
    )

    return phone_numbers
