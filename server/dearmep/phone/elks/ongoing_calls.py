from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col

from ...config import Language
from ...database.models import Call, Destination


class CallError(Exception):
    pass


def get_call(
        callid: str,
        provider: str,
        session: Session,
) -> Call:
    try:
        call = (session.query(Call)
                .filter(Call.provider_call_id == callid)
                .filter(Call.provider == provider)
                .options(
                joinedload(Call.destination)
                .joinedload(Destination.contacts)
                ).one())
        return call
    except NoResultFound:
        raise CallError(f"Call {callid=}, {provider=} not found")


def remove_call(call: Call, session: Session):
    """ removes a call from the database """
    session.delete(call)
    session.commit()


def connect_call(call: Call, session: Session):
    """ sets a call as connected in database """
    call.connected_at = datetime.now()
    session.add(call)
    session.commit()


def end_call(call: Call, session: Session):
    """ sets a call as ended in database """
    call.ended_at = datetime.now()
    session.add(call)
    session.commit()


def destination_is_in_call(destination_id: str, session: Session):
    """ returns True if the destination is in a call """
    stmt = select(Call).where(
        and_(
            Call.destination_id == destination_id,
            col(Call.connected_at).isnot(None),
            col(Call.ended_at).is_(None),
        )
    ).exists()
    in_call = session.query(stmt).scalar()
    return in_call


def add_call(
    provider: str,
    provider_call_id: str,
    destination_id: str,
    user_language: Language,
    user_id,
    session: Session
) -> Call:
    """ adds a call to the database """
    call = Call(
        provider=provider,
        provider_call_id=provider_call_id,
        destination_id=destination_id,
        user_language=user_language,
        user_id=user_id,
    )
    session.add(call)
    session.commit()
    return call


def get_mep_number(call: Call) -> str:
    """ returns the MEP number of the call """
    query = [x for x in call.destination.contacts if x.type == "phone"]
    if not query:
        return ""
    return query[0].contact
