from dearmep.config import Language
from typing import Optional
from datetime import datetime
from dearmep.database.models import Call, Destination
from dearmep.database import connection
from sqlmodel import Session
from sqlalchemy import exists, and_
from sqlalchemy.orm import joinedload


def session(func):
    def wrapper(*args, **kwargs):
        if "session" in kwargs:
            return func(*args, **kwargs)
        with connection.get_session() as session:
            result = func(*args, **kwargs, session=session)
            return result
    return wrapper


@session
def get_call(callid: str, session: Session) -> Optional[Call]:
    call = (session.query(Call)
            .filter(Call.provider_call_id == callid)
            .options(
            joinedload(Call.destination)
            .joinedload(Destination.contacts)
            ).one_or_none())
    return call


@session
def remove_call(callid: str, session: Session):
    """ removes a call from the database """
    call = get_call(callid, session=session)
    session.delete(call)
    session.commit()


def connect_call(call: Call):
    """ sets a call as connected in database """
    with connection.get_session() as session:
        call.connected_at = datetime.now()
        session.add(call)
        session.commit()


def end_call(call: Call):
    """ sets a call as ended in database """
    with connection.get_session() as session:
        call.ended_at = datetime.now()
        session.add(call)
        session.commit()


@session
def destination_is_in_call(destination_id: str, session: Session):
    """ returns True if the destination is in a call """
    query = session.query(
        exists().where(
            and_(Call.destination_id == destination_id,
                 Call.connected_at.isnot(None),  # type: ignore
                 Call.ended_at.is_(None)  # type: ignore
                 )
        )
    )
    in_call = session.execute(query).scalar()
    return in_call


@session
def add_call(
    provider: str,
    provider_call_id: str,
    user_language: Language,
    destination_id: str,
    session: Session
) -> Call:
    """ adds a call to the database """
    call = Call(
        provider=provider,
        provider_call_id=provider_call_id,
        user_language=user_language,
        destination_id=destination_id,
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
