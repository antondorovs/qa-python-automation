import pytest

from qa_python_lab.api_client import ApiClient

pytestmark = [pytest.mark.api, pytest.mark.contract]


def test_client_handles_no_content_response(base_url: str) -> None:
    response = ApiClient(base_url).request("OPTIONS", "/api/users")

    assert response.status == 204
    assert response.body is None
