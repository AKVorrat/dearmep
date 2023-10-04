from fastapi.testclient import TestClient
from dearmep.phone.elks import ongoing_calls
import secrets
import datetime


def test_ongoing_calls_interface(client: TestClient):
    """ test the flow of a call """
    provider = "46elks"
    provider_call_id = secrets.token_hex(10)
    user_language = "en"
    destination_id = "38595"

    # we don't find the call in the database
    assert not ongoing_calls.get_call(provider_call_id)

    # call gets created
    ongoing_calls.add_call(
        provider,
        provider_call_id,
        user_language,
        destination_id
    )
    # we find the call in the database
    call = ongoing_calls.get_call(provider_call_id)
    assert call
    assert call.destination_id == destination_id
    assert call.provider_call_id == provider_call_id
    assert call.user_language == user_language
    assert call.provider == provider
    # call is not connected yet
    # check call instance and via interface method
    assert call.connected_at is None
    in_call = ongoing_calls.destination_is_in_call(destination_id)
    assert not in_call

    # connecting the call
    ongoing_calls.connect_call(call)
    # connected_at becomes a timestamp
    call = ongoing_calls.get_call(provider_call_id)
    assert type(call.connected_at) is datetime.datetime
    # call has not ended yet
    assert not call.ended_at
    # the interface returns true for being in a call
    in_call = ongoing_calls.destination_is_in_call(destination_id)
    assert in_call

    # ending the call
    ongoing_calls.end_call(call)
    # ended_at becomes a timestamp
    call = ongoing_calls.get_call(provider_call_id)
    assert type(call.ended_at) is datetime.datetime
    # interface results in returning false again
    in_call = ongoing_calls.destination_is_in_call(destination_id)
    assert not in_call

    # call is removed
    ongoing_calls.remove_call(provider_call_id)
    # call is not in database
    call = ongoing_calls.get_call(provider_call_id)
    assert not call
