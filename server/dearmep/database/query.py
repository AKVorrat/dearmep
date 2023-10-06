from datetime import datetime, timedelta
from typing import Callable, Dict, List, NamedTuple, Optional, Union, cast
from secrets import randbelow
import re
import backoff
from pydantic import UUID4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql import label
from sqlmodel import and_, case, col, column, or_

from ..config import Config
from ..convert.blobfile import BlobOrFile
from ..models import CountryCode, DestinationSearchGroup, \
    DestinationSearchResult, FeedbackToken, Language, PhoneRejectReason, \
    SearchResult, UserPhone, VerificationCode
from .connection import Session, select
from .models import Blob, BlobID, Destination, DestinationID, \
    DestinationSelectionLog, DestinationSelectionLogEvent, MediaList, \
    NumberVerificationRequest, UserFeedback

import logging

logger = logging.getLogger(__name__)


class NotFound(Exception):
    pass


class NumberVerificationRequestCount(NamedTuple):
    """The number of incomplete & completed number verification requests."""
    incomplete: int = 0
    complete: int = 0


def escape_for_like(value: str) -> str:
    return re.sub(r"([%_#])", r"#\1", value)


def get_available_countries(session: Session) -> List[str]:
    countries = session.exec(select(Destination.country).distinct()).all()
    return cast(List[str], countries) \
        if isinstance(countries, List) and len(countries) \
        and isinstance(countries[0], str) \
        else []


def get_blob_by_id(session: Session, id: BlobID) -> Blob:
    if not (blob := session.get(Blob, id)):
        raise NotFound(f"no blob with ID {id}")
    return blob


def get_blob_by_name(session: Session, name: str) -> Blob:
    try:
        return session.exec(select(Blob).where(Blob.name == name)).one()
    except NoResultFound:
        raise NotFound(f"no blob named `{name}`")


def get_blobs_by_names(
    session: Session,
    names: List[str],
) -> Dict[str, Blob]:
    blobs = session.exec(
        select(Blob)
        .where(col(Blob.name).in_(names))
    ).all()
    return {
        blob.name: blob
        for blob in blobs
    }


def get_destination_by_id(
    session: Session,
    id: DestinationID,
) -> Destination:
    dest = session.get(Destination, id)
    if not dest:
        raise NotFound(f"no destination with ID {id} found")
    return dest


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
    event: Optional[DestinationSelectionLogEvent] = None,
    user_id: Optional[UserPhone] = None,
    call_id: Optional[str] = None,
) -> Destination:
    stmt = select(Destination)
    if country:
        stmt = stmt.where(Destination.country == country)
    dest = session.exec(stmt.order_by(func.random())).first()
    if not dest:
        matching = " matching query" if country else ""
        raise NotFound(f"no destination{matching} found")
    if event:
        log_destination_selection(
            session,
            dest,
            event=event,
            user_id=user_id,
            call_id=call_id,
        )
    return dest


def log_destination_selection(
    session: Session,
    destination: Destination,
    *,
    event: DestinationSelectionLogEvent,
    user_id: Optional[UserPhone] = None,
    call_id: Optional[str] = None,
):
    session.add(DestinationSelectionLog(
        destination=destination,
        event=event,
        user_id=user_id,
        call_id=call_id,
    ))


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


def get_number_verification_count(
    session: Session,
    *,
    user: UserPhone,
    reset_incomplete_on_successful_login: bool = True,
    cutoff_completed_older_than_s: Optional[int] = None,
) -> NumberVerificationRequestCount:
    """Get the number of completed & incomplete phone number verifications.

    We are deliberately also considering expired requests here, to prevent
    someone spamming a victim's number with codes by simply doing it _slowly_,
    or to prevent people from logging in 100 times during the course of a day.
    """
    # Subquery for the timestamp of the last successful login of that user.
    last_successful = select(  # type: ignore[call-overload]
        func.max(NumberVerificationRequest.completed_at)
    ).where(
        NumberVerificationRequest.user == user,
        col(NumberVerificationRequest.ignore).is_(False),
    ).scalar_subquery()

    incomplete_filter = [column("completed").is_(False)]
    if reset_incomplete_on_successful_login:
        # Only incomplete attempts since the last successful one will be
        # considered. This effectively resets the "incomplete" counter once
        # there has been a successful login. If there was no last successful
        # one, consider all since Jan 1 2000.
        incomplete_filter.append(
            NumberVerificationRequest.requested_at > func.coalesce(
                last_successful,
                datetime(2000, 1, 1),
            ))

    complete_filter = [column("completed").is_(True)]
    if cutoff_completed_older_than_s:
        # Only completed attempts in the last n seconds will be counted. This
        # effectively limits the "complete" counter to that timespan. Note that
        # this limit has no effect on how far back the "reset incomplete on
        # successful login" logic will look.
        complete_filter.append(
            col(NumberVerificationRequest.requested_at) >=
            datetime.now() - timedelta(seconds=cutoff_completed_older_than_s)
        )

    request_counts: Dict[bool, int] = dict(session.exec(
        select(  # type: ignore[call-overload]
            label("completed", case(
                (col(NumberVerificationRequest.completed_at).is_(None), False),
                else_=True,
            )),
            label("count", func.count()),
        ).group_by("completed")
        .where(
            NumberVerificationRequest.user == user,
            col(NumberVerificationRequest.ignore).is_(False),
            # Use different filtering depending on whether the attempt was
            # completed or not.
            or_(
                and_(*incomplete_filter),
                and_(*complete_filter),
            ),
        )
    ).all())

    return NumberVerificationRequestCount(**{
        "complete" if k else "incomplete": v
        for k, v in request_counts.items()
    })


def get_new_sms_auth_code(
    session: Session,
    *,
    user: UserPhone,
    language: Language,
) -> Union[PhoneRejectReason, VerificationCode]:
    """Generate SMS verification code & store it in the database."""
    config = Config.get()
    now = datetime.now()

    # Reject the user if they have too many open verification requests.
    cutoff_s = config.authentication.session.max_logins_cutoff_days * 86_400
    counts = get_number_verification_count(
        session, user=user, cutoff_completed_older_than_s=cutoff_s)

    if (
        counts.incomplete >= config.authentication.session.max_unused_codes
        or counts.complete >= config.authentication.session.max_logins
    ):
        return PhoneRejectReason.TOO_MANY_VERIFICATION_REQUESTS

    code = VerificationCode(f"{randbelow(1_000_000):06}")

    session.add(NumberVerificationRequest(
        user=user,
        code=code,
        requested_at=now,
        expires_at=now + timedelta(minutes=10),  # TODO: make configurable
        language=language,
    ))

    return code


def verify_sms_auth_code(
    session: Session,
    *,
    user: UserPhone,
    code: VerificationCode,
) -> bool:
    """Check SMS verification code validity & mark as used."""
    if request := session.exec(
        select(NumberVerificationRequest)
        .where(
            NumberVerificationRequest.user == user,
            NumberVerificationRequest.code == code,
            col(NumberVerificationRequest.ignore).is_(False),
            col(NumberVerificationRequest.completed_at).is_(None),
            NumberVerificationRequest.expires_at > datetime.now(),
        ).order_by(col(NumberVerificationRequest.requested_at).desc())
    ).first():
        request.completed_at = datetime.now()
        return True
    return False


def create_feedback_token(
    session: Session,
    *,
    user: UserPhone,
    destination_id: DestinationID,
    language: Language,
) -> FeedbackToken:
    """Create a new, unique feedback token for a call.

    Note: `language` can be used to initialize the feedback form to that
    language, even if the User is accessing the form using a completely new
    browser. Therefore, please provide the language the User _requested_ for
    the call, even if the call took place in another language due to the
    requested one not being available for calls.
    """
    now = datetime.now()
    expires_at = now + timedelta(seconds=Config.get().feedback.token_timeout)

    @backoff.on_exception(
        backoff.constant,
        exception=IntegrityError,
        max_tries=50,
        interval=0.01,
    )
    def insert_new_token() -> FeedbackToken:
        """Generate a new token until we find a unique one."""
        token = FeedbackToken.generate()
        feedback = UserFeedback(
            token=token,
            issued_at=now,
            expires_at=expires_at,
            destination_id=destination_id,
            calling_code=user.calling_code,
            language=language,
        )
        # Tests for uniqueness violation without affecting outer transaction.
        with session.begin_nested():
            session.add(feedback)
        return token

    return insert_new_token()


def get_user_feedback_by_token(
    session: Session,
    *,
    token: FeedbackToken,
) -> UserFeedback:
    """Get the `UserFeedback` model for a given token."""
    if not (feedback := session.get(UserFeedback, token)):
        raise NotFound(f"unknown token `{token}`")
    return feedback


def store_medialist(
    session: Session,
    items: List[BlobOrFile],
    *,
    format: str,
    mimetype: str,
) -> UUID4:
    mlitems = [item.as_medialist_item() for item in items]

    if existing := session.exec(
        select(MediaList)
        .where(MediaList.items == mlitems)
    ).first():
        return existing.id

    mlist = MediaList(
        items=mlitems,
        format=format,
        mimetype=mimetype,
    )
    with session.begin_nested():
        session.add(mlist)
    return mlist.id


def get_medialist_by_id(
    session: Session,
    id: UUID4,
) -> MediaList:
    if not (mlist := session.get(MediaList, str(id))):
        raise NotFound(f"no such medialist: `{str(id)}`")
    return mlist
