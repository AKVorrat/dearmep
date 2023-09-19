from .elks import phone_numbers, Number
from ..config import Language
from random import choice

def choose_from_number(language: Language) -> Number:
    """
    Returns a phonenumber, preferably from the given language.
    In case a local country number does not exist,
    returns any international number.
    """

    lang_numbers = [nr for nr in phone_numbers if nr.country == language]

    if len(lang_numbers) == 0:
        return choice(phone_numbers)

    return choice(lang_numbers)
