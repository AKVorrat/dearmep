from typing import List, Tuple

import pytest

from dearmep.models import PhoneRejectReason as Reason, UserPhone


@pytest.mark.parametrize("number", (
    ("+49"),
    ("ring ring ring ring ring ring ring bananaphone"),
))
def test_invalid_format(number: str):
    with pytest.raises(ValueError):
        UserPhone(number)


# TODO: These tests assume that the configured pepper is `CHANGE ME`. They
# should instead probably patch the config and set their own.
@pytest.mark.parametrize("number,e164,hash", ((
    "+49621123456",
    "+49621123456",
    "Hg2QmiDdgr1cZhA4zpjrhyJ5jwKcHgzBo85nf0Ovjvc=",
), (
    "+49 (0621) 1234-56",
    "+49621123456",
    "Hg2QmiDdgr1cZhA4zpjrhyJ5jwKcHgzBo85nf0Ovjvc=",
)))
def test_valid_format(number: str, e164: str, hash: str, fastapi_app):
    up = UserPhone(number)
    assert up.hash == hash
    assert up.original_number is not None
    assert up.format_number(up.original_number) == e164


@pytest.mark.parametrize("number,prefix,countries", (
    ("+49621123456", 49, ("DE",)),
    ("+396123456", 39, ("IT", "VA")),
))
def test_country(number: str, prefix: int, countries: Tuple[str], fastapi_app):
    up = UserPhone(number)
    assert up.calling_code == prefix
    assert up.country_codes == countries


def test_original_number_is_lost(fastapi_app):
    up = UserPhone("+49 (0621) 1234-56")
    assert up.original_number is not None
    assert UserPhone.format_number(up.original_number) == "+49621123456"
    from_json = UserPhone(up)
    assert from_json.original_number is None


@pytest.mark.parametrize("number,reasons", (
    ("+4917567", [Reason.INVALID_PATTERN]),  # too short
    ("+49621123456", [Reason.DISALLOWED_TYPE]),  # landline
    ("+499001774442", [Reason.DISALLOWED_TYPE]),  # service number
    ("+491751234567", []),
    ("+43 680 1234567", []),
    # from disallowed country, but also prefix-blocked in example config
    ("+1-202-501-4444", [Reason.BLOCKED, Reason.DISALLOWED_COUNTRY]),
    # hash-blocked in example config
    ("+491701111111", [Reason.BLOCKED]),
    # hash-approved in example config
    ("+496215555555", []),
))
def test_number_allowed(number: str, reasons: List[Reason], fastapi_app):
    up = UserPhone(number)
    assert up.check_allowed() == reasons
    assert not up.is_allowed() if reasons else up.is_allowed()
