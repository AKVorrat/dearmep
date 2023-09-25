from typing import Any, Callable, Dict, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, \
    Response, status
from prometheus_client import Counter

from ..config import Config, Language, all_frontend_strings
from ..database.connection import get_session
from ..database.models import Blob, Destination, DestinationGroupListItem, \
    DestinationID, DestinationRead
from ..database import query
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import MAX_SEARCH_RESULT_LIMIT, CountryCode, \
    DestinationSearchResult, FrontendStringsResponse, LanguageDetection, \
    LocalizationResponse, RateLimitResponse, SearchResult, SearchResultLimit
from ..ratelimit import Limit, client_addr
from ..phone.elks import initiate_call, InitialElkResponseState, ongoing_calls


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
            dest = query.get_random_destination(session, country=country)
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        return destination_to_destinationread(dest)


@router.post(
    "/initiate-call",
    operation_id="initiateCall",
    dependencies=(simple_rate_limit,),
    status_code=status.HTTP_204_NO_CONTENT
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

    if ongoing_calls.destination_is_in_call(destination_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already on a call")

    with get_session() as session:
        try:
            contact = query.get_contact_for_destination(
                session,
                destination_id=destination_id
            )
        except query.NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    call_state: InitialElkResponseState = initiate_call(
        user_phone_number=user_phone,
        user_language=language,
        contact=contact
    )

    if call_state == "failed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call failed")
