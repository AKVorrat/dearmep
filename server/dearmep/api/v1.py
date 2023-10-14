from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Header, Query, \
    Response, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from pydantic import BaseModel

from ..config import Config, Language, all_frontend_strings
from ..database.connection import get_session
from ..database.models import Blob, Destination, DestinationGroupListItem, \
    DestinationID, DestinationRead, DestinationSelectionLogEvent, \
    FeedbackContext
from ..database import query
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import MAX_SEARCH_RESULT_LIMIT, CountryCode, \
    DestinationSearchResult, FeedbackSubmission, FeedbackToken, \
    FrontendStringsResponse, JWTResponse, LanguageDetection, \
    LocalizationResponse, PhoneNumberVerificationRejectedResponse, \
    PhoneNumberVerificationResponse, PhoneRejectReason, RateLimitResponse, \
    SMSCodeVerificationFailedResponse, SearchResult, SearchResultLimit, \
    UserPhone, PhoneNumberVerificationRequest, SMSCodeVerificationRequest
from ..phone.abstract import get_phone_service
from ..ratelimit import Limit, client_addr
from ..phone.elks.elks import initiate_call, InitialElkResponseState


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


@router.post(
    "/initiate-call",
    operation_id="initiateCall",
    responses=rate_limit_response,  # type: ignore[arg-type]
    dependencies=(simple_rate_limit,),
    status_code=status.HTTP_204_NO_CONTENT,
)
def post_initiate_call(
    language: Language,
    destination_id: DestinationID,
    user_phone: str
):
    """
    Selects a phone number based on MEP's country
    and initiates a call to the user.
    """

    call_state: InitialElkResponseState = initiate_call(
        user_phone_number=user_phone,
        user_language=language,
        destination_id=destination_id,
        config=Config.get()
    )

    if call_state == "failed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call failed")


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

        message = f"Your code is {result}"  # TODO translation
        get_phone_service().send_sms(number, message)
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
        response = JWTResponse(
            access_token="TODO",  # TODO
            expires_in=3600,  # TODO
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
