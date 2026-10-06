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
    assert response.body == {"status": "ok", "user_count": 2, "next_user_id": 3}


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
def test_list_users_honors_limit_query_parameter(base_url: str) -> None:
    client = ApiClient(base_url)

    response = client.request("GET", "/api/users?limit=1")

    assert response.status == 200
    assert response.body == [{"id": 1, "name": "Anna Smith", "email": "anna@example.com"}]


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
@pytest.mark.contract
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("  ", id="spaces"),
        pytest.param("\t", id="tab"),
        pytest.param("\n", id="newline"),
        pytest.param(" \t\r\n ", id="mixed-whitespace"),
        pytest.param(None, id="null"),
        pytest.param(42, id="non-string"),
    ],
)
def test_invalid_user_name_does_not_change_users_or_consume_id(base_url: str, name: object) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body

    rejected = client.request("POST", "/api/users", {"name": name, "email": "casey@example.com"})
    assert rejected.status == 400
    assert rejected.body == {"error": "name and email are required"}
    assert client.request("GET", "/api/users").body == original_users

    created = client.request(
        "POST", "/api/users", {"name": "Casey", "email": "casey@example.com"}
    )
    assert created.status == 201
    assert created.body == {"id": 3, "name": "Casey", "email": "casey@example.com"}
    assert client.request("GET", "/api/users").body == original_users + [created.body]


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
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/users", id="collection"),
        pytest.param("/api/users?limit=1", id="collection-query"),
    ],
)
def test_users_options_returns_supported_methods(base_url: str, path: str) -> None:
    request = Request(f"{base_url}{path}", method="OPTIONS")
    with urlopen(request, timeout=5) as response:
        assert response.status == 204
        assert response.headers["Allow"] == "GET, POST, OPTIONS"
        assert response.headers["Content-Length"] == "0"
        assert response.read() == b""


@pytest.mark.api
@pytest.mark.contract
@pytest.mark.parametrize("body", [b"", b'{"name":'])
def test_users_options_preserves_user_state(base_url: str, body: bytes) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    request = Request(
        f"{base_url}/api/users",
        data=body,
        method="OPTIONS",
        headers={"Content-Type": "application/json"},
    )

    with urlopen(request, timeout=5) as response:
        assert response.status == 204
        assert response.read() == b""

    assert client.request("GET", "/api/users").body == original_users
    created = client.request(
        "POST", "/api/users", {"name": "Carla", "email": "carla@example.com"}
    )
    assert created.status == 201
    assert created.body["id"] == 3
    assert client.request("GET", "/api/users").body == original_users + [created.body]


@pytest.mark.api
@pytest.mark.contract
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/users/1", id="existing-user"),
        pytest.param("/api/users/999", id="missing-user"),
        pytest.param("/api/unknown", id="unknown-route"),
    ],
)
def test_options_on_other_routes_returns_404_without_changing_users(
    base_url: str, path: str
) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    request = Request(f"{base_url}{path}", method="OPTIONS")

    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=5)
    with error.value as response:
        response_body = response.read()
        assert response.status == 404
        assert response.headers.get_content_type() == "application/json"
        assert response.headers.get_content_charset() == "utf-8"
        assert response.headers["Content-Length"] == str(len(response_body))
        assert json.loads(response_body) == {"error": "Resource not found"}

    assert client.request("GET", "/api/users").body == original_users


@pytest.mark.api
@pytest.mark.contract
@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/users", id="collection"),
        pytest.param("/api/users/1", id="existing-user"),
        pytest.param("/api/users/999", id="missing-user"),
        pytest.param("/api/users?limit=1", id="collection-query"),
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            b'{"name": "Carla", "email": "carla@example.com"}', id="valid-user"
        ),
        pytest.param(b'{"name":', id="malformed-json"),
    ],
)
def test_unsupported_user_method_returns_405(
    base_url: str, method: str, path: str, body: bytes
) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    request = Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=5)
    with error.value as response:
        response_body = response.read()
        assert response.status == 405
        assert response.headers["Allow"] == "GET, POST"
        assert response.headers.get_content_type() == "application/json"
        assert response.headers.get_content_charset() == "utf-8"
        assert response.headers["Content-Length"] == str(len(response_body))
        assert json.loads(response_body) == {"error": "Method not allowed"}

    assert client.request("GET", "/api/users").body == original_users
    created = client.request(
        "POST", "/api/users", {"name": "Carla", "email": "carla@example.com"}
    )
    assert created.status == 201
    assert created.body == {"id": 3, "name": "Carla", "email": "carla@example.com"}
    assert client.request("GET", "/api/users/3").body == created.body
    assert client.request("GET", "/api/users").body == original_users + [created.body]
