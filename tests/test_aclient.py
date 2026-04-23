"""Tests for :class:`railtech_mme.AsyncMME` — async parity with the sync client.

Every behavior covered in :mod:`tests.test_client` for the sync client should
hold identically here. If a test in this module diverges from its sync sibling,
that's a bug in one of the two clients — keep them in lockstep.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Callable

import httpx
import pytest
from pytest_httpx import HTTPXMock

from railtech_mme import (
    AsyncMME,
    MMEAuthError,
    MMEClientError,
    MMEError,
    MMERateLimitError,
    MMEServerError,
    MMETimeoutError,
    Pack,
    SaveResult,
)
from railtech_mme.models import InjectFilters

# ---------------------------------------------------------------------------
# Structural tests — no HTTP
# ---------------------------------------------------------------------------


async def test_constructor_requires_api_key() -> None:
    with pytest.raises(ValueError, match="No API key"):
        AsyncMME()


async def test_constructor_reads_env(monkeypatch: pytest.MonkeyPatch, api_key: str) -> None:
    monkeypatch.setenv("RAILTECH_API_KEY", api_key)
    client = AsyncMME()
    assert client._api_key == api_key
    await client.aclose()


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_save_success(
    httpx_mock: HTTPXMock,
    api_key: str,
    test_jwt: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={"id": "mem-async-1", "status": "created", "success": True},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        result = await mme.save("hello async", tags=["async"], section="work")

    assert isinstance(result, SaveResult)
    assert result.id == "mem-async-1"

    save_req = httpx_mock.get_requests()[1]
    assert save_req.url.path == "/memory/save"
    assert save_req.headers["Authorization"] == f"Bearer {test_jwt}"
    assert json.loads(save_req.content) == {
        "content": "hello async",
        "tags": ["async"],
        "section": "work",
    }


async def test_inject_injects_org_id_into_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/inject",
        json={
            "packId": "pack-async",
            "seedTags": ["async"],
            "tokenBudget": 1024,
            "totalTokens": 0,
            "items": [],
        },
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        pack = await mme.inject("what's up", token_budget=1024)

    assert isinstance(pack, Pack)
    assert pack.pack_id == "pack-async"

    body = json.loads(httpx_mock.get_requests()[1].content)
    assert body["orgId"] == "test-org-id"
    assert body["prompt"] == "what's up"
    assert body["tokenBudget"] == 1024
    assert body["debug"] is False


async def test_feedback_returns_none_and_sends_correct_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/feedback",
        json={"status": "success"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        result = await mme.feedback(pack_id="pack-async", accepted=True)

    assert result is None
    body = json.loads(httpx_mock.get_requests()[1].content)
    assert body == {
        "packId": "pack-async",
        "accepted": True,
        "itemIds": [],
        "tags": [],
        "orgId": "test-org-id",
    }


async def test_recent_unwraps_results(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="GET",
        url=f"{base_url}/memory/recent?limit=3",
        json={
            "results": [
                {"id": "a", "title": "A", "tags": [], "excerpt": "", "tokenCost": 1},
                {"id": "b", "title": "B", "tags": [], "excerpt": "", "tokenCost": 2},
            ]
        },
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        items = await mme.recent(limit=3)

    assert [i.id for i in items] == ["a", "b"]


async def test_delete_sends_delete_method(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="DELETE",
        url=f"{base_url}/memory/mem-async",
        json={"status": "deleted"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        await mme.delete("mem-async")

    delete_req = httpx_mock.get_requests()[1]
    assert delete_req.method == "DELETE"
    assert delete_req.url.path == "/memory/mem-async"


async def test_tags_unwraps_tags_key(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="GET",
        url=f"{base_url}/tags/all",
        json={"tags": ["x", "y"]},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        tags = await mme.tags()

    assert tags == ["x", "y"]


# ---------------------------------------------------------------------------
# Error paths — same taxonomy as the sync client
# ---------------------------------------------------------------------------


async def test_401_triggers_one_retry_then_success(
    httpx_mock: HTTPXMock,
    api_key: str,
    test_jwt: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=401,
        json={"error": "Token expired"},
    )
    register_auth_exchange(token=test_jwt + "-refreshed")
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={"id": "mem-retry"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        result = await mme.save("retry me")

    assert result.id == "mem-retry"
    assert len(httpx_mock.get_requests()) == 4


async def test_403_raises_auth_error_without_retry(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=403,
        json={"error": "Forbidden"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        with pytest.raises(MMEAuthError) as exc:
            await mme.save("nope")

    assert exc.value.status_code == 403
    assert len(httpx_mock.get_requests()) == 2


async def test_429_raises_rate_limit_with_retry_after_header(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=429,
        headers={"Retry-After": "30"},
        json={"error": "Slow down"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        with pytest.raises(MMERateLimitError) as exc:
            await mme.save("too fast")

    assert exc.value.retry_after == 30


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (400, MMEClientError),
        (422, MMEClientError),
        (500, MMEServerError),
        (503, MMEServerError),
    ],
)
async def test_status_code_maps_to_exception(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
    status_code: int,
    expected_exception: type[MMEError],
) -> None:
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        status_code=status_code,
        json={"error": f"Boom {status_code}"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        with pytest.raises(expected_exception) as exc:
            await mme.save("payload")

    assert exc.value.status_code == status_code


async def test_timeout_raises_mme_timeout_error(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange()
    httpx_mock.add_exception(httpx.ReadTimeout("read timed out"), method="POST")

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        with pytest.raises(MMETimeoutError):
            await mme.save("slow")


async def test_invalid_api_key_exchange_raises_auth_error(
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    register_auth_exchange(
        status_code=401,
        response_json={"error": "Invalid or inactive API key"},
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        with pytest.raises(MMEAuthError) as exc:
            await mme.save("never gets through")

    assert exc.value.status_code == 401


async def test_jwt_is_cached_across_requests(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """Async client should also cache the JWT and not re-exchange per call."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/save",
        json={"id": "ok"},
        is_reusable=True,
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        await mme.save("a")
        await mme.save("b")

    requests = httpx_mock.get_requests()
    exchange_calls = [r for r in requests if r.url.path == "/auth/exchange"]
    assert len(exchange_calls) == 1


async def test_inject_filters_round_trip_into_body(
    httpx_mock: HTTPXMock,
    api_key: str,
    base_url: str,
    register_auth_exchange: Callable[..., None],
) -> None:
    """Datetime coercion must work the same on the async client."""
    register_auth_exchange()
    httpx_mock.add_response(
        method="POST",
        url=f"{base_url}/memory/inject",
        json={"packId": "p", "seedTags": [], "tokenBudget": 2048, "totalTokens": 0, "items": []},
    )

    filters = InjectFilters(
        section="work",
        since=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    async with AsyncMME(api_key=api_key, base_url=base_url) as mme:
        await mme.inject("recap", filters=filters)

    body = json.loads(httpx_mock.get_requests()[1].content)
    assert body["filters"] == {"section": "work", "since": "2026-01-01T00:00:00Z"}
