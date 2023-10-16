from typing import Iterable

from fastapi import status
from fastapi.testclient import TestClient
import pytest

from dearmep.config import APP_NAME


def metrics_lines_func(client: TestClient) -> Iterable[str]:
    res = client.get("/metrics")
    assert res.status_code == status.HTTP_200_OK
    for line in res.iter_lines():
        yield str(line).rstrip("\r\n")


@pytest.fixture
def metrics_lines(client: TestClient):
    yield list(metrics_lines_func(client))


def test_python_info_in_metrics(metrics_lines: Iterable[str]):
    assert [
        line
        for line in metrics_lines
        if line.startswith("python_info{")
        and line.endswith(" 1.0")
    ]


def test_non_grouped_status_codes(client: TestClient):
    # Do a throwaway request in order to have at least one request in the
    # metrics when doing the actual test.
    assert client.get("/metrics").status_code == status.HTTP_200_OK

    mark = f'starlette_requests_total{{app_name="{APP_NAME}",method="GET",' \
        + 'path="/metrics",status_code="200"} '
    assert [
        line
        for line in metrics_lines_func(client)
        if line.startswith(mark)
    ]


def test_no_unknown_paths(client: TestClient):
    """Unknown paths should not create a new `path` label.

    This creates a massive number of useless labels when someone scans the
    backend for security vulnerabilities, Wordpress paths etc.
    """
    # Try accessing two non-existing endpoints.
    assert client.get("/api/v1/foo").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/api/v1/bar").status_code == status.HTTP_404_NOT_FOUND
    # Try accessing an endpoint that exists, but will return 404.
    assert client.get("/api/v1/blob/doesnotexist.exe").status_code \
        == status.HTTP_404_NOT_FOUND

    # Assert that the non-existing endpoints are not showing up in the metrics.
    assert not [
        line
        for line in metrics_lines_func(client)
        if line.find("/foo") != -1 or line.find("/bar") != -1
    ]

    # Assert that the existing endpoint that returned 404 _does_ show up.
    mark = ',method="GET",path="/api/v1/blob/{name}",status_code="404"'
    assert [
        line
        for line in metrics_lines_func(client)
        if line.find(mark) != -1
    ]
