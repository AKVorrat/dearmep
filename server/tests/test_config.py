from typing import Callable

from fastapi import FastAPI
from pydantic import ValidationError
import pytest
from yaml.parser import ParserError

from dearmep.config import Config, FrontendStrings, L10nConfig, L10nEntry, \
    L10nStrings


@pytest.fixture
def dummy_translation_strings() -> L10nStrings:
    return L10nStrings.parse_obj({
        k: "foo"
        for k in L10nStrings.__fields__.keys()
    })


@pytest.fixture
def dummy_frontend_strings() -> FrontendStrings:
    return FrontendStrings.parse_obj({
        "title": L10nEntry.parse_obj("foo"),
        "languages.de": "Deutsch",
        "languages.en": "English",
        "languages.fr": "Français",
    })


def test_default_language_in_language_list():
    with pytest.raises(ValidationError) as e_info:
        L10nConfig(
            languages=["en", "de"],
            default_language="fr",
        )
    errs = e_info.value.errors()
    assert len(errs) == 3
    assert errs[0]["loc"] == ("default_language",)
    assert errs[0]["type"] == "value_error"
    assert errs[0]["msg"].find(" needs to be in the list of available ") != -1
    for pos, k in enumerate(("frontend_strings", "strings"), start=1):
        assert errs[pos]["loc"] == (k,)
        assert errs[pos]["type"] == "value_error.missing"


def test_missing_translation_in_default_language(
    dummy_frontend_strings: FrontendStrings,
    dummy_translation_strings: L10nStrings,
):
    # Replace one of the dummies with one that only has French.
    dummy_translation_strings.phone_number_verification_sms = (
        L10nEntry.parse_obj({"fr": "toto"}))
    with pytest.raises(ValidationError) as e_info:
        L10nConfig(
            languages=["en", "fr"],
            default_language="en",
            frontend_strings=dummy_frontend_strings,
            strings=dummy_translation_strings,
        )
    errs = e_info.value.errors()
    assert len(errs) == 1
    assert errs[0]["loc"] == ("strings",)
    assert errs[0]["type"] == "value_error"
    assert errs[0]["msg"].find(" needs a translation in the default ") != -1


def test_invalid_default_language(
    dummy_frontend_strings: FrontendStrings,
    dummy_translation_strings: L10nStrings,
):
    with pytest.raises(ValidationError) as e_info:
        L10nConfig(
            languages=["en"],
            default_language="",
            frontend_strings=dummy_frontend_strings,
            strings=dummy_translation_strings,
        )
    errs = e_info.value.errors()
    assert len(errs) == 1
    assert errs[0]["loc"] == ("default_language",)
    assert errs[0]["type"] == "value_error.str.regex"


def test_access_config_without_loading():
    with pytest.raises(
        Exception,
        match=r"attempt to access config without loading it",
    ):
        Config.get()


@pytest.mark.config_path("/this/path/should/not/exist/on/any/sane/system")
def test_config_not_found(fastapi_factory: Callable[[], FastAPI]):
    with pytest.raises(ValidationError) as e_info:
        fastapi_factory()
    errs = e_info.value.errors()
    assert len(errs) == 1
    assert errs[0]["loc"] == ("config_file",)
    assert errs[0]["type"] == "value_error.path.not_exists"


# Syntactically invalid YAML.
@pytest.mark.config_content(b"foo: [ bar\n")
def test_invalid_yaml(fastapi_factory: Callable[[], FastAPI]):
    with pytest.raises(ParserError):
        fastapi_factory()


# YAML is syntactically okay, but missing necessary values.
@pytest.mark.config_content(b"foo: [ bar ]\n")
def test_invalid_config(fastapi_factory: Callable[[], FastAPI]):
    with pytest.raises(ValidationError):
        fastapi_factory()
