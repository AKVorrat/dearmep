from __future__ import annotations
from base64 import b64encode
import enum
from hashlib import sha256
import json
import re
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Literal, \
    Optional, Set, Tuple, TypeVar

from canonicaljson import encode_canonical_json
import phonenumbers
from pydantic import BaseModel, ConstrainedFloat, ConstrainedInt, \
    ConstrainedStr, Field
from pydantic.generics import GenericModel

if TYPE_CHECKING:
    from .database.connection import Session


T = TypeVar("T")

MAX_SEARCH_RESULT_LIMIT = 20


class CountryCode(ConstrainedStr):
    """An ISO-639 country code."""
    min_length = 2
    max_length = 3
    to_upper = True


class Language(ConstrainedStr):
    regex = re.compile(r"^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{1,8})*$")


class LanguageMixin(BaseModel):
    language: Language = Field(
        description="The language to use for interactions with the User.",
        example="de",
    )


class SearchResultLimit(ConstrainedInt):
    """The number of search results to return."""
    gt = 0
    le = MAX_SEARCH_RESULT_LIMIT


class Score(ConstrainedFloat):
    """A number between 0 and 1, inclusive."""
    ge = 0.0
    le = 1.0


INPUT_NUMBER_REGEX = re.compile(r"^[+0-9./ ()-]+$")


class InputPhoneNumber(ConstrainedStr):
    """An international phone number, as input by a User.

    This class is somewhat lenient regarding the format it accepts, but still
    strict enough to allow converting the number into a (canonicalized, E.164)
    `PhoneNumber`.
    """
    max_length = 32  # should allow enough superfluous characters
    regex = INPUT_NUMBER_REGEX


class PhoneNumber(ConstrainedStr):
    """An E.164-canonicalized international phone number."""
    max_length = 16
    regex = re.compile(r"^\+[1-9][0-9]{1,14}$")


class PhoneRejectReason(str, enum.Enum):
    """Reasons why a phone number is rejected by the system.

    * `INVALID_PATTERN`: It does not match the validation rules for a number of
      that country. For example, there might be too many or too few digits for
      the given area code.
    * `DISALLOWED_COUNTRY`: The number belongs to a country that has not been
      enabled as being one of the allowed ones.
    * `DISALLOWED_TYPE`: The number is of a type that we do not support, for
      example a landline, pager, or paid service number.
    * `BLOCKED`: This number or some prefix of it has been manually blocked by
      the administrator.
    * `TOO_MANY_VERIFICATION_REQUESTS`: This number has issued too many
      verification requests (each resulting in an SMS message being sent)
      without confirming them.
    """
    INVALID_PATTERN = "INVALID_PATTERN"
    DISALLOWED_COUNTRY = "DISALLOWED_COUNTRY"
    DISALLOWED_TYPE = "DISALLOWED_TYPE"
    BLOCKED = "BLOCKED"
    TOO_MANY_VERIFICATION_REQUESTS = "TOO_MANY_VERIFICATION_REQUESTS"


class UserPhone(str):
    """A User’s phone number, hashed & peppered.

    Since we do not want to store our users’ phone numbers in the database
    unprotected, we store them hashed most of the time, using a JSON
    representation. The numbers are peppered, not salted, so that the same
    number will always result in the same hash. The numbers are normalized
    before hashing; spaces, extra characters and equivalent representations of
    the same number will result in the same hash. In addition to the hash, we
    store the country code of the number, to allow for some statistical
    analysis on the stored numbers.

    This class is based on the standard `str` class and can be used everywhere
    a string can be. Its value is always the normalized JSON representation,
    but you can construct it from a simple string:

    ```
    >>> p = UserPhone("+49 (0621) 12345-678")
    >>> p
    '{"c":49,"h":"SSHdXE1PA9D4s2Aqb/ISR6l7WxwkcchWcWx8QubZRrE=","v":1}'
    ```

    As you can see, the input number is somewhat lenient regarding the format,
    to account for users entering it in a non-standard way.

    You can compare two `UserPhone` objects for equality (their hashes will be
    compared), or compare a `UserPhone` object with a plain string containing a
    phone number (it will be converted to a `UserPhone` on the fly, then its
    hash will be compared).

    ```
    >>> p == "+4962112345678"
    True
    ```

    Note that in order to compare a unhashed phone number to hashed one, you
    have to use the same pepper (set in the config value
    `authentication.secrets.pepper`), else the hashes will not match.

    For convenience, the `UserPhone` instance also provides a `country_codes`
    tuple that tells you the countries this number can belong to. This is not a
    single value, since several countries can share the same prefix, e.g. +39
    can either be Italy or the Vatican City State.
    """

    class Structured(BaseModel):
        class Config:
            allow_mutation = False
            allow_population_by_field_name = True
            arbitrary_types_allowed = True  # for original_number

        version: Literal[1] = Field(1, alias="v")
        hash: str = Field(alias="h")
        calling_code: int = Field(alias="c")
        original_number: Optional[phonenumbers.PhoneNumber] = Field(
            exclude=True,
        )

    ALLOWED_TYPES = {
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
        phonenumbers.PhoneNumberType.MOBILE,
    }

    country_codes: Tuple[CountryCode, ...]
    structured: Structured

    def __new__(cls, value) -> UserPhone:
        # Ensure that we're being initialized from a string.
        if not isinstance(value, str):
            value = str(value)

        # Try parsing as a JSON dict, if it starts with {
        struct: Optional[UserPhone.Structured] = None
        if value.startswith("{"):
            try:
                struct = cls.Structured.parse_obj(json.loads(value))
            except json.JSONDecodeError:
                pass  # Ignore, struct will stay None, number parsing occurs.
        if not struct:
            # Try parsing as a raw phone number.
            number = cls.parse_number(value)
            struct = cls.Structured(
                hash=cls.compute_hash(cls.format_number(number)),
                calling_code=number.country_code,
                original_number=number,
            )

        value = encode_canonical_json(struct.dict(by_alias=True)).decode()

        instance = super(UserPhone, cls).__new__(cls, value)
        object.__setattr__(instance, "country_codes", tuple(map(
            CountryCode,
            phonenumbers.COUNTRY_CODE_TO_REGION_CODE[struct.calling_code])))
        object.__setattr__(instance, "structured", struct)
        return instance

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UserPhone):
            return self.hash == other.hash
        # If it's a simple string, try parsing it as a UserPhone.
        if isinstance(other, str):
            try:
                parsed = UserPhone(other)
                return self.hash == parsed.hash
            except Exception:  # apparently not a phone number
                return False
        # All other things are not equal to us.
        return False

    # Needs to be set explicitly since we define __eq__.
    __hash__ = str.__hash__

    def __setattr__(self, __name: str, __value: Any) -> None:
        raise TypeError(
            "UserPhone is immutable and does not allow item assignment")

    @staticmethod
    def compute_hash(number: str) -> str:
        """Compute the peppered hash of a phone number.

        It is up to the caller to bring this number into a canonical format
        before computing the hash, e.g. using `UserPhone.format_number()`.
        """
        from .config import Config

        hash = sha256(
            f"{Config.get().authentication.secrets.pepper}{number}".encode(),
        )
        return b64encode(hash.digest()).decode()

    @staticmethod
    def format_number(number: phonenumbers.PhoneNumber) -> PhoneNumber:
        """Format a phone number into canonical E.164 form.

        You should use `UserPhone.parse_number()` to convert a phone number
        string into a `phonenumbers.PhoneNumber` object.
        """
        return PhoneNumber(phonenumbers.format_number(
            number, phonenumbers.PhoneNumberFormat.E164))

    @classmethod
    def parse_number(cls, number: str) -> phonenumbers.PhoneNumber:
        """Parse a string into a PhoneNumber instance.

        As `phonenumbers.parse()` is quite lenient, this method employs some
        additional checks.
        """
        if not INPUT_NUMBER_REGEX.fullmatch(number):
            raise ValueError(f"'{number}' does not look like a phone number")
        try:
            parsed = phonenumbers.parse(number, region=None)
        except phonenumbers.NumberParseException as e:
            raise ValueError(f"'{number}' could not be parsed: {e}")
        return parsed

    @property
    def calling_code(self) -> int:
        """Return the international calling prefix of the phone number."""
        return self.structured.calling_code

    @property
    def hash(self) -> str:
        """Return the peppered hash of the original phone number."""
        return self.structured.hash

    @property
    def original_number(self) -> Optional[phonenumbers.PhoneNumber]:
        """Return the original phone number as parsed.

        The original phone number is only available if this instance has been
        created by supplying an unhashed phone number. If it has instead been
        created from a JSON representation, the original number is no longer
        known due to the hashing.
        """
        return self.structured.original_number

    def check_allowed(
        self,
        session: Optional[Session] = None,
    ) -> Set[PhoneRejectReason]:
        """Return reasons why this phone number may not use the application.

        Note that this method is best used on a `UserPhone` instance created
        from an unhashed phone number, not from the JSON representation, since
        only then can additional checks be performed (e.g. whether it is a
        mobile number, whether it might actually exist, etc.).
        """
        from .config import Config
        from .database import query
        from .database.models import BlockReason

        config = Config.get().telephony
        reasons: Set[PhoneRejectReason] = set()

        # Allow if it's been manually approved.
        if self.matches_filter(config.approved_numbers):
            return reasons

        # Fail if it's been manually blocked.
        if self.matches_filter(config.blocked_numbers):
            reasons.add(PhoneRejectReason.BLOCKED)

        # If we can access the database, check if it's blocked there.
        if session:
            if db_reason := query.get_block_reason(session, self):
                if db_reason == BlockReason.TOO_MANY_VERIFICATION_REQUESTS:
                    reasons.add(
                        PhoneRejectReason.TOO_MANY_VERIFICATION_REQUESTS)

        # Fail if it's not in our list of allowed countries.
        if self.calling_code not in config.allowed_calling_codes:
            reasons.add(PhoneRejectReason.DISALLOWED_COUNTRY)

        # Checks that we can only do if the original number is available.
        if number := self.original_number:
            # Fail if it's an invalid number.
            if not phonenumbers.is_valid_number(number):
                reasons.add(PhoneRejectReason.INVALID_PATTERN)
            # Else check the type of the number.
            else:
                type = phonenumbers.number_type(number)
                if type not in self.ALLOWED_TYPES:
                    reasons.add(PhoneRejectReason.DISALLOWED_TYPE)

        return reasons

    def is_allowed(self, session: Optional[Session] = None) -> bool:
        """Check whether this phone number may use the application.

        This is a convenience method that checks whether `check_allowed()`
        returned no reasons for disallowing the phone number, i.e. is empty.
        See that method for usage hints.
        """
        return len(self.check_allowed(session)) == 0

    def matches_filter(self, filter: List[str]) -> bool:
        """Check whether this phone number matches an entry in the list.

        List items may either be raw hashes (not the whole JSON), or a phone
        number prefix like `+49123`. Using a whole number instead of just a
        prefix is fine, too. Phone number entries in the list will be
        normalized to E.164, it's not a simple string comparison.

        However, this instance can only check itself against prefixes if its
        own `original_number` is available. Hash matching will always work.
        """
        orig = self.format_number(self.original_number) \
            if self.original_number else None

        for pattern in filter:
            if self.hash == pattern:
                return True

            # Following checks require original phone number.
            if not orig:
                continue

            # If pattern is a phone number prefix, convert it to E.164 first.
            prefix = None
            try:
                prefix = self.parse_number(pattern)
            except ValueError:
                pass
            if prefix and orig.startswith(self.format_number(prefix)):
                return True

        return False


frontend_strings_field = Field(
    description="A key-value mapping of translation keys to translation "
    "template strings. The template strings can contain placeholders, but "
    "those have to be interpreted by the frontend.",
    example={
        "title": "Call your MEP!",
        "call.start-call-btn.title": "Start Call",
        "veification.description": "We've sent a code to {{ number }}.",
    }
)


class DestinationSearchGroup(BaseModel):
    """One of the groups a Destination belongs to, optimized for display in
    a search result."""
    name: str = Field(
        description="The group's long name, e.g. to display as alt text on "
        "the logo.",
        example="Group of the Progressive Alliance of Socialists and "
        "Democrats in the European Parliament",
    )
    type: str = Field(
        description="The group's type.",
        example="parl_group",
    )
    logo: Optional[str] = Field(
        None,
        description="URL path to the group's logo, if any.",
        example="/api/v1/blob/s-and-d.png",
    )


class DestinationSearchResult(BaseModel):
    """A single Destination returned from a search."""
    id: str = Field(
        description="The Destination's ID.",
        example="36e04ddf-73e7-4af6-a8af-24556d610f6d",
    )
    name: str = Field(
        description="The Destination's name.",
        example="Jakob Maria MIERSCHEID",
    )
    country: Optional[CountryCode] = Field(
        description="The country code associated with this Destination.",
        example="DE",
    )
    groups: List[DestinationSearchGroup] = Field(
        description="The groups this Destination is a member of.",
    )


class FrontendStringsResponse(BaseModel):
    frontend_strings: Dict[str, str] = frontend_strings_field


class LanguageDetection(BaseModel):
    available: List[str] = Field(
        ...,
        description="The list of languages supported by the server.",
        example=["en-GB", "fr-FR", "de"],
    )
    recommended: str = Field(
        ...,
        description="Which of the available languages best matches the user's "
                    "preferences",
        example="en-GB",
    )
    user_preferences: List[str] = Field(
        ...,
        description="The preferences stated by the user, as recognized by the "
                    "server, e.g. via parsing the `Accept-Language` header.",
        example=["en-US", "en", "tlh"],
    )


class LocationDetection(BaseModel):
    available: List[CountryCode] = Field(
        ...,
        description="The list of countries supported by the server.",
        example=["at", "be", "uk"],
    )
    country: Optional[CountryCode] = Field(
        None,
        description="The ISO code of the country the user most likely "
                    "currently is in.",
        example="be",
    )
    recommended: Optional[CountryCode] = Field(
        None,
        description="Which of the available languages matches the user's "
                    "location. Will be `null` if none matches. There might "
                    "be additional logic in the future that provides "
                    "configurable fallbacks etc.",
        example="be",
    )
    db_result: Any = Field(
        None,
        title="DB Result",
        description="The raw geo database lookup result, mainly for debugging "
                    "purposes.",
        example={"country": "be"},
    )
    ip_address: Optional[str] = Field(
        None,
        title="IP Address",
        description="The client's IP address that has been looked up in the "
                    "location database. Can be IPv4 or IPv6.",
        example="123.123.123.123",
    )


class LocalizationResponse(BaseModel):
    language: LanguageDetection = Field(
        ...,
        description="Information about the available and recommended "
                    "languages.",
    )
    location: LocationDetection = Field(
        ...,
        description="Information about the probable physical location.",
    )
    frontend_strings: Optional[Dict[str, str]] = frontend_strings_field


class RateLimitResponse(BaseModel):
    """
    The request was denied, because the client issued too many requests in a
    certain amount of time.
    """

    detail: str = Field(
        ...,
        description="Error message.",
        example="rate limit exceeded, try again in 42 seconds",
    )


class SearchResult(GenericModel, Generic[T]):
    """Result of a search."""
    results: List[T] = Field(
        description="The actual search results.",
    )


class PhoneNumberVerificationRequest(LanguageMixin):
    phone_number: InputPhoneNumber = Field(
        description="The User’s phone number. Some additional characters like "
        "spaces, braces, dashes, slashes and periods are allowed and will be "
        "ignored.",
        example="+49 175 1234567",
    )
    accepted_dpp: Literal[True] = Field(
        title="Accepted DPP",
        description="Whether the User has accepted the data protection "
        "policy. Must be `true` for the request to succeed.",
    )


class PhoneNumberVerificationResponse(BaseModel):
    phone_number: PhoneNumber = Field(
        description="The canocial form of the phone number that has been "
        "input. Should be used for display purposes in the frontend.",
        example="+491751234567",
    )


class PhoneNumberVerificationRejectedResponse(BaseModel):
    """The phone number was rejected for one or more reasons."""
    errors: List[PhoneRejectReason]


class VerificationCode(ConstrainedStr):
    min_length = 6
    max_length = 6


class SMSCodeVerificationRequest(BaseModel):
    phone_number: PhoneNumber
    code: VerificationCode


class SMSCodeVerificationFailedResponse(BaseModel):
    error: Literal["CODE_VERIFICATION_FAILED"] = Field(
        "CODE_VERIFICATION_FAILED",
        description="Either the code did not match the one from the challenge "
        "SMS message, or there is no challenge running for the supplied phone "
        "number at all. (For security reasons, it’s not disclosed which one "
        "of the reasons actually applies.)",
    )


class JWTResponse(BaseModel):
    access_token: str = Field(
        description="The JWT that proves ownership over a specific phone "
        "number. Clients should treat this as an opaque string and not try to "
        "extract information from it.",
        example="TW9vcHN5IQo=",
    )
    token_type: Literal["Bearer"] = Field(
        "Bearer",
        description="Type of the token as specified by OAuth2.",
    )
    expires_in: int = Field(
        description="Number of seconds after which this JWT will expire.",
        example=3600,
    )
