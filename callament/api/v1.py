from fastapi import APIRouter, Depends, Header
from prometheus_client import Counter

from ..config import Config
from ..l10n import find_preferred_language, get_country, parse_accept_language
from ..models import LanguageDetection, LocalizationResponse
from ..util import client_addr


l10n_autodetect_counter = Counter(
    "l10n_autodetect_total",
    "Number of times language/country autodetection was performed, by results",
    ["language", "country"],
)


router = APIRouter()


@router.get(
    "/localization",
    response_model=LocalizationResponse,
)
def localize(
    client_addr: str = Depends(client_addr),
    accept_language: str = Header(""),
):
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
    l10n_autodetect_counter.labels(
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