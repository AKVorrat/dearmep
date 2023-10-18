# mypy: ignore-errors
from fastapi.testclient import TestClient
from dearmep.models import UserPhone
from dearmep.phone.elks import ongoing_calls
from dearmep.database.connection import get_session
import secrets
import datetime
import pytest


def test_ongoing_calls_interface(client: TestClient):
    """ test the flow of a call """
    with get_session() as session:
        provider = "46elks"
        provider_call_id = secrets.token_hex(10)
        user_language = "en"
        destination_id = "38595"
        user_id = UserPhone("+49123456789")

        # we don't find the call in the database
        with pytest.raises(ongoing_calls.CallError) as excinfo:
            call = ongoing_calls.get_call(provider_call_id, provider, session)
        assert provider_call_id in str(excinfo.value)
        assert provider in str(excinfo.value)

        # call gets created
        ongoing_calls.add_call(
            provider=provider,
            provider_call_id=provider_call_id,
            user_language=user_language,
            destination_id=destination_id,
            user_id=user_id,
            session=session,
            started_at=datetime.datetime.now(),

        )
        # we find the call in the database
        call = ongoing_calls.get_call(provider_call_id, provider, session)
        assert call
        assert call.destination_id == destination_id
        assert call.provider_call_id == provider_call_id
        assert call.user_language == user_language
        assert call.provider == provider
        # call is not connected yet
        # check call instance and via interface method
        assert call.connected_at is None
        in_call = ongoing_calls.destination_is_in_call(destination_id, session)
        assert not in_call

        # connecting the call
        ongoing_calls.connect_call(call, session)
        # connected_at becomes a timestamp
        call = ongoing_calls.get_call(provider_call_id, provider, session)
        assert type(call.connected_at) is datetime.datetime
        # the interface returns true for being in a call
        in_call = ongoing_calls.destination_is_in_call(destination_id, session)
        assert in_call

        # call is removed
        ongoing_calls.remove_call(call, session)
        # call is not in database
        # we don't find the call in the database
        # interface results in returning false again
        in_call = ongoing_calls.destination_is_in_call(destination_id, session)
        assert not in_call
        with pytest.raises(ongoing_calls.CallError) as excinfo:
            call = ongoing_calls.get_call(provider_call_id, provider, session)
        assert provider_call_id in str(excinfo.value)
        assert provider in str(excinfo.value)
