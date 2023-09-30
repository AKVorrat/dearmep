from typing import Tuple

import pytest

from dearmep.models import UserPhone


@pytest.mark.parametrize("number", (
    ("+49"),
    ("ring ring ring ring ring ring ring bananaphone"),
))
def test_invalid_format(number: str):
    with pytest.raises(ValueError):
        UserPhone(number)


# TODO: These tests assume that the configured pepper is `CHANGE ME`. They
# should instead probably patch the config and set their own.
@pytest.mark.parametrize("number,hash", (
    ("+49621123456", "Hg2QmiDdgr1cZhA4zpjrhyJ5jwKcHgzBo85nf0Ovjvc="),
    ("+49 (0621) 1234-56", "Hg2QmiDdgr1cZhA4zpjrhyJ5jwKcHgzBo85nf0Ovjvc="),
))
def test_valid_format(number: str, hash: str, fastapi_app):
    up = UserPhone(number)
    assert up.hash == hash


@pytest.mark.parametrize("number,prefix,countries", (
    ("+49621123456", 49, ("DE",)),
    ("+396123456", 39, ("IT", "VA")),
))
def test_country(number: str, prefix: int, countries: Tuple[str], fastapi_app):
    up = UserPhone(number)
    assert up.calling_code == prefix
    assert up.country_codes == countries
