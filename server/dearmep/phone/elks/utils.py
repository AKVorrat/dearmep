import logging
from random import choice
from typing import List, Tuple

import requests

from ...config import Language
from .models import Number

_logger = logging.getLogger(__name__)


def choose_from_number(
        user_number_prefix: str,
        user_language: Language,
        phone_numbers: List[Number],
) -> Number:
    """
    Returns a phonenumber we use to call the user. Preferably from the same
    country as the users number. In case a local country number does not exist,
    it falls back on the users language. In case there is no match it returns
    any international number.
    """

    number_prefix = [n for n in phone_numbers
                     if n.number[1:3] == user_number_prefix]
    if number_prefix:
        return choice(number_prefix)

    lang_numbers = [n for n in phone_numbers if n.country == user_language]
    if lang_numbers:
        return choice(lang_numbers)

    return choice(phone_numbers)


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
    _logger.info(
        "Currently available 46elks phone numbers: "
        f"{[number.number for number in phone_numbers]}",
    )

    return phone_numbers
