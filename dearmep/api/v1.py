from typing import Any, Dict

from fastapi import APIRouter, Depends, Header
from prometheus_client import Counter

from ..config import Config, Language, all_frontend_strings
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import FrontendStringsResponse, LanguageDetection, \
    LocalizationResponse, RateLimitResponse
from ..util import Limit, client_addr


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


router = APIRouter()


@router.get(
    "/localization",
    response_model=LocalizationResponse,
    # TODO: This explicit limit here makes little sense, it's more of a demo.
    dependencies=[Depends(Limit("5/minute"))],
    responses=rate_limit_response,  # type: ignore[arg-type]
)
def localize(
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

    location = get_country(geo_db, client_addr)

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
    )


# TODO: Add caching headers, this is pretty static data.
@router.get(
    "/frontend-strings/{language}",
    response_model=FrontendStringsResponse,
    responses=rate_limit_response,  # type: ignore[arg-type]
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
