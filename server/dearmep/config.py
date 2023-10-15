import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union

import yaml
from pydantic import AnyHttpUrl, BaseModel, BaseSettings, DirectoryPath, \
    Field, FilePath, PositiveInt, ValidationError, validator
from pydantic.fields import ModelField
from pydantic.utils import deep_update
from yaml.parser import ParserError

from .models import Language

_logger = logging.getLogger(__name__)


APP_NAME = "DearMEP"
CMD_NAME = APP_NAME.lower()
ENV_PREFIX = f"{APP_NAME.upper()}_"


EMBEDDED_STATIC_DIR: Optional[Path] = Path(
    Path(__file__).parent, "static_files", "static")
if EMBEDDED_STATIC_DIR and not EMBEDDED_STATIC_DIR.is_dir():
    EMBEDDED_STATIC_DIR = None


class ConfigNotLoaded(Exception):
    pass


class IPRateLimits(BaseModel):
    ip_limit: str
    small_block_limit: str
    large_block_limit: str


class CorsConfig(BaseModel):
    """Allowed access for other web hosts to this backend via Ajax"""
    origins: List[Union[Literal["*"], AnyHttpUrl]]


class APIRateLimitConfig(BaseModel):
    simple: IPRateLimits
    computational: IPRateLimits
    sms: IPRateLimits


class APIConfig(BaseModel):
    base_url: AnyHttpUrl
    cors: CorsConfig
    rate_limits: APIRateLimitConfig


class ElksConfig(BaseModel):
    provider_name: Literal["46elks"]
    username: str
    password: str
    allowed_ips: Tuple[str, ...]


class SecretsConfig(BaseModel):
    pepper: str


class SessionConfig(BaseModel):
    max_logins: PositiveInt
    max_logins_cutoff_days: PositiveInt
    max_unused_codes: PositiveInt


class AuthenticationConfig(BaseModel):
    secrets: SecretsConfig
    session: SessionConfig


class FeedbackConfig(BaseModel):
    token_timeout: PositiveInt


class ContactTimespanFilterTimespan(BaseModel):
    start: date
    end: date

    @validator("end")
    def end_not_before_start(cls, v: date, values: Dict[str, date]) -> date:
        if v < values["start"]:
            raise ValueError("end date cannot be before start date")
        return v


class ContactTimespanFilterConfig(BaseModel):
    types: List[str]
    default: str
    timespans: Dict[str, List[ContactTimespanFilterTimespan]]


class DatabaseConfig(BaseModel):
    url: str  # AnyUrl requires a host, which doesn't apply for SQLite.


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


class FrontendStrings(BaseModel):
    __root__: Dict[str, L10nEntry]


class L10nStrings(BaseModel):
    campaign_name: L10nEntry
    phone_number_verification_sms: L10nEntry


class L10nConfig(BaseModel):
    languages: List[Language]
    default_language: Language
    geo_mmdb: Optional[FilePath]
    frontend_strings: FrontendStrings
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

    @validator("frontend_strings", "strings")
    def every_string_must_be_available_in_default_language(
        cls,
        v: Union[FrontendStrings, L10nStrings],
        field: ModelField,
        values: Dict[str, Any],
    ):
        if "default_language" not in values:
            # Validation of `default_language` probably failed, skip.
            return v
        default = values["default_language"]
        d = v.dict()
        for k, entry in d.get("__root__", d).items():
            if isinstance(entry, dict) and default not in entry:
                src = "l10n" if field.name == "strings" else "frontend"
                raise ValueError(
                    f"{src} string '{k}' needs a translation in the default "
                    f"language ('{default}')"
                )
        return v

    @validator("frontend_strings")
    def every_language_must_have_a_name(
        cls,
        v: FrontendStrings,
        values: Dict[str, Any],
    ) -> FrontendStrings:
        languages: List[Language] = values["languages"]
        for lang in languages:
            lang_key = f"languages.{lang}"
            if lang_key not in v.__root__:
                raise ValueError(
                    f'missing name for language "{lang}" ("frontend_strings" '
                    f'should have a key "{lang_key}")'
                )
            # We also recommend the language names to _not_ have sub-dicts for
            # translation. That way, the language name can be _in_ the very
            # language that it signifies. However, if campaigns want to go
            # against that recommendation and translate language names, they
            # are free to do so, which is why we're not checking it here.
        return v


class TelephonyConfig(BaseModel):
    allowed_calling_codes: List[int]
    approved_numbers: List[str] = []
    blocked_numbers: List[str] = []
    dry_run: bool = False
    phone_call_threshhold: PositiveInt
    provider: ElksConfig
    audio_source: Path
    test_call: Optional[str]


class Config(BaseModel):
    """The main application configuration supplied via the config file."""
    api: APIConfig
    authentication: AuthenticationConfig
    contact_timespan_filter: Optional[ContactTimespanFilterConfig]
    database: DatabaseConfig
    feedback: FeedbackConfig
    l10n: L10nConfig
    telephony: TelephonyConfig

    _instance: ClassVar[Optional["Config"]] = None
    _patch: ClassVar[Optional[Dict]] = None

    @classmethod
    def get(cls) -> "Config":
        """Get the singleton configuration object instance."""
        if cls._instance is None:
            raise ConfigNotLoaded("attempt to access config without loading "
                                  "it first; this is a bug")
        return cls._instance

    @classmethod
    def load(cls) -> "Config":
        """Try to load the config as specified in the environment."""
        try:
            settings = Settings()
        except ValidationError as e:
            if is_config_missing(e):
                _logger.exception(
                    "The configuration file was not found. This usually means "
                    f"that you did not set the {ENV_PREFIX}CONFIG environment "
                    "variable to the config file name, or its path is "
                    "incorrect.",
                )
            raise
        return cls.load_yaml_file(settings.config_file)

    @classmethod
    def load_dict(cls, obj: Dict) -> "Config":
        if cls._patch:
            obj = deep_update(obj, cls._patch)
        try:
            cls._instance = cls.parse_obj(obj)
        except ValidationError:
            _logger.exception(
                "Your config file is correct YAML, but did not pass semantic "
                "validation.",
            )
            raise
        return cls._instance

    @classmethod
    def load_yaml_file(cls, filename: Path) -> "Config":
        with filename.open("r") as f:
            try:
                yaml_dict = yaml.load(f, yaml.Loader)
            except ParserError:
                _logger.exception(
                    "There was an error loading your YAML config.",
                )
                raise
            return cls.load_dict(yaml_dict)

    @classmethod
    def set_patch(cls, patch: Optional[Dict]):
        cls._patch = patch

    @classmethod
    def strings(cls) -> L10nStrings:
        return cls.get().l10n.strings


class Settings(BaseSettings):
    """Settings supplied via environment variables."""
    config_file: FilePath = Field(
        "config.yaml",
        env={f"{ENV_PREFIX}CONFIG", f"{ENV_PREFIX}CONFIG_FILE"},  # allow both
    )
    demo_page: bool = Field(
        False,
        description="Whether to return a HTML demo skeleton at the root path. "
        f"This setting is ignored unless {ENV_PREFIX}STATIC_FILES_DIR is also "
        "provided.",
    )
    static_files_dir: Optional[DirectoryPath] = Field(
        EMBEDDED_STATIC_DIR,
        description="Path to a directory that will be served as static files. "
        "Normally, this is used to let this application serve the front end.",
    )
    markdown_files_dir: Optional[DirectoryPath] = Field(
        description="Path to a directory to serve multilingual Markdown "
        "files.",
    )

    class Config:
        env_prefix = ENV_PREFIX

    @validator("static_files_dir", "markdown_files_dir", pre=True)
    def empty_string_is_none(cls, v):
        return None if v == "" else v


def is_config_missing(e: ValidationError):
    """Check whether e means that the config is missing."""
    cfg_errs = (err for err in e.errors() if err["loc"] == ("config_file",))
    for err in cfg_errs:
        if err["type"] in (
            "value_error.path.not_exists", "value_error.path.not_a_file",
        ):
            return True
    return False


def included_file(name: str) -> Path:
    return Path(Path(__file__).parent, name)


@lru_cache(maxsize=1000)
def all_frontend_strings(language: Language) -> Dict[str, str]:
    """Get all frontend strings, if possible in the given language.

    If a given string has not been translated to the requested language, it
    will be returned in the default language instead.
    """
    return {
        k: entry.for_language(language)
        for k, entry in Config.get().l10n.frontend_strings.__root__.items()
    }
