from typing import Callable, List, Optional, cast
import re

from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlmodel import case

from ..models import CountryCode, DestinationSearchGroup, \
    DestinationSearchResult, SearchResult
from .connection import Session, select
from .models import Blob, Destination, DestinationID, Contact

import logging

logger = logging.getLogger(__name__)


class NotFound(Exception):
    pass


def escape_for_like(value: str) -> str:
    return re.sub(r"([%_#])", r"#\1", value)


def get_available_countries(session: Session) -> List[str]:
    countries = session.exec(select(Destination.country).distinct()).all()
    return cast(List[str], countries) \
        if isinstance(countries, List) and len(countries) \
        and isinstance(countries[0], str) \
        else []


def get_blob_by_name(session: Session, name: str) -> Blob:
    try:
        return session.exec(select(Blob).where(Blob.name == name)).one()
    except NoResultFound:
        raise NotFound(f"no blob named `{name}`")


def get_destination_by_id(
    session: Session,
    id: DestinationID,
) -> Destination:
    dest = session.get(Destination, id)
    if not dest:
        raise NotFound(f"no destination with ID {id} found")
    return dest


def get_contact_for_destination(
    session: Session,
    destination_id: DestinationID,
) -> Contact:
    contact = session.query(Contact).join(Destination.contacts) \
        .filter(Destination.id == destination_id) \
        .filter(Contact.type == "phone") \
        .one_or_none()
    if not contact:
        logger.critical(
            f"No contact for <Destination.id: {destination_id}, "
            f"Contact.type: phone> found"
        )
        raise NotFound(f"Contact for destination {destination_id} found")
    return contact


def get_destinations_by_country(
    session: Session,
    country: CountryCode,
) -> List[Destination]:
    dests = session.exec(
        select(Destination)
        .where(Destination.country == country)
        .order_by(Destination.sort_name)
    ).all()
    return dests


def get_destinations_by_name(
    session: Session,
    name: str,
    *,
    all_countries: bool,
    country: Optional[CountryCode],
    limit: int,
) -> List[Destination]:
    stmt = select(Destination).where(
        Destination.name.like(  # type: ignore[attr-defined]
            f"%{escape_for_like(name)}%", escape="#",
        )).limit(limit)
    if all_countries:
        if country is not None:
            # List countries matching the specified one first.
            stmt = stmt.order_by(case(
                (Destination.country == country, 0),
                else_=1,
            ))
    else:
        if country is None:
            raise ValueError("country needs to be set")
        stmt = stmt.where(Destination.country == country)
    stmt = stmt.order_by(Destination.sort_name)
    dests = session.exec(stmt).all()
    return dests


def get_random_destination(
    session: Session,
    *,
    country: Optional[CountryCode] = None,
) -> Destination:
    stmt = select(Destination)
    if country:
        stmt = stmt.where(Destination.country == country)
    dest = session.exec(stmt.order_by(func.random())).first()
    if not dest:
        matching = " matching query" if country else ""
        raise NotFound(f"no destination{matching} found")
    return dest


def to_destination_search_result(
    destinations: List[Destination],
    blob_path: Callable[[Optional[Blob]], Optional[str]],
) -> SearchResult[DestinationSearchResult]:
    return SearchResult(
        results=[
            DestinationSearchResult(
                id=dest.id,
                name=dest.name,
                country=dest.country,
                groups=[
                    DestinationSearchGroup(
                        name=group.long_name,
                        type=group.type,
                        logo=blob_path(group.logo),
                    )
                    for group in dest.groups
                ]
            )
            for dest in destinations
        ]
    )
