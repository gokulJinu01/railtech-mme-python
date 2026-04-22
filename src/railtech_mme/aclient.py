"""Async client for the MME HTTP API — mirror of :mod:`railtech_mme.client`.

Example::

    import asyncio
    from railtech_mme import AsyncMME

    async def main():
        async with AsyncMME(api_key="mme_live_...") as mme:
            await mme.save("hello")
            pack = await mme.inject("hello")
            print(pack.items[0].excerpt)

    asyncio.run(main())
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Optional

import httpx

from railtech_mme.auth import TokenCache
from railtech_mme.client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, _resolve_api_key
from railtech_mme.exceptions import MMEError
from railtech_mme.models import (
    FeedbackRequest,
    InjectFilters,
    InjectRequest,
    Pack,
    PackItem,
    SaveRequest,
    SaveResult,
)


class AsyncMME:
    """Async MME client. See :class:`~railtech_mme.client.MME` for parameter docs."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        project_id: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        resolved_key = _resolve_api_key(api_key)
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._project_id = project_id
        self._timeout = timeout

        self._owned_http_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
        )

        self._tokens = TokenCache(api_key=resolved_key)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncMME":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP pool."""
        if self._owned_http_client:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Public API — signatures mirror the sync client 1:1
    # ------------------------------------------------------------------

    async def save(
        self,
        content: str,
        *,
        tags: Optional[list[str]] = None,
        section: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SaveResult:
        """Persist a memory block. See :meth:`MME.save`."""
        del content, tags, section, status, source
        raise NotImplementedError("TODO Day 2: async POST /memory/save")

    async def inject(
        self,
        prompt: str,
        *,
        token_budget: int = 2048,
        limit: Optional[int] = None,
        filters: Optional[InjectFilters] = None,
        project_id: Optional[str] = None,
        debug: bool = False,
    ) -> Pack:
        """Retrieve a memory pack. See :meth:`MME.inject`."""
        del prompt, token_budget, limit, filters, project_id, debug
        raise NotImplementedError("TODO Day 2: async POST /memory/inject")

    async def feedback(
        self,
        *,
        pack_id: str,
        accepted: bool,
        item_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Record pack feedback. See :meth:`MME.feedback`."""
        del pack_id, accepted, item_ids, tags, project_id
        raise NotImplementedError("TODO Day 2: async POST /memory/feedback")

    async def recent(
        self,
        *,
        limit: int = 20,
        section: Optional[str] = None,
    ) -> list[PackItem]:
        """Return recent memory blocks."""
        del limit, section
        raise NotImplementedError("TODO Day 2: async GET /memory/recent")

    async def delete(self, memory_id: str) -> None:
        """Delete a memory block."""
        del memory_id
        raise NotImplementedError("TODO Day 2: async DELETE /memory/:id")

    async def tags(self) -> list[str]:
        """Return all tags for the authenticated org."""
        raise NotImplementedError("TODO Day 2: async GET /tags/all")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Async version of :meth:`MME._request`. Same contract."""
        del method, path, json_body, params
        raise NotImplementedError("TODO Day 2: async HTTP dispatcher")

    async def _ensure_jwt(self) -> str:
        """Async version of :meth:`MME._ensure_jwt`."""
        raise NotImplementedError("TODO Day 2: async JWT exchange")

    _unused_refs = (FeedbackRequest, InjectRequest, SaveRequest, MMEError)
