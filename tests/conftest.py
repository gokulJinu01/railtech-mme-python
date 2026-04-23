"""Pytest fixtures for the railtech-mme test suite."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from typing import Any, Callable

import pytest
from pytest_httpx import HTTPXMock

TEST_API_KEY = "mme_live_test_fixture_key_1234567890"
TEST_BASE_URL = "https://api.railtech.test"


def _make_test_jwt(ttl_seconds: int = 3600) -> str:
    """Construct an unsigned test JWT with an ``exp`` claim in the future."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload_dict = {
        "user_id": "test-user",
        "org_id": "test-org",
        "exp": int(time.time()) + ttl_seconds,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()
    signature = "test-signature"
    return f"{header}.{payload}.{signature}"


@pytest.fixture
def test_jwt() -> str:
    """A valid-looking JWT with a future ``exp`` claim."""
    return _make_test_jwt()


@pytest.fixture
def expired_jwt() -> str:
    """A JWT whose ``exp`` claim is in the past."""
    return _make_test_jwt(ttl_seconds=-10)


@pytest.fixture
def api_key() -> str:
    """Sample API key used in all tests."""
    return TEST_API_KEY


@pytest.fixture
def base_url() -> str:
    """Sample base URL for pytest-httpx matching."""
    return TEST_BASE_URL


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent a real RAILTECH_API_KEY from leaking into tests."""
    monkeypatch.delenv("RAILTECH_API_KEY", raising=False)
    yield


@pytest.fixture
def register_auth_exchange(
    httpx_mock: HTTPXMock, base_url: str, test_jwt: str
) -> Callable[..., None]:
    """Return a callable that registers a /auth/exchange mock response.

    Default response is a successful exchange with ``test_jwt`` and
    ``test-org-id``. Pass any keyword arg to override individual fields, or
    ``status_code=...`` and ``response_json=...`` to fake an error.

    Usage::

        def test_something(register_auth_exchange, httpx_mock, ...):
            register_auth_exchange()                       # success
            register_auth_exchange(status_code=429)        # rate limited
            register_auth_exchange(token="other-jwt")      # custom token
    """

    def _register(
        *,
        status_code: int = 200,
        response_json: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> None:
        if response_json is None:
            response_json = {
                "token": test_jwt,
                "user_id": "test-user-id",
                "org_id": "test-org-id",
                "expires_in": 86400,
                "token_type": "Bearer",
            }
        if overrides:
            response_json = {**response_json, **overrides}
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/auth/exchange",
            status_code=status_code,
            json=response_json,
        )

    return _register
