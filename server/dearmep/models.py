from typing import Any, Dict, Generic, List, Optional, TypeVar, Literal

from pydantic import BaseModel, ConstrainedInt, ConstrainedStr, Field
from pydantic.generics import GenericModel


T = TypeVar("T")


MAX_SEARCH_RESULT_LIMIT = 20


class CountryCode(ConstrainedStr):
    """An ISO-639 country code."""
    min_length = 2
    max_length = 3
    to_upper = True


class SearchResultLimit(ConstrainedInt):
    """The number of search results to return."""
    gt = 0
    le = MAX_SEARCH_RESULT_LIMIT


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
