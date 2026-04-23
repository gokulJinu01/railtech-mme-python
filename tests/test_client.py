"""Tests for :class:`railtech_mme.MME` — mocked HTTP via pytest-httpx."""

from __future__ import annotations

import datetime as dt
import json
from typing import Callable

import httpx
import pytest
from pytest_httpx import HTTPXMock

from railtech_mme import (
    MME,
    MMEAuthError,
    MMEClientError,
    MMEError,
    MMERateLimitError,
    MMEServerError,
    MMETimeoutError,
    Pack,
    SaveResult,
)
from railtech_mme.auth import TokenCache
from railtech_mme.models import InjectFilters

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
            "tags": [
                {
                    "label": "dark_chocolate",
                    "origin": "unknown",
                    "scope": "shared",
                    "type": "concept",
                    "confidence": 0.6,
                },
            ],
            "tagsFlat": ["dark_chocolate", "dark", "chocolate"],
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        result = mme.save("I like dark chocolate.", tags=["preferences"], section="personal")

    assert isinstance(result, SaveResult)
    assert result.id == "mem-abc123"
    assert result.status == "created"
    # New in 0.1.1: server-side context surfaced as typed fields
    assert result.success is True
    assert result.org_id == "test-org-id"
    assert result.user_id == "test-user-id"
    assert len(result.tags) == 1
    assert result.tags[0].label == "dark_chocolate"
    assert result.tags_flat == ["dark_chocolate", "dark", "chocolate"]

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
    """``recent`` returns :class:`MemoryBlock` objects matching the real wire shape.

    Mirrors what ``GET /memory/recent`` actually emits: structured ``tags``
    (full :class:`Tag` dicts, not flat strings), ``tagsFlat`` for substring
    search, raw ``content`` (no projected ``title``), and provenance fields
    like ``createdAt`` / ``hash``. Prior to 0.1.1 the SDK parsed this as
    :class:`PackItem`, which crashed because ``title`` was missing.
    """
    _exchange_response(httpx_mock, base_url, test_jwt)
    httpx_mock.add_response(
        method="GET",
        url=f"{base_url}/memory/recent?limit=5",
        json={
            "results": [
                {
                    "id": "mem-1",
                    "orgId": "test-org-id",
                    "userId": "test-user-id",
                    "content": "Dark chocolate is the user's favorite dessert.",
                    "tags": [
                        {
                            "label": "dark_chocolate",
                            "origin": "unknown",
                            "scope": "shared",
                            "type": "concept",
                            "confidence": 0.6,
                        },
                    ],
                    "tagsFlat": ["dark_chocolate", "dark", "chocolate"],
                    "createdAt": "2026-04-23T06:28:00.104Z",
                    "hash": "eec351280c6b59ec",
                },
                {
                    "id": "mem-2",
                    "content": "Allergic to peanuts.",
                    "tags": [],
                    "tagsFlat": [],
                },
            ],
            "userId": "test-user-id",
            "count": 2,
        },
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        items = mme.recent(limit=5)

    assert len(items) == 2
    assert items[0].id == "mem-1"
    assert items[0].content == "Dark chocolate is the user's favorite dessert."
    assert items[0].tags[0].label == "dark_chocolate"
    assert items[0].tags[0].confidence == 0.6
    assert items[0].tags_flat == ["dark_chocolate", "dark", "chocolate"]
    assert items[0].created_at is not None
    assert items[0].hash == "eec351280c6b59ec"
    assert items[1].content == "Allergic to peanuts."
    assert items[1].tags == []


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


# ---------------------------------------------------------------------------
# Day 3.3: error coverage — every status family + transport-level failures
# ---------------------------------------------------------------------------


def test_403_raises_auth_error_without_retry(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """403 is a permission problem, not a stale token — must NOT trigger a retry."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=403,
        json={"error": "Forbidden", "code": "FORBIDDEN"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEAuthError) as exc:
        mme.save("nope")

    assert exc.value.status_code == 403
    # Exactly two requests — exchange + the failed save. No retry.
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (400, MMEClientError),
        (404, MMEClientError),
        (422, MMEClientError),
        (500, MMEServerError),
        (502, MMEServerError),
        (503, MMEServerError),
    ],
)
def test_status_code_maps_to_exception(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
    status_code: int,
    expected_exception: type[MMEError],
) -> None:
    """4xx (non-401/403/429) → MMEClientError; 5xx → MMEServerError."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=status_code,
        json={"error": f"Boom {status_code}"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(expected_exception) as exc:
        mme.save("payload")

    assert exc.value.status_code == status_code
    assert exc.value.message == f"Boom {status_code}"


def test_timeout_raises_mme_timeout_error(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_exception(httpx.ReadTimeout("read timed out"), method="POST")

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMETimeoutError):
        mme.save("slow")


def test_network_error_raises_mme_error(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), method="POST")

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEError) as exc:
        mme.save("offline")

    # Concrete type is the base MMEError, not a subclass
    assert type(exc.value) is MMEError


def test_malformed_json_on_2xx_raises_server_error(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """A 200 with non-JSON body indicates server bug — surface as MMEServerError."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=200,
        content=b"not json at all",
        headers={"Content-Type": "text/plain"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEServerError):
        mme.save("hello")


def test_2xx_with_json_array_raises_server_error(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """The SDK expects a JSON object on success — an array is a server contract violation."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json=[1, 2, 3],
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEServerError) as exc:
        mme.save("hello")

    assert "object" in exc.value.message.lower() or "list" in exc.value.message.lower()


# ---------------------------------------------------------------------------
# Day 3.4: /auth/exchange edge cases beyond 401
# ---------------------------------------------------------------------------


def test_exchange_429_raises_rate_limit(
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange(
        status_code=429,
        response_json={"error": "Too many exchange attempts"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMERateLimitError) as exc:
        mme.save("blocked at the door")

    assert exc.value.status_code == 429


def test_exchange_500_raises_server_error(
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange(
        status_code=500,
        response_json={"error": "auth backend down"},
    )

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEServerError) as exc:
        mme.save("blocked at the door")

    assert exc.value.status_code == 500


def test_exchange_2xx_without_token_raises_server_error(
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """A 200 response that omits the ``token`` field is a contract bug."""
    register_auth_exchange(response_json={"user_id": "u", "org_id": "o"})

    with MME(api_key=api_key, base_url=base_url) as mme, pytest.raises(MMEServerError) as exc:
        mme.save("hello")

    assert "token" in exc.value.message.lower()


def test_jwt_is_cached_across_requests(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """Once exchanged, the JWT should be reused — not re-exchanged on every call."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={"id": "mem-1", "status": "ok"},
        is_reusable=True,
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        mme.save("first")
        mme.save("second")
        mme.save("third")

    requests = httpx_mock.get_requests()
    exchange_calls = [r for r in requests if r.url.path == "/auth/exchange"]
    save_calls = [r for r in requests if r.url.path == "/memory/save"]
    assert len(exchange_calls) == 1, "JWT should have been cached, not re-exchanged"
    assert len(save_calls) == 3


# ---------------------------------------------------------------------------
# Day 3.5: filters and project_id scoping
# ---------------------------------------------------------------------------


def _stub_inject_response(httpx_mock: HTTPXMock, base_url: str) -> None:
    """Minimal /memory/inject success body — items list intentionally empty."""
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/inject",
        json={
            "packId": "pack-empty",
            "seedTags": [],
            "tokenBudget": 2048,
            "totalTokens": 0,
            "items": [],
        },
    )


def test_inject_filters_round_trip_into_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """``InjectFilters`` instance is serialized with camelCase aliases & no None fields."""
    register_auth_exchange()
    _stub_inject_response(httpx_mock, base_url)

    filters = InjectFilters(
        section="work",
        status="completed",
        since=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    with MME(api_key=api_key, base_url=base_url) as mme:
        mme.inject("recap last quarter", filters=filters)

    inject_body = json.loads(httpx_mock.get_requests()[1].content)
    assert inject_body["filters"] == {
        "section": "work",
        "status": "completed",
        "since": "2026-01-01T00:00:00Z",
    }


def test_inject_filters_only_section_omits_none_fields(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """exclude_none=True — fields the caller didn't set must not appear in the body."""
    register_auth_exchange()
    _stub_inject_response(httpx_mock, base_url)

    with MME(api_key=api_key, base_url=base_url) as mme:
        mme.inject("hello", filters=InjectFilters(section="personal"))

    inject_body = json.loads(httpx_mock.get_requests()[1].content)
    assert inject_body["filters"] == {"section": "personal"}


def test_constructor_project_id_propagates_to_inject_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    _stub_inject_response(httpx_mock, base_url)

    with MME(api_key=api_key, base_url=base_url, project_id="proj-default") as mme:
        mme.inject("hello")

    body = json.loads(httpx_mock.get_requests()[1].content)
    assert body["projectId"] == "proj-default"


def test_per_call_project_id_overrides_constructor_default(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    _stub_inject_response(httpx_mock, base_url)

    with MME(api_key=api_key, base_url=base_url, project_id="proj-default") as mme:
        mme.inject("hello", project_id="proj-override")

    body = json.loads(httpx_mock.get_requests()[1].content)
    assert body["projectId"] == "proj-override"


def test_no_project_id_omits_field_from_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    _stub_inject_response(httpx_mock, base_url)

    with MME(api_key=api_key, base_url=base_url) as mme:
        mme.inject("hello")

    body = json.loads(httpx_mock.get_requests()[1].content)
    assert "projectId" not in body
    assert body["orgId"] == "test-org-id"  # but orgId is always present
