from datetime import datetime, timedelta
from typing import Callable, Dict, List, NamedTuple, Optional, Union, cast
from secrets import randbelow
import re
import backoff
from pydantic import UUID4
import random
import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql import label
from sqlmodel import and_, case, col, column, or_

from ..config import Config
from ..convert.blobfile import BlobOrFile
from ..models import CountryCode, DestinationSearchGroup, \
    DestinationSearchResult, FeedbackToken, Language, PhoneRejectReason, \
    SearchResult, UserPhone, VerificationCode, FeedbackConvinced
from .connection import Session, select
from .models import Blob, BlobID, Destination, DestinationID, \
    DestinationSelectionLog, DestinationSelectionLogEvent, MediaList, \
    NumberVerificationRequest, UserFeedback


_logger = logging.getLogger(__name__)


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


def base_endorsement_scoring(base_score: float) -> float:
    """Computes the likeliness of being selected based on
    the 'base_endorsement'.
    A plot of the function applied:
    https://www.wolframalpha.com/input?i=1%2F%281%28abs%28x-0.5%29*4%29%5E3+
    %2B1%29%2C+1%2F%281%28abs%28x-0.7%29*4%29%5E3+%2B1%29+%2C+1%2F%281%28abs
    %28x-0.7%29*16%29%5E3+%2B1%29*0.9%2B0.1++for+0%3C%3Dx%3C%3D1
    returns a value between 0 and 1.
    """
    rc = Config.get().recommender
    center = rc.base_endorsement_scoring.center
    minimum = rc.base_endorsement_scoring.minimum
    steepness = rc.base_endorsement_scoring.steepness

    return 1 / (
        1 + (
            abs(
                base_score - center
            ) * steepness
        ) ** 3
    ) * (1-minimum) + minimum


def feedback_scoring(feedback_sum: int) -> float:
    """Computes the likeliness of being selected based on
    the feedback.
    A plot of the function applied:
    https://www.wolframalpha.com/input?i=plot+1%2F%281%28abs%28x%2F%28N*8%29%29
    *3%29%5E4+%2B1%29+for+-40%3C%3Dx%3C%3D40%2C+N%3D10
    returns a value between 0 and 1.
    """
    rc = Config.get().recommender
    threshold = rc.n_clear_feedback_threshold
    return 1 / (
        1 + (abs(feedback_sum / (threshold*8)) * 3) ** 4
    )


def get_recommended_destination(
    session: Session,
    *,
    country: Optional[CountryCode] = None,
    event: Optional[DestinationSelectionLogEvent] = None,
    user_id: Optional[UserPhone] = None,
    call_id: Optional[str] = None,
) -> Destination:
    """This function randomly selects destinations, while
    the likeliness of being selected is tweaked with
    three main methods:

    1. Hard filter: Removes destinations from
    the selection based on these hard criteria.
    - If 'country' is set, all other countries are excluded.
    - Hard cut offs for base_endorsement.
    - If destination is in call, destination is excluded.

    2. Scores: Over all destinations, a scoring algorithm is applied to
    change the destinations likeliness of being selected.
    - 'base_endorsement' close to center (default=0.5) boosts the likeliness.
    - Clear repeated feedback (negative or positive) leads to
    reduced likeliness.

    3. Rule based drop of likeliness ("soft cool down") if
    - destination was suggested in last request.
    - destination was called very recently.
    - caller called destination already.
    """
    rc = Config.get().recommender

    # select all destinations
    stmt_destinations = select(Destination)

    # 1. hard filter
    # exclude other destinations from other countries, if country is set
    if country:
        stmt_destinations = stmt_destinations.where(
            Destination.country == country
        )

    # cut off by base_endorsement
    MAX_ENDORSEMENT_CUTOFF = rc.endorsement_cutoff.max
    MIN_ENDORSEMENT_CUTOFF = rc.endorsement_cutoff.min
    stmt_destinations = stmt_destinations.where(
        Destination.base_endorsement <= MAX_ENDORSEMENT_CUTOFF,
        Destination.base_endorsement >= MIN_ENDORSEMENT_CUTOFF,
    )

    # exclude destinations in call by selecting
    # all call events
    # outter joining with CALL_ENDED events as last event per destination

    # events designating a call is initiated
    CALL_INITIATED = [
        DestinationSelectionLogEvent.CALLING_DESTINATION,
        DestinationSelectionLogEvent.CALLING_USER,
        DestinationSelectionLogEvent.DESTINATION_CONNECTED,
        DestinationSelectionLogEvent.IVR_SUGGESTED,
    ]

    # events designating a call has ended
    CALL_ENDED = [
        DestinationSelectionLogEvent.CALL_ABORTED,
        DestinationSelectionLogEvent.CALLING_DESTINATION_FAILED,
        DestinationSelectionLogEvent.FINISHED_CALL,
        DestinationSelectionLogEvent.FINISHED_SHORT_CALL,
        DestinationSelectionLogEvent.CALLING_USER_FAILED,
    ]

    # subquery selecting all the latest timestamps of
    # all CALL events (CALL_INITIATED + CALL_ENDED)
    # from sqlalchemy import select

    max_timestamps_subquery = (
        select(  # type: ignore[call-overload]
            DestinationSelectionLog,
            func.max(DestinationSelectionLog.timestamp).label("max_timestamp")
        )
        .where(
            col(DestinationSelectionLog.event).in_(CALL_INITIATED+CALL_ENDED)
        )
        .group_by(DestinationSelectionLog.destination_id)
        .subquery()
    )

    # join the selection logs with the latest timestamps of each destination_id
    latest_logs_subquery = (
        select(DestinationSelectionLog)
        .join(
            max_timestamps_subquery,
            and_(
                DestinationSelectionLog.destination_id ==
                max_timestamps_subquery.c.destination_id,
                DestinationSelectionLog.timestamp ==
                max_timestamps_subquery.c.max_timestamp
            )
        )
        .subquery()
    )

    # outer left join with all Destinations
    stmt_destinations = stmt_destinations.outerjoin(
        latest_logs_subquery,
        or_(
            Destination.id is None,  # there may be no logs
            Destination.id == latest_logs_subquery.c.destination_id,
        )
    )

    # get all destinations
    destinations = session.exec(stmt_destinations).all()
    _logger.debug(
        f"remaning destinations after removal of those in call: "
        f"{len(destinations)}"
    )

    # 2. Scores
    # scoring based on 'base_endorsement'
    weights = [
            base_endorsement_scoring(dest.base_endorsement)
            for dest in destinations
        ]

    # scoring based on feedback
    stmt_feedback = select(  # type: ignore[call-overload]
        UserFeedback.destination_id,
        func.sum(
            label(
                "numeric_feedback",
                case(
                    (UserFeedback.convinced ==
                     FeedbackConvinced.YES,            2),
                    (UserFeedback.convinced ==
                     FeedbackConvinced.LIKELY_YES,     1),
                    (UserFeedback.convinced ==
                     FeedbackConvinced.LIKELY_NO,     -1),
                    (UserFeedback.convinced ==
                     FeedbackConvinced.NO,            -2),
                )
            )
        ).label("numeric_feedback_sum")
    ).group_by(UserFeedback.destination_id)

    feedbacks = session.exec(stmt_feedback).all()

    feedback_scores = [
            (
                fb.destination_id,
                feedback_scoring(fb.numeric_feedback_sum),
            )
            for fb in feedbacks
        ]
    _logger.debug(f"feedback scores: {feedback_scores}")
    for i, dest in enumerate(destinations):
        for fb in feedback_scores:
            if dest.id == fb[0]:
                # merge scoring of feedback + base_endorsement by
                # taking the average
                # https://www.wolframalpha.com/input?i=plot+%281%2F%281%28abs%
                # 28x%2F80%29*3%29%5E4+%2B1%29+%2B+1%2F%281%28abs%28y-0.5%29*4
                # %29%5E3+%2B1%29%29%2F2+for+0%3C%3Dy%3C%3D1+%2C+-40%3C%3Dx%3C
                # %3D40
                weights[i] = (weights[i] + fb[1]) / 2
                break

    # 3. Soft cool down
    # destination was suggested in last request

    # only applies for suggestion events, otherwise looking up the latest
    # suggestion is useless.
    SUGGEST_EVENTS = [
        DestinationSelectionLogEvent.WEB_SUGGESTED,
        DestinationSelectionLogEvent.IVR_SUGGESTED,
    ]
    if event in SUGGEST_EVENTS:
        latest_log = session.query(DestinationSelectionLog).where(
            col(DestinationSelectionLog.event).in_(SUGGEST_EVENTS)
        ).order_by(col(DestinationSelectionLog.timestamp).desc()).first()
        if latest_log:
            # making sure that there is a log at all
            for i, dest in enumerate(destinations):
                if dest.id == latest_log.destination_id:
                    weights[i] = 0.00001
                    break

    # destination was called recently
    SOFT_COOL_DOWN_CALL_DURATION_MINUTES = (
        rc.soft_cool_down_call_timeout
    )
    recent_cutoff = datetime.utcnow() - \
        timedelta(minutes=SOFT_COOL_DOWN_CALL_DURATION_MINUTES)

    destination_logs_recent_calls = session.exec(
        select(DestinationSelectionLog)
        .where(
            col(DestinationSelectionLog.event).in_(CALL_ENDED),
            col(DestinationSelectionLog.timestamp) >= recent_cutoff,
        )
    )
    for i, dest in enumerate(destinations):
        for dest_log in destination_logs_recent_calls:
            if dest.id == dest_log.destination_id:
                weights[i] = 0.1
                break

    # caller called destination already

    if user_id:
        SOFT_COOL_DOWN_CALLER_CALLED_DESTINATION_DURATION_HOURS = 24
        recently_talked_cutoff = datetime.utcnow() - \
            timedelta(
                hours=SOFT_COOL_DOWN_CALLER_CALLED_DESTINATION_DURATION_HOURS
            )
        stmt_calls_ended = (
            select(DestinationSelectionLog)
            .where(
                col(DestinationSelectionLog.event).in_(CALL_ENDED),
                col(DestinationSelectionLog.timestamp) >=
                recently_talked_cutoff,
                DestinationSelectionLog.user_id == user_id,
                )
        )
        dest_logs_recent_calls_with_user = session.exec(stmt_calls_ended)
        for i, dest in enumerate(destinations):
            for dest_log in dest_logs_recent_calls_with_user:
                if dest.id == dest_log.destination_id:
                    weights[i] = 0.1
                    break

    # finally select a destination
    if len(destinations) > 0:
        # log weights if loglevel debug
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "\n" + "\n".join(
                    [
                        f"{weights[i]:.3f} {destinations[i].name}"
                        for i in range(len(destinations))
                    ]
                )
            )
        # select destination
        final_dest = random.choices(destinations, weights=weights, k=1)[0]
    else:
        final_dest = None

    if not final_dest:
        raise NotFound("no destination found that could be recommended")

    if event:
        log_destination_selection(
            session=session,
            destination=final_dest,
            event=event,
            user_id=user_id,
            call_id=call_id,
        )
    return final_dest


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
