import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from qa_python_lab.api_client import ApiClient


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.contract
def test_health_check_contract(base_url: str) -> None:
    response = ApiClient(base_url).request("GET", "/api/health")
    assert response.status == 200
    assert response.body == {"status": "ok"}


@pytest.mark.api
@pytest.mark.smoke
def test_get_existing_user(base_url: str) -> None:
    response = ApiClient(base_url).request("GET", "/api/users/1")
    assert response.status == 200
    assert response.body == {"id": 1, "name": "Anna Smith", "email": "anna@example.com"}


@pytest.mark.api
def test_missing_user_returns_404(base_url: str) -> None:
    response = ApiClient(base_url).request("GET", "/api/users/999")
    assert response.status == 404
    assert response.body == {"error": "User not found"}


@pytest.mark.api
@pytest.mark.contract
def test_list_user_contract(base_url: str) -> None:
    response = ApiClient(base_url).request("GET", "/api/users")
    assert response.status == 200
    assert len(response.body) == 2
    for user in response.body:
        assert set(user) == {"id", "name", "email"}
        assert isinstance(user["id"], int)
        assert isinstance(user["name"], str) and user["name"]
        assert isinstance(user["email"], str) and "@" in user["email"]


@pytest.mark.api
@pytest.mark.contract
def test_create_user_and_read_back(base_url: str) -> None:
    client = ApiClient(base_url)
    created = client.request("POST", "/api/users", {
        "name": " Carla ",
        "email": " CARLA@example.com ",
    })
    assert created.status == 201
    assert created.body == {"id": 3, "name": "Carla", "email": "carla@example.com"}
    assert client.request("GET", "/api/users/3").body == created.body


@pytest.mark.api
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"name": "Carla"}, id="missing-email"),
        pytest.param({"name": "  ", "email": "carla@example.com"}, id="blank-name"),
        pytest.param({"name": "Carla", "email": " \t "}, id="blank-email"),
        pytest.param({"name": "Carla", "email": 42}, id="non-string-email"),
    ],
)
def test_invalid_create_is_rejected(base_url: str, payload: dict[str, object]) -> None:
    client = ApiClient(base_url)
    response = client.request("POST", "/api/users", payload)
    assert response.status == 400
    assert response.body == {"error": "name and email are required"}
    assert len(client.request("GET", "/api/users").body) == 2


@pytest.mark.api
@pytest.mark.parametrize("email", ["carla.example.com", "@example.com", "carla@"])
def test_create_user_with_malformed_email_is_rejected(base_url: str, email: str) -> None:
    client = ApiClient(base_url)
    response = client.request("POST", "/api/users", {"name": "Carla", "email": email})
    assert response.status == 400
    assert response.body == {"error": "valid email is required"}
    assert len(client.request("GET", "/api/users").body) == 2


@pytest.mark.api
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"", id="empty-body"),
        pytest.param(b'{"name": "Carla",', id="truncated-object"),
        pytest.param(
            b'{"name": "Carla", "email": "carla@example.com"} trailing',
            id="trailing-data",
        ),
        pytest.param(b"\xff", id="invalid-utf8"),
    ],
)
def test_malformed_json_is_rejected_without_creating_user(base_url: str, body: bytes) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    request = Request(
        f"{base_url}/api/users",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=5)
    with error.value as response:
        assert response.status == 400
        assert json.load(response) == {"error": "Invalid JSON"}
    assert client.request("GET", "/api/users").body == original_users


@pytest.mark.api
def test_create_user_with_existing_normalized_email_is_rejected(base_url: str) -> None:
    client = ApiClient(base_url)
    response = client.request("POST", "/api/users", {
        "name": "Another Anna",
        "email": " ANNA@example.com ",
    })
    assert response.status == 409
    assert response.body == {"error": "email already exists"}
    assert len(client.request("GET", "/api/users").body) == 2


@pytest.mark.api
def test_unknown_route_returns_404(base_url: str) -> None:
    response = ApiClient(base_url).request("GET", "/api/unknown")
    assert response.status == 404


@pytest.mark.api
@pytest.mark.contract
@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_unsupported_user_method_returns_405(base_url: str, method: str) -> None:
    request = Request(f"{base_url}/api/users", data=b"{}", method=method)
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=5)
    with error.value as response:
        assert response.status == 405
        assert response.headers["Allow"] == "GET, POST"
        assert json.load(response) == {"error": "Method not allowed"}
