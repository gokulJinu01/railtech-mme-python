"""Smoke tests + Day-1 fill-in targets for :class:`railtech_mme.MME`.

Each test that raises ``NotImplementedError`` today will pass automatically
once the corresponding HTTP body is implemented in ``client.py``. Do not
rewrite the tests first — implement the client method, then xfail becomes a
real pass.
"""

from __future__ import annotations

import pytest

from railtech_mme import (
    MME,
    MMEAuthError,
    MMEError,
    MMERateLimitError,
    Pack,
    SaveResult,
)
from railtech_mme.auth import TokenCache


# ----------------------------------------------------------------------------
# Structural / smoke tests — should pass today, no HTTP required
# ----------------------------------------------------------------------------


def test_version_exported() -> None:
    import railtech_mme

    assert railtech_mme.__version__


def test_constructor_requires_api_key() -> None:
    with pytest.raises(ValueError, match="No API key"):
        MME()


def test_constructor_reads_env(monkeypatch: pytest.MonkeyPatch, api_key: str) -> None:
    monkeypatch.setenv("RAILTECH_API_KEY", api_key)
    client = MME()
    assert client._api_key == api_key  # noqa: SLF001
    client.close()


def test_exception_hierarchy() -> None:
    # Any specific error can be caught as MMEError — that is the contract.
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


# ----------------------------------------------------------------------------
# Day-1 targets — these fail with NotImplementedError today.
# Mark xfail so `pytest` is green; they flip to pass automatically as each
# method gets implemented.
# ----------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="Day 1: wire POST /memory/save")
def test_save_returns_memory_id(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        result = mme.save("test content")
    assert isinstance(result, SaveResult)
    assert result.id


@pytest.mark.xfail(strict=True, reason="Day 1: wire POST /memory/inject")
def test_inject_returns_pack(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        pack = mme.inject("test prompt")
    assert isinstance(pack, Pack)
    assert pack.pack_id


@pytest.mark.xfail(strict=True, reason="Day 1: wire POST /memory/feedback")
def test_feedback_returns_none(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        mme.feedback(pack_id="pack-123", accepted=True)


@pytest.mark.xfail(strict=True, reason="Day 1: wire GET /memory/recent")
def test_recent_returns_list(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        items = mme.recent(limit=5)
    assert isinstance(items, list)


@pytest.mark.xfail(strict=True, reason="Day 1: wire DELETE /memory/:id")
def test_delete_returns_none(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        mme.delete("memory-id-123")


@pytest.mark.xfail(strict=True, reason="Day 1: wire GET /tags/all")
def test_tags_returns_list(api_key: str) -> None:
    with MME(api_key=api_key) as mme:
        tags = mme.tags()
    assert isinstance(tags, list)
