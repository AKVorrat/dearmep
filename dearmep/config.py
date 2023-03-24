from pathlib import Path
import re
from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import BaseModel, BaseSettings, ConstrainedStr, Field, \
                     FilePath, validator
import yaml


APP_NAME = "DearMEP"
ENV_PREFIX = f"{APP_NAME.upper()}_"


class Language(ConstrainedStr):
    regex = re.compile(r"^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{1,8})*$")


class L10nEntry(BaseModel):
    __root__: Union[str, Dict[Language, str]]

    def apply(
        self,
        placeholders: Dict[str, Any] = {},
        language: str = "",
    ) -> str:
        l10nconfig = Config.get().l10n

        # Look for the language from the function argument, or the default.
        # TODO: Use a context-set language?
        lang = Language(language) if language else l10nconfig.default_language

        return self.for_language(lang).format(**{
            "campaign": l10nconfig.strings.campaign_name.for_language(lang),
            **placeholders,
        })

    def for_language(self, language: Language) -> str:
        # If the entry is a simple string, use that.
        if isinstance(self.__root__, str):
            return self.__root__
        # If it's a dict, look up the string for the language. If there isn't
        # one, use the default language's string. The L10nConfig validator
        # guarantees that the fallback exists.
        return self.__root__.get(
            language,
            self.__root__[Config.get().l10n.default_language],
        )


class L10nStrings(BaseModel):
    campaign_name: L10nEntry
    phone_number_verification_sms: L10nEntry


class L10nConfig(BaseModel):
    languages: List[Language]
    default_language: Language
    geo_mmdb: Optional[FilePath]
    strings: L10nStrings

    @validator("default_language")
    def default_language_must_be_in_languages(
        cls,
        v: Language,
        values: Dict[str, Any],
    ):
        if "languages" in values and v not in values["languages"]:
            raise ValueError(
                f"default language '{v}' needs to be in the list of available "
                f"languages: {values['languages']}"
            )
        return v

    @validator("strings")
    def every_string_must_be_available_in_default_language(
        cls,
        v: L10nStrings,
        values: Dict[str, Any],
    ):
        if "default_language" not in values:
            # Validation of `default_language` probably failed, skip.
            return v
        default = values["default_language"]
        for k, entry in v.dict().items():
            if isinstance(entry, dict) and default not in entry:
                raise ValueError(
                    f"l10n string '{k}' needs a translation in the default "
                    f"language ('{default}')"
                )
        return v


class Config(BaseModel):
    """The main application configuration supplied via the config file."""
    l10n: L10nConfig

    _instance: ClassVar[Optional["Config"]] = None

    @classmethod
    def get(cls) -> "Config":
        """Get the singleton configuration object instance."""
        if cls._instance is None:
            raise Exception("attempt to access config without loading it "
                            "first; this is a bug")
        return cls._instance

    @classmethod
    def load_dict(cls, obj: Dict) -> "Config":
        cls._instance = cls.parse_obj(obj)
        return cls._instance

    @classmethod
    def load_yaml_file(cls, filename: Path) -> "Config":
        with filename.open("r") as f:
            return cls.load_dict(yaml.load(f, yaml.Loader))

    @classmethod
    def strings(cls) -> L10nStrings:
        return cls.get().l10n.strings


class Settings(BaseSettings):
    """Settings supplied via environment variables."""
    config_file: FilePath = Field(
        "config.yaml",
        env=f"{ENV_PREFIX}CONFIG",
    )

    class Config:
        env_prefix = ENV_PREFIX