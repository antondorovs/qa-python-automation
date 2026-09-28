import json
from urllib.request import urlopen

import pytest

from qa_python_lab.api_client import ApiClient

pytestmark = [pytest.mark.api, pytest.mark.contract]


def test_repeated_health_checks_preserve_users_and_http_contract(base_url: str) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body

    for _ in range(3):
        with urlopen(f"{base_url}/api/health", timeout=5) as response:
            body = response.read()
            assert response.status == 200
            assert response.headers.get_content_type() == "application/json"
            assert response.headers.get_content_charset() == "utf-8"
            assert response.headers["Content-Length"] == str(len(body))
            assert json.loads(body) == {"status": "ok"}

    assert client.request("GET", "/api/users").body == original_users
    created = client.request(
        "POST", "/api/users", {"name": "Carla", "email": "carla@example.com"}
    )
    assert created.status == 201
    assert created.body["id"] == 3


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        pytest.param(
            {"name": "Carla", "email": "carla@example.com"}, 201, id="created-user"
        ),
        pytest.param({"name": "Carla"}, 400, id="invalid-user"),
        pytest.param(
            {"name": "Another Anna", "email": "anna@example.com"}, 409, id="duplicate-user"
        ),
    ],
)
def test_health_remains_available_after_user_creation_attempt(
    base_url: str, payload: dict[str, object], expected_status: int
) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    creation = client.request("POST", "/api/users", payload)
    assert creation.status == expected_status
    expected_users = original_users + [creation.body] if expected_status == 201 else original_users

    health = client.request("GET", "/api/health")
    assert health.status == 200
    assert health.body == {"status": "ok"}
    assert client.request("GET", "/api/users").body == expected_users
