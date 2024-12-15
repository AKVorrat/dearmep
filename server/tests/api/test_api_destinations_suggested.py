from fastapi.testclient import TestClient

from dearmep.api.v1 import router
from pathlib import Path
from dearmep.config import Config
from unittest.mock import patch
parent_path = Path(__file__).parent

Config.load_yaml_file(
    filename=parent_path / "test_api_destinations_suggested_config.yaml"
)

client = TestClient(router)


def mock_random_choices(items, weights, k=1):
    # ignores parameter k, as k=1 is implemented

    # TODO: this becomes hardly predictable when the two heightest weights
    # are equal
    max_index = weights.index(max(weights))
    return [items[max_index]]


def test_dest_sugg():
    with patch(
        "dearmep.api.v1.query.random.choices",
        side_effect=mock_random_choices
    ):
        response = client.get(
            "/destinations/suggested?country=DE"
        )

    assert response.status_code == 200

    data = response.json()
    assert data["country"] == "DE"
