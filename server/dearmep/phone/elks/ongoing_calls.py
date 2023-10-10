from dearmep.config import Language
from typing import Optional
from datetime import datetime
from dearmep.database.models import Call, Destination
from sqlmodel import Session
from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload


def get_call(callid: str, session: Session) -> Optional[Call]:
    call = (session.query(Call)
            .filter(Call.provider_call_id == callid)
            .options(
            joinedload(Call.destination)
            .joinedload(Destination.contacts)
            ).one_or_none())
    return call


def remove_call(callid: str, session: Session):
    """ removes a call from the database """
    call = get_call(callid, session=session)
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
            Call.connected_at.isnot(None),  # type: ignore
            Call.ended_at.is_(None)  # type: ignore
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
