import enum
from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, \
    Response, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from pydantic import BaseModel

from ..config import Config, Language, all_frontend_strings
from ..database.connection import get_session
from ..database.models import Blob, Destination, DestinationGroupListItem, \
    DestinationID, DestinationRead, DestinationSelectionLogEvent
from ..database import query
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import MAX_SEARCH_RESULT_LIMIT, CountryCode, \
    DestinationSearchResult, FrontendStringsResponse, LanguageDetection, \
    LocalizationResponse, RateLimitResponse, SearchResult, SearchResultLimit
from ..ratelimit import Limit, client_addr


l10n_autodetect_total = Counter(
    "l10n_autodetect_total",
    "Number of times language/country autodetect was performed, by results.",
    ("language", "country"),
)


rate_limit_response: Dict[int, Dict[str, Any]] = {
    429: {
        "description": "Rate Limit Exceeded",
        "model": RateLimitResponse,
        "headers": {
            "Retry-After": {
                "description": "The number of seconds until the limit resets.",
                "schema": {"type": "integer"},
            },
        },
    },
}


simple_rate_limit = Depends(Limit("simple"))
computational_rate_limit = Depends(Limit("computational"))


BlobURLDep = Callable[[Optional[Blob]], Optional[str]]


def blob_path(blob: Optional[Blob]) -> Optional[str]:
    # FIXME: This should not be hardcoded.
    return None if blob is None else f"/api/v1/blob/{blob.name}"


def blob_url() -> Iterable[BlobURLDep]:
    """Dependency to convert a Blob to a corresponding API request path."""
    yield blob_path


def destination_to_destinationread(dest: Destination) -> DestinationRead:
    return DestinationRead.from_orm(dest, {
        "portrait": blob_path(dest.portrait),
        "groups": [
            DestinationGroupListItem.from_orm(group, {
                "logo": blob_path(group.logo),
            })
            for group in dest.groups
        ],
    })


def error_model(status_code: int, instance: BaseModel) -> JSONResponse:
    return JSONResponse(instance.dict(), status_code=status_code)


router = APIRouter()


@router.get(
    "/localization", operation_id="getLocalization",
    response_model=LocalizationResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(computational_rate_limit,),
)
def get_localization(
    frontend_strings: bool = Query(
        False,
        description="Whether to also include all frontend translation strings "
        "for the detected language. If you don’t request this, the "
        "`frontend_strings` field in the response will be `null` to save "
        "bandwidth.",
    ),
    client_addr: str = Depends(client_addr),
    accept_language: str = Header(""),
):
    """
    Based on the user’s IP address and `Accept-Language` header, suggest a
    country and language from the ones available in the campaign.
    """
    l10n_config = Config.get().l10n
    available_languages = l10n_config.languages
    default_language = l10n_config.default_language
    geo_db = l10n_config.geo_mmdb

    preferences = parse_accept_language(accept_language)
    recommended_lang = find_preferred_language(
                prefs=preferences,
                available=available_languages,
                fallback=default_language,
            )

    with get_session() as session:
        location = get_country(session, geo_db, client_addr)

    # Track localization results in Prometheus.
    l10n_autodetect_total.labels(
        recommended_lang, str(location.country)
    ).inc()

    return LocalizationResponse(
        language=LanguageDetection(
            available=available_languages,
            recommended=recommended_lang,
            user_preferences=preferences,
        ),
        location=location,
        frontend_strings=all_frontend_strings(recommended_lang)
        if frontend_strings else None,
    )


# TODO: Add caching headers, this is pretty static data.
@router.get(
    "/frontend-strings/{language}", operation_id="getFrontendStrings",
    response_model=FrontendStringsResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_frontend_strings(
    language: Language,
):
    """
    Returns a list of translation strings, for the given language, to be used
    by the frontend code. If a string is not available in that language, it
    will be returned in the default language instead. All strings that exist
    in the config's `frontend_strings` section are guaranteed to be available
    at least in the default language.
    """
    return FrontendStringsResponse(
        frontend_strings=all_frontend_strings(language),
    )


# TODO: Add caching headers.
@router.get(
    "/blob/{name}", operation_id="getBlob",
    response_class=Response,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        200: {
            "content": {"application/octet-stream": {}},
            "description": "The contents of the named blob, with a matching "
                           "mimetype set.",
        },
    },
    dependencies=(simple_rate_limit,),
)
def get_blob_contents(
    name: str,
):
    """
    Returns the contents of a blob, e.g. an image or audio file.
    """
    with get_session() as session:
        try:
            blob = query.get_blob_by_name(session, name)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return Response(blob.data, media_type=blob.mime_type)


@router.get(
    "/destinations/country/{country}", operation_id="getDestinationsByCountry",
    response_model=SearchResult[DestinationSearchResult],
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_destinations_by_country(
    country: CountryCode,
) -> SearchResult[DestinationSearchResult]:
    """Return all destinations in a given country."""
    with get_session() as session:
        # TODO: This query result should be cached.
        dests = query.get_destinations_by_country(session, country)
        return query.to_destination_search_result(dests, blob_path)


@router.get(
    "/destinations/name", operation_id="getDestinationsByName",
    response_model=SearchResult[DestinationSearchResult],
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_destinations_by_name(
    name: str = Query(
        description="The (part of the) name to search for.",
        example="miers",
    ),
    all_countries: bool = Query(
        True,
        description="Whether to only search in the country specified by "
        "`country`, or in all countries. If `true`, and `country` is "
        "provided, Destinations from that country will be listed first.",
    ),
    country: Optional[CountryCode] = Query(
        None,
        description="The country to search in (if `all_countries` is false) "
        "or prefer (if `all_countries` is true). Has to be specified if "
        "`all_countries` is false.",
        example="DE",
    ),
    limit: SearchResultLimit = Query(
        MAX_SEARCH_RESULT_LIMIT,
        description="Maximum number of results to be returned.",
        example=MAX_SEARCH_RESULT_LIMIT,
    ),
) -> SearchResult[DestinationSearchResult]:
    """Return Destinations by searching for (parts of) their name."""
    if not all_countries and country is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="country is required if all_countries is false",
        )
    with get_session() as session:
        dests = query.get_destinations_by_name(
            session, name,
            all_countries=all_countries,
            country=country,
            limit=limit,
        )
        return query.to_destination_search_result(dests, blob_path)


@router.get(
    "/destinations/id/{id}", operation_id="getDestinationByID",
    response_model=DestinationRead,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_destination_by_id(
    id: DestinationID,
) -> DestinationRead:
    with get_session() as session:
        try:
            dest = query.get_destination_by_id(session, id)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        return destination_to_destinationread(dest)


@router.get(
    "/destinations/suggested", operation_id="getSuggestedDestination",
    response_model=DestinationRead,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(computational_rate_limit,),
)
def get_suggested_destination(
    country: Optional[CountryCode] = None,
):
    """
    Return a suggested destination to contact, possibly limited by country.
    """
    with get_session() as session:
        try:
            # TODO: Replace with actually _recommended_, not random.
            dest = query.get_random_destination(
                session,
                country=country,
                event=DestinationSelectionLogEvent.WEB_SUGGESTED,
            )
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        session.commit()
        return destination_to_destinationread(dest)


# *** Stubs for describing the API for the frontend. ***


import re  # noqa: E402
from typing import Literal  # noqa: E402
from pydantic import ConstrainedStr, Field  # noqa: E402


# #122: feature/dpp-timestamp


class PhoneNumber(ConstrainedStr):
    regex = re.compile(r"^\+4")  # TODO: mockup constraint


class VerificationCode(ConstrainedStr):
    min_length = 6
    max_length = 6


class LanguageMixin(BaseModel):
    language: Language = Field(
        description="The language to use for interactions with the User.",
        example="de",
    )


class PhoneNumberMixin(BaseModel):
    phone_number: PhoneNumber = Field(
        description="The User’s phone number.",
        example="+491751234567",
    )


class PhoneNumberVerificationRequest(LanguageMixin, PhoneNumberMixin):
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


class PhoneNumberVerificationRejectedResponse(BaseModel):
    """The phone number was rejected for one or more reasons."""
    errors: List[PhoneRejectReason]


class SMSCodeVerificationRequest(PhoneNumberMixin):
    code: VerificationCode = Field(
        description="The verification code the User received via SMS.",
        example="123456",
    )


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


@router.post(
    "/number-verification/request",
    operation_id="requestNumberVerification",
    response_model=PhoneNumberVerificationResponse,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        400: {
            "model": PhoneNumberVerificationRejectedResponse,
        },
    },
)
def request_number_verification(request: PhoneNumberVerificationRequest):
    """Request ownership verification of a phone number.

    This will send an SMS text message with a random code to the given phone
    number. Provide this code to the _Verify Number_ endpoint to receive a JWT
    proving that you have access to that number.

    **MOCKUP:** Phone numbers not starting with `+4` are considered invalid.

    **MOCKUP:** Phone numbers starting with `+42` are not allowed. This is to
    simulate the backend rejecting numbers that are not mobile phone numbers,
    for example.
    """
    if request.phone_number.startswith("+42"):  # TODO: mockup constraint
        return error_model(
            status.HTTP_400_BAD_REQUEST,
            PhoneNumberVerificationRejectedResponse(errors=[
                PhoneRejectReason.DISALLOWED_COUNTRY,
            ]))

    return PhoneNumberVerificationResponse(
        phone_number=request.phone_number.strip(),  # TODO: canonicalize
    )


@router.post(
    "/number-verification/verify",
    operation_id="verifyNumber",
    response_model=JWTResponse,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        400: {
            "model": SMSCodeVerificationFailedResponse,
        },
    },
)
def verify_number(request: SMSCodeVerificationRequest):
    """Prove ownership of a phone number.

    Provide the random code that has been sent using the _Request Number
    Verification_ endpoint to receive a JWT proving that you have access to
    that number.

    **MOCKUP:** All codes except `123456` are invalid.
    """
    if request.code != "123456":
        return error_model(
            status.HTTP_400_BAD_REQUEST, SMSCodeVerificationFailedResponse())

    return JWTResponse(
        access_token="asdf",
        expires_in=3600,
    )


# #125: phonecall


from datetime import datetime  # noqa: E402
import enum  # noqa: E402
from typing import Union  # noqa: E402
from fastapi.security import OAuth2PasswordBearer  # noqa: E402


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/number-verification/verify")  # TODO: don't hardcode


class CallState(str, enum.Enum):
    # NOTE: This model and `DestinationSelectionLogEvent` share many of their
    # states, as well as a lot of the docstring. If you make changes to either
    # of them, please check whether making changes to the other might be useful
    # as well.
    """
    The state of the User’s current call. The meanings of the values are:

    * `NO_CALL`: The User does not have a current (or most recent) call.
    * `CALLING_USER`: The User has requested to be called, in order to be
      connected to a Destination. This is the case when the User clicks on
      “call now” in the web frontend. Now, the system tries to call the User’s
      phone and place them into the IVR menu, targeting the Destination.
    * `IN_MENU`: We have successfully established a call with the User, they
      are currently in the IVR menu.
    * `CALLING_DESTINATION`: The User has asked the IVR menu to be connected to
      a Destination now, all sanity checks have been completed successfully and
      the system is now trying to establish a call with the Destination.
    * `DESTINATION_CONNECTED`: The system has successfully connected the User
      and the Destination, and they are probably talking at the moment.
    * `FINISHED_SHORT_CALL`: The call between User and Destination has been
      completed. They were only talking for a short time, and it’s probably
      okay to assume that only an assistant or voicemail has been reached, but
      not the actual Member of Parliament.
    * `FINISHED_CALL`: The call between User and Destination has been
      completed. Also, they were talking long enough to assume that the Member
      of Parliament has actually been reached and talked to.
    * `CALL_ABORTED`: The call has been aborted prematurely, e.g. because the
      User hung up before being connected to the Destination, or because the
      User was never called due to policy reasons, etc.
    * `CALLING_USER_FAILED`: The system was unable to call the User due to an
      unexpected error. No call was established.
    * `CALLING_DESTINATION_FAILED`: The system was in a call with the User, and
      the User requested to be connected to the Destination, but the
      Destination call could not be established due to an unexpected error.
    """
    NO_CALL = "NO_CALL"
    CALLING_USER = "CALLING_USER"
    IN_MENU = "IN_MENU"
    CALLING_DESTINATION = "CALLING_DESTINATION"
    DESTINATION_CONNECTED = "DESTINATION_CONNECTED"
    FINISHED_SHORT_CALL = "FINISHED_SHORT_CALL"
    FINISHED_CALL = "FINISHED_CALL"
    CALL_ABORTED = "CALL_ABORTED"
    CALLING_USER_FAILED = "CALLING_USER_FAILED"
    CALLING_DESTINATION_FAILED = "CALLING_DESTINATION_FAILED"


class InitiateCallRequest(LanguageMixin):
    destination_id: DestinationID = Field(
        description="The Destination to call.",
    )


class DestinationInCallResponse(BaseModel):
    error: Literal["DESTINATION_IN_CALL"] = Field(
        "DESTINATION_IN_CALL",
        description="The Destination cannot be called right now because "
        "another User is currently in a call with them. Ask the User to try "
        "again later.",
    )


class UserInCallResponse(BaseModel):
    error: Literal["USER_IN_CALL"] = Field(
        "USER_IN_CALL",
        description="There is already a call taking place with the User’s "
        "phone number.",
    )


class OutsideHoursResponse(BaseModel):
    error: Literal["OUTSIDE_HOURS"] = Field(
        "OUTSIDE_HOURS",
        description="The system currently does not allow calls, because the"
        "Destinations are probably out of office right now. Ask the User to "
        "try again later.",
    )


class CallStateResponse(BaseModel):
    state: CallState


@router.post(
    "/call/initiate",
    operation_id="initiateCall",
    response_model=CallStateResponse,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        503: {
            "model": Union[
                DestinationInCallResponse,
                UserInCallResponse,
                OutsideHoursResponse,
            ],
        },
    },
    dependencies=(simple_rate_limit,),
)
def initiate_call(
    request: InitiateCallRequest,
    token: str = Depends(oauth2_scheme),
):
    """
    Call the User and start an IVR interaction with them.

    Pay attention to the return value. It is possible that the backend refuses
    to start a call.

    **MOCKUP:** Destinations that start with `5` will be in a call already.

    **MOCKUP:** If the system time is at an odd minute, this endpoint will
    return “outside office hours”.

    **MOCKUP:** If the token starts with `x`, the endpoint will return that the
    User already is in a call.
    """
    if token.startswith("x"):  # TODO: mockup code
        return error_model(
            status.HTTP_503_SERVICE_UNAVAILABLE, UserInCallResponse())

    if datetime.now().minute % 2:  # TODO: mockup code
        return error_model(
            status.HTTP_503_SERVICE_UNAVAILABLE, OutsideHoursResponse())

    with get_session() as session:
        try:
            query.get_destination_by_id(
                session,
                request.destination_id,
            )
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    if request.destination_id.startswith("5"):  # TODO: mockup code
        return error_model(
            status.HTTP_503_SERVICE_UNAVAILABLE, DestinationInCallResponse())

    return CallStateResponse(state=CallState.CALLING_USER)


@router.get(
    "/call/state",
    operation_id="getCallState",
    response_model=CallStateResponse,
)
def get_call_state(
    token: str = Depends(oauth2_scheme),
):
    """
    Request the state of the User’s current call.

    **MOCKUP:** This will return `CALLING_USER` or `IN_MENU` only.
    """
    tenths = datetime.now().second // 10
    return CallStateResponse(
        state=CallState.CALLING_USER if tenths % 2 else CallState.IN_MENU,
    )
