from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from callament.util import client_addr


def test_l10n(fastapi_app: FastAPI, client: TestClient):
    # Set a custom source IP to get a defined geo IP result.
    ip_addr = "2a01:4f8::1"
    fastapi_app.dependency_overrides = {
        client_addr: lambda: ip_addr,
    }

    res = client.get(
        "/api/v1/localization",
        headers={
            "Accept-Language": "tlh;q=1, en;q=0.8",
        }
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert isinstance(data, dict)

    assert "language" in data
    language = data["language"]
    assert isinstance(language, dict)

    assert "available" in language
    assert isinstance(language["available"], list)
    assert len(language["available"]) > 0
    for la in language["available"]:
        assert isinstance(la, str)
    assert "tlh" not in language["available"]

    assert "user_preferences" in language
    assert isinstance(language["user_preferences"], list)
    assert language["user_preferences"] == ["tlh", "en"]

    assert "recommended" in language
    assert language["recommended"].startswith("en")

    assert "location" in data
    location = data["location"]
    assert isinstance(location, dict)

    assert "country" in location
    assert location["country"] == "de"
    assert location["ip_address"] == ip_addr
    assert location["db_result"] == {"country": {"iso_code": "de"}}
