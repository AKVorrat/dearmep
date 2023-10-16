from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import pytest
from sqlmodel import Session

from dearmep.config import Config
from dearmep import l10n


TEST_MMDB = str(Path(Path(__file__).parent, "geo_ip", "test.mmdb"))


@pytest.mark.parametrize("header,expected", [
    ("en-US,en;q=0.7,de;q=0.3", ["en-US", "en", "de"]),
    ("en;q=0.7,en-US,de;q=0.3", [  # sorting should stay the same
        "en-US", "en", "de",
    ]),
    ("pt;gonzo=5", ["pt"]),  # option which is not a q-value
    ("en", ["en"]),
    ("pt;q=0.5,en;q=9000", ["en", "pt"]),  # invalid q-value equals 1.0
    ("", []),  # empty Accept-Language header
    ("  ", []),  # some spaces? still empty
    ("de, , en", ["de", "en"]),  # ignore empty blocks
])
def test_parse_accept_language(header: str, expected: List[str]):
    assert l10n.parse_accept_language(header) == expected


@pytest.mark.parametrize("prefs,available,fallback,expected", [
    (["de-de", "en"], ["de-DE-1996", "en-US"], None, "de-DE-1996"),
    (["de-de", "en-GB"], ["de-AT", "en-US"], "", ""),
    (["de-de", "en-GB", "*"], ["de-AT", "en-US"], None, "de-AT"),
    (["de-de", "en"], ["de-AT", "en-US"], "", "en-US"),
    (["de-de", "en", "*"], ["de-AT", "en-US"], None, "en-US"),
    (["de-de", "de", "en", "*"], ["de-AT", "de-DE", "en-US"], None, "de-DE"),
    (["de-de", "tlh"], ["de-AT", "de-DE", "en-US"], None, "de-DE"),
    (["de-de", "tlh"], ["de-AT", "en-US"], None, False),
])
def test_find_preferred_language(
    prefs: List[str],
    available: List[str],
    fallback: Optional[str],
    expected: Union[str, Literal[False]],
):
    if expected is False:  # parameter means "expect an exception"
        with pytest.raises(l10n.LanguageNotAvailableException):
            l10n.find_preferred_language(
                prefs=prefs,
                available=available,
                fallback=fallback,
            )
    else:
        assert l10n.find_preferred_language(
            prefs=prefs,
            available=available,
            fallback=fallback,
        ) == expected


def test_find_preferred_with_no_available_languages():
    with pytest.raises(ValueError):
        l10n.find_preferred_language(prefs=["de-DE", "*"], available=[])


@pytest.mark.parametrize("db,ip,expect", [
    # Invalid database file.
    ("", "123.123.123.123", {"country": None, "db_result": None}),
    # Using our test database.
    (TEST_MMDB, "123.123.123.123", {
        "country": "BE", "recommended": None, "db_result": {"country": "be"},
    }),
    (TEST_MMDB, "2a01:4f8:c012:abcd::1", {
        "country": "DE", "recommended": "DE", "db_result": {
            "country": {"iso_code": "de"},
        },
    }),
    (TEST_MMDB, "127.1.2.3", {
        "country": None, "recommended": None, "db_result": {"foo": "bar"},
    }),
    (TEST_MMDB, "1.0.0.1", {
        "country": None, "recommended": None, "db_result": {
            "country": {"iso_code": "None"},
        },
    }),
])
def test_get_country(
    db: str,
    ip: str,
    expect: Dict[str, Any],
    with_example_destinations: Session,
):
    res = l10n.get_country(with_example_destinations, db, ip)
    assert res.ip_address == ip
    for k, v in expect.items():
        assert getattr(res, k) == v


def test_translate_string(fastapi_app):
    template = Config.strings().phone_number_verification_sms
    translated = template.apply({"code": "12345"})
    assert translated == "12345 is your verification code. " \
        "If you think you have received this message in error, simply " \
        "ignore it."
