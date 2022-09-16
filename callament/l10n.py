import re
from typing import List, Optional


Q_VALUE_RE = r"^(?:0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?)$"


class LanguageNotAvailableException(Exception):
    pass


def parse_accept_language(spec: str) -> List[str]:
    """Convert the value of an Accept-Language header to an ordered list."""
    # This will become the resulting list.
    pairs = []

    # First of all, split the user's prefence list by commas.
    prefs = spec.split(",")
    for pref in prefs:
        # There can be an optional "quality value" after the language,
        # delimited by a semicolon and prefixed with `q=`.
        split = pref.strip().split(";")
        # The base language is everything before the first semicolon.
        lang = split[0].strip()
        # If the base language is empty (usually because the whole input string
        # is empty), it makes no sense to use it.
        if lang == "":
            continue

        # To be future-proof, iterate over the other parts and look for one
        # starting with `q=`. Default to 1.0 if there is none.
        q = 1.0
        for option in split[1:]:
            k, v = option.strip().split("=")
            if k.strip() == "q":
                v = v.strip()
                if re.match(Q_VALUE_RE, v):
                    q = float(v)

        pairs.append((lang, q))

    pairs.sort(reverse=True, key=lambda pair: pair[1])
    # Cut off the q-value, the caller is probably not interested in it.
    return [pair[0] for pair in pairs]


def find_preferred_language(
    *,
    prefs: List[str],
    available: List[str],
    fallback: Optional[str] = None,
) -> str:
    """From a list of available languages, select the one most preferred.

    The preferences list should be ordered with the most preferred language
    first, just like `parse_accept_language` returns it.

    The matching is performed as described under "Basic Filtering" (section
    3.3.1) in RFC 4647: Either the preference matches an available language
    exactly, or the preference is a prefix of an available language (e.g.
    `de-de` would match `de-DE-1996`). Matching is case insensitive.

    If no preferred language is available, either return the fallback (if
    specified), or raise a LanguageNotAvailableExecption. However, if there is
    an asterisk `*` in the preferences, the first item in `available` will be
    selected instead of the fallback or raising an exception.
    """
    if not len(available):
        raise ValueError("there should be at least one available language")

    for preference in prefs:
        preference = preference.lower()

        # Look for an exact match.
        for av in available:
            if preference == av.lower():
                return av

        # If there was no exact match, try a prefix match.
        prefix = f"{preference}-"
        for av in available:
            if av.lower().startswith(prefix):
                return av

    # No available language matched. If the wildcard is accepted, use the first
    # available language.
    if "*" in prefs:
        return available[0]

    # If there is a fallback, return that. Else, raise an exception.
    if fallback is not None:
        return fallback

    raise LanguageNotAvailableException(
        "none of the preferred languages are available")
