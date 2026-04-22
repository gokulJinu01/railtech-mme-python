"""Tests for :class:`railtech_mme.MME` — mocked HTTP via pytest-httpx."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from railtech_mme import (
    MME,
    MMEAuthError,
    MMEError,
    MMERateLimitError,
    Pack,
    SaveResult,
)
from railtech_mme.auth import TokenCache

# ---------------------------------------------------------------------------
# Structural / smoke tests — no HTTP
# ---------------------------------------------------------------------------


def test_version_exported() -> None:
    import railtech_mme

    assert railtech_mme.__version__


def test_constructor_requires_api_key() -> None:
    with pytest.raises(ValueError, match="No API key"):
        MME()


def test_constructor_reads_env(monkeypatch: pytest.MonkeyPatch, api_key: str) -> None:
    monkeypatch.setenv("RAILTECH_API_KEY", api_key)
    client = MME()
    assert client._api_key == api_key
    client.close()


def test_exception_hierarchy() -> None:
    for cls in (MMEAuthError, MMERateLimitError):
        assert issubclass(cls, MMEError)


def test_rate_limit_retry_after() -> None:
    err = MMERateLimitError("slow down", retry_after=60)
    assert err.retry_after == 60
    assert err.status_code == 429


def test_token_cache_future_jwt_is_returned(test_jwt: str) -> None:
    cache = TokenCache(api_key="mme_live_x")
    cache.set(test_jwt)
    assert cache.jwt == test_jwt


def test_token_cache_expired_jwt_is_dropped(expired_jwt: str) -> None:
    cache = TokenCache(api_key="mme_live_x")
    cache.set(expired_jwt)
    assert cache.jwt is None


def test_token_cache_invalidate(test_jwt: str) -> None:
    cache = TokenCache(api_key="mme_live_x")
    cache.set(test_jwt)
    cache.invalidate()
    assert cache.jwt is None


# ---------------------------------------------------------------------------
# HTTP tests — pytest-httpx mocks
# ---------------------------------------------------------------------------


def _exchange_response(httpx_mock: HTTPXMock, base_url: str, test_jwt: str) -> None:
    """Register the standard /auth/exchange success response."""
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/auth/exchange",
        json={
            "token": test_jwt,
            "user_id": "test-user-id",
            "org_id": "test-org-id",
            "expires_in": 86400,
            "token_type": "Bearer",
        },
    )


def test_save_success(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={
            "id": "mem-abc123",
            "message": "Saved",
            "status": "created",
            "success": True,
            "userId": "test-user-id",
            "orgId": "test-org-id",
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        result = mme.save("I like dark chocolate.", tags=["preferences"], section="personal")

    assert isinstance(result, SaveResult)
    assert result.id == "mem-abc123"
    assert result.status == "created"

    # Verify request details
    requests = httpx_mock.get_requests()
    assert len(requests) == 2

    exchange = requests[0]
    assert exchange.url.path == "/auth/exchange"
    assert json.loads(exchange.content) == {"apiKey": api_key}

    save = requests[1]
    assert save.url.path == "/memory/save"
    assert save.headers["Authorization"] == f"Bearer {test_jwt}"
    assert json.loads(save.content) == {
        "content": "I like dark chocolate.",
        "tags": ["preferences"],
        "section": "personal",
    }


def test_inject_injects_org_id_into_body(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/inject",
        json={
            "packId": "pack-xyz",
            "seedTags": ["chocolate"],
            "bounds": {"M": 32, "D": 2, "B": 128, "alpha": 0.85, "theta": 0.05},
            "tokenBudget": 1024,
            "totalTokens": 128,
            "items": [
                {
                    "id": "mem-abc",
                    "title": "Preference",
                    "tags": ["chocolate", "food"],
                    "excerpt": "I like dark chocolate.",
                    "tokenCost": 64,
                    "score": {
                        "activation": 0.9,
                        "recency": 0.8,
                        "importance": 1.0,
                        "statusBonus": 0.0,
                        "diversityPenalty": 0.0,
                        "total": 1.05,
                    },
                }
            ],
            "rationale": {"paths": [], "notes": ["seed matched"]},
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        pack = mme.inject("What do I like to eat?", token_budget=1024)

    assert isinstance(pack, Pack)
    assert pack.pack_id == "pack-xyz"
    assert pack.token_budget == 1024
    assert len(pack.items) == 1
    assert pack.items[0].id == "mem-abc"
    assert pack.items[0].score is not None
    assert pack.items[0].score.total == pytest.approx(1.05)

    inject_req = httpx_mock.get_requests()[1]
    body = json.loads(inject_req.content)
    # orgId must be auto-injected from the /auth/exchange response
    assert body["orgId"] == "test-org-id"
    assert body["prompt"] == "What do I like to eat?"
    assert body["tokenBudget"] == 1024
    assert body["debug"] is False


def test_feedback_returns_none_and_sends_correct_body(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/feedback",
        json={"status": "success", "event": {"packId": "pack-xyz"}},
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        result = mme.feedback(
            pack_id="pack-xyz",
            accepted=True,
            item_ids=["mem-abc"],
            tags=["chocolate"],
        )

    assert result is None
    fb_body = json.loads(httpx_mock.get_requests()[1].content)
    assert fb_body == {
        "packId": "pack-xyz",
        "accepted": True,
        "itemIds": ["mem-abc"],
        "tags": ["chocolate"],
        "orgId": "test-org-id",
    }


def test_recent_unwraps_results(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="GET",
        url=f"{base_url}/memory/recent?limit=5",
        json={
            "results": [
                {"id": "mem-1", "title": "First", "tags": [], "excerpt": "a", "tokenCost": 10},
                {"id": "mem-2", "title": "Second", "tags": [], "excerpt": "b", "tokenCost": 12},
            ],
            "userId": "test-user-id",
            "count": 2,
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        items = mme.recent(limit=5)

    assert len(items) == 2
    assert items[0].id == "mem-1"
    assert items[1].excerpt == "b"


def test_delete_sends_delete_method(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="DELETE",
        url=f"{base_url}/memory/mem-abc",
        json={"status": "deleted", "success": True},
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        mme.delete("mem-abc")

    delete_req = httpx_mock.get_requests()[1]
    assert delete_req.method == "DELETE"
    assert delete_req.url.path == "/memory/mem-abc"


def test_tags_unwraps_tags_key(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="GET",
        url=f"{base_url}/tags/all",
        json={
            "userId": "test-user-id",
            "tags": ["chocolate", "food", "preferences"],
            "count": 3,
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        tags = mme.tags()

    assert tags == ["chocolate", "food", "preferences"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_401_triggers_one_retry_then_success(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    """First call: stale JWT → 401. SDK invalidates, re-exchanges, retries once → 200."""
    # First exchange (to get initial JWT)
    _exchange_response(httpx_mock, base_url, test_jwt)
    # First save attempt → 401
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=401,
        json={"error": "Token expired", "code": "JWT_EXPIRED"},
    )
    # Retry: re-exchange (returns a new JWT)
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/auth/exchange",
        json={
            "token": test_jwt + "-refreshed",
            "user_id": "test-user-id",
            "org_id": "test-org-id",
        },
    )
    # Second save attempt → 200
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={"id": "mem-retry-success", "status": "ok", "success": True},
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        result = mme.save("hello after refresh")

    assert result.id == "mem-retry-success"
    # 4 total requests: exchange, save(401), exchange-retry, save(200)
    assert len(httpx_mock.get_requests()) == 4


def test_429_raises_rate_limit_with_retry_after_header(
    httpx_mock: HTTPXMock, api_key: str, test_jwt: str, base_url: str
) -> None:
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=429,
        headers={"Retry-After": "42"},
        json={"error": "Rate limited", "code": "RATE_LIMITED"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMERateLimitError) as exc:
        mme.save("too fast")

    assert exc.value.retry_after == 42
    assert exc.value.status_code == 429


def test_invalid_api_key_exchange_raises_auth_error(
    httpx_mock: HTTPXMock, api_key: str, base_url: str
) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/auth/exchange",
        status_code=401,
        json={"error": "Invalid or inactive API key", "code": "INVALID_KEY"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEAuthError) as exc:
        mme.save("never gets through")

    assert exc.value.status_code == 401
    assert "Invalid" in exc.value.message
