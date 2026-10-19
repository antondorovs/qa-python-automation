import pytest

from qa_python_lab.api_client import ApiClient

pytestmark = [pytest.mark.api, pytest.mark.contract]


def test_client_handles_no_content_response(base_url: str) -> None:
    response = ApiClient(base_url).request("OPTIONS", "/api/users")

    assert response.status == 204
    assert response.body is None


def test_client_handles_empty_success_and_error_responses_in_sequence(base_url: str) -> None:
    client = ApiClient(base_url)
    original_users = client.request("GET", "/api/users").body
    original_health = client.request("GET", "/api/health").body

    empty = client.request("OPTIONS", "/api/users")
    assert empty.status == 204
    assert empty.body is None

    invalid = client.request("POST", "/api/users", {"name": "Carla"})
    assert invalid.status == 400
    assert invalid.body == {"error": "name and email are required"}
    assert client.request("GET", "/api/health").body == original_health

    created = client.request(
        "POST", "/api/users", {"name": " Carla ", "email": " CARLA@example.com "}
    )
    assert created.status == 201
    assert created.body == {
        "id": original_health["next_user_id"],
        "name": "Carla",
        "email": "carla@example.com",
    }

    empty_after_creation = client.request("OPTIONS", "/api/users?limit=1")
    assert empty_after_creation.status == 204
    assert empty_after_creation.body is None

    duplicate = client.request(
        "POST", "/api/users", {"name": "Another Carla", "email": " CARLA@example.com "}
    )
    assert duplicate.status == 409
    assert duplicate.body == {"error": "email already exists"}

    fetched = client.request("GET", f"/api/users/{created.body['id']}")
    assert fetched.status == 200
    assert fetched.body == created.body
    assert client.request("GET", "/api/users").body == original_users + [created.body]
