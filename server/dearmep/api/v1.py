from typing import Any, Callable, Dict, Iterable, List, Optional, Union
from typing_extensions import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, Query, \
    Request, Response, status
from fastapi.responses import JSONResponse

from prometheus_client import Counter

from pydantic import BaseModel
import pytz
from sqlmodel import col

from . import authtoken
from ..config import Config, Language, all_frontend_strings
from ..database.connection import get_session
from ..database.models import Blob, Destination, DestinationGroupListItem, \
    DestinationID, DestinationRead, DestinationSelectionLog, \
    DestinationSelectionLogEvent, FeedbackContext
from ..database import query
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import MAX_SEARCH_RESULT_LIMIT, CallState, CallStateResponse, \
    CountryCode, DestinationInCallResponse, DestinationSearchResult, \
    FeedbackSubmission, FeedbackToken, FrontendStringsResponse, \
    InitiateCallRequest, JWTClaims, JWTResponse, LanguageDetection, \
    LocalizationResponse, OutsideHoursResponse, \
    PhoneNumberVerificationRejectedResponse, PhoneNumberVerificationResponse, \
    PhoneRejectReason, RateLimitResponse, SMSCodeVerificationFailedResponse, \
    SearchResult, SearchResultLimit, UserPhone, UserInCallResponse, \
    PhoneNumberVerificationRequest, SMSCodeVerificationRequest

from ..ratelimit import Limit, client_addr
from ..phone.abstract import get_phone_service


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
sms_rate_limit = Depends(Limit("sms"))


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


def browser_cache_headers(ttl: timedelta,
                          etag: Optional[str] = None) -> Dict[str, str]:
    """
    Generate a dictionary that contains header fields to control the caching of
    assets in the web browser.
    This dictionary can be used with a `Response.headers` object.
    """
    result = {"Cache-Control": f"max-age={int(ttl.total_seconds())}"}
    if tag := etag:
        result["ETag"] = tag
    return result


def not_modified(request: Request, etag: str, cache_duration: timedelta) \
        -> Optional[Response]:
    """
    Create a HTTP 304 Not-Modified response if the `etag` matches the
    `If-None-Match` parameter in the `Request`
    """

    # see https://web.dev/http-cache/#unversioned-urls
    if header_etag := request.headers.get("If-None-Match"):
        if header_etag.strip('"') == etag:
            return Response(status_code=304,
                            headers=browser_cache_headers(cache_duration,
                                                          etag))
    return None


router = APIRouter()


@router.get(
    "/localization", operation_id="getLocalization",
    response_model=LocalizationResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(computational_rate_limit,),
)
def get_localization(
    request: Request,
    response: Response,
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

    if frontend_strings:
        strings = all_frontend_strings(recommended_lang)
        etag = str(id(strings))
        cache_duration = timedelta(days=1)
        if nm_response := not_modified(request, etag, cache_duration):
            return nm_response
        # only send a cache header if we actually send the frontend strings
        response.headers.update(browser_cache_headers(cache_duration, etag))
    else:
        strings = None

    return LocalizationResponse(
        language=LanguageDetection(
            available=available_languages,
            recommended=recommended_lang,
            user_preferences=preferences,
        ),
        location=location,
        frontend_strings=strings,
    )


@router.get(
    "/frontend-strings/{language}", operation_id="getFrontendStrings",
    response_model=FrontendStringsResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_frontend_strings(
    language: Language,
    request: Request,
    response: Response,
):
    """
    Returns a list of translation strings, for the given language, to be used
    by the frontend code. If a string is not available in that language, it
    will be returned in the default language instead. All strings that exist
    in the config's `frontend_strings` section are guaranteed to be available
    at least in the default language.
    """
    strings = all_frontend_strings(language)
    cache_duration = timedelta(days=1)
    etag = str(id(strings))

    if not_modified_response := not_modified(request, etag, cache_duration):
        return not_modified_response

    response.headers.update(browser_cache_headers(timedelta(days=1), etag))
    return FrontendStringsResponse(
        frontend_strings=strings,
    )


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
    request: Request,
):
    """
    Returns the contents of a blob, e.g. an image or audio file.
    """
    cache_duration = timedelta(days=1)
    with get_session() as session:
        try:
            blob = query.get_blob_by_name(session, name)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    etag = str(blob.etag)
    if not_modified_response := not_modified(request, etag, cache_duration):
        return not_modified_response
    return Response(blob.data,
                    media_type=blob.mime_type,
                    headers=browser_cache_headers(cache_duration,
                                                  etag))


@router.get(
    "/destinations/country/{country}", operation_id="getDestinationsByCountry",
    response_model=SearchResult[DestinationSearchResult],
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_destinations_by_country(
    country: CountryCode,
    response: Response,
) -> SearchResult[DestinationSearchResult]:
    """Return all destinations in a given country."""
    response.headers.update(browser_cache_headers(timedelta(days=1)))
    with get_session() as session:
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
            dest = query.get_recommended_destination(
                session,
                country=country,
                event=DestinationSelectionLogEvent.WEB_SUGGESTED,
            )
        except query.NotFound as e:
            if country:
                # Try getting someone from a different country then.
                try:
                    dest = query.get_recommended_destination(
                        session,
                        event=DestinationSelectionLogEvent.WEB_SUGGESTED,
                    )
                except query.NotFound as e2:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, str(e2))
            else:
                raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        session.commit()
        return destination_to_destinationread(dest)


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
    dependencies=(computational_rate_limit,),
)
def initiate_call(
    request: InitiateCallRequest,
    claims: Annotated[JWTClaims, Depends(authtoken.validate_token)],
):
    """
    Call the User and start an IVR interaction with them.
    """
    now = datetime.now(pytz.timezone("Europe/Brussels"))
    if now.weekday() >= 5 or now.hour < 9 or now.hour > 19:
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

        fb_token = query.create_feedback_token(
            session,
            user=UserPhone(claims.phone),
            destination_id=request.destination_id,
            language=request.language,
        )

        call_state = get_phone_service().establish_call(
            user_phone=claims.phone,
            language=request.language,
            destination_id=request.destination_id,
            session=session,
        )
        if isinstance(call_state,
                      (DestinationInCallResponse, UserInCallResponse)):
            return error_model(status.HTTP_503_SERVICE_UNAVAILABLE, call_state)

    return CallStateResponse(state=call_state, feedback_token=fb_token)


@router.get(
    "/call/state",
    operation_id="getCallState",
    response_model=CallStateResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
)
def get_call_state(
    claims: Annotated[JWTClaims, Depends(authtoken.validate_token)],
):
    """
    Returns the state of the User’s latest call.
    """
    with get_session() as session:

        user_id = UserPhone(claims.phone)

        if (last_log := (
            session.query(DestinationSelectionLog.event).filter(
                DestinationSelectionLog.user_id == user_id
            ).filter(
                col(DestinationSelectionLog.event).in_(
                    CallState.__members__.keys())
            ).order_by(
                col(DestinationSelectionLog.timestamp).desc()).first())):

            return CallStateResponse(state=CallState[last_log.event.name])
        return CallStateResponse(state=CallState.NO_CALL)


@router.post(
    "/number-verification/request", operation_id="requestNumberVerification",
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        400: {"model": PhoneNumberVerificationRejectedResponse},
    },
    response_model=PhoneNumberVerificationResponse,
    dependencies=(sms_rate_limit,),
)
def request_number_verification(
    request: PhoneNumberVerificationRequest,
) -> Union[JSONResponse, PhoneNumberVerificationResponse]:
    """Request ownership verification of a phone number.

    This will send an SMS text message with a random code to the given phone
    number. Provide this code to the _Verify Number_ endpoint to receive a JWT
    proving that you have access to that number.
    """
    def reject(errors: List[PhoneRejectReason]) -> JSONResponse:
        return error_model(
            status.HTTP_400_BAD_REQUEST,
            PhoneNumberVerificationRejectedResponse(errors=errors))

    user = UserPhone(request.phone_number)
    assert user.original_number  # sure, we just created it from one
    number = user.format_number(user.original_number)

    # Check if the number is forbidden by policy.
    if reject_reasons := user.check_allowed():
        return reject(reject_reasons)

    with get_session() as session:
        result = query.get_new_sms_auth_code(
            session, user=user, language=request.language)
        # Number could be rejected because of too many requests.
        if isinstance(result, PhoneRejectReason):
            return reject([result])

        config = Config.get()
        message = config.l10n.strings.phone_number_verification_sms.apply({
            "code": result,
        }, request.language)

        get_phone_service().send_sms(
            sender=config.telephony.sms_sender_name,
            content=message,
            recipient=number,
        )

        response = PhoneNumberVerificationResponse(
            phone_number=number,
        )
        # Only commit after sending the code successfully.
        session.commit()
    return response


@router.post(
    "/number-verification/verify", operation_id="verifyNumber",
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        400: {"model": SMSCodeVerificationFailedResponse},
    },
    response_model=JWTResponse,
    dependencies=(simple_rate_limit,),
)
def verify_number(
    request: SMSCodeVerificationRequest,
) -> Union[JWTResponse, JSONResponse]:
    """Prove ownership of a phone number.

    Provide the random code that has been sent using the _Request Number
    Verification_ endpoint to receive a JWT proving that you have access to
    that number.
    """
    with get_session() as session:
        user = UserPhone(request.phone_number)
        if not query.verify_sms_auth_code(
            session, user=user, code=request.code,
        ):
            return error_model(
                status.HTTP_400_BAD_REQUEST,
                SMSCodeVerificationFailedResponse())
        response = authtoken.create_token(
            phone=request.phone_number,
        )
        session.commit()
    return response


@router.get(
    "/call/feedback/{token}", operation_id="getFeedbackContext",
    response_model=FeedbackContext,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        404: {"description": "Token Not Found"},
    },
    dependencies=(simple_rate_limit,),
)
def get_feedback_context(
    token: FeedbackToken,
) -> FeedbackContext:
    with get_session() as session:
        try:
            feedback = query.get_user_feedback_by_token(session, token=token)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        return FeedbackContext(
            expired=feedback.expires_at <= datetime.now(),
            used=feedback.feedback_entered_at is not None,
            destination=destination_to_destinationread(feedback.destination),
        )


@router.post(
    "/call/feedback/{token}", operation_id="submitCallFeedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **rate_limit_response,  # type: ignore[arg-type]
        403: {"description": "Token Already Used"},
        404: {"description": "Token Not Found"},
    },
    dependencies=(simple_rate_limit,),
)
def submit_call_feedback(
    token: FeedbackToken,
    submission: FeedbackSubmission,
):
    with get_session() as session:
        try:
            feedback = query.get_user_feedback_by_token(session, token=token)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        if feedback.feedback_entered_at is not None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "token has already been used")

        feedback.feedback_entered_at = datetime.now()
        feedback.convinced = submission.convinced
        feedback.technical_problems = submission.technical_problems
        feedback.additional = submission.additional
        session.add(feedback)
        session.commit()
