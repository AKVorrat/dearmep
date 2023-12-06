from datetime import datetime
from random import choice

from prometheus_client import Counter

from ..config import Config
from ..database import query
from ..database.models import CallType, DestinationSelectionLogEvent, \
    QueuedCall, UserPhone
from ..database.connection import get_session
from ..phone.abstract import get_phone_service

queued_calls_total = Counter(
    name="queued_calls_total",
    documentation="Total number of calls queued",
)


def build_queue() -> None:

    now = datetime.now()
    office_hours = Config.get().telephony.office_hours
    if not office_hours.open(now):
        return

    with get_session() as session:
        calls = query.get_currently_scheduled_calls(session, now)
        for call in calls.regular:
            session.add(
                QueuedCall(
                    phone_number=call.phone_number,
                    language=call.language,
                ))
        for call in calls.postponed:
            session.add(
                QueuedCall(
                    phone_number=call.phone_number,
                    language=call.language,
                    is_postponed=True,
                ))
        queued_calls_total.inc(
            (len(calls.regular) + len(calls.postponed)))
        query.mark_scheduled_calls_queued(session, calls, now)
        session.commit()


def handle_queue() -> None:

    now = datetime.now()
    with get_session() as session:
        queued_call = query.get_next_queued_call(session, now)
        if queued_call is None:
            return
        session.delete(queued_call)
        session.commit()
        user_id = UserPhone(queued_call.phone_number)
        try:
            destination = query.get_recommended_destination(
                session,
                country=choice(user_id.country_codes),
                event=DestinationSelectionLogEvent.IVR_SUGGESTED,
                user_id=user_id,
            )
        except query.NotFound:
            # We do nothing if we can't find a destination to call.
            return

        get_phone_service().establish_call(
            user_phone=queued_call.phone_number,
            type_of_call=CallType.SCHEDULED,
            language=queued_call.language,
            destination_id=destination.id,
            session=session,
        )
