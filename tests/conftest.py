"""Pytest fixtures for the railtech-mme test suite."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator

import pytest

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
