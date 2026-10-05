import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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
            assert json.loads(body) == {
                "status": "ok",
                "user_count": len(original_users),
                "next_user_id": len(original_users) + 1,
            }

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
    assert health.body == {
        "status": "ok",
        "user_count": len(expected_users),
        "next_user_id": len(expected_users) + 1,
    }
    assert client.request("GET", "/api/users").body == expected_users


def test_health_user_count_tracks_mixed_user_creation_attempts(base_url: str) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    expected_users = original_users.copy()
    assert client.request("GET", "/api/health").body == {
        "status": "ok",
        "user_count": len(expected_users),
        "next_user_id": len(expected_users) + 1,
    }

    attempts = [
        ({"name": "Carla"}, 400),
        ({"name": "Carla", "email": "carla@example.com"}, 201),
        ({"name": "Another Carla", "email": " CARLA@example.com "}, 409),
        ({"name": "Dana", "email": "dana.example.com"}, 400),
        ({"name": "Dana", "email": "dana@example.com"}, 201),
    ]
    for payload, expected_status in attempts:
        creation = client.request("POST", "/api/users", payload)
        assert creation.status == expected_status
        if expected_status == 201:
            expected_users.append(creation.body)

        health = client.request("GET", "/api/health")
        assert health.status == 200
        assert health.body == {
            "status": "ok",
            "user_count": len(expected_users),
            "next_user_id": len(expected_users) + 1,
        }
        assert client.request("GET", "/api/users").body == expected_users


def test_health_next_user_id_only_advances_after_successful_creation(base_url: str) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    next_id = client.request("GET", "/api/health").body["next_user_id"]

    malformed = Request(
        f"{base_url}/api/users",
        data=b'{"name": "Carla",',
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as error:
        urlopen(malformed, timeout=5)
    with error.value as response:
        assert response.status == 400
        assert json.load(response) == {"error": "Invalid JSON"}
    assert client.request("GET", "/api/health").body["next_user_id"] == next_id

    invalid = client.request("POST", "/api/users", {"name": "Carla"})
    assert invalid.status == 400
    assert client.request("GET", "/api/health").body["next_user_id"] == next_id

    created = client.request(
        "POST", "/api/users", {"name": "Carla", "email": "carla@example.com"}
    )
    assert created.status == 201
    assert created.body["id"] == next_id
    next_id += 1
    assert client.request("GET", "/api/health").body["next_user_id"] == next_id

    duplicate = client.request(
        "POST", "/api/users", {"name": "Another Carla", "email": " CARLA@example.com "}
    )
    assert duplicate.status == 409
    assert client.request("GET", "/api/health").body["next_user_id"] == next_id

    created_again = client.request(
        "POST", "/api/users", {"name": "Dana", "email": "dana@example.com"}
    )
    assert created_again.status == 201
    assert created_again.body["id"] == next_id
    assert client.request("GET", "/api/health").body["next_user_id"] == next_id + 1
    assert client.request("GET", "/api/users").body == original_users + [
        created.body,
        created_again.body,
    ]


@pytest.mark.parametrize(
    ("method", "expected_status"),
    [
        pytest.param("PUT", 405, id="put"),
        pytest.param("PATCH", 405, id="patch"),
        pytest.param("DELETE", 405, id="delete"),
        pytest.param("OPTIONS", 204, id="options"),
    ],
)
def test_health_next_user_id_survives_non_creating_methods(
    base_url: str, method: str, expected_status: int
) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    original_health = client.request("GET", "/api/health").body
    payload = b'{"name": "Carla", "email": "carla@example.com"}'
    request = Request(
        f"{base_url}/api/users",
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )

    if expected_status == 204:
        with urlopen(request, timeout=5) as response:
            assert response.status == expected_status
            assert response.read() == b""
    else:
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=5)
        with error.value as response:
            assert response.status == expected_status

    assert client.request("GET", "/api/users").body == original_users
    assert client.request("GET", "/api/health").body == original_health

    created = client.request(
        "POST", "/api/users", {"name": "Carla", "email": "carla@example.com"}
    )
    assert created.status == 201
    assert created.body["id"] == original_health["next_user_id"]
    assert client.request("GET", "/api/health").body == {
        "status": "ok",
        "user_count": original_health["user_count"] + 1,
        "next_user_id": created.body["id"] + 1,
    }
